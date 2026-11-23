"""Simple test for ASDA Algolia API - standalone, no dependencies."""
import asyncio
import httpx

ALGOLIA_APP_ID = "1KBYJ8SZ65"
ALGOLIA_API_KEY = "fea321f42e897ee5331d030d1ca9c464"
ALGOLIA_INDEX = "asda_prod__products__default"


async def test_algolia():
    print("=" * 60)
    print("Testing ASDA/George Algolia API")
    print("=" * 60)

    url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"

    headers = {
        "X-Algolia-Application-Id": ALGOLIA_APP_ID,
        "X-Algolia-API-Key": ALGOLIA_API_KEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        # Test 1: Women's Dresses
        print("\n1. Women's Dresses:")
        resp = await client.post(url, headers=headers, json={
            "query": "",
            "hitsPerPage": 5,
            "facetFilters": [["gender:Womens"], ["product_type:Dresses"]],
            "attributesToRetrieve": ["name", "current_price", "primary_image", "bucket_size", "url"],
        })
        data = resp.json()
        print(f"   Total found: {data.get('nbHits', 0)}")

        for hit in data.get("hits", []):
            name = hit.get("name", "")[:45]
            price = hit.get("current_price", 0)
            sizes = hit.get("bucket_size", [])[:5]
            img_id = hit.get("primary_image", "")
            img_url = f"https://asda.scene7.com/is/image/Asda/{img_id}" if img_id else ""

            print(f"   - {name}")
            print(f"     Price: £{price} | Sizes: {sizes}")
            print(f"     Image: {img_url}")

        # Test 2: Men's Footwear
        print("\n2. Men's Footwear:")
        resp = await client.post(url, headers=headers, json={
            "query": "",
            "hitsPerPage": 3,
            "facetFilters": [["gender:Mens"], ["product_type:Footwear"]],
            "attributesToRetrieve": ["name", "current_price", "bucket_size"],
        })
        data = resp.json()
        print(f"   Total found: {data.get('nbHits', 0)}")

        for hit in data.get("hits", []):
            print(f"   - {hit.get('name', '')[:50]}: £{hit.get('current_price', 0)}")
            print(f"     Sizes: {hit.get('bucket_size', [])}")

        # Test 3: Size filter simulation
        print("\n3. Testing size filter (looking for size 10, 12):")
        resp = await client.post(url, headers=headers, json={
            "query": "",
            "hitsPerPage": 20,
            "facetFilters": [["gender:Womens"], ["product_type:Dresses"]],
            "attributesToRetrieve": ["name", "current_price", "bucket_size"],
        })
        data = resp.json()

        filtered = []
        for hit in data.get("hits", []):
            sizes = hit.get("bucket_size", [])
            if "10" in sizes or "12" in sizes:
                filtered.append(hit)

        print(f"   Products with size 10 or 12: {len(filtered)} out of {len(data.get('hits', []))}")
        for hit in filtered[:3]:
            print(f"   - {hit.get('name', '')[:40]}: £{hit.get('current_price', 0)}")

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_algolia())
