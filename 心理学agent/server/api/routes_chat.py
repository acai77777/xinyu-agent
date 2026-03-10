"""
WebSocket 实时对话路由
协议：JSON 消息，格式 {"type": "text|voice|image", "content": "...", "metadata": {...}}
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

from agent.loop import run_agent
from safety.resources import CrisisHolding

router = APIRouter()


class ConnectionManager:
    """管理活跃的 WebSocket 连接"""

    def __init__(self):
        self.active: dict[str, WebSocket] = {}  # user_id -> ws

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active[user_id] = ws

    def disconnect(self, user_id: str):
        self.active.pop(user_id, None)

    async def send_json(self, user_id: str, data: dict):
        if ws := self.active.get(user_id):
            await ws.send_json(data)


manager = ConnectionManager()


@router.websocket("/ws/{user_id}")
async def chat_websocket(ws: WebSocket, user_id: str):
    await manager.connect(user_id, ws)
    conversation_history = []  # TODO: Phase 3 从记忆系统加载
    crisis_holding = CrisisHolding.load(user_id)  # 从 DB 恢复抱持状态

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            # 根据消息类型预处理
            user_text = msg.get("content", "")
            msg_type = msg.get("type", "text")

            if msg_type == "voice":
                # Phase 4：语音消息先转文字
                # from multimodal.stt import transcribe
                # user_text = await transcribe(msg["audio_url"])
                await manager.send_json(user_id, {
                    "type": "transcription",
                    "content": user_text,
                })

            if msg_type == "image":
                # Phase 4：图片消息走 Vision 分析
                # from multimodal.vision import analyze_image
                # image_analysis = await analyze_image(msg["image_url"], user_text)
                user_text = f"[用户发送了一张图片] {user_text}"

            # 发送"正在思考"状态
            await manager.send_json(user_id, {"type": "status", "content": "thinking"})

            # 调用 Agent 核心循环
            response = await run_agent(
                user_message=user_text,
                conversation_history=conversation_history,
                user_id=user_id,
                crisis_holding=crisis_holding,
            )

            # 更新对话历史
            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": response["text"]})

            # 发送回复
            reply = {"type": "text", "content": response["text"]}

            # 附带情绪元数据（前端可用于 UI 状态变化）
            if response.get("emotion"):
                reply["emotion"] = response["emotion"]

            # 附带危机抱持状态（前端可显示 CrisisBanner 等特殊 UI）
            if response.get("crisis_holding_active"):
                reply["crisis_holding"] = True

            await manager.send_json(user_id, reply)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
