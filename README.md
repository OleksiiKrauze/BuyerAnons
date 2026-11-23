# BuyerAnons - Сервіс моніторингу знижок

Telegram-бот для автоматичного пошуку знижок в іноземних інтернет-магазинах з перекладом на українську мову.

## Можливості

- 🔍 Сканування сторінок розпродажів Zara, ASDA/George та DKNY
- 🌍 Підтримка різних регіонів (UK, PT, ES, тощо)
- 🇺🇦 Автоматичний переклад на українську (DeepL)
- 📊 Три режими сортування товарів
- 🔒 Обмеження доступу за списком користувачів
- 🐳 Docker-контейнеризація

## Архітектура

```
BuyerAnons/
├── src/
│   ├── config/
│   │   └── settings.py          # Налаштування з .env
│   ├── models/
│   │   └── product.py           # Модель товару
│   ├── scrapers/
│   │   ├── base.py              # Базовий клас скрапера
│   │   ├── zara.py              # Zara API скрапер
│   │   ├── asda.py              # ASDA браузерний скрапер
│   │   └── asda_api.py          # ASDA Algolia API скрапер
│   └── services/
│       ├── telegram_bot.py      # Telegram бот
│       ├── translator.py        # DeepL перекладач
│       └── link_shortener.py    # Скорочувач посилань
├── run_bot.py                   # Запуск бота
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env                         # Конфігурація (не в git)
```

## Встановлення

### 1. Клонування репозиторію

```bash
git clone <repository-url>
cd BuyerAnons
```

### 2. Налаштування .env

Скопіюйте `.env.example` в `.env` та заповніть:

```env
# DeepL API (обов'язково для перекладу)
# Отримати: https://www.deepl.com/pro-api
DEEPL_API_KEY=your_deepl_api_key

# Telegram Bot (обов'язково)
# Отримати: https://t.me/BotFather
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id

# Список дозволених користувачів (через кому)
TELEGRAM_ALLOWED_USERS=123456789,987654321

# Налаштування за замовчуванням
DEFAULT_TOP_COUNT=10
DEFAULT_MIN_DISCOUNT=30
LOG_LEVEL=INFO
```

### 3. Запуск через Docker

```bash
# Збірка та запуск
docker-compose build
docker-compose run --rm -d buyer-anons python run_bot.py

# Перегляд логів
docker logs <container_id> -f

# Зупинка
docker-compose down
```

## Використання бота

### Команди

| Команда | Опис |
|---------|------|
| `/start` | Привітання та інструкції |
| `/help` | Довідка по командах |
| `/id` | Показати ваш Chat ID |
| `/scan URL` | Сканувати сторінку |

### Параметри /scan

| Параметр | Опис | Приклад |
|----------|------|---------|
| `--top N` | Кількість товарів | `--top 10` |
| `--sizes` | Фільтр розмірів | `--sizes M,L,42` |
| `--min-discount N` | Мінімальна знижка % | `--min-discount 30` |
| `--sort discount` | Сортування за знижкою (за замовч.) | |
| `--sort price` | Сортування за ціною (дешеві) | |
| `--sort value N` | Ціна до N + знижка | `--sort value 50` |

### Приклади

```
# 5 товарів з найбільшою знижкою
/scan https://www.zara.com/pt/pt/s-mulher-precos-especiais-l9982.html --top 5

# 10 найдешевших товарів
/scan https://www.zara.com/pt/pt/s-mulher-precos-especiais-l9982.html --top 10 --sort price

# Товари до 30€ з найбільшою знижкою
/scan https://www.zara.com/pt/pt/s-mulher-precos-especiais-l9982.html --top 5 --sort value 30

# Фільтр за розмірами
/scan https://www.zara.com/uk/en/woman-new-in-l1180.html --sizes M,L --top 5
```

## Підтримувані магазини

### Zara (zara.com)
- ✅ Всі регіони (UK, PT, ES, DE, тощо)
- ✅ Сторінки розпродажів (Special Prices)
- ✅ Нові надходження
- ✅ Категорії товарів
- ✅ Ціни та знижки (oldPrice)
- ⚠️ Розміри недоступні в API категорій

### ASDA/George (direct.asda.com)
- ✅ Algolia API для пошуку
- ⚠️ Браузерний скрапінг блокується Cloudflare
- ⚠️ Знижки не завжди доступні в API

### DKNY (dkny.com)
- ✅ Shopify JSON API (`/collections/<розділ>/products.json`), без браузера
- ✅ Ціни зі знижками (compare_at_price), розміри в наявності, фото
- ✅ Посилання на розділ: `https://www.dkny.com/collections/sale` (також `clearance`, `sale-shoes`, `sale-bags`, `sale-men`...)
- ⚠️ Посилання на окремий товар (`/products/...`) не підтримується
- 💡 Ринок США (USD) зафіксовано cookie `localization=US` — інакше Shopify визначає країну за IP і віддає ціни без знижок

### Joe's New Balance Outlet (joesnewbalanceoutlet.com)
- ✅ Підтримує парсинг через Playwright Firefox
- ✅ Ціни, знижки, фото товарів
- ⚠️ **Блокується з серверних IP** (PerimeterX захист)
- ⚠️ Працює тільки з резидентними IP або проксі
- 💡 Для хмарного деплою потрібен residential proxy

## Технічні деталі

### Zara API

Zara використовує JSON API з параметром `?ajax=true`:

```
https://www.zara.com/{country}/{lang}/{category}.html?ajax=true
```

Структура відповіді:
```
productGroups → elements → commercialComponents
                              ├── name
                              ├── price (в центах)
                              ├── oldPrice (стара ціна)
                              ├── seo.keyword
                              └── detail.colors[].xmedia
```

### Модель товару

```python
@dataclass
class Product:
    name: str               # Назва товару
    original_price: float   # Стара ціна
    sale_price: float       # Поточна ціна
    currency: str           # Валюта (GBP, EUR)
    image_url: str          # URL зображення
    product_url: str        # Посилання на товар
    available_sizes: list   # Доступні розміри
    description: str        # Опис (англійською)
    description_ua: str     # Опис (українською)
    store: str              # Назва магазину

    @property
    def discount_percent(self) -> int:
        # Автоматичний розрахунок знижки
```

### Перекладач (DeepL)

- Batch-переклад для оптимізації
- Переклад назв та описів товарів
- Fallback на оригінал при помилці

### Безпека

- Обмеження доступу за Chat ID
- Команда `/id` доступна всім (для отримання ID)
- API ключі зберігаються в `.env` (не в git)

## Залежності

```
playwright==1.40.0          # Браузерна автоматизація
httpx==0.25.2               # HTTP клієнт
deepl==1.16.1               # Переклад
pydantic==2.5.2             # Валідація даних
pydantic-settings==2.1.0    # Налаштування з .env
loguru==0.7.2               # Логування
```

## Розробка

### Запуск тестів

```bash
# Тест Zara скрапера
docker-compose run --rm buyer-anons python test_zara_scraper.py

# Тест перекладача
docker-compose run --rm buyer-anons python test_translator.py

# Тест Telegram бота
docker-compose run --rm buyer-anons python test_telegram_bot.py
```

### Додавання нового магазину

1. Створіть `src/scrapers/newstore.py`:

```python
from .base import BaseScraper
from ..models import Product

class NewStoreScraper(BaseScraper):
    STORE_NAME = "NewStore"
    DOMAINS = ["newstore.com"]

    async def scrape(self, url, sizes=None, top_count=10,
                     min_discount=0, sort_mode="discount",
                     max_price=None) -> list[Product]:
        # Реалізація
        pass
```

2. Зареєструйте в `src/scrapers/__init__.py`

3. Додайте в `run_bot.py`:
```python
scrapers = {
    "zara": ZaraScraper(),
    "asda": AsdaApiScraper(),
    "newstore": NewStoreScraper(),  # Новий
}
```

## Статус реалізації

| Компонент | Статус |
|-----------|--------|
| Zara скрапер | ✅ Готово |
| ASDA/George API | ✅ Готово |
| Joe's New Balance | ⚠️ Готово (потребує residential proxy) |
| DKNY | ✅ Готово |
| DeepL переклад | ✅ Готово |
| Telegram бот | ✅ Готово |
| Сортування (3 режими) | ✅ Готово |
| Обмеження доступу | ✅ Готово |
| Docker | ✅ Готово |
| Viber бот | ❌ Скасовано (Viber вимагає бізнес-контракт) |
| AWS деплой | ⏳ Очікує |

## Ліцензія

Приватний проект.

## Контакти

Telegram бот: @BuyerAnons_bot
