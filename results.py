"""
results.py — Модуль обробки та відображення результатів профілювання
Виводить форматований звіт, порівнює результати різних моделей,
оцінює стабільність профілю та зберігає фінальний JSON
"""

import json
import os
from parser import load_posts, parse_telegram_chat_by_hashtag, prepare_sample, parse_telegram_channel, save_posts
from analyzer import analyze_profile, LLM_PROVIDER

# ============================================================
# НАЛАШТУВАННЯ ЗАПУСКУ
# ============================================================

# Список ДЖЕРЕЛ для аналізу. 
# Ключ: Назва папки (куди зберегти)
# Значення: Словник з налаштуваннями джерела (url - посилання, target_user - юзернейм або None для всього каналу)
SOURCES_TO_ANALYZE = {

    "Channel_1_Example_Channel": {
        "url": "https://t.me/example_channel",
        "target_user": None
    },
    
    # Приклад 2: Груповий чат, але нас цікавить ТІЛЬКИ ОДНА людина в ньому
    "Channel_2_Example_Group": {
        "url": "https://t.me/example_group",  
        "target_user": "example_username",
        "months_limit": 12  # 0 означає "за весь час"
    }

}

# Які провайдери порівнювати
PROVIDERS_TO_COMPARE = ["openai", "gemini"] 

# Які вибірки аналізувати
SAMPLES = {
    "first":  "перші 30%",
    "middle": "середні 30%",
    "last":   "останні 30%"
}

# ============================================================
# ВІДОБРАЖЕННЯ РЕЗУЛЬТАТІВ
# ============================================================

def print_result(result, channel_url, log_file=None):
    """Виводить форматований профіль у термінал та опціонально у файл"""

    if not result:
        msg = "[!] Результат відсутній\n"
        print(msg)
        if log_file: log_file.write(msg)
        return

    sep = "=" * 60
    
    lines = []
    lines.append(f"\n{sep}")
    lines.append(f"  ДЖЕРЕЛО АНАЛІЗУ: {channel_url}")
    lines.append(f"  ВИБІРКА: {result.get('sample', '—')}  |  МОДЕЛЬ: {result.get('provider', '—').upper()}")
    lines.append(sep)

    # DISC
    disc = result.get("disc_profile", {})
    if disc:
        lines.append(f"\n▶ DISC ПРОФІЛЬ")
        scores = disc.get("scores", {})
        for key in ['D', 'I', 'S', 'C']:
            bar = '█' * (scores.get(key, 0) // 5)
            lines.append(f"  {key}: {bar:<20} {scores.get(key, 0)}%")
        lines.append(f"  Основний тип:  {disc.get('primary_type')} ({disc.get('primary_confidence')}%)")
        if disc.get('secondary_type'):
            lines.append(f"  Вторинний тип: {disc.get('secondary_type')} ({disc.get('secondary_confidence')}%)")

    # Big Five
    bf = result.get("big_five", {})
    if bf:
        lines.append(f"\n▶ BIG FIVE")
        labels = {
            "openness": "Відкритість",
            "conscientiousness": "Сумлінність",
            "extraversion": "Екстраверсія",
            "agreeableness": "Доброзичливість"
        }
        for key, label in labels.items():
            val = bf.get(key, 0)
            bar = '█' * (val // 5)
            lines.append(f"  {label:<18}: {bar:<20} {val}%")
        if bf.get("neuroticism_note"):
            lines.append(f"  Нейротизм: {bf['neuroticism_note']}")

    # Демографія
    demo = result.get("demographics", {})
    if demo:
        lines.append(f"\n▶ ДЕМОГРАФІЧНИЙ ПРОФІЛЬ")
        fields = {
            "approximate_age_range": "Приблизний вік",
            "gender_presentation": "Стать/гендер",
            "languages": "Мови",
            "region_or_city": "Регіон/місто",
            "education_level": "Освіта",
            "family_status": "Сімейний стан",
            "has_pets_or_children": "Діти/тварини"
        }
        for key, label in fields.items():
            val = demo.get(key)
            if val:
                if isinstance(val, list):
                    val = ", ".join(val)
                lines.append(f"  {label:<20}: {val}")

    # Професійний профіль
    prof = result.get("professional_profile", {})
    if prof:
        lines.append(f"\n▶ ПРОФЕСІЙНИЙ ПРОФІЛЬ")
        fields = {
            "field": "Галузь",
            "role_or_position": "Роль/посада",
            "expertise_level": "Рівень експертизи",
            "social_environment": "Соціальне середовище",
            "attitude_to_work": "Ставлення до роботи",
            "career_ambitions": "Кар'єрні амбіції",
            "burnout_signs": "Ознаки вигорання"
        }
        for key, label in fields.items():
            val = prof.get(key)
            if val:
                lines.append(f"  {label:<22}: {val}")
        interests = prof.get("professional_interests", [])
        if interests:
            lines.append(f"  {'Проф. інтереси':<22}: {', '.join(interests)}")

    # Стиль комунікації
    comm = result.get("communication_style", {})
    if comm:
        lines.append(f"\n▶ КОМУНІКАЦІЙНИЙ СТИЛЬ")
        fields = {
            "formality": "Формальність",
            "humor_irony": "Гумор/іронія",
            "directness": "Прямота",
            "emoji_frequency": "Частота емодзі",
            "message_length": "Довжина повідомлень",
            "text_structure": "Структура тексту"
        }
        for key, label in fields.items():
            val = comm.get(key)
            if val:
                lines.append(f"  {label:<22}: {val}")
        slang = comm.get("own_lexicon_or_slang", [])
        if slang:
            lines.append(f"  {'Власна лексика':<22}: {', '.join(slang)}")

    # Цінності
    vals = result.get("values_and_motivation", {})
    if vals:
        lines.append(f"\n▶ ЦІННОСТІ ТА МОТИВАЦІЯ")
        if vals.get("core_values"):
            lines.append(f"  Базові цінності:  {', '.join(vals['core_values'])}")
        if vals.get("motivation_type"):
            lines.append(f"  Тип мотивації:    {vals['motivation_type']}")
        if vals.get("recurring_themes"):
            lines.append(f"  Повторювані теми: {', '.join(vals['recurring_themes'])}")

    # Поведінкові патерни
    beh = result.get("behavioral_patterns", {})
    if beh:
        lines.append(f"\n▶ ПОВЕДІНКОВІ ПАТЕРНИ")
        fields = {
            "activity_time": "Час активності",
            "posting_frequency": "Частота публікацій",
            "content_type": "Тип контенту",
            "asks_for_help": "Просить допомоги",
            "self_irony": "Самоіронія",
            "reaction_to_stress": "Реакція на стрес"
        }
        for key, label in fields.items():
            val = beh.get(key)
            if val:
                lines.append(f"  {label:<22}: {val}")

    # Цифрова гігієна
    dh = result.get("digital_hygiene", {})
    if dh:
        lines.append(f"\n▶ ЦИФРОВА ГІГІЄНА")
        lines.append(f"  Надмірний шер особистого: {'Так' if dh.get('overshares_personal_info') else 'Ні'}")
        lines.append(f"  Публікує геолокацію:      {'Так' if dh.get('shares_location') else 'Ні'}")
        lines.append(f"  Згадує робочі процеси:    {'Так' if dh.get('mentions_work_processes') else 'Ні'}")
        if dh.get("privacy_awareness_level"):
            lines.append(f"  Рівень приватності:       {dh['privacy_awareness_level']}")

    # Ризики соціальної інженерії
    se_risks = result.get("social_engineering_risks", [])
    if se_risks:
        lines.append(f"\n▶ МОЖЛИВІ РИЗИКИ СОЦІАЛЬНОЇ ІНЖЕНЕРІЇ")
        for risk in se_risks:
            lines.append(f"  • {risk}")

    # Ключові теми та докази
    topics = result.get("key_topics", [])
    if topics:
        lines.append(f"\n▶ КЛЮЧОВІ ТЕМИ: {', '.join(topics)}")

    evidence = result.get("evidence", [])
    if evidence:
        lines.append(f"\n▶ ДОКАЗИ З ТЕКСТУ")
        for ev in evidence:
            lines.append(f"  • {ev}")

    # Emoji аналіз
    if result.get("emoji_analysis"):
        lines.append(f"\n▶ АНАЛІЗ ЕМОДЗІ\n  {result['emoji_analysis']}")

    # Загальний профіль
    if result.get("summary_profile"):
        lines.append(f"\n▶ ЗАГАЛЬНИЙ ПРОФІЛЬ\n  {result['summary_profile']}")

    lines.append(f"\n{sep}\n")
    
    output_str = "\n".join(lines)
    print(output_str)
    if log_file:
        log_file.write(output_str + "\n")


def print_stability_report(all_results, log_file=None):
    """Оцінює стабільність DISC-профілю між вибірками"""
    
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("  ПІДСУМОК СТАБІЛЬНОСТІ ПРОФІЛЮ")
    lines.append("=" * 60)

    by_provider = {}
    for r in all_results:
        p = r.get("provider", "unknown")
        if p not in by_provider:
            by_provider[p] = []
        disc = r.get("disc_profile", {})
        by_provider[p].append(disc.get("primary_type", "?"))

    for provider, types in by_provider.items():
        lines.append(f"\n  [{provider.upper()}]  Типи по вибірках: {' / '.join(types)}")
        if len(set(types)) == 1:
            lines.append(f"  [✓] Профіль СТАБІЛЬНИЙ: {types[0]}")
        else:
            lines.append(f"  [~] Профіль ВАРІАТИВНИЙ — можлива зміна поведінки в часі")

    # Порівняння між моделями (якщо є кілька провайдерів)
    providers = list(by_provider.keys())
    if len(providers) > 1:
        lines.append(f"\n  ПОРІВНЯННЯ МОДЕЛЕЙ:")
        for p in providers:
            dominant = max(set(by_provider[p]), key=by_provider[p].count)
            lines.append(f"  {p.upper():<10}: домінуючий тип — {dominant}")
            
    output_str = "\n".join(lines)
    print(output_str)
    if log_file:
        log_file.write(output_str + "\n")


# ============================================================
# ГОЛОВНА ФУНКЦІЯ
# ============================================================

def main():
    # Базова папка для всіх результатів
    base_results_dir = "Results"
    os.makedirs(base_results_dir, exist_ok=True)

    # 1. Цикл по всіх джерелах
    for source_name, source_data in SOURCES_TO_ANALYZE.items():
        source_url = source_data["url"]
        target_user = source_data.get("target_user")
        months = source_data.get("months_limit", 12) # За замовчуванням 12 місяців
        
        print(f"\n{'#'*70}")
        if target_user:
            print(f"[*] РОЗПОЧИНАЮ АНАЛІЗ КОРИСТУВАЧА: {target_user} у групі ({source_url})")
        else:
            print(f"[*] РОЗПОЧИНАЮ АНАЛІЗ КАНАЛУ: {source_name} ({source_url})")
        print(f"{'#'*70}\n")
        
        # Створюємо папку для конкретного джерела
        channel_dir = os.path.join(base_results_dir, source_name)
        os.makedirs(channel_dir, exist_ok=True)
        
        posts_file = os.path.join(channel_dir, "posts.json")
        results_file = os.path.join(channel_dir, "disc_results.json")
        report_file = os.path.join(channel_dir, "report.txt")

        # 2. Отримуємо пости
        try:
            posts = load_posts(posts_file)
            print(f"[+] Завантажено {len(posts)} збережених постів з {posts_file}")
        except Exception:
            print(f"[!] {posts_file} не знайдено, запускаємо парсер...")
            
            # Якщо вказано конкретного користувача, нам треба парсити як чат і дістати саме його
            if target_user:
                # Використовуємо parse_telegram_chat_by_hashtag (який також парсить авторів)
                from parser import parse_telegram_chat_by_hashtag, group_posts_by_author
                all_group_posts = parse_telegram_chat_by_hashtag(group_url=source_url, months_limit=months)
                
                # Групуємо і витягуємо потрібного юзера
                grouped = group_posts_by_author(all_group_posts)
                posts = grouped.get(target_user, [])
                
                print(f"[+] Знайдено {len(posts)} повідомлень від користувача {target_user}")
                
            else:
                # Звичайний парсинг каналу
                posts = parse_telegram_channel(url=source_url, months_limit=months)
                
            save_posts(posts, filename=posts_file)

        if not posts:
            print(f"[!] Пости відсутні для {source_name}. Пропускаємо...")
            continue

        all_results = []

        # Відкриваємо файл для текстового звіту
        with open(report_file, "w", encoding="utf-8") as log_f:
            if target_user:
                log_f.write(f"АНАЛІЗ КОРИСТУВАЧА: {target_user} (з {source_url})\n")
            else:
                log_f.write(f"АНАЛІЗ КАНАЛУ: {source_url}\n")
            
            # 3. Аналізуємо кожну вибірку (SAMPLES тимчасово визначено)
            SAMPLES = {
                "first":  "перші 30%",
                "middle": "середні 30%",
                "last":   "останні 30%"
            }
            
            for provider in PROVIDERS_TO_COMPARE:
                for sample_key, sample_label in SAMPLES.items():
                    text = prepare_sample(posts, sample=sample_key)
                    if not text:
                        continue
                    
                    try:
                        from parser import collect_image_urls
                        image_urls = collect_image_urls(posts, sample=sample_key)
                    except ImportError:
                        image_urls = []
                        
                    result = analyze_profile(
                        text, sample_name=sample_label,
                        provider=provider, image_urls=image_urls
                    )
                    
                    if result:
                        all_results.append(result)
                        print_result(result, source_url, log_file=log_f)

            if all_results:
                print_stability_report(all_results, log_file=log_f)

        # 4. Зберігаємо JSON з результатами для поточного каналу
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"\n[✓] Аналіз {source_name} завершено. Результати у папці: {channel_dir}")

if __name__ == "__main__":
    main()
