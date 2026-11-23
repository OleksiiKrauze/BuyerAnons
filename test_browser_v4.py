"""Test browser scraping v4 - with stealth mode."""
import asyncio
import re
import os
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

os.makedirs("/app/output", exist_ok=True)


async def scrape_george_page(url: str):
    print("=" * 60)
    print("Browser Scraping v4 - Stealth Mode")
    print("=" * 60)

    async with async_playwright() as p:
        # Launch with more realistic settings
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-GB",
            timezone_id="Europe/London",
            geolocation={"latitude": 51.5074, "longitude": -0.1278},
            permissions=["geolocation"],
        )

        page = await context.new_page()

        # Apply stealth mode
        await stealth_async(page)
        print("   Stealth mode applied")

        # Set extra headers
        await page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })

        print("\n1. Loading page...")
        print(f"   URL: {url[:70]}...")

        response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        print(f"   Response status: {response.status}")
        print(f"   Final URL: {page.url[:70]}...")

        # Wait for dynamic content
        print("   Waiting for content to render...")
        await asyncio.sleep(10)

        # Handle cookie consent
        try:
            accept_btn = page.locator('#onetrust-accept-btn-handler')
            if await accept_btn.is_visible(timeout=3000):
                await accept_btn.click()
                print("   Accepted cookies")
                await asyncio.sleep(2)
        except:
            pass

        # Scroll
        for i in range(5):
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(0.5)
        print("   Scrolled page")

        # Take screenshot
        await page.screenshot(path="/app/output/screenshot_v4.png", full_page=False)
        print("   Screenshot saved")

        # Check what we got
        title = await page.title()
        print(f"\n2. Page title: {title}")

        # Count elements
        print("\n3. Element analysis:")
        counts = await page.evaluate("""
            () => {
                return {
                    divs: document.querySelectorAll('div').length,
                    imgs: document.querySelectorAll('img').length,
                    links: document.querySelectorAll('a').length,
                    buttons: document.querySelectorAll('button').length,
                    priceElements: document.querySelectorAll('[class*="price"]').length,
                    productElements: document.querySelectorAll('[class*="product"], [class*="tile"], [class*="card"]').length,
                };
            }
        """)
        for key, val in counts.items():
            print(f"   {key}: {val}")

        # Get HTML
        html = await page.content()
        with open("/app/output/page_v4.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n4. HTML saved: {len(html)} bytes")

        # Search for products/prices
        print("\n5. Searching for content patterns:")

        patterns = {
            "GEM IDs": r'GEM\d{6,}',
            "Prices £X.XX": r'£\d+\.\d{2}',
            "Product URLs": r'/george/[^"]+pd\.html',
            "Image URLs scene7": r'scene7\.com[^"\'>\s]+',
        }

        for name, pattern in patterns.items():
            matches = list(set(re.findall(pattern, html)))
            if matches:
                print(f"   {name}: {len(matches)} unique")
                for m in matches[:3]:
                    print(f"      {m[:60]}")
            else:
                print(f"   {name}: 0")

        # Check if we're on a Cloudflare challenge page
        if "challenge" in html.lower() or "cf-browser-verification" in html.lower():
            print("\n   ⚠️ Cloudflare challenge detected!")

        # Check for redirect message
        if "redirectFromInt" in page.url:
            print("\n   ⚠️ Site redirected us (possible geo-block or bot detection)")

        await browser.close()

    print("\n" + "=" * 60)
    print("Done! Check output/screenshot_v4.png")
    print("=" * 60)


if __name__ == "__main__":
    url = "https://direct.asda.com/george/baby-girl/D5M10G1,default,sc.html"
    asyncio.run(scrape_george_page(url))
