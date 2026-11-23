"""Test Zara API v3 - Search API and Playwright."""
import asyncio
import httpx
import json
import re
import os
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

os.makedirs("/app/output", exist_ok=True)


async def test_search_api():
    """Test Zara search API."""
    print("=" * 60)
    print("Part 1: Zara Search API")
    print("=" * 60)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Test search API
        search_url = "https://www.zara.com/uk/en/search?searchTerm=dress&ajax=true"
        print(f"\n1. Testing search: {search_url}")

        try:
            resp = await client.get(search_url, headers=headers)
            print(f"   Status: {resp.status_code}")
            print(f"   Content-Type: {resp.headers.get('content-type', 'N/A')}")
            print(f"   Content-Length: {len(resp.content)} bytes")

            # Try to decode with different encodings
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    text = resp.content.decode(encoding)
                    print(f"   Decoded with {encoding}: {len(text)} chars")

                    # Check if it's JSON
                    if text.strip().startswith('{') or text.strip().startswith('['):
                        data = json.loads(text)
                        print(f"   JSON type: {type(data).__name__}")
                        if isinstance(data, dict):
                            print(f"   Keys: {list(data.keys())}")

                            # Look for products
                            for key in ['products', 'items', 'results', 'productGroups']:
                                if key in data:
                                    items = data[key]
                                    if isinstance(items, list) and len(items) > 0:
                                        print(f"\n   Found {len(items)} {key}!")
                                        # Show first product
                                        p = items[0]
                                        if isinstance(p, dict):
                                            print(f"   Sample product keys: {list(p.keys())[:10]}")
                                            name = p.get('name', p.get('productName', p.get('displayName', 'N/A')))
                                            price = p.get('price', p.get('currentPrice', 'N/A'))
                                            print(f"   Name: {name}")
                                            print(f"   Price: {price}")
                    break
                except Exception as e:
                    print(f"   {encoding} failed: {str(e)[:50]}")

        except Exception as e:
            print(f"   Error: {e}")


async def test_playwright():
    """Test Zara with Playwright."""
    print("\n" + "=" * 60)
    print("Part 2: Zara with Playwright")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-GB",
        )
        page = await context.new_page()
        await stealth_async(page)

        print("\n1. Loading Zara sale page...")
        url = "https://www.zara.com/uk/en/woman-sale-l1314.html"

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print("   DOM loaded, waiting for content...")
            await asyncio.sleep(10)

            # Accept cookies if present
            try:
                cookie_btn = page.locator('#onetrust-accept-btn-handler, button:has-text("ACCEPT")')
                if await cookie_btn.is_visible(timeout=3000):
                    await cookie_btn.click()
                    print("   Accepted cookies")
                    await asyncio.sleep(2)
            except:
                pass

            # Scroll to load products
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(0.5)

            # Take screenshot
            await page.screenshot(path="/app/output/zara_screenshot.png")
            print("   Screenshot saved")

            # Get page info
            title = await page.title()
            current_url = page.url
            print(f"\n2. Page info:")
            print(f"   Title: {title}")
            print(f"   URL: {current_url[:70]}...")

            # Count elements
            counts = await page.evaluate("""
                () => ({
                    divs: document.querySelectorAll('div').length,
                    imgs: document.querySelectorAll('img').length,
                    links: document.querySelectorAll('a').length,
                    productCards: document.querySelectorAll('[class*="product"], [data-productid]').length,
                    prices: document.querySelectorAll('[class*="price"]').length,
                })
            """)
            print(f"\n3. Element counts:")
            for k, v in counts.items():
                print(f"   {k}: {v}")

            # Get HTML
            html = await page.content()
            with open("/app/output/zara_full.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"\n4. HTML saved: {len(html)} bytes")

            # Look for product data
            print("\n5. Searching for products...")

            # Try to get products from page
            products = await page.evaluate("""
                () => {
                    const results = [];
                    // Zara uses various product selectors
                    const selectors = [
                        '.product-grid-product',
                        '[data-productid]',
                        '.product-card',
                        'article.product',
                        'li.product-grid__item',
                    ];

                    for (const sel of selectors) {
                        const items = document.querySelectorAll(sel);
                        if (items.length > 0) {
                            items.forEach((item, idx) => {
                                if (idx < 10) {
                                    const nameEl = item.querySelector('[class*="name"], [class*="title"], h2, h3');
                                    const priceEl = item.querySelector('[class*="price"]');
                                    const oldPriceEl = item.querySelector('[class*="old"], [class*="was"], [class*="original"], s, del');
                                    const imgEl = item.querySelector('img');
                                    const linkEl = item.querySelector('a');

                                    results.push({
                                        selector: sel,
                                        name: nameEl ? nameEl.textContent.trim() : null,
                                        price: priceEl ? priceEl.textContent.trim() : null,
                                        oldPrice: oldPriceEl ? oldPriceEl.textContent.trim() : null,
                                        img: imgEl ? imgEl.src : null,
                                        link: linkEl ? linkEl.href : null,
                                    });
                                }
                            });
                            break;
                        }
                    }
                    return results;
                }
            """)

            if products:
                print(f"   Found {len(products)} products!")
                for i, p in enumerate(products[:5]):
                    print(f"\n   Product {i+1}:")
                    print(f"      Name: {p.get('name', 'N/A')}")
                    print(f"      Price: {p.get('price', 'N/A')}")
                    print(f"      Old Price: {p.get('oldPrice', 'N/A')}")
            else:
                print("   No products found with standard selectors")

                # Try looking at raw HTML for prices
                print("\n   Searching HTML for price patterns...")
                price_matches = re.findall(r'£\d+\.\d{2}', html)
                if price_matches:
                    unique = list(set(price_matches))[:10]
                    print(f"   Found prices: {unique}")

                # Look for Zara-specific data
                print("\n   Looking for __PRELOADED_STATE__...")
                preload = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.+?});', html, re.DOTALL)
                if preload:
                    print("   Found __PRELOADED_STATE__!")
                    try:
                        data = json.loads(preload.group(1))
                        print(f"   Keys: {list(data.keys())[:10]}")
                    except:
                        print("   Could not parse JSON")

        except Exception as e:
            print(f"   Error: {e}")

        await browser.close()

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


async def main():
    await test_search_api()
    await test_playwright()


if __name__ == "__main__":
    asyncio.run(main())
