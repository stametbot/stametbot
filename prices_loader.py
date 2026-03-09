import json
import os
from typing import Dict, Any, Optional, List, Union

def load_products():
    """
    Загружает каталог товаров из data/products.json
    """
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ Загружено {len(data.get('products', []))} товаров")
        return data
        
    except FileNotFoundError:
        print("⚠️ Файл products.json не найден. Используем базовые данные.")
        return get_default_products()
    except json.JSONDecodeError:
        print("❌ Ошибка чтения products.json.")
        return get_default_products()
    except Exception as e:
        print(f"❌ Ошибка загрузки товаров: {str(e)}")
        return get_default_products()

def get_default_products():
    """Возвращает базовые данные если файл не найден."""
    return {
        "products": [],
        "categories": [],
        "company_info": {
            "address": "Московская область, г.о. Мытищи, ул. Хлебозаводская, влд. 4А, стр. 1",
            "phone": "+7 (495) 109-33-88",
            "telegram": "@superlestnica_bot",
            "hours": "Пн-Пт 9:00–18:00, Сб-Вс по договоренности",
            "delivery": "Доставка по всей России транспортными компаниями",
            "payment": "Наличный и безналичный расчет"
        }
    }

def get_price_for_product(product_name: str, product_type: str = None) -> Optional[Union[int, float, str, Dict]]:
    """
    Ищет цену для товара.
    
    Args:
        product_name: Название товара или модели
        product_type: Тип товара (прямая/поворотная, материал и т.д.)
    
    Returns:
        Цена или словарь с ценами
    """
    data = load_products()
    product_name_lower = product_name.lower()
    
    for product in data.get('products', []):
        name = product.get('name', '').lower()
        
        # Проверяем точное совпадение названия
        if product_name_lower in name or any(word in name for word in product_name_lower.split()):
            
            # Если есть прямая цена
            if 'price' in product:
                return product['price']
            
            # Если есть цена "от"
            if 'price_from' in product:
                return product['price_from']
            
            # Если есть цены для разных типов
            if 'prices' in product and product_type:
                type_lower = product_type.lower()
                for price_type, price in product['prices'].items():
                    if type_lower in price_type.lower():
                        return price
            
            # Если есть комплексы/варианты
            if 'variants' in product:
                return product['variants']
    
    return None

def get_product_info(product_name: str) -> Optional[Dict]:
    """
    Возвращает полную информацию о товаре.
    """
    data = load_products()
    product_name_lower = product_name.lower()
    
    for product in data.get('products', []):
        name = product.get('name', '').lower()
        
        if product_name_lower in name or any(word in name for word in product_name_lower.split()):
            return product
    
    return None

def get_company_info():
    """
    Возвращает информацию о компании.
    """
    data = load_products()
    return data.get('company_info', get_default_products()['company_info'])

def search_products_by_category(category: str) -> List[Dict]:
    """
    Ищет товары по категории.
    
    Categories: "Лестницы", "Каркасы", "Комплектующие"
    """
    data = load_products()
    category_lower = category.lower()
    results = []
    
    for product in data.get('products', []):
        product_category = product.get('category', '').lower()
        product_subcategory = product.get('subcategory', '').lower()
        
        if category_lower in product_category or category_lower in product_subcategory:
            results.append(product)
    
    return results

def search_products_by_series(series: str) -> List[Dict]:
    """
    Ищет товары по серии (Престиж, Элегант и т.д.)
    """
    data = load_products()
    series_lower = series.lower()
    results = []
    
    for product in data.get('products', []):
        subcategory = product.get('subcategory', '').lower()
        name = product.get('name', '').lower()
        
        if series_lower in subcategory or series_lower in name:
            results.append(product)
    
    return results

def get_steps_by_material(material: str) -> List[Dict]:
    """
    Возвращает ступени по материалу (хвоя/бук)
    """
    data = load_products()
    material_lower = material.lower()
    results = []
    
    for product in data.get('products', []):
        if 'ступен' in product.get('name', '').lower():
            specs = product.get('specs', {})
            product_material = specs.get('material', '').lower()
            
            if material_lower in product_material:
                results.append(product)
    
    return results

def get_accessories_by_type(accessory_type: str) -> List[Dict]:
    """
    Возвращает комплектующие по типу (поручни, балясины, подпорки и т.д.)
    """
    data = load_products()
    type_lower = accessory_type.lower()
    results = []
    
    for product in data.get('products', []):
        if product.get('category') == 'Комплектующие':
            subcategory = product.get('subcategory', '').lower()
            name = product.get('name', '').lower()
            
            if type_lower in subcategory or type_lower in name:
                results.append(product)
    
    return results

def format_price_response(product_name: str, price_info, additional_info: str = None) -> str:
    """
    Форматирует ответ с ценой.
    """
    if isinstance(price_info, dict):
        # Если это словарь цен для разных конфигураций
        response = f"💰 Цены на {product_name}:\n"
        for config, price in price_info.items():
            if isinstance(price, (int, float)):
                response += f"  • {config}: {price:,} руб.\n".replace(',', ' ')
            else:
                response += f"  • {config}: {price}\n"
        
        if additional_info:
            response += f"\n{additional_info}"
        
        return response
    
    elif isinstance(price_info, (int, float)):
        # Если это одна цена
        response = f"💰 {product_name}: {price_info:,} руб.".replace(',', ' ')
        
        if additional_info:
            response += f"\n\n{additional_info}"
        
        return response
    
    elif isinstance(price_info, str):
        # Если это текстовая информация о цене
        response = f"💰 {product_name}: {price_info}"
        
        if additional_info:
            response += f"\n\n{additional_info}"
        
        return response
    
    else:
        return f"Информация о ценах на {product_name} доступна после консультации с менеджером. Оставьте ваш телефон для связи."

def get_all_categories() -> List[Dict]:
    """
    Возвращает все категории товаров.
    """
    data = load_products()
    return data.get('categories', [])

def get_price_range_for_series(series: str) -> Optional[str]:
    """
    Возвращает диапазон цен для серии лестниц.
    """
    products = search_products_by_series(series)
    
    if not products:
        return None
    
    prices = []
    for product in products:
        if 'price_from' in product:
            prices.append(product['price_from'])
        elif 'price' in product:
            prices.append(product['price'])
    
    if prices:
        min_price = min(prices)
        max_price = max(prices)
        return f"от {min_price:,} до {max_price:,} руб.".replace(',', ' ')
    
    return None

def calculate_staircase_cost(series: str, height_mm: int, staircase_type: str = "прямая") -> Optional[int]:
    """
    Примерный расчет стоимости лестницы по высоте.
    Это упрощенный расчет, для точного нужна консультация менеджера.
    """
    base_prices = {
        "престиж": {"прямая": 74400, "поворотная": 85000},
        "престиж комфорт": {"прямая": 119000, "поворотная": 130000},
        "элегант": {"прямая": 87200, "поворотная": 95000},
        "элегант комфорт": {"прямая": 105000, "поворотная": 115000},
        "престиж мини": {"прямая": 53900}
    }
    
    series_lower = series.lower()
    type_lower = staircase_type.lower()
    
    # Базовая высота для расчета (в мм)
    base_heights = {
        "престиж": 2025,
        "престиж комфорт": 2090,
        "элегант": 2070,
        "элегант комфорт": 2090,
        "престиж мини": 2000
    }
    
    if series_lower in base_prices and type_lower in base_prices[series_lower]:
        base_price = base_prices[series_lower][type_lower]
        base_height = base_heights.get(series_lower, 2000)
        
        # Примерный расчет: пропорционально высоте
        if height_mm != base_height:
            # Каждый дополнительный модуль стоит примерно 1000-1500 руб
            height_diff = height_mm - base_height
            modules_count = height_diff / 225  # шаг модуля примерно 225 мм
            additional_cost = int(modules_count * 1200)  # ~1200 руб за модуль
            estimated_price = base_price + additional_cost
        else:
            estimated_price = base_price
        
        return estimated_price
    
    return None

# Тестовый вызов
if __name__ == "__main__":
    print("🧪 Тестируем загрузку товаров с ценами")
    
    products = load_products()
    company_info = get_company_info()
    
    print(f"\n🏢 Информация о компании:")
    print(f"  📍 Адрес: {company_info.get('address')}")
    print(f"  📞 Телефон: {company_info.get('phone')}")
    print(f"  📱 Telegram: {company_info.get('telegram')}")
    print(f"  ⏰ Часы работы: {company_info.get('hours')}")
    print(f"  🚚 Доставка: {company_info.get('delivery')}")
    print(f"  💳 Оплата: {company_info.get('payment')}")
    
    print(f"\n📋 Всего товаров: {len(products.get('products', []))}")
    
    # Тестируем поиск цен
    test_cases = [
        ("престиж", "прямая"),
        ("элегант", None),
        ("ступени бук", None),
        ("поручни", "2 метра")
    ]
    
    for product_name, product_type in test_cases:
        price = get_price_for_product(product_name, product_type)
        print(f"\n🔍 Поиск цены для '{product_name}' {f'тип {product_type}' if product_type else ''}:")
        if price:
            if isinstance(price, dict):
                print(f"  Найдено {len(price)} вариантов")
                for key, val in list(price.items())[:3]:
                    if isinstance(val, (int, float)):
                        print(f"  - {key}: {val:,} руб".replace(',', ' '))
                    else:
                        print(f"  - {key}: {val}")
            else:
                print(f"  Цена: {price}")
        else:
            print("  Цена не найдена")
    
    # Тестируем расчет стоимости
    print("\n🧮 Тест расчета стоимости:")
    test_height = 2500
    estimated = calculate_staircase_cost("престиж", test_height, "поворотная")
    if estimated:
        print(f"  Престиж поворотная, высота {test_height} мм: ~{estimated:,} руб".replace(',', ' '))
