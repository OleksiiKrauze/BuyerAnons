"""
Скрапер DKNY (dkny.com).

Сайт работает на Shopify, поэтому браузер не нужен: каждая коллекция
отдаёт JSON по адресу /collections/<handle>/products.json с ценами
(price / compare_at_price), размерами и наличием по каждому варианту.
"""
import re
import html as html_lib
from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

from .base import BaseScraper
from ..models import Product


class DknyScraper(BaseScraper):
    """Скрапер DKNY через Shopify products.json."""

    STORE_NAME = "DKNY"
    DOMAINS = ["dkny.com"]

    BASE_URL = "https://www.dkny.com"
    DEFAULT_COLLECTION = "sale"
    CURRENCY = "USD"

    PAGE_LIMIT = 250  # максимум, который отдаёт Shopify
    MAX_PAGES = 20  # защита от бесконечной пагинации (до 5000 товаров)

    COLLECTION_RE = re.compile(r"/collections/([a-z0-9][a-z0-9_-]*)", re.IGNORECASE)
    TAG_RE = re.compile(r"<[^>]+>")

    def __init__(self):
        super().__init__()
        # Shopify выбирает рынок по IP: с европейского IP отдаёт цены в EUR без
        # распродажных скидок. Явно фиксируем рынок США — как на dkny.com.
        self._client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            cookies={"localization": "US", "cart_currency": "USD"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    async def scrape(
        self,
        url: str,
        sizes: Optional[list[str]] = None,
        top_count: int = 10,
        min_discount: int = 0,
        sort_mode: str = "discount",
        max_price: Optional[float] = None,
    ) -> list[Product]:
        logger.info(f"Scraping {self.STORE_NAME}: {url}")

        collection = self._extract_collection(url)
        logger.debug(f"DKNY collection: {collection}")

        products = await self._fetch_collection(collection, sizes)
        logger.info(f"Got {len(products)} products in stock")

        if min_discount > 0:
            products = [p for p in products if p.discount_percent >= min_discount]
            logger.info(f"After discount filter ({min_discount}%): {len(products)} products")

        if sizes:
            products = [p for p in products if p.has_size(sizes)]
            logger.info(f"After size filter: {len(products)} products")

        if sort_mode == "price":
            products.sort(key=lambda p: p.sale_price)
        elif sort_mode == "value" and max_price:
            products = [p for p in products if p.sale_price <= max_price]
            products.sort(key=lambda p: p.discount_percent, reverse=True)
            logger.info(f"Filtered by max price {max_price}: {len(products)} products")
        else:
            products.sort(key=lambda p: p.discount_percent, reverse=True)

        # Каждый цвет у DKNY — отдельный товар с тем же названием.
        # Оставляем лучший по текущей сортировке, чтобы в выдаче не было повторов.
        unique: list[Product] = []
        seen: set[str] = set()
        for p in products:
            if p.name.lower() not in seen:
                seen.add(p.name.lower())
                unique.append(p)

        return unique[:top_count]

    def _extract_collection(self, url: str) -> str:
        """Достать handle коллекции из URL; для ссылок без коллекции — распродажа."""
        path = urlparse(url if "://" in url else f"https://{url}").path
        match = self.COLLECTION_RE.search(path)
        if match:
            return match.group(1).lower()
        if "/products/" in path:
            raise ValueError(
                "Це посилання на окремий товар. Надішліть посилання на розділ, "
                "наприклад https://www.dkny.com/collections/sale"
            )
        return self.DEFAULT_COLLECTION

    async def _fetch_collection(self, collection: str, sizes: Optional[list[str]]) -> list[Product]:
        products: list[Product] = []
        api_url = f"{self.BASE_URL}/collections/{collection}/products.json"

        for page in range(1, self.MAX_PAGES + 1):
            response = await self._client.get(api_url, params={"limit": self.PAGE_LIMIT, "page": page})
            if response.status_code == 404:
                raise ValueError(f"Розділ DKNY «{collection}» не знайдено")
            response.raise_for_status()

            items = response.json().get("products", [])
            logger.debug(f"DKNY page {page}: {len(items)} products")

            # Несуществующий раздел Shopify отдаёт как 200 с пустым списком
            if page == 1 and not items:
                raise ValueError(f"Розділ DKNY «{collection}» не знайдено або він порожній")

            for item in items:
                product = self._parse_product(item, sizes)
                if product:
                    products.append(product)

            if len(items) < self.PAGE_LIMIT:
                break

        return products

    def _parse_product(self, item: dict, wanted_sizes: Optional[list[str]]) -> Optional[Product]:
        try:
            variants = [v for v in item.get("variants", []) if v.get("available")]
            if not variants:
                return None  # нет в наличии

            size_pos = self._option_position(item, "size")
            wanted = {s.strip().lower() for s in wanted_sizes} if wanted_sizes else None

            # Цену берём у варианта нужного размера (если задан фильтр),
            # иначе у варианта с самой большой скидкой.
            priced = variants
            if wanted and size_pos:
                matching = [v for v in variants if str(v.get(f"option{size_pos}") or "").lower() in wanted]
                priced = matching or variants
            best = max(priced, key=self._variant_discount)

            sale_price = float(best.get("price") or 0)
            if sale_price <= 0:
                return None
            compare_at = float(best.get("compare_at_price") or 0)
            original_price = compare_at if compare_at > sale_price else sale_price

            available_sizes: list[str] = []
            if size_pos:
                for v in variants:
                    size = v.get(f"option{size_pos}")
                    if size and size not in available_sizes:
                        available_sizes.append(size)

            image_url = ""
            images = item.get("images") or []
            if images and images[0].get("src"):
                src = images[0]["src"]
                image_url = f"{src}{'&' if '?' in src else '?'}width=1000"

            return Product(
                name=self._clean_title(item.get("title", "")),
                original_price=original_price,
                sale_price=sale_price,
                currency=self.CURRENCY,
                image_url=image_url,
                product_url=f"{self.BASE_URL}/products/{item.get('handle', '')}",
                available_sizes=available_sizes,
                description=self._clean_description(item.get("body_html") or ""),
                store=self.STORE_NAME,
                category=item.get("product_type", ""),
            )
        except Exception as e:
            logger.warning(f"Failed to parse DKNY product {item.get('handle')}: {e}")
            return None

    @staticmethod
    def _option_position(item: dict, name: str) -> Optional[int]:
        for opt in item.get("options", []):
            if str(opt.get("name", "")).lower() == name:
                return opt.get("position")
        return None

    @staticmethod
    def _variant_discount(variant: dict) -> float:
        price = float(variant.get("price") or 0)
        compare_at = float(variant.get("compare_at_price") or 0)
        if price <= 0 or compare_at <= price:
            return 0.0
        return 1 - price / compare_at

    @staticmethod
    def _clean_title(title: str) -> str:
        """DKNY пишет названия капсом — приводим к обычному виду (логотип DKNY оставляем)."""
        title = title.strip()
        if title.isupper():
            title = title.title().replace("Dkny", "DKNY")
        return title

    def _clean_description(self, body_html: str) -> str:
        """Первые пункты описания без HTML, до ~200 символов."""
        text = re.sub(r"</(li|p|div)>|<br\s*/?>", ". ", body_html, flags=re.IGNORECASE)
        text = html_lib.unescape(self.TAG_RE.sub("", text))
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"(\s*\.\s*)+", ". ", text).strip(" .")
        if len(text) > 200:
            text = text[:200].rsplit(" ", 1)[0] + "…"
        return text

    async def parse_products(self, html: str, base_url: str) -> list[Product]:
        """Не используется — данные берутся из JSON API."""
        return []

    async def close(self):
        await self._client.aclose()
