"""
Модуль для обработки входящих сообщений в Telegram боте
Поддерживает:
- Личные сообщения боту (@superlestnica_bot)
- Бизнес-сообщения (личка через Business Mode)
"""

import os
import asyncio
import requests
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# Хранилище сессий для Telegram пользователей
telegram_sessions = {}

# Константы для работы с лестницами (как в main.py)
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

def get_bot_token():
    """Возвращает токен бота"""
    return os.getenv("TELEGRAM_BOT_TOKEN", "")

async def cleanup_old_telegram_sessions():
    """Очистка старых Telegram сессий"""
    try:
        now = datetime.now()
        to_delete = []
        
        for session_id, session_data in list(telegram_sessions.items()):
            session_age = now - session_data['created_at']
            
            # ТАЙМАУТ 10 минут: отправляем неполную заявку если есть контакты
            if (session_age > timedelta(minutes=10) and 
                not session_data.get('telegram_sent', False) and 
                session_data.get('phone') and 
                session_data.get('name')):
                
                print(f"⏰ ТАЙМАУТ 10 минут (Telegram): отправляем неполную заявку")
                
                full_text = "\n".join(session_data.get('text_parts', []))
                source = "Telegram (бизнес)" if session_data.get('is_business') else "Telegram (личка боту)"
                
                # Отправляем неполную заявку
                from telegram_utils import send_incomplete_to_telegram
                
                await asyncio.to_thread(
                    send_incomplete_to_telegram,
                    f"📱 ИСТОЧНИК: {source}\n\n{full_text}",
                    session_data.get('name'),
                    session_data.get('phone'),
                    session_data.get('product_interest')
                )
                session_data['telegram_sent'] = True
                session_data['incomplete_sent'] = True
            
            # Удаляем сессии старше 2 часов
            if session_age > timedelta(hours=2):
                to_delete.append(session_id)
        
        for session_id in to_delete:
            del telegram_sessions[session_id]
            
        if to_delete:
            print(f"🧹 Очищено {len(to_delete)} старых Telegram сессий")
            
    except Exception as e:
        print(f"❌ Ошибка при очистке Telegram сессий: {e}")

async def periodic_cleanup():
    """Запускает очистку сессий каждые 5 минут"""
    while True:
        try:
            await asyncio.sleep(300)  # 5 минут
            await cleanup_old_telegram_sessions()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Ошибка в periodic_cleanup: {e}")

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
    
    # Ищем просто числа, которые могут быть высотой
    numbers = re.findall(r'\b(\d{4})\b', message_lower)
    if numbers:
        return f"{numbers[0]} мм"
    
    return None

async def extract_contacts_from_message_ai(message: str, session: Dict[str, Any], api_key: str):
    """Извлекает контакты и определяет интересующий товар с использованием AI"""
    try:
        message_lower = message.lower()
        
        # ===== ПОИСК ТЕЛЕФОНА (регулярками) =====
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
        
        # ===== ПОИСК ИМЕНИ (сначала регулярками, потом AI) =====
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
        
        # ===== AI ДЛЯ ИМЕНИ (если не нашли регулярками) =====
        if (not session.get('name') or session.get('name', '').lower() in ['привет', 'здравствуйте', 'добрый']) and api_key and len(message.strip()) > 3:
            try:
                print(f"🔍 Использую AI для поиска имени в: '{message[:30]}...'")
                from chatbot_logic import extract_name_with_ai
                
                found_name = await asyncio.to_thread(
                    extract_name_with_ai,
                    api_key,
                    message
                )
                
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
        
        # ===== AI ДЛЯ ОПРЕДЕЛЕНИЯ ТОВАРА (если не нашли по ключевым словам) =====
        if api_key and len(message.strip()) > 3 and not session.get('product_interest'):
            try:
                print(f"🔍 Использую AI для определения товара в: '{message[:30]}...'")
                
                # Создаем промпт для определения товара
                product_prompt = f"""Определи, о каком товаре для лестниц идет речь в сообщении клиента.
                
Сообщение: "{message}"

Выбери ОДНУ наиболее подходящую категорию из списка:
- престиж (модульная лестница, шаг 225 мм, классическая)
- престиж комфорт (улучшенная версия, шаг 190 мм)
- престиж мини (компактная, гусиный шаг)
- элегант (изящная лестница, шаг 230 мм)
- элегант комфорт (улучшенная, шаг 190 мм)
- каркас (металлическая основа для самостоятельной отделки)
- ступени (деревянные ступени, хвоя, бук)
- поручни (перила, балясины, ограждения)
- комплектующие (модули, подпорки, фланцы, крепеж)
- другое (если не подходит ни одна категория)

Верни ТОЛЬКО название категории из списка выше, ничего больше."""

                # Используем тот же AI, что и для имени
                from chatbot_logic import extract_name_with_ai
                
                detected_product_ai = await asyncio.to_thread(
                    extract_name_with_ai,
                    api_key,
                    product_prompt
                )
                
                # Проверяем, что полученный результат - допустимый товар
                valid_products = [
                    'престиж', 'престиж комфорт', 'престиж мини', 
                    'элегант', 'элегант комфорт', 'каркас',
                    'ступени', 'поручни', 'комплектующие'
                ]
                
                if detected_product_ai and detected_product_ai.lower() in valid_products:
                    session['product_interest'] = detected_product_ai.lower()
                    session['product_mentioned'] = True
                    print(f"✅ AI определил товар: {session['product_interest']}")
                            
            except Exception as e:
                print(f"⚠️ Ошибка AI при определении товара: {e}")
                
    except Exception as e:
        print(f"❌ Ошибка в extract_contacts_from_message_ai: {e}")

async def handle_telegram_update(update: Dict[str, Any]):
    """
    Обрабатывает входящее обновление от Telegram
    """
    try:
        # Определяем тип сообщения
        message = None
        chat_id = None
        user_id = None
        text = None
        username = None
        chat_type = None
        is_business = False
        
        # Обычное сообщение (личка боту)
        if 'message' in update:
            message = update['message']
            chat_type = message['chat']['type']
            
            # Игнорируем групповые чаты и каналы
            if chat_type in ['group', 'supergroup', 'channel']:
                print(f"⏭️ Игнорируем сообщение из группы/канала")
                return
            
            chat_id = message['chat']['id']
            user_id = message['from']['id']
            text = message.get('text', '')
            username = message['from'].get('first_name', 'Пользователь')
            is_business = False
        
        # Бизнес-сообщение (личка @superlestnica_bot)
        elif 'business_message' in update:
            message = update['business_message']
            chat_id = message['chat']['id']
            user_id = message['from']['id']
            text = message.get('text', '')
            username = message['from'].get('first_name', 'Пользователь')
            is_business = True
        
        else:
            return  # Игнорируем другие типы
        
        # Игнорируем команды
        if text.startswith('/'):
            return
        
        print(f"\n📱 ВХОДЯЩЕЕ СООБЩЕНИЕ В TELEGRAM")
        print(f"   Тип: {'Бизнес (личка @superlestnica_bot)' if is_business else 'Личка боту'}")
        print(f"   От: {username} (ID: {user_id})")
        print(f"   Текст: {text[:50]}..." if len(text) > 50 else f"   Текст: {text}")
        
        # Получаем или создаем сессию
        session_key = f"tg_{user_id}"
        if session_key not in telegram_sessions:
            telegram_sessions[session_key] = {
                'created_at': datetime.now(),
                'name': None,
                'phone': None,
                'text_parts': [],
                'message_count': 0,
                'product_interest': None,
                'material_interest': None,
                'color_interest': None,
                'opening_height': None,
                'telegram_chat_id': chat_id,
                'telegram_user_id': user_id,
                'is_business': is_business,
                'telegram_sent': False,
                'incomplete_sent': False,
                'product_mentioned': False
            }
        
        session = telegram_sessions[session_key]
        session['text_parts'].append(text)
        session['message_count'] += 1
        
        # Извлекаем контакты и товар с помощью AI
        api_key = os.getenv("REPLICATE_API_TOKEN")
        await extract_contacts_from_message_ai(text, session, api_key)
        
        # Генерируем ответ через AI
        from chatbot_logic import generate_bot_reply
        
        if not api_key:
            reply = "Здравствуйте! Меня зовут Алина, я помогу подобрать лестницу для вашего дома. Какая модель вас интересует?"
        else:
            is_first = session['message_count'] == 1
            has_name = bool(session.get('name'))
            has_phone = bool(session.get('phone'))
            telegram_sent = bool(session.get('telegram_sent'))
            product_interest = session.get('product_interest')
            
            # Генерируем ответ (в отдельном потоке)
            reply = await asyncio.to_thread(
                generate_bot_reply,
                api_key,
                text,
                is_first,
                has_name,
                has_phone,
                telegram_sent,
                product_interest
            )
        
        # Отправляем ответ
        await send_telegram_reply(chat_id, reply)
        
        # Проверяем, нужно ли отправить заявку
        if session.get('name') and session.get('phone') and not session.get('telegram_sent', False):
            message_lower = text.lower()
            explicit_intent = any(word in message_lower for word in [
                'заказ', 'хочу', 'нужно', 'можно', 'готов', 'давайте', 
                'рассчита', 'сколько стоит', 'цена', 'купить', 'оформить'
            ])
            
            product_mentioned = session.get('product_mentioned', False) or session.get('opening_height') is not None
            
            if explicit_intent or product_mentioned:
                from telegram_utils import send_complete_application_to_telegram
                
                full_conversation = "\n".join(session['text_parts'])
                source = "Telegram (бизнес @superlestnica_bot)" if is_business else "Telegram (личка боту)"
                
                session_with_source = session.copy()
                session_with_source['source'] = source
                if session.get('product_interest'):
                    session_with_source['product_type'] = session['product_interest']
                if session.get('opening_height'):
                    session_with_source['opening_params'] = f"Высота проема: {session['opening_height']}"
                
                await asyncio.to_thread(
                    send_complete_application_to_telegram,
                    session_with_source,
                    f"📱 ИСТОЧНИК: {source}\n\n{full_conversation}"
                )
                session['telegram_sent'] = True
                print(f"✅ Заявка из Telegram отправлена в группу")
        
        print(f"📊 СОСТОЯНИЕ TELEGRAM СЕССИИ:")
        print(f"   👤 Имя: {'✅ ' + session['name'] if session.get('name') else '❌ Нет'}")
        print(f"   📞 Телефон: {'✅ ' + str(session['phone']) if session.get('phone') else '❌ Нет'}")
        print(f"   📨 Отправлено в группу: {'✅' if session.get('telegram_sent') else '❌'}")
        print(f"   🪜 Модель: {session.get('product_interest', '❌ Не определена')}")
        print(f"   📏 Высота проема: {session.get('opening_height', '❌ Не указана')}")
        print(f"   🤖 Ответ: {reply[:100]}..." if len(reply) > 100 else f"   🤖 Ответ: {reply}")
        
    except Exception as e:
        print(f"❌ Ошибка обработки Telegram сообщения: {e}")
        import traceback
        traceback.print_exc()

async def send_telegram_reply(chat_id: int, text: str):
    """
    Отправляет ответ пользователю в Telegram
    """
    try:
        token = get_bot_token()
        if not token:
            print("❌ Нет токена бота")
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        response = await asyncio.to_thread(
            requests.post, url, json=payload, timeout=10
        )
        
        if response.status_code == 200:
            return True
        else:
            print(f"❌ Ошибка Telegram API: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

async def telegram_polling():
    """
    Постоянный опрос Telegram API (long polling)
    """
    token = get_bot_token()
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN не настроен, polling отключен")
        return
    
    bot_username = os.getenv("TELEGRAM_BOT_TOKEN", "").split(':')[0] if ':' in os.getenv("TELEGRAM_BOT_TOKEN", "") else "superlestnica_bot"
    
    print("🔄 Запуск Telegram polling...")
    print("   Будет обрабатывать:")
    print(f"   - личные сообщения @{bot_username}")
    print("   - бизнес-сообщения @superlestnica_bot (если бот подключен)")
    
    # Запускаем периодическую очистку сессий
    asyncio.create_task(periodic_cleanup())
    print("🧹 Запущена периодическая очистка сессий (каждые 5 минут)")
    
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["message", "business_message"]
            }
            
            response = await asyncio.to_thread(
                requests.get, url, params=params, timeout=35
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok") and data.get("result"):
                    for update in data["result"]:
                        await handle_telegram_update(update)
                        offset = update["update_id"] + 1
            
            await asyncio.sleep(0.5)
            
        except asyncio.CancelledError:
            print("🛑 Telegram polling остановлен")
            break
        except Exception as e:
            print(f"❌ Ошибка polling: {e}")
            await asyncio.sleep(5)
