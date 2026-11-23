"""Test Joe's New Balance Outlet with different approaches."""
import asyncio
import sys
sys.path.insert(0, '/app')

from loguru import logger
from playwright.async_api import async_playwright


async def test_chromium():
    """Test with Chromium and stealth."""
    logger.info("Testing with Chromium...")

    url = "https://www.joesnewbalanceoutlet.com/women/deals/bundle-and-save/"

    playwright = await async_playwright().start()

    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--window-size=1920,1080',
        ]
    )

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York",
    )

    # Stealth scripts for Chromium
    await context.add_init_script("""
        // Mask webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
            configurable: true
        });

        // Mask chrome
        window.chrome = {
            runtime: {},
        };

        // Mask permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );

        // Mask plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Mask languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
    """)

    page = await context.new_page()

    response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    logger.info(f"Chromium status: {response.status}")

    await asyncio.sleep(5)

    html = await page.content()
    logger.info(f"HTML size: {len(html)} bytes")

    if "Oops" in html:
        logger.warning("Chromium BLOCKED")
    else:
        logger.info("Chromium SUCCESS!")
        price_els = await page.query_selector_all('[data-style-price]')
        logger.info(f"Found {len(price_els)} price elements")

    await context.close()
    await browser.close()
    await playwright.stop()


async def test_api():
    """Try to find and use any API endpoints."""
    import httpx

    logger.info("Testing API approaches...")

    # Try different API patterns that New Balance sites commonly use
    apis_to_try = [
        # Search API
        "https://www.joesnewbalanceoutlet.com/on/demandware.store/Sites-joes-Site/default/Search-UpdateGrid?cgid=women-deals-bundle-and-save&pmin=0&start=0&sz=24",
        # Catalog API
        "https://www.joesnewbalanceoutlet.com/on/demandware.store/Sites-joes-Site/default/Product-GetProducts?cgid=women-deals-bundle-and-save",
        # Alternative search endpoint
        "https://www.joesnewbalanceoutlet.com/s/women/deals/bundle-and-save?format=ajax",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.joesnewbalanceoutlet.com/women/deals/bundle-and-save/",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for api_url in apis_to_try:
            try:
                response = await client.get(api_url, headers=headers)
                logger.info(f"API {api_url[:60]}... => {response.status_code}, {len(response.text)} bytes")
                if response.status_code == 200 and len(response.text) > 1000:
                    # Found something
                    print(f"\n=== POSSIBLE API FOUND ===")
                    print(f"URL: {api_url}")
                    print(f"Response preview: {response.text[:500]}")
                    print("=" * 50)
            except Exception as e:
                logger.error(f"API error: {e}")


async def main():
    await test_chromium()
    await test_api()


if __name__ == "__main__":
    asyncio.run(main())
