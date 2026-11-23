"""Find Algolia credentials in ASDA page."""
import httpx
import re

url = 'https://direct.asda.com/george/women/dresses/dept/D30M01,default,sc.html'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.9',
}

print(f"Fetching {url}...")
response = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
print(f"Status: {response.status_code}")
print(f"Size: {len(response.text)} bytes")

html = response.text

# Search for Algolia patterns
patterns = [
    (r'algoliaAppId["\s:]+(["\'])([^"\']+)\1', 'App ID'),
    (r'algoliaApiKey["\s:]+(["\'])([^"\']+)\1', 'API Key'),
    (r'algoliaIndex["\s:]+(["\'])([^"\']+)\1', 'Index'),
    (r'applicationId["\s:]+(["\'])([^"\']+)\1', 'Application ID'),
    (r'apiKey["\s:]+(["\'])([a-f0-9]{32})\1', 'API Key (hex)'),
    (r'["\']([A-Z0-9]{10})["\'].*algolia', 'Possible App ID'),
    (r'1KBYJ8SZ65', 'Known ASDA App ID'),  # from earlier debug
]

print("\nSearching for Algolia credentials...")
print("=" * 60)

for pattern, name in patterns:
    matches = re.findall(pattern, html, re.IGNORECASE)
    if matches:
        print(f"{name}: {matches[:3]}")

# Also search for Algolia URLs
algolia_urls = re.findall(r'https?://[^"\s]*algolia[^"\s]*', html, re.IGNORECASE)
if algolia_urls:
    print(f"\nAlgolia URLs found:")
    for url in set(algolia_urls)[:5]:
        print(f"  {url[:100]}")

# Search for search-insights (Algolia tracking)
if 'search-insights' in html:
    print("\nAlgolia Search Insights found in page")

# Save HTML for reference
with open('/tmp/asda_raw.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("\nSaved HTML to /tmp/asda_raw.html")
