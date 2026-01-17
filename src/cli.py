"""
CLI для тестирования сканирования без Viber.

Запуск:
    python -m src.cli https://direct.asda.com/george/men/sale/ --sizes M,L --top 5
"""
import asyncio
import argparse
from loguru import logger

from .scrapers.browser import browser_manager
from .services.translator import translator
from .services.link_shortener import link_shortener
from .utils import get_scraper, detect_store


async def scan(url: str, sizes: list[str], top: int, min_discount: int) -> None:
    """Выполнить сканирование."""
    store = detect_store(url)
    if not store:
        logger.error(f"Unsupported store: {url}")
        return

    scraper = get_scraper(url)
    if not scraper:
        logger.error(f"No scraper for: {url}")
        return

    logger.info(f"Scanning {store}: {url}")
    logger.info(f"Filters: sizes={sizes}, top={top}, min_discount={min_discount}%")

    # Запускаем браузер
    await browser_manager.start()

    try:
        # Сканируем
        products = await scraper.scrape(
            url=url,
            sizes=sizes if sizes else None,
            top_count=top,
            min_discount=min_discount,
        )

        if not products:
            logger.warning("No products found")
            return

        # Переводим описания
        if translator.is_available:
            descriptions = [p.description for p in products if p.description]
            if descriptions:
                translations = translator.translate_batch(descriptions)
                idx = 0
                for product in products:
                    if product.description:
                        product.description_ua = translations[idx]
                        idx += 1

        # Сокращаем ссылки
        if link_shortener.is_available:
            urls = [p.product_url for p in products]
            short_urls = link_shortener.shorten_batch(urls)
            for product, short_url in zip(products, short_urls):
                product.short_url = short_url

        # Выводим результаты
        print("\n" + "=" * 60)
        print(f"Found {len(products)} products:")
        print("=" * 60 + "\n")

        for i, product in enumerate(products, 1):
            print(f"[{i}] {product.to_viber_message()}")
            print(f"    Image: {product.image_url}")
            print()

    finally:
        await browser_manager.stop()


def main():
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(
        description="BuyerAnons - CLI для тестирования сканирования"
    )
    parser.add_argument("url", help="URL страницы со скидками")
    parser.add_argument(
        "--sizes", "-s",
        help="Размеры через запятую (M,L,42,43)",
        default=""
    )
    parser.add_argument(
        "--top", "-t",
        type=int,
        help="Количество товаров",
        default=10
    )
    parser.add_argument(
        "--min-discount", "-m",
        type=int,
        help="Минимальная скидка в %%",
        default=30
    )

    args = parser.parse_args()

    sizes = [s.strip() for s in args.sizes.split(",") if s.strip()]

    asyncio.run(scan(args.url, sizes, args.top, args.min_discount))


if __name__ == "__main__":
    main()
