from typing import Dict, Any, Optional
from datetime import datetime
import os
import requests

def send_to_telegram(text: str, name: str = None, phone: str = None):
    """
    Отправляет сообщение в Telegram.
    """
    try:
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "@superlestnica_bot")
        
        if not TELEGRAM_BOT_TOKEN:
            print("⚠️ TELEGRAM_BOT_TOKEN не настроен, сообщение не отправлено")
            print(f"📝 Текст сообщения: {text[:200]}...")
            return False
        
        # Формируем URL для отправки
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        # Добавляем контакты в сообщение если они есть
        full_text = text
        if name or phone:
            full_text += f"\n\n📋 КОНТАКТНЫЕ ДАННЫЕ:\n"
            if name:
                full_text += f"👤 Имя: {name}\n"
            if phone:
                full_text += f"📞 Телефон: {phone}\n"
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": full_text,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Сообщение отправлено в Telegram")
            return True
        else:
            print(f"❌ Ошибка Telegram API: {response.status_code}")
            print(f"   Ответ: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при отправке в Telegram: {str(e)}")
        return False

def send_incomplete_to_telegram(full_text: str, name: str = None, phone: str = None, product: str = None):
    """
    Отправляет неполную заявку по таймауту.
    """
    try:
        if not os.getenv("TELEGRAM_BOT_TOKEN"):
            print("⚠️ Telegram не настроен, неполная заявка не отправлена")
            return False
        
        telegram_text = f"⚠️ НЕПОЛНАЯ ЗАЯВКА (таймаут 10 минут)\n\n"
        
        if name:
            telegram_text += f"👤 Имя: {name}\n"
        else:
            telegram_text += f"👤 Имя: Не указано\n"
            
        if phone:
            telegram_text += f"📞 Телефон: {phone}\n"
        else:
            telegram_text += f"📞 Телефон: Не указан\n"
            
        if product:
            telegram_text += f"🪜 Интересующая модель: {product}\n"
            
        telegram_text += f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        telegram_text += f"💬 Часть диалога:\n{full_text[:1000]}..."
        
        return send_to_telegram(telegram_text, name, phone)
        
    except Exception as e:
        print(f"❌ Ошибка при отправке неполной заявки: {str(e)}")
        return False

def send_complete_application_to_telegram(session: Dict[str, Any], full_conversation: str):
    """
    Отправляет полную заявку с деталями диалога в Telegram.
    Включает все детали, собранные ботом о лестнице.
    """
    try:
        print(f"\n📨 ОТПРАВКА ПОЛНОЙ ЗАЯВКИ В TELEGRAM")
        print(f"   👤 Имя: {session.get('name')}")
        print(f"   📞 Телефон: {session.get('phone')}")
        print(f"   🪜 Модель: {session.get('product_interest')}")
        
        # Формируем детализированное сообщение
        telegram_text = f"🚨 НОВАЯ ЗАЯВКА НА ЛЕСТНИЦУ\n\n"
        
        # Основная информация
        telegram_text += f"👤 КЛИЕНТ: {session.get('name', 'Не указано')}\n"
        telegram_text += f"📞 ТЕЛЕФОН: {session.get('phone', 'Не указан')}\n"
        telegram_text += f"⏰ ВРЕМЯ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Информация о лестнице
        if session.get('product_interest'):
            telegram_text += f"🪜 МОДЕЛЬ: {session['product_interest'].upper()}\n"
        
        if session.get('product_type'):  # для совместимости
            telegram_text += f"🪜 МОДЕЛЬ: {session['product_type']}\n"
        
        if session.get('opening_height'):
            telegram_text += f"📏 ВЫСОТА ПРОЕМА: {session['opening_height']}\n"
        
        if session.get('opening_params'):
            telegram_text += f"📐 ПАРАМЕТРЫ ПРОЕМА: {session['opening_params']}\n"
        
        if session.get('material_interest'):
            telegram_text += f"🪵 МАТЕРИАЛ: {session['material_interest']}\n"
        
        if session.get('color_interest'):
            telegram_text += f"🎨 ЦВЕТ: {session['color_interest']}\n"
        
        # Информация о типе лестницы (если есть в сессии)
        if session.get('staircase_type'):
            telegram_text += f"🏗️ ТИП: {session['staircase_type']}\n"
        
        # Источник
        source = session.get('source', 'Чат-бот на сайте')
        telegram_text += f"\n🔗 ИСТОЧНИК: {source}\n"
        
        # Добавляем полный диалог
        telegram_text += f"\n💬 ПОЛНЫЙ ДИАЛОГ:\n{full_conversation}\n\n"
        
        # Отправляем через существующую функцию
        return send_to_telegram(telegram_text, session.get('name'), session.get('phone'))
        
    except Exception as e:
        print(f"❌ Ошибка при отправке полной заявки: {str(e)}")
        return False

def format_staircase_application(session: Dict[str, Any]) -> str:
    """
    Форматирует заявку на лестницу для красивого отображения.
    """
    text = "🚨 НОВАЯ ЗАЯВКА\n\n"
    
    # Контакты
    text += "👤 КОНТАКТЫ:\n"
    text += f"  Имя: {session.get('name', 'Не указано')}\n"
    text += f"  Телефон: {session.get('phone', 'Не указан')}\n\n"
    
    # Информация о лестнице
    text += "🏠 ИНФОРМАЦИЯ О ЛЕСТНИЦЕ:\n"
    
    if session.get('product_interest'):
        text += f"  Модель: {session['product_interest'].capitalize()}\n"
    
    if session.get('opening_height'):
        text += f"  Высота проема: {session['opening_height']}\n"
    
    if session.get('material_interest'):
        text += f"  Материал: {session['material_interest'].capitalize()}\n"
    
    if session.get('color_interest'):
        text += f"  Цвет: {session['color_interest'].capitalize()}\n"
    
    # Время
    text += f"\n⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    
    # Источник
    if session.get('source'):
        text += f"📱 Источник: {session['source']}\n"
    
    return text

# Тестовый вызов при запуске файла
if __name__ == "__main__":
    print("🧪 Тестирование telegram_utils.py")
    print(f"   TELEGRAM_CHAT_ID: {os.getenv('TELEGRAM_CHAT_ID', '@superlestnica_bot')}")
    print("   ✅ Файл готов к работе")
