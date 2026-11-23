"""Test translator service."""
import os
import sys

# Ensure we can import from src
sys.path.insert(0, '/app')

from src.services.translator import translator


def test_translator():
    print("=" * 60)
    print("Testing DeepL Translator")
    print("=" * 60)

    # Check if translator is available
    print(f"\n1. Translator available: {translator.is_available}")

    if not translator.is_available:
        print("\n   DEEPL_API_KEY not set in .env file!")
        print("   Get your free API key at: https://www.deepl.com/pro-api")
        print("\n   Add to .env file:")
        print("   DEEPL_API_KEY=your_key_here")
        return

    # Test single translation
    print("\n2. Single translation test:")
    print("-" * 40)

    test_texts = [
        "Black leather jacket with zipper",
        "Summer dress with floral pattern",
        "Running shoes for men, size 42",
        "50% off - Limited time offer!",
    ]

    for text in test_texts:
        translated = translator.translate(text, target_lang="UK")
        print(f"   EN: {text}")
        print(f"   UK: {translated}")
        print()

    # Test batch translation
    print("3. Batch translation test:")
    print("-" * 40)

    product_descriptions = [
        "Comfortable cotton t-shirt",
        "Slim fit jeans with stretch",
        "Warm winter coat with hood",
    ]

    translations = translator.translate_batch(product_descriptions, target_lang="UK")
    for orig, trans in zip(product_descriptions, translations):
        print(f"   {orig}")
        print(f"   → {trans}")
        print()

    print("=" * 60)
    print("Translation test completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_translator()
