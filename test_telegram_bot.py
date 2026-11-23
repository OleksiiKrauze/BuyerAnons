"""Test Telegram bot."""
import asyncio
import sys
sys.path.insert(0, '/app')

from src.services.telegram_bot import telegram_bot
from src.models import Product


async def test_telegram():
    print("=" * 60)
    print("Testing Telegram Bot")
    print("=" * 60)

    # Check if bot is available
    print(f"\n1. Bot available: {telegram_bot.is_available}")

    if not telegram_bot.is_available:
        print("\n   TELEGRAM_BOT_TOKEN not set in .env file!")
        print("\n   How to create a Telegram bot:")
        print("   1. Open Telegram and find @BotFather")
        print("   2. Send /newbot")
        print("   3. Follow instructions to create bot")
        print("   4. Copy the token and add to .env:")
        print("   TELEGRAM_BOT_TOKEN=your_token_here")
        return

    # Get bot info
    print("\n2. Getting bot info...")
    me = await telegram_bot.get_me()
    if me:
        print(f"   Bot username: @{me.get('username')}")
        print(f"   Bot name: {me.get('first_name')}")
        print(f"   Bot ID: {me.get('id')}")
    else:
        print("   Failed to get bot info - check token")
        return

    # Test sending message (if admin chat ID is set)
    from src.config import settings
    if settings.telegram_admin_chat_id:
        print(f"\n3. Sending test message to {settings.telegram_admin_chat_id}...")

        result = await telegram_bot.send_message(
            settings.telegram_admin_chat_id,
            "🧪 <b>Test message from BuyerAnons</b>\n\nBot is working correctly!"
        )

        if result:
            print("   Message sent successfully!")
        else:
            print("   Failed to send message")

        # Test sending product
        print("\n4. Sending test product...")
        test_product = Product(
            name="Test Leather Jacket",
            original_price=199.99,
            sale_price=99.99,
            currency="GBP",
            image_url="https://static.zara.net/photos///2024/V/0/1/p/4341/792/800/2/w/750/4341792800_1_1_1.jpg",
            product_url="https://www.zara.com/uk/en/test-product-p12345.html",
            available_sizes=["S", "M", "L", "XL"],
            description="Stylish leather jacket with zipper",
            store="Zara",
        )

        await telegram_bot.send_products(settings.telegram_admin_chat_id, [test_product])
        print("   Product sent!")
    else:
        print("\n3. TELEGRAM_ADMIN_CHAT_ID not set")
        print("   To test sending messages:")
        print("   1. Start a chat with your bot")
        print("   2. Send /id to get your chat ID")
        print("   3. Add it to .env: TELEGRAM_ADMIN_CHAT_ID=your_chat_id")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Find your bot in Telegram: @" + (me.get('username') if me else 'your_bot'))
    print("2. Start a chat and send /start")
    print("3. Send /id to get your chat ID")
    print("4. Add TELEGRAM_ADMIN_CHAT_ID to .env")


if __name__ == "__main__":
    asyncio.run(test_telegram())
