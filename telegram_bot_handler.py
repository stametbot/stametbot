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
from typing import Dict, Any
from datetime import datetime, timedelta

# Хранилище сессий для Telegram пользователей
telegram_sessions = {}

def get_bot_token():
    """Возвращает токен бота"""
    return os.getenv("TELEGRAM_BOT_TOKEN", "")

async def cleanup_old_telegram_sessions():
    """Очистка старых Telegram сессий (аналог cleanup_old_sessions из main.py)"""
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
                source = "Telegram (личка @gladisSochi)" if session_data.get('is_business') else "Telegram (личка боту)"
                
                # Отправляем неполную заявку
                from telegram_utils import send_incomplete_to_telegram
                
                await asyncio.to_thread(
                    send_incomplete_to_telegram,
                    f"📱 ИСТОЧНИК: {source}\n\n{full_text}",
                    session_data.get('name'),
                    session_data.get('phone'),
                    session_data.get('last_procedure')
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

async def extract_contacts_from_message_ai(message: str, session: Dict[str, Any], api_key: str):
    """Извлекает контакты и определяет процедуру с использованием AI"""
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
        
        if phone_matches and not session['phone']:
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
        
        for name in russian_names:
            name_lower = name.lower()
            
            procedure_words = ['ботокс', 'эпиляция', 'лазер', 'коллаген', 
                             'чистка', 'пилинг', 'смас', 'морфиус', 'александрит',
                             'перманент', 'биоревитализация', 'инъекция', 'мезотерапия']
            
            is_procedure = any(proc in name_lower for proc in procedure_words)
            is_common_name = name_lower in common_russian_names
            is_near_phone = phone_matches and (abs(message.find(name) - message.find(phone_matches[0])) < 30)
            
            if (is_common_name and not is_procedure) or (is_near_phone and not is_procedure):
                temp_name = name
                print(f"👤 Найдено возможное имя в сообщении: {temp_name}")
                break
        
        if temp_name and temp_name.lower() not in ['привет', 'здравствуйте', 'добрый', 'пока', 'спасибо']:
            session['name'] = temp_name
            print(f"✅ Обновлено имя в сессии: {session['name']}")
        
        # ===== AI ДЛЯ ИМЕНИ (если не нашли регулярками) =====
        if (not session['name'] or session['name'].lower() in ['привет', 'здравствуйте', 'добрый']) and api_key and len(message.strip()) > 3:
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
        
        # ===== AI ДЛЯ ОПРЕДЕЛЕНИЯ ПРОЦЕДУРЫ =====
        if api_key and len(message.strip()) > 3:
            try:
                print(f"🔍 Использую AI для определения процедуры в: '{message[:30]}...'")
                
                # Создаем промпт для определения процедуры
                procedure_prompt = f"""Определи, о какой косметологической процедуре идет речь в сообщении клиента.
                
Сообщение: "{message}"

Выбери ОДНУ наиболее подходящую категорию из списка:
- лазерная эпиляция (удаление волос лазером, эпиляция)
- чистка лица (чистка, пилинг, акне, поры)
- ботулотоксин (ботокс, морщины, уколы от морщин)
- лифтинг (подтяжка, смас, морфиус, ультера)
- биоревитализация (увлажнение, гиалуроновая кислота)
- капельницы (инфузии, витамины, детокс)
- фотоомоложение (пигментные пятна, веснушки, люмекка)
- мезотерапия (инъекции, уколы для кожи)
- перманентный макияж (татуаж, брови, губы)
- удаление тату (удаление татуировок, татуажа)
- прокол ушей (пирсинг, сережки)
- другое (если не подходит ни одна категория)

Верни ТОЛЬКО название категории из списка выше, ничего больше."""

                # Используем тот же AI, что и для имени
                from chatbot_logic import extract_name_with_ai
                
                detected_procedure = await asyncio.to_thread(
                    extract_name_with_ai,  # Переиспользуем функцию, но с другим промптом
                    api_key,
                    procedure_prompt
                )
                
                # Проверяем, что полученный результат - допустимая процедура
                valid_procedures = [
                    'лазерная эпиляция', 'чистка лица', 'ботулотоксин', 
                    'лифтинг', 'биоревитализация', 'капельницы', 
                    'фотоомоложение', 'мезотерапия', 'перманентный макияж',
                    'удаление тату', 'прокол ушей'
                ]
                
                if detected_procedure and detected_procedure.lower() in [p.lower() for p in valid_procedures]:
                    # Находим правильное название с учетом регистра
                    for valid_proc in valid_procedures:
                        if valid_proc.lower() == detected_procedure.lower():
                            session['last_procedure'] = valid_proc
                            print(f"✅ AI определил процедуру: {session['last_procedure']}")
                            break
                elif detected_procedure and detected_procedure.lower() != 'другое':
                    # Если AI вернул что-то другое, но похожее на процедуру
                    print(f"🤔 AI вернул: {detected_procedure}, ищем совпадения...")
                    
                    # Ищем частичное совпадение
                    for valid_proc in valid_procedures:
                        if any(word in detected_procedure.lower() for word in valid_proc.lower().split()):
                            session['last_procedure'] = valid_proc
                            print(f"✅ Найдено частичное совпадение: {session['last_procedure']}")
                            break
                            
            except Exception as e:
                print(f"⚠️ Ошибка AI при определении процедуры: {e}")
                
                # Fallback: используем ключевые слова если AI не сработал
                procedure_keywords = {
                    'лазерная эпиляция': ['эпиляция', 'лазер', 'удаление волос', 'бикини', 'подмышки', 'ноги', 'александрит'],
                    'чистка лица': ['чистка', 'пилинг', 'акне', 'поры'],
                    'ботулотоксин': ['ботокс', 'ботулин', 'морщины'],
                    'лифтинг': ['лифтинг', 'подтяжка', 'смас', 'морфиус'],
                    'биоревитализация': ['биоревитализация', 'гиалуроновая'],
                    'капельницы': ['капельниц', 'детокс', 'витамин'],
                    'фотоомоложение': ['пигмент', 'пятн', 'веснушк', 'люмекка'],
                    'мезотерапия': ['мезотерапия', 'инъекци', 'укол'],
                    'перманентный макияж': ['перманент', 'татуаж', 'брови', 'губы'],
                    'удаление тату': ['тату', 'татуировк'],
                    'прокол ушей': ['прокол', 'ухо', 'уши']
                }
                
                for procedure_type, keywords in procedure_keywords.items():
                    if any(keyword in message_lower for keyword in keywords):
                        session['last_procedure'] = procedure_type
                        print(f"📋 Fallback: определена процедура по ключевым словам: {procedure_type}")
                        break
        
        # ===== ОПРЕДЕЛЕНИЕ ПРОЦЕДУРЫ ПО КЛЮЧЕВЫМ СЛОВАМ (если AI не использовался) =====
        elif not api_key and not session.get('last_procedure'):
            procedure_keywords = {
                'лазерная эпиляция': ['эпиляция', 'лазер', 'удаление волос', 'бикини', 'подмышки', 'ноги', 'александрит'],
                'чистка лица': ['чистка', 'пилинг', 'акне', 'поры'],
                'ботулотоксин': ['ботокс', 'ботулин', 'морщины'],
                'лифтинг': ['лифтинг', 'подтяжка', 'смас', 'морфиус'],
                'биоревитализация': ['биоревитализация', 'гиалуроновая'],
                'капельницы': ['капельниц', 'детокс', 'витамин'],
                'фотоомоложение': ['пигмент', 'пятн', 'веснушк', 'люмекка'],
                'мезотерапия': ['мезотерапия', 'инъекци', 'укол'],
                'перманентный макияж': ['перманент', 'татуаж', 'брови', 'губы'],
                'удаление тату': ['тату', 'татуировк'],
                'прокол ушей': ['прокол', 'ухо', 'уши']
            }
            
            for procedure_type, keywords in procedure_keywords.items():
                if any(keyword in message_lower for keyword in keywords):
                    session['last_procedure'] = procedure_type
                    print(f"📋 Определена процедура по ключевым словам: {procedure_type}")
                    break
                
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
        
        # Бизнес-сообщение (личка @gladisSochi)
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
        print(f"   Тип: {'Бизнес (личка @gladisSochi)' if is_business else 'Личка боту'}")
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
                'last_procedure': None,
                'telegram_chat_id': chat_id,
                'telegram_user_id': user_id,
                'is_business': is_business,
                'telegram_sent': False,
                'incomplete_sent': False
            }
        
        session = telegram_sessions[session_key]
        session['text_parts'].append(text)
        session['message_count'] += 1
        
        # Извлекаем контакты и процедуру с помощью AI
        api_key = os.getenv("REPLICATE_API_TOKEN")
        await extract_contacts_from_message_ai(text, session, api_key)
        
        # Генерируем ответ через AI
        from chatbot_logic import generate_bot_reply
        
        if not api_key:
            reply = "Здравствуйте! Клиника GLADIS. Чем могу помочь?"
        else:
            is_first = session['message_count'] == 1
            has_name = bool(session['name'])
            has_phone = bool(session['phone'])
            telegram_sent = False
            last_procedure = session.get('last_procedure')
            
            # Генерируем ответ (в отдельном потоке)
            reply = await asyncio.to_thread(
                generate_bot_reply,
                api_key,
                text,
                is_first,
                has_name,
                has_phone,
                telegram_sent,
                last_procedure
            )
        
        # Отправляем ответ
        await send_telegram_reply(chat_id, reply)
        
        # Проверяем, нужно ли отправить заявку
        if session['name'] and session['phone'] and not session.get('telegram_sent', False):
            message_lower = text.lower()
            explicit_intent = any(word in message_lower for word in [
                'запис', 'хочу', 'нужно', 'можно', 'готов', 'давайте', 
                'интересует', 'завтра', 'сегодня', 'после'
            ])
            
            procedure_mentioned = session.get('last_procedure') is not None
            
            if explicit_intent or procedure_mentioned:
                from telegram_utils import send_complete_application_to_telegram
                
                full_conversation = "\n".join(session['text_parts'])
                source = "Telegram (личка @gladisSochi)" if is_business else "Telegram (личка боту)"
                
                session_with_source = session.copy()
                session_with_source['source'] = source
                if session.get('last_procedure'):
                    session_with_source['procedure_type'] = session['last_procedure']
                
                await asyncio.to_thread(
                    send_complete_application_to_telegram,
                    session_with_source,
                    f"📱 ИСТОЧНИК: {source}\n\n{full_conversation}"
                )
                session['telegram_sent'] = True
                print(f"✅ Заявка из Telegram отправлена в группу")
        
        print(f"📊 СОСТОЯНИЕ TELEGRAM СЕССИИ:")
        print(f"   👤 Имя: {'✅ ' + session['name'] if session['name'] else '❌ Нет'}")
        print(f"   📞 Телефон: {'✅ ' + str(session['phone']) if session['phone'] else '❌ Нет'}")
        print(f"   📨 Отправлено в группу: {'✅' if session.get('telegram_sent') else '❌'}")
        print(f"   💉 Процедура: {session.get('last_procedure', '❌ Не определена')}")
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
    
    print("🔄 Запуск Telegram polling...")
    print("   Будет обрабатывать:")
    print("   - личные сообщения @" + os.getenv("TELEGRAM_BOT_TOKEN", "").split(':')[0])
    print("   - бизнес-сообщения @gladisSochi (если бот подключен)")
    
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
