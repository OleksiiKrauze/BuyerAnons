"""Test Algolia API - find discounted products."""
import httpx
import json

ALGOLIA_APP_ID = "1KBYJ8SZ65"
ALGOLIA_API_KEY = "fea321f42e897ee5331d030d1ca9c464"
ALGOLIA_INDEX = "asda_prod__products__default"

url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"

headers = {
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
}

# Get more products to find discounts
params = {
    "query": "",
    "hitsPerPage": 100,
    "attributesToRetrieve": ["name", "current_price", "was_price", "bucket_size", "url", "primary_image", "product_type", "gender"],
}

print("Searching for discounted products...")
print("=" * 60)

response = httpx.post(url, headers=headers, json=params, timeout=30)
data = response.json()

print(f"Total products in index: {data.get('nbHits', 0)}")
print(f"Retrieved: {len(data.get('hits', []))}")

# Find products with discount
discounted = []
for h in data.get('hits', []):
    was = h.get('was_price')
    current = h.get('current_price')
    if was and current and float(was) > float(current):
        discount = int((1 - float(current)/float(was)) * 100)
        h['_discount'] = discount
        discounted.append(h)

# Sort by discount
discounted.sort(key=lambda x: x['_discount'], reverse=True)

print(f"\nProducts with discount: {len(discounted)}")

if discounted:
    print("\n" + "=" * 60)
    print("TOP 5 DISCOUNTED PRODUCTS:")
    print("=" * 60)

    for i, p in enumerate(discounted[:5], 1):
        print(f"\n{i}. {p.get('name', '')[:50]}")
        print(f"   £{p.get('current_price')} (was £{p.get('was_price')}) -{p['_discount']}%")
        print(f"   Sizes: {p.get('bucket_size', [])}")
        print(f"   Type: {p.get('product_type')} | Gender: {p.get('gender')}")

        # Build image URL
        img_id = p.get('primary_image')
        if img_id:
            img_url = f"https://asda.scene7.com/is/image/Asda/{img_id}"
            print(f"   Image: {img_url}")

        url_path = p.get('url', '')
        if url_path:
            full_url = f"https://direct.asda.com{url_path}" if not url_path.startswith('http') else url_path
            print(f"   URL: {full_url[:70]}...")
else:
    # Maybe need to look at different fields
    print("\nNo discounts found in first 100 products.")
    print("Checking which products have 'was_price' field...")
    with_was = [h for h in data.get('hits', []) if h.get('was_price')]
    print(f"Products with was_price: {len(with_was)}")
