from typing import Optional
from loguru import logger
import deepl

from ..config import settings


class Translator:
    """Сервис перевода текста на украинский."""

    def __init__(self):
        self._client: Optional[deepl.Translator] = None
        self._init_client()

    def _init_client(self) -> None:
        """Инициализировать клиент DeepL."""
        if settings.deepl_api_key:
            try:
                self._client = deepl.Translator(settings.deepl_api_key)
                logger.info("DeepL translator initialized")
            except Exception as e:
                logger.warning(f"Failed to init DeepL: {e}")
                self._client = None
        else:
            logger.warning("DEEPL_API_KEY not set, translations disabled")

    def translate(self, text: str, target_lang: str = "UK") -> str:
        """
        Перевести текст.

        Args:
            text: Исходный текст
            target_lang: Целевой язык (UK = украинский)

        Returns:
            Переведённый текст или оригинал при ошибке
        """
        if not text or not self._client:
            return text

        try:
            result = self._client.translate_text(text, target_lang=target_lang)
            return result.text
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return text

    def translate_batch(self, texts: list[str], target_lang: str = "UK") -> list[str]:
        """
        Перевести список текстов.

        Args:
            texts: Список текстов
            target_lang: Целевой язык

        Returns:
            Список переведённых текстов
        """
        if not texts or not self._client:
            return texts

        try:
            results = self._client.translate_text(texts, target_lang=target_lang)
            return [r.text for r in results]
        except Exception as e:
            logger.warning(f"Batch translation failed: {e}")
            return texts

    @property
    def is_available(self) -> bool:
        """Проверить доступность переводчика."""
        return self._client is not None


# Глобальный экземпляр
translator = Translator()
