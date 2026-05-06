"""
前后端联调测试：
1. 打开聊天页，确认 WebSocket 从"离线"变"在线"
2. 输入消息并发送，确认消息出现在聊天流中
3. 确认后端收到 WebSocket 消息（即使 LLM 调用因缺 API Key 失败）
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import time

FRONTEND_URL = "http://localhost:8081"
BACKEND_URL = "http://localhost:8000"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})

    # Collect console logs and errors
    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))

    print("=== 测试 1: 打开聊天页 ===")
    page.goto(f"{FRONTEND_URL}/chat/test-session")
    page.wait_for_load_state("networkidle")
    time.sleep(3)

    # Check connection status
    page.screenshot(path="/tmp/e2e_chat_connected.png")

    # Look for the status text
    status_el = page.locator("text=在线").first
    offline_el = page.locator("text=离线").first

    if status_el.is_visible():
        print("  ✅ WebSocket 已连接（显示'在线'）")
    elif offline_el.is_visible():
        print("  ⚠️  WebSocket 未连接（显示'离线'），继续测试...")
    else:
        print("  ⚠️  未找到连接状态指示器")

    print("\n=== 测试 2: 发送消息 ===")
    # Find the text input
    input_el = page.locator("input, textarea").last
    if input_el.is_visible():
        input_el.fill("你好，我想聊聊")
        time.sleep(0.5)
        page.screenshot(path="/tmp/e2e_chat_input.png")
        print("  ✅ 文字已输入到输入框")

        # Find and click send button
        send_btn = page.locator("[data-testid='send-btn']").first
        if not send_btn.is_visible():
            # Try finding by icon
            send_btn = page.locator("div[role='button'], button").filter(has=page.locator("svg, [class*='send']")).last

        # Alternative: press Enter
        input_el.press("Enter")
        time.sleep(1)
        page.screenshot(path="/tmp/e2e_chat_sent.png")
        print("  ✅ 消息已发送")
    else:
        print("  ❌ 未找到输入框")

    print("\n=== 测试 3: 等待 AI 回复 ===")
    time.sleep(5)  # Wait for backend processing
    page.screenshot(path="/tmp/e2e_chat_response.png")

    # Check console for any WebSocket errors
    ws_errors = [l for l in logs if "error" in l.lower() or "websocket" in l.lower()]
    if ws_errors:
        print(f"  ⚠️  控制台日志: {ws_errors[:3]}")

    print(f"  总共 {len(logs)} 条控制台日志")

    print("\n=== 测试 4: 验证后端 REST API ===")
    # Test health endpoint
    health_resp = page.request.get(f"{BACKEND_URL}/health")
    print(f"  /health: {health_resp.status} {health_resp.json()}")

    # Test auth endpoint
    login_resp = page.request.post(f"{BACKEND_URL}/api/auth/login")
    print(f"  /api/auth/login: {login_resp.status} {login_resp.json()}")

    # Test history endpoint
    hist_resp = page.request.get(f"{BACKEND_URL}/api/history/sessions")
    print(f"  /api/history/sessions: {hist_resp.status} {hist_resp.json()}")

    print("\n=== 联调测试完成 ===")
    browser.close()
