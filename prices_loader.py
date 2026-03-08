import json
import os

def load_procedures():
    """
    Загружает список процедур из data/procedures.json
    """
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'data', 'procedures.json')
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ Загружено {len(data.get('procedures', []))} процедур")
        return data
        
    except FileNotFoundError:
        print("⚠️ Файл procedures.json не найден. Используем базовые данные.")
        return get_default_procedures()
    except json.JSONDecodeError:
        print("❌ Ошибка чтения procedures.json.")
        return get_default_procedures()
    except Exception as e:
        print(f"❌ Ошибка загрузки процедур: {str(e)}")
        return get_default_procedures()

def get_default_procedures():
    """Возвращает базовые данные если файл не найден."""
    return {
        "procedures": [],
        "clinic_info": {
            "address_sochi": "Сочи, ул. Воровского, 22",
            "address_adler": "Адлер, ул. Кирова, 26а",
            "phone": "8-928-458-32-88",
            "hours": "Ежедневно 10:00–20:00",
            "no_installment": "Рассрочка и кредитование предоставляются"
        }
    }

def get_price_for_procedure(procedure_name: str, zone: str = None):
    """
    Ищет цену для процедуры и зоны.
    """
    data = load_procedures()
    procedure_name_lower = procedure_name.lower()
    
    for procedure in data.get('procedures', []):
        proc_name = procedure.get('name', '').lower()
        
        # Проверяем частичное совпадение названия
        if procedure_name_lower in proc_name or any(word in proc_name for word in procedure_name_lower.split()):
            
            # Если есть зона, ищем цену для зоны
            if zone and 'prices' in procedure:
                zone_lower = zone.lower()
                for price_zone, price in procedure['prices'].items():
                    if zone_lower in price_zone.lower():
                        return price
            
            # Если есть комплексы, возвращаем их
            if 'complexes' in procedure:
                return procedure['complexes']
            
            # Или возвращаем первую цену если есть
            if 'prices' in procedure and procedure['prices']:
                first_price = next(iter(procedure['prices'].values()))
                return first_price
    
    return None

def get_clinic_info():
    """
    Возвращает информацию о клинике.
    """
    data = load_procedures()
    return data.get('clinic_info', {})

def search_procedures_by_category(category: str):
    """
    Ищет процедуры по категории.
    """
    data = load_procedures()
    category_lower = category.lower()
    results = []
    
    for procedure in data.get('procedures', []):
        proc_category = procedure.get('category', '').lower()
        
        if category_lower in proc_category:
            results.append(procedure)
    
    return results

def format_price_response(procedure_name: str, price_info):
    """
    Форматирует ответ с ценой.
    """
    if isinstance(price_info, dict):
        # Если это словарь цен (например, для лазерной эпиляции)
        response = f"💰 Цены на {procedure_name}:\n"
        for zone, price in price_info.items():
            response += f"  • {zone}: {price} руб.\n"
        return response
    elif isinstance(price_info, (int, float)):
        # Если это одна цена
        return f"💰 {procedure_name}: {price_info} руб."
    else:
        return f"Информация о ценах на {procedure_name} доступна на консультации."

def get_all_categories():
    """
    Возвращает все категории процедур.
    """
    data = load_procedures()
    categories = set()
    
    for procedure in data.get('procedures', []):
        if 'category' in procedure:
            categories.add(procedure['category'])
    
    return list(categories)

# Тестовый вызов
if __name__ == "__main__":
    print("🧪 Тестируем загрузку процедур с ценами")
    
    procedures = load_procedures()
    clinic_info = get_clinic_info()
    
    print(f"\n🏥 Информация о клинике:")
    print(f"  📍 Сочи: {clinic_info.get('address_sochi')}")
    print(f"  📍 Адлер: {clinic_info.get('address_adler')}")
    print(f"  📞 Телефон: {clinic_info.get('phone')}")
    print(f"  ⏰ Часы работы: {clinic_info.get('hours')}")
    print(f"  💳 {clinic_info.get('no_installment')}")
    
    print(f"\n📋 Всего процедур: {len(procedures.get('procedures', []))}")
    
    # Тестируем поиск цен
    test_cases = [
        ("лазерная эпиляция", "подмышки"),
        ("ботулотоксин", None),
        ("чистка лица", None)
    ]
    
    for proc_name, zone in test_cases:
        price = get_price_for_procedure(proc_name, zone)
        print(f"\n🔍 Поиск цены для '{proc_name}' {f'зона {zone}' if zone else ''}:")
        if price:
            if isinstance(price, dict):
                print(f"  Найдено {len(price)} вариантов")
                for key, val in list(price.items())[:3]:
                    print(f"  - {key}: {val} руб")
            else:
                print(f"  Цена: {price} руб")
        else:
            print("  Цена не найдена")
