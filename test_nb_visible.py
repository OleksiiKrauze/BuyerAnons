"""Test New Balance with visible browser."""
import asyncio
from playwright.async_api import async_playwright

async def test():
    print("Starting visible Firefox...")

    pw = await async_playwright().start()
    browser = await pw.firefox.launch(headless=False)  # Visible browser

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        viewport={"width": 1920, "height": 1080},
    )

    page = await context.new_page()

    print("Loading page...")
    await page.goto("https://www.joesnewbalanceoutlet.com/women/deals/bundle-and-save/", timeout=60000)

    await asyncio.sleep(5)

    html = await page.content()
    print(f"HTML size: {len(html)} bytes")

    if "Oops" in html:
        print("BLOCKED!")
    else:
        print("SUCCESS!")
        els = await page.query_selector_all('[data-style-price]')
        print(f"Found {len(els)} products")

    input("Press Enter to close...")
    await browser.close()
    await pw.stop()

asyncio.run(test())
