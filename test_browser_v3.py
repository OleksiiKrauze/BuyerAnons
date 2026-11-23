"""Test browser scraping v3 - with screenshot and deeper wait."""
import asyncio
import re
import os
from playwright.async_api import async_playwright

# Ensure output directory exists
os.makedirs("/app/output", exist_ok=True)


async def scrape_george_page(url: str):
    print("=" * 60)
    print("Browser Scraping v3 - Debug Mode")
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
        print("   DOM loaded, waiting for content...")
        await asyncio.sleep(8)  # Wait for JS to render

        # Handle cookie consent
        try:
            accept_btn = page.locator('#onetrust-accept-btn-handler').first
            if await accept_btn.is_visible(timeout=5000):
                await accept_btn.click()
                print("   Clicked cookie consent")
                await asyncio.sleep(2)
        except:
            print("   No cookie popup found")

        # Wait more and scroll
        await asyncio.sleep(3)
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(0.5)

        # Take screenshot
        await page.screenshot(path="/app/output/screenshot.png", full_page=False)
        print("   Screenshot saved to output/screenshot.png")

        # Get page title and URL
        title = await page.title()
        print(f"\n2. Page info:")
        print(f"   Title: {title}")
        print(f"   URL: {page.url[:80]}...")

        # Check for any visible text content
        print("\n3. Checking page content...")
        body_text = await page.locator("body").text_content()
        body_text_clean = ' '.join(body_text.split())[:500]
        print(f"   Body text preview: {body_text_clean}...")

        # Count various elements
        print("\n4. Element counts:")
        elements_to_check = [
            ("div", "div"),
            ("article", "article"),
            ("img", "img"),
            ("a[href*='george']", "links with 'george'"),
            ("*[class*='product']", "elements with 'product' in class"),
            ("*[class*='tile']", "elements with 'tile' in class"),
            ("*[class*='card']", "elements with 'card' in class"),
            ("*[class*='item']", "elements with 'item' in class"),
            ("*[class*='price']", "elements with 'price' in class"),
        ]

        for selector, desc in elements_to_check:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    print(f"   {desc}: {count}")
            except:
                pass

        # Get all classes that contain 'product'
        print("\n5. Classes containing 'product':")
        try:
            classes = await page.evaluate("""
                () => {
                    const allElements = document.querySelectorAll('*');
                    const productClasses = new Set();
                    allElements.forEach(el => {
                        if (el.className && typeof el.className === 'string') {
                            el.className.split(' ').forEach(cls => {
                                if (cls.toLowerCase().includes('product') ||
                                    cls.toLowerCase().includes('tile') ||
                                    cls.toLowerCase().includes('plp')) {
                                    productClasses.add(cls);
                                }
                            });
                        }
                    });
                    return Array.from(productClasses).slice(0, 20);
                }
            """)
            if classes:
                for cls in classes:
                    print(f"   .{cls}")
            else:
                print("   No matching classes found")
        except Exception as e:
            print(f"   Error: {e}")

        # Look at HTML for specific George structure
        print("\n6. Searching HTML for George-specific patterns...")
        html = await page.content()

        # Save full HTML
        with open("/app/output/page_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"   Saved {len(html)} bytes to output/page_debug.html")

        # Search for common patterns
        patterns = {
            'GEM product IDs': r'GEM\d{6,}',
            'Product URLs': r'/george/[^"\'>\s]+/\d+,default,pd\.html',
            'Image URLs': r'asda\.scene7\.com/is/image/Asda/\d+',
            'Price £': r'>\s*£\d+\.?\d*\s*<',
            'data-product': r'data-product[^=]*="[^"]+"',
        }

        for name, pattern in patterns.items():
            matches = re.findall(pattern, html)
            if matches:
                unique = list(set(matches))[:5]
                print(f"   {name}: {len(matches)} found")
                for m in unique[:3]:
                    print(f"      {m[:60]}")

        # Check if page has React/Vue root
        print("\n7. Checking for JS frameworks...")
        try:
            framework = await page.evaluate("""
                () => {
                    if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) return 'React detected';
                    if (window.Vue) return 'Vue detected';
                    if (window.angular) return 'Angular detected';
                    if (document.querySelector('[data-reactroot]')) return 'React root found';
                    if (document.querySelector('[ng-app]')) return 'Angular app found';
                    return 'No framework detected';
                }
            """)
            print(f"   {framework}")
        except:
            pass

        # Check for lazy loading or infinite scroll
        print("\n8. Checking for dynamic loading...")
        try:
            has_lazy = await page.evaluate("""
                () => {
                    const lazyImages = document.querySelectorAll('img[loading="lazy"], img[data-src]');
                    const infiniteScroll = document.querySelector('[data-infinite-scroll], .infinite-scroll');
                    return {
                        lazyImages: lazyImages.length,
                        infiniteScroll: !!infiniteScroll
                    };
                }
            """)
            print(f"   Lazy images: {has_lazy['lazyImages']}")
            print(f"   Infinite scroll: {has_lazy['infiniteScroll']}")
        except:
            pass

        await browser.close()

    print("\n" + "=" * 60)
    print("Debug completed! Check screenshot.png and page_debug.html")
    print("=" * 60)


if __name__ == "__main__":
    url = "https://direct.asda.com/george/baby-girl/D5M10G1,default,sc.html"
    asyncio.run(scrape_george_page(url))
