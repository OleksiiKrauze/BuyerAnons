from typing import Optional, Type
from ..scrapers.base import BaseScraper
from ..scrapers.asda import AsdaScraper


# Реестр скраперов
SCRAPERS: list[Type[BaseScraper]] = [
    AsdaScraper,
    # Добавить другие скраперы здесь
]


def detect_store(url: str) -> Optional[str]:
    """
    Определить магазин по URL.

    Args:
        url: URL страницы

    Returns:
        Название магазина или None
    """
    for scraper_class in SCRAPERS:
        if scraper_class.can_handle(url):
            return scraper_class.STORE_NAME
    return None


def get_scraper(url: str) -> Optional[BaseScraper]:
    """
    Получить подходящий скрапер для URL.

    Args:
        url: URL страницы

    Returns:
        Экземпляр скрапера или None
    """
    for scraper_class in SCRAPERS:
        if scraper_class.can_handle(url):
            return scraper_class()
    return None
