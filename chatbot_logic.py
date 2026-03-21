# chatbot_logic.py
import replicate
import re
import json
import os

def detect_order_intent_with_ai(api_key: str, conversation_history: str, current_message: str) -> bool:
    """
    Использует AI для определения, хочет ли клиент заказать или рассчитать стоимость лестницы.
    Возвращает True если клиент хочет заказать/рассчитать.
    """
    try:
        prompt = f"""Проанализируй диалог и определи, хочет ли клиент заказать лестницу или рассчитать стоимость.

ПРАВИЛА АНАЛИЗА:
1. Клиент ХОЧЕТ заказать/рассчитать если:
   - Явно говорит "хочу заказать", "сделайте заказ", "оформите заказ"
   - Просит рассчитать стоимость для своих параметров
   - Указывает высоту проема или другие параметры для расчета
   - Дает свое имя и телефон после обсуждения модели
   - Спрашивает "сколько будет стоить для моих размеров", "рассчитайте стоимость"

2. Клиент НЕ хочет заказывать если:
   - Только спрашивает информацию о моделях
   - Просто интересуется ценами без конкретных параметров
   - Обсуждает характеристики без планов покупки

ИСТОРИЯ ДИАЛОГА:
{conversation_history}

ПОСЛЕДНЕЕ СООБЩЕНИЕ КЛИЕНТА:
"{current_message}"

ВОПРОС: Клиент хочет заказать или рассчитать стоимость? 

ОТВЕТ (ТОЛЬКО "ДА" или "НЕТ"):"""

        client = replicate.Client(api_token=api_key)
        
        output = client.run(
            "meta/meta-llama-3-70b-instruct",
            input={
                "prompt": prompt,
                "max_tokens": 10,
                "temperature": 0.1,
                "top_p": 0.9
            }
        )
        
        # Обрабатываем ответ
        result = ""
        if hasattr(output, '__iter__') and not isinstance(output, str):
            for chunk in output:
                if isinstance(chunk, str):
                    result += chunk
                else:
                    result += str(chunk)
        elif isinstance(output, str):
            result = output
        else:
            result = str(output)
        
        result = result.strip().lower()
        print(f"🤖 AI анализ намерения: '{result}'")
        
        if "да" in result:
            return True
        elif "нет" in result:
            return False
        else:
            # Если AI дал неоднозначный ответ, проверяем по ключевым словам
            current_lower = current_message.lower()
            action_words = ["заказ", "хочу", "нужно", "можно", "готов", "давайте", "рассчитай", "сколько стоит", "цена"]
            return any(word in current_lower for word in action_words)
            
    except Exception as e:
        print(f"❌ Ошибка AI при анализе намерения: {str(e)}")
        # Fallback только при ошибке AI
        current_lower = current_message.lower()
        action_words = ["заказ", "хочу", "нужно", "можно", "готов", "давайте", "рассчитай", "сколько стоит", "цена"]
        return any(word in current_lower for word in action_words)

# Загружаем каталог товаров из файла
def load_products_catalog():
    """Загружает каталог товаров из файла products.json."""
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'data', 'products.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка загрузки каталога товаров: {e}")
        return {}

def format_product_for_prompt(product):
    """Форматирует товар для включения в промпт."""
    result = f"\n• {product.get('name', '')}"
    
    # Добавляем описание
    if product.get('description'):
        result += f" — {product['description']}"
    
    # Добавляем цену
    if product.get('price'):
        result += f"\n  Цена: {product['price']} руб."
    elif product.get('price_from'):
        result += f"\n  Цена от {product['price_from']} руб. (зависит от высоты и комплектации)"
    
    # Добавляем характеристики
    specs = product.get('specs', {})
    if specs:
        if specs.get('materials'):
            result += f"\n  Материалы: {', '.join(specs['materials'])}"
        if specs.get('colors'):
            result += f"\n  Цвета: {', '.join(specs['colors'])}"
        if specs.get('types'):
            result += f"\n  Типы: {', '.join(specs['types'][:3])}..."
    
    return result

def create_system_prompt():
    """Создает SYSTEM_PROMPT с актуальным каталогом товаров."""
    products_data = load_products_catalog()
    products = products_data.get('products', [])
    
    base_prompt = """
Ты — Алина, менеджер компании по производству лестниц.

ТВОЙ СТИЛЬ ОБЩЕНИЯ:
- Дружелюбная, профессиональная, эксперт по всем видам лестниц и комплектующим
- ОТВЕЧАЙ НА ВСЕ ВОПРОСЫ о лестницах, используя каталог товаров ниже
- Если спрашивают о конкретной модели — расскажи особенности и УКАЖИ ЦЕНУ из каталога
- ОПИСЫВАЙ ХАРАКТЕРИСТИКИ: материалы (хвоя/бук), цвета RAL, типы (прямая/поворотная)
- Если хотят заказать или рассчитать стоимость — попроси параметры проема и контакты
- ИСПОЛЬЗУЙ КАТАЛОГ НИЖЕ для точных цен и информации

ВАЖНЫЕ ПРАВИЛА:
1. НИКОГДА не говори "у нас нет такой лестницы"! ВСЕ товары из каталога ниже доступны.
2. Если клиент спрашивает общую категорию (например "лестница престиж") — перечисли ВСЕ варианты из этой категории с ценами.
3. Если спрашивают конкретную модель — найди ее в каталоге и дай точную цену.
4. Представляйся только при первом сообщении.
5. Контакты добавляй только когда клиент хочет заказать или уточнить расчет.
6. При вопросах о материалах — объясни разницу между хвоей и буком.
7. При вопросах о типах — объясни особенности прямых, поворотных, разворотных лестниц.
8. Если клиент хочет заказать, но не указал параметры — ПОПРОСИ высоту проема (от пола до пола).

ВАЖНО ПРО СЕРИИ:
- Престиж: шаг 225 мм, надежная классическая модель
- Престиж Комфорт: шаг 190 мм, более комфортный подъем
- Престиж Мини: ступени "гусиный шаг", компактная
- Элегант: шаг 230 мм, легкий изящный дизайн
- Элегант Комфорт: шаг 190 мм, изящная и комфортная

ЦВЕТА RAL:
• RAL 1015 (слоновая кость)
• RAL 9005 (черный матовый)
• RAL 9006 (алюминиевый металлик)

КОНТАКТЫ КОМПАНИИ (добавляй только когда нужно):
📞 Телефон: 8-9XX-XXX-XX-XX
📍 Адрес: Московская область, г. [Ваш город], ул. [Ваша улица]
🚚 Доставка по всей России транспортными компаниями
⏰ Работаем: Пн-Пт 9:00–18:00, Сб-Вс по договоренности
"""

    # Формируем детальный каталог
    catalog_section = "\n" + "="*60 + "\n"
    catalog_section += "📋 ПОЛНЫЙ КАТАЛОГ ЛЕСТНИЦ И КОМПЛЕКТУЮЩИХ\n"
    catalog_section += "="*60 + "\n\n"
    
    if products:
        # Группируем товары по категориям
        categories = {}
        
        for product in products:
            category = product.get('category', 'другое')
            subcategory = product.get('subcategory', '')
            
            if category not in categories:
                categories[category] = []
            
            categories[category].append(format_product_for_prompt(product))
        
        # Категории для отображения
        category_names = {
            'Лестницы': '🏠 МОДУЛЬНЫЕ ЛЕСТНИЦЫ',
            'Каркасы': '🛠️ КАРКАСЫ ДЛЯ ЛЕСТНИЦ',
            'Комплектующие': '🔧 КОМПЛЕКТУЮЩИЕ'
        }
        
        for category_ru, products_list in categories.items():
            category_display = category_names.get(category_ru, category_ru.upper())
            catalog_section += f"\n{category_display}:\n"
            catalog_section += "-" * 40 + "\n"
            for product_desc in products_list:
                catalog_section += product_desc + "\n"
    
    else:
        # Запасной каталог если файл не загрузился
        catalog_section += """
Основные модели и цены:

1. ЛЕСТНИЦА ПРЕСТИЖ:
   • Прямая: от 74 400 руб
   • Поворотная: от 85 000 руб
   • Материалы: хвоя, бук
   • Цвета: слоновая кость, черный, алюминий

2. ЛЕСТНИЦА ЭЛЕГАНТ:
   • Прямая: от 87 200 руб
   • Поворотная: от 95 000 руб
   • Материалы: хвоя, бук
   • Цвета: слоновая кость, черный, алюминий

3. СТУПЕНИ:
   • Прямая (хвоя): 3 500 руб/шт
   • Прямая (бук): 2 580 руб/шт
   • Угловая (хвоя): 1 900 руб/шт
"""
    
    full_prompt = base_prompt + catalog_section
    
    return full_prompt

def handle_opening_question(message: str) -> tuple[bool, str]:
    """Проверяет, спрашивают ли о размере/параметрах проема."""
    message_lower = message.lower()
    keywords = ["высота", "проем", "размер", "параметр", "габарит", "от пола до пола", "от пола", "до потолка"]
    
    if any(keyword in message_lower for keyword in keywords):
        return True, "Для точного расчета стоимости лестницы мне нужна высота от пола первого этажа до пола второго этажа (в миллиметрах). Также, если знаете, укажите длину и ширину проема. Эти параметры помогут подобрать оптимальную конфигурацию."
    
    return False, ""

def handle_material_question(message: str) -> tuple[bool, str]:
    """Проверяет, спрашивают ли о материалах ступеней."""
    message_lower = message.lower()
    keywords = ["материал", "дерево", "хвоя", "бук", "сосна", "из чего", "какая древесина"]
    
    if any(keyword in message_lower for keyword in keywords):
        response = """Мы используем два вида древесины для ступеней:

🌲 ХВОЯ (сосна):
• Более доступная цена
• Светлый оттенок
• Мягкая древесина, легко поддается обработке
• Требует более бережного ухода

🌳 БУК:
• Плотная, износостойкая древесина
• Красивая текстура
• Дольше служит
• Выше стоимость

Оба варианта экологичны и прекрасно подходят для лестниц. Какой вас интересует?"""
        return True, response
    
    return False, ""

def handle_color_question(message: str) -> tuple[bool, str]:
    """Проверяет, спрашивают ли о цветах."""
    message_lower = message.lower()
    keywords = ["цвет", "ral", "краска", "покраск", "оттенок", "палитр"]
    
    if any(keyword in message_lower for keyword in keywords):
        response = """Лестницы и комплектующие доступны в четырех цветах RAL:

• RAL 1015 (слоновая кость) — теплый светлый оттенок
• RAL 9005 (черный матовый) — глубокий черный цвет
• RAL 9006 (алюминиевый металлик) — серебристый с блеском

Какой цвет вас интересует?"""
        return True, response
    
    return False, ""

def handle_installation_question(message: str) -> tuple[bool, str]:
    """Проверяет, спрашивают ли о монтаже."""
    message_lower = message.lower()
    keywords = ["монтаж", "установк", "сборк", "собрать", "поставить", "кто устанавливает"]
    
    if any(keyword in message_lower for keyword in keywords):
        response = """По монтажу лестниц:

🔨 Вы можете собрать лестницу самостоятельно — модульные конструкции спроектированы так, чтобы сборка была интуитивно понятной. В комплекте идет инструкция.

👷 Если нужна помощь профессиональных монтажников, мы можем порекомендовать проверенных специалистов в вашем регионе.

💡 Также возможен выезд нашей бригады (стоимость рассчитывается индивидуально, зависит от удаленности объекта).

Вам нужна помощь со сборкой?"""
        return True, response
    
    return False, ""

def handle_delivery_question(message: str) -> tuple[bool, str]:
    """Проверяет, спрашивают ли о доставке."""
    message_lower = message.lower()
    keywords = ["доставк", "транспорт", "отправк", "перевозк", "как получить", "везете"]
    
    if any(keyword in message_lower for keyword in keywords):
        response = """🚚 Доставка осуществляется по всей России через транспортные компании (Деловые Линии, ПЭК, СДЭК, Байкал Сервис и др.).

Стоимость доставки рассчитывается индивидуально, исходя из:
• Габаритов груза
• Удаленности вашего региона
• Тарифов выбранной ТК

Отправляем в день готовности заказа. После отгрузки вы получите трек-номер для отслеживания.

Рассчитать примерную стоимость доставки в ваш город?"""
        return True, response
    
    return False, ""

def handle_payment_question(message: str) -> tuple[bool, str]:
    """Проверяет, спрашивают ли об оплате."""
    message_lower = message.lower()
    keywords = ["оплат", "рассрочк", "кредит", "как оплатить", "предоплат", "расчет"]
    
    if any(keyword in message_lower for keyword in keywords):
        response = """💳 Условия оплаты:

• Работаем по 100% предоплате
• Доступны наличный и безналичный расчет
• Для юридических лиц выставляем счет с НДС

Рассрочку и кредит, к сожалению, не предоставляем. Оплата производится полностью при заказе."""
        return True, response
    
    return False, ""

def handle_timing_question(message: str) -> tuple[bool, str]:
    """Проверяет, спрашивают ли о сроках изготовления."""
    message_lower = message.lower()
    keywords = ["срок", "изготовлени", "производств", "когда будет", "через сколько", "время"]
    
    if any(keyword in message_lower for keyword in keywords):
        response = """⏱️ Сроки изготовления:

• Прямые лестницы: 5-7 рабочих дней
• Поворотные/разворотные конфигурации: 10-15 рабочих дней
• Каркасы: 7-10 рабочих дней

Срок зависит от сложности конструкции и текущей загруженности производства. Точный срок скажет менеджер после согласования проекта.

Можете оставить заявку для уточнения по вашей конфигурации?"""
        return True, response
    
    return False, ""

def detect_order_intent_with_ai(api_key: str, conversation_history: str, current_message: str) -> bool:
    """
    Использует AI для определения, хочет ли клиент заказать или рассчитать стоимость.
    Возвращает True если клиент хочет заказать.
    """
    try:
        prompt = f"""Проанализируй диалог и определи, хочет ли клиент заказать лестницу или рассчитать стоимость.

ПРАВИЛА АНАЛИЗА:
1. Клиент ХОЧЕТ заказать если:
   - Явно говорит "хочу заказать", "сделайте заказ", "оформите"
   - Просит рассчитать стоимость для своих параметров
   - Дает свое имя и телефон после обсуждения модели
   - Указывает высоту проема или другие параметры для расчета
   - Спрашивает "сколько будет стоить для моих размеров"

2. Клиент НЕ хочет заказывать если:
   - Только спрашивает информацию о моделях
   - Просто интересуется без конкретных параметров
   - Обсуждает в общем без планов покупки

ИСТОРИЯ ДИАЛОГА:
{conversation_history}

ПОСЛЕДНЕЕ СООБЩЕНИЕ КЛИЕНТА:
"{current_message}"

ВОПРОС: Клиент хочет заказать или рассчитать стоимость? 

ОТВЕТ (ТОЛЬКО "ДА" или "НЕТ"):"""

        client = replicate.Client(api_token=api_key)
        
        output = client.run(
            "meta/meta-llama-3-70b-instruct",
            input={
                "prompt": prompt,
                "max_tokens": 10,
                "temperature": 0.1,
                "top_p": 0.9
            }
        )
        
        # Обрабатываем ответ
        result = ""
        if hasattr(output, '__iter__') and not isinstance(output, str):
            for chunk in output:
                if isinstance(chunk, str):
                    result += chunk
                else:
                    result += str(chunk)
        elif isinstance(output, str):
            result = output
        else:
            result = str(output)
        
        result = result.strip().lower()
        print(f"🤖 AI анализ намерения: '{result}'")
        
        if "да" in result:
            return True
        elif "нет" in result:
            return False
        else:
            # Если AI дал неоднозначный ответ, проверяем по ключевым словам
            current_lower = current_message.lower()
            action_words = ["заказ", "хочу", "нужно", "можно", "готов", "давайте", "рассчитай", "сколько стоит", "цена"]
            return any(word in current_lower for word in action_words)
            
    except Exception as e:
        print(f"❌ Ошибка AI при анализе намерения: {str(e)}")
        current_lower = current_message.lower()
        action_words = ["заказ", "хочу", "нужно", "можно", "готов", "давайте", "рассчитай", "сколько стоит", "цена"]
        return any(word in current_lower for word in action_words)

def is_simple_greeting(message: str) -> bool:
    """Проверяет, является ли сообщение простым приветствием."""
    message_lower = message.lower()
    
    greetings = [
        "добрый день", "добрый вечер", "доброе утро",
        "здравствуйте", "привет", "здрасьте", "приветствую",
        "доброго времени суток", "доброй ночи", "добрый",
        "здравия", "приветик", "доброго"
    ]
    
    for greeting in greetings:
        if greeting in message_lower:
            clean_msg = message_lower.replace(greeting, "").strip()
            if not clean_msg or len(clean_msg.replace(" ", "")) < 3:
                return True
    
    return False

def is_order_request(message: str) -> bool:
    """Определяет, хочет ли клиент заказать (улучшенная версия)."""
    message_lower = message.lower()
    
    # Явные фразы
    if "заказ" in message_lower:
        if any(word in message_lower for word in ["хочу", "можно", "нужно", "готов", "давайте", "оформи"]):
            return True
    
    # Расчет стоимости
    if "рассчита" in message_lower or "сколько стоит" in message_lower or "цена" in message_lower:
        if any(word in message_lower for word in ["лестниц", "престиж", "элегант", "модел"]):
            return True
    
    # Указание параметров
    if "высот" in message_lower and ("мм" in message_lower or "метр" in message_lower):
        return True
    
    return False

def should_add_contacts_to_reply(user_message: str, bot_reply: str, is_first_message: bool = False) -> bool:
    """
    Определяет, нужно ли добавлять контакты к ответу.
    """
    user_lower = user_message.lower()
    reply_lower = bot_reply.lower()
    
    # Всегда добавляем контакты если:
    # 1. Клиент явно хочет заказать
    if is_order_request(user_message):
        return True
    
    # 2. Клиент спрашивает контакты
    if any(word in user_lower for word in ["телефон", "адрес", "контакт", "позвонить", "номер", "как связаться"]):
        return True
    
    # 3. В ответе уже просят контакты
    if any(phrase in reply_lower for phrase in [
        "укажите ваше имя и телефон",
        "назовите имя и телефон для связи",
        "мне нужны ваши контакты",
        "для расчета нужны ваши контакты"
    ]):
        return True
    
    # 4. Это завершение консультации И клиент проявлял интерес
    if len(bot_reply) > 300 and ("руб" in reply_lower or "стоимость" in reply_lower):
        if "заказ" in user_lower or "хочу" in user_lower:
            return True
    
    # Не добавляем контакты если:
    # 1. Это просто приветствие
    if is_simple_greeting(user_message):
        return False
    
    # 2. Это простой информационный вопрос
    if (len(bot_reply) < 200 and 
        "?" in user_message and 
        not is_order_request(user_message)):
        return False
    
    return False

def generate_bot_reply(api_key: str, message: str, is_first_in_session: bool = False, 
                      has_name: bool = False, has_phone: bool = False,
                      telegram_sent: bool = False, last_product: str = None,
                      opening_height: str = None) -> str:
    """Генерация ответа бота через Replicate API."""
    try:
        print(f"\n🤖 Генерация ответа AI")
        print(f"   Сообщение: '{message}'")
        print(f"   Первое в сессии: {is_first_in_session}")
        print(f"   Есть имя: {has_name}, Есть телефон: {has_phone}")
        print(f"   Telegram отправлен: {telegram_sent}")
        print(f"   Контекст товара: {last_product or 'Нет контекста'}")
        
        message_lower = message.lower()
        
        # 1. ОЧЕНЬ простые случаи обрабатываем сразу
        if is_simple_greeting(message_lower):
            if is_first_in_session:
                return "Здравствуйте! Меня зовут Алина, я помощник в подборе лестниц. Чем могу вам помочь?"
            else:
                return "Чем могу помочь?"
        
        # 2. Специфичные вопросы - закомментированы, всё через AI
        # is_opening, opening_response = handle_opening_question(message)
        # if is_opening:
        #     return opening_response
        # 
        # is_material, material_response = handle_material_question(message)
        # if is_material:
        #     return material_response
        # 
        # is_color, color_response = handle_color_question(message)
        # if is_color:
        #     return color_response
        # 
        # is_installation, installation_response = handle_installation_question(message)
        # if is_installation:
        #     return installation_response
        # 
        # is_delivery, delivery_response = handle_delivery_question(message)
        # if is_delivery:
        #     return delivery_response
        # 
        # is_payment, payment_response = handle_payment_question(message)
        # if is_payment:
        #     return payment_response
        # 
        # is_timing, timing_response = handle_timing_question(message)
        # if is_timing:
        #     return timing_response
        
        # 3. Проверяем, явный ли это запрос на заказ
        basic_order_check = is_order_request(message)
        
        # 4. ВСЁ ОСТАЛЬНОЕ отдаем AI с полным контекстом
        system_prompt = create_system_prompt()
        
        # Формируем контекст для AI
        context_lines = []
        
        # Информация о сессии
        context_lines.append(f"📊 СТАТУС СЕССИИ:")
        context_lines.append(f"   • {'Начало диалога - представься' if is_first_in_session else 'Диалог уже идет - не представляйся'}")
        context_lines.append(f"   • {'✅ Есть имя клиента' if has_name else '❌ Имя не указано'}")
        context_lines.append(f"   • {'✅ Есть телефон клиента' if has_phone else '❌ Телефон не указан'}")
        
        if telegram_sent:
            context_lines.append(f"   • ✅ ЗАЯВКА УЖЕ ОТПРАВЛЕНА МЕНЕДЖЕРУ")
            context_lines.append(f"   • Клиент продолжает диалог после отправки заявки - отвечай на вопросы как обычно, не предлагай оформить заказ повторно")
        else:
            context_lines.append(f"   • 📝 Заявка еще не отправлена")
        
        # Контекст товара
        if last_product:
            context_lines.append(f"\n📋 ИСТОРИЯ ТОВАРА:")
            context_lines.append(f"   • Ранее обсуждалась модель: {last_product}")
        
        # ВЫСОТА ПРОЕМА (важно!)
        if opening_height:
            context_lines.append(f"\n📏 ВЫСОТА ПРОЕМА (УЖЕ УКАЗАНА): {opening_height}")
            context_lines.append(f"   • НЕ СПРАШИВАЙ высоту повторно!")
            context_lines.append(f"   • Используй эту высоту для расчета стоимости")
        
        # Анализ текущего сообщения
        context_lines.append(f"\n🎯 АНАЛИЗ ТЕКУЩЕГО СООБЩЕНИЯ:")
        context_lines.append(f"   • Сообщение: \"{message}\"")
        
        # Определяем тип сообщения
        msg_type = []
        if basic_order_check:
            msg_type.append("запрос на заказ/расчет")
        if "цена" in message_lower or "стоимость" in message_lower or "сколько" in message_lower:
            msg_type.append("вопрос о цене")
        if "высот" in message_lower or "проем" in message_lower:
            msg_type.append("указаны параметры проема")
        
        if msg_type:
            context_lines.append(f"   • Тип: {', '.join(msg_type)}")
        
        context_section = "\n".join(context_lines)
        
        # ОСНОВНОЙ ПРОМПТ ДЛЯ AI
        full_prompt = f"""{system_prompt}

================================================================================
КОНТЕКСТ ДЛЯ AI (ЭТО ВИДИШЬ ТОЛЬКО ТЫ):
{context_section}
================================================================================

🧠 ТВОЯ ЗАДАЧА КАК АЛИНЫ (менеджер компании по лестницам):

1. ПРОАНИЛИЗИРУЙ сообщение клиента и контекст выше
2. ОПРЕДЕЛИ что хочет клиент:
   - ✅ ЗАКАЗАТЬ/РАССЧИТАТЬ стоимость → действуй по шагу A
   - 📋 УЗНАТЬ информацию о моделях/ценах → действуй по шагу B
   - 🔧 УТОЧНИТЬ детали → действуй по шагу C

ШАГ A: ЕСЛИ КЛИЕНТ ХОЧЕТ ЗАКАЗАТЬ ИЛИ РАССЧИТАТЬ
{"1. Клиент явно хочет заказать (есть слова 'заказать', 'рассчитать' и т.д.)" if basic_order_check else ""}
{"2. Используй контекст модели если клиент не уточнил: '{last_product}'" if last_product and not any(word in message_lower for word in ["престиж", "элегант", "мини"]) else ""}
3. ДЕЙСТВИЯ:
   • Подтверди модель если указана
   • Если модель не ясна - УТОЧНИ ("Какую модель лестницы вы рассматриваете?")
   • ПОПРОСИ параметры: "Для расчета укажите высоту от пола до пола (в мм)"
   • ПОПРОСИ контакты: "Оставьте ваше имя и телефон для связи"

ШАГ B: ЕСЛИ КЛИЕНТ СПРАШИВАЕТ ИНФОРМАЦИЮ
1. Дай ПОЛНЫЙ ответ используя каталог ниже
2. Упомяни материалы и цвета если спрашивают
3. Предложи рассчитать стоимость если уместно

ШАГ C: ЕСЛИ КЛИЕНТ УТОЧНЯЕТ ДЕТАЛИ
{"1. Клиент уточняет детали модели: '{last_product}'" if last_product else ""}
1. Ответь на вопрос используя каталог
2. Помоги определиться с выбором
3. Предложи следующий шаг (расчет или доп. информация)

{'⚠️ ВАЖНО: Заявка клиента уже отправлена менеджеру! Отвечай на вопросы как обычно, НЕ предлагай оформить заказ повторно.' if telegram_sent else ''}

================================================================================
КЛИЕНТ ПИШЕТ: "{message}"

ТВОЙ ОТВЕТ (Алина):
{"1. Представься: 'Здравствуйте! Меня зовут Алина.'" if is_first_in_session else "1. НЕ представляйся снова"}
2. Ответь согласно анализу выше
3. Будь экспертом, но дружелюбной
4. Используй смайлики если уместно
5. {"Упомяни скидки/акции если спрашивают про цены" if "цена" in message_lower or "стоимость" in message_lower else ""}

ОТВЕТ:"""
        
        # Используем AI
        client = replicate.Client(api_token=api_key)
        
        output = client.run(
            "meta/meta-llama-3-70b-instruct",
            input={
                "prompt": full_prompt,
                "max_tokens": 1000,
                "temperature": 0.7,
                "top_p": 0.9
            }
        )
        
        # Обрабатываем ответ
        result = ""
        if hasattr(output, '__iter__') and not isinstance(output, str):
            for chunk in output:
                if isinstance(chunk, str):
                    result += chunk
                else:
                    result += str(chunk)
        elif isinstance(output, str):
            result = output
        else:
            result = str(output)
        
        result = result.strip()
        print(f"   Ответ AI (сырой): '{result[:200]}...'")
        
        # Очищаем ответ если нужно
        if not result or len(result) < 10:
            result = "Извините, не удалось обработать запрос. Пожалуйста, позвоните нам по телефону 8-9XX-XXX-XX-XX для консультации."
        
        # Убираем повторные приветствия
        if not is_first_in_session:
            result = re.sub(r'^Здравствуйте[!\.]?\s*', '', result)
            result = re.sub(r'^Добрый день[!\.]?\s*', '', result)
            result = re.sub(r'^Меня зовут Алина[!\.]?\s*', '', result)
            result = re.sub(r'^Привет[!\.]?\s*', '', result)      # добавить
            result = re.sub(r'^Hello[!\.]?\s*', '', result)       # добавить
            result = re.sub(r'^😊\s*', '', result)                # добавить (убирает смайлик)
        
        return result
            
    except Exception as e:
        print(f"❌ Ошибка AI: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        
        # Fallback на случай ошибки AI
        message_lower = message.lower()
        
        if "адрес" in message_lower or "телефон" in message_lower:
            return "Наш адрес: Московская область, г. [Ваш город], ул. [Ваша улица]. Телефон: 8-9XX-XXX-XX-XX"
        elif telegram_sent:
            return "Извините за техническую неполадку. Чем еще могу помочь? Если есть вопросы по моделям или ценам, спрашивайте!"
        elif "заказ" in message_lower or "рассчита" in message_lower:
            if last_product:
                return f"Для расчета стоимости {last_product} укажите высоту от пола до пола (в мм) и оставьте ваше имя и телефон для связи."
            else:
                return "Для расчета стоимости укажите, пожалуйста, высоту от пола до пола (в мм) и модель лестницы, которая вас интересует. Также оставьте ваше имя и телефон для связи."
        else:
            return "Для консультации по лестницам позвоните по телефону 8-9XX-XXX-XX-XX"

def extract_name_with_ai(api_key: str, message: str) -> str:
    """
    Использует AI для извлечения имени человека из сообщения.
    """
    try:
        prompt = f"""Определи, есть ли в сообщении имя человека. Если есть - верни ТОЛЬКО имя. Если нет - верни "not_found".

ВОТ ПРАВИЛА:
1. Имя - это личное имя человека (Анна, Иван, Мария, Дмитрий и т.д.)
2. НЕ имя: названия моделей лестниц (престиж, элегант, мини)
3. НЕ имя: общие слова (привет, здравствуйте, хочу, заказать и т.д.)
4. Если сомневаешься - верни "not_found"

Примеры:
Сообщение: "Меня зовут Анна, хочу заказать лестницу" → Ответ: "Анна"
Сообщение: "Хочу заказать Престиж" → Ответ: "not_found"
Сообщение: "Иван, 89161234567" → Ответ: "Иван"
Сообщение: "Сколько стоит Элегант" → Ответ: "not_found"

Сообщение: "{message}"

Ответ (только имя или "not_found"):"""

        client = replicate.Client(api_token=api_key)
        
        output = client.run(
            "meta/meta-llama-3-70b-instruct",
            input={
                "prompt": prompt,
                "max_tokens": 20,
                "temperature": 0.1,
                "top_p": 0.9
            }
        )
        
        # Обрабатываем ответ
        result = ""
        if hasattr(output, '__iter__') and not isinstance(output, str):
            for chunk in output:
                if isinstance(chunk, str):
                    result += chunk
                else:
                    result += str(chunk)
        elif isinstance(output, str):
            result = output
        else:
            result = str(output)
        
        result = result.strip().lower()
        print(f"🔍 AI анализ имени из '{message}': получил '{result}'")
        
        # Очищаем ответ
        if result in ['not_found', 'none', 'null', 'нет', 'no name', '']:
            return None
        
        # Удаляем кавычки и лишние символы
        result = re.sub(r'["\'\.,!?]', '', result).strip()
        
        if not result:
            return None
        
        # Фильтруем названия моделей
        model_keywords = [
            'престиж', 'элегант', 'мини', 'комфорт',
            'лестниц', 'ступен', 'модуль', 'каркас'
        ]
        
        if any(model in result for model in model_keywords):
            print(f"⚠️ Отфильтровано: '{result}' похоже на модель лестницы")
            return None
        
        # Проверяем что это похоже на имя
        if not re.match(r'^[А-ЯЁа-яё\-]+$', result):
            return None
        
        # Капитализируем первую букву
        if '-' in result:
            parts = result.split('-')
            result = '-'.join([part.capitalize() for part in parts])
        else:
            result = result.capitalize()
        
        if len(result) < 2 or len(result) > 30:
            return None
        
        return result if result else None
            
    except Exception as e:
        print(f"❌ Ошибка AI при извлечении имени: {str(e)}")
        return None

def check_interesting_application(text: str):
    """
    Проверяем, является ли сообщение заявкой на заказ/расчет.
    """
    t = text.lower()
    
    # РАСШИРЕННЫЙ СПИСОК КЛЮЧЕВЫХ СЛОВ
    order_keywords = [
        "заказать", "заказ", "оформить", "хочу", "можно", "мне нужно",
        "нужно", "готов", "давайте", "интересует", "интересуюсь",
        "престиж", "элегант", "мини", "лестниц", "модель",
        "стоит", "цена", "прайс", "стоимость", "сколько",
        "высот", "проем", "размер", "параметр", "мм", "метр",
        "рассчита", "посчита", "подбери", "подбор"
    ]
    
    contact_keywords = ["имя", "зовут", "телефон", "телефоне", "номер", "позвонить", "мне зовут", "контакт"]
    
    has_order = any(keyword in t for keyword in order_keywords)
    has_contacts = any(keyword in t for keyword in contact_keywords)
    
    print(f"🔍 Проверка заявки: '{text[:100]}...'")
    print(f"   Слова заказа: {has_order}")
    print(f"   Контактные слова: {has_contacts}")
    
    return has_order or has_contacts
