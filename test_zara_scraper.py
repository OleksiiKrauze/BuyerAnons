"""Test Zara scraper integration."""
import asyncio
from src.scrapers.zara import ZaraScraper


async def test_zara_scraper():
    print("=" * 60)
    print("Testing Zara Scraper")
    print("=" * 60)

    scraper = ZaraScraper()

    try:
        # Test 1: Women's new arrivals
        print("\n1. Women's new arrivals (top 5):")
        print("-" * 40)
        products = await scraper.scrape("woman-new", top_count=5)
        print(f"   Found {len(products)} products")
        for i, p in enumerate(products, 1):
            print(f"\n   {i}. {p.name}")
            print(f"      Price: £{p.sale_price:.2f}")
            if p.discount_percent > 0:
                print(f"      Original: £{p.original_price:.2f} (-{p.discount_percent}%)")
            print(f"      Sizes: {', '.join(p.available_sizes[:5]) if p.available_sizes else 'N/A'}")
            print(f"      URL: {p.product_url[:60]}...")

        # Test 2: Direct URL
        print("\n" + "=" * 60)
        print("2. Direct URL test (woman best sellers):")
        print("-" * 40)
        products = await scraper.scrape(
            "https://www.zara.com/uk/en/woman-best-sellers-l1299.html",
            top_count=3
        )
        print(f"   Found {len(products)} products")
        for i, p in enumerate(products, 1):
            print(f"\n   {i}. {p.name}")
            print(f"      Price: £{p.sale_price:.2f}")

        # Test 3: Search
        print("\n" + "=" * 60)
        print("3. Search test (dress):")
        print("-" * 40)
        products = await scraper.search("dress", limit=5)
        print(f"   Found {len(products)} products")
        for i, p in enumerate(products[:3], 1):
            print(f"\n   {i}. {p.name}")
            print(f"      Price: £{p.sale_price:.2f}")
            print(f"      Category: {p.category}")

        # Test 4: Size filtering
        print("\n" + "=" * 60)
        print("4. Size filter test (M, L sizes):")
        print("-" * 40)
        products = await scraper.scrape(
            "woman-new",
            sizes=["M", "L"],
            top_count=10
        )
        print(f"   Found {len(products)} products with M or L size")
        for i, p in enumerate(products[:3], 1):
            print(f"\n   {i}. {p.name}")
            print(f"      Sizes: {', '.join(p.available_sizes)}")

        # Test 5: Viber message format
        print("\n" + "=" * 60)
        print("5. Viber message format:")
        print("-" * 40)
        products = await scraper.scrape("woman-new", top_count=1)
        if products:
            # Set some test data for demo
            p = products[0]
            if not p.available_sizes:
                p.available_sizes = ["S", "M", "L"]
            print(p.to_viber_message())

    finally:
        await scraper.close()

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_zara_scraper())
