"""
ASDA/George scraper using Algolia API + browser for prices.
Algolia provides fast product search, browser extracts actual prices with discounts.
"""
import httpx
import re
import json
from typing import Optional
from loguru import logger

from .base import BaseScraper
from .browser import browser_manager
from ..models import Product


class AsdaApiScraper(BaseScraper):
    """Скрапер ASDA через Algolia API + browser для цен."""

    STORE_NAME = "ASDA"
    DOMAINS = ["direct.asda.com", "asda.com", "george.com"]

    # Algolia credentials (public, read-only)
    ALGOLIA_APP_ID = "1KBYJ8SZ65"
    ALGOLIA_API_KEY = "fea321f42e897ee5331d030d1ca9c464"
    ALGOLIA_INDEX = "asda_prod__products__default"

    # Category codes for sale sections
    SALE_CATEGORY = "D55"  # Sale & Offers category

    def __init__(self):
        super().__init__()
        self._client = httpx.AsyncClient(timeout=30)

    async def scrape(
        self,
        url: str,
        sizes: Optional[list[str]] = None,
        top_count: int = 10,
        min_discount: int = 0,
    ) -> list[Product]:
        """
        Получить товары со скидками.

        Стратегия:
        1. Пробуем получить товары через браузер (имеют реальные цены)
        2. Если не получается - используем Algolia (только current_price)

        Args:
            url: URL категории
            sizes: Фильтр по размерам
            top_count: Количество товаров
            min_discount: Минимальная скидка в %
        """
        logger.info(f"Scraping {self.STORE_NAME}: {url}")

        # Сначала пробуем через браузер - там есть цены со скидками
        products = await self._scrape_via_browser(url)

        if not products:
            logger.warning("Browser scraping failed, falling back to Algolia")
            # Fallback на Algolia (без скидок)
            facet_filters = self._parse_category_from_url(url)
            products = await self._search_algolia(
                facet_filters=facet_filters if facet_filters else None,
                hits_per_page=100,
            )

        logger.info(f"Got {len(products)} products total")

        # Фильтруем только товары со скидкой
        if min_discount > 0:
            products = [p for p in products if p.discount_percent >= min_discount]
            logger.info(f"After discount filter ({min_discount}%): {len(products)} products")

        # Фильтруем по размерам
        if sizes:
            products = [p for p in products if p.has_size(sizes)]
            logger.info(f"After size filter: {len(products)} products")

        # Сортируем по скидке
        products.sort(key=lambda p: p.discount_percent, reverse=True)

        return products[:top_count]

    async def _scrape_via_browser(self, url: str) -> list[Product]:
        """Скрапинг через браузер для получения реальных цен."""
        try:
            html = await browser_manager.fetch_page(
                url,
                wait_selector=".product-card, .product-tile, [data-product-id]",
                timeout=45000,
            )

            # Пробуем извлечь JSON данные из страницы
            products = self._extract_products_from_html(html)

            if products:
                logger.info(f"Extracted {len(products)} products from browser HTML")
                return products

        except Exception as e:
            logger.error(f"Browser scraping failed: {e}")

        return []

    def _extract_products_from_html(self, html: str) -> list[Product]:
        """Извлечь товары из HTML страницы."""
        products = []

        # Ищем JSON данные в script тегах (часто содержат product data)
        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
            r'window\.dataLayer\s*=\s*(\[.+?\]);',
            r'"products"\s*:\s*(\[.+?\])',
            r'<script type="application/ld\+json">(.+?)</script>',
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    extracted = self._parse_json_products(data)
                    if extracted:
                        products.extend(extracted)
                except json.JSONDecodeError:
                    continue

        # Если JSON не найден, парсим HTML напрямую
        if not products:
            products = self._parse_html_products(html)

        return products

    def _parse_json_products(self, data: dict | list) -> list[Product]:
        """Парсинг товаров из JSON данных."""
        products = []

        # Обработка разных структур JSON
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    product = self._try_parse_product_dict(item)
                    if product:
                        products.append(product)
        elif isinstance(data, dict):
            # Ищем массив товаров в разных местах
            for key in ['products', 'items', 'hits', 'results']:
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        product = self._try_parse_product_dict(item)
                        if product:
                            products.append(product)

        return products

    def _try_parse_product_dict(self, item: dict) -> Optional[Product]:
        """Попытка распарсить словарь как товар."""
        # Ищем название
        name = item.get('name') or item.get('title') or item.get('productName')
        if not name:
            return None

        # Ищем цены
        current_price = (
            item.get('current_price') or
            item.get('price') or
            item.get('salePrice') or
            item.get('now_price')
        )
        was_price = (
            item.get('was_price') or
            item.get('originalPrice') or
            item.get('wasPrice') or
            item.get('rrp')
        )

        if not current_price:
            return None

        try:
            current_price = float(str(current_price).replace('£', '').replace(',', ''))
            if was_price:
                was_price = float(str(was_price).replace('£', '').replace(',', ''))
            else:
                was_price = current_price
        except (ValueError, TypeError):
            return None

        # URL и изображение
        product_url = item.get('url') or item.get('productUrl') or ''
        if product_url and not product_url.startswith('http'):
            product_url = f"https://direct.asda.com{product_url}"

        image_url = item.get('image_url') or item.get('imageUrl') or item.get('primary_image') or ''
        if image_url and not image_url.startswith('http'):
            if image_url.startswith('//'):
                image_url = f"https:{image_url}"
            else:
                image_url = f"https://asda.scene7.com/is/image/Asda/{image_url}"

        # Размеры
        sizes = item.get('bucket_size') or item.get('sizes') or item.get('availableSizes') or []
        if isinstance(sizes, str):
            sizes = [sizes]

        return Product(
            name=name,
            original_price=was_price,
            sale_price=current_price,
            currency="GBP",
            image_url=image_url,
            product_url=product_url,
            available_sizes=sizes,
            description=item.get('description', '')[:200],
            store=self.STORE_NAME,
            category=item.get('product_type') or item.get('category') or '',
        )

    def _parse_html_products(self, html: str) -> list[Product]:
        """Парсинг товаров из HTML разметки (fallback)."""
        products = []

        # Ищем product cards с ценами
        # Паттерн для поиска цен: £XX.XX
        price_pattern = r'£(\d+(?:\.\d{2})?)'

        # Упрощённый парсинг - ищем блоки с ценами
        # Это fallback если JSON не доступен
        # Более точный парсинг требует BeautifulSoup

        return products

    def _parse_category_from_url(self, url: str) -> list[list[str]]:
        """Извлечь фильтры категории из URL для facetFilters."""
        url_lower = url.lower()

        facet_filters = []

        # Определяем пол (используем правильные значения из Algolia)
        if '/women/' in url_lower or '/womens/' in url_lower:
            facet_filters.append(['gender:Womens'])
        elif '/men/' in url_lower or '/mens/' in url_lower:
            facet_filters.append(['gender:Mens'])
        elif '/kids/' in url_lower:
            facet_filters.append(['gender:Kids'])
        elif '/girls/' in url_lower:
            facet_filters.append(['genderCategory:Girls'])
        elif '/boys/' in url_lower:
            facet_filters.append(['genderCategory:Boys'])
        elif '/baby/' in url_lower:
            facet_filters.append(['gender:Baby'])

        # Определяем тип товара
        product_type_map = {
            '/dresses/': 'Dresses',
            '/tops/': 'Tops & T-Shirts',
            '/t-shirts/': 'Tops & T-Shirts',
            '/shoes/': 'Footwear',
            '/footwear/': 'Footwear',
            '/jeans/': 'Jeans',
            '/trousers/': 'Trousers',
            '/coats/': 'Coats',
            '/jackets/': 'Jackets',
            '/nightwear/': 'Pyjamas',
            '/pyjamas/': 'Pyjamas',
            '/swimwear/': 'Swimsuits',
            '/lingerie/': 'Bras',
            '/underwear/': 'Underwear',
            '/jumpers/': 'Jumpers',
            '/cardigans/': 'Cardigans',
            '/shirts/': 'Shirts',
            '/blouses/': 'Blouses',
            '/skirts/': 'Skirts',
            '/shorts/': 'Shorts',
        }

        for pattern, product_type in product_type_map.items():
            if pattern in url_lower:
                facet_filters.append([f'product_type:{product_type}'])
                break

        return facet_filters

    async def _search_algolia(
        self,
        query: str = "",
        facet_filters: list[list[str]] | None = None,
        hits_per_page: int = 50,
    ) -> list[Product]:
        """Выполнить поиск через Algolia API."""
        url = f"https://{self.ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{self.ALGOLIA_INDEX}/query"

        headers = {
            "X-Algolia-Application-Id": self.ALGOLIA_APP_ID,
            "X-Algolia-API-Key": self.ALGOLIA_API_KEY,
            "Content-Type": "application/json",
        }

        # Параметры поиска
        params = {
            "query": query,
            "hitsPerPage": hits_per_page,
            "attributesToRetrieve": [
                "name", "url", "primary_image", "current_price", "was_price",
                "bucket_size", "description", "brand", "product_type", "gender",
                "genderCategory", "colour", "style"
            ],
        }

        if facet_filters:
            params["facetFilters"] = facet_filters

        try:
            response = await self._client.post(url, headers=headers, json=params)
            response.raise_for_status()
            data = response.json()

            products = []
            for hit in data.get("hits", []):
                product = self._parse_hit(hit)
                if product:
                    products.append(product)

            return products

        except Exception as e:
            logger.error(f"Algolia search failed: {e}")
            return []

    def _parse_hit(self, hit: dict) -> Optional[Product]:
        """Преобразовать Algolia hit в Product."""
        try:
            name = hit.get("name", "")
            if not name:
                return None

            current_price = hit.get("current_price", 0)
            was_price = hit.get("was_price")  # May be None in Algolia

            if not current_price:
                return None

            # URL товара
            product_url = hit.get("url", "")
            if product_url and not product_url.startswith("http"):
                product_url = f"https://direct.asda.com{product_url}"

            # Изображение - используем primary_image для построения URL
            image_id = hit.get("primary_image") or hit.get("image_url", "")
            if image_id and not image_id.startswith("http"):
                if image_id.startswith("//"):
                    image_url = f"https:{image_id}"
                else:
                    image_url = f"https://asda.scene7.com/is/image/Asda/{image_id}"
            else:
                image_url = image_id

            # Размеры
            sizes = hit.get("bucket_size", [])
            if isinstance(sizes, str):
                sizes = [sizes]

            # Если нет was_price, используем current_price (без скидки)
            original = float(was_price) if was_price else float(current_price)
            sale = float(current_price)

            return Product(
                name=name,
                original_price=original,
                sale_price=sale,
                currency="GBP",
                image_url=image_url,
                product_url=product_url,
                available_sizes=sizes,
                description=hit.get("description", "")[:200] if hit.get("description") else "",
                store=self.STORE_NAME,
                category=hit.get("product_type", ""),
            )

        except Exception as e:
            logger.warning(f"Failed to parse hit: {e}")
            return None

    async def parse_products(self, html: str, base_url: str) -> list[Product]:
        """Не используется для API скрапера."""
        return []
