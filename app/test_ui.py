"""Playwright UI screenshots for all pages"""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})  # iPhone 14 size

    # 1. Home page
    page.goto("http://localhost:8081")
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    page.screenshot(path="/tmp/ui_home.png", full_page=False)
    print("Home page screenshot saved")

    # 2. Chat page
    page.goto("http://localhost:8081/chat/1")
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    page.screenshot(path="/tmp/ui_chat.png", full_page=False)
    print("Chat page screenshot saved")

    # 3. History page
    page.goto("http://localhost:8081/history")
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    page.screenshot(path="/tmp/ui_history.png", full_page=False)
    print("History page screenshot saved")

    # 4. Profile page
    page.goto("http://localhost:8081/profile")
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    page.screenshot(path="/tmp/ui_profile.png", full_page=False)
    print("Profile page screenshot saved")

    browser.close()
    print("All screenshots done!")
