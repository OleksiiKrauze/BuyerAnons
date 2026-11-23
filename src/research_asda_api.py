"""
Research ASDA/George Algolia API.
Run: docker exec buyer-anons-dev python /app/src/research_asda_api.py
"""
import asyncio
import json
import re
from playwright.async_api import async_playwright


async def main():
    api_calls = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Intercept all network requests
        async def handle_request(request):
            url = request.url.lower()
            if 'algolia' in url or 'search' in url:
                print(f"\n[REQUEST] {request.method} {request.url[:100]}")
                if request.post_data:
                    print(f"  Body: {request.post_data[:200]}")

        async def handle_response(response):
            url = response.url.lower()
            if 'algolia' in url:
                print(f"\n[RESPONSE] {response.status} {response.url[:100]}")
                try:
                    data = await response.json()
                    api_calls.append({
                        'url': response.url,
                        'data': data
                    })
                    if 'results' in data:
                        for i, result in enumerate(data['results']):
                            if 'hits' in result:
                                print(f"  Result {i}: {len(result['hits'])} hits")
                                if result['hits']:
                                    print(f"  Sample keys: {list(result['hits'][0].keys())[:10]}")
                except:
                    pass

        page.on('request', handle_request)
        page.on('response', handle_response)

        print("Loading George sale page...")
        print("=" * 60)

        try:
            await page.goto(
                'https://direct.asda.com/george/women/dresses/dept/D30M01,default,sc.html',
                wait_until='networkidle',
                timeout=60000
            )
        except Exception as e:
            print(f"Page load error (expected): {e}")

        print("\n" + "=" * 60)
        print(f"Captured {len(api_calls)} Algolia API calls")

        if api_calls:
            # Save first API call for analysis
            with open('/tmp/algolia_api.json', 'w') as f:
                json.dump(api_calls[0], f, indent=2)
            print("Saved to /tmp/algolia_api.json")

            # Extract Algolia credentials from URL
            for call in api_calls:
                url = call['url']
                if 'x-algolia-api-key' in url.lower() or 'algolia' in url:
                    print(f"\nAlgolia URL: {url}")
                    # Parse query params
                    if '?' in url:
                        params = url.split('?')[1]
                        for param in params.split('&'):
                            if 'key' in param.lower() or 'app' in param.lower():
                                print(f"  {param}")

        await browser.close()


asyncio.run(main())
