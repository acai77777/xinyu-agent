"""
API 路由测试——test_api.py
覆盖：HTTP 健康检查、WebSocket 连接管理、消息协议
使用 FastAPI TestClient，不调用真实 LLM
"""
import pytest
import json
import logging
import sys
import types
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app

TEST_MAIN_MODEL = "doubao-seed-2-0-mini-260428"


def _ws_json(payload: dict) -> str:
    return json.dumps({"model": TEST_MAIN_MODEL, **payload})


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
            "raw_text": "你好，我是心语。",
            "emotion": {"primary_emotion": "平静", "intensity": 3},
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-user-2") as ws:
                    ws.send_text(_ws_json({
                        "type": "text",
                        "content": "你好",
                    }))

                    # 第一条：thinking 状态
                    msg1 = ws.receive_json()
                    assert msg1["type"] == "status"
                    assert msg1["content"] == "thinking"

                    # 第二条：回复（raw_text == text，走 text_done）
                    msg2 = ws.receive_json()
                    assert msg2["type"] == "text_done"
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
                    ws.send_text(_ws_json({"type": "text", "content": "我很难过"}))
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
                    ws.send_text(_ws_json({"type": "text", "content": "我不想活了"}))
                    ws.receive_json()  # skip thinking
                    reply = ws.receive_json()
                    assert reply.get("crisis_holding") is True

    def test_ws_image_message(self):
        """图片消息应被预处理为 [用户发送了一张图片] 前缀"""
        mock_response = {
            "text": "我看到了你发的图片。",
            "raw_text": "我看到了你发的图片。",
            "emotion": None,
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response) as mock_agent:
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-user-5") as ws:
                    ws.send_text(_ws_json({
                        "type": "image",
                        "content": "这是我今天画的",
                        "image_url": "http://example.com/img.jpg",
                    }))
                    ws.receive_json()  # thinking
                    reply = ws.receive_json()
                    assert reply["type"] == "text_done"
                    # 验证 run_agent 收到了带前缀的文本
                    call_kwargs = mock_agent.call_args.kwargs
                    assert "[用户发送了一张图片]" in call_kwargs.get("user_message", "")


# =====================================================================
# 3. 连接管理器
# =====================================================================

    def test_ws_voice_message_uses_top_level_audio_url(self):
        """Voice messages from the app send audio_url at the top level."""
        mock_response = {
            "text": "已收到语音",
            "raw_text": "已收到语音",
            "emotion": None,
            "crisis_holding_active": False,
        }
        stt_module = types.ModuleType("multimodal.stt")
        stt_module.transcribe_with_emotion_hints = AsyncMock(return_value={
            "text": "我今天有点累",
            "emotion_hints": [],
            "duration_seconds": 0,
        })

        with _ws_patches(), \
             patch.dict(sys.modules, {"multimodal.stt": stt_module}), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response) as mock_agent:
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-user-voice") as ws:
                    ws.send_text(_ws_json({
                        "type": "voice",
                        "content": "",
                        "audio_url": "C:/tmp/audio.wav",
                    }))

                    transcription = ws.receive_json()
                    assert transcription["type"] == "transcription"
                    assert transcription["content"] == "我今天有点累"
                    ws.receive_json()  # thinking
                    reply = ws.receive_json()
                    assert reply["type"] == "text_done"

        stt_module.transcribe_with_emotion_hints.assert_awaited_once_with("C:/tmp/audio.wav")
        assert mock_agent.call_args.kwargs["user_message"] == "我今天有点累"


class TestConnectionManager:

    def test_multiple_users(self):
        """多用户应独立管理"""
        mock_response = {
            "text": "回复",
            "raw_text": "回复",
            "emotion": None,
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/user-a") as ws_a:
                    with client.websocket_connect("/ws/user-b") as ws_b:
                        ws_a.send_text(_ws_json({"type": "text", "content": "a"}))
                        ws_b.send_text(_ws_json({"type": "text", "content": "b"}))

                        assert ws_a.receive_json()["type"] == "status"
                        assert ws_a.receive_json()["type"] == "text_done"

                        assert ws_b.receive_json()["type"] == "status"
                        assert ws_b.receive_json()["type"] == "text_done"


# =====================================================================
# 4. 流式协议路由分支（Phase A 引入）
# 目的：raw_text == final_text 走 text_done；不等或 raw_text 空走 text_patch。
#      前端依赖这个区分来决定"保留累积 chunks vs 整体替换"。
# =====================================================================

class TestStreamingProtocol:

    @pytest.mark.parametrize("model", [
        "doubao-seed-2-0-mini-260428",
        "doubao-seed-2-0-lite-260428",
        "deepseek-v4-flash",
    ])
    def test_ws_forwards_allowed_model_to_main_agent(self, model):
        """会话消息选择的模型只作为本轮主 Agent 覆盖值传递。"""
        mock_response = {
            "text": "好的。",
            "raw_text": "好的。",
            "emotion": None,
            "crisis_holding_active": False,
        }
        agent = AsyncMock(return_value=mock_response)
        with _ws_patches(), patch("api.routes_chat.run_agent", agent):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-model-select") as ws:
                    ws.send_text(_ws_json({
                        "type": "text",
                        "content": "你好",
                        "model": model,
                    }))
                    ws.receive_json()  # thinking
                    ws.receive_json()  # reply

        assert agent.await_args.kwargs["main_model"] == model

    def test_ws_rejects_unknown_model_without_calling_agent(self):
        """模型不在白名单时返回协议错误，且不发起任何 LLM 调用。"""
        agent = AsyncMock()
        with _ws_patches(), patch("api.routes_chat.run_agent", agent):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-model-reject") as ws:
                    ws.send_text(_ws_json({
                        "type": "text",
                        "content": "你好",
                        "model": "unknown-model",
                    }))
                    reply = ws.receive_json()

        assert reply["type"] == "error"
        assert reply["code"] == "unsupported_model"
        agent.assert_not_awaited()

    def test_ws_text_done_when_raw_equals_final(self):
        """LLM 输出未被审核改写 → text_done"""
        mock_response = {
            "text": "听起来你最近压力很大。",
            "raw_text": "听起来你最近压力很大。",
            "emotion": None,
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-stream-done") as ws:
                    ws.send_text(_ws_json({"type": "text", "content": "我累了"}))
                    ws.receive_json()  # thinking
                    reply = ws.receive_json()
                    assert reply["type"] == "text_done"
                    assert reply["content"] == "听起来你最近压力很大。"

    def test_ws_text_done_content_is_complete_not_truncated(self):
        """
        契约保险：text_done 的 content 必须等于完整 final_text，不能空/截断。

        背景：Web 端"流字末尾几个字消失"bug 的根因是 stream_cb 异常被后端
        warning 吞掉 + 前端只信累积 chunks。前端已修为优先用 content 兜底，
        但前端能兜底的前提是后端 text_done 始终发完整 content。
        如果未来有人把 text_done 的 content 改成空/截断（比如"省流量优化"），
        前端无法补齐，bug 复现。这条测试就是不让这事发生。
        """
        full = "这是一段较长的文本，模拟流式输出末尾包含关键安抚语句。" * 3
        mock_response = {
            "text": full,
            "raw_text": full,
            "emotion": None,
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-done-contract") as ws:
                    ws.send_text(_ws_json({"type": "text", "content": "ping"}))
                    ws.receive_json()  # thinking
                    reply = ws.receive_json()
                    assert reply["type"] == "text_done"
                    # 1) content 不能为空字符串
                    assert reply["content"], "text_done 的 content 不能为空——前端将无法兜底末尾丢字"
                    # 2) content 必须严格等于完整 final_text（不能截断）
                    assert reply["content"] == full, (
                        "text_done 的 content 必须等于完整 final_text；"
                        f"实际长度 {len(reply['content'])} vs 期望 {len(full)}"
                    )
                    # 3) 长度也必须严格相等
                    assert len(reply["content"]) == len(full)

    def test_ws_text_patch_when_safety_rewrote(self):
        """_post_safety_check 改写过 → text_patch（前端整体替换 chunks）"""
        mock_response = {
            "text": "你可以咨询你的医生。（提醒：用药请遵医嘱）",
            "raw_text": "你可以停药试试。",
            "emotion": None,
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-stream-patch") as ws:
                    ws.send_text(_ws_json({"type": "text", "content": "我能不能停药"}))
                    ws.receive_json()  # thinking
                    reply = ws.receive_json()
                    assert reply["type"] == "text_patch"
                    assert "咨询你的医生" in reply["content"]
                    assert "停药" not in reply["content"]

    def test_ws_empty_raw_text_falls_back_to_patch(self):
        """raw_text 为空（异常 fallback 或旧 mock）→ if raw_text 短路 → text_patch"""
        mock_response = {
            "text": "我在这里。",
            "raw_text": "",
            "emotion": None,
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-stream-empty") as ws:
                    ws.send_text(_ws_json({"type": "text", "content": "嗯"}))
                    ws.receive_json()  # thinking
                    reply = ws.receive_json()
                    assert reply["type"] == "text_patch"


# =====================================================================
# 5. WS 关键运行日志（Phase C 引入）
# 目的：清调试 print 后保留可见性。recv/reply sent/error 缺一条都会导致线上失明。
# =====================================================================

class TestWebSocketLogs:

    def test_ws_logs_recv_and_reply_sent(self, caplog):
        """正常一轮应打 [WS] recv 和 [WS] reply sent 各一条"""
        caplog.set_level(logging.INFO, logger="api.routes_chat")
        mock_response = {
            "text": "好的。",
            "raw_text": "好的。",
            "emotion": None,
            "crisis_holding_active": False,
        }
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock, return_value=mock_response):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-ws-log-1") as ws:
                    ws.send_text(_ws_json({"type": "text", "content": "你好"}))
                    ws.receive_json()  # thinking
                    ws.receive_json()  # reply

        messages = [r.getMessage() for r in caplog.records]
        recv_logs = [m for m in messages if "[WS]" in m and "recv type=text" in m]
        sent_logs = [m for m in messages if "[WS]" in m and "reply sent type=text_done" in m]
        assert len(recv_logs) >= 1, f"应有 recv 日志，实际: {messages}"
        assert len(sent_logs) >= 1, f"应有 reply sent 日志，实际: {messages}"
        # session_id 前 8 字符在日志中
        assert "test-ws-" in recv_logs[0]
        assert "len=2" in recv_logs[0]  # "你好" 2 字符

    def test_ws_logs_agent_error_with_exc_info(self, caplog):
        """run_agent 抛异常时应通过 logger.error 记录（带 exc_info）"""
        caplog.set_level(logging.ERROR, logger="api.routes_chat")
        with _ws_patches(), \
             patch("api.routes_chat.run_agent", new_callable=AsyncMock,
                   side_effect=RuntimeError("LLM timeout")):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/test-ws-log-err") as ws:
                    ws.send_text(_ws_json({"type": "text", "content": "x"}))
                    ws.receive_json()  # thinking
                    ws.receive_json()  # fallback reply

        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "[Agent]" in r.getMessage()
            and "run_agent failed" in r.getMessage()
        ]
        assert len(error_records) == 1, \
            f"应有 1 条 agent error 日志，实际: {[r.getMessage() for r in caplog.records]}"
        # exc_info=True 时 record 会带 traceback 信息
        assert error_records[0].exc_info is not None, "logger.error 必须带 exc_info"
        assert "LLM timeout" in error_records[0].getMessage() or \
               "RuntimeError" in error_records[0].getMessage()
