"""
BuyerAnons - Сервис мониторинга скидок в интернет-магазинах.

Запуск:
    python -m src.main
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from loguru import logger
import uvicorn

from .config import settings
from .models import Product
from .scrapers.browser import browser_manager
from .services.translator import translator
from .services.link_shortener import link_shortener
from .services.telegram_bot import telegram_bot
from .utils import get_scraper, detect_store


class ScanOrchestrator:
    """Оркестратор процесса сканирования."""

    async def scan(
        self,
        url: str,
        sizes: Optional[list[str]] = None,
        top_count: int = 10,
        min_discount: int = 0,
        sort_mode: str = "discount",
        max_price: Optional[float] = None,
    ) -> list[Product]:
        store = detect_store(url)
        if not store:
            raise ValueError(f"Unsupported store: {url}")

        scraper = get_scraper(url)
        if not scraper:
            raise ValueError(f"No scraper for: {url}")

        logger.info(f"Scanning {store}: {url}")
        logger.info(f"Filters: sizes={sizes}, top={top_count}, min_discount={min_discount}%")

        products = await scraper.scrape(
            url=url,
            sizes=sizes,
            top_count=top_count,
            min_discount=min_discount,
        )

        if not products:
            logger.warning("No products found")
            return []

        # Сортировка
        if sort_mode == "price":
            products.sort(key=lambda p: p.sale_price)
        elif sort_mode == "value" and max_price is not None:
            products = [p for p in products if p.sale_price <= max_price]
            products.sort(key=lambda p: -p.discount_percent)
        else:
            products.sort(key=lambda p: -p.discount_percent)

        products = products[:top_count]

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

        logger.info(f"Found {len(products)} products")
        return products


orchestrator = ScanOrchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting BuyerAnons service...")
    await browser_manager.start()

    telegram_bot.register_scan_handler(orchestrator.scan)
    await telegram_bot.start_polling()

    yield

    logger.info("Shutting down...")
    await telegram_bot.close()
    await browser_manager.stop()


app = FastAPI(
    title="BuyerAnons",
    description="Сервис мониторинга скидок в интернет-магазинах",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {"status": "ok", "service": "BuyerAnons"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "services": {
            "telegram_bot": telegram_bot.is_available,
            "translator": translator.is_available,
            "link_shortener": link_shortener.is_available,
        }
    }


@app.post("/api/scan")
async def api_scan(
    url: str,
    sizes: Optional[str] = None,
    top: int = 10,
    min_discount: int = 0,
    sort: str = "discount",
    max_price: Optional[float] = None,
):
    """API endpoint для тестирования без Telegram."""
    size_list = sizes.split(",") if sizes else None

    try:
        products = await orchestrator.scan(
            url=url,
            sizes=size_list,
            top_count=top,
            min_discount=min_discount,
            sort_mode=sort,
            max_price=max_price,
        )

        return {
            "status": "ok",
            "count": len(products),
            "products": [
                {
                    "name": p.name,
                    "original_price": p.original_price,
                    "sale_price": p.sale_price,
                    "discount_percent": p.discount_percent,
                    "currency": p.currency,
                    "sizes": p.available_sizes,
                    "description": p.description_ua or p.description,
                    "url": p.short_url or p.product_url,
                    "image": p.image_url,
                }
                for p in products
            ]
        }

    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
