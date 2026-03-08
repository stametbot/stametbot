# admin_script.py
import json
import os
import random

def load_admin_script():
    """
    Загружает скрипт администратора из data/admin_script.json
    """
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'data', 'admin_script.json')
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ Загружен скрипт администратора")
        return data
        
    except FileNotFoundError:
        print("⚠️ Файл admin_script.json не найден.")
        return get_default_script()
    except json.JSONDecodeError:
        print("❌ Ошибка чтения admin_script.json.")
        return get_default_script()
    except Exception as e:
        print(f"❌ Ошибка загрузки скрипта: {str(e)}")
        return get_default_script()

def get_default_script():
    """Возвращает скрипт по умолчанию если файл не найден."""
    return {
        "greetings": ["Здравствуйте! Клиника GLADIS, чем могу помочь?"],
        "frequent_questions": [],
        "closing_phrases": ["Приходите на консультацию! Сочи, ул. Воровского, 22. Телефон: 8-928-458-32-88"],
        "emergency_response": "Для уточнения этого вопроса лучше связаться с администратором по телефону 8-928-458-32-88"
    }

def get_greeting():
    """
    Возвращает приветствие.
    """
    script = load_admin_script()
    greetings = script.get('greetings', [])
    
    if greetings:
        return random.choice(greetings)
    else:
        return "Здравствуйте! Клиника GLADIS, чем могу помочь?"

def get_answer_for_question(question: str):
    """
    Ищет ответ на частый вопрос.
    """
    script = load_admin_script()
    faq = script.get('frequent_questions', [])
    
    question_lower = question.lower()
    
    # Сначала ищем точное совпадение по ключевым словам
    for item in faq:
        if 'question' in item and item['question'].lower() in question_lower:
            return item.get('answer')
    
    # Если не нашли, ищем частичное совпадение
    for item in faq:
        if 'question' in item:
            keywords = item['question'].split()
            if any(keyword in question_lower for keyword in keywords):
                return item.get('answer')
    
    return None

def get_emergency_response():
    """
    Возвращает стандартный ответ для сложных вопросов.
    """
    script = load_admin_script()
    return script.get('emergency_response', "Для уточнения этого вопроса лучше связаться с администратором по телефону 8-928-458-32-88")

def get_closing_phrase():
    """
    Возвращает завершающую фразу с контактами.
    """
    script = load_admin_script()
    closings = script.get('closing_phrases', [])
    
    if closings:
        return random.choice(closings)
    else:
        return "Приходите на консультацию! Сочи, ул. Воровского, 22. Телефон: 8-928-458-32-88. Ежедневно 10:00-20:00."

def get_procedure_info(procedure_name: str):
    """
    Возвращает информацию о процедуре из шаблонов.
    """
    script = load_admin_script()
    templates = script.get('procedure_templates', {})
    
    procedure_lower = procedure_name.lower()
    
    # Ищем процедуру по ключевым словам
    for proc_key, proc_info in templates.items():
        if proc_key in procedure_lower:
            return proc_info
    
    # Если не нашли точное совпадение, ищем частичное
    for proc_key, proc_info in templates.items():
        keywords = proc_key.split()
        if any(keyword in procedure_lower for keyword in keywords):
            return proc_info
    
    return None

def get_clinic_info():
    """
    Возвращает информацию о клинике.
    """
    return {
        "address": "Сочи, ул. Воровского, 22",
        "address_adler": "Адлер, ул. Бестужева 1/1 ТЦ Мандарин, 1 этаж",
        "phone": "8-928-458-32-88",
        "hours": "Ежедневно 10:00-20:00"
    }

# Тестовый вызов
if __name__ == "__main__":
    print("🧪 Тестируем скрипт администратора")
    
    print(f"\n📝 Приветствие: {get_greeting()}")
    
    clinic = get_clinic_info()
    print(f"\n🏥 Информация о клинике:")
    print(f"  📍 Сочи: {clinic['address']}")
    print(f"  📍 Адлер: {clinic['address_adler']}")
    print(f"  📞 Телефон: {clinic['phone']}")
    print(f"  ⏰ Часы работы: {clinic['hours']}")
    
    print(f"\n⚠️ Ответ на сложный вопрос: {get_emergency_response()}")
    
    print(f"\n👋 Завершающая фраза: {get_closing_phrase()}")
