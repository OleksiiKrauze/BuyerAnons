"""
George/ASDA scraper using Chrome CDP.

Uses Chrome DevTools Protocol to connect to a real Chrome browser,
which bypasses bot detection better than Playwright's Chromium.
"""
import asyncio
from typing import Optional
from urllib.parse import urlparse
from loguru import logger

from .base import BaseScraper
from .chrome_cdp import ChromeCDP
from ..models import Product


class GeorgeScraper(BaseScraper):
    """Scraper for George/ASDA via Chrome CDP."""

    STORE_NAME = "George"
    DOMAINS = ["george.com"]
    BASE_URL = "https://direct.asda.com"
    CDP_PORT = 9223  # Different port from New Balance

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Check if this scraper can handle the URL - specifically for George pages."""
        url_lower = url.lower()
        return "george.com" in url_lower or "/george/" in url_lower

    def __init__(self):
        super().__init__()
        self._chrome = ChromeCDP("george", self.CDP_PORT)

    async def scrape(
        self,
        url: str,
        sizes: Optional[list[str]] = None,
        top_count: int = 10,
        min_discount: int = 0,
        sort_mode: str = "discount",
        max_price: Optional[float] = None,
    ) -> list[Product]:
        """Scrape products from George/ASDA."""
        logger.info(f"Scraping {self.STORE_NAME}: {url}")

        if not url.startswith("http"):
            url = f"{self.BASE_URL}{url}"

        products = await self._fetch_products(url)
        logger.info(f"Got {len(products)} products total")

        # Filter by minimum discount
        if min_discount > 0:
            products = [p for p in products if p.discount_percent >= min_discount]
            logger.info(f"After discount filter ({min_discount}%): {len(products)} products")

        # Filter by sizes
        if sizes:
            products = [p for p in products if p.has_size(sizes)]
            logger.info(f"After size filter: {len(products)} products")

        # Sort based on mode
        if sort_mode == "price":
            products.sort(key=lambda p: p.sale_price)
            logger.info("Sorted by price (lowest first)")
        elif sort_mode == "value" and max_price:
            products = [p for p in products if p.sale_price <= max_price]
            products.sort(key=lambda p: p.discount_percent, reverse=True)
            logger.info(f"Filtered by max price {max_price}, sorted by discount")
        else:
            products.sort(key=lambda p: p.discount_percent, reverse=True)
            logger.info("Sorted by discount (highest first)")

        return products[:top_count]

    async def _fetch_products(self, url: str) -> list[Product]:
        """Fetch products from page using Chrome CDP."""
        products = []

        try:
            browser = await self._chrome.get_browser()
            if not browser:
                logger.error("Could not get browser. Is Chrome installed?")
                return []

            context = await browser.new_context()
            page = await context.new_page()

            logger.debug(f"Loading {url}")
            await page.goto(url, wait_until="load", timeout=60000)

            # Wait for page to load
            await asyncio.sleep(10)

            # Scroll to load more products
            for _ in range(8):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)

            await asyncio.sleep(3)

            # Extract products
            raw_products = await page.evaluate(r'''
                () => {
                    const results = [];
                    const seen = new Set();
                    const productCards = document.querySelectorAll('.product-mini, .product-card, .product-tile, [class*="productCard"]');

                    productCards.forEach(card => {
                        try {
                            const nameEl = card.querySelector('.product-mini-link, .product-name, h3, h4, [class*="name"]');
                            const name = nameEl?.textContent?.trim() || '';

                            if (!name || seen.has(name)) return;
                            seen.add(name);

                            const priceContainer = card.querySelector('[class*="price"], .mini-product-info');
                            let nowPrice = 0;
                            let wasPrice = 0;
                            let currency = '';

                            if (priceContainer) {
                                const text = priceContainer.textContent;
                                // \u00a3 \u2014 \u0431\u0440\u0438\u0442\u0430\u043d\u0441\u043a\u0430\u044f \u0432\u0435\u0440\u0441\u0438\u044f, \u20ac \u2014 \u043c\u0435\u0436\u0434\u0443\u043d\u0430\u0440\u043e\u0434\u043d\u0430\u044f (global.direct.asda.com)
                                const prices = [...text.matchAll(/([\u00a3$\u20ac])\s?(\d+(?:[.,]\d{1,2})?)/g)];
                                const num = m => parseFloat(m[2].replace(',', '.'));
                                if (prices.length >= 2) {
                                    nowPrice = num(prices[0]);
                                    wasPrice = num(prices[1]);
                                } else if (prices.length === 1) {
                                    nowPrice = num(prices[0]);
                                    wasPrice = nowPrice;
                                }
                                if (prices.length) currency = prices[0][1];
                            }

                            const img = card.querySelector('img');
                            const image = img?.src || img?.getAttribute('data-src') || '';
                            const link = card.querySelector('a')?.href || '';

                            if (name && nowPrice > 0) {
                                results.push({
                                    name,
                                    nowPrice,
                                    wasPrice: wasPrice || nowPrice,
                                    currency,
                                    image,
                                    link
                                });
                            }
                        } catch(e) {}
                    });
                    return results;
                }
            ''')

            logger.info(f"Extracted {len(raw_products)} raw products")

            await context.close()

            # Относительные ссылки — от домена страницы (британская или международная версия)
            site_url = f"https://{urlparse(url).netloc}" if urlparse(url).netloc else self.BASE_URL

            # Convert to Product objects
            for raw in raw_products:
                if raw.get("nowPrice", 0) > 0:
                    product_url = raw.get("link", "")
                    if product_url and not product_url.startswith("http"):
                        product_url = f"{site_url}{product_url}"

                    image_url = raw.get("image", "")

                    product = Product(
                        name=raw.get("name", "George Item"),
                        original_price=float(raw.get("wasPrice", 0)),
                        sale_price=float(raw.get("nowPrice", 0)),
                        currency={"€": "EUR", "$": "USD"}.get(raw.get("currency"), "GBP"),
                        image_url=image_url,
                        product_url=product_url,
                        available_sizes=[],
                        description="",
                        store=self.STORE_NAME,
                        category="",
                    )
                    products.append(product)

        except Exception as e:
            logger.error(f"Failed to fetch products: {e}")
            import traceback
            traceback.print_exc()

        return products

    async def parse_products(self, html: str, base_url: str) -> list[Product]:
        """Not used - we use CDP for scraping."""
        return []

    async def close(self):
        """Close browser and Chrome process."""
        await self._chrome.stop()
