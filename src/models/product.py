from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Product:
    """Модель товара со скидкой."""

    name: str
    original_price: float
    sale_price: float
    currency: str
    image_url: str
    product_url: str
    available_sizes: list[str] = field(default_factory=list)
    description: str = ""
    description_ua: str = ""  # Перевод на украинский
    store: str = ""
    short_url: str = ""  # Сокращённая ссылка
    category: str = ""  # Категория товара

    @property
    def discount_percent(self) -> int:
        """Рассчитать процент скидки."""
        if self.original_price <= 0:
            return 0
        # round, а не int: 12/15 даёт 19.999…, а скидка на самом деле 20%
        return round((1 - self.sale_price / self.original_price) * 100)

    @property
    def savings(self) -> float:
        """Экономия в валюте."""
        return self.original_price - self.sale_price

    def has_size(self, sizes: list[str]) -> bool:
        """Проверить наличие нужных размеров."""
        if not sizes:
            return True
        sizes_lower = [s.lower().strip() for s in sizes]
        available_lower = [s.lower().strip() for s in self.available_sizes]
        return any(s in available_lower for s in sizes_lower)

    def to_viber_message(self) -> str:
        """Форматировать для отправки в Viber."""
        currency_symbol = {
            "GBP": "£",
            "EUR": "€",
            "USD": "$",
            "UAH": "₴",
        }.get(self.currency, self.currency)

        sizes_str = ", ".join(self.available_sizes[:5])
        if len(self.available_sizes) > 5:
            sizes_str += "..."

        description = self.description_ua or self.description
        if len(description) > 100:
            description = description[:97] + "..."

        link = self.short_url or self.product_url

        return (
            f"📦 {self.name}\n"
            f"💰 {currency_symbol}{self.sale_price:.0f} (було {currency_symbol}{self.original_price:.0f}) -{self.discount_percent}%\n"
            f"📏 Розміри: {sizes_str}\n"
            f"📝 {description}\n"
            f"🔗 {link}"
        )

    def __repr__(self) -> str:
        return f"Product({self.name}, {self.discount_percent}% off, sizes: {self.available_sizes})"
