"""
Joe's New Balance Outlet scraper using Chrome CDP.

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


class NewBalanceScraper(BaseScraper):
    """Scraper for Joe's New Balance Outlet via Chrome CDP."""

    STORE_NAME = "Joe's New Balance"
    DOMAINS = ["joesnewbalanceoutlet.com", "newbalance.com"]
    BASE_URL = "https://www.joesnewbalanceoutlet.com"
    CDP_PORT = 9222

    CHROME_PATHS = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"/usr/bin/google-chrome",
        r"/usr/bin/chromium-browser",
    ]

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
        profile_dir = r"C:\temp\chrome_nb_bot"

        # Ensure directory exists
        os.makedirs(profile_dir, exist_ok=True)

        logger.info(f"Starting Chrome with CDP on port {self.CDP_PORT}...")
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
            logger.info("Connected to Chrome via CDP")
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
        """Scrape products from Joe's New Balance Outlet."""
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

            # Always create new context and page for clean state
            context = await browser.new_context()
            page = await context.new_page()

            logger.debug(f"Loading {url}")
            await page.goto(url, wait_until="load", timeout=60000)

            # Wait for products to load
            await asyncio.sleep(5)

            # Wait for price elements to appear
            try:
                await page.wait_for_selector('[data-style-price]', timeout=10000)
            except:
                logger.warning("Price elements not found immediately, continuing...")

            # Check if blocked
            content = await page.content()
            if "Oops" in content and "Something went wrong" in content:
                logger.error("Site blocked the request")
                return []

            # Scroll to load more products
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(0.5)

            # Extract products
            raw_products = await page.evaluate('''
                () => {
                    const products = [];
                    const seen = new Set();
                    const priceElements = document.querySelectorAll('[data-style-price]');

                    priceElements.forEach(el => {
                        try {
                            const priceData = JSON.parse(el.getAttribute('data-style-price'));
                            const style = el.getAttribute('data-style') || '';
                            const href = el.getAttribute('href') || '';

                            const key = style + priceData.sales?.value;
                            if (seen.has(key)) return;
                            seen.add(key);

                            let parent = el.closest('[class*="getproduct"]') ||
                                        el.closest('.product-tile') ||
                                        el.closest('[class*="product"]');

                            let name = '';
                            let image = '';
                            let description = '';

                            if (parent) {
                                const nameEl = parent.querySelector('h3, h4, h5, h6, .product-name, [class*="product-name"], .title');
                                if (nameEl) name = nameEl.textContent.trim();

                                const imgEl = parent.querySelector('img[data-large-src], img[data-src], img.product-image');
                                if (imgEl) {
                                    image = imgEl.getAttribute('data-large-src') ||
                                           imgEl.getAttribute('data-src') || imgEl.src || '';
                                }

                                const colorEl = parent.querySelector('[data-colors]');
                                if (colorEl) description = colorEl.getAttribute('data-colors') || '';
                            }

                            if (!name && style) name = style;

                            products.push({
                                style: style,
                                name: name,
                                url: href,
                                image: image,
                                description: description,
                                sale_price: priceData.sales?.value || 0,
                                original_price: priceData.list?.value || priceData.sales?.value || 0,
                                discount: parseInt(priceData.list?.percentage || '0'),
                                currency: priceData.sales?.currency || 'USD',
                            });
                        } catch (e) {}
                    });
                    return products;
                }
            ''')

            logger.info(f"Extracted {len(raw_products)} raw products")

            # Close context to free resources
            await context.close()

            # Convert to Product objects
            for raw in raw_products:
                if raw.get("sale_price", 0) > 0:
                    product_url = raw.get("url", "")
                    if product_url and not product_url.startswith("http"):
                        product_url = f"{self.BASE_URL}{product_url}"

                    image_url = raw.get("image", "").replace("&amp;", "&")

                    name = raw.get("name", "")
                    style = raw.get("style", "")
                    if not name:
                        name = f"New Balance {style}" if style else "New Balance Shoe"
                    elif style and style not in name:
                        name = f"{name} ({style})"

                    product = Product(
                        name=name,
                        original_price=float(raw.get("original_price", 0)),
                        sale_price=float(raw.get("sale_price", 0)),
                        currency="USD",
                        image_url=image_url,
                        product_url=product_url,
                        available_sizes=[],
                        description=raw.get("description", ""),
                        store=self.STORE_NAME,
                        category="Shoes",
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
