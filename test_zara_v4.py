"""Test Zara API v4 - Deep dive into Search API."""
import asyncio
import httpx
import json


async def explore_search_api():
    print("=" * 60)
    print("Zara Search API - Deep Analysis")
    print("=" * 60)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Test search API
        search_url = "https://www.zara.com/uk/en/search?searchTerm=sale&ajax=true"
        print(f"\n1. Fetching: {search_url}")

        resp = await client.get(search_url, headers=headers)
        print(f"   Status: {resp.status_code}")

        data = resp.json()

        # Explore structure
        print("\n2. Top-level keys:")
        for key in data.keys():
            val = data[key]
            val_type = type(val).__name__
            if isinstance(val, (list, dict)):
                size = len(val)
                print(f"   {key}: {val_type} ({size} items)")
            else:
                print(f"   {key}: {val_type} = {str(val)[:50]}")

        # Explore categories
        if 'categories' in data:
            print("\n3. Categories structure:")
            cats = data['categories']
            if isinstance(cats, list):
                print(f"   {len(cats)} categories")
                for i, cat in enumerate(cats[:3]):
                    if isinstance(cat, dict):
                        print(f"\n   Category {i+1}:")
                        print(f"      Keys: {list(cat.keys())[:10]}")
                        if 'name' in cat:
                            print(f"      Name: {cat['name']}")
                        if 'productGroups' in cat:
                            groups = cat['productGroups']
                            print(f"      productGroups: {len(groups)} groups")
                            if groups:
                                g = groups[0]
                                print(f"         Group keys: {list(g.keys())[:10]}")
                                if 'elements' in g:
                                    elements = g['elements']
                                    print(f"         elements: {len(elements)} items")
                                    if elements:
                                        elem = elements[0]
                                        print(f"            Element keys: {list(elem.keys())[:15]}")

        # Try to find actual products
        print("\n4. Searching for products in data...")

        def find_products(obj, path="", depth=0):
            if depth > 10:
                return []

            results = []

            if isinstance(obj, dict):
                # Check if this looks like a product
                if 'price' in obj or 'currentPrice' in obj or 'displayPrice' in obj:
                    results.append((path, obj))

                for k, v in obj.items():
                    results.extend(find_products(v, f"{path}.{k}", depth+1))

            elif isinstance(obj, list):
                for i, item in enumerate(obj[:5]):  # Check first 5 items
                    results.extend(find_products(item, f"{path}[{i}]", depth+1))

            return results

        products = find_products(data)
        print(f"   Found {len(products)} potential products")

        if products:
            print("\n5. Sample products:")
            for i, (path, prod) in enumerate(products[:5]):
                print(f"\n   Product {i+1} at {path}:")
                # Extract common fields
                name = prod.get('name', prod.get('displayName', prod.get('productName', 'N/A')))
                price = prod.get('price', prod.get('currentPrice', prod.get('displayPrice', 'N/A')))
                old_price = prod.get('oldPrice', prod.get('originalPrice', prod.get('crossedOutPrice', 'N/A')))
                print(f"      Name: {name}")
                print(f"      Price: {price}")
                print(f"      Old Price: {old_price}")
                print(f"      Keys: {list(prod.keys())[:10]}")

        # Save full response for analysis
        with open("/app/output/zara_search_response.json", "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n6. Full response saved to output/zara_search_response.json")

        # Now try a category-specific request
        print("\n" + "=" * 60)
        print("Testing category API...")
        print("=" * 60)

        # Try to get women's sale category
        # Common Zara category IDs for sales
        category_urls = [
            "https://www.zara.com/uk/en/categories?categoryId=1030040506&ajax=true",
            "https://www.zara.com/uk/en/category/1030040506/products?ajax=true",
            "https://www.zara.com/uk/en/woman-sale-l1314.html?ajax=true",
        ]

        for url in category_urls:
            print(f"\n   Testing: {url[:60]}...")
            try:
                resp = await client.get(url, headers=headers)
                print(f"   Status: {resp.status_code}")
                if resp.status_code == 200:
                    try:
                        cat_data = resp.json()
                        print(f"   Keys: {list(cat_data.keys())[:10]}")

                        # Look for products
                        if 'productGroups' in cat_data:
                            print(f"   Found productGroups!")
                    except:
                        print(f"   Not JSON, length: {len(resp.text)}")
            except Exception as e:
                print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(explore_search_api())
