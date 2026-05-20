"""
对话历史压缩器——滑动窗口 + LLM 摘要 + 安全消息钉住 + 工具结果压缩

核心逻辑：
1. 保留最近 N 轮原始对话（滑动窗口）
2. 将更早的非安全消息压缩为结构化摘要（轻量 LLM）
3. 安全关键消息永远保留原始内容，不参与压缩
4. 工具调用结果压缩为关键信息摘要

集成方式：摘要注入 system prompt（context_hints），不构造假消息
"""
import json
import logging

from config import settings
from safety.crisis_detector import CRISIS_KEYWORDS

logger = logging.getLogger(__name__)

# ── 从 crisis_detector 拉取安全关键词，保持单一数据源 ──
_SAFETY_KEYWORDS: set[str] = set()
for _kw_list in CRISIS_KEYWORDS.values():
    _SAFETY_KEYWORDS.update(_kw_list)


# ====================================================================
# 对话压缩器
# ====================================================================

class ConversationCompressor:
    """
    滑动窗口 + 渐进式 LLM 摘要。

    返回值约定：
        compress_if_needed() → (处理后的消息列表, 摘要文本 | None)
        摘要文本由调用方注入 system prompt，不放入 messages。
    """

    def __init__(
        self,
        keep_recent: int | None = None,
        compress_threshold: int | None = None,
        max_incremental_rounds: int = 5,
    ):
        self.keep_recent = keep_recent or settings.compress_keep_recent
        self.compress_threshold = compress_threshold or settings.compress_threshold
        self.max_incremental_rounds = max_incremental_rounds

    # ── 主入口 ──────────────────────────────────────────────

    async def compress_if_needed(
        self,
        messages: list[dict],
        session_id: str,
        prior_summary: str | None = None,
        prior_compressed_count: int | None = None,
        incremental_rounds: int = 0,
    ) -> tuple[list[dict], str | None]:
        """
        检查是否需要压缩，按需执行。

        参数:
            messages:               完整对话历史
            session_id:             会话 ID（日志用）
            prior_summary:          上一次压缩的摘要（增量压缩用）
            prior_compressed_count: 上一次压缩覆盖的非安全早期消息条数
            incremental_rounds:     已连续增量压缩次数

        返回:
            (保留的消息列表, 摘要文本 | None)
            摘要文本为 None 时表示未触发压缩。
        """
        turn_count = sum(1 for m in messages if m["role"] == "user")
        if turn_count <= self.compress_threshold:
            return messages, prior_summary

        split_idx = self._find_split_point(messages, self.keep_recent)
        early = messages[:split_idx]
        recent = messages[split_idx:]

        # 分离安全关键消息
        safety_pinned, compressible = self._partition_safety(early)

        if not compressible:
            return safety_pinned + recent, prior_summary

        # 决定增量 vs 全量
        use_incremental = (
            prior_summary is not None
            and prior_compressed_count is not None
            and incremental_rounds < self.max_incremental_rounds
        )

        if use_incremental:
            new_messages = compressible[prior_compressed_count:]
            if not new_messages:
                return safety_pinned + recent, prior_summary
            summary = await self._incremental_compress(
                prior_summary, new_messages, session_id,
            )
        else:
            summary = await self._summarize(compressible, session_id)

        logger.info(
            "[Compressor] session=%s turns=%d early=%d pinned=%d compressed=%d",
            session_id[:8], turn_count, len(early),
            len(safety_pinned), len(compressible),
        )

        return safety_pinned + recent, summary

    # ── 安全消息分区 ────────────────────────────────────────

    @staticmethod
    def _is_safety_critical(msg: dict) -> bool:
        content = msg.get("content", "")
        if not isinstance(content, str):
            return False
        return any(kw in content for kw in _SAFETY_KEYWORDS)

    def _partition_safety(
        self, messages: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """将消息分为 (安全关键, 可压缩) 两组，保持各自内部顺序。"""
        pinned, compressible = [], []
        for msg in messages:
            if self._is_safety_critical(msg):
                pinned.append(msg)
            else:
                compressible.append(msg)
        return pinned, compressible

    # ── 滑动窗口分割 ────────────────────────────────────────

    @staticmethod
    def _find_split_point(messages: list[dict], keep_recent: int) -> int:
        """从后往前数 keep_recent 轮 user 消息，返回分割索引。"""
        user_count = 0
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                user_count += 1
                if user_count >= keep_recent:
                    return i
        return 0

    # ── LLM 摘要 ────────────────────────────────────────────

    async def _summarize(self, messages: list[dict], session_id: str) -> str:
        """全量压缩：将一段对话消息压缩为结构化摘要。"""
        from agent.loop import _llm_chat
        from llm_client import get_light_model

        prompt = (
            "请将以下心理咨询对话压缩为结构化摘要，保留：\n"
            "1. 用户提到的核心问题和情绪状态\n"
            "2. 咨询师已采用的干预方法和用户反应\n"
            "3. 重要的事实信息（人物、事件、时间）\n"
            "4. 用户的洞察和转变时刻\n\n"
            "⚠️ 特别注意：如果对话中出现过任何自伤/自杀/危机相关内容，"
            "必须在摘要中明确标注 [安全标记]，绝对不得遗漏。\n"
            "控制总长度在 300 字以内。"
        )
        # 将消息列表转为可读文本传给轻量模型
        readable = self._messages_to_readable(messages)
        result = await _llm_chat(
            system=prompt,
            messages=[{"role": "user", "content": readable}],
            model_override=get_light_model(),
            max_tokens=settings.medium_max_tokens,
        )
        return result["text"] or ""

    async def _incremental_compress(
        self, old_summary: str, new_messages: list[dict], session_id: str,
    ) -> str:
        """增量压缩：在旧摘要基础上整合新对话内容。"""
        from agent.loop import _llm_chat
        from llm_client import get_light_model

        readable = self._messages_to_readable(new_messages)
        prompt = (
            "你之前生成过一份心理咨询对话摘要。现在有新的对话内容需要整合。\n\n"
            "规则：\n"
            "1. 保留旧摘要中仍然重要的信息\n"
            "2. 整合新对话的要点（情绪变化、新议题、干预反应）\n"
            "3. 如果旧信息已被更新（如情绪好转），替换而非叠加\n"
            "4. [安全标记] 相关内容永远保留\n"
            "5. 控制总长度在 300 字以内\n\n"
            f"旧摘要：\n{old_summary}"
        )
        result = await _llm_chat(
            system=prompt,
            messages=[{"role": "user", "content": readable}],
            model_override=get_light_model(),
            max_tokens=settings.medium_max_tokens,
        )
        return result["text"] or old_summary

    @staticmethod
    def _messages_to_readable(messages: list[dict]) -> str:
        """将消息列表转为可读文本（给 LLM 压缩用）。"""
        lines = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            label = "用户" if role == "user" else "咨询师" if role == "assistant" else role
            lines.append(f"{label}：{content[:500]}")
        return "\n".join(lines)


# ====================================================================
# 工具结果压缩
# ====================================================================

def compress_tool_results(messages: list[dict]) -> list[dict]:
    """
    压缩工具调用结果——保留工具名和关键结论，删除冗余细节。
    自动检测 Anthropic / DeepSeek 格式。
    """
    from agent.loop import _is_deepseek
    is_ds = _is_deepseek()

    compressed = []
    for msg in messages:
        if is_ds and msg.get("role") == "tool":
            compressed.append({
                **msg,
                "content": _shorten_tool_output(msg.get("content", "")),
            })
        elif (
            not is_ds
            and isinstance(msg.get("content"), list)
            and any(
                isinstance(c, dict) and c.get("type") == "tool_result"
                for c in msg["content"]
            )
        ):
            new_content = []
            for item in msg["content"]:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    new_content.append({
                        **item,
                        "content": _shorten_tool_output(str(item.get("content", ""))),
                    })
                else:
                    new_content.append(item)
            compressed.append({**msg, "content": new_content})
        else:
            compressed.append(msg)
    return compressed


def _shorten_tool_output(raw: str, max_len: int = 200) -> str:
    """
    将工具输出压缩为关键信息。
    识别常见工具结果的 JSON 结构，提取关键字段。
    """
    if not raw or len(raw) <= max_len:
        return raw

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return raw[:max_len] + "..."

        # 情绪评估结果
        if "primary" in data or "emotion" in data:
            emotion_data = data if "primary" in data else data.get("emotion", {})
            primary = emotion_data.get("primary", "")
            intensity = emotion_data.get("intensity", "")
            trigger = data.get("trigger", "")
            result = f"情绪：{primary}({intensity}/10)"
            if trigger:
                result += f"，触发：{trigger[:50]}"
            return result

        # 认知扭曲结果
        if "distortions" in data:
            distortions = data["distortions"]
            if isinstance(distortions, list):
                types = [
                    d.get("type", "") for d in distortions[:3]
                    if isinstance(d, dict)
                ]
                return f"认知扭曲：{'、'.join(types)}"

        # 干预策略结果
        if "strategy" in data or "intervention" in data:
            strategy = data.get("strategy") or data.get("intervention", "")
            if isinstance(strategy, str):
                return f"干预：{strategy[:100]}"

        # 通用：紧凑 JSON
        compact = json.dumps(data, ensure_ascii=False)
        return compact[:max_len] + ("..." if len(compact) > max_len else "")
    except (json.JSONDecodeError, TypeError, KeyError):
        return raw[:max_len] + "..."
