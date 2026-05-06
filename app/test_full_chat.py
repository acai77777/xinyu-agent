"""
完整对话测试：前端发消息 -> 后端 Agent 循环 -> Claude API -> AI 回复显示
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})

    logs = []
    page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))

    print("=== 1. 打开聊天页 ===")
    page.goto("http://localhost:8081/chat/e2e-full")
    page.wait_for_load_state("networkidle")
    time.sleep(3)

    status = page.locator("text=在线")
    if status.is_visible():
        print("  [OK] WebSocket 已连接")
    else:
        print("  [WARN] WebSocket 未连接")

    print("\n=== 2. 发送第一条消息 ===")
    input_el = page.locator("textarea").last
    if not input_el.is_visible():
        input_el = page.locator("input").last
    input_el.click()
    input_el.fill("我最近压力很大，工作上总是加班，感觉很累")
    time.sleep(0.5)
    input_el.press("Enter")
    print("  [OK] 消息已发送: '我最近压力很大，工作上总是加班，感觉很累'")

    print("\n=== 3. 等待 AI 回复（最多60秒）===")
    initial_text = page.inner_text("body")
    ai_replied = False
    for i in range(60):
        time.sleep(1)
        current_text = page.inner_text("body")
        # Check if new text appeared beyond what we had
        if len(current_text) > len(initial_text) + 20:
            ai_replied = True
            # Extract the new part
            new_content = current_text[len(initial_text):]
            print(f"  [OK] AI 已回复（等待 {i+1} 秒）")
            # Find AI response text
            break
        if i % 10 == 9:
            print(f"  ... 等待中（{i+1}秒）")

    page.screenshot(path="/tmp/e2e_round1.png")

    if not ai_replied:
        print("  [FAIL] 60秒内未收到 AI 回复")
        # Check backend logs
        errors = [l for l in logs if "error" in l.lower()]
        if errors:
            print(f"  控制台错误: {errors[:3]}")
        browser.close()
        sys.exit(1)

    print("\n=== 4. 发送第二条消息 ===")
    time.sleep(2)
    input_el2 = page.locator("textarea").last
    if not input_el2.is_visible():
        input_el2 = page.locator("input").last
    input_el2.click()
    input_el2.fill("有什么方法能让我放松一下吗")
    time.sleep(0.5)
    input_el2.press("Enter")
    print("  [OK] 消息已发送: '有什么方法能让我放松一下吗'")

    print("\n=== 5. 等待第二轮回复（最多60秒）===")
    after_send2 = page.inner_text("body")
    for i in range(60):
        time.sleep(1)
        current = page.inner_text("body")
        if len(current) > len(after_send2) + 20:
            print(f"  [OK] 第二轮 AI 已回复（等待 {i+1} 秒）")
            break
        if i % 10 == 9:
            print(f"  ... 等待中（{i+1}秒）")

    page.screenshot(path="/tmp/e2e_round2.png")

    errors = [l for l in logs if l.startswith("[error")]
    if errors:
        print(f"\n  [WARN] 控制台错误: {errors[:5]}")

    print(f"\n=== 完整对话测试结束 ===")
    browser.close()
