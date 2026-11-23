"""Run Telegram bot with polling."""
import asyncio
import sys
sys.path.insert(0, '/app')

from loguru import logger
from src.services.telegram_bot import telegram_bot
from src.services.translator import translator
from src.scrapers import ZaraScraper, AsdaApiScraper, NewBalanceScraper, GeorgeScraper, DknyScraper


# Scrapers registry - order matters! More specific scrapers first
scrapers = {
    "george": GeorgeScraper(),  # Must be before ASDA (handles /george/ URLs)
    "zara": ZaraScraper(),
    "asda": AsdaApiScraper(),
    "newbalance": NewBalanceScraper(),
    "dkny": DknyScraper(),
}


def translate_products(products):
    """Translate product names and descriptions to Ukrainian."""
    if not translator.is_available:
        logger.warning("Translator not available, skipping translation")
        return products

    # Collect texts to translate
    texts_to_translate = []
    for p in products:
        texts_to_translate.append(p.name)
        if p.description:
            texts_to_translate.append(p.description)

    if not texts_to_translate:
        return products

    # Batch translate
    logger.info(f"Translating {len(texts_to_translate)} texts...")
    translated = translator.translate_batch(texts_to_translate, target_lang="UK")

    # Apply translations back to products
    idx = 0
    for p in products:
        p.name = translated[idx]
        idx += 1
        if p.description:
            p.description_ua = translated[idx]
            idx += 1

    logger.info("Translation completed")
    return products


async def scan_handler(url: str, sizes: list, top_count: int, min_discount: int, sort_mode: str = "discount", max_price: float = None):
    """Handle /scan command."""
    logger.info(f"Scanning: {url}, sizes={sizes}, top={top_count}, min_discount={min_discount}, sort={sort_mode}, max_price={max_price}")

    # Find appropriate scraper
    scraper = None
    url_lower = url.lower()

    for name, s in scrapers.items():
        if s.can_handle(url):
            scraper = s
            logger.info(f"Using scraper: {name}")
            break

    # Try Zara scraper for zara URLs or keywords
    if not scraper and "zara" in url_lower:
        scraper = scrapers["zara"]

    if not scraper:
        raise ValueError(f"No scraper found for URL: {url}")

    products = await scraper.scrape(
        url=url,
        sizes=sizes if sizes else None,
        top_count=top_count,
        min_discount=min_discount,
        sort_mode=sort_mode,
        max_price=max_price,
    )

    # Translate to Ukrainian
    products = translate_products(products)

    return products


async def main():
    logger.info("Starting BuyerAnons Telegram bot...")

    # Check bot
    me = await telegram_bot.get_me()
    if not me:
        logger.error("Failed to connect to Telegram API")
        return

    logger.info(f"Bot @{me.get('username')} is online!")

    # Register scan handler
    telegram_bot.register_scan_handler(scan_handler)

    # Start polling
    await telegram_bot.start_polling()

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await telegram_bot.close()


if __name__ == "__main__":
    asyncio.run(main())
