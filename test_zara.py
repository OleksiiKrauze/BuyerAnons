"""Test Zara API exploration."""
import asyncio
import httpx
import json
import re

# Zara uses an internal API. Let's try to find it.
BASE_URL = "https://www.zara.com"


async def explore_zara():
    print("=" * 60)
    print("Exploring Zara API")
    print("=" * 60)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Test 1: Check Zara UK sale page
        print("\n1. Checking Zara UK...")
        try:
            resp = await client.get(f"{BASE_URL}/uk/", headers=headers)
            print(f"   Status: {resp.status_code}")
            print(f"   URL: {resp.url}")
        except Exception as e:
            print(f"   Error: {e}")

        # Test 2: Try Zara's known API endpoints
        print("\n2. Testing Zara API endpoints...")

        # Zara uses these API patterns
        api_endpoints = [
            # Product catalog API
            "/uk/en/categories/1030040506/products",  # Women's sale
            "/uk/en/category/1030040506/products",
            # Search API
            "/uk/en/search/products",
        ]

        for endpoint in api_endpoints:
            try:
                url = f"{BASE_URL}{endpoint}"
                resp = await client.get(url, headers={
                    **headers,
                    "Accept": "application/json",
                })
                print(f"   {endpoint}: {resp.status_code}")
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        print(f"      JSON response: {str(data)[:200]}...")
                    except:
                        print(f"      Response: {resp.text[:200]}...")
            except Exception as e:
                print(f"   {endpoint}: Error - {e}")

        # Test 3: Try the actual product API that Zara uses
        print("\n3. Testing Zara product API (v2)...")

        # Zara's actual API format
        zara_api_urls = [
            "https://www.zara.com/uk/en/category/1030040506/products?ajax=true",
            "https://www.zara.com/uk/en/woman-sale-l1314.html?ajax=true",
            "https://www.zara.com/itxrest/2/catalog/store/11719/category/1030040506/product?languageId=-1",
        ]

        for url in zara_api_urls:
            try:
                resp = await client.get(url, headers={
                    **headers,
                    "Accept": "application/json, text/javascript, */*",
                    "X-Requested-With": "XMLHttpRequest",
                })
                print(f"\n   URL: {url[:60]}...")
                print(f"   Status: {resp.status_code}")
                if resp.status_code == 200:
                    content = resp.text[:500]
                    print(f"   Content: {content}...")

                    # Try to parse as JSON
                    try:
                        data = resp.json()
                        if isinstance(data, dict):
                            print(f"   Keys: {list(data.keys())[:10]}")
                        elif isinstance(data, list):
                            print(f"   List with {len(data)} items")
                    except:
                        pass
            except Exception as e:
                print(f"   Error: {e}")

        # Test 4: Try ITX REST API (Inditex group API)
        print("\n4. Testing ITX REST API...")

        # Zara store IDs: UK = 11719
        itx_urls = [
            "https://www.zara.com/itxrest/2/catalog/store/11719/category?languageId=-1",
            "https://www.zara.com/itxrest/3/catalog/store/11719/category/1030040506/product?languageId=-1&ajax=true",
        ]

        for url in itx_urls:
            try:
                resp = await client.get(url, headers={
                    **headers,
                    "Accept": "application/json",
                })
                print(f"\n   {url.split('itxrest')[1][:50]}...")
                print(f"   Status: {resp.status_code}")
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        print(f"   Response type: {type(data).__name__}")
                        if isinstance(data, dict):
                            print(f"   Keys: {list(data.keys())[:5]}")
                            # Look for products
                            if 'productGroups' in data:
                                print(f"   Found productGroups!")
                            if 'products' in data:
                                prods = data['products']
                                print(f"   Found {len(prods)} products!")
                                if prods:
                                    p = prods[0]
                                    print(f"   Sample: {p.get('name', 'N/A')}")
                    except json.JSONDecodeError:
                        print(f"   Not JSON: {resp.text[:100]}...")
            except Exception as e:
                print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Exploration completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(explore_zara())
