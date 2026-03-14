import os
import sys
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from chatbot_logic import generate_bot_reply, extract_name_with_ai
from telegram_utils import send_to_telegram, send_incomplete_to_telegram, send_complete_application_to_telegram
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta
import requests
from telegram_bot_handler import telegram_polling

# Загружаем переменные окружения
load_dotenv()

def validate_environment():
    """Проверяем обязательные переменные окружения."""
    print("🔍 Проверка переменных окружения...")
    
    required_vars = ["REPLICATE_API_TOKEN"]
    missing = []
    
    for var_name in required_vars:
        value = os.getenv(var_name)
        
        if not value or value.strip() == "":
            missing.append(var_name)
            print(f"   ❌ {var_name}: ОТСУТСТВУЕТ")
        else:
            if len(value) > 8:
                masked_value = value[:4] + "..." + value[-4:]
            else:
                masked_value = "***"
            print(f"   ✅ {var_name}: {masked_value}")
    
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "@superlestnica_bot")
    if not TELEGRAM_CHAT_ID:
        print(f"   ⚠️ TELEGRAM_CHAT_ID: не настроен (может быть пустым)")
    else:
        print(f"   ✅ TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID}")
    
    if missing:
        print(f"\n❌ Отсутствуют обязательные переменные: {missing}")
        return False
    
    print("✅ Все обязательные переменные окружения присутствуют")
    return True

print("\n" + "="*60)
print("🚀 Запуск LESTNITSA Chatbot API")
print("="*60)

env_valid = validate_environment()
if not env_valid:
    print("\n❌ Приложение остановлено")
    sys.exit(1)

# Создаем приложение FastAPI
app = FastAPI(
    title="LESTNITSA Chatbot API",
    description="Чат-бот для компании по производству и продаже лестниц",
    version="1.0.0"
)

# Настраиваем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем папку static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Получаем переменные окружения
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "@superlestnica_bot")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")

# Хранилище сессий пользователей
user_sessions = {}

# Константы для работы с лестницами
PRODUCT_KEYWORDS = {
    'престиж': ['престиж', 'prestige', 'шаг 225', 'классическая'],
    'престиж комфорт': ['престиж комфорт', 'комфорт', 'шаг 190'],
    'престиж мини': ['престиж мини', 'мини', 'гусиный шаг', 'компактная'],
    'элегант': ['элегант', 'elegant', 'шаг 230', 'изящная'],
    'элегант комфорт': ['элегант комфорт', 'элегант комфорт', 'шаг 190'],
    'каркас': ['каркас', 'металлический', 'для отделки', 'основа'],
    'ступени': ['ступени', 'ступень', 'хвоя', 'бук', 'сосна', 'прямая ступень', 'угловая'],
    'поручни': ['поручень', 'перила', 'ограждение', 'балясины'],
    'комплектующие': ['модуль', 'подпорка', 'фланец', 'крепеж']
}

# Ключевые слова для определения материалов
MATERIAL_KEYWORDS = {
    'хвоя': ['хвоя', 'сосна', 'сосновые'],
    'бук': ['бук', 'буковые']
}

# Ключевые слова для определения цветов
COLOR_KEYWORDS = {
    'слоновая кость': ['слоновая кость', 'ral 1015', 'бежевый', 'кремовый'],
    'черный': ['черный', 'ral 9005', 'матовый черный'],
    'алюминиевый': ['алюминиевый', 'ral 9006', 'металлик', 'серебристый']
}

def get_fallback_response(message: str) -> str:
    """Простая логика ответа когда AI недоступен."""
    message_lower = message.lower()
    
    # Приветствие
    if any(greet in message_lower for greet in ["добрый", "здравствуйте", "привет"]):
        return "Здравствуйте! Меня зовут Алина, я помогу подобрать лестницу для вашего дома. Какая модель вас интересует?"
    
    # Вопрос о ценах
    elif any(word in message_lower for word in ["цена", "стоимость", "сколько стоит"]):
        return """Цена зависит от модели и комплектации:

🏠 ПРЕСТИЖ:
• Прямая: от 74 400 руб
• Поворотная: от 85 000 руб

🏠 ЭЛЕГАНТ:
• Прямая: от 87 200 руб
• Поворотная: от 95 000 руб

🪜 СТУПЕНИ:
• Прямая (хвоя): 3 500 руб/шт
• Прямая (бук): 2 580 руб/шт

Для точного расчета напишите высоту вашего проема (в мм)."""
    
    # Вопрос о материалах
    elif any(word in message_lower for word in ["материал", "дерево", "хвоя", "бук"]):
        return """Мы используем два вида древесины:

🌲 ХВОЯ (сосна):
• Доступная цена
• Светлый оттенок
• Мягкая древесина

🌳 БУК:
• Плотная и износостойкая
• Красивая текстура
• Дольше служит

Какой вариант вас интересует?"""
    
    # Вопрос о цветах
    elif any(word in message_lower for word in ["цвет", "ral", "покраска"]):
        return """Доступные цвета RAL:

🎨 RAL 1015 (слоновая кость)
🎨 RAL 9005 (черный матовый)
🎨 RAL 9006 (алюминиевый металлик)

Какой цвет предпочитаете?"""
    
    # Вопрос о доставке
    elif any(word in message_lower for word in ["доставк", "транспорт", "отправк"]):
        return "🚚 Доставляем по всей России транспортными компаниями. Стоимость зависит от габаритов и вашего региона. Отправляем в день готовности заказа."
    
    # Вопрос об адресе или контактах
    elif any(word in message_lower for word in ["адрес", "где находитесь", "локация", "телефон"]):
        return "📍 Наш адрес: Московская область, г.о. Мытищи, ул. Хлебозаводская, влд. 4А, стр. 1\n📞 Телефон: +7 (495) 109-33-88\n⏰ Пн-Пт 9:00–18:00"
    
    # Вопрос о сроках
    elif any(word in message_lower for word in ["срок", "изготовление", "когда будет"]):
        return "⏱️ Сроки изготовления:\n• Прямые лестницы: 5-7 рабочих дней\n• Поворотные: 10-15 рабочих дней\n• Каркасы: 7-10 рабочих дней"
    
    # Запрос на расчет/заказ
    elif any(word in message_lower for word in ["рассчита", "заказ", "хочу заказать"]):
        return "Для расчета стоимости лестницы мне нужны параметры проема: высота от пола до пола (в мм). Также укажите, какая модель вас интересует, и оставьте ваш телефон для связи."
    
    # Если клиент указывает высоту
    elif "высот" in message_lower and ("мм" in message_lower or "метр" in message_lower):
        return "Отлично! Для точного расчета также нужны длина и ширина проема. Если знаете эти параметры, напишите их. И оставьте ваш телефон, чтобы менеджер мог связаться с вами."
    
    # Общий ответ
    else:
        return "Здравствуйте! Меня зовут Алина, я помогу подобрать лестницу для вашего дома. Какая модель вас интересует? У нас есть Престиж, Элегант, Престиж Мини и другие варианты."

def is_contact_collection_request(bot_reply: str) -> bool:
    """Проверяет, просит ли бот контакты в ответе."""
    reply_lower = bot_reply.lower()
    
    contact_phrases = [
        "для расчета мне нужно ваше имя и телефон",
        "оставьте ваше имя и телефон для связи",
        "укажите имя и телефон",
        "мне нужны ваши контакты",
        "ваше имя и номер телефона",
        "предоставьте имя и телефон",
        "оставьте контактные данные"
    ]
    
    for phrase in contact_phrases:
        if phrase in reply_lower:
            return True
    
    return False

def cleanup_old_sessions():
    """Очистка старых сессий."""
    try:
        now = datetime.now()
        to_delete = []
        
        for session_id, session_data in list(user_sessions.items()):
            session_age = now - session_data['created_at']
            
            if (session_age > timedelta(minutes=10) and 
                not session_data.get('telegram_sent', False) and 
                session_data.get('phone') and 
                session_data.get('name')):
                
                print(f"⏰ ТАЙМАУТ 10 минут: отправляем неполную заявку")
                
                full_text = "\n".join(session_data.get('text_parts', []))
                send_incomplete_to_telegram(
                    full_text, 
                    session_data.get('name'),
                    session_data.get('phone'),
                    session_data.get('product_interest')
                )
                session_data['telegram_sent'] = True
                session_data['incomplete_sent'] = True
            
            if session_age > timedelta(hours=2):
                to_delete.append(session_id)
        
        for session_id in to_delete:
            del user_sessions[session_id]
    except Exception as e:
        print(f"❌ Ошибка при очистке сессий: {e}")

from typing import Dict, Any, Optional  # добавьте Optional в импорт в начале файла

def extract_product_from_message(message: str) -> Optional[str]:
    """Извлекает упоминание товара из сообщения."""
    message_lower = message.lower()
    
    for product, keywords in PRODUCT_KEYWORDS.items():
        if any(keyword in message_lower for keyword in keywords):
            return product
    
    return None

def extract_material_from_message(message: str) -> Optional[str]:
    """Извлекает упоминание материала из сообщения."""
    message_lower = message.lower()
    
    for material, keywords in MATERIAL_KEYWORDS.items():
        if any(keyword in message_lower for keyword in keywords):
            return material
    
    return None

def extract_color_from_message(message: str) -> Optional[str]:
    """Извлекает упоминание цвета из сообщения."""
    message_lower = message.lower()
    
    for color, keywords in COLOR_KEYWORDS.items():
        if any(keyword in message_lower for keyword in keywords):
            return color
    
    return None

def extract_opening_height(message: str) -> Optional[str]:
    """Извлекает высоту проема из сообщения."""
    message_lower = message.lower()
    
    # Ищем высоту в мм
    mm_pattern = r'(\d+)\s*мм'
    mm_matches = re.findall(mm_pattern, message_lower)
    if mm_matches:
        return f"{mm_matches[0]} мм"
    
    # Ищем высоту в метрах
    m_pattern = r'(\d+[.,]?\d*)\s*метр'
    m_matches = re.findall(m_pattern, message_lower)
    if m_matches:
        height = float(m_matches[0].replace(',', '.')) * 1000
        return f"{int(height)} мм"
    
    # Ищем просто числа, которые могут быть высотой (4-значные числа)
    numbers = re.findall(r'\b(\d{4})\b', message_lower)
    if numbers:
        return f"{numbers[0]} мм"
    
    return None

def extract_contacts_from_message(message: str, session: Dict[str, Any]):
    """Извлекает контакты и информацию о лестнице из сообщения."""
    message_lower = message.lower()
    
    # ===== ПОИСК ТЕЛЕФОНА =====
    phone_patterns = [
        r'\b8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b',
        r'\b\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b',
        r'\b7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b',
    ]
    
    phone_matches = []
    for pattern in phone_patterns:
        matches = re.findall(pattern, message)
        if matches:
            phone_matches.extend(matches)
            break
    
    if phone_matches and not session.get('phone'):
        raw_phone = phone_matches[0]
        clean_phone = re.sub(r'\D', '', raw_phone)
        
        if len(clean_phone) == 10:
            clean_phone = '7' + clean_phone
        elif len(clean_phone) == 11 and clean_phone.startswith('8'):
            clean_phone = '7' + clean_phone[1:]
        
        if 10 <= len(clean_phone) <= 11:
            session['phone'] = clean_phone
            print(f"📞 Найден телефон: {raw_phone} → {session['phone']}")
    
    # ===== ПОИСК ИМЕНИ =====
    temp_name = None
    
    russian_names = re.findall(r'\b[А-ЯЁ][а-яё]{1,20}\b', message)
    
    common_russian_names = [
        'анна', 'мария', 'елена', 'ольга', 'наталья', 'ирина', 'светлана',
        'александра', 'татьяна', 'юлия', 'евгения', 'дарья', 'екатерина',
        'виктория', 'иван', 'алексей', 'сергей', 'андрей', 'дмитрий', 'михаил',
        'владимир', 'павел', 'максим', 'николай', 'евгений', 'артем', 'антон',
        'вадим', 'рома', 'кирилл', 'игорь', 'вадим'
    ]
    
    # Слова, которые не являются именами (названия моделей)
    product_words = ['престиж', 'элегант', 'комфорт', 'мини', 'каркас', 'ступени', 'модуль']
    
    for name in russian_names:
        name_lower = name.lower()
        
        is_product = any(prod in name_lower for prod in product_words)
        is_common_name = name_lower in common_russian_names
        is_near_phone = phone_matches and (abs(message.find(name) - message.find(phone_matches[0])) < 30)
        
        if (is_common_name and not is_product) or (is_near_phone and not is_product):
            temp_name = name
            print(f"👤 Найдено возможное имя в сообщении: {temp_name}")
            break
    
    if temp_name and temp_name.lower() not in ['привет', 'здравствуйте', 'добрый', 'пока', 'спасибо']:
        session['name'] = temp_name
        print(f"✅ Обновлено имя в сессии: {session['name']}")
    
    # Используем AI для поиска имени, если не нашли регулярками
    if (not session.get('name') or session.get('name', '').lower() in ['привет', 'здравствуйте', 'добрый']) and REPLICATE_API_TOKEN and len(message.strip()) > 3:
        try:
            print(f"🔍 Использую AI для поиска имени в: '{message[:30]}...'")
            from chatbot_logic import extract_name_with_ai
            found_name = extract_name_with_ai(REPLICATE_API_TOKEN, message)
            
            if found_name and found_name.lower() not in ['привет', 'здравствуйте', 'добрый']:
                session['name'] = found_name
                print(f"✅ AI определил/исправил имя: {session['name']}")
        except Exception as e:
            print(f"⚠️ Ошибка AI при извлечении имени: {e}")
    
    # ===== ОПРЕДЕЛЕНИЕ МОДЕЛИ ЛЕСТНИЦЫ =====
    detected_product = extract_product_from_message(message)
    if detected_product:
        session['product_interest'] = detected_product
        session['product_mentioned'] = True
        print(f"📋 Определена модель: {detected_product}")
    
    # ===== ОПРЕДЕЛЕНИЕ МАТЕРИАЛА =====
    detected_material = extract_material_from_message(message)
    if detected_material:
        session['material_interest'] = detected_material
        print(f"🪵 Определен материал: {detected_material}")
    
    # ===== ОПРЕДЕЛЕНИЕ ЦВЕТА =====
    detected_color = extract_color_from_message(message)
    if detected_color:
        session['color_interest'] = detected_color
        print(f"🎨 Определен цвет: {detected_color}")
    
    # ===== ОПРЕДЕЛЕНИЕ ВЫСОТЫ ПРОЕМА =====
    detected_height = extract_opening_height(message)
    if detected_height:
        session['opening_height'] = detected_height
        print(f"📏 Определена высота: {detected_height}")

def get_product_interest_from_history(session: Dict[str, Any]) -> Optional[str]:
    """Определяет интересующую модель из истории диалога."""
    if session.get('product_interest'):
        return session['product_interest']
    
    for msg in reversed(session.get('text_parts', [])):
        product = extract_product_from_message(msg)
        if product:
            return product
    
    return None

@app.post("/chat")
async def chat_endpoint(request: Request):
    """Основной endpoint для общения с ботом."""
    print(f"\n{'='*60}")
    print(f"🔍 /chat endpoint вызван")
    print(f"{'='*60}")
    
    try:
        data = await request.json()
        user_message = data.get("message", "")
        user_ip = request.client.host
        
        print(f"👤 IP: {user_ip}")
        print(f"💬 Сообщение: '{user_message[:50]}...'" if len(user_message) > 50 else f"💬 Сообщение: '{user_message}'")
        
        cleanup_old_sessions()
        
        if user_ip not in user_sessions:
            user_sessions[user_ip] = {
                'created_at': datetime.now(),
                'name': None,
                'phone': None,
                'stage': 'consultation',
                'text_parts': [],
                'telegram_sent': False,
                'incomplete_sent': False,
                'message_count': 0,
                'contacts_provided': False,
                'product_mentioned': False,
                'product_interest': None,        # интересующая модель (престиж, элегант и т.д.)
                'material_interest': None,       # материал (хвоя, бук)
                'color_interest': None,           # цвет (слоновая кость, черный, алюминий)
                'opening_height': None,           # высота проема в мм
                'opening_length': None,           # длина проема (опционально)
                'opening_width': None,            # ширина проема (опционально)
                'staircase_type': None,           # тип (прямая, поворотная, разворотная)
                'questions_answered': []          # ответы на уточняющие вопросы
            }
        
        session = user_sessions[user_ip]
        session['text_parts'].append(user_message)
        session['message_count'] += 1
        
        full_conversation = "\n".join(session['text_parts']).lower()
        
        # Проверяем, упоминались ли товары в диалоге
        all_product_keywords = [keyword for keywords in PRODUCT_KEYWORDS.values() for keyword in keywords]
        if any(keyword in full_conversation for keyword in all_product_keywords):
            session['product_mentioned'] = True
            print(f"🔍 В диалоге упоминались модели лестниц")
        
        extract_contacts_from_message(user_message, session)
        
        product_interest = get_product_interest_from_history(session)
        
                # ===== ОТПРАВКА В TELEGRAM =====
        telegram_was_sent_now = False

        if session.get('name') and session.get('phone') and not session.get('telegram_sent', False):
            print(f"🚨 ПРОВЕРКА ОТПРАВКИ В TELEGRAM:")
            print(f"   👤 Имя: {session['name']}")
            print(f"   📞 Телефон: {session['phone']}")
            
            # Получаем историю диалога для анализа
            full_conversation = "\n".join(session.get('text_parts', []))
            
            # Используем AI для определения намерения
            order_intent = False
            if REPLICATE_API_TOKEN:
                try:
                    from chatbot_logic import detect_order_intent_with_ai
                    order_intent = detect_order_intent_with_ai(
                        REPLICATE_API_TOKEN, 
                        full_conversation, 
                        user_message
                    )
                    print(f"🤖 AI определил намерение заказа: {order_intent}")
                except Exception as e:
                    print(f"⚠️ Ошибка AI при анализе намерения: {e}")
                    # Fallback на простую проверку
                    message_lower = user_message.lower()
                    order_intent = any(word in message_lower for word in [
                        'заказ', 'хочу', 'нужно', 'можно', 'готов', 'давайте', 
                        'рассчита', 'сколько стоит', 'цена', 'купить', 'оформить'
                    ])
            else:
                # Если AI недоступен, используем простую проверку
                message_lower = user_message.lower()
                order_intent = any(word in message_lower for word in [
                    'заказ', 'хочу', 'нужно', 'можно', 'готов', 'давайте', 
                    'рассчита', 'сколько стоит', 'цена', 'купить', 'оформить'
                ])
            
            # Определяем, упоминались ли товары в диалоге
            product_mentioned = session.get('product_mentioned', False) or session.get('product_interest') is not None
            
            # Определяем, указаны ли параметры
            has_params = session.get('opening_height') is not None
            
            # Отправляем заявку если есть намерение И (товар упоминался ИЛИ есть параметры)
            should_send = order_intent and (product_mentioned or has_params)
            
            if should_send:
                print(f"🚨 ОТПРАВЛЯЕМ ЗАЯВКУ В TELEGRAM!")
                print(f"   Намерение: {order_intent}")
                print(f"   Товар упоминался: {product_mentioned}")
                print(f"   Есть параметры: {has_params}")
                
                full_conversation = "\n".join(session.get('text_parts', []))
                
                # Сохраняем информацию о товаре для отправки
                if session.get('product_interest'):
                    session['product_type'] = session['product_interest']
                
                # Формируем параметры для отправки
                params_list = []
                if session.get('opening_height'):
                    params_list.append(f"Высота: {session['opening_height']}")
                if session.get('material_interest'):
                    params_list.append(f"Материал: {session['material_interest']}")
                if session.get('color_interest'):
                    params_list.append(f"Цвет: {session['color_interest']}")
                if session.get('staircase_type'):
                    params_list.append(f"Тип: {session['staircase_type']}")
                
                if params_list:
                    session['product_params'] = "\n".join(params_list)
                
                try:
                    success = send_complete_application_to_telegram(session, full_conversation)
                    
                    if success:
                        session['telegram_sent'] = True
                        session['stage'] = 'completed'
                        session['contacts_provided'] = True
                        telegram_was_sent_now = True
                        print(f"✅ Заявка отправлена в Telegram")
                        
                        # Подтверждение клиенту будет отправлено ниже
                        
                    else:
                        print(f"⚠️ Ошибка отправки в Telegram")
                except Exception as e:
                    print(f"❌ Исключение при отправке в Telegram: {e}")
            else:
                print(f"ℹ️ Контакты есть, но нет явного намерения заказать")
                print(f"   Намерение: {order_intent}, Товар: {product_mentioned}, Параметры: {has_params}")
                session['contacts_provided'] = True
        
        # ===== ГЕНЕРАЦИЯ ОТВЕТА БОТА =====
        bot_reply = ""
        is_first_in_session = (session['message_count'] == 1)
        
        # Если заявка ТОЛЬКО ЧТО отправлена - показываем подтверждение
        if telegram_was_sent_now:
            if session.get('name'):
                bot_reply = f"✅ Спасибо, {session['name']}! Ваша заявка передана менеджеру. С вами свяжутся для уточнения деталей и расчета стоимости.\n\n📞 Телефон компании: +7 (495) 109-33-88"
            else:
                bot_reply = "✅ Спасибо! Ваша заявка передана менеджеру. С вами свяжутся для уточнения деталей и расчета стоимости.\n\n📞 Телефон компании: +7 (495) 109-33-88"
        
        # Если заявка уже была отправлена, НО клиент продолжает диалог - используем AI
        elif session.get('telegram_sent', False):
            print("🤖 Заявка уже отправлена, но продолжаем диалог...")
            
            if REPLICATE_API_TOKEN and len(REPLICATE_API_TOKEN) > 20:
                try:
                    ai_task = asyncio.create_task(
                        asyncio.to_thread(
                            generate_bot_reply,
                            REPLICATE_API_TOKEN,
                            user_message,
                            is_first_in_session,
                            bool(session['name']),
                            bool(session['phone']),
                            True,  # telegram_sent = True (для контекста)
                            product_interest
                        )
                    )
                    
                    try:
                        bot_reply = await asyncio.wait_for(ai_task, timeout=8.0)
                        print(f"✅ AI ответ сгенерирован за <8 сек")
                    except asyncio.TimeoutError:
                        print(f"⚠️ Таймаут AI (8 сек), используем fallback")
                        ai_task.cancel()
                        bot_reply = get_fallback_response(user_message)
                        
                except Exception as e:
                    print(f"❌ Ошибка при вызове AI: {str(e)}")
                    bot_reply = get_fallback_response(user_message)
            else:
                bot_reply = get_fallback_response(user_message)
        
        # Обычный режим (заявка еще не отправлена)
        elif REPLICATE_API_TOKEN and len(REPLICATE_API_TOKEN) > 20:
            print("🤖 Использую AI для генерации ответа...")
            
            try:
                ai_task = asyncio.create_task(
                    asyncio.to_thread(
                        generate_bot_reply,
                        REPLICATE_API_TOKEN,
                        user_message,
                        is_first_in_session,
                        bool(session['name']),
                        bool(session['phone']),
                        False,  # telegram_sent = False
                        product_interest
                    )
                )
                
                try:
                    bot_reply = await asyncio.wait_for(ai_task, timeout=8.0)
                    print(f"✅ AI ответ сгенерирован за <8 сек")
                except asyncio.TimeoutError:
                    print(f"⚠️ Таймаут AI (8 сек), используем fallback")
                    ai_task.cancel()
                    bot_reply = get_fallback_response(user_message)
                
                if is_contact_collection_request(bot_reply):
                    session['stage'] = 'contact_collection'
                    print("📝 AI запросил контакты")
                    
            except Exception as e:
                print(f"❌ Ошибка при вызове AI: {str(e)}")
                bot_reply = get_fallback_response(user_message)
        
        # Fallback если AI недоступен
        else:
            print("⚠️ AI недоступен, использую простую логику")
            bot_reply = get_fallback_response(user_message)
        
        print(f"📊 СОСТОЯНИЕ СЕССИИ:")
        print(f"   👤 Имя: {'✅ ' + session['name'] if session['name'] else '❌ Нет'}")
        print(f"   📞 Телефон: {'✅ ' + str(session['phone']) if session['phone'] else '❌ Нет'}")
        print(f"   📨 Отправлено в Telegram: {'✅' if session.get('telegram_sent') else '❌'}")
        print(f"   🪜 Модель: {session.get('product_interest', '❌ Не определена')}")
        print(f"   📏 Высота проема: {session.get('opening_height', '❌ Не указана')}")
        
        print(f"🤖 Ответ бота: '{bot_reply[:100]}...'" if len(bot_reply) > 100 else f"🤖 Ответ бота: '{bot_reply}'")
        print("="*40)
        
        return {"reply": bot_reply}
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА В /chat: {e}")
        import traceback
        traceback.print_exc()
        
        return {"reply": "Извините, произошла техническая ошибка. Пожалуйста, позвоните нам по телефону +7 (495) 109-33-88 для консультации."}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check(request: Request):
    """Проверка здоровья сервиса."""
    if request.method == "HEAD":
        return Response(status_code=200)
    
    return {
        "status": "ok",
        "service": "lestnitsa-chatbot-api",
        "timestamp": datetime.now().isoformat(),
        "sessions_count": len(user_sessions),
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    """Корневой endpoint."""
    return {
        "service": "LESTNITSA Chatbot API",
        "description": "Чат-бот для компании по производству и продаже лестниц",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/ping")
async def ping():
    """Пинг сервера."""
    return {
        "status": "pong",
        "timestamp": datetime.now().isoformat(),
        "service": "lestnitsa-chatbot"
    }

async def keep_alive_task():
    """Простой асинхронный keep-alive без aiohttp."""
    while True:
        try:
            await asyncio.sleep(180)  # 3 минуты
            if RENDER_EXTERNAL_URL and RENDER_EXTERNAL_URL.startswith("http"):
                try:
                    # Используем requests в отдельном потоке
                    await asyncio.to_thread(
                        requests.get, 
                        f"{RENDER_EXTERNAL_URL}/health", 
                        timeout=5
                    )
                    print(f"🔔 Keep-alive ping успешен")
                except Exception as e:
                    print(f"⚠️ Keep-alive ping failed: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Keep-alive error: {e}")

@app.on_event("startup")
async def startup_event():
    """Запускается при старте приложения."""
    print("\n" + "="*60)
    print("🏢 LESTNITSA Chatbot API запущен")
    print("="*60)
    
    print(f"🤖 AI сервис: {'✅ Replicate' if REPLICATE_API_TOKEN else '❌ Не настроен'}")
    print(f"📱 Telegram (отправка в группу): {'✅ Настроен' if TELEGRAM_BOT_TOKEN else '⚠️ Только логи'}")
    
    # Запускаем Telegram polling для ответов на сообщения
    if TELEGRAM_BOT_TOKEN:
        print("📱 Запуск обработки входящих Telegram сообщений...")
        asyncio.create_task(telegram_polling())
        print("✅ Telegram polling запущен (бот готов отвечать в личке @superlestnica_bot)")
    
    if RENDER_EXTERNAL_URL and RENDER_EXTERNAL_URL.startswith("http"):
        print(f"🔔 Keep-alive URL: {RENDER_EXTERNAL_URL}")
        asyncio.create_task(keep_alive_task())
        print("🔔 Keep-alive запущен")
    
    print("✅ Приложение готово к работе")
    print("="*60 + "\n")

@app.on_event("shutdown")
async def shutdown_event():
    """Завершение работы."""
    print("\n🛑 Завершение работы приложения...")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
