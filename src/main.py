"""
BuyerAnons - Сервис мониторинга скидок в интернет-магазинах.

Запуск:
    python -m src.main
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from loguru import logger
import uvicorn

from .config import settings
from .models import Product
from .scrapers.browser import browser_manager
from .services.translator import translator
from .services.link_shortener import link_shortener
from .services.viber_bot import viber_bot
from .utils import get_scraper, detect_store


class ScanOrchestrator:
    """Оркестратор процесса сканирования."""

    async def scan(
        self,
        url: str,
        sizes: Optional[list[str]] = None,
        top_count: int = 10,
        min_discount: int = 30,
    ) -> list[Product]:
        """
        Сканировать страницу и вернуть топ предложений.

        Args:
            url: URL страницы со скидками
            sizes: Фильтр по размерам
            top_count: Количество товаров
            min_discount: Минимальная скидка

        Returns:
            Список товаров с переводами и короткими ссылками
        """
        # Определяем магазин и получаем скрапер
        store = detect_store(url)
        if not store:
            raise ValueError(f"Unsupported store: {url}")

        scraper = get_scraper(url)
        if not scraper:
            raise ValueError(f"No scraper for: {url}")

        logger.info(f"Scanning {store}: {url}")
        logger.info(f"Filters: sizes={sizes}, top={top_count}, min_discount={min_discount}%")

        # Запускаем скрапинг
        products = await scraper.scrape(
            url=url,
            sizes=sizes,
            top_count=top_count,
            min_discount=min_discount,
        )

        if not products:
            logger.warning("No products found")
            return []

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


# Создаём оркестратор
orchestrator = ScanOrchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для FastAPI."""
    # Startup
    logger.info("Starting BuyerAnons service...")
    await browser_manager.start()

    # Регистрируем обработчик сканирования для Viber бота
    viber_bot.register_scan_handler(orchestrator.scan)

    # Устанавливаем webhook если настроен
    if settings.viber_webhook_url:
        viber_bot.set_webhook(settings.viber_webhook_url)

    yield

    # Shutdown
    logger.info("Shutting down...")
    await browser_manager.stop()


# Создаём приложение FastAPI
app = FastAPI(
    title="BuyerAnons",
    description="Сервис мониторинга скидок в интернет-магазинах",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": "BuyerAnons"}


@app.get("/health")
async def health():
    """Детальный health check."""
    return {
        "status": "ok",
        "services": {
            "viber_bot": viber_bot.is_available,
            "translator": translator.is_available,
            "link_shortener": link_shortener.is_available,
        }
    }


@app.post("/viber/webhook")
async def viber_webhook(request: Request):
    """
    Webhook для Viber бота.

    Viber отправляет сюда все события.
    """
    if not viber_bot.is_available:
        raise HTTPException(status_code=503, detail="Viber bot not configured")

    # Получаем данные запроса
    signature = request.headers.get("X-Viber-Content-Signature", "")
    body = await request.body()

    # Проверяем подпись
    if not viber_bot.verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Парсим запрос
    data = await request.json()
    viber_request = viber_bot.parse_request(data)

    if viber_request is None:
        return {"status": "ok"}

    # Обрабатываем запрос
    from viberbot.api.viber_requests import (
        ViberMessageRequest,
        ViberConversationStartedRequest,
    )

    if isinstance(viber_request, ViberMessageRequest):
        await viber_bot.handle_message(viber_request)
    elif isinstance(viber_request, ViberConversationStartedRequest):
        await viber_bot.handle_conversation_started(viber_request)

    return {"status": "ok"}


@app.post("/api/scan")
async def api_scan(
    url: str,
    sizes: Optional[str] = None,
    top: int = 10,
    min_discount: int = 30,
):
    """
    API endpoint для сканирования.

    Для тестирования без Viber.
    """
    size_list = sizes.split(",") if sizes else None

    try:
        products = await orchestrator.scan(
            url=url,
            sizes=size_list,
            top_count=top,
            min_discount=min_discount,
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
    """Точка входа."""
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
