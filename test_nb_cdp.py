"""Test connecting to existing Chrome via CDP."""
import asyncio
import subprocess
import time
from playwright.async_api import async_playwright

async def test():
    # Start Chrome with debugging port
    print("Starting Chrome with debugging...")
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    proc = subprocess.Popen([
        chrome_path,
        "--remote-debugging-port=9222",
        "--user-data-dir=C:\\temp\\chrome_debug",
        "https://www.joesnewbalanceoutlet.com/women/deals/bundle-and-save/"
    ])

    print("Waiting for Chrome to load...")
    time.sleep(10)

    # Connect via CDP
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")

    contexts = browser.contexts
    if contexts:
        page = contexts[0].pages[0]

        html = await page.content()
        print(f"HTML size: {len(html)} bytes")

        if "Oops" in html:
            print("BLOCKED!")
        else:
            print("SUCCESS!")
            els = await page.query_selector_all('[data-style-price]')
            print(f"Found {len(els)} products")

            # Print first few
            for i, el in enumerate(els[:3]):
                data = await el.get_attribute('data-style-price')
                print(f"Product {i+1}: {data[:80]}...")

    await browser.close()
    await pw.stop()
    proc.terminate()

asyncio.run(test())
