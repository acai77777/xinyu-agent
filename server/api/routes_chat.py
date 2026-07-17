"""
WebSocket 实时对话路由
协议：JSON 消息，格式 {"type": "text|voice|image", "content": "...", "model": "...", "metadata": {...}}
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import asyncio
import json
import logging
from datetime import datetime, timezone

from agent.loop import run_agent
from agent.session_strategy import generate_session_strategy, load_session_strategy
from safety.resources import CrisisHolding
from db import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MAIN_MODELS = {
    "doubao-seed-2-0-mini-260428",
    "doubao-seed-2-0-lite-260428",
    "deepseek-v4-flash",
}


class ConnectionManager:
    """管理活跃的 WebSocket 连接"""

    def __init__(self):
        self.active: dict[str, WebSocket] = {}  # session_id -> ws

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.active[session_id] = ws

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)

    async def send_json(self, session_id: str, data: dict):
        if ws := self.active.get(session_id):
            await ws.send_json(data)


manager = ConnectionManager()


async def _save_message(session_id: str, role: str, content: str, msg_type: str = "text"):
    """将消息持久化到数据库"""
    db = await get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """INSERT INTO messages (session_id, role, content, msg_type, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, role, content, msg_type, now),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        await db.commit()
    finally:
        await db.close()


async def _load_history(session_id: str) -> list[dict]:
    """从数据库加载会话历史（完整版，供内存追加用）"""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT role, content FROM messages
               WHERE session_id = ?
               ORDER BY created_at ASC""",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [{"role": row[0], "content": row[1]} for row in rows]
    finally:
        await db.close()


async def _load_latest_summary(session_id: str) -> dict | None:
    """
    加载最新的压缩摘要。
    返回 dict: {summary_text, compressed_up_to_msg_id, compressed_count,
                incremental_rounds, safety_pins}
    或 None（无摘要）。
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT summary_text, compressed_up_to_msg_id, compressed_count,
                      incremental_rounds, safety_pins_json
               FROM conversation_summaries
               WHERE session_id = ?
               ORDER BY summary_version DESC LIMIT 1""",
            (session_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "summary_text": row[0],
            "compressed_up_to_msg_id": row[1],
            "compressed_count": row[2],
            "incremental_rounds": row[3],
            "safety_pins": json.loads(row[4]) if row[4] else [],
        }
    finally:
        await db.close()


async def _save_summary(
    session_id: str,
    summary_text: str,
    compressed_up_to_msg_id: int,
    compressed_count: int,
    incremental_rounds: int,
    safety_pins: list[dict],
) -> None:
    """将压缩摘要写入 DB，版本号自增。"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT MAX(summary_version) FROM conversation_summaries WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        next_version = (row[0] or 0) + 1

        pins_json = json.dumps(
            [{"role": m["role"], "content": m["content"]} for m in safety_pins],
            ensure_ascii=False,
        )
        await db.execute(
            """INSERT INTO conversation_summaries
               (session_id, summary_version, summary_text,
                compressed_up_to_msg_id, compressed_count,
                incremental_rounds, safety_pins_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, next_version, summary_text,
             compressed_up_to_msg_id, compressed_count,
             incremental_rounds, pins_json),
        )
        await db.commit()
    finally:
        await db.close()


async def _get_max_message_id(session_id: str) -> int:
    """获取当前会话的最大 message_id（用于标记压缩截止点）。"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT MAX(message_id) FROM messages WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return row[0] or 0
    finally:
        await db.close()


async def _resolve_user_id(session_id: str) -> str:
    """从数据库查询 session 对应的 user_id，查不到则返回 session_id。"""
    try:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT user_id FROM conversations WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            if row:
                return row[0]
        finally:
            await db.close()
    except Exception as e:
        print(f"[WS] DB user_id error: {e}", flush=True)
    return session_id


@router.websocket("/ws/{session_id}")
async def chat_websocket(ws: WebSocket, session_id: str):
    print(f"[WS] Connecting session={session_id[:8]}...", flush=True)
    await manager.connect(session_id, ws)
    print(f"[WS] Connected session={session_id[:8]}", flush=True)

    # 从数据库加载历史消息 + 压缩摘要
    try:
        conversation_history = await _load_history(session_id)
        print(f"[WS] Loaded {len(conversation_history)} history msgs", flush=True)
    except Exception as e:
        print(f"[WS] _load_history error: {e}", flush=True)
        conversation_history = []

    # 加载已有的压缩摘要元数据（断连恢复用）
    prior_summary: str | None = None
    prior_compressed_count: int | None = None
    incremental_rounds: int = 0
    try:
        summary_meta = await _load_latest_summary(session_id)
        if summary_meta:
            prior_summary = summary_meta["summary_text"]
            prior_compressed_count = summary_meta["compressed_count"]
            incremental_rounds = summary_meta["incremental_rounds"]
            print(f"[WS] Loaded summary v{incremental_rounds}, "
                  f"compressed={prior_compressed_count} msgs", flush=True)
    except Exception as e:
        print(f"[WS] _load_latest_summary error: {e}", flush=True)

    # 获取 user_id
    user_id = await _resolve_user_id(session_id)

    print(f"[WS] user_id={user_id[:8]}..., waiting for messages", flush=True)
    crisis_holding = CrisisHolding.load(user_id)

    try:
        while True:
            raw = await ws.receive_text()
            print(f"[WS] Received msg: {raw[:100]}", flush=True)
            msg = json.loads(raw)

            main_model = msg.get("model")
            if main_model not in ALLOWED_MAIN_MODELS:
                await manager.send_json(session_id, {
                    "type": "error",
                    "code": "unsupported_model",
                    "content": "不支持的主对话模型",
                })
                continue

            # 根据消息类型预处理
            user_text = msg.get("content", "")
            msg_type = msg.get("type", "text")
            multimodal_context = []

            sid8 = (session_id or "anon")[:8]
            logger.info(f"[WS] {sid8} recv type={msg_type} len={len(user_text)}")

            if msg_type == "voice":
                audio_url = msg.get("audio_url") or msg.get("metadata", {}).get("audio_url", "")
                if audio_url:
                    try:
                        from multimodal.stt import transcribe_with_emotion_hints
                        stt_result = await transcribe_with_emotion_hints(audio_url)
                        user_text = stt_result["text"] or user_text
                        if stt_result.get("emotion_hints"):
                            multimodal_context.append(
                                f"[语音情绪线索] {'；'.join(stt_result['emotion_hints'])}"
                            )
                    except Exception as e:
                        logger.warning(f"[STT] transcribe failed: {e}")
                await manager.send_json(session_id, {
                    "type": "transcription",
                    "content": user_text,
                })

            if msg_type == "image":
                image_url = msg.get("image_url") or msg.get("metadata", {}).get("image_url", "")
                if image_url:
                    try:
                        from multimodal.vision import analyze_image
                        vision_result = await analyze_image(image_url, user_context=user_text)
                        multimodal_context.append(f"[图片分析] {vision_result}")
                    except Exception as e:
                        logger.warning(f"[Vision] analyze_image failed: {e}")
                user_text = f"[用户发送了一张图片] {user_text}"

            # 保存用户消息到数据库
            await _save_message(session_id, "user", user_text, msg_type)

            # 发送"正在思考"状态
            await manager.send_json(session_id, {"type": "status", "content": "thinking"})

            # 流式回调——LLM 每产出一段 content 就实时推送给前端
            async def stream_cb(delta: str):
                await manager.send_json(session_id, {"type": "text_chunk", "content": delta})

            # 调用 Agent 核心循环
            try:
                response = await run_agent(
                    user_message=user_text,
                    conversation_history=conversation_history,
                    user_id=user_id,
                    crisis_holding=crisis_holding,
                    session_id=session_id,
                    multimodal_context=multimodal_context if multimodal_context else None,
                    prior_summary=prior_summary,
                    prior_compressed_count=prior_compressed_count,
                    incremental_rounds=incremental_rounds,
                    main_model=main_model,
                    stream_cb=stream_cb,
                )
            except Exception as e:
                logger.error(
                    f"[Agent] {sid8} run_agent failed: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                response = {"text": "抱歉，处理消息时遇到了问题，请稍后重试。", "raw_text": "", "emotion": None}

            # 更新内存中的对话历史
            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": response["text"]})

            # 持久化压缩摘要（如果本轮产生了新摘要）
            new_summary = response.get("summary")
            if new_summary and new_summary != prior_summary:
                try:
                    max_msg_id = await _get_max_message_id(session_id)
                    # 计算已压缩的非安全消息条数
                    from context.compressor import ConversationCompressor
                    comp = ConversationCompressor()
                    split_idx = comp._find_split_point(conversation_history, comp.keep_recent)
                    early = conversation_history[:split_idx]
                    _, compressible = comp._partition_safety(early)
                    new_compressed_count = len(compressible)

                    new_incremental = (
                        incremental_rounds + 1 if prior_summary else 1
                    )
                    # 全量重压缩时重置计数
                    if new_incremental > comp.max_incremental_rounds:
                        new_incremental = 1

                    safety_pinned, _ = comp._partition_safety(early)
                    await _save_summary(
                        session_id=session_id,
                        summary_text=new_summary,
                        compressed_up_to_msg_id=max_msg_id,
                        compressed_count=new_compressed_count,
                        incremental_rounds=new_incremental,
                        safety_pins=safety_pinned,
                    )
                    # 更新内存中的元数据供下一轮使用
                    prior_summary = new_summary
                    prior_compressed_count = new_compressed_count
                    incremental_rounds = new_incremental
                    print(f"[WS] Saved summary v{new_incremental}, "
                          f"compressed={new_compressed_count}", flush=True)
                except Exception as e:
                    print(f"[WS] _save_summary error: {e}", flush=True)

            # 保存 AI 回复到数据库
            await _save_message(session_id, "assistant", response["text"])

            # 后台生成策略（无策略时每轮尝试，有了就不再触发）
            try:
                existing_strategy = await load_session_strategy(session_id)
                if not existing_strategy:
                    asyncio.create_task(
                        _generate_and_send_strategy(session_id, conversation_history, user_id)
                    )
            except Exception:
                pass

            # 自动生成会话标题（首次对话时）
            if len(conversation_history) == 2:
                title = user_text[:20] + ("..." if len(user_text) > 20 else "")
                db = await get_db()
                try:
                    await db.execute(
                        "UPDATE conversations SET title = ? WHERE session_id = ? AND (title = '' OR title IS NULL)",
                        (title, session_id),
                    )
                    await db.commit()
                finally:
                    await db.close()

            # 发送回复——流式协议
            # raw_text == final_text → 流字未被改写，发 text_done
            # raw_text != final_text → 审核改写了，发 text_patch（带完整修正文本，前端替换累积 chunks）
            final_text = response["text"]
            raw_text = response.get("raw_text", "")
            if raw_text and raw_text == final_text:
                reply = {"type": "text_done", "content": final_text}
            else:
                reply = {"type": "text_patch", "content": final_text}

            if response.get("emotion"):
                reply["emotion"] = response["emotion"]

            if response.get("crisis_holding_active"):
                reply["crisis_holding"] = True

            await manager.send_json(session_id, reply)
            logger.info(
                f"[WS] {sid8} reply sent type={reply['type']} "
                f"len={len(reply.get('content', ''))}"
            )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        await _finalize_session_safe(user_id, session_id, conversation_history)
    except Exception as e:
        logger.error(
            f"[WS] {(session_id or 'anon')[:8]} error: {type(e).__name__}: {e}",
            exc_info=True,
        )
        manager.disconnect(session_id)
        await _finalize_session_safe(user_id, session_id, conversation_history)


async def _finalize_session_safe(
    user_id: str, session_id: str, conversation_history: list[dict],
) -> None:
    """WS 断开后触发跨会话记忆固化。所有异常静默降级，绝不影响连接清理。"""
    try:
        from memory.writer import finalize_session_memory
        await finalize_session_memory(user_id, session_id, conversation_history)
    except Exception as e:
        logger.warning(
            f"[Memory] finalize failed for session {(session_id or 'anon')[:8]}: {e}"
        )


async def _generate_and_send_strategy(
    session_id: str,
    conversation_history: list[dict],
    user_id: str,
) -> None:
    """后台任务：生成会话策略并通过 WebSocket 发送给前端。"""
    try:
        # 尝试加载用户画像作为额外上下文
        user_profile_text = ""
        try:
            from memory.user_profile import ProfileStore
            ps = ProfileStore()
            profile = ps.load(user_id)
            if profile:
                parts = []
                if profile.current_phase:
                    parts.append(f"阶段：{profile.current_phase}")
                if profile.signature_strengths:
                    parts.append(f"优势：{'、'.join(profile.signature_strengths)}")
                if profile.common_distortions:
                    parts.append(f"认知扭曲：{'、'.join(profile.common_distortions)}")
                user_profile_text = "；".join(parts)
        except Exception:
            pass

        strategy = await generate_session_strategy(
            session_id=session_id,
            conversation_history=conversation_history,
            user_profile=user_profile_text,
        )

        if strategy and strategy.user_summary:
            await manager.send_json(session_id, {
                "type": "strategy_hint",
                "content": strategy.user_summary,
            })
            logger.info(f"[Strategy] Sent hint to session {session_id[:8]}")
    except Exception as e:
        logger.error(f"[Strategy] Background task failed: {e}")
