"""Test Zara API v5 - Working endpoints."""
import asyncio
import httpx
import json


async def test_zara():
    print("=" * 60)
    print("Zara API - Finding Working Endpoints")
    print("=" * 60)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Test 1: Search for "dress"
        print("\n1. Search for 'dress'...")
        resp = await client.get(
            "https://www.zara.com/uk/en/search?searchTerm=dress&ajax=true",
            headers=headers
        )
        data = resp.json()
        print(f"   Categories: {len(data.get('categories', []))}")

        if data.get('categories'):
            cat = data['categories'][0]
            print(f"   First category: {cat.get('name', 'N/A')}")
            print(f"   Category keys: {list(cat.keys())}")

            if 'productGroups' in cat:
                groups = cat['productGroups']
                print(f"   Product groups: {len(groups)}")
                if groups:
                    g = groups[0]
                    print(f"   Group keys: {list(g.keys())}")

                    if 'elements' in g:
                        elements = g['elements']
                        print(f"   Elements: {len(elements)}")
                        if elements:
                            elem = elements[0]
                            print(f"   Element keys: {list(elem.keys())}")

                            # Try to extract product info
                            if 'commercialComponents' in elem:
                                comps = elem['commercialComponents']
                                print(f"   Commercial components: {len(comps)}")
                                if comps:
                                    comp = comps[0]
                                    print(f"   Component keys: {list(comp.keys())}")

        # Test 2: Get categories list
        print("\n2. Getting categories list...")
        resp = await client.get(
            "https://www.zara.com/uk/en/categories?ajax=true",
            headers=headers
        )
        data = resp.json()

        if 'categories' in data:
            cats = data['categories']
            print(f"   Total categories: {len(cats)}")

            # Find sale categories
            sale_cats = [c for c in cats if 'sale' in str(c).lower()]
            print(f"   Sale-related categories: {len(sale_cats)}")

            # Show first few categories
            for cat in cats[:5]:
                if isinstance(cat, dict):
                    print(f"   - {cat.get('name', cat.get('id', 'N/A'))}")

        # Test 3: Try product list endpoint
        print("\n3. Testing product list endpoint...")

        # Try to get products from a category
        # Zara uses different endpoint formats
        endpoints = [
            "https://www.zara.com/uk/en/category/2292631/products?ajax=true",  # Random category
            "https://www.zara.com/uk/en/woman/new-in-l1180.html?ajax=true",
        ]

        for url in endpoints:
            try:
                print(f"\n   URL: {url[:60]}...")
                resp = await client.get(url, headers=headers)
                print(f"   Status: {resp.status_code}")

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        print(f"   Keys: {list(data.keys())[:10]}")

                        # Look for products in the response
                        products_found = 0
                        def count_products(obj, depth=0):
                            nonlocal products_found
                            if depth > 5:
                                return
                            if isinstance(obj, dict):
                                if 'price' in obj or 'seo' in obj:
                                    products_found += 1
                                for v in obj.values():
                                    count_products(v, depth+1)
                            elif isinstance(obj, list):
                                for item in obj[:10]:
                                    count_products(item, depth+1)

                        count_products(data)
                        print(f"   Potential products: {products_found}")

                    except:
                        print(f"   Not JSON: {resp.text[:100]}...")
            except Exception as e:
                print(f"   Error: {e}")

        # Test 4: Get raw category page and look for API calls
        print("\n4. Checking raw HTML for API endpoints...")

        resp = await client.get(
            "https://www.zara.com/uk/en/woman-sale-l1314.html",
            headers={**headers, "Accept": "text/html"}
        )

        html = resp.text
        print(f"   HTML size: {len(html)} bytes")

        # Look for API URLs in the HTML
        import re
        api_patterns = [
            r'https://www\.zara\.com/[^"\'>\s]*api[^"\'>\s]*',
            r'https://www\.zara\.com/[^"\'>\s]*/products[^"\'>\s]*',
            r'categoryId["\s:=]+(\d+)',
        ]

        for pattern in api_patterns:
            matches = list(set(re.findall(pattern, html)))
            if matches:
                print(f"   Pattern '{pattern[:30]}...': {matches[:3]}")

        # Test 5: Try Inditex API with proper store ID
        print("\n5. Testing Inditex REST API...")

        # UK store ID = 11719, language = -1 (default)
        itx_endpoints = [
            "https://www.zara.com/itxrest/3/catalog/store/11719/category?languageId=-1&ajax=true",
        ]

        for url in itx_endpoints:
            try:
                print(f"\n   {url}")
                resp = await client.get(url, headers={
                    **headers,
                    "x-requested-with": "XMLHttpRequest",
                })
                print(f"   Status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"   Type: {type(data).__name__}")
                    if isinstance(data, dict):
                        print(f"   Keys: {list(data.keys())[:10]}")
                    elif isinstance(data, list):
                        print(f"   Items: {len(data)}")
                        if data:
                            print(f"   First item keys: {list(data[0].keys())[:10] if isinstance(data[0], dict) else 'N/A'}")
            except Exception as e:
                print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_zara())
