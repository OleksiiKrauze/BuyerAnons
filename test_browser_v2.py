"""Test browser scraping v2 - deep analysis of dataLayer and HTML."""
import asyncio
import re
import json
from playwright.async_api import async_playwright


async def scrape_george_page(url: str):
    print("=" * 60)
    print("Browser Scraping v2 - Deep Analysis")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        print("\n1. Loading page...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        # Handle cookie consent
        try:
            accept_btn = page.locator('#onetrust-accept-btn-handler, button:has-text("Accept")').first
            if await accept_btn.is_visible(timeout=3000):
                await accept_btn.click()
                await asyncio.sleep(1)
        except:
            pass

        # Scroll to load products
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(0.3)

        print("   Page loaded!")

        # Get dataLayer content
        print("\n2. Analyzing dataLayer...")
        try:
            data_layer = await page.evaluate("() => window.dataLayer")
            if data_layer:
                print(f"   dataLayer has {len(data_layer)} entries")

                # Look for ecommerce/product data
                for i, entry in enumerate(data_layer):
                    if isinstance(entry, dict):
                        # Check for ecommerce data
                        if 'ecommerce' in entry:
                            print(f"\n   Entry {i} has ecommerce data!")
                            ecom = entry['ecommerce']
                            print(f"   Keys: {list(ecom.keys())}")

                            # Look for impressions or products
                            for key in ['impressions', 'products', 'items', 'productImpressions']:
                                if key in ecom and ecom[key]:
                                    products = ecom[key]
                                    print(f"\n   Found {len(products)} products in '{key}'!")

                                    # Show first 5 products
                                    for j, prod in enumerate(products[:5]):
                                        name = prod.get('name', prod.get('item_name', 'N/A'))
                                        price = prod.get('price', prod.get('item_price', 'N/A'))
                                        print(f"      {j+1}. {name}: £{price}")
                                    break

                        # Check for product arrays directly
                        if 'products' in entry:
                            print(f"\n   Entry {i} has products array!")

        except Exception as e:
            print(f"   Error reading dataLayer: {e}")

        # Look for Algolia instant search data
        print("\n3. Looking for Algolia data on page...")
        try:
            algolia_data = await page.evaluate("""
                () => {
                    // Try to find Algolia search results
                    if (window.__ALGOLIA_STATE__) return window.__ALGOLIA_STATE__;
                    if (window.algoliaState) return window.algoliaState;

                    // Look for search results in DOM
                    const hits = document.querySelectorAll('[data-insights-object-id]');
                    if (hits.length > 0) {
                        return Array.from(hits).slice(0, 5).map(el => ({
                            id: el.getAttribute('data-insights-object-id'),
                            html: el.innerHTML.substring(0, 200)
                        }));
                    }
                    return null;
                }
            """)
            if algolia_data:
                print(f"   Found Algolia data: {type(algolia_data)}")
        except Exception as e:
            print(f"   No Algolia state found")

        # Analyze HTML structure for products
        print("\n4. Analyzing HTML structure...")
        html = await page.content()

        # Save HTML
        with open("/app/page_v2.html", "w", encoding="utf-8") as f:
            f.write(html)

        # Look for common product card classes
        product_patterns = [
            r'class="[^"]*product[^"]*tile[^"]*"',
            r'class="[^"]*product[^"]*card[^"]*"',
            r'class="[^"]*plp[^"]*item[^"]*"',
            r'data-product-id="([^"]+)"',
            r'data-sku="([^"]+)"',
        ]

        for pattern in product_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                print(f"   Pattern '{pattern[:30]}...' found {len(matches)} matches")
                if len(matches) <= 5:
                    print(f"      Examples: {matches[:3]}")

        # Look for price HTML patterns
        print("\n5. Looking for price HTML patterns...")

        # Common price class patterns
        price_html_patterns = [
            r'<[^>]*class="[^"]*price[^"]*"[^>]*>([^<]+)</[^>]+>',
            r'<[^>]*class="[^"]*was[^"]*"[^>]*>([^<]+)</[^>]+>',
            r'<[^>]*class="[^"]*now[^"]*"[^>]*>([^<]+)</[^>]+>',
            r'<[^>]*class="[^"]*sale[^"]*"[^>]*>([^<]+)</[^>]+>',
            r'<span[^>]*>£(\d+\.?\d*)</span>',
        ]

        for pattern in price_html_patterns:
            matches = re.findall(pattern, html)
            if matches:
                # Clean and dedupe
                clean = [m.strip() for m in matches if m.strip()][:10]
                if clean:
                    print(f"   Pattern found prices: {clean[:5]}")

        # Try to find product containers and extract structured data
        print("\n6. Extracting product data from page...")
        try:
            products = await page.evaluate("""
                () => {
                    const results = [];

                    // Try different selectors
                    const selectors = [
                        '.product-tile',
                        '.product-card',
                        '[data-product-id]',
                        '.plp-product',
                        'article.product',
                        '.product-item',
                        '.hit', // Algolia
                        '[class*="ProductCard"]',
                        '[class*="product-tile"]',
                    ];

                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            console.log('Found with:', selector, elements.length);

                            elements.forEach((el, idx) => {
                                if (idx < 10) {
                                    // Try to extract product info
                                    const nameEl = el.querySelector('[class*="name"], [class*="title"], h2, h3, .product-name');
                                    const priceEl = el.querySelector('[class*="price"], .price');
                                    const wasEl = el.querySelector('[class*="was"], .was-price, .original-price, s, del');
                                    const nowEl = el.querySelector('[class*="now"], .now-price, .sale-price, .current-price');
                                    const imgEl = el.querySelector('img');
                                    const linkEl = el.querySelector('a[href*="/george/"]');

                                    results.push({
                                        selector: selector,
                                        name: nameEl ? nameEl.textContent.trim().substring(0, 50) : null,
                                        price: priceEl ? priceEl.textContent.trim() : null,
                                        was: wasEl ? wasEl.textContent.trim() : null,
                                        now: nowEl ? nowEl.textContent.trim() : null,
                                        img: imgEl ? imgEl.src : null,
                                        link: linkEl ? linkEl.href : null,
                                        html: el.innerHTML.substring(0, 300),
                                    });
                                }
                            });
                            break; // Use first matching selector
                        }
                    }
                    return results;
                }
            """)

            if products:
                print(f"   Found {len(products)} product elements!")
                for i, prod in enumerate(products[:5]):
                    print(f"\n   Product {i+1}:")
                    print(f"      Name: {prod.get('name', 'N/A')}")
                    print(f"      Price: {prod.get('price', 'N/A')}")
                    print(f"      Was: {prod.get('was', 'N/A')}")
                    print(f"      Now: {prod.get('now', 'N/A')}")
                    if prod.get('img'):
                        print(f"      Image: {prod['img'][:60]}...")
            else:
                print("   No products found with standard selectors")

                # Last resort: dump some HTML snippets with prices
                print("\n   Searching raw HTML for £ symbols...")
                price_contexts = re.findall(r'.{50}£\d+\.?\d*.{50}', html)
                for ctx in price_contexts[:5]:
                    print(f"      ...{ctx}...")

        except Exception as e:
            print(f"   Error: {e}")

        await browser.close()

    print("\n" + "=" * 60)
    print("Analysis completed!")
    print("=" * 60)


if __name__ == "__main__":
    url = "https://direct.asda.com/george/baby-girl/D5M10G1,default,sc.html?displayAs=George&pmid=grg_tact_2026_wk2_babyevent_clothing"
    asyncio.run(scrape_george_page(url))
