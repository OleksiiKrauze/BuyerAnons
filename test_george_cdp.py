"""Test George/ASDA with Chrome CDP - extract products."""
import asyncio
import subprocess
import time
import sys
sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright

async def test():
    print("Starting Chrome with debugging...")
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    subprocess.run(["taskkill", "/f", "/im", "chrome.exe"], capture_output=True)
    time.sleep(2)

    proc = subprocess.Popen([
        chrome_path,
        "--remote-debugging-port=9222",
        "--user-data-dir=C:\\temp\\chrome_george4",
        "https://direct.asda.com/george/sale/womens/D55M3G1C1,default,sc.html"
    ])

    print("Waiting 15 seconds...")
    time.sleep(15)

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")

    contexts = browser.contexts
    if contexts and contexts[0].pages:
        page = contexts[0].pages[0]

        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 1000)")
            await asyncio.sleep(1)
        await asyncio.sleep(3)

        products = await page.evaluate(r'''
            () => {
                const results = [];
                const productCards = document.querySelectorAll('.product-mini, .product-card, .product-tile');

                productCards.forEach(card => {
                    try {
                        const nameEl = card.querySelector('.product-mini-link, .product-name, h3, h4');
                        const name = nameEl?.textContent?.trim() || '';

                        const priceContainer = card.querySelector('[class*="price"], .mini-product-info');
                        let nowPrice = '';
                        let wasPrice = '';

                        if (priceContainer) {
                            const text = priceContainer.textContent;
                            const prices = text.match(/[\u00a3$][\d.]+/g) || [];
                            if (prices.length >= 2) {
                                nowPrice = prices[0];
                                wasPrice = prices[1];
                            } else if (prices.length === 1) {
                                nowPrice = prices[0];
                            }
                        }

                        const img = card.querySelector('img');
                        const image = img?.src || '';
                        const link = card.querySelector('a')?.href || '';

                        if (name && nowPrice) {
                            results.push({ name, nowPrice, wasPrice, image, link });
                        }
                    } catch(e) {}
                });
                return results;
            }
        ''')

        print(f"\nFound {len(products)} products with prices:\n")
        for i, p in enumerate(products[:15]):
            discount = ""
            if p['wasPrice'] and p['nowPrice']:
                try:
                    was = float(p['wasPrice'].replace('\u00a3','').replace('$',''))
                    now = float(p['nowPrice'].replace('\u00a3','').replace('$',''))
                    disc = int((1 - now/was) * 100)
                    discount = f" (-{disc}%)"
                except:
                    pass
            now = p['nowPrice'].replace('\u00a3', 'GBP ')
            was = p['wasPrice'].replace('\u00a3', 'GBP ') if p['wasPrice'] else 'N/A'
            print(f"{i+1}. {p['name'][:50]}")
            print(f"   Now: {now}, Was: {was}{discount}")

    await browser.close()
    await pw.stop()
    proc.terminate()
    print("\nDone!")

asyncio.run(test())
