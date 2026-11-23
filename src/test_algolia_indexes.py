"""Try different Algolia indexes and filters."""
import httpx

ALGOLIA_APP_ID = "1KBYJ8SZ65"
ALGOLIA_API_KEY = "fea321f42e897ee5331d030d1ca9c464"

base_url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes"

headers = {
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
}

# Try different index names
indexes = [
    "asda_prod__products__default",
    "asda_prod__products__price_asc",
    "asda_prod__products__price_desc",
    "asda_prod__products__newest",
    "asda_prod__sale",
    "george_products",
    "george_sale",
    "asda_sale",
]

print("Testing different Algolia indexes...")
print("=" * 60)

for index in indexes:
    url = f"{base_url}/{index}/query"
    try:
        response = httpx.post(url, headers=headers, json={"query": "", "hitsPerPage": 1}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ {index}: {data.get('nbHits', 0)} products")
        else:
            print(f"✗ {index}: {response.status_code}")
    except Exception as e:
        print(f"✗ {index}: Error - {e}")

# Try filters on main index
print("\n" + "=" * 60)
print("Testing filters on main index...")
print("=" * 60)

index = "asda_prod__products__default"
url = f"{base_url}/{index}/query"

filters_to_try = [
    "was_price > 0",
    "on_sale:true",
    "sale:true",
    "is_sale:true",
    "has_discount:true",
    "discount > 0",
]

for f in filters_to_try:
    try:
        response = httpx.post(url, headers=headers, json={"query": "", "hitsPerPage": 1, "filters": f}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            hits = data.get('nbHits', 0)
            if hits > 0:
                print(f"✓ Filter '{f}': {hits} products")
            else:
                print(f"  Filter '{f}': 0 products")
        else:
            error = response.json().get('message', '')[:50]
            print(f"✗ Filter '{f}': {error}")
    except Exception as e:
        print(f"✗ Filter '{f}': {e}")

# Check facets to understand filtering options
print("\n" + "=" * 60)
print("Checking available facets...")
print("=" * 60)

response = httpx.post(url, headers=headers, json={
    "query": "",
    "hitsPerPage": 0,
    "facets": ["*"],  # Get all facets
}, timeout=10)

if response.status_code == 200:
    data = response.json()
    facets = data.get('facets', {})
    for facet_name, values in list(facets.items())[:15]:
        sample_values = list(values.keys())[:3]
        print(f"  {facet_name}: {sample_values}")
