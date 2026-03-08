(function() {
    if (window.__LESTNITSA_CHAT_LOADED) return;
    window.__LESTNITSA_CHAT_LOADED = true;
    
    // Ждем полной загрузки страницы
    function initWhenReady() {
        setTimeout(initWidget, 1500);
    }
    
    if (document.readyState === 'complete') {
        initWhenReady();
    } else {
        window.addEventListener('load', initWhenReady);
        document.addEventListener('DOMContentLoaded', initWhenReady);
    }
    
    function initWidget() {
        try {
            if (!document.body) {
                setTimeout(initWidget, 500);
                return;
            }
            
            createChatElements();
            
        } catch (e) {
            console.error('Lestnitsa Chat init error:', e);
            setTimeout(initWidget, 1000);
        }
    }
    
    function createChatElements() {
        if (document.getElementById('lestnitsa-chat-icon')) return;
        
        // Создаем иконку
        const chatIcon = document.createElement('div');
        chatIcon.id = 'lestnitsa-chat-icon';
        chatIcon.innerHTML = `<svg width="30" height="30" viewBox="0 0 24 24" fill="white"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>`;
        
        // Стили под дизайн superlestnica.com
        chatIcon.style.cssText = `
            position: fixed !important;
            bottom: 25px !important;
            right: 25px !important;
            width: 60px !important;
            height: 60px !important;
            border-radius: 50% !important;
            background: #d4a373 !important;
            color: white !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            cursor: pointer !important;
            z-index: 999999 !important;
            box-shadow: 0 4px 15px rgba(212, 163, 115, 0.3) !important;
            transition: all 0.3s ease !important;
            pointer-events: auto !important;
        `;
        
        // Эффект при наведении
        chatIcon.onmouseover = () => {
            chatIcon.style.transform = 'scale(1.1)';
            chatIcon.style.boxShadow = '0 6px 20px rgba(212, 163, 115, 0.4)';
        };
        chatIcon.onmouseout = () => {
            chatIcon.style.transform = 'scale(1)';
            chatIcon.style.boxShadow = '0 4px 15px rgba(212, 163, 115, 0.3)';
        };
        
        // Создаем окно чата (скрытое)
        const chatWindow = document.createElement('div');
        chatWindow.id = 'lestnitsa-chat-window';
        chatWindow.style.cssText = `
            position: fixed !important;
            bottom: 100px !important;
            right: 20px !important;
            width: 350px !important;
            height: 500px !important;
            background: white !important;
            border: 1px solid #e8e0d5 !important;
            border-radius: 12px !important;
            display: none !important;
            flex-direction: column !important;
            z-index: 999998 !important;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1) !important;
            overflow: hidden !important;
            font-family: 'Montserrat', 'Arial', sans-serif !important;
            pointer-events: auto !important;
        `;
        
        document.body.appendChild(chatIcon);
        document.body.appendChild(chatWindow);
        
        setupChatContent(chatWindow, chatIcon);
    }
    
    function setupChatContent(chatWindow, chatIcon) {
        // Заголовок
        const header = document.createElement('div');
        header.style.cssText = `
            background: #d4a373 !important;
            color: white !important;
            padding: 18px 15px !important;
            font-weight: 600 !important;
            font-size: 16px !important;
            display: flex !important;
            align-items: center !important;
            font-family: 'Montserrat', 'Arial', sans-serif !important;
            position: relative !important;
            letter-spacing: 0.5px !important;
        `;
        header.innerHTML = `
            <svg width="22" height="22" viewBox="0 0 24 24" fill="white" style="margin-right: 10px;">
                <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
            </svg>
            Консультация по лестницам
        `;
        
        // Кнопка закрытия
        const closeBtn = document.createElement('span');
        closeBtn.innerHTML = '×';
        closeBtn.style.cssText = `
            position: absolute !important;
            top: 12px !important;
            right: 15px !important;
            color: white !important;
            cursor: pointer !important;
            font-size: 26px !important;
            font-weight: 300 !important;
            opacity: 0.8 !important;
            transition: opacity 0.3s !important;
            font-family: 'Montserrat', 'Arial', sans-serif !important;
            line-height: 1 !important;
        `;
        closeBtn.onmouseover = () => closeBtn.style.opacity = '1';
        closeBtn.onmouseout = () => closeBtn.style.opacity = '0.8';
        header.appendChild(closeBtn);
        
        // Область сообщений
        const chatArea = document.createElement('div');
        chatArea.style.cssText = `
            flex: 1 !important;
            padding: 20px 15px !important;
            overflow-y: auto !important;
            background-color: #faf8f5 !important;
            font-size: 14px !important;
            line-height: 1.6 !important;
            font-family: 'Montserrat', 'Arial', sans-serif !important;
        `;
        chatArea.innerHTML = `
            <div style="background: #f5efe9; padding: 12px 16px; border-radius: 18px 18px 18px 5px; margin-bottom: 15px; max-width: 85%; color: #4a4a4a;">
                <div style="font-weight: 600; color: #d4a373; margin-bottom: 6px; font-size: 13px; letter-spacing: 0.3px;">КОНСУЛЬТАНТ</div>
                Здравствуйте! Я помогу подобрать лестницу для вашего дома. Рассчитать стоимость или ответить на вопросы? 
            </div>
        `;
        
        // Поле ввода
        const inputContainer = document.createElement('div');
        inputContainer.style.cssText = `
            display: flex !important;
            border-top: 1px solid #e8e0d5 !important;
            padding: 12px !important;
            background: white !important;
            font-family: 'Montserrat', 'Arial', sans-serif !important;
        `;
        
        const input = document.createElement('input');
        input.placeholder = 'Ваш вопрос...';
        input.style.cssText = `
            border: 1px solid #e0d6cc !important;
            flex: 1 !important;
            padding: 12px 16px !important;
            outline: none !important;
            font-size: 14px !important;
            border-radius: 30px !important;
            background-color: #faf8f5 !important;
            font-family: 'Montserrat', 'Arial', sans-serif !important;
            transition: border-color 0.3s !important;
        `;
        input.onfocus = () => input.style.borderColor = '#d4a373';
        input.onblur = () => input.style.borderColor = '#e0d6cc';
        
        const sendBtn = document.createElement('button');
        sendBtn.innerHTML = '➤';
        sendBtn.style.cssText = `
            background: #d4a373 !important;
            color: white !important;
            border: none !important;
            border-radius: 50% !important;
            width: 44px !important;
            height: 44px !important;
            margin-left: 10px !important;
            cursor: pointer !important;
            font-size: 18px !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            transition: background 0.3s !important;
            font-family: 'Montserrat', 'Arial', sans-serif !important;
        `;
        sendBtn.onmouseover = () => sendBtn.style.background = '#c48b5e';
        sendBtn.onmouseout = () => sendBtn.style.background = '#d4a373';
        
        inputContainer.appendChild(input);
        inputContainer.appendChild(sendBtn);
        
        chatWindow.appendChild(header);
        chatWindow.appendChild(chatArea);
        chatWindow.appendChild(inputContainer);
        
        // Логика открытия/закрытия
        let isChatOpen = false;
        
        function toggleChat(e) {
            e.stopPropagation();
            isChatOpen = !isChatOpen;
            chatWindow.style.display = isChatOpen ? 'flex' : 'none';
            if (isChatOpen) setTimeout(() => input.focus(), 100);
        }
        
        chatIcon.onclick = toggleChat;
        closeBtn.onclick = toggleChat;
        
        // Функция отправки сообщения
        async function sendMessage() {
            const message = input.value.trim();
            if (!message) return;
            
            // Сообщение пользователя
            chatArea.innerHTML += `
                <div style="text-align: right; margin-bottom: 15px;">
                    <div style="background: #d4a373; color: white; padding: 10px 16px; border-radius: 18px 18px 5px 18px; display: inline-block; max-width: 85%; font-size: 14px; line-height: 1.5;">
                        ${escapeHtml(message)}
                    </div>
                </div>
            `;
            
            input.value = '';
            chatArea.scrollTop = chatArea.scrollHeight;
            
            // Индикатор загрузки
            const loadingId = 'loading-' + Date.now();
            chatArea.innerHTML += `
                <div id="${loadingId}" style="background: #f5efe9; padding: 12px 16px; border-radius: 18px 18px 18px 5px; margin-bottom: 15px; max-width: 85%;">
                    <div style="font-weight: 600; color: #d4a373; margin-bottom: 6px; font-size: 13px;">КОНСУЛЬТАНТ</div>
                    <div style="display: flex; align-items: center;">
                        <div class="typing-indicator">
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                    </div>
                </div>
            `;
            
            // Стили для индикатора печати
            if (!document.getElementById('typing-styles')) {
                const style = document.createElement('style');
                style.id = 'typing-styles';
                style.textContent = `
                    .typing-indicator { display: flex; align-items: center; height: 24px; }
                    .typing-indicator span { 
                        height: 8px; width: 8px; background: #d4a373; 
                        border-radius: 50%; margin: 0 3px; opacity: 0.4;
                        animation: typing 1.2s infinite ease-in-out;
                    }
                    .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
                    .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
                    @keyframes typing { 0%,60%,100%{opacity:0.4; transform: translateY(0);} 30%{opacity:1; transform: translateY(-4px);} }
                `;
                document.head.appendChild(style);
            }
            
            try {
                const API_URL = window.LESTNITSA_BOT_URL || "https://lestnitsa-bot.onrender.com/chat";
                
                const res = await fetch(API_URL, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message })
                });
                
                const data = await res.json();
                
                // Убираем индикатор
                const loadingEl = document.getElementById(loadingId);
                if (loadingEl) loadingEl.remove();
                
                // Ответ
                chatArea.innerHTML += `
                    <div style="margin-bottom: 15px;">
                        <div style="font-weight: 600; color: #d4a373; margin-bottom: 6px; font-size: 13px;">КОНСУЛЬТАНТ</div>
                        <div style="background: #f5efe9; padding: 12px 16px; border-radius: 18px 18px 18px 5px; max-width: 85%; color: #4a4a4a; font-size: 14px; line-height: 1.6;">
                            ${escapeHtml(data.reply).replace(/\n/g, '<br>')}
                        </div>
                    </div>
                `;
                
            } catch (error) {
                console.error('Chat error:', error);
                const loadingEl = document.getElementById(loadingId);
                if (loadingEl) loadingEl.remove();
                
                chatArea.innerHTML += `
                    <div style="margin-bottom: 15px;">
                        <div style="font-weight: 600; color: #d4a373; margin-bottom: 6px; font-size: 13px;">КОНСУЛЬТАНТ</div>
                        <div style="background: #fef2f2; padding: 12px 16px; border-radius: 18px 18px 18px 5px; max-width: 85%; color: #b91c1c; font-size: 14px; border: 1px solid #fecaca;">
                            Извините, произошла ошибка. Позвоните нам: 8-9XX-XXX-XX-XX
                        </div>
                    </div>
                `;
            }
            
            chatArea.scrollTop = chatArea.scrollHeight;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
        
        sendBtn.onclick = sendMessage;
    }
})();
