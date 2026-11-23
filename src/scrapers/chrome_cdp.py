"""
Запуск настоящего Chrome с DevTools-портом (CDP) для скраперов,
которым нужно обходить антибот-защиту (George, Joe's New Balance).

Работает на Windows (локальный запуск) и на Linux/Docker:
- ищет Google Chrome, затем Chromium, затем Chromium из комплекта Playwright;
- на Linux без экрана поднимает виртуальный экран Xvfb (окно браузера
  нужно, headless-режим антибот-системы распознают легче);
- под root добавляет --no-sandbox, в Docker — --disable-dev-shm-usage.
"""
import asyncio
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

import httpx
from loguru import logger
from playwright.async_api import async_playwright, Browser

IS_WINDOWS = sys.platform.startswith("win")

_WINDOWS_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]
_LINUX_PATHS = [
    "/opt/google/chrome/chrome",  # ставится `playwright install chrome`
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]
# Chromium из комплекта Playwright — запасной вариант (например, на ARM, где нет Google Chrome)
_PLAYWRIGHT_CHROMIUM_GLOBS = [
    os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/ms-playwright"), "chromium-*", "chrome-linux", "chrome"),
    os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome"),
]

_XVFB_DISPLAY = ":99"
_xvfb_process: Optional[subprocess.Popen] = None  # один виртуальный экран на весь процесс


def find_chrome() -> Optional[str]:
    """Найти браузер: CHROME_PATH из окружения, Google Chrome, Chromium, Chromium Playwright."""
    env_path = os.environ.get("CHROME_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    for path in (_WINDOWS_PATHS if IS_WINDOWS else _LINUX_PATHS):
        if os.path.exists(path):
            return path

    if not IS_WINDOWS:
        for pattern in _PLAYWRIGHT_CHROMIUM_GLOBS:
            matches = sorted(glob.glob(pattern))
            if matches:
                logger.warning("Google Chrome не найден, используется Chromium из Playwright (антибот может заметить)")
                return matches[-1]
    return None


def _profile_dir(name: str) -> str:
    base = os.environ.get("CHROME_PROFILE_DIR") or (r"C:\temp" if IS_WINDOWS else tempfile.gettempdir())
    path = os.path.join(base, f"chrome_{name}_bot")
    os.makedirs(path, exist_ok=True)
    return path


def _ensure_display() -> Optional[str]:
    """На Linux без экрана запустить Xvfb. Возвращает DISPLAY или None, если экрана не будет."""
    global _xvfb_process
    if IS_WINDOWS or sys.platform == "darwin":
        return None
    if os.environ.get("DISPLAY"):
        return os.environ["DISPLAY"]
    if _xvfb_process and _xvfb_process.poll() is None:
        return _XVFB_DISPLAY

    xvfb = shutil.which("Xvfb")
    if not xvfb:
        return None
    logger.info(f"Starting virtual display Xvfb {_XVFB_DISPLAY}")
    _xvfb_process = subprocess.Popen(
        [xvfb, _XVFB_DISPLAY, "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return _XVFB_DISPLAY


class ChromeCDP:
    """Один экземпляр Chrome на скрапер: запускается при первом запросе и переиспользуется."""

    def __init__(self, name: str, port: int):
        self.name = name
        self.port = port
        self._process: Optional[subprocess.Popen] = None
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def _cdp_ready(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                r = await client.get(f"http://127.0.0.1:{self.port}/json/version")
                return r.status_code == 200
        except Exception:
            return False

    async def _start_chrome(self) -> bool:
        if self._process and self._process.poll() is None and await self._cdp_ready():
            return True  # уже запущен

        chrome_path = find_chrome()
        if not chrome_path:
            logger.error("Chrome не найден. Установите Google Chrome или задайте CHROME_PATH.")
            return False

        args = [
            chrome_path,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={_profile_dir(self.name)}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            "--disable-sync",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-client-side-phishing-detection",
            "--profile-directory=Default",
            "--window-size=1920,1080",
        ]
        env = os.environ.copy()
        if not IS_WINDOWS:
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                args.append("--no-sandbox")  # Chrome не стартует под root без этого
            args.append("--disable-dev-shm-usage")  # в Docker /dev/shm всего 64 МБ
            display = _ensure_display()
            if display:
                env["DISPLAY"] = display
            elif sys.platform != "darwin":
                logger.warning("Нет экрана и Xvfb — Chrome запускается в headless-режиме")
                args.append("--headless=new")
        args.append("about:blank")

        logger.info(f"Starting Chrome for {self.name} on CDP port {self.port}: {chrome_path}")
        self._process = subprocess.Popen(args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for _ in range(40):  # до 20 секунд
            if self._process.poll() is not None:
                logger.error(f"Chrome завершился сразу после запуска (код {self._process.returncode})")
                return False
            if await self._cdp_ready():
                return True
            await asyncio.sleep(0.5)
        logger.error("Chrome не открыл CDP-порт за 20 секунд")
        return False

    async def get_browser(self) -> Optional[Browser]:
        """Свежее CDP-подключение к запущенному Chrome."""
        await self.disconnect()
        if not await self._start_chrome():
            return None

        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{self.port}")
            logger.info(f"Connected to Chrome via CDP ({self.name})")
            return self._browser
        except Exception as e:
            logger.error(f"Failed to connect to Chrome CDP: {e}")
            await self.disconnect()
            return None

    async def disconnect(self) -> None:
        """Отключиться от Chrome (сам браузер продолжает работать)."""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    async def stop(self) -> None:
        """Отключиться и закрыть Chrome."""
        await self.disconnect()
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
