"""Test browser scraping for discount prices."""
import asyncio
import re
import json
from playwright.async_api import async_playwright


async def scrape_george_page(url: str):
    print("=" * 60)
    print("Testing Browser Scraping for Discounts")
    print("=" * 60)
    print(f"\nURL: {url[:80]}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        print("\n1. Loading page...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(3)

            # Handle cookie consent
            try:
                accept_btn = page.locator('button:has-text("Accept"), #onetrust-accept-btn-handler').first
                if await accept_btn.is_visible(timeout=3000):
                    await accept_btn.click()
                    print("   Clicked cookie consent")
                    await asyncio.sleep(1)
            except:
                pass

            # Scroll to load more products
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(0.5)

            print("   Page loaded!")

            # Get page content
            html = await page.content()
            print(f"   HTML size: {len(html)} bytes")

            # Save HTML for analysis
            with open("/app/page_dump.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("   Saved HTML to page_dump.html")

            # Try to find product data in JSON
            print("\n2. Looking for embedded JSON data...")

            # Look for dataLayer or similar
            json_patterns = [
                (r'window\.__INITIAL_STATE__\s*=\s*({.+?});', 'INITIAL_STATE'),
                (r'dataLayer\.push\(({.+?"ecommerce".+?})\)', 'dataLayer'),
                (r'"products"\s*:\s*(\[{.+?}\])', 'products array'),
            ]

            for pattern, name in json_patterns:
                matches = re.findall(pattern, html, re.DOTALL)
                if matches:
                    print(f"   Found {name}: {len(matches)} match(es)")

            # Try to extract products from HTML structure
            print("\n3. Extracting products from HTML...")

            # Look for product cards with various selectors
            selectors = [
                '.product-tile',
                '.product-card',
                '[data-product-id]',
                '.product-item',
                '.plp-product-tile',
                'article[data-product]',
            ]

            for selector in selectors:
                elements = await page.locator(selector).count()
                if elements > 0:
                    print(f"   Found {elements} elements with selector: {selector}")

            # Try to get product info using George's specific structure
            print("\n4. Trying to extract product details...")

            # Look for price elements
            price_selectors = [
                '.product-price',
                '.price',
                '[class*="price"]',
                '.was-price',
                '.now-price',
                '.sale-price',
                '.original-price',
            ]

            for selector in price_selectors:
                elements = await page.locator(selector).count()
                if elements > 0:
                    print(f"   Found {elements} price elements: {selector}")
                    # Get first few examples
                    for i in range(min(3, elements)):
                        try:
                            text = await page.locator(selector).nth(i).text_content()
                            if text:
                                print(f"      Example: {text.strip()[:50]}")
                        except:
                            pass

            # Look for specific George price pattern in HTML
            print("\n5. Searching for price patterns in HTML...")

            # Pattern for £XX.XX prices
            price_pattern = r'£(\d+(?:\.\d{2})?)'
            prices = re.findall(price_pattern, html)
            if prices:
                unique_prices = list(set(prices))[:10]
                print(f"   Found {len(prices)} price occurrences")
                print(f"   Sample prices: {unique_prices}")

            # Look for was/now price pairs
            was_now_pattern = r'(?:was|Was|WAS)[^£]*£(\d+(?:\.\d{2})?)[^£]*(?:now|Now|NOW)[^£]*£(\d+(?:\.\d{2})?)'
            was_now = re.findall(was_now_pattern, html, re.IGNORECASE)
            if was_now:
                print(f"   Found {len(was_now)} was/now price pairs!")
                for was, now in was_now[:5]:
                    discount = int((1 - float(now)/float(was)) * 100)
                    print(f"      Was £{was} -> Now £{now} (-{discount}%)")

            # Try evaluating JavaScript to get product data
            print("\n6. Trying to get data via JavaScript...")
            try:
                # Check if there's a global products object
                js_data = await page.evaluate("""
                    () => {
                        // Try various ways to get product data
                        if (window.__INITIAL_STATE__) return {source: 'INITIAL_STATE', data: window.__INITIAL_STATE__};
                        if (window.dataLayer) return {source: 'dataLayer', data: window.dataLayer};
                        if (window.products) return {source: 'products', data: window.products};
                        return null;
                    }
                """)
                if js_data:
                    print(f"   Found JS data: {js_data.get('source')}")
            except Exception as e:
                print(f"   JS evaluation: {str(e)[:50]}")

        except Exception as e:
            print(f"   Error: {e}")

        finally:
            await browser.close()

    print("\n" + "=" * 60)
    print("Scraping test completed!")
    print("=" * 60)


if __name__ == "__main__":
    url = "https://direct.asda.com/george/baby-girl/D5M10G1,default,sc.html?displayAs=George&pmid=grg_tact_2026_wk2_babyevent_clothing&cm_sp=e-desktop_p-homepage-uk_t-tier02_b-block01_d-260112_l-link02_c-babygirlsevent_s-AW_tp-moduleA"
    asyncio.run(scrape_george_page(url))
