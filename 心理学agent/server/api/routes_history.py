"""
会话历史 REST API——管理对话会话和消息记录
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import get_db
from api.routes_auth import get_current_user

router = APIRouter()


# === 请求模型 ===

class CreateSessionRequest(BaseModel):
    title: str = ""


class SaveMessageRequest(BaseModel):
    session_id: str
    role: str  # "user" | "assistant"
    content: str
    msg_type: str = "text"
    metadata: dict | None = None


# === 路由 ===

@router.get("/sessions")
async def list_sessions(user_id: str = Depends(get_current_user)):
    """获取用户的所有会话列表（按更新时间倒序）"""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT session_id, title, created_at, updated_at
               FROM conversations
               WHERE user_id = ?
               ORDER BY updated_at DESC""",
            (user_id,),
        )
        rows = await cursor.fetchall()

        sessions = []
        for row in rows:
            session_id = row[0]
            # 获取最后一条消息作为预览
            msg_cursor = await db.execute(
                """SELECT content FROM messages
                   WHERE session_id = ? AND role = 'user'
                   ORDER BY created_at DESC LIMIT 1""",
                (session_id,),
            )
            last_msg = await msg_cursor.fetchone()
            preview = (last_msg[0][:50] + "...") if last_msg and len(last_msg[0]) > 50 else (last_msg[0] if last_msg else "")

            # 获取消息数量
            count_cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                (session_id,),
            )
            count = (await count_cursor.fetchone())[0]

            sessions.append({
                "session_id": row[0],
                "title": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "preview": preview,
                "message_count": count,
            })

        return {"sessions": sessions}
    finally:
        await db.close()


@router.post("/sessions")
async def create_session(
    req: CreateSessionRequest,
    user_id: str = Depends(get_current_user),
):
    """创建新会话"""
    session_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    title = req.title or f"对话 {now[:10]}"

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO conversations (session_id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, title, now, now),
        )
        await db.commit()
        return {"session_id": session_id, "title": title}
    finally:
        await db.close()


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
):
    """获取指定会话的所有消息"""
    db = await get_db()
    try:
        # 验证会话属于当前用户
        cursor = await db.execute(
            "SELECT title, created_at FROM conversations WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        )
        session_row = await cursor.fetchone()
        if not session_row:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 获取消息
        msg_cursor = await db.execute(
            """SELECT role, content, msg_type, metadata_json, created_at
               FROM messages
               WHERE session_id = ?
               ORDER BY created_at ASC""",
            (session_id,),
        )
        rows = await msg_cursor.fetchall()

        import json
        messages = []
        for row in rows:
            msg = {
                "role": row[0],
                "content": row[1],
                "type": row[2],
                "created_at": row[4],
            }
            if row[3] and row[3] != "{}":
                try:
                    msg["metadata"] = json.loads(row[3])
                except json.JSONDecodeError:
                    pass
            messages.append(msg)

        return {
            "session_id": session_id,
            "title": session_row[0],
            "created_at": session_row[1],
            "messages": messages,
        }
    finally:
        await db.close()


@router.post("/messages")
async def save_message(
    req: SaveMessageRequest,
    user_id: str = Depends(get_current_user),
):
    """保存一条消息到指定会话"""
    import json

    db = await get_db()
    try:
        # 验证会话属于当前用户
        cursor = await db.execute(
            "SELECT 1 FROM conversations WHERE session_id = ? AND user_id = ?",
            (req.session_id, user_id),
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="会话不存在")

        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(req.metadata or {}, ensure_ascii=False)

        await db.execute(
            """INSERT INTO messages (session_id, role, content, msg_type, metadata_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (req.session_id, req.role, req.content, req.msg_type, metadata_json, now),
        )
        # 更新会话时间
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE session_id = ?",
            (now, req.session_id),
        )
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
):
    """删除会话及其所有消息"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT 1 FROM conversations WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        )
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="会话不存在")

        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        await db.commit()
        return {"status": "deleted"}
    finally:
        await db.close()
