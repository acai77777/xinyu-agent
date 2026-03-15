"""数据查询和聚合服务"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, func, case, text
from database import async_session, SalesData


def _escape_like(value: str) -> str:
    """转义 LIKE 通配符"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# 包含 fabric_code 字段的表（跨表搜索用）
CROSS_SEARCH_TABLES = {
    "面料货盘": ("fabric_cargo", "fabric_code, category_1, category_2, composition_cn, weight_after, width, elasticity, function_feature, cost_per_yard, system_comment"),
    "特惠货盘": ("special_cargo", "fabric_code, status, category_1, category_2, composition, weight_after, cost, fixed_price, clearance_price, stock"),
    "新品清单": ("new_products", "fabric_code, date, craft, category_1, category_2, composition_cn, weight_after, width, comment"),
    "主推备货": ("recommended_stock", "fabric_code, production_available, spot_available, total_available"),
    "在产明细": ("production_detail", "fabric_code, production_no, confirmed_qty, warehoused_qty, delivery_date"),
    "现货库存": ("spot_inventory", "fabric_code, today_stock"),
    "月度下单": ("domestic_monthly", "fabric_code, in_cargo, month_1, month_2, month_3, month_4, total"),
    "ERP合同": ("sales_data", "fabric_code, customer, quantity, sign_date, department"),
}

# 数据源名称与工具的映射
TOOL_SOURCE_MAP = {
    "tool_query_sales": "erp",
    "tool_query_fabric_cargo": "dingtalk",
    "tool_query_inventory": "tencent",
    "tool_query_monthly_orders": "dingtalk",
    "tool_query_special_cargo": "dingtalk",
    "tool_query_new_products": "dingtalk",
    "tool_cross_table_search": "dingtalk",
}


class DataService:
    # 需要排除的部门
    EXCLUDED_DEPARTMENTS = ["公司推荐库存", "公司", "公司大货", "1", ""]

    @staticmethod
    def _to_ma(col):
        """将数量列按单位统一转换为码（1码 = 0.9144米）"""
        return case(
            (SalesData.unit == "米", col / 0.9144),
            else_=col,
        )

    def _date_range(self, start_date: Optional[str], end_date: Optional[str], days: int):
        """计算日期范围，优先使用 start_date/end_date，回退到 days"""
        if start_date and end_date:
            return start_date, end_date
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        until = datetime.now().strftime("%Y-%m-%d")
        return since, until

    async def _get_last_sync_time(self, source: str) -> str:
        """查询指定数据源的最后成功同步时间"""
        async with async_session() as session:
            row = (await session.execute(text("""
                SELECT finished_at FROM sync_log
                WHERE source = :source AND status = 'success'
                ORDER BY finished_at DESC LIMIT 1
            """), {"source": source})).first()
        if row and row[0]:
            return str(row[0])[:16]  # "2026-02-28 08:30"
        return "未知"

    async def get_sales_summary(self, days: int = 7, start_date: str = None, end_date: str = None) -> dict:
        """获取指定时间范围的合同汇总"""
        since, until = self._date_range(start_date, end_date, days)
        async with async_session() as session:
            result = await session.execute(
                select(
                    func.count(SalesData.id).label("total_orders"),
                    func.sum(self._to_ma(SalesData.quantity)).label("total_quantity"),
                    func.sum(SalesData.ship_quantity).label("total_shipped"),
                    func.sum(SalesData.balance).label("total_balance"),
                ).where(SalesData.sign_date >= since)
                .where(SalesData.sign_date <= until)
                .where(SalesData.department.notin_(self.EXCLUDED_DEPARTMENTS))
            )
            row = result.one()
            return {
                "start_date": since,
                "end_date": until,
                "total_orders": row.total_orders or 0,
                "total_quantity": float(row.total_quantity or 0),
                "total_shipped": float(row.total_shipped or 0),
                "total_balance": float(row.total_balance or 0),
            }

    async def get_sales_by_date(self, days: int = 30, start_date: str = None, end_date: str = None) -> list[dict]:
        """按签订日期聚合合同数据"""
        since, until = self._date_range(start_date, end_date, days)
        async with async_session() as session:
            result = await session.execute(
                select(
                    SalesData.sign_date,
                    func.sum(self._to_ma(SalesData.quantity)).label("quantity"),
                    func.count(SalesData.id).label("orders"),
                ).where(SalesData.sign_date >= since)
                .where(SalesData.sign_date <= until)
                .where(SalesData.department.notin_(self.EXCLUDED_DEPARTMENTS))
                .group_by(SalesData.sign_date)
                .order_by(SalesData.sign_date)
            )
            return [{"date": r.sign_date, "quantity": float(r.quantity or 0), "orders": r.orders} for r in result.all()]

    async def get_sales_by_product(self, days: int = 30, start_date: str = None, end_date: str = None) -> list[dict]:
        """按布编聚合合同数据"""
        since, until = self._date_range(start_date, end_date, days)
        async with async_session() as session:
            result = await session.execute(
                select(
                    SalesData.fabric_code,
                    func.sum(self._to_ma(SalesData.quantity)).label("quantity"),
                    func.count(SalesData.id).label("orders"),
                ).where(SalesData.sign_date >= since)
                .where(SalesData.sign_date <= until)
                .where(SalesData.fabric_code != "")
                .where(SalesData.department.notin_(self.EXCLUDED_DEPARTMENTS))
                .group_by(SalesData.fabric_code)
                .order_by(func.sum(self._to_ma(SalesData.quantity)).desc())
            )
            return [{"product": r.fabric_code, "quantity": float(r.quantity or 0), "orders": r.orders} for r in result.all()]

    # ================================================================
    # Tool 方法 —— 供 AI Function Calling 调用
    # ================================================================

    async def tool_query_sales(self, query_type: str = "overview", rank_by: str = "fabric",
                               days: int = 30, top_n: int = 10) -> str:
        """ERP销售数据查询：概况/趋势/排行"""
        sync_time = await self._get_last_sync_time("erp")
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        until = datetime.now().strftime("%Y-%m-%d")
        excluded = ",".join(f"'{d}'" for d in self.EXCLUDED_DEPARTMENTS)

        if query_type == "overview":
            summary = await self.get_sales_summary(days)
            trend = await self.get_sales_by_date(days)
            ctx = f"ERP业务合同统计（{since} ~ {until}，数据更新于: {sync_time}）\n"
            ctx += f"- 总合同数: {summary['total_orders']}\n"
            ctx += f"- 总数量: {summary['total_quantity']:.0f} 码\n"
            ctx += f"- 总发货量: {summary['total_shipped']:.0f} 码\n"
            ctx += f"- 总结存: {summary['total_balance']:.0f} 码\n"
            ctx += "\n每日签约趋势（最近10天）:\n| 日期 | 数量(码) | 合同数 |\n| --- | --- | --- |\n"
            for s in trend[-10:]:
                ctx += f"| {s['date']} | {s['quantity']:.0f} | {s['orders']} |\n"
            return ctx

        elif query_type == "trend":
            trend = await self.get_sales_by_date(days)
            ctx = f"每日签约趋势（{since} ~ {until}，数据更新于: {sync_time}）:\n| 日期 | 数量(码) | 合同数 |\n| --- | --- | --- |\n"
            for s in trend:
                ctx += f"| {s['date']} | {s['quantity']:.0f} | {s['orders']} |\n"
            return ctx

        elif query_type == "ranking":
            col_map = {
                "fabric": ("fabric_code", "布编"),
                "customer": ("customer", "客户"),
                "department": ("department", "业务组"),
                "salesperson": ("salesperson", "销售员"),
            }
            col_name, label = col_map.get(rank_by, ("fabric_code", "布编"))
            extra_where = f"AND {col_name} != ''" if rank_by != "department" else ""
            limit_clause = f"LIMIT {top_n}" if rank_by != "department" else ""

            async with async_session() as session:
                rows = (await session.execute(text(f"""
                    SELECT {col_name},
                           SUM(CASE WHEN unit='米' THEN quantity/0.9144 ELSE quantity END) AS qty,
                           COUNT(*) AS cnt
                    FROM sales_data
                    WHERE sign_date >= :since
                      {extra_where}
                      AND department NOT IN ({excluded})
                    GROUP BY {col_name}
                    ORDER BY qty DESC
                    {limit_clause}
                """), {"since": since})).all()

            ctx = f"{label}排行（{since}起，{'TOP' + str(top_n) if limit_clause else '全部'}，数据更新于: {sync_time}）:\n"
            ctx += f"| {label} | 数量(码) | 合同数 |\n| --- | --- | --- |\n"
            for r in rows:
                ctx += f"| {r[0]} | {r[1]:.0f} | {r[2]} |\n"
            return ctx

        return "未知的查询类型"

    async def tool_query_fabric_cargo(self, fabric_code: str = None) -> str:
        """面料货盘信息查询（含产品属性）"""
        sync_time = await self._get_last_sync_time("dingtalk")
        async with async_session() as session:
            if fabric_code:
                escaped = _escape_like(fabric_code)
                rows = (await session.execute(text("""
                    SELECT fabric_code, category_1, category_2, composition_cn, weight_after,
                           width, elasticity, function_feature, cost_per_yard, system_comment,
                           first_stock_date, lifecycle, selling_point, elasticity_rate
                    FROM fabric_cargo
                    WHERE fabric_code LIKE :code ESCAPE '\\'
                    ORDER BY fabric_code
                """), {"code": f"%{escaped}%"})).all()
            else:
                total = (await session.execute(text(
                    "SELECT COUNT(*) FROM fabric_cargo"
                ))).scalar()

                rows = (await session.execute(text("""
                    SELECT fabric_code, category_1, category_2, composition_cn, weight_after,
                           width, elasticity, function_feature, cost_per_yard, system_comment,
                           first_stock_date, lifecycle
                    FROM fabric_cargo
                    ORDER BY fabric_code
                    LIMIT 50
                """))).all()

        if not rows:
            return "未找到面料货盘数据" + (f"（布编: {fabric_code}）" if fabric_code else "")

        ctx = ""

        if fabric_code:
            ctx += f"面料货盘查询结果（共{len(rows)}款，数据更新于: {sync_time}）:\n"
            ctx += "| 布编 | 一级品类 | 二级品类 | 成分 | 克重 | 幅宽 | 弹力 | 功能特性 | 成本(元/码) | 系统评语 | 首次入库 | 生命周期(月) | 卖点 | 弹力率 |\n"
            ctx += "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            for r in rows:
                ctx += "| " + " | ".join(str(r[i] or '') for i in range(14)) + " |\n"
        else:
            # 无布编时追加统计摘要
            async with async_session() as session:
                # 按一级品类统计
                cat_rows = (await session.execute(text(
                    "SELECT category_1, COUNT(*) AS cnt FROM fabric_cargo WHERE category_1 IS NOT NULL AND category_1 != '' GROUP BY category_1 ORDER BY cnt DESC"
                ))).all()
                # 按成分统计（取前10）
                comp_rows = (await session.execute(text(
                    "SELECT composition_cn, COUNT(*) AS cnt FROM fabric_cargo WHERE composition_cn IS NOT NULL AND composition_cn != '' GROUP BY composition_cn ORDER BY cnt DESC LIMIT 10"
                ))).all()
                # 成本范围
                cost_range = (await session.execute(text("""
                    SELECT MIN(CAST(REPLACE(REPLACE(cost_per_yard, ',', ''), ' ', '') AS REAL)),
                           MAX(CAST(REPLACE(REPLACE(cost_per_yard, ',', ''), ' ', '') AS REAL))
                    FROM fabric_cargo
                    WHERE cost_per_yard IS NOT NULL AND cost_per_yard != ''
                """))).first()

            ctx += f"面料货盘统计摘要（共{total}款）：\n"
            if cat_rows:
                ctx += "- 按一级品类分布：" + "、".join(f"{r[0]} {r[1]}款" for r in cat_rows if r[0]) + "\n"
            if comp_rows:
                ctx += "- 主要成分分布（前10）：" + "、".join(f"{r[0]} {r[1]}款" for r in comp_rows if r[0]) + "\n"
            if cost_range and cost_range[0] is not None:
                ctx += f"- 成本范围：{cost_range[0]:.2f} ~ {cost_range[1]:.2f} 元/码\n"
            ctx += "\n"

            ctx += f"详细数据（展示前50条，数据更新于: {sync_time}）:\n"
            ctx += "| 布编 | 一级品类 | 二级品类 | 成分 | 克重 | 幅宽 | 弹力 | 功能特性 | 成本(元/码) | 系统评语 | 首次入库 | 生命周期(月) |\n"
            ctx += "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            for r in rows:
                ctx += "| " + " | ".join(str(r[i] or '') for i in range(12)) + " |\n"
            if total > 50:
                ctx += f"\n\n（共 {total} 条记录，仅展示前 50 条。请提供布编号缩小查询范围）"

        return ctx

    async def tool_query_inventory(self, fabric_code: str = None) -> str:
        """库存查询：主推备货 + 在产明细 + 现货"""
        sync_time = await self._get_last_sync_time("tencent")
        ctx = f"库存信息（数据更新于: {sync_time}）\n"
        ctx += '【字段说明】"现货可用"=除去客户锁单后的实际可用库存；"现货库存"=仓库总库存（含已被客户预定/锁单的部分）。判断是否需要补货应以"现货可用"为准。\n\n'
        code_filter = ""
        params = {}
        if fabric_code:
            escaped = _escape_like(fabric_code)
            code_filter = "WHERE fabric_code LIKE :code ESCAPE '\\'"
            params = {"code": f"%{escaped}%"}

        has_data = False
        async with async_session() as session:
            # 主推产品备货库存
            rows = (await session.execute(text(f"""
                SELECT fabric_code, production_available, spot_available, total_available
                FROM recommended_stock
                {code_filter}
                ORDER BY fabric_code
            """), params)).all()

            if rows:
                has_data = True
                ctx += f"主推产品备货库存（共{len(rows)}款）:\n"
                ctx += "| 布编 | 在产可用 | 现货可用 | 总可用 |\n| --- | --- | --- | --- |\n"
                for r in rows:
                    ctx += f"| {r[0] or ''} | {r[1] or ''} | {r[2] or ''} | {r[3] or ''} |\n"

            # 在产明细
            rows = (await session.execute(text(f"""
                SELECT fabric_code, production_no, confirmed_qty, warehoused_qty, delivery_date
                FROM production_detail
                {code_filter}
                ORDER BY fabric_code
            """), params)).all()

            if rows:
                has_data = True
                ctx += f"\n在产明细（共{len(rows)}条）:\n"
                ctx += "| 布编 | 生产单号 | 确认数量 | 已进仓 | 交期 |\n| --- | --- | --- | --- | --- |\n"
                for r in rows:
                    ctx += f"| {r[0] or ''} | {r[1] or ''} | {r[2] or ''} | {r[3] or ''} | {r[4] or ''} |\n"

            # 现货库存按布编聚合
            spot_filter = "WHERE fabric_code IS NOT NULL AND fabric_code != ''"
            if fabric_code:
                escaped = _escape_like(fabric_code)
                spot_filter += " AND fabric_code LIKE :code ESCAPE '\\'"
            rows = (await session.execute(text(f"""
                SELECT fabric_code,
                       SUM(CAST(REPLACE(REPLACE(today_stock, ',', ''), ' ', '') AS REAL)) AS total_stock
                FROM spot_inventory
                {spot_filter}
                GROUP BY fabric_code
                ORDER BY total_stock DESC
            """), params)).all()

            if rows:
                has_data = True
                ctx += f"\n现货库存汇总（共{len(rows)}款，含已预定/锁单部分，非实际可用）:\n"
                ctx += "| 布编 | 库存码数(含锁单) |\n| --- | --- |\n"
                for r in rows:
                    ctx += f"| {r[0]} | {r[1]:.0f} |\n"

        if not has_data:
            return "未找到库存数据" + (f"（布编: {fabric_code}）" if fabric_code else "")
        return ctx

    async def tool_query_monthly_orders(self, fabric_code: str = None) -> str:
        """25年内销月度下单数据查询"""
        sync_time = await self._get_last_sync_time("dingtalk")
        code_filter = ""
        params = {}
        if fabric_code:
            escaped = _escape_like(fabric_code)
            code_filter = "WHERE fabric_code LIKE :code ESCAPE '\\'"
            params = {"code": f"%{escaped}%"}

        async with async_session() as session:
            if not fabric_code:
                total = (await session.execute(text(
                    "SELECT COUNT(*) FROM domestic_monthly"
                ))).scalar()

            rows = (await session.execute(text(f"""
                SELECT fabric_code, in_cargo, month_1, rank_1,
                       month_2, rank_2, month_3, rank_3,
                       month_4, rank_4, total
                FROM domestic_monthly
                {code_filter}
                ORDER BY CAST(REPLACE(REPLACE(total, ',', ''), ' ', '') AS REAL) DESC
                {"LIMIT 50" if not fabric_code else ""}
            """), params)).all()

        if not rows:
            return "未找到月度下单数据" + (f"（布编: {fabric_code}）" if fabric_code else "")

        if fabric_code:
            ctx = f"25年内销月度下单数据（共{len(rows)}款，数据更新于: {sync_time}）:\n"
        else:
            ctx = f"25年内销月度下单数据（共{total}款，展示前50条，数据更新于: {sync_time}）:\n"
        ctx += "| 布编 | 在货盘 | 1月 | 排名 | 2月 | 排名 | 3月 | 排名 | 4月 | 排名 | 总计 |\n"
        ctx += "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        for r in rows:
            ctx += "| " + " | ".join(str(r[i] or '') for i in range(11)) + " |\n"

        if not fabric_code and total > 50:
            ctx += f"\n\n（共 {total} 条记录，仅展示前 50 条。请提供布编号缩小查询范围）"

        return ctx

    async def tool_query_special_cargo(self, fabric_code: str = None) -> str:
        """特惠货盘查询"""
        sync_time = await self._get_last_sync_time("dingtalk")
        code_filter = ""
        params = {}
        if fabric_code:
            escaped = _escape_like(fabric_code)
            code_filter = "WHERE fabric_code LIKE :code ESCAPE '\\'"
            params = {"code": f"%{escaped}%"}

        async with async_session() as session:
            if not fabric_code:
                total = (await session.execute(text(
                    "SELECT COUNT(*) FROM special_cargo"
                ))).scalar()

            rows = (await session.execute(text(f"""
                SELECT fabric_code, status, cost, fixed_price, clearance_price, stock,
                       category_1, category_2, composition, weight_after
                FROM special_cargo
                {code_filter}
                ORDER BY fabric_code
                {"LIMIT 50" if not fabric_code else ""}
            """), params)).all()

        if not rows:
            return "未找到特惠货盘数据" + (f"（布编: {fabric_code}）" if fabric_code else "")

        ctx = ""

        # 无布编时追加统计摘要
        if not fabric_code:
            async with async_session() as session:
                # 按状态统计
                status_rows = (await session.execute(text(
                    "SELECT status, COUNT(*) AS cnt FROM special_cargo GROUP BY status ORDER BY cnt DESC"
                ))).all()
                # 按一级品类统计
                cat_rows = (await session.execute(text(
                    "SELECT category_1, COUNT(*) AS cnt FROM special_cargo WHERE category_1 IS NOT NULL AND category_1 != '' GROUP BY category_1 ORDER BY cnt DESC"
                ))).all()
                # 库存TOP5
                stock_rows = (await session.execute(text("""
                    SELECT fabric_code, CAST(REPLACE(REPLACE(stock, ',', ''), ' ', '') AS REAL) AS stock_num
                    FROM special_cargo
                    WHERE stock IS NOT NULL AND stock != ''
                    ORDER BY stock_num DESC LIMIT 5
                """))).all()
                # 成本范围
                cost_range = (await session.execute(text("""
                    SELECT MIN(CAST(REPLACE(REPLACE(cost, ',', ''), ' ', '') AS REAL)),
                           MAX(CAST(REPLACE(REPLACE(cost, ',', ''), ' ', '') AS REAL))
                    FROM special_cargo
                    WHERE cost IS NOT NULL AND cost != ''
                """))).first()

            ctx += f"特惠货盘统计摘要（共{total}款）：\n"
            if status_rows:
                ctx += "- 按状态：" + "、".join(f"{r[0]} {r[1]}款" for r in status_rows if r[0]) + "\n"
            if cat_rows:
                ctx += "- 按一级品类：" + "、".join(f"{r[0]} {r[1]}款" for r in cat_rows if r[0]) + "\n"
            if stock_rows:
                ctx += "- 库存TOP5：" + "、".join(f"{r[0]} ({r[1]:.0f}码)" for r in stock_rows if r[0]) + "\n"
            if cost_range and cost_range[0] is not None:
                ctx += f"- 成本范围：{cost_range[0]:.2f} ~ {cost_range[1]:.2f} 元/码\n"
            ctx += "\n"

        if fabric_code:
            ctx += f"特惠货盘（共{len(rows)}款，数据更新于: {sync_time}）:\n"
        else:
            ctx += f"详细数据（展示前50条，数据更新于: {sync_time}）:\n"
        ctx += "| 布编 | 状态 | 成本(元/码) | 定价(元/码) | 沽清价(元/码) | 库存 | 一级品类 | 二级品类 | 成分 | 克重 |\n"
        ctx += "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        for r in rows:
            ctx += "| " + " | ".join(str(r[i] or '') for i in range(10)) + " |\n"

        if not fabric_code and total > 50:
            ctx += f"\n\n（共 {total} 条记录，仅展示前 50 条。请提供布编号缩小查询范围）"

        return ctx

    async def tool_query_new_products(self, fabric_code: str = None) -> str:
        """新品清单查询"""
        sync_time = await self._get_last_sync_time("dingtalk")
        code_filter = ""
        params = {}
        if fabric_code:
            escaped = _escape_like(fabric_code)
            code_filter = "WHERE fabric_code LIKE :code ESCAPE '\\'"
            params = {"code": f"%{escaped}%"}

        async with async_session() as session:
            if not fabric_code:
                total = (await session.execute(text(
                    "SELECT COUNT(*) FROM new_products"
                ))).scalar()

            rows = (await session.execute(text(f"""
                SELECT fabric_code, date, craft, category_1, category_2,
                       composition_cn, weight_after, width, comment
                FROM new_products
                {code_filter}
                ORDER BY fabric_code
                {"LIMIT 50" if not fabric_code else ""}
            """), params)).all()

        if not rows:
            return "未找到新品数据" + (f"（布编: {fabric_code}）" if fabric_code else "")

        ctx = ""

        # 无布编时追加统计摘要
        if not fabric_code:
            async with async_session() as session:
                # 按一级品类统计
                cat_rows = (await session.execute(text(
                    "SELECT category_1, COUNT(*) AS cnt FROM new_products WHERE category_1 IS NOT NULL AND category_1 != '' GROUP BY category_1 ORDER BY cnt DESC"
                ))).all()
                # 按工艺统计
                craft_rows = (await session.execute(text(
                    "SELECT craft, COUNT(*) AS cnt FROM new_products WHERE craft IS NOT NULL AND craft != '' GROUP BY craft ORDER BY cnt DESC"
                ))).all()
                # 最近上新日期
                latest_date = (await session.execute(text(
                    "SELECT MAX(date) FROM new_products WHERE date IS NOT NULL AND date != ''"
                ))).scalar()

            ctx += f"新品清单统计摘要（共{total}款）：\n"
            if cat_rows:
                ctx += "- 按一级品类分布：" + "、".join(f"{r[0]} {r[1]}款" for r in cat_rows if r[0]) + "\n"
            if craft_rows:
                ctx += "- 按工艺分布：" + "、".join(f"{r[0]} {r[1]}款" for r in craft_rows if r[0]) + "\n"
            if latest_date:
                ctx += f"- 最近上新日期：{latest_date}\n"
            ctx += "\n"

        if fabric_code:
            ctx += f"新品清单（共{len(rows)}款，数据更新于: {sync_time}）:\n"
        else:
            ctx += f"详细数据（展示前50条，数据更新于: {sync_time}）:\n"
        ctx += "| 布编 | 日期 | 工艺 | 一级品类 | 二级品类 | 成分 | 克重 | 幅宽 | 评语 |\n"
        ctx += "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        for r in rows:
            ctx += "| " + " | ".join(str(r[i] or '') for i in range(9)) + " |\n"

        if not fabric_code and total > 50:
            ctx += f"\n\n（共 {total} 条记录，仅展示前 50 条。请提供布编号缩小查询范围）"

        return ctx

    async def tool_cross_table_search(self, fabric_code: str) -> str:
        """根据布编跨表搜索全部相关数据"""
        if not fabric_code or len(fabric_code) < 2:
            return "请提供至少2个字符的布编号"

        escaped = _escape_like(fabric_code)
        found_any = False
        table_data: dict[str, list] = {}  # label -> rows
        detail_parts: list[str] = []

        async with async_session() as session:
            for label, (table, columns) in CROSS_SEARCH_TABLES.items():
                rows = (await session.execute(text(f"""
                    SELECT {columns} FROM {table}
                    WHERE fabric_code LIKE :code ESCAPE '\\'
                    LIMIT 20
                """), {"code": f"%{escaped}%"})).all()

                if rows:
                    found_any = True
                    table_data[label] = rows
                    col_names = [c.strip() for c in columns.split(",")]
                    part = f"\n### {label}（{len(rows)}条）\n"
                    part += "| " + " | ".join(col_names) + " |\n"
                    part += "| " + " | ".join("---" for _ in col_names) + " |\n"
                    for r in rows:
                        part += "| " + " | ".join(str(r[i] or '') for i in range(len(col_names))) + " |\n"
                    detail_parts.append(part)

        if not found_any:
            return f"未在任何数据表中找到布编 {fabric_code} 的相关数据"

        # ---- 构建数据摘要 ----
        summary_lines = []

        # 货盘信息
        if "面料货盘" in table_data:
            r = table_data["面料货盘"][0]  # 取第一条
            # columns: fabric_code, category_1, category_2, composition_cn, weight_after, width, elasticity, function_feature, cost_per_yard, system_comment
            summary_lines.append(f"- 货盘：一级品类={r[1] or '—'}，二级品类={r[2] or '—'}，成分={r[3] or '—'}，克重={r[4] or '—'}，幅宽={r[5] or '—'}，弹力={r[6] or '—'}，成本={r[8] or '—'}元/码")

        # 库存信息（主推备货 + 现货）
        stock_parts = []
        if "主推备货" in table_data:
            r = table_data["主推备货"][0]
            # columns: fabric_code, production_available, spot_available, total_available
            stock_parts.append(f"现货可用 {r[2] or 0}码，在产可用 {r[1] or 0}码，总可用 {r[3] or 0}码")
        if "现货库存" in table_data:
            # columns: fabric_code, today_stock — 可能有多行颜色，求和
            try:
                total_spot = sum(float(str(r[1] or '0').replace(',', '').replace(' ', '')) for r in table_data["现货库存"])
                stock_parts.append(f"现货库存(含锁单) {total_spot:.0f}码")
            except (ValueError, TypeError):
                pass
        if stock_parts:
            summary_lines.append("- 库存：" + "；".join(stock_parts))

        # 在产明细
        if "在产明细" in table_data:
            prod_rows = table_data["在产明细"]
            # columns: fabric_code, production_no, confirmed_qty, warehoused_qty, delivery_date
            try:
                total_confirmed = sum(float(str(r[2] or '0').replace(',', '').replace(' ', '')) for r in prod_rows)
            except (ValueError, TypeError):
                total_confirmed = 0
            # 最近交期
            dates = [str(r[4] or '') for r in prod_rows if r[4]]
            nearest_date = min(dates) if dates else "—"
            summary_lines.append(f"- 在产：共{len(prod_rows)}单，总确认数量 {total_confirmed:.0f}码，最近交期 {nearest_date}")

        # 月度下单
        if "月度下单" in table_data:
            r = table_data["月度下单"][0]
            # columns: fabric_code, in_cargo, month_1, month_2, month_3, month_4, total
            in_cargo_str = "是" if r[1] and str(r[1]).strip() not in ('', '0', '否') else "否"
            summary_lines.append(f"- 月度下单：总计 {r[6] or 0}码，是否在货盘：{in_cargo_str}")

        # ERP合同
        if "ERP合同" in table_data:
            erp_rows = table_data["ERP合同"]
            # columns: fabric_code, customer, quantity, sign_date, department
            try:
                total_qty = sum(float(str(r[2] or '0').replace(',', '').replace(' ', '')) for r in erp_rows)
            except (ValueError, TypeError):
                total_qty = 0
            summary_lines.append(f"- ERP合同：共{len(erp_rows)}份，总数量 {total_qty:.0f}码")

        # 特惠
        summary_lines.append(f"- 特惠：{'有' if '特惠货盘' in table_data else '无'}")

        # 新品
        summary_lines.append(f"- 新品：{'有' if '新品清单' in table_data else '无'}")

        # ---- 拼装最终结果 ----
        ctx = f"布编 {fabric_code} 跨表搜索结果:\n\n"
        ctx += "【数据摘要】\n"
        ctx += "\n".join(summary_lines)
        ctx += "\n\n详细数据："
        ctx += "".join(detail_parts)
        return ctx


data_service = DataService()
