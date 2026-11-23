"""
Telegram бот для отправки уведомлений о скидках.
"""
import re
import asyncio
import hashlib
from typing import Optional, Callable
from loguru import logger
import httpx

from ..config import settings
from ..models import Product
from ..utils.helpers import detect_currency, CURRENCY_SYMBOL


# Варианты сканирования для inline-кнопок (label зависит от валюты, строится динамически)
# (sort_mode, top, min_discount, max_price, sizes)
_SCAN_OPTIONS_BASE = [
    ("🔥 Топ-10 знижок",   "discount", 10, 0,  None, []),
    ("💰 Топ-10 дешевших", "price",    10, 0,  None, []),
    ("🏷 Знижка 30%+",     "discount", 10, 30, None, []),
    ("🏷 Знижка 50%+",     "discount", 10, 50, None, []),
    (None,                  "value",    10, 0,  20.0, []),  # label строится динамически
    (None,                  "value",    10, 0,  50.0, []),  # label строится динамически
    ("📏 Розмір S",         "discount", 10, 0,  None, ["S"]),
    ("📏 Розмір M",         "discount", 10, 0,  None, ["M"]),
    ("📏 Розмір L",         "discount", 10, 0,  None, ["L"]),
    ("📏 Розмір XL",        "discount", 10, 0,  None, ["XL"]),
]


def _build_scan_options(currency: str) -> list[tuple]:
    """Собрать список кнопок с учётом валюты."""
    sym = CURRENCY_SYMBOL.get(currency, currency)
    result = []
    for label, sort_mode, top, min_disc, max_price, sizes in _SCAN_OPTIONS_BASE:
        if label is None:
            label = f"💵 До {sym}{int(max_price)} + знижка"
        result.append((label, sort_mode, top, min_disc, max_price, sizes))
    return result


class TelegramBot:
    """Telegram бот для отправки уведомлений о скидках."""

    API_BASE = "https://api.telegram.org/bot"
    URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)

    def __init__(self):
        self._token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._scan_handler: Optional[Callable] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._last_update_id: int = 0
        self._url_store: dict[str, str] = {}  # key -> url
        self._init_bot()

    def _init_bot(self) -> None:
        if settings.telegram_bot_token:
            self._token = settings.telegram_bot_token
            # Таймаут больше, чем long polling getUpdates (30 с), иначе запрос обрывается
            self._client = httpx.AsyncClient(timeout=45)
            logger.info("Telegram bot initialized")
        else:
            logger.warning("TELEGRAM_BOT_TOKEN not set, Telegram bot disabled")

    def _url_key(self, url: str) -> str:
        """Короткий ключ для URL (8 символов hex)."""
        return hashlib.md5(url.encode()).hexdigest()[:8]

    async def _api_call(self, method: str, **params) -> Optional[dict]:
        if not self._token or not self._client:
            return None
        url = f"{self.API_BASE}{self._token}/{method}"
        try:
            response = await self._client.post(url, json=params)
            data = response.json()
            if not data.get("ok"):
                logger.error(f"Telegram API error: {data.get('description')}")
                return None
            return data.get("result")
        except Exception as e:
            logger.error(f"Telegram API call failed: {e}")
            return None

    async def get_me(self) -> Optional[dict]:
        return await self._api_call("getMe")

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
        reply_markup: Optional[dict] = None,
    ) -> Optional[dict]:
        params = dict(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
        if reply_markup:
            params["reply_markup"] = reply_markup
        return await self._api_call("sendMessage", **params)

    async def send_photo(
        self,
        chat_id: int | str,
        photo_url: str,
        caption: str = "",
        parse_mode: str = "HTML",
    ) -> Optional[dict]:
        return await self._api_call(
            "sendPhoto",
            chat_id=chat_id,
            photo=photo_url,
            caption=caption[:1024],
            parse_mode=parse_mode,
        )

    async def answer_callback_query(self, callback_query_id: str, text: str = "") -> None:
        await self._api_call("answerCallbackQuery", callback_query_id=callback_query_id, text=text)

    def register_scan_handler(self, handler: Callable) -> None:
        self._scan_handler = handler

    def _is_user_allowed(self, chat_id: int) -> bool:
        allowed = settings.allowed_user_ids
        if not allowed:
            return True
        return chat_id in allowed

    async def handle_update(self, update: dict) -> None:
        # Обработка нажатия inline-кнопки
        if "callback_query" in update:
            await self._handle_callback_query(update["callback_query"])
            return

        message = update.get("message", {})
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        if not chat_id or not text:
            return

        logger.info(f"Message from {chat_id}: {text}")

        if text.startswith("/id"):
            await self.send_message(chat_id, f"Ваш Chat ID: <code>{chat_id}</code>")
            return

        if not self._is_user_allowed(chat_id):
            await self.send_message(
                chat_id,
                "⛔ Доступ заборонено.\n\nВаш Chat ID: <code>{}</code>\nЗверніться до адміністратора.".format(chat_id)
            )
            return

        if text.startswith("/scan"):
            await self._handle_scan_command(chat_id, text)
        elif text.startswith("/start"):
            await self._send_welcome(chat_id)
        elif text.startswith("/help"):
            await self._send_help(chat_id)
        else:
            # Проверяем, есть ли URL в сообщении
            url_match = self.URL_RE.search(text)
            if url_match:
                await self._handle_url_message(chat_id, url_match.group(0))
            else:
                await self.send_message(chat_id, "Невідома команда. Надішліть посилання або /help.")

    async def _handle_url_message(self, chat_id: int, url: str) -> None:
        """Пользователь прислал ссылку — отвечаем кнопками выбора."""
        key = self._url_key(url)
        self._url_store[key] = url

        currency = detect_currency(url)
        scan_options = _build_scan_options(currency)

        buttons = []
        row = []
        for i, (label, *_) in enumerate(scan_options):
            row.append({"text": label, "callback_data": f"{key}|{i}"})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        markup = {"inline_keyboard": buttons}
        await self.send_message(
            chat_id,
            "🔗 <b>Посилання отримано</b>\nОберіть варіант виборки:",
            reply_markup=markup,
        )

    async def _handle_callback_query(self, callback_query: dict) -> None:
        """Пользователь нажал кнопку."""
        query_id = callback_query.get("id")
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        data = callback_query.get("data", "")

        await self.answer_callback_query(query_id)

        if not chat_id or not data or "|" not in data:
            return

        if not self._is_user_allowed(chat_id):
            return

        parts = data.split("|")
        if len(parts) != 2:
            return

        key, idx_str = parts
        url = self._url_store.get(key)
        if not url:
            await self.send_message(chat_id, "❌ Посилання застаріло, надішліть його ще раз.")
            return

        try:
            idx = int(idx_str)
            currency = detect_currency(url)
            scan_options = _build_scan_options(currency)
            label, sort_mode, top_count, min_discount, max_price, sizes = scan_options[idx]
        except (ValueError, IndexError):
            return

        await self.send_message(chat_id, f"🔍 Сканую...\n<b>{label}</b>")

        if self._scan_handler:
            try:
                products = await self._scan_handler(url, sizes, top_count, min_discount, sort_mode, max_price)
                await self.send_products(chat_id, products)
            except Exception as e:
                logger.error(f"Scan failed: {e}")
                await self.send_message(chat_id, f"❌ Помилка сканування: {e}")
        else:
            await self.send_message(chat_id, "❌ Обробник сканування не налаштований")

    async def _handle_scan_command(self, chat_id: int, message: str) -> None:
        """Обработать команду /scan (для ручного использования)."""
        pattern = r'/scan\s+(https?://\S+)(?:\s+--sizes\s+(\S+))?(?:\s+--top\s+(\d+))?(?:\s+--min-discount\s+(\d+))?(?:\s+--sort\s+(\w+)(?:\s+(\d+(?:\.\d+)?))?)?'
        match = re.match(pattern, message)

        if not match:
            await self.send_message(
                chat_id,
                "❌ Невірний формат.\n\n"
                "Або просто надішліть посилання без команди.\n\n"
                "Приклад /scan:\n"
                "<code>/scan https://www.zara.com/... --top 10 --sort price</code>"
            )
            return

        url = match.group(1)
        sizes = match.group(2).split(",") if match.group(2) else []
        top_count = int(match.group(3)) if match.group(3) else settings.default_top_count
        min_discount = int(match.group(4)) if match.group(4) else 0
        sort_mode = match.group(5) if match.group(5) else "discount"
        max_price = float(match.group(6)) if match.group(6) else None

        await self.send_message(chat_id, f"🔍 Сканую {url}...")

        if self._scan_handler:
            try:
                products = await self._scan_handler(url, sizes, top_count, min_discount, sort_mode, max_price)
                await self.send_products(chat_id, products)
            except Exception as e:
                logger.error(f"Scan failed: {e}")
                await self.send_message(chat_id, f"❌ Помилка сканування: {e}")
        else:
            await self.send_message(chat_id, "❌ Обробник сканування не налаштований")

    async def _send_welcome(self, chat_id: int) -> None:
        welcome = (
            "👋 Вітаю! Я <b>BuyerAnons</b> - бот для пошуку знижок.\n\n"
            "Просто надішліть посилання на сторінку магазину — я запропоную варіанти виборки.\n\n"
            f"Ваш Chat ID: <code>{chat_id}</code>"
        )
        await self.send_message(chat_id, welcome)

    async def _send_help(self, chat_id: int) -> None:
        help_text = (
            "📖 <b>BuyerAnons - Пошук знижок</b>\n\n"
            "<b>Як користуватись:</b>\n"
            "Надішліть посилання на сторінку магазину — бот покаже кнопки з варіантами виборки.\n\n"
            "<b>Підтримувані магазини:</b>\n"
            "• Zara (zara.com)\n"
            "• ASDA / George (asda.com, george.com)\n"
            "• DKNY (dkny.com)\n"
            "• Joe's New Balance Outlet (joesnewbalanceoutlet.com)\n\n"
            "<b>Команди:</b>\n"
            "/help - ця довідка\n"
            "/id - показати ваш Chat ID\n"
            "/scan URL [параметри] - ручний запит"
        )
        await self.send_message(chat_id, help_text)

    async def send_products(self, chat_id: int, products: list[Product]) -> None:
        if not products:
            await self.send_message(chat_id, "😕 Товарів не знайдено за вашими критеріями")
            return

        await self.send_message(chat_id, f"✅ Знайдено {len(products)} товарів:")

        for product in products:
            message = self._format_product(product)
            if product.image_url:
                result = await self.send_photo(chat_id, product.image_url, message)
                if not result:
                    await self.send_message(chat_id, message)
            else:
                await self.send_message(chat_id, message)
            await asyncio.sleep(0.5)

    def _format_product(self, product: Product) -> str:
        currency_symbol = {
            "GBP": "£", "EUR": "€", "USD": "$", "UAH": "₴"
        }.get(product.currency, product.currency)

        sizes_str = ", ".join(product.available_sizes[:5])
        if len(product.available_sizes) > 5:
            sizes_str += "..."

        description = product.description_ua if product.description_ua else product.description
        if description and len(description) > 100:
            description = description[:97] + "..."

        link = product.short_url or product.product_url

        lines = [f"📦 <b>{product.name}</b>", f"💰 {currency_symbol}{product.sale_price:.0f}"]

        if product.discount_percent > 0:
            lines[1] += f" <s>{currency_symbol}{product.original_price:.0f}</s> <b>-{product.discount_percent}%</b>"

        if sizes_str:
            lines.append(f"📏 Розміри: {sizes_str}")

        if description:
            lines.append(f"📝 {description}")

        lines.append(f"🔗 <a href=\"{link}\">Перейти до товару</a>")

        return "\n".join(lines)

    async def start_polling(self) -> None:
        if not self._token:
            logger.error("Cannot start polling: token not set")
            return
        logger.info("Starting Telegram bot polling...")
        self._polling_task = asyncio.create_task(self._polling_loop())

    async def stop_polling(self) -> None:
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            logger.info("Polling stopped")

    async def _polling_loop(self) -> None:
        while True:
            try:
                updates = await self._api_call(
                    "getUpdates",
                    offset=self._last_update_id + 1,
                    timeout=30,
                )
                if updates:
                    for update in updates:
                        self._last_update_id = update.get("update_id", 0)
                        await self.handle_update(update)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)

    @property
    def is_available(self) -> bool:
        return self._token is not None

    async def close(self) -> None:
        await self.stop_polling()
        if self._client:
            await self._client.aclose()


telegram_bot = TelegramBot()
