"""
端到端性能实测：注册临时账号 → 建会话 → WS 发一条消息 → 测各阶段时间
跑完后请 ssh 拉服务器 data/llm_calls.jsonl 最后几条做调用拆解
"""
import asyncio
import json
import time
import aiohttp

BASE_HTTP = "https://xinyu.acai777.cn"
BASE_WS = "wss://xinyu.acai777.cn"

TEST_MSG = "最近工作压力很大，总觉得做什么都不对，是不是我能力有问题？"


async def main():
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as http:
        wall = time.monotonic()

        # 1. 注册
        uname = f"perf_{int(time.time())}"
        t1 = time.monotonic()
        async with http.post(
            f"{BASE_HTTP}/api/auth/register",
            json={"username": uname, "password": "test123456"},
        ) as r:
            r.raise_for_status()
            data = await r.json()
            token = data["access_token"]
            user_id = data["user_id"]
        print(f"[+{time.monotonic()-wall:5.2f}s] registered user={user_id[:8]} ({time.monotonic()-t1:.2f}s)")

        # 2. 建 session
        t2 = time.monotonic()
        async with http.post(
            f"{BASE_HTTP}/api/history/sessions",
            json={"title": "perf-test"},
            headers={"Authorization": f"Bearer {token}"},
        ) as r:
            r.raise_for_status()
            data = await r.json()
            session_id = data["session_id"]
        print(f"[+{time.monotonic()-wall:5.2f}s] session={session_id[:8]} ({time.monotonic()-t2:.2f}s)")

        # 3. WS 连接 + 发消息 + 收回复
        ws_url = f"{BASE_WS}/ws/{session_id}"
        t3 = time.monotonic()
        async with http.ws_connect(ws_url, heartbeat=30) as ws:
            print(f"[+{time.monotonic()-wall:5.2f}s] WS connected ({time.monotonic()-t3:.2f}s)")

            send_t = time.monotonic()
            await ws.send_json({"type": "text", "content": TEST_MSG})
            print(f"[+{time.monotonic()-wall:5.2f}s] SENT: {TEST_MSG}")

            status_at = None
            ttft_at = None       # 首字 chunk 到达时间
            text_at = None       # text_done / text_patch 到达时间
            strategy_at = None
            chunks_count = 0
            chunks_acc = ""       # 累积的 text_chunk 内容
            reply_text = ""       # 最终文本（done 用 chunks_acc，patch 用 content）
            patched = False
            emotion = None

            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                data = json.loads(msg.data)
                msg_type = data.get("type")
                now = time.monotonic()
                elapsed_send = now - send_t

                if msg_type == "status":
                    status_at = elapsed_send
                    print(f"[+{now-wall:5.2f}s | +{elapsed_send:.2f}s after send] STATUS: {data.get('content')}")

                elif msg_type == "text_chunk":
                    chunks_count += 1
                    delta = data.get("content", "")
                    chunks_acc += delta
                    if ttft_at is None:
                        ttft_at = elapsed_send
                        print(f"[+{now-wall:5.2f}s | +{elapsed_send:.2f}s after send] FIRST CHUNK ({len(delta)} chars)")

                elif msg_type in ("text_done", "text_patch"):
                    text_at = elapsed_send
                    patched = (msg_type == "text_patch")
                    reply_text = data.get("content", "") if patched else chunks_acc
                    emotion = data.get("emotion")
                    kind_label = "TEXT_PATCH (改写)" if patched else "TEXT_DONE (流字未改)"
                    print(f"[+{now-wall:5.2f}s | +{elapsed_send:.2f}s after send] {kind_label} ({len(reply_text)} chars, {chunks_count} chunks):")
                    safe = reply_text[:300].encode("utf-8", errors="replace").decode("utf-8")
                    try:
                        print(f"  {safe}")
                    except UnicodeEncodeError:
                        print(f"  {safe.encode('ascii', errors='replace').decode('ascii')}")
                    if emotion:
                        print(f"  emotion: {emotion}")
                    # 主文完成后，再等 5 秒看有没有 strategy_hint
                    try:
                        late_msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                        if late_msg.type == aiohttp.WSMsgType.TEXT:
                            d2 = json.loads(late_msg.data)
                            if d2.get("type") == "strategy_hint":
                                strategy_at = time.monotonic() - send_t
                                print(f"[+{time.monotonic()-wall:5.2f}s | +{strategy_at:.2f}s] STRATEGY: {d2.get('content')[:100]}")
                    except asyncio.TimeoutError:
                        pass
                    break

            await ws.close()

        print()
        print("=" * 60)
        print("性能小结")
        print("=" * 60)
        print(f"  注册: {t2-t1:.2f}s")
        print(f"  建会话: {t3-t2:.2f}s")
        if status_at is not None:
            print(f"  发送 → thinking status: {status_at:.2f}s")
        if ttft_at is not None:
            print(f"  发送 → 首字 (TTFT): {ttft_at:.2f}s  ← MAOMAO 看到字开始出来的延迟")
        if text_at is not None:
            kind = "改写后完整文本" if patched else "流字完成"
            print(f"  发送 → 完整回复 ({kind}): {text_at:.2f}s  ← 端到端延迟")
        if ttft_at is not None and text_at is not None:
            print(f"  流字总时长: {text_at - ttft_at:.2f}s ({chunks_count} chunks)")
        if strategy_at is not None:
            print(f"  发送 → strategy_hint: {strategy_at:.2f}s")
        print(f"  总耗时: {time.monotonic()-wall:.2f}s")
        print()
        print(f"  测试账号: {uname}")
        print(f"  session_id: {session_id}")


if __name__ == "__main__":
    asyncio.run(main())
