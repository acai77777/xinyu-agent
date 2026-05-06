"""
直接 WebSocket 测试：跳过前端，直接连后端 WebSocket 验证 Agent 循环
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import asyncio
import websockets
import json

async def test_chat():
    uri = "ws://localhost:8000/ws/ws-direct-test"

    print("=== 1. 连接 WebSocket ===")
    try:
        async with websockets.connect(uri) as ws:
            print("  [OK] 已连接")

            print("\n=== 2. 发送消息 ===")
            msg = {"type": "text", "content": "我最近压力很大，工作上总是加班，感觉很累"}
            await ws.send(json.dumps(msg))
            print(f"  [OK] 已发送: {msg['content']}")

            print("\n=== 3. 等待回复 ===")
            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=60)
                    data = json.loads(response)
                    print(f"  收到: type={data.get('type')}")

                    if data.get("type") == "status":
                        print(f"    状态: {data.get('content')}")
                    elif data.get("type") == "text":
                        content = data.get("content", "")
                        emotion = data.get("emotion", {})
                        crisis = data.get("crisis_holding", False)
                        print(f"    AI回复: {content[:200]}")
                        if emotion:
                            print(f"    情绪: {emotion}")
                        if crisis:
                            print(f"    危机抱持: {crisis}")
                        break
                    else:
                        print(f"    数据: {json.dumps(data, ensure_ascii=False)[:200]}")
                except asyncio.TimeoutError:
                    print("  [FAIL] 60秒超时")
                    break

            print("\n=== 4. 发送第二条消息 ===")
            msg2 = {"type": "text", "content": "有什么方法能让我放松一下吗"}
            await ws.send(json.dumps(msg2))
            print(f"  [OK] 已发送: {msg2['content']}")

            print("\n=== 5. 等待第二轮回复 ===")
            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=60)
                    data = json.loads(response)
                    print(f"  收到: type={data.get('type')}")

                    if data.get("type") == "status":
                        print(f"    状态: {data.get('content')}")
                    elif data.get("type") == "text":
                        content = data.get("content", "")
                        emotion = data.get("emotion", {})
                        print(f"    AI回复: {content[:200]}")
                        if emotion:
                            print(f"    情绪: {emotion}")
                        break
                except asyncio.TimeoutError:
                    print("  [FAIL] 60秒超时")
                    break

            print("\n=== 完整对话测试通过 ===")

    except Exception as e:
        print(f"  [FAIL] 连接失败: {e}")

asyncio.run(test_chat())
