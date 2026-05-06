from playwright.sync_api import sync_playwright
import sys
sys.stdout.reconfigure(encoding='utf-8')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})

    console_logs = []
    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

    # Login
    page.goto('https://xinyu.acai777.cn', wait_until='networkidle')
    page.wait_for_timeout(3000)
    inputs = page.locator('input').all()
    inputs[0].fill("testbot2")
    inputs[1].fill("test1234")
    page.get_by_text("登录").first.click()
    page.wait_for_timeout(4000)

    # Navigate to chat
    try:
        page.get_by_text("还没有对话").first.click(timeout=5000)
    except:
        page.mouse.click(338, 710)
    page.wait_for_timeout(6000)

    # Type and send
    textarea = page.locator('textarea').first
    textarea.click()
    textarea.fill("你好")
    page.wait_for_timeout(1000)
    page.mouse.click(360, 716)
    print("Message sent, waiting for response...")

    # Wait for AI response (up to 60 seconds)
    page.wait_for_timeout(45000)
    page.screenshot(path='H:/AI/心理学agent/app/ss5_final.png', full_page=True)
    print("Final screenshot taken")

    print("\n--- Console Logs ---")
    for log in console_logs:
        print(log)

    browser.close()
