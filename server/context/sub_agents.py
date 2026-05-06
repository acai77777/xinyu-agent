"""
子 Agent 统一编排器——按需分发深度任务，并行执行，超时降级。

替代：
- loop.py 的 _background_assess()  → analysis agent
- loop.py 的知识库直接检索          → knowledge agent
- routes_chat.py 的策略后台生成     → strategy agent（仅冷启动时）

每个子 Agent 使用隔离的上下文窗口，只返回精炼摘要给主 Agent。
"""
import asyncio
import json
import logging

from config import settings
from context.cache import cache

logger = logging.getLogger(__name__)


class SubAgentOrchestrator:
    """
    并行分发子 Agent 任务，收集精炼结果。

    返回:
        {
            "analysis":  {"assessment": str, "emotion": dict} | None,
            "knowledge": str | None,
        }
    """

    async def dispatch(
        self,
        user_msg: str,
        session_id: str,
        recent_messages: list[dict],
        user_profile_summary: str = "",
        presenting_issue: str = "",
    ) -> dict:
        tasks: dict[str, asyncio.Task] = {}

        # 分析 Agent（替代 _background_assess）
        if self._needs_analysis(user_msg):
            tasks["analysis"] = asyncio.create_task(
                self._run_analysis_agent(user_msg, recent_messages, user_profile_summary)
            )

        # 知识检索 Agent
        if self._needs_knowledge(user_msg, presenting_issue):
            tasks["knowledge"] = asyncio.create_task(
                self._run_knowledge_agent(user_msg, presenting_issue)
            )

        if not tasks:
            return {}

        # 带超时的并行等待
        done, pending = await asyncio.wait(
            tasks.values(),
            timeout=settings.sub_agent_timeout,
        )

        # 取消超时的任务
        for t in pending:
            t.cancel()
            logger.warning("[SubAgent] Task cancelled due to timeout")

        # 收集结果 + 缓存降级
        results: dict = {}
        for name, task in tasks.items():
            if task in done and not task.cancelled():
                try:
                    value = task.result()
                    if value is not None:
                        results[name] = value
                        cache.put(session_id, name, json.dumps(value, ensure_ascii=False))
                except Exception as e:
                    logger.warning(f"[SubAgent:{name}] error: {e}")
                    self._try_cache_fallback(results, session_id, name)
            else:
                # 超时：尝试缓存
                self._try_cache_fallback(results, session_id, name)

        return results

    # ── 子 Agent 实现 ──────────────────────────────────────

    async def _run_analysis_agent(
        self, user_msg: str, recent: list[dict], profile: str,
    ) -> dict | None:
        """
        深度分析子 Agent——独立上下文，返回结构化评估。
        替代 loop.py 的 _background_assess()。
        """
        from agent.loop import _llm_chat
        from llm_client import get_light_model

        # 构建精简上下文（最近6轮）
        context_parts = []
        for msg in recent[-6:]:
            role_label = "用户" if msg["role"] == "user" else "AI"
            content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
            context_parts.append(f"{role_label}：{content[:200]}")

        if context_parts:
            eval_input = f"最近对话：\n" + "\n".join(context_parts) + f"\n\n当前用户消息：{user_msg}"
        else:
            eval_input = user_msg

        system = (
            "简要评估用户情绪和可能的认知模式。注意结合对话上下文判断——"
            "用户当前的情绪可能是前几轮的延续或转变。"
        )
        if profile:
            system += f"\n用户画像：{profile}"
        system += (
            '\n返回JSON格式：\n'
            '{"assessment": "一句话概括（需体现情绪变化趋势）", '
            '"emotion": {"primary": "情绪名", "intensity": 1-10}}'
        )

        try:
            result = await _llm_chat(
                system=system,
                messages=[{"role": "user", "content": eval_input}],
                model_override=get_light_model(),
                max_tokens=200,
            )
            parsed = json.loads(result["text"].strip())
            assessment = parsed.get("assessment", "")
            emotion = parsed.get("emotion")
            if assessment and len(assessment) > 5:
                return {"assessment": assessment, "emotion": emotion}
        except Exception:
            pass
        return None

    async def _run_knowledge_agent(
        self, query: str, issue: str,
    ) -> str | None:
        """
        知识检索子 Agent——隔离的检索 + 轻量模型精选。
        替代 loop.py _inject_full_context 中的直接检索注入。
        """
        from knowledge.knowledge_base import search_books_semantic
        from agent.loop import _llm_chat
        from llm_client import get_light_model

        try:
            search_query = f"{issue} {query}" if issue else query
            raw_results = await asyncio.to_thread(
                search_books_semantic, search_query, 5,
            )
        except Exception:
            return None

        if not raw_results:
            return None

        # 过滤低相似度
        candidates = []
        for r in raw_results:
            if r.get("similarity", 0) > 0.25:
                source = f"{r.get('book', '')}·{r.get('chapter', '')}"
                candidates.append(f"【{source}】{r['content'][:200]}")

        if not candidates:
            return None

        # 如果候选少于等于2条，直接返回不需要精选
        if len(candidates) <= 2:
            return "\n".join(candidates)

        # 用轻量模型从候选中精选 1-2 条
        try:
            result = await _llm_chat(
                system=(
                    "从以下心理学知识中，选出与用户问题最相关的1-2条，"
                    "用自己的话重述要点（不超过150字）。"
                    f"\n用户问题：{query}"
                ),
                messages=[{"role": "user", "content": "\n".join(candidates)}],
                model_override=get_light_model(),
                max_tokens=200,
            )
            return result["text"]
        except Exception:
            # LLM 精选失败，直接返回前2条原始结果
            return "\n".join(candidates[:2])

    # ── 触发条件 ───────────────────────────────────────────

    @staticmethod
    def _needs_analysis(msg: str) -> bool:
        """几乎所有消息都需要情绪评估，仅跳过极短输入"""
        return len(msg) >= 5

    @staticmethod
    def _needs_knowledge(msg: str, issue: str) -> bool:
        """有明确议题且消息有一定长度时才检索（中文1字=1 char）"""
        return bool(issue) and len(msg) > 8

    # ── 缓存降级 ───────────────────────────────────────────

    @staticmethod
    def _try_cache_fallback(
        results: dict, session_id: str, agent_name: str,
    ) -> None:
        cached = cache.get(session_id, agent_name)
        if cached:
            try:
                results[agent_name] = json.loads(cached)
            except (json.JSONDecodeError, TypeError):
                results[agent_name] = cached
            logger.info(f"[SubAgent:{agent_name}] timeout/error, using cached result")
