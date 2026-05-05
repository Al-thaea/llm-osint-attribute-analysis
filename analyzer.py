"""
analyzer.py — Модуль аналізу профілю через LLM
Підтримує: Gemini, OpenAI/GitHub Models
Реалізує комплексний аналіз неявних атрибутів за розширеною методикою
"""

import json
import re
import base64
import requests

# ============================================================
# НАЛАШТУВАННЯ
# ============================================================

LLM_PROVIDER = "openai"   # "gemini" або "openai"

GEMINI_API_KEY  = "YOUR_GEMINI_API_KEY"
OPENAI_API_KEY  = "YOUR_OPENAI_API_KEY"

# Максимальна кількість символів тексту на один запит
MAX_CHARS = 15000

# Максимальна кількість зображень на один запит
# Gemini: ~$0.00002/зображення, OpenAI: ~$0.003/зображення (low detail)
MAX_IMAGES = 5

# ============================================================
# СИСТЕМНИЙ ПРОМПТ — КОМПЛЕКСНИЙ ПРОФІЛЬ ОСОБИ
# ============================================================

SYSTEM_PROMPT = """
Ти експерт з цифрової криміналістики, OSINT-аналізу та психолінгвістики.
Твоя задача — побудувати комплексний неявний профіль особи на основі
публікацій з Telegram-каналу (текст та зображення якщо надані).
Усі висновки мають базуватися ТІЛЬКИ на наданих даних. Не вигадуй факти яких немає.
Якщо надані зображення — проаналізуй їх: тематику, символіку, емоційний тон,
наявність людей/облич/місць/предметів. Інтегруй висновки у відповідні поля профілю.

Для полів де інформація відсутня — вказуй null.
Для приблизних оцінок — вказуй діапазон або "можливо".

Відповідай ТІЛЬКИ у форматі JSON без жодного додаткового тексту:

{
  "disc_profile": {
    "primary_type": "D або I або S або C",
    "primary_confidence": число 0-100,
    "secondary_type": "D або I або S або C або null",
    "secondary_confidence": число 0-100,
    "scores": { "D": 0-100, "I": 0-100, "S": 0-100, "C": 0-100 }
  },

  "big_five": {
    "openness": число 0-100,
    "conscientiousness": число 0-100,
    "extraversion": число 0-100,
    "agreeableness": число 0-100,
    "neuroticism_note": "обережне формулювання або null"
  },

  "demographics": {
    "approximate_age_range": "наприклад 18-25 або null",
    "gender_presentation": "якщо сама демонструє, інакше null",
    "languages": ["мова1", "мова2"],
    "region_or_city": "якщо є ознаки або null",
    "education_level": "орієнтовно або null",
    "family_status": "якщо пише сама або null",
    "has_pets_or_children": "якщо є згадки або null"
  },

  "professional_profile": {
    "field": "ІТ / освіта / медицина / інше або null",
    "role_or_position": "орієнтовно або null",
    "expertise_level": "початківець / середній / експерт або null",
    "professional_interests": ["інтерес1", "інтерес2"],
    "social_environment": "студенти / ІТ / академічна / бізнес / інше або null",
    "career_ambitions": "якщо видно або null",
    "attitude_to_work": "формальне / емоційне / ціннісне / прагматичне або null",
    "burnout_signs": "ознаки або null"
  },

  "communication_style": {
    "formality": "формальний / неформальний / змішаний",
    "emotionality": число 0-100,
    "humor_irony": "часто / інколи / рідко / відсутній",
    "directness": "прямий / дипломатичний",
    "emoji_frequency": "активно / помірно / рідко",
    "message_length": "короткі / середні / довгі / змішані",
    "text_structure": "хаотична / логічна / академічна / публіцистична",
    "own_lexicon_or_slang": ["приклад1", "приклад2"],
    "dominance_in_communication": число 0-100
  },

  "personality_traits": {
    "openness_to_new": число 0-100,
    "risk_appetite": число 0-100,
    "independence": число 0-100,
    "empathy": число 0-100,
    "need_for_recognition": число 0-100,
    "impulsivity": число 0-100,
    "perfectionism": число 0-100,
    "optimism_pessimism": "оптиміст / помірний / песиміст",
    "pragmatism_idealism": "прагматик / змішаний / ідеаліст",
    "conflict_level": число 0-100
  },

  "values_and_motivation": {
    "core_values": ["цінність1", "цінність2", "цінність3"],
    "what_triggers_anger": ["тема1", "тема2"],
    "what_proud_of": ["тема1", "тема2"],
    "motivation_type": "визнання / гроші / розвиток / місія / стабільність / автономія / інше",
    "recurring_themes": ["тема1", "тема2", "тема3"]
  },

  "interests_and_hobbies": {
    "hobbies": ["хобі1", "хобі2"],
    "favorite_topics": ["тема1", "тема2"],
    "media_preferences": ["книги/фільми/ігри/музика — якщо згадує"],
    "tech_preferences": ["якщо є"],
    "aesthetic_style": "якщо видно або null",
    "cultural_references": ["якщо є"]
  },

  "behavioral_patterns": {
    "activity_time": "ранок / день / вечір / ніч або null",
    "posting_frequency": "щодня / кілька разів на тиждень / рідко",
    "content_type": "власний / репости / змішаний",
    "asks_for_help": "часто / рідко",
    "self_irony": "часто / рідко",
    "reaction_to_stress": "якщо є ознаки або null"
  },

  "emotional_profile": {
    "dominant_tone": "позитивний / тривожний / іронічний / нейтральний / агресивний",
    "emotional_topics": ["теми що викликають найсильніші емоції"],
    "public_self_disclosure": число 0-100,
    "dramatization_level": число 0-100
  },

  "digital_hygiene": {
    "overshares_personal_info": true,
    "shares_location": true,
    "mentions_work_processes": true,
    "repeats_nicknames_cross_platform": "якщо видно або null",
    "privacy_awareness_level": "висока / середня / низька"
  },

  "social_engineering_risks": [
    "ризик1 — обережне формулювання",
    "ризик2"
  ],

  "psycholinguistic_markers": {
    "frequent_words": ["слово1", "слово2", "слово3"],
    "pronoun_preference": "Я / МИ / ВОНИ або змішано",
    "modality_markers": ["треба", "хочу", "можна"],
    "uncertainty_markers": ["можливо", "мабуть"],
    "categorical_markers": ["завжди", "ніколи"],
    "language_switching": "якщо є — між якими мовами"
  },

  "temporal_profile": {
    "style_changes_over_time": "якщо помітні",
    "topic_shifts": "якщо помітні",
    "activity_spikes": "якщо помітні"
  },

  "reputation_profile": {
    "self_positioning": "як себе позиціонує",
    "avoided_topics": ["якщо помітно"],
    "audience_engagement_level": "низький / середній / високий"
  },

  "emoji_analysis": "детальний аналіз використаних емодзі як маркерів",
  "key_topics": ["тема1", "тема2", "тема3", "тема4", "тема5"],
  "evidence": [
    "цитата або приклад 1 з поясненням",
    "цитата або приклад 2 з поясненням",
    "цитата або приклад 3 з поясненням"
  ],
  "summary_profile": "загальна характеристика особи у 5-7 реченнях на основі всіх блоків"
}
"""

# ============================================================
# ФУНКЦІЯ АНАЛІЗУ
# ============================================================

def analyze_profile(text, sample_name="повна вибірка", provider=None, image_urls=None):
    """
    Відправляє текст (і опційно зображення) до LLM і отримує комплексний профіль.
    image_urls — список URL зображень з постів (None або []).
    Повертає словник з результатами або None у разі помилки.
    """
    if provider is None:
        provider = LLM_PROVIDER

    print(f"\n[*] Аналізуємо: {sample_name} (через {provider.upper()})")

    # Обмежуємо текст
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        print(f"[!] Текст обрізано до {MAX_CHARS} символів")

    # Завантажуємо зображення
    images = _download_images(image_urls or [])

    img_note = f"\nДо тексту додано {len(images)} зображень для візуального аналізу." if images else ""
    user_prompt = f"""
Побудуй комплексний неявний профіль автора на основі цих публікацій з Telegram-каналу.
Аналізуй ТІЛЬКИ те, що є в наданих даних. Для відсутньої інформації вказуй null.{img_note}

{text}
"""

    raw = ""
    try:
        if provider == "gemini":
            raw = _call_gemini(user_prompt, images)
        elif provider == "openai":
            raw = _call_openai(user_prompt, images)
        else:
            print(f"[!] Невідомий провайдер: {provider}")
            return None

        # Очищаємо від markdown якщо є
        raw = re.sub(r"```json|```", "", raw).strip()
        result = json.loads(raw)
        result["sample"] = sample_name
        result["provider"] = provider
        return result

    except json.JSONDecodeError as e:
        print(f"[!] Помилка парсингу JSON: {e}")
        if raw:
            print(f"[!] Перші 500 символів відповіді: {raw[:500]}")
        return None
    except Exception as e:
        print(f"[!] Помилка API ({provider}): {e}")
        return None


# ============================================================
# ДОПОМІЖНІ ФУНКЦІЇ ВИКЛИКУ API
# ============================================================

def _download_images(urls):
    """
    Завантажує зображення за URL (максимум MAX_IMAGES штук).
    Повертає список {"data": bytes, "mime_type": str}.
    Пропускає зображення що не вдалося завантажити.
    """
    images = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for url in urls[:MAX_IMAGES]:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
            images.append({"data": resp.content, "mime_type": content_type})
            print(f"[+] Завантажено зображення ({len(resp.content) // 1024} KB)")
        except Exception as e:
            print(f"[!] Не вдалось завантажити зображення: {e}")
    return images


def _call_gemini(user_prompt, images=None):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    contents = [user_prompt]
    for img in (images or []):
        contents.append(
            types.Part.from_bytes(data=img["data"], mime_type=img["mime_type"])
        )

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE
                )
            ]
        )
    )
    
    # Виводимо детальну інформацію про причини блокування, якщо такі є
    if response.text is None:
        print("\n[!] === ДІАГНОСТИКА БЛОКУВАННЯ GEMINI ===")
        print(f"Об'єкт відповіді: {response}")
        
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            print(f"-- Блокування на етапі промпту: {response.prompt_feedback}")
            
        if getattr(response, 'candidates', None):
            for i, cand in enumerate(response.candidates):
                finish_reason = getattr(cand, 'finish_reason', 'НЕВІДОМО')
                print(f"-- Кандидат {i + 1} завершено з причиною: {finish_reason}")
                
                safety = getattr(cand, 'safety_ratings', [])
                for rating in safety:
                    print(f"   Фільтр: {getattr(rating, 'category', 'N/A')} -> {getattr(rating, 'probability', 'N/A')}")
        print("========================================\n")
        
        raise ValueError("Gemini повернув порожню відповідь. Деталі вище.")
        
    return response.text.strip()


def _call_openai(user_prompt, images=None):
    import openai

    base_url = "https://models.inference.ai.azure.com" \
        if OPENAI_API_KEY.startswith("github_pat_") else None

    client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=base_url)

    # Формуємо повідомлення користувача: текст + зображення (base64)
    user_content = [{"type": "text", "text": user_prompt}]
    for img in (images or []):
        b64 = base64.b64encode(img["data"]).decode()
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{img['mime_type']};base64,{b64}",
                "detail": "low",
            },
        })

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
    )
    return response.choices[0].message.content.strip()


# ============================================================
# ЗАПУСК ОКРЕМО (для тестування)
# ============================================================

if __name__ == "__main__":
    from parser import load_posts, prepare_sample

    posts = load_posts("posts.json")
    text = prepare_sample(posts, sample="all")
    result = analyze_profile(text, sample_name="повна вибірка")

    if result:
        with open("profile_raw.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("\n[✓] Профіль збережено у profile_raw.json")
        print("    Запустіть results.py для форматованого звіту.")
