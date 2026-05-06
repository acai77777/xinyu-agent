"""
心情打卡路由——每日心情记录 / 历史 / 统计
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_db
from api.routes_auth import get_current_user

router = APIRouter()


class CheckinRequest(BaseModel):
    score: int = Field(..., ge=1, le=10, description="心情分数 1-10")
    note: str = Field(default="", max_length=500, description="可选备注")


@router.post("/checkin")
async def create_checkin(req: CheckinRequest, user_id: str = Depends(get_current_user)):
    """记录一次心情打卡"""
    now = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO mood_checkins (user_id, score, note, created_at) VALUES (?, ?, ?, ?)",
            (user_id, req.score, req.note, now),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "score": req.score,
            "note": req.note,
            "created_at": now,
        }
    finally:
        await db.close()


@router.get("/today")
async def get_today(user_id: str = Depends(get_current_user)):
    """获取今日最近一次打卡"""
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, score, note, created_at FROM mood_checkins "
            "WHERE user_id = ? AND created_at LIKE ? "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, f"{today_prefix}%"),
        )
        row = await cursor.fetchone()
        if not row:
            return {"checkin": None}
        return {
            "checkin": {
                "id": row[0],
                "score": row[1],
                "note": row[2],
                "created_at": row[3],
            }
        }
    finally:
        await db.close()


@router.get("/history")
async def get_history(
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = Depends(get_current_user),
):
    """获取最近 N 天的打卡记录"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, score, note, created_at FROM mood_checkins "
            "WHERE user_id = ? AND created_at >= datetime('now', ?) "
            "ORDER BY created_at DESC",
            (user_id, f"-{days} days"),
        )
        rows = await cursor.fetchall()
        return {
            "records": [
                {"id": r[0], "score": r[1], "note": r[2], "created_at": r[3]}
                for r in rows
            ]
        }
    finally:
        await db.close()


@router.get("/stats")
async def get_stats(
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = Depends(get_current_user),
):
    """获取统计数据：平均分、最高、最低、趋势方向"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT AVG(score), MAX(score), MIN(score), COUNT(*) FROM mood_checkins "
            "WHERE user_id = ? AND created_at >= datetime('now', ?)",
            (user_id, f"-{days} days"),
        )
        row = await cursor.fetchone()
        avg_score, max_score, min_score, count = row

        # 计算趋势：比较前半段和后半段平均分
        trend = "stable"
        if count and count >= 2:
            half_days = days // 2
            cursor2 = await db.execute(
                "SELECT AVG(score) FROM mood_checkins "
                "WHERE user_id = ? AND created_at >= datetime('now', ?) "
                "AND created_at < datetime('now', ?)",
                (user_id, f"-{days} days", f"-{half_days} days"),
            )
            first_half = (await cursor2.fetchone())[0]

            cursor3 = await db.execute(
                "SELECT AVG(score) FROM mood_checkins "
                "WHERE user_id = ? AND created_at >= datetime('now', ?)",
                (user_id, f"-{half_days} days"),
            )
            second_half = (await cursor3.fetchone())[0]

            if first_half and second_half:
                diff = second_half - first_half
                if diff > 0.5:
                    trend = "up"
                elif diff < -0.5:
                    trend = "down"

        return {
            "avg_score": round(avg_score, 1) if avg_score else None,
            "max_score": max_score,
            "min_score": min_score,
            "count": count,
            "trend": trend,
        }
    finally:
        await db.close()
