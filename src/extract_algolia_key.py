"""Extract Algolia API key from George main page."""
import asyncio
import re
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        await stealth_async(page)

        print("Loading George main page...")
        await page.goto('https://direct.asda.com/george/', wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(5)

        html = await page.content()
        print(f"Page size: {len(html)} bytes")

        # Search for Algolia patterns
        patterns = [
            (r'"algoliaAppId"\s*:\s*"([^"]+)"', 'algoliaAppId'),
            (r'"algoliaApiKey"\s*:\s*"([^"]+)"', 'algoliaApiKey'),
            (r'"algoliaIndex"\s*:\s*"([^"]+)"', 'algoliaIndex'),
            (r"algoliaAppId\s*[=:]\s*['\"]([^'\"]+)['\"]", 'algoliaAppId alt'),
            (r"algoliaApiKey\s*[=:]\s*['\"]([^'\"]+)['\"]", 'algoliaApiKey alt'),
            (r"'apiKey'\s*:\s*'([a-f0-9]{32})'", 'apiKey'),
            (r'"apiKey"\s*:\s*"([a-f0-9]{32})"', 'apiKey'),
            (r"applicationId['\"]?\s*[=:]\s*['\"]([A-Z0-9]{10})['\"]", 'applicationId'),
            (r"searchApiKey['\"]?\s*[=:]\s*['\"]([a-f0-9]{32})['\"]", 'searchApiKey'),
            (r"x-algolia-api-key['\"]?\s*[=:]\s*['\"]([a-f0-9]{32})['\"]", 'x-algolia-api-key'),
        ]

        print("\n" + "=" * 60)
        print("Searching for Algolia credentials...")
        print("=" * 60)

        found = {}
        for pattern, name in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                found[name] = matches[0] if len(matches) == 1 else matches
                print(f"  {name}: {matches[0][:50]}...")

        # Also look for configuration objects
        config_pattern = r'"algolia"\s*:\s*\{[^}]+\}'
        config_matches = re.findall(config_pattern, html)
        if config_matches:
            print(f"\nAlgolia config objects found: {len(config_matches)}")
            for config in config_matches[:2]:
                print(f"  {config[:200]}")

        # Search in script tags specifically
        print("\n" + "=" * 60)
        print("Searching script tags...")
        print("=" * 60)

        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
        for i, script in enumerate(scripts):
            if 'algolia' in script.lower():
                # Extract relevant part
                lines = [l for l in script.split('\n') if 'algolia' in l.lower()]
                if lines:
                    print(f"\nScript {i}:")
                    for line in lines[:5]:
                        print(f"  {line.strip()[:100]}")

        # Save for manual inspection
        with open('/tmp/george_main.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("\nSaved to /tmp/george_main.html")

        await browser.close()

        return found


asyncio.run(main())
