from playwright.async_api import async_playwright, Browser, Page, Playwright
from playwright_stealth import stealth_async
from contextlib import asynccontextmanager
from loguru import logger
from typing import Optional
import asyncio


class BrowserManager:
    """Менеджер браузера Playwright."""

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    async def start(self) -> None:
        """Запустить браузер."""
        if self._browser:
            return

        logger.info("Starting Playwright browser...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
            ]
        )
        logger.info("Browser started successfully")

    async def stop(self) -> None:
        """Остановить браузер."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser stopped")

    @asynccontextmanager
    async def new_page(self):
        """Создать новую страницу."""
        if not self._browser:
            await self.start()

        page = await self._browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )

        # Применяем stealth режим для обхода детекции
        await stealth_async(page)

        try:
            yield page
        finally:
            await page.close()

    async def fetch_page(
        self,
        url: str,
        wait_selector: Optional[str] = None,
        timeout: int = 30000,
    ) -> str:
        """
        Загрузить страницу и вернуть HTML.

        Args:
            url: URL страницы
            wait_selector: CSS селектор для ожидания
            timeout: Таймаут в мс

        Returns:
            HTML содержимое страницы
        """
        async with self.new_page() as page:
            logger.info(f"Fetching: {url}")

            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

            # Обработка cookie consent popup
            await self._handle_cookie_consent(page)

            # Ждём загрузки динамического контента
            await asyncio.sleep(3)

            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=timeout)
                except Exception as e:
                    logger.warning(f"Selector {wait_selector} not found: {e}")

            # Прокрутка для загрузки lazy-load контента
            await self._scroll_page(page)

            # Ждём ещё немного после прокрутки
            await asyncio.sleep(2)

            html = await page.content()
            logger.info(f"Page loaded: {len(html)} bytes")

            return html

    async def _handle_cookie_consent(self, page: Page) -> None:
        """Обработать cookie consent popup."""
        # Список селекторов для кнопок согласия
        consent_selectors = [
            # ASDA/George
            'button:has-text("I Accept")',
            'button:has-text("Accept All")',
            'button:has-text("Accept")',
            '#onetrust-accept-btn-handler',
            '.onetrust-accept-btn-handler',
            '[data-testid="accept-cookies"]',
            # Общие варианты
            'button:has-text("Accept Cookies")',
            'button:has-text("Accept all cookies")',
            'button:has-text("Allow all")',
            '.accept-cookies',
            '#accept-cookies',
            '[aria-label="Accept cookies"]',
        ]

        for selector in consent_selectors:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=2000):
                    await button.click()
                    logger.info(f"Clicked cookie consent: {selector}")
                    await asyncio.sleep(1)
                    return
            except Exception:
                continue

    async def _scroll_page(self, page: Page, scrolls: int = 3) -> None:
        """Прокрутить страницу для загрузки lazy-load контента."""
        for _ in range(scrolls):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(0.5)


# Глобальный экземпляр
browser_manager = BrowserManager()
