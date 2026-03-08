import os
import sys
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from chatbot_logic import generate_bot_reply, extract_name_with_ai
from telegram_utils import send_to_telegram, send_incomplete_to_telegram, send_complete_application_to_telegram
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta
import requests
import time
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
    
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
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
print("🚀 Запуск GLADIS Chatbot API")
print("="*60)

env_valid = validate_environment()
if not env_valid:
    print("\n❌ Приложение остановлено")
    sys.exit(1)

# Создаем приложение FastAPI
app = FastAPI(
    title="GLADIS Chatbot API",
    description="Чат-бот для клиники эстетической медицины GLADIS в Сочи",
    version="2.2.0"
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
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")

# Хранилище сессий пользователей
user_sessions = {}

def get_fallback_response(message: str) -> str:
    """Простая логика ответа когда AI недоступен."""
    message_lower = message.lower()
    
    # Прокол ушей
    if "прокол" in message_lower and ("ухо" in message_lower or "уши" in message_lower):
        return "Прокол ушей выполняется специальным пистолетом. Стоимость:\n• Оба уха: 4000 руб.\n• Одно ухо: 2000 руб.\n\nСерёжки из медицинской стали включены в стоимость! Используем только стерильные одноразовые картриджи. Хотите записаться?"
    
    if any(greet in message_lower for greet in ["добрый", "здравствуйте", "привет"]):
        return "Здравствуйте! Клиника GLADIS, меня зовут Александра. Чем могу вам помочь?"
    
    elif "трихолакс" in message_lower:
        if "запис" in message_lower:
            return "Трихолакс — это инъекционная процедура для укрепления и роста волос. Стоимость: 6000 руб.\n\nДля записи мне нужно ваше имя и телефон."
        else:
            return "Трихолакс — это инъекционная процедура для укрепления и роста волос. Стоимость: 6000 руб."
    
    elif "запис" in message_lower:
        return "Для записи мне нужно ваше имя и телефон. Укажите их, пожалуйста."
    
    elif any(word in message_lower for word in ["цена", "стоимость", "сколько стоит"]):
        return "Стоимость зависит от выбранной процедуры. Могу подсказать цены на:\n• Лазерную эпиляцию\n• Чистку лица\n• Биоревитализацию\n• Ботулотоксин\n• Прокол ушей\n\nЧто именно вас интересует?"
    
    elif any(word in message_lower for word in ["адрес", "где находитесь", "локация"]):
        return "📍 Наши адреса:\n• Сочи: ул. Воровского, 22\n• Адлер: ул. Кирова, д. 26а\n\n📞 Телефон: 8-928-458-32-88\n⏰ Ежедневно 10:00-20:00"
    
    elif any(word in message_lower for word in ["эпиляция", "лазерная"]):
        return "Лазерная эпиляция удаляет волосы надолго. Цены зависят от зоны:\n• Подмышки: 1100-1400 руб\n• Бикини: 1900-3500 руб\n• Ноги полностью: 4500-5800 руб\n\nХотите записаться на консультацию?"
    
    else:
        return "Здравствуйте! Клиника GLADIS, меня зовут Александра. Чем могу вам помочь? Расскажите, какая процедура вас интересует."

def is_contact_collection_request(bot_reply: str) -> bool:
    """Проверяет, просит ли бот контакты в ответе."""
    reply_lower = bot_reply.lower()
    
    contact_phrases = [
        "для записи мне нужно ваше имя и телефон",
        "укажите ваше имя и телефон для записи",
        "назовите ваше имя и телефон",
        "мне нужны ваше имя и телефон",
        "имя и телефон для записи",
        "ваше имя и номер телефона",
        "предоставьте имя и телефон",
        "оставьте имя и телефон",
        "дайте имя и телефон"
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
                    session_data.get('procedure_type')
                )
                session_data['telegram_sent'] = True
                session_data['incomplete_sent'] = True
            
            if session_age > timedelta(hours=2):
                to_delete.append(session_id)
        
        for session_id in to_delete:
            del user_sessions[session_id]
    except Exception as e:
        print(f"❌ Ошибка при очистке сессий: {e}")

def extract_contacts_from_message(message: str, session: Dict[str, Any]):
    """Извлекает контакты из сообщения и обновляет сессию."""
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
    
    if (not session['name'] or session['name'].lower() in ['привет', 'здравствуйте', 'добрый']) and REPLICATE_API_TOKEN and len(message.strip()) > 3:
        try:
            print(f"🔍 Использую AI для поиска имени в: '{message[:30]}...'")
            found_name = extract_name_with_ai(REPLICATE_API_TOKEN, message)
            
            if found_name and found_name.lower() not in ['привет', 'здравствуйте', 'добрый']:
                session['name'] = found_name
                print(f"✅ AI определил/исправил имя: {session['name']}")
        except Exception as e:
            print(f"⚠️ Ошибка AI при извлечении имени: {e}")
    
    # ===== ОПРЕДЕЛЕНИЕ ПРОЦЕДУРЫ =====
    procedure_keywords = {
        'лазерная эпиляция': ['эпиляция', 'лазер', 'удаление волос', 'бикини', 'подмышки', 'ноги', 'александрит', 'инновейшен', 'innovation', 'quanta'],
        'чистка лица': ['чистка', 'пилинг', 'акне', 'поры', 'ультразвуковая', 'механическая', 'гидропилинг'],
        'ботулотоксин': ['ботокс', 'ботулин', 'морщины', 'диспорт', 'гипергидроз'],
        'лифтинг': ['лифтинг', 'подтяжка', 'смас', 'ультера', 'морфиус'],
        'биоревитализация': ['биоревитализация', 'гиалуроновая', 'профхайло', 'hyaron'],
        'капельницы': ['капельниц', 'инфузи', 'витамин', 'детокс', 'иммуносуппорт'],
        'фотоомоложение': ['пигмент', 'пятн', 'веснушк', 'фотоомоложение', 'люмекка', 'lumecca'],
        'мезотерапия': ['мезотерапия', 'инъекци', 'укол'],
        'перманентный макияж': ['перманент', 'макияж', 'татуаж', 'брови', 'губы'],
        'удаление тату': ['тату', 'татуировк', 'удаление тату'],
        'прокол ушей': ['прокол', 'ухо', 'уши', 'пирсинг']
    }
    
    for procedure_type, keywords in procedure_keywords.items():
        if any(keyword in message_lower for keyword in keywords):
            session['last_procedure'] = procedure_type
            print(f"📋 Определена процедура: {procedure_type}")
            break

def get_last_procedure_from_history(session: Dict[str, Any]) -> str:
    """Определяет последнюю процедуру из истории диалога."""
    if session.get('last_procedure'):
        return session['last_procedure']
    
    procedure_keywords = {
        'лазерная эпиляция': ['эпиляция', 'лазер', 'бикини', 'подмышки'],
        'чистка лица': ['чистка', 'пилинг', 'акне'],
        'ботулотоксин': ['ботокс', 'ботулин', 'морщины'],
        'биоревитализация': ['биоревитализация', 'гиалуроновая'],
        'капельницы': ['капельниц', 'детокс', 'витамин'],
        'прокол ушей': ['прокол', 'ухо', 'уши']
    }
    
    for msg in reversed(session.get('text_parts', [])):
        msg_lower = msg.lower()
        for procedure_type, keywords in procedure_keywords.items():
            if any(keyword in msg_lower for keyword in keywords):
                return procedure_type
    
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
                'procedure_mentioned': False,
                'last_procedure': None
            }
        
        session = user_sessions[user_ip]
        session['text_parts'].append(user_message)
        session['message_count'] += 1
        
        full_conversation = "\n".join(session['text_parts']).lower()
        procedure_keywords = ['эпиляция', 'лазер', 'ботокс', 'чистка', 'пилинг', 'бикини', 
                             'коллаген', 'биоревитализация', 'инъекция', 'укол', 'смас', 'морфиус', 
                             'прокол', 'ухо', 'уши']
        
        if any(keyword in full_conversation for keyword in procedure_keywords):
            session['procedure_mentioned'] = True
            print(f"🔍 В диалоге упоминались процедуры")
        
        extract_contacts_from_message(user_message, session)
        
        last_procedure = get_last_procedure_from_history(session)
        
        # ===== ОТПРАВКА В TELEGRAM =====
        telegram_was_sent_now = False
        
        if session['name'] and session['phone'] and not session.get('telegram_sent', False):
            print(f"🚨 ПРОВЕРКА ОТПРАВКИ В TELEGRAM:")
            print(f"   👤 Имя: {session['name']}")
            print(f"   📞 Телефон: {session['phone']}")
            
            message_lower = user_message.lower()
            explicit_intent = any(word in message_lower for word in [
                'запис', 'хочу', 'нужно', 'можно', 'готов', 'давайте', 
                'интересует', 'завтра', 'сегодня', 'после'
            ])
            
            should_send = explicit_intent or session['procedure_mentioned']
            
            if should_send:
                print(f"🚨 ОТПРАВЛЯЕМ ЗАЯВКУ В TELEGRAM!")
                full_conversation = "\n".join(session['text_parts'])
                
                if last_procedure:
                    session['procedure_type'] = last_procedure
                
                try:
                    success = send_complete_application_to_telegram(session, full_conversation)
                    
                    if success:
                        session['telegram_sent'] = True
                        session['stage'] = 'completed'
                        session['contacts_provided'] = True
                        telegram_was_sent_now = True
                        print(f"✅ Заявка отправлена в Telegram")
                    else:
                        print(f"⚠️ Ошибка отправки в Telegram")
                except Exception as e:
                    print(f"❌ Исключение при отправке в Telegram: {e}")
            else:
                print(f"ℹ️  Контакты есть, но нет явного намерения записаться")
                session['contacts_provided'] = True
        
        # ===== ГЕНЕРАЦИЯ ОТВЕТА БОТА =====
        bot_reply = ""
        is_first_in_session = (session['message_count'] == 1)
        
        # Если заявка ТОЛЬКО ЧТО отправлена - показываем подтверждение
        if telegram_was_sent_now:
            if session.get('name'):
                bot_reply = f"✅ Спасибо, {session['name']}! Ваша заявка передана менеджеру. С вами свяжутся для подтверждения записи.\n\n📞 Телефон клиники: 8-928-458-32-88"
            else:
                bot_reply = "✅ Спасибо! Ваша заявка передана менеджеру. С вами свяжутся для подтверждения записи.\n\n📞 Телефон клиники: 8-928-458-32-88"
        
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
                            last_procedure
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
                        last_procedure
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
        print(f"   💉 Процедуры: {session.get('last_procedure', '❌ Не определены')}")
        
        print(f"🤖 Ответ бота: '{bot_reply[:100]}...'" if len(bot_reply) > 100 else f"🤖 Ответ бота: '{bot_reply}'")
        print("="*40)
        
        return {"reply": bot_reply}
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА В /chat: {e}")
        import traceback
        traceback.print_exc()
        
        return {"reply": "Извините, произошла техническая ошибка. Пожалуйста, позвоните нам по телефону 8-928-458-32-88 для консультации."}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check(request: Request):
    """Проверка здоровья сервиса."""
    if request.method == "HEAD":
        return Response(status_code=200)
    
    return {
        "status": "ok",
        "service": "gladis-chatbot-api",
        "timestamp": datetime.now().isoformat(),
        "sessions_count": len(user_sessions),
        "version": "2.2.0"
    }

@app.get("/")
async def root():
    """Корневой endpoint."""
    return {
        "service": "GLADIS Chatbot API",
        "description": "Чат-бот для клиники эстетической медицины GLADIS в Сочи",
        "status": "running",
        "version": "2.2.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/ping")
async def ping():
    """Пинг сервера."""
    return {
        "status": "pong",
        "timestamp": datetime.now().isoformat(),
        "service": "gladis-chatbot"
    }

# Убираем обработчики сигналов - они конфликтуют с Render
# Вместо этого используем простой keep-alive с requests
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
    print("🏥 GLADIS Chatbot API запущен")
    print("="*60)
    
    print(f"🤖 AI сервис: {'✅ Replicate' if REPLICATE_API_TOKEN else '❌ Не настроен'}")
    print(f"📱 Telegram (отправка в группу): {'✅ Настроен' if TELEGRAM_BOT_TOKEN else '⚠️ Только логи'}")
    
    # Запускаем Telegram polling для ответов на сообщения ← НОВОЕ
    if TELEGRAM_BOT_TOKEN:  # ← НОВОЕ
        print("📱 Запуск обработки входящих Telegram сообщений...")  # ← НОВОЕ
        asyncio.create_task(telegram_polling())  # ← НОВОЕ
        print("✅ Telegram polling запущен (бот готов отвечать в личке @sochigladisbot и @gladisSochi)")  # ← НОВОЕ
    
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
    # Просто логируем, не вызываем sys.exit()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

dialog_logic.py
"""
Логика многоэтапного диалога для бота GLADIS
"""

import re
from typing import Dict, Any

def analyze_client_needs_simple(message: str, session: Dict[str, Any]) -> str:
    """
    Простой анализ без AI.
    """
    message_lower = message.lower()
    
    # Приветственные фразы
    greetings = [
        "добрый день", "добрый вечер", "доброе утро",
        "здравствуйте", "привет", "доброго времени суток",
        "здрасьте", "приветствую"
    ]
    
    # Если это просто приветствие
    if any(greeting in message_lower for greeting in greetings):
        return "Здравствуйте! Клиника GLADIS, меня зовут Александра.\n\nЧем могу вам помочь?"
    
    # Если клиент хочет записаться
    wants_to_register = any(word in message_lower for word in [
        "хочу записаться", "запишите", "можно записаться", "готов записаться",
        "давайте запишем", "хочу на процедуру", "запишите меня", "хотел записаться"
    ])
    
    if wants_to_register:
        return "Для записи мне нужно ваше имя и телефон для связи. Укажите их, пожалуйста."
    
    # Общий ответ
    return "Здравствуйте! Клиника GLADIS, меня зовут Александра.\n\nЧем могу вам помочь? Расскажите, что вас интересует, или задайте вопрос."

def should_move_to_contacts(message: str, session: Dict[str, Any]) -> bool:
    """
    Определяет, пора ли переходить к сбору контактов.
    """
    message_lower = message.lower()
    
    # Ключевые слова, указывающие на готовность записаться
    ready_keywords = [
        "хочу записаться", "запишите", "можно записаться", 
        "готов записаться", "давайте запишем", "хочу на процедуру",
        "интересует запись", "хочу сделать", "запишите меня",
        "давайте", "согласен", "ок", "хорошо", "идемте", "хотел записаться"
    ]
    
    # Если клиент явно говорит о записи
    if any(keyword in message_lower for keyword in ready_keywords):
        return True
    
    # Если клиент дает контакты
    contact_patterns = [
        r'\d{10,11}',
        r'[\+7]?[-\s]?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{2}[-\s]?\d{2,3}',
        r'меня\s+зовут',
        r'имя\s+',
        r'телефон'
    ]
    
    for pattern in contact_patterns:
        if re.search(pattern, message_lower):
            return True
    
    # Если уже было много сообщений в диалоге
    if session.get('message_count', 0) >= 5:
        return True
    
    return False

def handle_contact_collection(message: str, session: Dict[str, Any]) -> str:
    """
    Этап 4: Сбор контактов.
    """
    print(f"🔍 Сбор контактов из сообщения: '{message}'")
    
    # Ищем телефон
    phone_pattern = r'[\+7]?[-\s]?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{2}[-\s]?\d{2,3}'
    phone_matches = re.findall(phone_pattern, message)
    
    # Также ищем просто 11 цифр подряд
    if not phone_matches:
        phone_pattern2 = r'\b\d{10,11}\b'
        phone_matches = re.findall(phone_pattern2, message)
    
    # Удаляем нецифровые символы из телефона
    if phone_matches:
        clean_phone = re.sub(r'\D', '', phone_matches[0])
        if 10 <= len(clean_phone) <= 11:
            session['phone'] = clean_phone
            print(f"📞 Найден телефон: {session['phone']}")
    
    # Ищем имя
    words = re.findall(r'[А-ЯЁа-яёA-Za-z]+', message)
    
    # Ищем русские слова с заглавной буквы (имена)
    russian_words = [word for word in words if re.match(r'^[А-ЯЁ][а-яё]*$', word)]
    
    if russian_words and not session['name']:
        # Берем первое слово с заглавной буквы как имя
        session['name'] = russian_words[0]
        print(f"👤 Найдено имя: {session['name']}")
    
    # Формируем ответ в зависимости от того, что уже есть
    has_name = bool(session['name'])
    has_phone = bool(session['phone'])
    
    if has_name and has_phone:
        return "Спасибо! Сейчас передам всю информацию администратору."
    elif has_name and not has_phone:
        return f"Спасибо, {session['name']}! Теперь укажите ваш телефон для связи."
    elif has_phone and not has_name:
        return f"Спасибо! Вижу ваш телефон {session['phone']}. Как вас зовут?"
    else:
        # Если ничего нет, просим оба
        return "Для записи мне нужно ваше имя и телефон для связи. Укажите их, пожалуйста."
