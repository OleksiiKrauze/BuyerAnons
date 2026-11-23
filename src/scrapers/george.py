"""
George/ASDA scraper using Chrome CDP.

Uses Chrome DevTools Protocol to connect to a real Chrome browser,
which bypasses bot detection better than Playwright's Chromium.
"""
import asyncio
import subprocess
import os
from typing import Optional
from loguru import logger
from playwright.async_api import async_playwright, Browser

from .base import BaseScraper
from ..models import Product


class GeorgeScraper(BaseScraper):
    """Scraper for George/ASDA via Chrome CDP."""

    STORE_NAME = "George"
    DOMAINS = ["george.com"]
    BASE_URL = "https://direct.asda.com"
    CDP_PORT = 9223  # Different port from New Balance

    CHROME_PATHS = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"/usr/bin/google-chrome",
        r"/usr/bin/chromium-browser",
    ]

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Check if this scraper can handle the URL - specifically for George pages."""
        url_lower = url.lower()
        return "george.com" in url_lower or "/george/" in url_lower

    def __init__(self):
        super().__init__()
        self._chrome_process: Optional[subprocess.Popen] = None
        self._playwright = None
        self._browser: Optional[Browser] = None

    def _find_chrome(self) -> Optional[str]:
        """Find Chrome executable."""
        for path in self.CHROME_PATHS:
            if os.path.exists(path):
                return path
        return None

    async def _start_chrome(self):
        """Start Chrome with remote debugging using isolated profile."""
        chrome_path = self._find_chrome()
        if not chrome_path:
            logger.error("Chrome not found. Please install Google Chrome.")
            return False

        # Use a completely isolated profile directory for scraping
        profile_dir = r"C:\temp\chrome_george_bot"

        # Ensure directory exists
        os.makedirs(profile_dir, exist_ok=True)

        logger.info(f"Starting Chrome for George on port {self.CDP_PORT}...")
        self._chrome_process = subprocess.Popen([
            chrome_path,
            f"--remote-debugging-port={self.CDP_PORT}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            "--disable-sync",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-client-side-phishing-detection",
            "--profile-directory=Default",
            "about:blank"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        await asyncio.sleep(3)
        return True

    async def _get_browser(self):
        """Get fresh browser connection via CDP."""
        # Always clean up old connection first
        await self._cleanup_browser()

        # Start Chrome and connect
        if not await self._start_chrome():
            return None

        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(
                f"http://localhost:{self.CDP_PORT}"
            )
            logger.info("Connected to Chrome via CDP for George")
        except Exception as e:
            logger.error(f"Failed to connect to Chrome CDP: {e}")
            return None

        return self._browser

    async def _cleanup_browser(self):
        """Clean up browser connection."""
        if self._browser:
            try:
                await self._browser.close()
            except:
                pass
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except:
                pass
            self._playwright = None

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
            browser = await self._get_browser()
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

                            if (priceContainer) {
                                const text = priceContainer.textContent;
                                const prices = text.match(/[\u00a3$]([\d.]+)/g) || [];
                                if (prices.length >= 2) {
                                    nowPrice = parseFloat(prices[0].replace(/[\u00a3$]/g, ''));
                                    wasPrice = parseFloat(prices[1].replace(/[\u00a3$]/g, ''));
                                } else if (prices.length === 1) {
                                    nowPrice = parseFloat(prices[0].replace(/[\u00a3$]/g, ''));
                                    wasPrice = nowPrice;
                                }
                            }

                            const img = card.querySelector('img');
                            const image = img?.src || img?.getAttribute('data-src') || '';
                            const link = card.querySelector('a')?.href || '';

                            if (name && nowPrice > 0) {
                                results.push({
                                    name,
                                    nowPrice,
                                    wasPrice: wasPrice || nowPrice,
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

            # Convert to Product objects
            for raw in raw_products:
                if raw.get("nowPrice", 0) > 0:
                    product_url = raw.get("link", "")
                    if product_url and not product_url.startswith("http"):
                        product_url = f"{self.BASE_URL}{product_url}"

                    image_url = raw.get("image", "")

                    product = Product(
                        name=raw.get("name", "George Item"),
                        original_price=float(raw.get("wasPrice", 0)),
                        sale_price=float(raw.get("nowPrice", 0)),
                        currency="GBP",
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
        await self._cleanup_browser()

        if self._chrome_process:
            try:
                self._chrome_process.terminate()
            except:
                pass
            self._chrome_process = None
