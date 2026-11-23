"""Test Zara API - Extract products from working endpoint."""
import asyncio
import httpx
import json


async def test_zara_products():
    print("=" * 60)
    print("Zara API - Extracting Products")
    print("=" * 60)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Test the working endpoint
        print("\n1. Fetching women's new arrivals...")
        resp = await client.get(
            "https://www.zara.com/uk/en/woman/new-in-l1180.html?ajax=true",
            headers=headers
        )
        print(f"   Status: {resp.status_code}")

        data = resp.json()
        print(f"   Top-level keys: {list(data.keys())}")

        # Explore productGroups
        if 'productGroups' in data:
            groups = data['productGroups']
            print(f"\n2. Product Groups: {len(groups)}")

            for i, group in enumerate(groups[:3]):
                print(f"\n   Group {i+1}:")
                print(f"      Keys: {list(group.keys())}")

                if 'elements' in group:
                    elements = group['elements']
                    print(f"      Elements: {len(elements)}")

                    for j, elem in enumerate(elements[:3]):
                        print(f"\n      Element {j+1}:")
                        print(f"         Keys: {list(elem.keys())[:15]}")

                        if 'commercialComponents' in elem:
                            comps = elem['commercialComponents']
                            print(f"         Commercial Components: {len(comps)}")

                            for k, comp in enumerate(comps[:2]):
                                print(f"\n         Component {k+1}:")
                                print(f"            Keys: {list(comp.keys())[:15]}")

                                # Extract product info
                                name = comp.get('name', 'N/A')
                                price = comp.get('price', 'N/A')
                                seo = comp.get('seo', {})
                                id_ = comp.get('id', 'N/A')

                                print(f"            ID: {id_}")
                                print(f"            Name: {name}")
                                print(f"            Price: {price}")
                                print(f"            SEO: {seo}")

                                # Look for price details
                                if 'detail' in comp:
                                    detail = comp['detail']
                                    print(f"            Detail keys: {list(detail.keys())[:10] if isinstance(detail, dict) else 'N/A'}")

                                    if isinstance(detail, dict) and 'colors' in detail:
                                        colors = detail['colors']
                                        if colors:
                                            color = colors[0]
                                            print(f"            Color keys: {list(color.keys())[:15]}")
                                            if 'price' in color:
                                                print(f"            Color price: {color['price']}")

        # Try to get sale page
        print("\n" + "=" * 60)
        print("3. Testing sale page...")
        print("=" * 60)

        sale_urls = [
            "https://www.zara.com/uk/en/woman-sale-l1314.html?ajax=true",
            "https://www.zara.com/uk/en/woman/woman-best-sellers-l1299.html?ajax=true",
            "https://www.zara.com/uk/en/woman-special-prices-l1410.html?ajax=true",
        ]

        for url in sale_urls:
            try:
                print(f"\n   {url.split('/')[-1]}")
                resp = await client.get(url, headers=headers)
                print(f"   Status: {resp.status_code}")

                if resp.status_code == 200:
                    data = resp.json()
                    print(f"   Keys: {list(data.keys())[:10]}")

                    if 'productGroups' in data:
                        groups = data['productGroups']
                        total_products = 0
                        for g in groups:
                            if 'elements' in g:
                                for e in g['elements']:
                                    if 'commercialComponents' in e:
                                        total_products += len(e['commercialComponents'])
                        print(f"   Total products: {total_products}")

                        # Extract first product with price
                        if groups and 'elements' in groups[0]:
                            for elem in groups[0]['elements']:
                                if 'commercialComponents' in elem:
                                    for comp in elem['commercialComponents']:
                                        name = comp.get('name', 'N/A')

                                        # Find price info
                                        price_info = None
                                        if 'detail' in comp and 'colors' in comp['detail']:
                                            colors = comp['detail']['colors']
                                            if colors and 'price' in colors[0]:
                                                price_info = colors[0]['price']

                                        if price_info:
                                            print(f"\n   Sample product: {name}")
                                            print(f"   Price: {price_info}")
                                            break
                                    break

                elif resp.status_code == 278:
                    print("   Redirect (278) - need to follow")

            except Exception as e:
                print(f"   Error: {e}")

        # Save a sample response
        print("\n" + "=" * 60)
        print("4. Saving sample data...")
        print("=" * 60)

        resp = await client.get(
            "https://www.zara.com/uk/en/woman/new-in-l1180.html?ajax=true",
            headers=headers
        )
        data = resp.json()

        with open("/app/output/zara_products.json", "w") as f:
            json.dump(data, f, indent=2)
        print("   Saved to output/zara_products.json")

        # Extract and display products
        print("\n" + "=" * 60)
        print("5. Products with prices:")
        print("=" * 60)

        products_found = []
        if 'productGroups' in data:
            for group in data['productGroups']:
                if 'elements' in group:
                    for elem in group['elements']:
                        if 'commercialComponents' in elem:
                            for comp in elem['commercialComponents']:
                                name = comp.get('name', '')
                                id_ = comp.get('id', '')

                                # Get price from detail.colors
                                price_str = 'N/A'
                                old_price_str = 'N/A'
                                if 'detail' in comp and 'colors' in comp.get('detail', {}):
                                    colors = comp['detail']['colors']
                                    if colors and 'price' in colors[0]:
                                        price_obj = colors[0]['price']
                                        price_str = price_obj if isinstance(price_obj, str) else str(price_obj)

                                        # Check for old price
                                        if isinstance(price_obj, dict):
                                            price_str = price_obj.get('current', price_obj.get('formatted', 'N/A'))
                                            old_price_str = price_obj.get('original', price_obj.get('crossedOut', 'N/A'))

                                products_found.append({
                                    'id': id_,
                                    'name': name,
                                    'price': price_str,
                                    'old_price': old_price_str,
                                })

        print(f"\n   Found {len(products_found)} products")
        for i, p in enumerate(products_found[:10]):
            print(f"\n   {i+1}. {p['name']}")
            print(f"      ID: {p['id']}")
            print(f"      Price: {p['price']}")
            if p['old_price'] != 'N/A':
                print(f"      Old Price: {p['old_price']}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_zara_products())
