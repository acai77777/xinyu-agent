"""
WebSocket 实时对话路由
协议：JSON 消息，格式 {"type": "text|voice|image", "content": "...", "metadata": {...}}
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
    """从数据库加载会话历史"""
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


@router.websocket("/ws/{session_id}")
async def chat_websocket(ws: WebSocket, session_id: str):
    print(f"[WS] Connecting session={session_id[:8]}...", flush=True)
    await manager.connect(session_id, ws)
    print(f"[WS] Connected session={session_id[:8]}", flush=True)

    # 从数据库加载历史消息
    try:
        conversation_history = await _load_history(session_id)
        print(f"[WS] Loaded {len(conversation_history)} history msgs", flush=True)
    except Exception as e:
        print(f"[WS] _load_history error: {e}", flush=True)
        conversation_history = []

    # 尝试从 session_id 获取 user_id（用于 Agent 上下文）
    user_id = session_id  # 默认用 session_id
    try:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT user_id FROM conversations WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            if row:
                user_id = row[0]
        finally:
            await db.close()
    except Exception as e:
        print(f"[WS] DB user_id error: {e}", flush=True)

    print(f"[WS] user_id={user_id[:8]}..., waiting for messages", flush=True)
    crisis_holding = CrisisHolding.load(user_id)

    try:
        while True:
            raw = await ws.receive_text()
            print(f"[WS] Received msg: {raw[:100]}", flush=True)
            msg = json.loads(raw)

            # 根据消息类型预处理
            user_text = msg.get("content", "")
            msg_type = msg.get("type", "text")

            if msg_type == "voice":
                await manager.send_json(session_id, {
                    "type": "transcription",
                    "content": user_text,
                })

            if msg_type == "image":
                user_text = f"[用户发送了一张图片] {user_text}"

            # 保存用户消息到数据库
            await _save_message(session_id, "user", user_text, msg_type)

            # 发送"正在思考"状态
            await manager.send_json(session_id, {"type": "status", "content": "thinking"})

            # 调用 Agent 核心循环
            try:
                response = await run_agent(
                    user_message=user_text,
                    conversation_history=conversation_history,
                    user_id=user_id,
                    crisis_holding=crisis_holding,
                    session_id=session_id,
                )
            except Exception as e:
                print(f"[Agent Error] {type(e).__name__}: {e}", flush=True)
                response = {"text": f"抱歉，处理消息时遇到了问题，请稍后重试。", "emotion": None}

            # 更新内存中的对话历史
            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": response["text"]})

            # 保存 AI 回复到数据库
            await _save_message(session_id, "assistant", response["text"])

            # 第1轮对话结束后（history == 2条：1 user + 1 assistant），后台生成策略
            if len(conversation_history) == 2:
                asyncio.create_task(
                    _generate_and_send_strategy(session_id, conversation_history, user_id)
                )

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

            # 发送回复
            reply = {"type": "text", "content": response["text"]}

            if response.get("emotion"):
                reply["emotion"] = response["emotion"]

            if response.get("crisis_holding_active"):
                reply["crisis_holding"] = True

            await manager.send_json(session_id, reply)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[WS Error] {type(e).__name__}: {e}", flush=True)
        manager.disconnect(session_id)


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
