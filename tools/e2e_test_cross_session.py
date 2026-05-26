"""
端到端跨会话失忆验证脚本——一次性使用，跑完自动清理。

流程：
1. 注册测试用户
2. session_1：聊 3 条带情绪/主题的消息
3. 断 WS → 触发 finalize_session_memory
4. 等 LLM 完成提取（轮询 DB，最长 30s）
5. 查 SQLite 看是否写入 narrative_arcs / user_profiles / semantic memory
6. session_2：问"你还记得我之前说过什么吗"
7. 检查 AI 回复是否包含 session_1 关键词
8. 清理：删 user / conversations / messages / narrative_arcs / user_profiles
9. 报告 PASS/FAIL
"""
import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path

import httpx
import websockets

# Windows GBK 控制台无法打印 AI 回复里的 emoji（💙 等），切 UTF-8 + 容错替换。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"
DB_PATH = Path(__file__).resolve().parent.parent / "server" / "data" / "agent.db"

TEST_USERNAME = f"e2e_test_{int(time.time())}"
TEST_PASSWORD = "test123456"

SESSION_1_MESSAGES = [
    "我最近失恋了，每天晚上都失眠到三四点。",
    "感觉自己什么都做不好，工作也没动力。",
    "想找个人聊聊，但是朋友们好像都在忙自己的事。",
]
SESSION_2_QUESTION = "你还记得我之前跟你说过什么吗？"
EXPECTED_KEYWORDS = ["失恋", "失眠", "工作", "朋友", "动力", "难过", "孤独"]


def log(level: str, msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


async def register(client: httpx.AsyncClient) -> tuple[str, str]:
    r = await client.post(
        f"{BASE_URL}/api/auth/register",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    r.raise_for_status()
    data = r.json()
    return data["access_token"], data["user_id"]


async def create_session(client: httpx.AsyncClient, token: str) -> str:
    r = await client.post(
        f"{BASE_URL}/api/history/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "e2e test"},
    )
    r.raise_for_status()
    return r.json()["session_id"]


async def chat_one_session(session_id: str, messages: list[str], collect_replies: bool = False) -> list[str]:
    """连 WS，按顺序发完所有消息，收完每条回复后再发下一条。最后主动断连。"""
    replies: list[str] = []
    async with websockets.connect(f"{WS_URL}/ws/{session_id}") as ws:
        for msg in messages:
            await ws.send(json.dumps({"type": "text", "content": msg}))
            log("WS", f"发: {msg[:30]}")

            current_reply = ""
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=60)
                payload = json.loads(raw)
                t = payload.get("type")
                if t == "text_chunk":
                    current_reply += payload.get("content", "")
                elif t == "text_done":
                    current_reply = payload.get("content", current_reply)
                    log("WS", f"收 (done): {current_reply[:60]}...")
                    break
                elif t == "text_patch":
                    current_reply = payload.get("content", "")
                    log("WS", f"收 (patch): {current_reply[:60]}...")
                    break
                elif t in ("status", "strategy_hint", "transcription"):
                    continue
                else:
                    log("WS", f"忽略 type={t}")
            if collect_replies:
                replies.append(current_reply)
    log("WS", f"session={session_id[:8]} 已断开")
    return replies


def query_db(sql: str, params: tuple = ()) -> list:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def cleanup_user(user_id: str):
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM conversations WHERE user_id = ?", (user_id,))
        sids = [r[0] for r in cur.fetchall()]
        for sid in sids:
            cur.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
            cur.execute("DELETE FROM conversation_summaries WHERE session_id = ?", (sid,))
        cur.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM narrative_arcs WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM user_profiles WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM relationship_states WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        log("CLEAN", f"删除 user={user_id[:8]} 共 {len(sids)} 个 session")
    finally:
        conn.close()


async def wait_for_finalize(user_id: str, timeout: float = 45.0) -> bool:
    """
    轮询 DB 等待 finalize 写入完成。

    narrative_arcs 是 per-turn record_emotion_snapshot 写的，每条消息后就有。
    user_profiles / relationship_states 才是 finalize_session_memory 的产物。
    所以要等 user_profiles 出现，光看 narrative_arcs 会被骗。
    """
    start = time.time()
    while time.time() - start < timeout:
        narratives = query_db(
            "SELECT COUNT(*) FROM narrative_arcs WHERE user_id = ?", (user_id,)
        )
        profile = query_db(
            "SELECT COUNT(*) FROM user_profiles WHERE user_id = ?", (user_id,)
        )
        n_narr = narratives[0][0] if narratives else 0
        n_prof = profile[0][0] if profile else 0
        if n_prof > 0:
            log("DB", f"finalize 落库: narrative_arcs={n_narr}, user_profiles={n_prof}")
            return True
        await asyncio.sleep(1)
    log("DB", f"finalize 超时 {timeout}s 仍无 user_profiles（narrative_arcs={n_narr}）")
    return False


async def main() -> int:
    user_id = None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            log("STEP", "1. 注册测试用户")
            token, user_id = await register(client)
            log("STEP", f"   user_id={user_id[:8]}, username={TEST_USERNAME}")

            log("STEP", "2. 创建 session_1")
            sid1 = await create_session(client, token)
            log("STEP", f"   session_1={sid1[:8]}")

            log("STEP", "3. session_1 聊 3 条消息")
            await chat_one_session(sid1, SESSION_1_MESSAGES, collect_replies=False)

            log("STEP", "4. 等 finalize 完成（轮询 DB）")
            await wait_for_finalize(user_id, timeout=30)

            log("STEP", "5. 检查 SQLite 写入情况")
            narratives = query_db(
                "SELECT theme, trend, snapshots_json FROM narrative_arcs WHERE user_id = ?",
                (user_id,),
            )
            log("DB", f"  narrative_arcs: {len(narratives)} 条")
            for theme, trend, snaps_json in narratives:
                snaps = json.loads(snaps_json)
                log("DB", f"    theme={theme}, trend={trend}, snapshots={len(snaps)}")

            profile_rows = query_db(
                "SELECT profile_json FROM user_profiles WHERE user_id = ?", (user_id,)
            )
            for (pj,) in profile_rows:
                p = json.loads(pj)
                log("DB", f"  user_profile: phase={p.get('current_phase')}, "
                          f"strengths={p.get('signature_strengths')}, "
                          f"distortions={p.get('common_distortions')}")

            log("STEP", "6. 创建 session_2，问 AI 是否记得")
            sid2 = await create_session(client, token)
            log("STEP", f"   session_2={sid2[:8]}")

            log("STEP", "7. session_2 发问题")
            replies = await chat_one_session(sid2, [SESSION_2_QUESTION], collect_replies=True)
            ai_reply = replies[0] if replies else ""
            log("STEP", f"   AI 回复: {ai_reply}")

            log("STEP", "8. 验证关键词")
            hits = [kw for kw in EXPECTED_KEYWORDS if kw in ai_reply]
            log("CHECK", f"   命中关键词: {hits}")

            ok_db = bool(narratives) or bool(profile_rows)
            ok_reply = len(hits) > 0
            if ok_db and ok_reply:
                log("RESULT", "[PASS] 跨会话记忆生效")
                return 0
            else:
                log("RESULT",
                    f"[FAIL] db_written={ok_db}, reply_recalls={ok_reply}")
                return 1

    except Exception as e:
        log("ERROR", f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 2
    finally:
        if user_id:
            log("STEP", "9. 清理测试数据")
            try:
                cleanup_user(user_id)
            except Exception as e:
                log("CLEAN", f"清理失败: {e}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
