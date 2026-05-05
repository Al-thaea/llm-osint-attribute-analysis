import os
import json
from bs4 import BeautifulSoup

def parse_telegram_html(export_dir, target_user):
    """
    Парсить HTML файли експорту Telegram (messages.html, messages2.html...)
    та повертає список повідомлень зазначеного користувача.
    """
    posts = []
    
    if not os.path.exists(export_dir):
        print(f"[-] Помилка: Папка '{export_dir}' не знайдена!")
        return []
        
    # Знаходимо всі файли messages*.html
    html_files = [f for f in os.listdir(export_dir) if f.startswith('messages') and f.endswith('.html')]
    
    if not html_files:
        print(f"[-] Помилка: У папці '{export_dir}' не знайдено файлів HTML експорту.")
        return []

    # Сортування для хронологічного порядку (messages.html -> 1, messages2.html -> 2)
    def file_index(name):
        num_str = name.replace('messages', '').replace('.html', '')
        return int(num_str) if num_str.isdigit() else 1
        
    html_files.sort(key=file_index)
    
    print(f"[*] Знайдено HTML файлів для обробки: {len(html_files)}")
    
    # Зберігаємо останнього автора, бо Телеграм групує повідомлення 
    # і показує ім'я тільки в першому повідомленні підряд
    current_author = None
    
    for filename in html_files:
        filepath = os.path.join(export_dir, filename)
        print(f"  -> Парсинг {filename}...")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            
        # Шукаємо всі блоки повідомлень
        message_blocks = soup.find_all('div', class_='message')
        
        for msg in message_blocks:
            # Пропускаємо системні повідомлення (створення чату, закріплення тощо)
            if 'service' in msg.get('class', []):
                continue

            from_name_div = msg.find('div', class_='from_name')
            if from_name_div:
                current_author = from_name_div.text.strip()
            
            text_div = msg.find('div', class_='text')
            date_div = msg.find('div', class_='date')
            
            if text_div and current_author:
                text = text_div.get_text(separator=' ', strip=True)
                date_str = date_div.get('title', '') if date_div else ''
                
                # Фільтруємо за вказаним користувачем (частковий збіг імені)
                if target_user.lower() in current_author.lower():
                    if text: # Зберігаємо, якщо є текстовий контент
                        posts.append({
                            "author": current_author,
                            "text": text,
                            "date": date_str,
                            "images": []
                        })
                        
    print(f"[*] Готово! Знайдено {len(posts)} повідомлень від '{target_user}'.")
    return posts

if __name__ == "__main__":
    # ================= НАЛАШТУВАННЯ =================
    # 1. Вкажіть повний шлях до папки з експортом (папка, де лежать messages.html)
    EXPORT_FOLDER = r'path/to/ChatExport_folder'
    
    # 2. Вкажіть ім'я користувача (ТАК, ЯК ВОНО ВІДОБРАЖАЄТЬСЯ В ЧАТІ ТЕЛЕГРАМУ!)
    TARGET_USER = "username"

    # 3. Назва файлу для збереження
    OUTPUT_FILE = "Results/Channel_Example/posts.json"
    # =================================================
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    extracted_posts = parse_telegram_html(EXPORT_FOLDER, TARGET_USER)
    
    if extracted_posts:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(extracted_posts, f, ensure_ascii=False, indent=2)
        print(f"[+] Результат успішно збережено у файл: {OUTPUT_FILE}")
        print("[!] Тепер ви можете запустити results.py - він побачить цей файл і проаналізує його.")
    else:
        print("[-] Повідомлень не знайдено, файл не створено.")
