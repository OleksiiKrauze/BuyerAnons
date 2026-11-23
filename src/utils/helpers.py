import re
from typing import Optional, Type
from ..scrapers.base import BaseScraper
from ..scrapers.asda_api import AsdaApiScraper
from ..scrapers.zara import ZaraScraper
from ..scrapers.dkny import DknyScraper


# Реестр скраперов
SCRAPERS: list[Type[BaseScraper]] = [
    ZaraScraper,
    AsdaApiScraper,
    DknyScraper,
]

# Маппинг кода страны в URL → валюта
_COUNTRY_CURRENCY: dict[str, str] = {
    "uk": "GBP",
    "us": "USD",
    "ca": "CAD",
    "au": "AUD",
    "es": "EUR",
    "fr": "EUR",
    "de": "EUR",
    "it": "EUR",
    "pt": "EUR",
    "nl": "EUR",
    "be": "EUR",
    "at": "EUR",
    "ie": "EUR",
    "gr": "EUR",
    "fi": "EUR",
    "se": "SEK",
    "no": "NOK",
    "dk": "DKK",
    "ch": "CHF",
    "pl": "PLN",
    "ro": "RON",
    "cz": "CZK",
    "hu": "HUF",
    "tr": "TRY",
    "ru": "RUB",
    "mx": "MXN",
    "br": "BRL",
    "in": "INR",
    "jp": "JPY",
    "kr": "KRW",
    "cn": "CNY",
    "sa": "SAR",
    "ae": "AED",
}

CURRENCY_SYMBOL: dict[str, str] = {
    "GBP": "£",
    "EUR": "€",
    "USD": "$",
    "CAD": "CA$",
    "AUD": "AU$",
    "PLN": "zł",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "CHF": "CHF",
    "RON": "lei",
    "CZK": "Kč",
    "HUF": "Ft",
    "TRY": "₺",
    "RUB": "₽",
    "MXN": "MX$",
    "BRL": "R$",
    "INR": "₹",
    "JPY": "¥",
    "KRW": "₩",
    "CNY": "¥",
    "SAR": "SAR",
    "AED": "AED",
}


def detect_currency(url: str) -> str:
    """
    Определить валюту по URL.
    Ищет двухбуквенный код страны в URL (напр. zara.com/es/en/).
    По умолчанию GBP.
    """
    url_lower = url.lower()

    # ASDA/George — всегда GBP
    if "asda.com" in url_lower or "george.com" in url_lower:
        return "GBP"

    # DKNY (dkny.com) — американский магазин, цены в USD
    if "dkny.com" in url_lower:
        return "USD"

    # Ищем паттерн /XX/ где XX — код страны
    match = re.search(r'\.com/([a-z]{2})/', url_lower)
    if match:
        country = match.group(1)
        return _COUNTRY_CURRENCY.get(country, "GBP")

    return "GBP"


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
