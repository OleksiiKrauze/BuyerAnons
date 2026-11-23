"""
Zara scraper using their JSON API.
Zara pages with ?ajax=true return JSON with product data.
"""
import httpx
from typing import Optional
from loguru import logger

from .base import BaseScraper
from ..models import Product


class ZaraScraper(BaseScraper):
    """Скрапер Zara через JSON API."""

    STORE_NAME = "Zara"
    DOMAINS = ["zara.com"]

    # Zara uses country/language prefixes
    DEFAULT_REGION = "uk/en"

    # Known category IDs for different sections
    CATEGORY_MAP = {
        "woman-new": "woman/new-in-l1180",
        "woman-sale": "woman-sale-l1314",
        "woman-special-prices": "woman-special-prices-l1410",
        "woman-best-sellers": "woman-best-sellers-l1299",
        "man-new": "man/new-in-l715",
        "man-sale": "man-sale-l1312",
        "kids-new": "kids/new-in-l412",
    }

    def __init__(self):
        super().__init__()
        self._currency = "GBP"  # будет переопределено в scrape()
        self._client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,  # Follow standard redirects (301, 302)
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-GB,en;q=0.9",
            }
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
        """
        Получить товары из Zara.

        Args:
            url: URL категории или ключевое слово (woman-new, woman-sale)
            sizes: Фильтр по размерам (S, M, L, XL, 36, 38, 40, etc.)
            top_count: Количество товаров
            min_discount: Минимальная скидка в %
            sort_mode: Режим сортировки:
                - "discount" - по скидке (макс → мин)
                - "price" - по цене (мин → макс)
                - "value" - цена до max_price + сортировка по скидке
            max_price: Максимальная цена для режима "value"
        """
        logger.info(f"Scraping {self.STORE_NAME}: {url}")

        # Определяем валюту по URL
        from ..utils.helpers import detect_currency
        self._currency = detect_currency(url)
        logger.debug(f"Detected currency: {self._currency}")

        # Конвертируем URL или ключевое слово в API endpoint
        api_url = self._build_api_url(url)
        logger.debug(f"API URL: {api_url}")

        # Получаем данные
        products = await self._fetch_products(api_url)
        logger.info(f"Got {len(products)} products total")

        # Фильтруем по минимальной скидке
        if min_discount > 0:
            products = [p for p in products if p.discount_percent >= min_discount]
            logger.info(f"After discount filter ({min_discount}%): {len(products)} products")

        # Фильтруем по размерам
        if sizes:
            products = [p for p in products if p.has_size(sizes)]
            logger.info(f"After size filter: {len(products)} products")

        # Фильтруем и сортируем в зависимости от режима
        if sort_mode == "price":
            # Сортировка по цене (от дешёвых к дорогим)
            products.sort(key=lambda p: p.sale_price)
            logger.info("Sorted by price (lowest first)")
        elif sort_mode == "value" and max_price:
            # Фильтр по максимальной цене + сортировка по скидке
            products = [p for p in products if p.sale_price <= max_price]
            products.sort(key=lambda p: p.discount_percent, reverse=True)
            logger.info(f"Filtered by max price {max_price}, sorted by discount: {len(products)} products")
        else:
            # По умолчанию - сортировка по скидке
            products.sort(key=lambda p: p.discount_percent, reverse=True)
            logger.info("Sorted by discount (highest first)")

        return products[:top_count]

    def _extract_region_from_url(self, url: str) -> str:
        """Extract region (country/language) from Zara URL."""
        import re
        # Pattern: zara.com/XX/YY/ where XX is country, YY is language
        match = re.search(r'zara\.com/([a-z]{2})/([a-z]{2})/', url.lower())
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        return self.DEFAULT_REGION

    def _build_api_url(self, url: str) -> str:
        """Построить API URL из обычного URL или ключевого слова."""
        url_lower = url.lower().strip()

        # Если это ключевое слово из нашей карты
        if url_lower in self.CATEGORY_MAP:
            category = self.CATEGORY_MAP[url_lower]
            return f"https://www.zara.com/{self.DEFAULT_REGION}/{category}.html?ajax=true"

        # Если это уже URL zara.com
        if "zara.com" in url_lower:
            # Добавляем ?ajax=true если его нет
            if "ajax=true" not in url:
                separator = "&" if "?" in url else "?"
                return f"{url}{separator}ajax=true"
            return url

        # По умолчанию - женские новинки
        category = self.CATEGORY_MAP.get("woman-new", "woman/new-in-l1180")
        return f"https://www.zara.com/{self.DEFAULT_REGION}/{category}.html?ajax=true"

    async def _fetch_products(self, api_url: str, max_redirects: int = 3) -> list[Product]:
        """Получить товары по API URL с обработкой 278 редиректов."""
        products = []
        current_url = api_url
        redirects = 0

        while redirects < max_redirects:
            try:
                response = await self._client.get(current_url)
                logger.debug(f"Response status: {response.status_code}, final URL: {response.url}")

                # Zara использует 278 как кастомный редирект (не следуется автоматически)
                if response.status_code == 278:
                    redirect_url = response.headers.get("Location")
                    if redirect_url:
                        logger.debug(f"Following 278 redirect to: {redirect_url}")
                        if not redirect_url.startswith("http"):
                            from urllib.parse import urljoin
                            redirect_url = urljoin(str(response.url), redirect_url)
                        if "ajax=true" not in redirect_url:
                            redirect_url += "&ajax=true" if "?" in redirect_url else "?ajax=true"
                        current_url = redirect_url
                        redirects += 1
                        continue
                    else:
                        # Try to get redirect URL from response body
                        try:
                            data = response.json()
                            redirect_url = data.get("redirect") or data.get("location") or data.get("url")
                            if redirect_url:
                                logger.debug(f"Found redirect in body: {redirect_url}")
                                if not redirect_url.startswith("http"):
                                    redirect_url = f"https://www.zara.com{redirect_url}"
                                if "ajax=true" not in redirect_url:
                                    redirect_url += "&ajax=true" if "?" in redirect_url else "?ajax=true"
                                current_url = redirect_url
                                redirects += 1
                                continue
                        except Exception:
                            pass
                        logger.warning("278 redirect without Location header or body redirect")
                        break

                if response.status_code != 200:
                    logger.warning(f"Unexpected status {response.status_code} for {current_url}")
                    break

                # Check content type
                content_type = response.headers.get("content-type", "")
                if "application/json" not in content_type and "text/json" not in content_type:
                    logger.warning(f"Unexpected content type: {content_type}")
                    # Try parsing anyway in case it's still JSON
                    try:
                        data = response.json()
                    except Exception:
                        logger.error("Response is not JSON")
                        break
                else:
                    data = response.json()

                products = self._parse_response(data)
                break

            except Exception as e:
                logger.error(f"Failed to fetch {current_url}: {e}")
                break

        return products

    def _parse_response(self, data: dict) -> list[Product]:
        """Парсить JSON ответ Zara."""
        products = []

        # Основная структура: productGroups -> elements -> commercialComponents
        product_groups = data.get("productGroups", [])

        for group in product_groups:
            elements = group.get("elements", [])

            for element in elements:
                components = element.get("commercialComponents", [])

                for comp in components:
                    product = self._parse_component(comp)
                    if product:
                        products.append(product)

        # Также проверяем альтернативные структуры (для поиска)
        if not products and "categories" in data:
            for category in data.get("categories", []):
                for group in category.get("productGroups", []):
                    for element in group.get("elements", []):
                        for comp in element.get("commercialComponents", []):
                            product = self._parse_component(comp)
                            if product:
                                products.append(product)

        return products

    def _parse_component(self, comp: dict) -> Optional[Product]:
        """Парсить commercialComponent в Product."""
        try:
            name = comp.get("name", "")
            if not name:
                return None

            product_id = comp.get("id", "")

            # Цены - проверяем несколько мест
            # 1. Прямо в component (в cents/pence)
            price_pence = comp.get("price")
            old_price_pence = comp.get("oldPrice")  # Старая цена для товаров со скидкой

            # 2. В detail.colors[0].price (более детальная информация)
            detail = comp.get("detail", {})
            colors = detail.get("colors", [])

            current_price = 0.0
            original_price = 0.0
            available_sizes = []
            image_url = ""
            color_name = ""

            if colors:
                color = colors[0]
                color_name = color.get("name", "")

                # Цена из color
                color_price = color.get("price")
                if isinstance(color_price, dict):
                    # Структурированная цена с original/current
                    current_price = color_price.get("current", 0) / 100
                    original_price = color_price.get("original", color_price.get("current", 0)) / 100
                elif isinstance(color_price, (int, float)):
                    current_price = color_price / 100
                    original_price = current_price

                # Размеры из availability
                availability = color.get("availability", "")
                if availability == "in_stock":
                    # Нужно отдельно получить размеры через API
                    pass

                # Размеры из sizes если есть
                sizes_data = color.get("sizes", [])
                if sizes_data:
                    for size in sizes_data:
                        if isinstance(size, dict):
                            size_name = size.get("name", size.get("value", ""))
                            if size.get("availability") != "out_of_stock" and size_name:
                                available_sizes.append(size_name)
                        elif isinstance(size, str):
                            available_sizes.append(size)

                # Изображение
                xmedia = color.get("xmedia", [])
                if xmedia:
                    # Берём первое изображение
                    media = xmedia[0]
                    path = media.get("path", "")
                    media_name = media.get("name", "")
                    timestamp = media.get("timestamp", "")
                    if path and media_name:
                        # Zara image URL format
                        image_url = f"https://static.zara.net/photos/{path}/{media_name}.jpg?ts={timestamp}"

            # Если цена не найдена в colors, берём из корня
            if current_price == 0 and price_pence:
                current_price = price_pence / 100
                original_price = current_price

            # Проверяем oldPrice из корня (для товаров со скидкой)
            if old_price_pence and old_price_pence > 0:
                original_price = old_price_pence / 100

            if current_price == 0:
                return None

            # URL товара
            seo = comp.get("seo", {})
            keyword = seo.get("keyword", "")
            seo_product_id = seo.get("seoProductId", "")

            if keyword and seo_product_id:
                product_url = f"https://www.zara.com/{self.DEFAULT_REGION}/{keyword}-p{seo_product_id}.html"
            else:
                product_url = f"https://www.zara.com/{self.DEFAULT_REGION}/product/{product_id}"

            # Если нет изображения в colors, берём из xmedia в корне
            if not image_url:
                xmedia = comp.get("xmedia", [])
                if xmedia:
                    media = xmedia[0]
                    path = media.get("path", "")
                    media_name = media.get("name", "")
                    timestamp = media.get("timestamp", "")
                    if path and media_name:
                        image_url = f"https://static.zara.net/photos/{path}/{media_name}.jpg?ts={timestamp}"

            # Описание
            description = comp.get("description", "")
            if not description:
                # Собираем описание из других полей
                family = comp.get("familyName", "")
                subfamily = comp.get("subfamilyName", "")
                if family or subfamily:
                    description = f"{family} {subfamily}".strip()

            return Product(
                name=name,
                original_price=original_price,
                sale_price=current_price,
                currency=self._currency,
                image_url=image_url,
                product_url=product_url,
                available_sizes=available_sizes,
                description=description,
                store=self.STORE_NAME,
                category=comp.get("sectionName", ""),
            )

        except Exception as e:
            logger.warning(f"Failed to parse Zara component: {e}")
            return None

    async def parse_products(self, html: str, base_url: str) -> list[Product]:
        """Не используется - Zara использует API."""
        return []

    async def search(self, query: str, limit: int = 50) -> list[Product]:
        """Поиск товаров по запросу."""
        search_url = f"https://www.zara.com/{self.DEFAULT_REGION}/search?searchTerm={query}&ajax=true"
        return await self._fetch_products(search_url)

    async def close(self):
        """Закрыть HTTP клиент."""
        await self._client.aclose()
