from typing import Optional
from loguru import logger
import pyshorteners
import httpx

from ..config import settings


class LinkShortener:
    """Сервис сокращения ссылок."""

    def __init__(self):
        self._shortener: Optional[pyshorteners.Shortener] = None
        self._init_shortener()

    def _init_shortener(self) -> None:
        """Инициализировать сокращатель."""
        try:
            if settings.bitly_api_key:
                self._shortener = pyshorteners.Shortener(api_key=settings.bitly_api_key)
                self._service = "bitly"
                logger.info("Using bit.ly for link shortening")
            else:
                self._shortener = pyshorteners.Shortener()
                self._service = "tinyurl"
                logger.info("Using TinyURL for link shortening (no API key)")
        except Exception as e:
            logger.warning(f"Failed to init shortener: {e}")
            self._shortener = None
            self._service = None

    def shorten(self, url: str) -> str:
        """
        Сократить ссылку.

        Args:
            url: Длинная ссылка

        Returns:
            Короткая ссылка или оригинал при ошибке
        """
        if not url or not self._shortener:
            return url

        try:
            if self._service == "bitly":
                return self._shortener.bitly.short(url)
            else:
                return self._shortener.tinyurl.short(url)
        except Exception as e:
            logger.warning(f"Link shortening failed: {e}")
            return url

    def shorten_batch(self, urls: list[str]) -> list[str]:
        """
        Сократить список ссылок.

        Args:
            urls: Список длинных ссылок

        Returns:
            Список коротких ссылок
        """
        return [self.shorten(url) for url in urls]

    @property
    def is_available(self) -> bool:
        """Проверить доступность сервиса."""
        return self._shortener is not None


# Глобальный экземпляр
link_shortener = LinkShortener()
