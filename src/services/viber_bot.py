import re
from typing import Optional, Callable, Awaitable
from loguru import logger
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.messages import TextMessage, PictureMessage
from viberbot.api.viber_requests import (
    ViberMessageRequest,
    ViberConversationStartedRequest,
    ViberSubscribedRequest,
)

from ..config import settings
from ..models import Product


class ViberBot:
    """Viber бот для отправки уведомлений о скидках."""

    def __init__(self):
        self._api: Optional[Api] = None
        self._scan_handler: Optional[Callable] = None
        self._init_api()

    def _init_api(self) -> None:
        """Инициализировать Viber API."""
        if settings.viber_bot_token:
            try:
                self._api = Api(BotConfiguration(
                    name=settings.viber_bot_name,
                    auth_token=settings.viber_bot_token,
                    avatar=None,
                ))
                logger.info(f"Viber bot '{settings.viber_bot_name}' initialized")
            except Exception as e:
                logger.error(f"Failed to init Viber API: {e}")
                self._api = None
        else:
            logger.warning("VIBER_BOT_TOKEN not set, Viber bot disabled")

    def set_webhook(self, url: str) -> bool:
        """
        Установить webhook URL.

        Args:
            url: URL для webhook (должен быть HTTPS)

        Returns:
            True если успешно
        """
        if not self._api:
            return False

        try:
            self._api.set_webhook(url)
            logger.info(f"Webhook set to: {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
            return False

    def verify_signature(self, request_data: bytes, signature: str) -> bool:
        """Проверить подпись запроса."""
        if not self._api:
            return False
        return self._api.verify_signature(request_data, signature)

    def parse_request(self, request_data: dict) -> Optional[dict]:
        """Распарсить входящий запрос."""
        if not self._api:
            return None
        return self._api.parse_request(request_data)

    def register_scan_handler(self, handler: Callable) -> None:
        """Зарегистрировать обработчик команды /scan."""
        self._scan_handler = handler

    async def handle_message(self, request: ViberMessageRequest) -> None:
        """Обработать входящее сообщение."""
        sender_id = request.sender.id
        message_text = request.message.text if hasattr(request.message, 'text') else ""

        logger.info(f"Message from {sender_id}: {message_text}")

        # Парсим команду /scan
        if message_text.startswith("/scan"):
            await self._handle_scan_command(sender_id, message_text)
        elif message_text.startswith("/help"):
            await self._send_help(sender_id)
        else:
            await self.send_text(
                sender_id,
                "Невідома команда. Використовуйте /help для довідки."
            )

    async def _handle_scan_command(self, sender_id: str, message: str) -> None:
        """Обработать команду /scan."""
        # Парсим параметры: /scan URL --sizes M,L --top 10
        pattern = r'/scan\s+(https?://\S+)(?:\s+--sizes\s+(\S+))?(?:\s+--top\s+(\d+))?(?:\s+--min-discount\s+(\d+))?'
        match = re.match(pattern, message)

        if not match:
            await self.send_text(
                sender_id,
                "Невірний формат. Приклад:\n"
                "/scan https://asos.com/sale --sizes M,L,42 --top 10"
            )
            return

        url = match.group(1)
        sizes = match.group(2).split(",") if match.group(2) else []
        top_count = int(match.group(3)) if match.group(3) else settings.default_top_count
        min_discount = int(match.group(4)) if match.group(4) else settings.default_min_discount

        await self.send_text(sender_id, f"🔍 Сканую {url}...")

        if self._scan_handler:
            try:
                products = await self._scan_handler(url, sizes, top_count, min_discount)
                await self.send_products(sender_id, products)
            except Exception as e:
                logger.error(f"Scan failed: {e}")
                await self.send_text(sender_id, f"❌ Помилка сканування: {e}")
        else:
            await self.send_text(sender_id, "❌ Обробник сканування не налаштований")

    async def _send_help(self, sender_id: str) -> None:
        """Отправить справку."""
        help_text = """
📖 *BuyerAnons - Пошук знижок*

Команди:
/scan URL --sizes M,L,42 --top 10

Параметри:
• URL - посилання на сторінку розпродажу
• --sizes - розміри через кому (опціонально)
• --top - кількість товарів (за замовч. 10)
• --min-discount - мін. знижка % (за замовч. 30)

Приклад:
/scan https://www.asos.com/men/sale/ --sizes M,L,42,43 --top 15
        """.strip()
        await self.send_text(sender_id, help_text)

    async def handle_conversation_started(self, request: ViberConversationStartedRequest) -> None:
        """Обработать начало диалога."""
        user_id = request.user.id
        logger.info(f"New conversation started with {user_id}")
        await self._send_help(user_id)

    def send_text(self, receiver: str, text: str) -> bool:
        """
        Отправить текстовое сообщение.

        Args:
            receiver: ID получателя
            text: Текст сообщения

        Returns:
            True если успешно
        """
        if not self._api:
            logger.warning("Viber API not initialized")
            return False

        try:
            self._api.send_messages(receiver, [TextMessage(text=text)])
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    def send_picture(self, receiver: str, image_url: str, text: str = "") -> bool:
        """
        Отправить изображение.

        Args:
            receiver: ID получателя
            image_url: URL изображения
            text: Подпись (опционально)

        Returns:
            True если успешно
        """
        if not self._api:
            return False

        try:
            self._api.send_messages(receiver, [
                PictureMessage(media=image_url, text=text)
            ])
            return True
        except Exception as e:
            logger.error(f"Failed to send picture: {e}")
            return False

    async def send_products(self, receiver: str, products: list[Product]) -> None:
        """
        Отправить список товаров.

        Args:
            receiver: ID получателя
            products: Список товаров
        """
        if not products:
            self.send_text(receiver, "😕 Товарів не знайдено за вашими критеріями")
            return

        self.send_text(receiver, f"✅ Знайдено {len(products)} товарів:")

        for product in products:
            # Отправляем фото с описанием
            if product.image_url:
                self.send_picture(
                    receiver,
                    product.image_url,
                    product.to_viber_message()
                )
            else:
                self.send_text(receiver, product.to_viber_message())

    @property
    def is_available(self) -> bool:
        """Проверить доступность бота."""
        return self._api is not None


# Глобальный экземпляр
viber_bot = ViberBot()
