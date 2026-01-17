from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger

from ..models import Product
from .browser import browser_manager


class BaseScraper(ABC):
    """Базовый класс для скраперов магазинов."""

    # Название магазина (переопределить в наследниках)
    STORE_NAME: str = "Unknown"

    # Домены магазина для идентификации
    DOMAINS: list[str] = []

    # CSS селектор для ожидания загрузки
    WAIT_SELECTOR: Optional[str] = None

    def __init__(self):
        self.browser = browser_manager

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Проверить, может ли этот скрапер обработать URL."""
        url_lower = url.lower()
        return any(domain in url_lower for domain in cls.DOMAINS)

    async def scrape(
        self,
        url: str,
        sizes: Optional[list[str]] = None,
        top_count: int = 10,
        min_discount: int = 0,
    ) -> list[Product]:
        """
        Получить топ предложений со страницы.

        Args:
            url: URL страницы со скидками
            sizes: Фильтр по размерам
            top_count: Количество товаров
            min_discount: Минимальная скидка в %

        Returns:
            Список товаров
        """
        logger.info(f"Scraping {self.STORE_NAME}: {url}")

        # Загружаем страницу
        html = await self.browser.fetch_page(url, self.WAIT_SELECTOR)

        # Парсим товары
        products = await self.parse_products(html, url)
        logger.info(f"Parsed {len(products)} products")

        # Фильтруем по размерам
        if sizes:
            products = [p for p in products if p.has_size(sizes)]
            logger.info(f"After size filter: {len(products)} products")

        # Фильтруем по минимальной скидке
        if min_discount > 0:
            products = [p for p in products if p.discount_percent >= min_discount]
            logger.info(f"After discount filter: {len(products)} products")

        # Сортируем по скидке (самые большие сверху)
        products.sort(key=lambda p: p.discount_percent, reverse=True)

        # Возвращаем топ N
        return products[:top_count]

    @abstractmethod
    async def parse_products(self, html: str, base_url: str) -> list[Product]:
        """
        Парсить товары из HTML.

        Args:
            html: HTML содержимое страницы
            base_url: Базовый URL для относительных ссылок

        Returns:
            Список товаров
        """
        pass

    def _normalize_size(self, size: str) -> str:
        """Нормализовать размер для сравнения."""
        return size.strip().upper()

    def _parse_price(self, price_str: str) -> float:
        """Извлечь числовое значение цены из строки."""
        import re
        # Удаляем всё кроме цифр и точки/запятой
        cleaned = re.sub(r"[^\d.,]", "", price_str)
        # Заменяем запятую на точку
        cleaned = cleaned.replace(",", ".")
        # Если есть несколько точек, оставляем только последнюю
        parts = cleaned.split(".")
        if len(parts) > 2:
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
