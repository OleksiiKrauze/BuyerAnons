"""Explore all available fields in Algolia products."""
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

# Get ALL attributes from a few products
params = {
    "query": "",
    "hitsPerPage": 5,
    "attributesToRetrieve": ["*"],  # Get ALL fields
}

print("Fetching products with ALL fields...")
print("=" * 60)

response = httpx.post(url, headers=headers, json=params, timeout=30)
data = response.json()

print(f"Total products: {data.get('nbHits', 0)}")
print(f"Retrieved: {len(data.get('hits', []))}")

# Print all fields from first product
if data.get('hits'):
    print("\n" + "=" * 60)
    print("ALL FIELDS IN FIRST PRODUCT:")
    print("=" * 60)

    first = data['hits'][0]
    for key, value in sorted(first.items()):
        # Truncate long values
        str_val = str(value)
        if len(str_val) > 100:
            str_val = str_val[:100] + "..."
        print(f"  {key}: {str_val}")

    # Look specifically for price-related fields
    print("\n" + "=" * 60)
    print("PRICE-RELATED FIELDS:")
    print("=" * 60)

    price_keywords = ['price', 'cost', 'sale', 'discount', 'was', 'original', 'rrp', 'promo']
    for key, value in first.items():
        if any(kw in key.lower() for kw in price_keywords):
            print(f"  {key}: {value}")

    # Check all 5 products for any with was_price
    print("\n" + "=" * 60)
    print("CHECKING ALL 5 PRODUCTS FOR PRICES:")
    print("=" * 60)

    for i, hit in enumerate(data['hits'], 1):
        name = hit.get('name', 'Unknown')[:40]
        current = hit.get('current_price', 'N/A')
        was = hit.get('was_price', 'N/A')
        print(f"{i}. {name}")
        print(f"   current_price: {current}, was_price: {was}")

        # Check for any other price fields
        other_prices = {k: v for k, v in hit.items() if 'price' in k.lower() and k not in ['current_price', 'was_price']}
        if other_prices:
            print(f"   Other price fields: {other_prices}")
