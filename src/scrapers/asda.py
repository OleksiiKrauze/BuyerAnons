import re
import json
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger
from urllib.parse import urljoin, urlparse, parse_qs

from .base import BaseScraper
from ..models import Product


class AsdaScraper(BaseScraper):
    """Скрапер для ASDA Direct (direct.asda.com)."""

    STORE_NAME = "ASDA"
    DOMAINS = ["direct.asda.com", "asda.com"]
    WAIT_SELECTOR = "[data-auto-id='productList'], .product-grid, .search-results"

    async def parse_products(self, html: str, base_url: str) -> list[Product]:
        """Парсить товары ASDA из HTML."""
        products = []

        # Сначала пробуем найти JSON данные в HTML
        json_products = self._extract_json_data(html)
        if json_products:
            logger.info(f"Found {len(json_products)} products in JSON data")
            for item in json_products:
                product = self._parse_json_product(item, base_url)
                if product:
                    products.append(product)
            if products:
                return products

        # Fallback: парсим HTML напрямую
        soup = BeautifulSoup(html, "html.parser")

        # ASDA использует разные селекторы для карточек товаров
        product_cards = soup.select("[data-auto-id='product-tile']")
        if not product_cards:
            product_cards = soup.select(".product-tile, .product-card")
        if not product_cards:
            product_cards = soup.select("[class*='product']")
            # Фильтруем только реальные карточки товаров
            product_cards = [c for c in product_cards if c.select_one("a[href*='/product/']")]

        logger.info(f"Found {len(product_cards)} product cards in HTML")

        for card in product_cards:
            try:
                product = self._parse_html_product(card, base_url)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Failed to parse product card: {e}")

        return products

    def _extract_json_data(self, html: str) -> Optional[list[dict]]:
        """Извлечь JSON данные о товарах из HTML."""
        patterns = [
            # Next.js data
            r'<script id="__NEXT_DATA__"[^>]*>({.*?})</script>',
            # Inline JSON
            r'"products"\s*:\s*(\[.*?\])',
            r'"items"\s*:\s*(\[.*?\])',
            # Window object
            r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
            r'window\.initialState\s*=\s*({.*?});',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))

                    # Ищем массив продуктов в разных местах
                    if isinstance(data, list):
                        return data

                    # Next.js структура
                    if "props" in data:
                        page_props = data.get("props", {}).get("pageProps", {})
                        products = (
                            page_props.get("products") or
                            page_props.get("items") or
                            page_props.get("searchResults", {}).get("products") or
                            page_props.get("data", {}).get("products")
                        )
                        if products:
                            return products

                    # Прямой доступ
                    if "products" in data:
                        return data["products"]
                    if "items" in data:
                        return data["items"]

                except json.JSONDecodeError:
                    continue

        return None

    def _parse_json_product(self, item: dict, base_url: str) -> Optional[Product]:
        """Парсить товар из JSON данных."""
        try:
            # Название
            name = (
                item.get("name") or
                item.get("title") or
                item.get("productName") or
                ""
            )
            if not name:
                return None

            # Цены - ASDA может использовать разные структуры
            price_data = item.get("price", {})
            if isinstance(price_data, dict):
                current_price = (
                    price_data.get("now") or
                    price_data.get("current") or
                    price_data.get("salePrice") or
                    price_data.get("price") or
                    0
                )
                original_price = (
                    price_data.get("was") or
                    price_data.get("previous") or
                    price_data.get("rrp") or
                    price_data.get("originalPrice") or
                    current_price
                )
            else:
                current_price = item.get("salePrice") or item.get("price") or 0
                original_price = item.get("wasPrice") or item.get("rrp") or current_price

            # Преобразуем в float
            current_price = self._to_float(current_price)
            original_price = self._to_float(original_price)

            # Если нет скидки, пропускаем
            if current_price >= original_price or current_price == 0:
                return None

            # URL товара
            product_url = (
                item.get("url") or
                item.get("pdpUrl") or
                item.get("link") or
                ""
            )
            if product_url and not product_url.startswith("http"):
                product_url = urljoin("https://direct.asda.com", product_url)

            # Изображение
            image_url = ""
            images = item.get("images") or item.get("image")
            if isinstance(images, list) and images:
                image_url = images[0].get("url") or images[0] if isinstance(images[0], str) else ""
            elif isinstance(images, dict):
                image_url = images.get("url") or images.get("src") or ""
            elif isinstance(images, str):
                image_url = images

            # Размеры
            sizes = []
            variants = item.get("variants") or item.get("sizes") or item.get("skus") or []
            for variant in variants:
                if isinstance(variant, dict):
                    in_stock = variant.get("inStock", True) or variant.get("available", True)
                    if in_stock:
                        size = variant.get("size") or variant.get("name") or variant.get("label") or ""
                        if size and size not in sizes:
                            sizes.append(str(size))
                elif isinstance(variant, str):
                    sizes.append(variant)

            # Описание
            description = (
                item.get("description") or
                item.get("shortDescription") or
                ""
            )
            if isinstance(description, list):
                description = " ".join(description)

            return Product(
                name=name,
                original_price=original_price,
                sale_price=current_price,
                currency="GBP",
                image_url=image_url,
                product_url=product_url,
                available_sizes=sizes,
                description=description[:200] if description else "",
                store=self.STORE_NAME,
            )

        except Exception as e:
            logger.warning(f"Failed to parse JSON product: {e}")
            return None

    def _parse_html_product(self, card, base_url: str) -> Optional[Product]:
        """Парсить товар из HTML карточки."""
        try:
            # Название
            name_elem = card.select_one(
                "[data-auto-id='product-tile-title'], "
                ".product-title, "
                ".product-name, "
                "h2, h3, "
                "[class*='title'], "
                "[class*='name']"
            )
            name = name_elem.get_text(strip=True) if name_elem else ""
            if not name:
                return None

            # Цены
            sale_price = 0
            original_price = 0

            # Текущая цена (со скидкой)
            sale_price_elem = card.select_one(
                "[data-auto-id='product-tile-price'], "
                ".sale-price, "
                ".now-price, "
                ".current-price, "
                "[class*='sale'], "
                "[class*='now']"
            )

            # Старая цена
            original_price_elem = card.select_one(
                ".was-price, "
                ".original-price, "
                ".rrp, "
                "[class*='was'], "
                "[class*='original'], "
                "s, strike, del"
            )

            if sale_price_elem:
                sale_price = self._parse_price(sale_price_elem.get_text())

            if original_price_elem:
                original_price = self._parse_price(original_price_elem.get_text())

            # Если нашли только одну цену, пробуем найти обе в общем блоке цен
            if sale_price == 0 or original_price == 0:
                price_container = card.select_one("[class*='price']")
                if price_container:
                    price_text = price_container.get_text()
                    prices = re.findall(r'£([\d.,]+)', price_text)
                    if len(prices) >= 2:
                        # Обычно первая - текущая, вторая - старая
                        sale_price = self._parse_price(prices[0])
                        original_price = self._parse_price(prices[1])
                        # Если перепутаны, меняем местами
                        if sale_price > original_price:
                            sale_price, original_price = original_price, sale_price
                    elif len(prices) == 1:
                        sale_price = self._parse_price(prices[0])

            # Если нет скидки или нет цены, пропускаем
            if sale_price == 0:
                return None
            if original_price == 0 or sale_price >= original_price:
                return None

            # URL товара
            link_elem = card.select_one("a[href*='/product/'], a[href*='productId']")
            if not link_elem:
                link_elem = card.select_one("a[href]")

            product_url = ""
            if link_elem:
                href = link_elem.get("href", "")
                product_url = urljoin(base_url, href)

            # Изображение
            img_elem = card.select_one("img")
            image_url = ""
            if img_elem:
                image_url = (
                    img_elem.get("src") or
                    img_elem.get("data-src") or
                    img_elem.get("data-lazy-src") or
                    ""
                )
                # Убираем placeholder изображения
                if "placeholder" in image_url.lower() or "loading" in image_url.lower():
                    image_url = img_elem.get("data-src") or ""

            return Product(
                name=name,
                original_price=original_price,
                sale_price=sale_price,
                currency="GBP",
                image_url=image_url,
                product_url=product_url,
                available_sizes=[],  # HTML парсинг обычно не даёт размеры на странице списка
                store=self.STORE_NAME,
            )

        except Exception as e:
            logger.warning(f"Failed to parse HTML product: {e}")
            return None

    def _to_float(self, value) -> float:
        """Преобразовать значение в float."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return self._parse_price(value)
        return 0.0
