FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (chromium for general, firefox for New Balance)
RUN playwright install chromium firefox

# Google Chrome for George / New Balance (real Chrome passes bot protection better).
# Google Chrome has no Linux ARM build - on ARM the bundled Playwright Chromium is used instead.
RUN if [ "$(dpkg --print-architecture)" = "amd64" ]; then playwright install chrome; fi

# Copy source code
COPY src/ ./src/
COPY test_api.py ./
COPY test_browser_scrape.py ./
COPY test_browser_v2.py ./
COPY test_browser_v3.py ./
COPY test_browser_v4.py ./
COPY test_zara.py ./
COPY test_zara_v2.py ./
COPY test_zara_v3.py ./
COPY test_zara_v4.py ./
COPY test_zara_v5.py ./
COPY test_zara_final.py ./
COPY test_zara_scraper.py ./
COPY test_translator.py ./
COPY test_telegram_bot.py ./
COPY test_newbalance.py ./
COPY run_bot.py ./

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "-m", "src.main"]
