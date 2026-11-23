"""Test Zara API v2 - deeper exploration."""
import asyncio
import httpx
import json
import re


async def explore_zara():
    print("=" * 60)
    print("Exploring Zara API v2")
    print("=" * 60)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Step 1: Load main page to get cookies and find API info
        print("\n1. Loading Zara UK sale page...")
        try:
            resp = await client.get("https://www.zara.com/uk/en/woman-sale-l1314.html", headers=headers)
            print(f"   Status: {resp.status_code}")
            print(f"   URL: {resp.url}")
            html = resp.text

            # Look for API URLs in the HTML
            print("\n2. Searching for API patterns in HTML...")

            # Find any JSON data embedded in the page
            patterns = {
                "window.__PRELOADED_STATE__": r'window\.__PRELOADED_STATE__\s*=\s*({.+?});?\s*</script>',
                "productIds": r'"productIds"\s*:\s*\[([^\]]+)\]',
                "categoryId": r'"categoryId"\s*:\s*"?(\d+)"?',
                "storeId": r'"storeId"\s*:\s*"?(\d+)"?',
                "apiUrl": r'"apiUrl"\s*:\s*"([^"]+)"',
            }

            for name, pattern in patterns.items():
                matches = re.findall(pattern, html, re.DOTALL)
                if matches:
                    print(f"   Found {name}: {str(matches[0])[:100]}...")

            # Look for specific Zara API structure
            print("\n3. Looking for embedded product data...")

            # Zara often embeds initial product data
            preload_match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.+?});?\s*</script>', html, re.DOTALL)
            if preload_match:
                try:
                    data = json.loads(preload_match.group(1))
                    print(f"   Found __PRELOADED_STATE__ with keys: {list(data.keys())[:10]}")

                    # Look for products
                    if 'products' in data:
                        products = data['products']
                        print(f"   Found {len(products)} products!")
                    if 'productGroups' in data:
                        print(f"   Found productGroups!")

                    # Recursive search for products
                    def find_products(obj, path=""):
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if 'product' in k.lower():
                                    print(f"   Found '{k}' at {path}")
                                find_products(v, f"{path}.{k}")
                        elif isinstance(obj, list) and len(obj) > 0:
                            find_products(obj[0], f"{path}[0]")

                    find_products(data)
                except json.JSONDecodeError as e:
                    print(f"   JSON parse error: {e}")

            # Save HTML for analysis
            with open("/app/output/zara_sale.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"\n   Saved HTML: {len(html)} bytes")

        except Exception as e:
            print(f"   Error: {e}")

        # Step 4: Try newer Zara API format
        print("\n4. Testing newer Zara API formats...")

        # Zara's current API uses different patterns
        api_tests = [
            # New format with ajax parameter
            ("https://www.zara.com/uk/en/category/1030040506/products?ajax=true", "Category products"),
            # Try with v2/v3 endpoints
            ("https://www.zara.com/api/products/1030040506", "API products"),
            # Search endpoint
            ("https://www.zara.com/uk/en/search?searchTerm=dress&ajax=true", "Search ajax"),
        ]

        for url, desc in api_tests:
            try:
                resp = await client.get(url, headers={
                    **headers,
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                })
                print(f"\n   {desc}: {resp.status_code}")
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    print(f"   Content-Type: {content_type}")
                    if "json" in content_type:
                        data = resp.json()
                        print(f"   JSON keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
            except Exception as e:
                print(f"   {desc}: Error - {str(e)[:50]}")

        # Step 5: Try to find products in the HTML directly
        print("\n5. Parsing products from HTML...")

        # Look for product cards
        product_patterns = [
            r'data-productid="(\d+)"',
            r'"id"\s*:\s*(\d{8})',  # Zara product IDs are usually 8 digits
            r'product/(\d+)',
        ]

        for pattern in product_patterns:
            matches = list(set(re.findall(pattern, html)))
            if matches:
                print(f"   Pattern '{pattern[:30]}...': {len(matches)} matches")
                print(f"   Sample: {matches[:5]}")

        # Look for price data
        print("\n6. Looking for prices...")
        price_patterns = [
            r'"price"\s*:\s*(\d+\.?\d*)',
            r'"currentPrice"\s*:\s*(\d+\.?\d*)',
            r'"originalPrice"\s*:\s*(\d+\.?\d*)',
            r'£(\d+\.\d{2})',
            r'"formattedValue"\s*:\s*"([^"]*£[^"]*)"',
        ]

        for pattern in price_patterns:
            matches = re.findall(pattern, html)
            if matches:
                unique = list(set(matches))[:10]
                print(f"   Pattern found: {unique}")

    print("\n" + "=" * 60)
    print("Exploration completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(explore_zara())
