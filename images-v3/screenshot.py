import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8765/images-v3/"
OUT = Path(r"H:\AI\心理学agent\images-v3")

PAGES = [
    "01-cover.html",
    "02-paper-info.html",
    "03-data.html",
    "04-architecture.html",
    "05-xinyu.html",
    "06-cta.html",
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1080, "height": 1440}, device_scale_factor=2)
        page = await ctx.new_page()
        for h in PAGES:
            await page.goto(BASE + h, wait_until="networkidle")
            await page.wait_for_timeout(900)
            png = OUT / h.replace(".html", ".png")
            await page.screenshot(path=str(png), full_page=False)
            print(f"  [OK] {png.name}")
        await browser.close()

asyncio.run(main())
