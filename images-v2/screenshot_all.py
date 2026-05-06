"""批量截图所有小红书图片"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:8765/images-v2/"
OUTPUT_DIR = Path(r"H:\AI\心理学agent\images-v2")

# 所有需要截图的页面
PAGES = [
    # 种草帖 6张
    "zc-01-cover.html",
    "zc-02-pain.html",
    "zc-03-intro.html",
    "zc-04-features.html",
    "zc-05-dialogue.html",
    "zc-06-end.html",
    # 测评帖 7张
    "cp-01-cover.html",
    "cp-02-overview.html",
    "cp-03-emotion.html",
    "cp-04-distortion.html",
    "cp-05-safety.html",
    "cp-06-radar.html",
    "cp-07-conclusion.html",
    # 科普帖 9张
    "kp-01-cover.html",
    "kp-02-concept.html",
    "kp-03-distortion-1.html",
    "kp-04-distortion-2.html",
    "kp-05-distortion-3.html",
    "kp-06-distortion-4.html",
    "kp-07-practice.html",
    "kp-08-perma.html",
    "kp-09-end.html",
]


async def screenshot_page(page, url: str, output: Path):
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(800)  # 等字体加载
    await page.screenshot(path=str(output), full_page=False)
    print(f"  [OK] {output.name}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1080, "height": 1440},
            device_scale_factor=2,  # 高清
        )
        page = await context.new_page()

        for html in PAGES:
            html_path = OUTPUT_DIR / html
            if not html_path.exists():
                print(f"  [SKIP] {html} (not found)")
                continue
            png_path = OUTPUT_DIR / html.replace(".html", ".png")
            await screenshot_page(page, BASE_URL + html, png_path)

        await browser.close()
        print(f"\nDone! Images at: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
