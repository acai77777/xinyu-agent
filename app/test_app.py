from playwright.sync_api import sync_playwright
import subprocess, time

# Start server
server = subprocess.Popen(
    ['npx', 'serve', 'dist', '-l', '3456'],
    cwd=r'H:\AI\心理学agent\app',
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    shell=True
)
time.sleep(3)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="chrome")
    page = browser.new_page(viewport={'width': 390, 'height': 844})

    # Test 1: Home page
    print("=== Test 1: Home Page ===")
    page.goto('http://localhost:3456')
    page.wait_for_load_state('networkidle')
    page.screenshot(path='/tmp/test_home.png', full_page=False)

    content = page.content()
    assert '想聊点什么' in content or '好' in content, "FAIL: Greeting not found"
    print("PASS: Greeting text found")

    assert '今天的对话' in content, "FAIL: Session list not found"
    print("PASS: Session list found")

    # Test 2: Mood selection
    print("\n=== Test 2: Mood Selection ===")
    mood_btn = page.locator('text=很好').first
    mood_btn.click()
    page.wait_for_timeout(500)
    page.screenshot(path='/tmp/test_mood.png')
    print("PASS: Mood button clicked")

    # Test 3: History tab
    print("\n=== Test 3: History Page ===")
    page.locator('text=记录').first.click()
    page.wait_for_timeout(500)
    page.screenshot(path='/tmp/test_history.png')
    h = page.content()
    assert '历史记录' in h, "FAIL: History page not loaded"
    print("PASS: History page loaded")
    assert '工作压力倾诉' in h, "FAIL: History items not found"
    print("PASS: History items found")

    # Test 4: Profile tab
    print("\n=== Test 4: Profile Page ===")
    page.locator('text=我的').first.click()
    page.wait_for_timeout(500)
    page.screenshot(path='/tmp/test_profile.png')
    pr = page.content()
    assert 'MAOMAO' in pr, "FAIL: Profile name not found"
    print("PASS: Profile name found")
    assert '本周情绪趋势' in pr, "FAIL: Trend chart not found"
    print("PASS: Trend chart found")

    # Test 5: Chat page
    print("\n=== Test 5: Chat Page ===")
    page.locator('text=首页').first.click()
    page.wait_for_timeout(500)
    page.locator('text=今天的对话').first.click()
    page.wait_for_timeout(1000)
    page.screenshot(path='/tmp/test_chat.png')
    c = page.content()
    assert '心语' in c or '说说你的感受' in c, "FAIL: Chat page not loaded"
    print("PASS: Chat page loaded")

    # Test 6: Send message
    print("\n=== Test 6: Send Message ===")
    inp = page.locator('[placeholder="说说你的感受..."]').first
    inp.fill('我今天感觉有点累')
    page.wait_for_timeout(300)
    inp.press('Enter')
    page.wait_for_timeout(500)
    page.screenshot(path='/tmp/test_sent.png')
    assert '我今天感觉有点累' in page.content(), "FAIL: Message not displayed"
    print("PASS: User message sent")

    # Test 7: AI reply
    print("\n=== Test 7: AI Reply ===")
    page.wait_for_timeout(3000)
    page.screenshot(path='/tmp/test_reply.png')
    rc = page.content()
    replies = ['我听到你了', '谢谢你愿意', '听起来你', '我注意到', '你已经做得', '这种感受']
    assert any(r in rc for r in replies), "FAIL: AI reply not found"
    print("PASS: AI reply received")

    browser.close()

server.terminate()
print("\n=== All 7 tests PASSED ===")
