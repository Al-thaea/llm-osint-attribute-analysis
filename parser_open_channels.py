"""
parser.py — Модуль парсингу публічного Telegram-каналу
Збирає пости через веб-інтерфейс t.me/s/ без використання API
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import json
import re

# ============================================================
# НАЛАШТУВАННЯ
# ============================================================

CHANNEL_URL = "https://t.me/example_channel"

# Опції для періоду: 0 - за весь час, 1 - за місяць,
# 3 - за 3 місяці, 6 - півроку, 12 - рік
TIME_LIMIT_MONTHS = 12

# Максимальна кількість сторінок для парсингу
MAX_PAGES = 100

# ============================================================
# ДОПОМІЖНІ ФУНКЦІЇ
# ============================================================

def _get_cutoff_date(months_limit):
    """Обчислює граничну дату на основі ліміту в місяцях."""
    if months_limit > 0:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30 * months_limit)
        print(f"[*] Обмеження по часу: пости новіші за {cutoff_date.strftime('%Y-%m-%d')}")
        return cutoff_date
    return None


def _extract_image_urls(msg):
    """
    Витягує URL зображень з одного повідомлення Telegram.
    Фото зберігаються як фонове зображення у тегу <a class="tgme_widget_message_photo_wrap">.
    """
    urls = []
    for wrap in msg.find_all("a", class_="tgme_widget_message_photo_wrap"):
        style = wrap.get("style", "")
        m = re.search(r"url\('([^']+)'\)", style)
        if m:
            urls.append(m.group(1))
    return urls


# ============================================================
# ПАРСИНГ
# ============================================================

def parse_telegram_channel(url, max_pages=MAX_PAGES, months_limit=TIME_LIMIT_MONTHS):
    """
    Збирає пости з публічного Telegram-каналу через веб-версію t.me/s/
    Повертає список словників: {"text": ..., "date": ..., "has_media": ...}
    Зберігає емодзі як значущі поведінкові маркери.
    """

    # Автоматично додаємо /s/ якщо URL без нього
    if "/s/" not in url:
        current_url = url.replace("t.me/", "t.me/s/")
    else:
        current_url = url

    all_posts = []

    cutoff_date = _get_cutoff_date(months_limit)

    print(f"[*] Починаємо парсинг каналу: {url}")

    for page in range(max_pages):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(current_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            messages = soup.find_all("div", class_="tgme_widget_message")

            if not messages:
                print(f"[!] Постів не знайдено на сторінці {page + 1}")
                break

            reached_cutoff = False
            page_count = 0

            for msg in reversed(messages):
                # Перевіряємо дату
                post_date = None
                time_node = msg.find("time")
                if time_node and time_node.get("datetime"):
                    post_date = datetime.fromisoformat(
                        time_node["datetime"].replace('Z', '+00:00')
                    )
                    if cutoff_date and post_date < cutoff_date:
                        reached_cutoff = True
                        break

                # Отримуємо текст (зберігаємо емодзі)
                text_div = msg.find("div", class_="tgme_widget_message_text")
                if text_div:
                    text = text_div.get_text(separator=" ", strip=True)
                    if text:
                        image_urls = _extract_image_urls(msg)
                        has_media = bool(
                            image_urls or
                            msg.find("div", class_="tgme_widget_message_video")
                        )
                        all_posts.append({
                            "text": text,
                            "date": post_date.isoformat() if post_date else None,
                            "has_media": has_media,
                            "image_urls": image_urls,
                        })
                        page_count += 1

            print(f"[+] Сторінка {page + 1}: зібрано {page_count} постів")

            if reached_cutoff:
                print("[*] Досягнуто ліміту по даті, зупиняємо парсинг.")
                break

            # Пагінація
            prev_link = soup.find("a", class_="tme_messages_more")
            if prev_link and prev_link.get("href"):
                current_url = "https://t.me" + prev_link["href"]
            else:
                break

        except Exception as e:
            print(f"[!] Помилка парсингу: {e}")
            break

    print(f"[+] Всього зібрано постів: {len(all_posts)}")
    return all_posts


def prepare_sample(posts, sample="all"):
    """
    Готує текст для аналізу з вибраної частини постів.
    sample: "all" / "first" / "middle" / "last"
    Видаляє URL-посилання, зберігає емодзі.
    """
    if not posts:
        return ""

    n = len(posts)
    if sample == "first":
        selected = posts[:n // 3]
    elif sample == "middle":
        selected = posts[n // 3: 2 * n // 3]
    elif sample == "last":
        selected = posts[2 * n // 3:]
    else:
        selected = posts

    cleaned = []
    for post in selected:
        text = post["text"] if isinstance(post, dict) else post
        text = re.sub(r"http\S+", "", text).strip()
        if text:
            cleaned.append(text)

    combined = "\n\n".join(cleaned)
    print(f"[+] Підготовлено текст: {len(cleaned)} постів, {len(combined)} символів")
    return combined


def collect_image_urls(posts, sample="all", max_total=10):
    """
    Збирає URL зображень з вибраної частини постів.
    Повертає список URL (не більше max_total).
    """
    n = len(posts)
    if sample == "first":
        selected = posts[:n // 3]
    elif sample == "middle":
        selected = posts[n // 3: 2 * n // 3]
    elif sample == "last":
        selected = posts[2 * n // 3:]
    else:
        selected = posts

    urls = []
    for post in selected:
        if isinstance(post, dict):
            urls.extend(post.get("image_urls", []))
        if len(urls) >= max_total:
            break

    print(f"[+] Знайдено зображень для аналізу: {len(urls[:max_total])}")
    return urls[:max_total]


def save_posts(posts, filename="posts.json"):
    """Зберігає зібрані пости у JSON файл"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    print(f"[+] Пости збережено у {filename}")


def load_posts(filename="posts.json"):
    """Завантажує пости з JSON файлу (щоб не парсити повторно)"""
    with open(filename, "r", encoding="utf-8") as f:
        posts = json.load(f)
    print(f"[+] Завантажено {len(posts)} постів з {filename}")
    return posts


# ============================================================
# ЗАПУСК ОКРЕМО (для тестування)
# ============================================================

if __name__ == "__main__":
    # --- Варіант 1: канал ---
    posts = parse_telegram_channel(url=CHANNEL_URL)
    save_posts(posts)

    print("\nПарсинг завершено. Запустіть analyzer.py для аналізу.")
