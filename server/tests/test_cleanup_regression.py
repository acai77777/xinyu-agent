"""
回归测试——确保重复代码清理后功能正常
覆盖：
1. main.py /uploads 只挂载一次
2. main.py /health 端点正常
3. routes_chat.py _resolve_user_id 逻辑正确
4. routes_chat.py WebSocket 完整流程（连接→发消息→收回复）
5. routes_chat.py ConnectionManager 基本行为
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from api.routes_chat import ConnectionManager, _resolve_user_id


# =====================================================================
# Helpers
# =====================================================================

def _mock_crisis_holding():
    mock = MagicMock()
    mock.active = False
    mock.current_phase = None
    return mock


def _ws_patches():
    return patch("api.routes_chat.CrisisHolding.load", return_value=_mock_crisis_holding())


# =====================================================================
# 1. /uploads 只挂载一次（回归：之前重复挂载了6次）
# =====================================================================

class TestUploadsMount:

    def test_uploads_mounted_once(self):
        """确保 /uploads 路由只被挂载一次"""
        upload_routes = [
            route for route in app.routes
            if hasattr(route, "path") and route.path == "/uploads"
        ]
        assert len(upload_routes) == 1, (
            f"期望 /uploads 挂载 1 次，实际挂载了 {len(upload_routes)} 次"
        )

    def test_uploads_is_static_files(self):
        """确保 /uploads 是 StaticFiles 挂载"""
        from starlette.routing import Mount
        upload_routes = [
            route for route in app.routes
            if isinstance(route, Mount) and route.path == "/uploads"
        ]
        assert len(upload_routes) == 1
        assert upload_routes[0].name == "uploads"


# =====================================================================
# 2. /health 端点
# =====================================================================

class TestHealthEndpoint:

    def test_health_returns_ok(self):
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

    def test_health_content_type(self):
        with TestClient(app) as client:
            resp = client.get("/health")
            assert "application/json" in resp.headers["content-type"]


# =====================================================================
# 3. _resolve_user_id（回归：之前重复查询了30+次）
# =====================================================================

class TestResolveUserId:

    @pytest.mark.asyncio
    async def test_returns_user_id_from_db(self):
        """数据库有记录时返回 user_id"""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=("real-user-123",))
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        mock_db.close = AsyncMock()

        with patch("api.routes_chat.get_db", return_value=mock_db):
            result = await _resolve_user_id("session-abc")
            assert result == "real-user-123"

        # 确保只查询了一次（回归核心：之前查了30+次）
        assert mock_db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_returns_session_id_when_no_record(self):
        """数据库没有记录时返回 session_id 作为 fallback"""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        mock_db.close = AsyncMock()

        with patch("api.routes_chat.get_db", return_value=mock_db):
            result = await _resolve_user_id("session-xyz")
            assert result == "session-xyz"

    @pytest.mark.asyncio
    async def test_returns_session_id_on_db_error(self):
        """数据库出错时不崩溃，返回 session_id"""
        with patch("api.routes_chat.get_db", side_effect=Exception("DB down")):
            result = await _resolve_user_id("session-err")
            assert result == "session-err"


# =====================================================================
# 4. WebSocket 完整流程
# =====================================================================

class TestWebSocketFlow:

    def test_connect_and_receive_reply(self):
        """WebSocket 连接后发消息，应收到 thinking + 回复"""
        mock_response = {
            "text": "你好，我是心语。",
            "raw_text": "你好，我是心语。",
            "emotion": {"primary_emotion": "平静", "intensity": 3},
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-regression-1") as ws:
                    ws.send_text(json.dumps({"type": "text", "content": "你好"}))

                    msg1 = ws.receive_json()
                    assert msg1["type"] == "status"
                    assert msg1["content"] == "thinking"

                    msg2 = ws.receive_json()
                    assert msg2["type"] == "text_done"
                    assert msg2["content"] == "你好，我是心语。"

    def test_agent_error_returns_fallback(self):
        """Agent 报错时应返回友好的错误提示而不是崩溃"""
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, side_effect=RuntimeError("LLM timeout")):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-regression-2") as ws:
                    ws.send_text(json.dumps({"type": "text", "content": "测试"}))

                    ws.receive_json()  # thinking
                    reply = ws.receive_json()
                    # fallback dict 没有 raw_text 字段 → 走 text_patch 分支
                    assert reply["type"] == "text_patch"
                    assert "抱歉" in reply["content"]


# =====================================================================
# 5. ConnectionManager
# =====================================================================

class TestConnectionManagerUnit:

    def test_disconnect_nonexistent_session(self):
        """断开不存在的 session 不应报错"""
        mgr = ConnectionManager()
        mgr.disconnect("nonexistent")  # 不应抛异常

    @pytest.mark.asyncio
    async def test_send_json_to_nonexistent_session(self):
        """向不存在的 session 发消息不应报错"""
        mgr = ConnectionManager()
        await mgr.send_json("nonexistent", {"type": "test"})  # 不应抛异常
