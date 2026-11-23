"""Test direct Algolia API access for ASDA/George."""
import httpx
import json

# ASDA Algolia credentials (found in page source)
ALGOLIA_APP_ID = "1KBYJ8SZ65"
# Public search API key (safe to expose, read-only)
# We need to find this - let's try common patterns

# Algolia search endpoint
base_url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes"

# Common index names for e-commerce
index_names = [
    "products",
    "george_products",
    "asda_products",
    "george_uk_products",
    "prod_products",
    "production_products",
]

print("Testing Algolia API for ASDA/George")
print("=" * 60)
print(f"App ID: {ALGOLIA_APP_ID}")

# Try to find the API key by testing with empty key first
# (some Algolia setups allow public access)

headers = {
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "Content-Type": "application/json",
}

# Try without API key (some allow this)
for index in index_names[:3]:
    url = f"{base_url}/{index}/query"
    try:
        response = httpx.post(
            url,
            headers=headers,
            json={"query": "dress", "hitsPerPage": 1},
            timeout=10
        )
        print(f"\n{index}: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Hits: {data.get('nbHits', 0)}")
        elif response.status_code == 403:
            print("  Needs API key")
    except Exception as e:
        print(f"  Error: {e}")

# The API key is usually embedded in the frontend
# Let's try to construct a search request like the frontend does
print("\n" + "=" * 60)
print("Trying Algolia search with InstantSearch pattern...")

# InstantSearch uses a different endpoint
instant_search_url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/*/queries"

# This is a typical InstantSearch request
search_request = {
    "requests": [
        {
            "indexName": "george_products_price_asc",
            "params": "query=&hitsPerPage=20&page=0"
        }
    ]
}

try:
    response = httpx.post(
        instant_search_url,
        headers=headers,
        json=search_request,
        timeout=10
    )
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

print("\nNote: We need the public API key from the frontend.")
print("This key is safe to use - it only allows search operations.")
