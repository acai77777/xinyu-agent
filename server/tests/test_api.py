"""
API 路由测试——test_api.py
覆盖：HTTP 健康检查、WebSocket 连接管理、消息协议
使用 FastAPI TestClient，不调用真实 LLM
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app


def _mock_crisis_holding():
    """创建 CrisisHolding mock，避免真实 DB 访问"""
    mock = MagicMock()
    mock.active = False
    mock.current_phase = None
    return mock


def _ws_patches():
    """WebSocket 测试通用 patches：mock CrisisHolding.load"""
    return patch("api.routes_chat.CrisisHolding.load", return_value=_mock_crisis_holding())


# =====================================================================
# 1. HTTP 健康检查
# =====================================================================

class TestHealthEndpoint:

    def test_health_ok(self):
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200


# =====================================================================
# 2. WebSocket 连接
# =====================================================================

class TestWebSocketConnection:

    def test_ws_connect_disconnect(self):
        """WebSocket 能正常连接和断开"""
        with _ws_patches():
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-user-1") as ws:
                    pass

    def test_ws_send_receive(self):
        """发送消息后应收到 status + reply"""
        mock_response = {
            "text": "你好，我是心语。",
            "emotion": {"primary_emotion": "平静", "intensity": 3},
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-user-2") as ws:
                    ws.send_text(json.dumps({
                        "type": "text",
                        "content": "你好",
                    }))

                    # 第一条：thinking 状态
                    msg1 = ws.receive_json()
                    assert msg1["type"] == "status"
                    assert msg1["content"] == "thinking"

                    # 第二条：回复
                    msg2 = ws.receive_json()
                    assert msg2["type"] == "text"
                    assert "心语" in msg2["content"]

    def test_ws_emotion_in_reply(self):
        """回复中应包含情绪元数据"""
        mock_response = {
            "text": "我理解你的感受。",
            "emotion": {"primary_emotion": "悲伤", "intensity": 7},
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-user-3") as ws:
                    ws.send_text(json.dumps({"type": "text", "content": "我很难过"}))
                    ws.receive_json()  # skip thinking
                    reply = ws.receive_json()
                    assert "emotion" in reply
                    assert reply["emotion"]["primary_emotion"] == "悲伤"

    def test_ws_crisis_holding_flag(self):
        """危机抱持状态应传递到前端"""
        mock_response = {
            "text": "我在这里。",
            "emotion": None,
            "crisis_holding_active": True,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-user-4") as ws:
                    ws.send_text(json.dumps({"type": "text", "content": "我不想活了"}))
                    ws.receive_json()  # skip thinking
                    reply = ws.receive_json()
                    assert reply.get("crisis_holding") is True

    def test_ws_image_message(self):
        """图片消息应被预处理为 [用户发送了一张图片] 前缀"""
        mock_response = {
            "text": "我看到了你发的图片。",
            "emotion": None,
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response) as mock_agent:
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-user-5") as ws:
                    ws.send_text(json.dumps({
                        "type": "image",
                        "content": "这是我今天画的",
                        "image_url": "http://example.com/img.jpg",
                    }))
                    ws.receive_json()  # thinking
                    reply = ws.receive_json()
                    assert reply["type"] == "text"
                    # 验证 run_agent 收到了带前缀的文本
                    call_kwargs = mock_agent.call_args.kwargs
                    assert "[用户发送了一张图片]" in call_kwargs.get("user_message", "")


# =====================================================================
# 3. 连接管理器
# =====================================================================

class TestConnectionManager:

    def test_multiple_users(self):
        """多用户应独立管理"""
        mock_response = {
            "text": "回复",
            "emotion": None,
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/user-a") as ws_a:
                    with client.websocket_connect("/ws/user-b") as ws_b:
                        ws_a.send_text(json.dumps({"type": "text", "content": "a"}))
                        ws_b.send_text(json.dumps({"type": "text", "content": "b"}))

                        assert ws_a.receive_json()["type"] == "status"
                        assert ws_a.receive_json()["type"] == "text"

                        assert ws_b.receive_json()["type"] == "status"
                        assert ws_b.receive_json()["type"] == "text"
