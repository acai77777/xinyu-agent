"""
跨会话记忆复现测试 —— 验证写入链路存在且生效

bug：写函数（add_snapshot/sm.store/ps.save）全项目零调用，导致新会话失忆。
本测试先红，待 memory/writer.py 实现后转绿。
"""
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from config import settings
from memory.narrative import NarrativeMemory
from memory.user_profile import ProfileStore, UserProfile
from memory.semantic import SemanticMemory


# ====================================================================
# 工具：每个测试用独立的 chroma 目录，避免数据互相污染
# ====================================================================

@pytest.fixture
def tmp_chroma_dir(tmp_path):
    d = tmp_path / "chroma"
    d.mkdir()
    return str(d)


@pytest.fixture(autouse=True)
def _clean_sqlite_tables():
    """每个测试清理 narrative_arcs / user_profiles 表，确保隔离"""
    conn = sqlite3.connect(settings.sqlite_db_path)
    for t in ("narrative_arcs", "user_profiles", "relationship_states"):
        try:
            conn.execute(f"DELETE FROM {t}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
    yield


# ====================================================================
# 1. 写入入口函数应存在 —— 失败说明 memory/writer.py 还没实现
# ====================================================================

class TestWriteEntrypointsExist:

    def test_writer_module_imports(self):
        """memory.writer 模块应该存在，导出两个核心函数"""
        from memory import writer
        assert hasattr(writer, "record_emotion_snapshot")
        assert hasattr(writer, "finalize_session_memory")

    @pytest.mark.asyncio
    async def test_record_emotion_snapshot_writes_narrative(self):
        """每轮快照写入：调用后 narrative_arcs 表应有该用户的记录"""
        from memory.writer import record_emotion_snapshot

        await record_emotion_snapshot(
            user_id="test_user_snapshot",
            session_id="sess_a",
            primary_emotion="悲伤",
            intensity=7,
            trigger="老板批评了我",
        )

        nm = NarrativeMemory()
        ctx = nm.get_narrative_context("test_user_snapshot")
        assert ctx is not None, "snapshot 写入后，叙事上下文应可读"
        assert "悲伤" in ctx or "老板" in ctx or "[叙事记忆]" in ctx

    @pytest.mark.asyncio
    async def test_finalize_session_writes_profile_and_semantic(self):
        """会话结束：应写入 user_profiles + 把 key_facts 全部递交给 SemanticMemory.store"""
        from memory import writer

        fake_extract = AsyncMock(return_value={
            "profile_updates": {
                "display_name": "小明",
                "current_phase": "distressed",
                "signature_strengths": ["共情力强"],
                "common_distortions": ["灾难化"],
                "preferred_interventions": ["认知重构"],
            },
            "key_facts": [
                "用户因被老板批评而感到悲伤",
                "用户最近一周睡眠不好",
            ],
        })

        store_calls: list[tuple[str, str, str]] = []

        class _FakeSM:
            def __init__(self, *a, **kw):
                pass

            def store(self, user_id, text, memory_type):
                store_calls.append((user_id, text, memory_type))

        with patch.object(writer, "_extract_session_memory", fake_extract), \
             patch("memory.semantic.SemanticMemory", _FakeSM):
            await writer.finalize_session_memory(
                user_id="test_user_final",
                session_id="sess_a",
                history=[
                    {"role": "user", "content": "我最近因为被老板批评了几次心情一直很差，晚上也睡不好觉"},
                    {"role": "assistant", "content": "听起来很难受……"},
                    {"role": "user", "content": "对，每天都很累，感觉自己什么都做不好，已经持续一周了"},
                ],
            )

        ps = ProfileStore()
        profile = ps.load("test_user_final")
        assert profile is not None, "会话结束后应写入 user_profiles"
        assert profile.display_name == "小明"
        assert "灾难化" in profile.common_distortions

        assert store_calls, "语义记忆 store 应被调用"
        assert all(uid == "test_user_final" for uid, _, _ in store_calls)
        assert any("老板" in text for _, text, _ in store_calls)


# ====================================================================
# 2. 跨会话读回 —— 写入后，新 session 的 system prompt 应包含历史
# ====================================================================

class TestCrossSessionReadback:

    @pytest.mark.asyncio
    async def test_inject_full_context_sees_prior_snapshot(self):
        """会话 A 写入快照后，会话 B 冷启动时 _inject_full_context 应能拿到"""
        from memory.writer import record_emotion_snapshot
        from agent.loop import _inject_full_context

        await record_emotion_snapshot(
            user_id="cross_user",
            session_id="sess_A",
            primary_emotion="悲伤",
            intensity=8,
            trigger="跟伴侣吵架",
        )

        hints: list[str] = []
        # 屏蔽知识库 Chroma 启动，专注验证叙事记忆注入
        with patch("knowledge.knowledge_base.search_books_semantic", return_value=[]):
            await _inject_full_context(
                hints,
                user_message="我之前有什么难受的情况吗",
                user_id="cross_user",
                session_id="sess_B",
                crisis_holding=None,
            )

        joined = "\n".join(hints)
        assert "[叙事记忆]" in joined, (
            "新会话 system prompt 应注入叙事记忆，否则 AI 会说'第一次对话'"
        )


# ====================================================================
# 3. 读路径完好性 —— 手动塞数据后能读出来（证明 bug 在写不在读）
# ====================================================================

class TestReadPathSanity:

    @pytest.mark.asyncio
    async def test_manual_snapshot_can_be_read_by_inject(self):
        """绕过 writer，手动写一条 → 读路径应能取到"""
        from memory.narrative import NarrativeMemory, EmotionSnapshot
        from agent.loop import _inject_full_context

        nm = NarrativeMemory()
        nm.add_snapshot(
            user_id="sanity_user",
            theme="工作压力",
            snapshot=EmotionSnapshot(
                timestamp="2026-05-26T15:00:00",
                primary_emotion="焦虑",
                intensity=6,
                trigger="项目延期",
                session_id="manual_sess",
            ),
        )

        hints: list[str] = []
        with patch("knowledge.knowledge_base.search_books_semantic", return_value=[]):
            await _inject_full_context(
                hints,
                user_message="hi",
                user_id="sanity_user",
                session_id="new_sess",
                crisis_holding=None,
            )
        joined = "\n".join(hints)
        assert "[叙事记忆]" in joined
        assert "工作压力" in joined


# ====================================================================
# 4. 边缘：用户没说有意义内容时，不应写垃圾
# ====================================================================

class TestWriteThreshold:

    @pytest.mark.asyncio
    async def test_skip_finalize_for_trivial_history(self, tmp_chroma_dir, monkeypatch):
        """历史只有'嗯/哦'这种内容时，不应触发 LLM 抽取或写入"""
        from memory import writer

        monkeypatch.setattr(settings, "chroma_persist_dir", tmp_chroma_dir)

        fake_extract = AsyncMock(return_value={"profile_updates": {}, "key_facts": []})
        with patch.object(writer, "_extract_session_memory", fake_extract):
            await writer.finalize_session_memory(
                user_id="trivial_user",
                session_id="t1",
                history=[
                    {"role": "user", "content": "嗯"},
                    {"role": "assistant", "content": "好的"},
                ],
            )

        fake_extract.assert_not_awaited()
        ps = ProfileStore()
        assert ps.load("trivial_user") is None
