"""Test the ASDA scraper."""
import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scrapers.asda_api import AsdaApiScraper


async def main():
    scraper = AsdaApiScraper()

    print("=" * 60)
    print("Testing ASDA Scraper")
    print("=" * 60)

    # Test 1: Basic Algolia search with facetFilters
    print("\n1. Testing Algolia search (Women's Dresses)...")

    products = await scraper._search_algolia(
        facet_filters=[["gender:Womens"], ["product_type:Dresses"]],
        hits_per_page=5,
    )

    print(f"   Found {len(products)} products")
    for p in products[:3]:
        print(f"   - {p.name[:40]}... £{p.sale_price}")
        print(f"     Image: {p.image_url[:60]}...")
        print(f"     Sizes: {p.available_sizes[:5]}")

    # Test 2: Search with sizes filter
    print("\n2. Testing size filter (10, 12 sizes)...")

    products = await scraper._search_algolia(
        facet_filters=[["gender:Womens"]],
        hits_per_page=50,
    )
    filtered = [p for p in products if p.has_size(["10", "12"])]
    print(f"   Found {len(filtered)} products with size 10 or 12")

    # Test 3: Full scrape method
    print("\n3. Testing full scrape method...")

    url = "https://direct.asda.com/george/women/dresses/"
    products = await scraper.scrape(
        url=url,
        sizes=["10", "12"],
        top_count=5,
        min_discount=0,  # No discount filter since Algolia lacks discount data
    )

    print(f"   Got {len(products)} products")
    for i, p in enumerate(products, 1):
        print(f"\n   {i}. {p.name}")
        print(f"      Price: £{p.sale_price}")
        print(f"      Sizes: {p.available_sizes[:5]}...")
        print(f"      Category: {p.category}")
        if p.image_url:
            print(f"      Image: {p.image_url}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
