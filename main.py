import random
import json
import time
import telebot
import os
import requests
import urllib.parse
import sys
import threading
from telebot import types
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from dotenv import load_dotenv
from datetime import datetime
from translations import translations
from bs4 import BeautifulSoup

# Set to store checked car IDs
checked_ids = set()

# Путь до файла
REQUESTS_FILE = "requests.json"
ACCESS_FILE = "access.json"


def load_access():
    if os.path.exists(ACCESS_FILE):
        try:
            with open(ACCESS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"⚠️ Не удалось загрузить access.json: {e}")
            return set()
    return set()


# Initialize ACCESS set
ACCESS = load_access()

# Глобальный словарь всех запросов пользователей
user_requests = {}


def save_access():
    try:
        with open(ACCESS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(ACCESS), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Ошибка при сохранении access.json: {e}")


MANAGER = 56022406  # Только этот пользователь может добавлять других

COLOR_TRANSLATIONS = {
    "검정색": "Чёрный",
    "쥐색": "Тёмно-серый",
    "은색": "Серебристый",
    "은회색": "Серо-серебристый",
    "흰색": "Белый",
    "은하색": "Галактический серый",
    "명은색": "Светло-серебристый",
    "갈대색": "Коричневато-серый",
    "연금색": "Светло-золотистый",
    "청색": "Синий",
    "하늘색": "Голубой",
    "담녹색": "Тёмно-зелёный",
    "청옥색": "Бирюзовый",
}

# Добавляем словарь с кодами цветов KBChaChaCha
KBCHACHACHA_COLORS = {
    "검정색": {"code": "006001", "ru": "Чёрный"},
    "흰색": {"code": "006002", "ru": "Белый"},
    "은색": {"code": "006003", "ru": "Серебристый"},
    "진주색": {"code": "006004", "ru": "Жемчужный"},
    "회색": {"code": "006005", "ru": "Серый"},
    "빨간색": {"code": "006006", "ru": "Красный"},
    "파란색": {"code": "006007", "ru": "Синий"},
    "주황색": {"code": "006008", "ru": "Оранжевый"},
    "갈색": {"code": "006009", "ru": "Коричневый"},
    "초록색": {"code": "006010", "ru": "Зелёный"},
    "노란색": {"code": "006011", "ru": "Жёлтый"},
    "보라색": {"code": "006012", "ru": "Фиолетовый"},
}

# Загружаем переменные из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# FSM-хранилище
state_storage = StateMemoryStorage()

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN, state_storage=state_storage)
user_search_data = {}


# Проверка на то может ли человек пользоваться ботом или нет
def is_authorized(user_id):
    return user_id in ACCESS


def translate_phrase(phrase):
    words = phrase.split()
    translated_words = [translations.get(word, word) for word in words]
    return " ".join(translated_words)


def load_requests():
    global user_requests
    if os.path.exists(REQUESTS_FILE):
        try:
            with open(REQUESTS_FILE, "r", encoding="utf-8") as f:
                user_requests = json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось загрузить запросы: {e}")
            user_requests = {}
    else:
        user_requests = {}


def save_requests(new_data):
    global user_requests
    try:
        if os.path.exists(REQUESTS_FILE):
            with open(REQUESTS_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                existing_data = json.loads(content) if content else {}
        else:
            existing_data = {}

        for user_id, new_requests in new_data.items():
            # Убедимся, что user_id — строка
            user_id_str = str(user_id)
            existing_data[user_id_str] = new_requests

        user_requests = existing_data  # Обновляем глобальные данные

        with open(REQUESTS_FILE, "w", encoding="utf-8") as f:
            json.dump(user_requests, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения запросов: {e}")


# FSM: Состояния формы
class CarForm(StatesGroup):
    brand = State()
    model = State()
    generation = State()
    trim = State()
    color = State()
    mileage_from = State()
    mileage_to = State()


def get_manufacturers():
    url = "https://api.encar.com/search/car/list/general?count=true&q=(And.Hidden.N._.SellType.%EC%9D%BC%EB%B0%98._.CarType.A.)&inav=%7CMetadata%7CSort"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        manufacturers = (
            data.get("iNav", {})
            .get("Nodes", [])[2]
            .get("Facets", [])[0]
            .get("Refinements", {})
            .get("Nodes", [])[0]
            .get("Facets", [])
        )
        manufacturers.sort(key=lambda x: x.get("Metadata", {}).get("EngName", [""])[0])
        return manufacturers
    except Exception as e:
        print("Ошибка при получении марок:", e)
        return []


def get_models_by_brand(manufacturer):
    url = f"https://api.encar.com/search/car/list/general?count=true&q=(And.Hidden.N._.SellType.%EC%9D%BC%EB%B0%98._.(C.CarType.A._.Manufacturer.{manufacturer}.))&inav=%7CMetadata%7CSort"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.encar.com/",
        "Origin": "https://www.encar.com",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    try:
        print(f"DEBUG: Making request to Encar API")
        print(f"DEBUG: URL: {url}")
        print(f"DEBUG: manufacturer={manufacturer}")

        response = requests.get(url, headers=headers)
        print(f"DEBUG: Response status code: {response.status_code}")

        if response.status_code != 200:
            print(f"ERROR: API request failed with status code {response.status_code}")
            print(f"ERROR: Response text: {response.text}")
            return []

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to parse JSON response: {str(e)}")
            print(f"ERROR: Raw response text: {response.text}")
            return []

        print(f"DEBUG: Successfully parsed JSON response")

        all_manufacturers = (
            data.get("iNav", {})
            .get("Nodes", [])[2]
            .get("Facets", [])[0]
            .get("Refinements", {})
            .get("Nodes", [])[0]
            .get("Facets", [])
        )

        selected_manufacturer = next(
            (item for item in all_manufacturers if item.get("IsSelected")), None
        )

        if not selected_manufacturer:
            print("ERROR: Selected manufacturer not found in response")
            return []

        models = (
            selected_manufacturer.get("Refinements", {})
            .get("Nodes", [])[0]
            .get("Facets", [])
        )

        if not models:
            print("ERROR: No models found for manufacturer")
            return []

        print(f"DEBUG: Found {len(models)} models")
        for model in models:
            print(
                f"DEBUG: Model: {model.get('DisplayValue')} (code: {model.get('Value')})"
            )

        return models

    except requests.RequestException as e:
        print(f"ERROR: Network error while fetching models: {str(e)}")
        return []
    except Exception as e:
        print(f"ERROR: Unexpected error while fetching models: {str(e)}")
        print(f"ERROR: URL: {url}")
        if "response" in locals():
            print(f"ERROR: Response text: {response.text}")
        return []


def get_generations_by_model(manufacturer, model_group):
    url = f"https://api.encar.com/search/car/list/general?count=true&q=(And.Hidden.N._.SellType.%EC%9D%BC%EB%B0%98._.(C.CarType.A._.(C.Manufacturer.{manufacturer}._.ModelGroup.{model_group}.)))&inav=%7CMetadata%7CSort"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        all_manufacturers = (
            data.get("iNav", {})
            .get("Nodes", [])[2]
            .get("Facets", [])[0]
            .get("Refinements", {})
            .get("Nodes", [])[0]
            .get("Facets", [])
        )
        selected_manufacturer = next(
            (item for item in all_manufacturers if item.get("IsSelected")), None
        )
        if not selected_manufacturer:
            return []
        model_group_data = (
            selected_manufacturer.get("Refinements", {})
            .get("Nodes", [])[0]
            .get("Facets", [])
        )
        selected_model = next(
            (item for item in model_group_data if item.get("IsSelected")), None
        )
        if not selected_model:
            return []
        return (
            selected_model.get("Refinements", {}).get("Nodes", [])[0].get("Facets", [])
        )
    except Exception as e:
        print(f"Ошибка при получении поколений для {manufacturer}, {model_group}:", e)
        return []


def get_trims_by_generation(manufacturer, model_group, model):
    url = f"https://api.encar.com/search/car/list/general?count=true&q=(And.Hidden.N._.(C.CarType.A._.(C.Manufacturer.{manufacturer}._.(C.ModelGroup.{model_group}._.Model.{model}.))))&inav=%7CMetadata%7CSort"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        all_manufacturers = (
            data.get("iNav", {})
            .get("Nodes", [])[1]
            .get("Facets", [])[0]
            .get("Refinements", {})
            .get("Nodes", [])[0]
            .get("Facets", [])
        )
        selected_manufacturer = next(
            (item for item in all_manufacturers if item.get("IsSelected")), None
        )
        if not selected_manufacturer:
            return []
        model_group_data = (
            selected_manufacturer.get("Refinements", {})
            .get("Nodes", [])[0]
            .get("Facets", [])
        )
        selected_model_group = next(
            (item for item in model_group_data if item.get("IsSelected")), None
        )
        if not selected_model_group:
            return []
        model_data = (
            selected_model_group.get("Refinements", {})
            .get("Nodes", [])[0]
            .get("Facets", [])
        )
        selected_model = next(
            (item for item in model_data if item.get("IsSelected")), None
        )
        if not selected_model:
            return []
        return (
            selected_model.get("Refinements", {}).get("Nodes", [])[0].get("Facets", [])
        )
    except Exception as e:
        print(
            f"Ошибка при получении комплектаций для {manufacturer}, {model_group}, {model}:",
            e,
        )
        return []


@bot.message_handler(commands=["start"])
def start_handler(message):
    if not is_authorized(message.from_user.id):
        bot.reply_to(message, "❌ У вас нет доступа к этому боту.")
        return

    # Главные кнопки
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 Найти авто", callback_data="search_car"),
    )
    markup.add(
        types.InlineKeyboardButton(
            "🧮 Рассчитать по ссылке", url="https://t.me/eightytwoautobot"
        ),
    )
    markup.add(
        types.InlineKeyboardButton(
            "📋 Список моих запросов", callback_data="my_requests"
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "🧹 Удалить все запросы", callback_data="delete_all_requests"
        )
    )

    # Дополнительные кнопки
    markup.add(
        types.InlineKeyboardButton(
            "📸 Instagram", url="https://www.instagram.com/82.auto"
        ),
        types.InlineKeyboardButton(
            "📢 Телеграм Канал", url="https://t.me/autofromkorea82"
        ),
    )

    welcome_text = (
        "👋 Добро пожаловать в официальный бот *82 Auto*!\n\n"
        "С помощью этого бота вы можете:\n"
        "• 🔍 Найти автомобиль, который вас интересует\n"
        "• 🧮 Получить расчёт стоимости автомобиля по предоставленной ссылке\n"
        "• 📬 Подписаться на наши социальные сети и быть в курсе всех новостей\n\n"
        "*Пожалуйста, выберите одно из действий ниже:*"
    )
    bot.send_message(
        message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup
    )


@bot.message_handler(commands=["add-user"])
def handle_add_user(message):
    if message.from_user.id != MANAGER:
        bot.reply_to(message, "❌ У вас нет прав для добавления пользователей.")
        return

    msg = bot.send_message(
        message.chat.id, "Введите ID пользователя для разрешения доступа к боту:"
    )
    bot.register_next_step_handler(msg, process_user_id_input)


def process_user_id_input(message):
    try:
        new_user_id = int(message.text.strip())
        ACCESS.add(new_user_id)
        save_access()
        bot.send_message(
            message.chat.id,
            f"✅ Пользователю с ID {new_user_id} разрешён доступ к боту.",
        )
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Введите корректный числовой ID.")


@bot.callback_query_handler(func=lambda call: call.data == "start")
def handle_start_callback(call):
    start_handler(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "my_requests")
def handle_my_requests(call):
    if not is_authorized(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ У вас нет доступа к боту.")
        return

    user_id = str(call.from_user.id)
    requests_list = user_requests.get(user_id, [])
    load_requests()

    if not requests_list:
        bot.answer_callback_query(call.id, "У вас пока нет сохранённых запросов.")
        return

    for idx, req in enumerate(requests_list, 1):
        text = (
            f"📌 *Запрос #{idx}:*\n"
            f"{req['manufacturer']} / {req['model_group']} / {req['model']} / {req['trim']}\n"
            f"Год: {req['year']}, Пробег: {req['mileage_from']}–{req['mileage_to']} км\n"
            f"Цвет: {req['color']}"
        )

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                f"🗑 Удалить запрос #{idx}", callback_data=f"delete_request_{idx - 1}"
            )
        )
        bot.send_message(
            call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_request_"))
def handle_delete_request(call):
    user_id = str(call.from_user.id)
    index = int(call.data.split("_")[2])
    if user_id not in user_requests or index >= len(user_requests[user_id]):
        bot.answer_callback_query(call.id, "⚠️ Запрос не найден.")
        return

    removed = user_requests[user_id].pop(index)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="start")
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="✅ Запрос успешно удалён.",
        reply_markup=markup,
    )

    print(f"🗑 Удалён запрос пользователя {user_id}: {removed}")
    save_requests(user_requests)
    load_requests()


@bot.callback_query_handler(func=lambda call: call.data == "delete_all_requests")
def handle_delete_all_requests(call):
    user_id = str(call.from_user.id)
    if user_id in user_requests:
        user_requests[user_id] = []
        save_requests(user_requests)
        load_requests()
        bot.send_message(call.message.chat.id, "✅ Все ваши запросы успешно удалены.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ У вас нет сохранённых запросов.")


@bot.callback_query_handler(func=lambda call: call.data == "search_car")
def handle_search_car(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Encar", callback_data="source_encar"),
        types.InlineKeyboardButton("KBChaChaCha", callback_data="source_kbchachacha"),
    )
    markup.add(
        types.InlineKeyboardButton("KCar", callback_data="source_kcar"),
    )

    bot.send_message(
        call.message.chat.id, "Выберите источник данных:", reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("source_"))
def handle_source_selection(call):
    source = call.data.split("_")[1]

    if source == "encar":
        manufacturers = get_manufacturers()
        if not manufacturers:
            bot.answer_callback_query(call.id, "Не удалось загрузить марки.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        for item in manufacturers:
            kr_name = item.get("DisplayValue", "Без названия")
            eng_name = item.get("Metadata", {}).get("EngName", [""])[0]
            callback_data = f"brand_encar_{eng_name}_{kr_name}"
            display_text = f"{eng_name}"
            markup.add(
                types.InlineKeyboardButton(display_text, callback_data=callback_data)
            )

        bot.edit_message_text(
            "Выбери марку автомобиля:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )
    elif source == "kbchachacha":
        manufacturers = get_kbchachacha_manufacturers()
        if not manufacturers:
            bot.answer_callback_query(call.id, "Не удалось загрузить марки.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        for item in manufacturers:
            kr_name = item.get("makerName", "Без названия")
            kr_name_translated = translations.get(kr_name, kr_name)
            maker_code = item.get("makerCode", "")
            callback_data = f"brand_kbchachacha_{kr_name_translated}_{maker_code}"
            display_text = f"{kr_name_translated}"
            markup.add(
                types.InlineKeyboardButton(display_text, callback_data=callback_data)
            )

        bot.edit_message_text(
            "Выбери марку автомобиля:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )
    elif source == "kcar":
        manufacturers = get_kcar_manufacturers()
        if not manufacturers:
            bot.answer_callback_query(call.id, "Не удалось загрузить марки KCar.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        for item in manufacturers:
            mnuftr_enm = item.get("mnuftrEnm", "Без названия")
            path = item.get("path", "")

            # Используем только код производителя (path) в callback_data,
            # чтобы избежать проблем с длиной и кодировкой
            callback_data = f"brand_kcar_{path}"
            display_text = mnuftr_enm

            markup.add(
                types.InlineKeyboardButton(display_text, callback_data=callback_data)
            )

        bot.edit_message_text(
            "Выбери марку автомобиля:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("brand_"))
def handle_brand_selection(call):
    parts = call.data.split("_", 3)
    source = parts[1]

    if source == "encar":
        eng_name = parts[2]
        kr_name = parts[3]

        # ... существующий код для Encar ...
        models = get_models_by_brand(kr_name)
        if not models:
            bot.answer_callback_query(call.id, "Не удалось загрузить модели.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        for item in models:
            model_kr = item.get("DisplayValue", "Без названия")
            model_eng = item.get("Metadata", {}).get("EngName", [""])[0]
            callback_data = f"model_{source}_{model_eng}_{model_kr}"
            display_text = f"{model_eng}"
            markup.add(
                types.InlineKeyboardButton(display_text, callback_data=callback_data)
            )

        bot.edit_message_text(
            f"Марка: {eng_name} ({kr_name})\nТеперь выбери модель:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )
    elif source == "kbchachacha":
        # Получаем maker_code из callback_data
        maker_code = parts[3]  # В случае KBChaChaCha, parts[3] содержит maker_code

        models = get_kbchachacha_models(maker_code)
        if not models:
            bot.answer_callback_query(call.id, "Не удалось загрузить модели.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        for item in models:
            model_kr = item.get("className", "Без названия")
            class_code = item.get("classCode", "")
            # Убедимся, что class_code не содержит подчеркивания
            if "_" in class_code:
                class_code = class_code.split("_")[0]
            # Формируем callback_data с maker_code и class_code
            callback_data = f"model_kbchachacha_{maker_code}_{class_code}"
            display_text = f"{model_kr}"
            markup.add(
                types.InlineKeyboardButton(display_text, callback_data=callback_data)
            )

        bot.edit_message_text(
            f"Марка: {kr_name}\nТеперь выбери модель:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )
    elif source == "kcar":
        # Для KCar у нас только код производителя в формате brand_kcar_{path}
        mnuftr_path = parts[2]

        # Получаем данные о производителе снова, чтобы отобразить имя
        manufacturers = get_kcar_manufacturers()
        selected_manufacturer = next(
            (m for m in manufacturers if m.get("path") == mnuftr_path), None
        )

        if not selected_manufacturer:
            bot.answer_callback_query(call.id, "Производитель не найден.")
            return

        manufacturer_name = selected_manufacturer.get("mnuftrEnm", "Без названия")

        # Получаем модели для выбранного производителя
        models = get_kcar_models(mnuftr_path)
        if not models:
            bot.answer_callback_query(call.id, "Не удалось загрузить модели.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        for model in models:
            model_name = model.get("modelGrpNm", "Без названия")
            model_grp_cd = model.get("modelGrpCd", "")
            car_count = model.get("count", 0)

            # Добавляем количество доступных автомобилей в название кнопки
            # Отображаем модели только если есть доступные автомобили
            if car_count > 0:
                display_text = f"{model_name} ({car_count})"

                # Используем mnuftr_path и model_grp_cd в callback_data
                callback_data = f"model_kcar_{mnuftr_path}_{model_grp_cd}"

                markup.add(
                    types.InlineKeyboardButton(
                        display_text, callback_data=callback_data
                    )
                )

        bot.edit_message_text(
            f"Марка: {manufacturer_name}\nТеперь выбери модель:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )

        # Сохраним данные о производителе в user_search_data
        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        user_search_data[user_id].update(
            {
                "manufacturer": manufacturer_name,
                "source": "kcar",
                "mnuftr_path": mnuftr_path,
            }
        )


def translate_trim(text):
    return (
        text.replace("가솔린+전기", "Гибрид")
        .replace("가솔린", "Бензин")
        .replace("디젤", "Дизель")
        .replace("전기", "Электро")
        .replace("2WD", "2WD")
        .replace("4WD", "4WD")
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("model_"))
def handle_model_selection(call):
    parts = call.data.split("_", 3)  # Split into 4 parts initially
    source = parts[1]

    if source == "encar":
        model_eng = parts[2]
        model_kr = parts[3]

        # Get manufacturer and model from message text
        message_text = call.message.text
        brand_line = next(
            (line for line in message_text.split("\n") if "Марка:" in line), ""
        )
        brand_part = brand_line.replace("Марка:", "").strip()
        if " (" in brand_part:
            brand_eng, brand_kr = brand_part.split(" (")
            brand_kr = brand_kr.rstrip(")")
        else:
            brand_eng = brand_part
            brand_kr = ""

        # Get generations for selected model
        generations = get_generations_by_model(brand_kr, model_kr)
        if not generations:
            bot.answer_callback_query(call.id, "Не удалось загрузить поколения.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)
        for item in generations:
            gen_kr = item.get("DisplayValue", "Без названия")
            gen_eng = item.get("Metadata", {}).get("EngName", [""])[0]

            start_raw = str(item.get("Metadata", {}).get("ModelStartDate", [""])[0])
            end_raw = str(item.get("Metadata", {}).get("ModelEndDate", [""])[0])

            def format_date(date_str):
                if len(date_str) == 6:
                    return f"{date_str[4:6]}.{date_str[0:4]}"
                return ""

            start_date = format_date(start_raw)
            end_date = format_date(end_raw) if len(end_raw) > 0 else "н.в."

            period = f"({start_date} — {end_date})" if start_date else ""

            callback_data = f"generation_{source}_{gen_eng}_{gen_kr}"
            print(
                f"🔍 DEBUG Creating generation button with callback_data: {callback_data}"
            )  # Debug print
            translated_gen_kr = translate_phrase(gen_kr)
            translated_gen_eng = translate_phrase(gen_eng)
            display_text = f"{translated_gen_kr} {translated_gen_eng} {period}".strip()
            markup.add(
                types.InlineKeyboardButton(display_text, callback_data=callback_data)
            )

        # Save initial data in user_search_data
        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        user_search_data[user_id].update(
            {
                "manufacturer": brand_eng,
                "model_group": model_eng,
                "model": model_eng,
                "source": source,
            }
        )

        print(f"✅ DEBUG Сохраненные данные для пользователя {user_id}:")
        print(user_search_data[user_id])

        bot.edit_message_text(
            f"Марка: {brand_eng.strip()} ({brand_kr})\nМодель: {model_eng} ({model_kr})\nТеперь выбери поколение:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )

    elif source == "kbchachacha":
        # For KBChaChaCha, we need maker_code and class_code
        maker_code = parts[2]
        class_code = parts[3]

        # Get the generations for this model
        generations = get_kbchachacha_generations(maker_code, class_code)
        if not generations:
            bot.answer_callback_query(call.id, "Не удалось загрузить поколения.")
            return

        # Create markup for generation selection
        markup = types.InlineKeyboardMarkup(row_width=2)
        for item in generations:
            gen_kr = item.get("carName", "Без названия")
            car_code = item.get("carCode", "")
            from_year = item.get("fromYear", "")
            to_year = item.get("toYear", "")

            # Format the period
            period = f"({from_year} — {to_year if to_year != '현재' else 'н.в.'})"

            callback_data = (
                f"generation_kbchachacha_{maker_code}_{class_code}_{car_code}"
            )
            print(
                f"🔍 DEBUG Creating KBChaChaCha generation button with callback_data: {callback_data}"
            )  # Debug print
            translated_gen_kr = translate_phrase(gen_kr)
            display_text = f"{translated_gen_kr} {period}".strip()
            markup.add(
                types.InlineKeyboardButton(display_text, callback_data=callback_data)
            )

        # Get the message text to display the selected options
        message_text = call.message.text
        brand_line = next(
            (line for line in message_text.split("\n") if "Марка:" in line), ""
        )
        model_line = next(
            (line for line in message_text.split("\n") if "Модель:" in line), ""
        )

        # Extract values
        brand = brand_line.replace("Марка:", "").strip()
        model = model_line.replace("Модель:", "").strip()

        # Save initial data in user_search_data
        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        user_search_data[user_id].update(
            {
                "manufacturer": brand,
                "model_group": model,
                "model": model,
                "source": source,
                "maker_code": maker_code,
                "class_code": class_code,
            }
        )

        print(f"✅ DEBUG Сохраненные данные для пользователя {user_id}:")
        print(user_search_data[user_id])

        bot.edit_message_text(
            f"Марка: {brand}\nМодель: {model}\nТеперь выбери поколение:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )

    elif source == "kcar":
        # Для KCar формат: model_kcar_mnuftr_path_model_grp_cd
        mnuftr_path = parts[2]
        model_grp_cd = parts[3]

        # Получаем данные о пользователе
        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        # Получаем данные о производителе
        manufacturers = get_kcar_manufacturers()
        selected_manufacturer = next(
            (m for m in manufacturers if m.get("path") == mnuftr_path), None
        )

        if not selected_manufacturer:
            bot.answer_callback_query(call.id, "Производитель не найден.")
            return

        manufacturer_name = selected_manufacturer.get("mnuftrEnm", "Без названия")

        # Получаем данные о модели
        models = get_kcar_models(mnuftr_path)
        selected_model = next(
            (m for m in models if m.get("modelGrpCd") == model_grp_cd), None
        )

        if not selected_model:
            bot.answer_callback_query(call.id, "Модель не найдена.")
            return

        model_name = selected_model.get("modelGrpNm", "Без названия")

        # Получаем список поколений для выбранной модели
        generations = get_kcar_generations(mnuftr_path, model_grp_cd)
        if not generations:
            bot.answer_callback_query(call.id, "Не удалось загрузить поколения модели.")
            return

        # Создаем клавиатуру с поколениями
        markup = types.InlineKeyboardMarkup(row_width=1)
        for gen in generations:
            model_nm = gen.get("modelNm", "Без названия")
            model_cd = gen.get("modelCd", "")
            car_count = gen.get("count", 0)
            production_year = gen.get("prdcnYear", "")

            # Переводим название поколения
            translated_model_nm = translate_phrase(model_nm)

            # Добавляем только модели с доступными автомобилями
            if car_count > 0:
                display_text = f"{translated_model_nm} {production_year} ({car_count})"
                callback_data = (
                    f"generation_kcar_{mnuftr_path}_{model_grp_cd}_{model_cd}"
                )

                markup.add(
                    types.InlineKeyboardButton(
                        display_text, callback_data=callback_data
                    )
                )

        # Сохраняем данные о выбранной модели
        user_search_data[user_id].update(
            {
                "model_group": model_name,
                "model_grp_cd": model_grp_cd,
            }
        )

        bot.edit_message_text(
            f"Марка: {manufacturer_name}\nМодель: {model_name}\nВыберите поколение:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("generation_"))
def handle_generation_selection(call):
    print(f"🔍 DEBUG: Received generation callback data: {call.data}")
    parts = call.data.split("_")  # Split all parts
    print(f"🔍 DEBUG: Split parts: {parts}")
    source = parts[1]
    print(f"🔍 DEBUG: Source: {source}")

    if source == "encar":
        generation_eng = parts[2]
        generation_kr = "_".join(
            parts[3:]
        )  # Join the remaining parts in case kr name contains underscores
        print(
            f"🔍 DEBUG Encar - generation_eng: {generation_eng}, generation_kr: {generation_kr}"
        )
        message_text = call.message.text
        print(f"🔍 DEBUG Message text: {message_text}")

        brand_line = next(
            (line for line in message_text.split("\n") if "Марка:" in line), ""
        )
        model_line = next(
            (line for line in message_text.split("\n") if "Модель:" in line), ""
        )

        try:
            brand_eng, brand_kr = brand_line.replace("Марка:", "").strip().split(" (")
            brand_kr = brand_kr.rstrip(")")
            model_eng, model_kr = model_line.replace("Модель:", "").strip().split(" (")
            model_kr = model_kr.rstrip(")")
        except ValueError as e:
            print(f"❌ ERROR parsing brand/model: {e}")
            print(f"brand_line: {brand_line}")
            print(f"model_line: {model_line}")
            bot.answer_callback_query(call.id, "Ошибка при обработке данных.")
            return

        print(f"🔍 DEBUG Brand: {brand_eng} ({brand_kr})")
        print(f"🔍 DEBUG Model: {model_eng} ({model_kr})")

        generations = get_generations_by_model(brand_kr, model_kr)
        if not generations:
            print("❌ ERROR: No generations found")
            bot.answer_callback_query(call.id, "Не удалось загрузить поколения.")
            return

        selected_generation = next(
            (
                g
                for g in generations
                if g.get("DisplayValue") == generation_kr
                or g.get("Metadata", {}).get("EngName", [""])[0] == generation_eng
            ),
            None,
        )
        if not selected_generation:
            print("❌ ERROR: Selected generation not found")
            print(
                f"Looking for DisplayValue={generation_kr} or EngName={generation_eng}"
            )
            print("Available generations:")
            for g in generations:
                print(f"- DisplayValue: {g.get('DisplayValue')}")
                print(f"  EngName: {g.get('Metadata', {}).get('EngName', [''])[0]}")
            bot.answer_callback_query(call.id, "Не удалось определить поколение.")
            return

        print(f"✅ Found selected generation: {selected_generation}")

        trims = get_trims_by_generation(brand_kr, model_kr, generation_kr)
        if not trims:
            print("❌ ERROR: No trims found")
            bot.answer_callback_query(call.id, "Не удалось загрузить комплектации.")
            return

        print(f"✅ Found {len(trims)} trims")

        markup = types.InlineKeyboardMarkup(row_width=2)
        for item in trims:
            trim_kr = item.get("DisplayValue", "Без названия")
            trim_eng = item.get("Metadata", {}).get("EngName", [""])[0]
            callback_data = f"trim_{source}_{trim_eng}_{trim_kr}"
            translated_text = translations.get(
                trim_eng, translations.get(trim_kr, trim_eng or trim_kr)
            )
            display_text = translate_trim(translated_text)
            markup.add(
                types.InlineKeyboardButton(display_text, callback_data=callback_data)
            )

        # Save generation data
        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        # Save ALL necessary data
        user_search_data[user_id].update(
            {
                "manufacturer": brand_kr.strip(),  # Save Korean name for manufacturer
                "manufacturer_eng": brand_eng.strip(),  # Save English name for manufacturer
                "model_group": model_kr.strip(),  # Save Korean name for model
                "model_group_eng": model_eng.strip(),  # Save English name for model
                "model": model_kr.strip(),  # Save Korean name for model
                "model_eng": model_eng.strip(),  # Save English name for model
                "generation": generation_eng,
                "generation_kr": generation_kr,
                "source": source,
            }
        )

        print(f"✅ Saved user data: {user_search_data[user_id]}")

        bot.edit_message_text(
            f"Марка: {brand_eng.strip()} ({brand_kr})\nМодель: {model_eng} ({model_kr})\nПоколение: {generation_eng} ({generation_kr})\nТеперь выбери комплектацию:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )

    elif source == "kbchachacha":
        try:
            # Extract codes from callback data
            maker_code = parts[2]
            class_code = parts[3]
            car_code = parts[4]
            print(
                f"🔍 DEBUG KBChaChaCha - maker_code: {maker_code}, class_code: {class_code}, car_code: {car_code}"
            )
        except IndexError as e:
            print(f"❌ ERROR parsing KBChaChaCha codes: {e}")
            print(f"Available parts: {parts}")
            bot.answer_callback_query(call.id, "Ошибка при обработке данных.")
            return

        # Get models for this generation
        models = get_kbchachacha_models_by_generation(maker_code, class_code, car_code)
        if not models:
            print("❌ ERROR: No models found")
            bot.answer_callback_query(call.id, "Не удалось загрузить модели.")
            return

        print(f"✅ Found {len(models)} models")

        # Create markup for model selection
        markup = types.InlineKeyboardMarkup(row_width=2)
        for model in models:
            model_name = model.get("modelName", "Без названия")
            model_code = model.get("modelCode", "")
            grades = model.get("grades", [])
            count = model.get("count", 0)
            print(f"Adding model: {model_name} (code: {model_code})")

            # For each model, add buttons for each grade if available
            if grades:
                for grade in grades:
                    grade_name = grade.get("gradeName", "")
                    model_grade_code = grade.get("modelGradeCode", "")
                    display_name = (
                        f"{model_name} {grade_name}"
                        if grade_name != "기본형"
                        else model_name
                    )
                    callback_data = f"trim_kbchachacha_{maker_code}_{class_code}_{car_code}_{model_grade_code}"
                    if count > 0:  # Only add models that have available cars
                        markup.add(
                            types.InlineKeyboardButton(
                                display_name, callback_data=callback_data
                            )
                        )
            else:
                # If no grades, add just the model
                callback_data = f"trim_kbchachacha_{maker_code}_{class_code}_{car_code}_{model_code}|002"
                if count > 0:  # Only add models that have available cars
                    markup.add(
                        types.InlineKeyboardButton(
                            model_name, callback_data=callback_data
                        )
                    )

        # Get the message text to display the selected options
        message_text = call.message.text
        brand_line = next(
            (line for line in message_text.split("\n") if "Марка:" in line), ""
        )
        model_line = next(
            (line for line in message_text.split("\n") if "Модель:" in line), ""
        )

        # Extract values
        brand = brand_line.replace("Марка:", "").strip()
        model = model_line.replace("Модель:", "").strip()

        # Save car_code in user data
        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        user_search_data[user_id].update({"car_code": car_code})

        print(f"✅ Saved user data: {user_search_data[user_id]}")

        bot.edit_message_text(
            f"Марка: {brand}\nМодель: {model}\nТеперь выбери модификацию:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )

    elif source == "kcar":
        # Для KCar формат: generation_kcar_mnuftr_path_model_grp_cd_model_cd
        if len(parts) < 5:
            bot.answer_callback_query(call.id, "Неверный формат данных.")
            return

        mnuftr_path = parts[2]
        model_grp_cd = parts[3]
        model_cd = parts[4]

        print(
            f"🔍 DEBUG KCar - mnuftr_path: {mnuftr_path}, model_grp_cd: {model_grp_cd}, model_cd: {model_cd}"
        )

        # Получаем информацию о пользователе
        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        # Получаем данные о поколении
        generations = get_kcar_generations(mnuftr_path, model_grp_cd)
        selected_generation = next(
            (g for g in generations if g.get("modelCd") == model_cd), None
        )

        if not selected_generation:
            bot.answer_callback_query(call.id, "Поколение не найдено.")
            return

        generation_name = selected_generation.get("modelNm", "")
        translated_generation = translate_phrase(generation_name)

        # Получаем информацию о производителе и модели из сообщения
        message_text = call.message.text
        brand_line = next(
            (line for line in message_text.split("\n") if "Марка:" in line), ""
        )
        model_line = next(
            (line for line in message_text.split("\n") if "Модель:" in line), ""
        )

        brand = brand_line.replace("Марка:", "").strip()
        model = model_line.replace("Модель:", "").strip()

        # Определяем диапазон годов выпуска
        production_year = selected_generation.get("prdcnYear", "")

        # Извлекаем годы из строки формата "(19~22년)" или "(22년~현재)"
        from_year = None
        to_year = None

        if production_year:
            # Убираем скобки и делим по символу ~
            year_range = production_year.strip("()").split("~")
            if len(year_range) == 2:
                from_year_str = year_range[0].strip("년")
                to_year_str = year_range[1].strip("년현재")

                # Определяем базовый год (2000 или 1900)
                base_year = 2000 if len(from_year_str) <= 2 else 1900

                # Преобразуем строки в числа
                try:
                    from_year = int(from_year_str) + (
                        base_year if len(from_year_str) <= 2 else 0
                    )

                    if to_year_str:  # Если не пустая строка (не "현재")
                        to_year = int(to_year_str) + (
                            base_year if len(to_year_str) <= 2 else 0
                        )
                    else:
                        to_year = datetime.now().year
                except ValueError:
                    from_year = datetime.now().year - 5
                    to_year = datetime.now().year

        # Если не удалось извлечь годы из строки, используем значения по умолчанию
        if not from_year or not to_year:
            from_year = datetime.now().year - 5
            to_year = datetime.now().year

        print(f"🔍 DEBUG KCar - Годы выпуска: с {from_year} по {to_year}")

        # Создаем клавиатуру для выбора года
        year_markup = types.InlineKeyboardMarkup(row_width=4)
        for y in range(from_year, to_year + 1):
            year_markup.add(
                types.InlineKeyboardButton(
                    str(y),
                    callback_data=f"year_kcar_{mnuftr_path}_{model_grp_cd}_{model_cd}_{y}",
                )
            )

        # Сохраняем данные о выбранном поколении
        user_search_data[user_id].update(
            {
                "generation": translated_generation,
                "generation_kr": generation_name,
                "model_cd": model_cd,
            }
        )

        print(f"✅ Saved user data: {user_search_data[user_id]}")

        # Отправляем сообщение с выбором года
        bot.edit_message_text(
            f"Марка: {brand}\nМодель: {model}\nПоколение: {translated_generation}\nТеперь выберите год выпуска:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=year_markup,
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("trim_"))
def handle_trim_selection(call):
    parts = call.data.split("_")
    source = parts[1]

    if source == "encar":
        # Handle Encar format: trim_encar_eng_name_kr_name
        trim_eng = parts[2]
        trim_kr = (
            "_".join(parts[3:]) if len(parts) > 3 else parts[2]
        )  # Handle trims with underscores

        message_text = call.message.text
        brand_line = next(
            (line for line in message_text.split("\n") if "Марка:" in line), ""
        )
        model_line = next(
            (line for line in message_text.split("\n") if "Модель:" in line), ""
        )
        generation_line = next(
            (line for line in message_text.split("\n") if "Поколение:" in line), ""
        )

        # Extract brand information
        brand_eng, brand_kr = brand_line.replace("Марка:", "").strip().split(" (")
        brand_kr = brand_kr.rstrip(")")

        # Extract model information
        model_part = model_line.replace("Модель:", "").strip()
        model_eng, model_kr = model_part.split(" (")
        model_kr = model_kr.rstrip(")")

        # Extract generation information
        generation_part = generation_line.replace("Поколение:", "").strip()
        generation_eng, generation_kr = generation_part.split(" (")
        generation_kr = generation_kr.rstrip(")")

        # Get generations data
        generations = get_generations_by_model(brand_kr, model_kr)
        selected_generation = next(
            (
                g
                for g in generations
                if g.get("DisplayValue") == generation_kr
                or generation_kr in g.get("DisplayValue", "")
                or generation_eng in g.get("Metadata", {}).get("EngName", [""])[0]
            ),
            None,
        )

        if not selected_generation:
            bot.answer_callback_query(call.id, "Не удалось определить поколение.")
            return

        # Get year range from generation metadata
        start_raw = str(
            selected_generation.get("Metadata", {}).get("ModelStartDate", [""])[0]
        )
        end_raw = str(
            selected_generation.get("Metadata", {}).get("ModelEndDate", [""])[0] or ""
        )

        current_year = datetime.now().year
        current_month = datetime.now().month

        # Calculate start and end years
        start_year = int(start_raw[:4]) if len(start_raw) == 6 else current_year

        if end_raw and end_raw.isdigit():
            end_year = int(end_raw[:4])
        else:
            end_year = current_year

        # Create year selection markup
        year_markup = types.InlineKeyboardMarkup(row_width=4)
        for y in range(start_year, end_year + 1):
            year_markup.add(
                types.InlineKeyboardButton(str(y), callback_data=f"year_{source}_{y}")
            )

        # Save ALL necessary data
        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        user_search_data[user_id].update(
            {
                "manufacturer": brand_kr.strip(),
                "manufacturer_eng": brand_eng.strip(),
                "model_group": model_kr.strip(),
                "model_group_eng": model_eng.strip(),
                "model": model_kr.strip(),
                "model_eng": model_eng.strip(),
                "generation": generation_eng,
                "generation_kr": generation_kr,
                "trim": trim_kr.strip(),
                "trim_eng": trim_eng.strip(),
                "source": source,
            }
        )

        print(f"✅ DEBUG Saved user data: {user_search_data[user_id]}")

        # Send messages
        bot.send_message(
            call.message.chat.id,
            f"Марка: {brand_eng.strip()} ({brand_kr})\n"
            f"Модель: {model_eng} ({model_kr})\n"
            f"Поколение: {generation_eng} ({generation_kr})\n"
            f"Комплектация: {trim_eng} ({trim_kr})",
        )
        bot.send_message(
            call.message.chat.id,
            "Выбери год выпуска автомобиля:",
            reply_markup=year_markup,
        )

    elif source == "kbchachacha":
        # Handle KBChaChaCha format: trim_kbchachacha_maker_code_class_code_car_code_model_grade_code
        if len(parts) < 6:
            bot.answer_callback_query(call.id, "Неверный формат данных.")
            return

        maker_code = parts[2]
        class_code = parts[3]
        car_code = parts[4]
        model_grade_code = parts[5]  # Now this can be "27034|002" format

        print(f"🔍 DEBUG KBChaChaCha callback data: {call.data}")
        print(f"🔍 DEBUG model_grade_code: {model_grade_code}")

        # Split model_grade_code if it contains the separator
        if "|" in model_grade_code:
            model_code, grade_code = model_grade_code.split("|")
        else:
            model_code = model_grade_code
            grade_code = "002"  # Default grade code

        print(f"🔍 DEBUG model_code: {model_code}, grade_code: {grade_code}")

        # Get model data from the API again to ensure we have fresh data
        models = get_kbchachacha_models_by_generation(maker_code, class_code, car_code)
        selected_model = next(
            (m for m in models if m.get("modelCode") == model_code), None
        )

        if not selected_model:
            print(f"❌ ERROR: Model not found for model_code {model_code}")
            print(f"Available models: {[m.get('modelCode') for m in models]}")
            bot.answer_callback_query(call.id, "Модель не найдена.")
            return

        model_name = selected_model.get("modelName", "")
        print(f"✅ Found model: {model_name}")

        message_text = call.message.text
        brand_line = next(
            (line for line in message_text.split("\n") if "Марка:" in line), ""
        )
        model_line = next(
            (line for line in message_text.split("\n") if "Модель:" in line), ""
        )
        # Извлекаем название марки и модели
        brand = brand_line.replace("Марка:", "").strip()
        model = model_line.replace("Модель:", "").strip()

        # Get the generation to determine the year range
        generations = get_kbchachacha_generations(maker_code, class_code)
        selected_generation = None
        for gen in generations:
            if gen.get("carCode") == car_code:
                selected_generation = gen
                break

        if not selected_generation:
            bot.answer_callback_query(call.id, "Не удалось определить поколение.")
            return

        from_year = int(selected_generation.get("fromYear", datetime.now().year))
        to_year_str = selected_generation.get("toYear", "")

        # If toYear is "현재" (current) or empty, use current year
        if to_year_str == "현재" or not to_year_str:
            to_year = datetime.now().year
        else:
            to_year = int(to_year_str)

        # Create year selection markup
        year_markup = types.InlineKeyboardMarkup(row_width=4)
        for y in range(from_year, to_year + 1):
            year_markup.add(
                types.InlineKeyboardButton(
                    str(y),
                    callback_data=f"year_kbchachacha_{maker_code}_{class_code}_{car_code}_{model_code}_{y}",
                )
            )

        # Save the selected data for later use
        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        user_search_data[user_id].update(
            {
                "manufacturer": brand,
                "model_group": model_name,
                "model": model_name,
                "source": source,
                "maker_code": maker_code,
                "class_code": class_code,
                "car_code": car_code,
                "model_code": model_code,
                "model_grade_code": model_grade_code,
                "year": from_year,  # Устанавливаем начальный год как значение по умолчанию
            }
        )

        print(f"✅ DEBUG Сохраненные данные для пользователя {user_id}:")
        print(user_search_data[user_id])

        # Get the car name (generation) from the selected generation
        generation_name = selected_generation.get("carName", "")

        bot.edit_message_text(
            f"Марка: {brand}\nМодель: {generation_name}\nМодификация: {model_name}\nТеперь выбери год выпуска автомобиля:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=year_markup,
        )

    elif source == "kcar":
        # Handle KCar format: trim_kcar_mnuftr_path_model_grp_cd_model_grade_code
        if len(parts) < 6:
            bot.answer_callback_query(call.id, "Неверный формат данных.")
            return

        mnuftr_path = parts[2]
        model_grp_cd = parts[3]
        model_grade_code = parts[4]  # Now this can be "27034|002" format

        print(f"🔍 DEBUG KCar callback data: {call.data}")
        print(f"🔍 DEBUG model_grade_code: {model_grade_code}")

        # Split model_grade_code if it contains the separator
        if "|" in model_grade_code:
            model_code, grade_code = model_grade_code.split("|")
        else:
            model_code = model_grade_code
            grade_code = "002"  # Default grade code

        print(f"🔍 DEBUG model_code: {model_code}, grade_code: {grade_code}")

        # Get model data from the API again to ensure we have fresh data
        models = get_kcar_models(mnuftr_path)
        selected_model = next(
            (m for m in models if m.get("modelGrpCd") == model_code), None
        )

        if not selected_model:
            print(f"❌ ERROR: Model not found for model_code {model_code}")
            print(f"Available models: {[m.get('modelGrpCd') for m in models]}")
            bot.answer_callback_query(call.id, "Модель не найдена.")
            return

        model_name = selected_model.get("modelGrpNm", "")
        print(f"✅ Found model: {model_name}")

        message_text = call.message.text
        brand_line = next(
            (line for line in message_text.split("\n") if "Марка:" in line), ""
        )
        model_line = next(
            (line for line in message_text.split("\n") if "Модель:" in line), ""
        )
        # Извлекаем название марки и модели
        brand = brand_line.replace("Марка:", "").strip()
        model = model_line.replace("Модель:", "").strip()

        # Get the generation to determine the year range
        generations = get_kcar_generations(mnuftr_path, model_grp_cd)
        selected_generation = None
        for gen in generations:
            if gen.get("modelCode") == model_code:
                selected_generation = gen
                break

        if not selected_generation:
            bot.answer_callback_query(call.id, "Не удалось определить поколение.")
            return

        from_year = int(selected_generation.get("fromYear", datetime.now().year))
        to_year_str = selected_generation.get("toYear", "")

        # If toYear is "현재" (current) or empty, use current year
        if to_year_str == "현재" or not to_year_str:
            to_year = datetime.now().year
        else:
            to_year = int(to_year_str)

        # Create year selection markup
        year_markup = types.InlineKeyboardMarkup(row_width=4)
        for y in range(from_year, to_year + 1):
            year_markup.add(
                types.InlineKeyboardButton(
                    str(y),
                    callback_data=f"year_kcar_{mnuftr_path}_{model_grp_cd}_{model_code}_{model_grade_code}_{y}",
                )
            )

        # Save the selected data for later use
        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        user_search_data[user_id].update(
            {
                "manufacturer": brand,
                "model_group": model_name,
                "model_grp_cd": model_grp_cd,
                "model_code": model_code,
                "model_grade_code": model_grade_code,
                "year": from_year,  # Устанавливаем начальный год как значение по умолчанию
            }
        )

        print(f"✅ DEBUG Сохраненные данные для пользователя {user_id}:")
        print(user_search_data[user_id])

        # Get the car name (generation) from the selected generation
        generation_name = selected_generation.get("mdlNm", "")

        bot.edit_message_text(
            f"Марка: {brand}\nМодель: {model_name}\nМодификация: {model_name}\nТеперь выбери год выпуска автомобиля:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=year_markup,
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("year_"))
def handle_year_selection(call):
    print(f"🔍 DEBUG: Получен callback для выбора года: {call.data}")
    parts = call.data.split("_")
    source = parts[1]

    if source == "kbchachacha":
        # Handle KBChaChaCha format: year_kbchachacha_maker_code_class_code_car_code_model_code_year
        if len(parts) < 7:
            bot.answer_callback_query(call.id, "Неверный формат данных.")
            return
        maker_code = parts[2]
        class_code = parts[3]
        car_code = parts[4]
        model_code = parts[5]
        selected_year = int(parts[6])

        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        # Preserve existing data like model_grade_code instead of overwriting it
        existing_data = user_search_data[user_id].copy()
        # Update with KBChaChaCha specific data
        existing_data.update(
            {
                "year": selected_year,
                "source": source,
                "maker_code": maker_code,
                "class_code": class_code,
                "car_code": car_code,
                "model_code": model_code,
            }
        )
        # Only set model_grade_code if it doesn't already exist
        if "model_grade_code" not in existing_data:
            existing_data["model_grade_code"] = f"{model_code}|002"

        user_search_data[user_id] = existing_data
    elif source == "encar":
        # Handle Encar format: year_encar_year
        selected_year = int(parts[2])

        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}
        user_search_data[user_id]["year"] = selected_year
        user_search_data[user_id]["source"] = source
    elif source == "kcar":
        # Handle KCar format: year_kcar_mnuftr_path_model_grp_cd_model_cd_year
        if len(parts) < 6:
            bot.answer_callback_query(call.id, "Неверный формат данных.")
            print(f"❌ ERROR: Неверный формат данных callback: {call.data}")
            return

        mnuftr_path = parts[2]
        model_grp_cd = parts[3]
        model_cd = parts[4]
        selected_year = int(parts[5])

        print(
            f"🔍 DEBUG KCar - mnuftr_path: {mnuftr_path}, model_grp_cd: {model_grp_cd}, model_cd: {model_cd}, year: {selected_year}"
        )

        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        # Обновляем данные пользователя с выбранным годом
        user_search_data[user_id].update(
            {
                "year": selected_year,
                "source": source,
                "mnuftr_path": mnuftr_path,
                "model_grp_cd": model_grp_cd,
                "model_cd": model_cd,
            }
        )

        print(f"✅ DEBUG user_data after year selection: {user_search_data[user_id]}")

        # Получаем список конфигураций для выбранного поколения
        try:
            configurations = get_kcar_configurations(
                mnuftr_path, model_grp_cd, model_cd
            )
            print(f"🔍 DEBUG: Получено конфигураций: {len(configurations)}")

            if not configurations:
                bot.answer_callback_query(call.id, "Не удалось загрузить конфигурации.")
                print("❌ ERROR: Пустой список конфигураций")
                return

            # Создаем клавиатуру для выбора конфигурации
            markup = types.InlineKeyboardMarkup(row_width=1)
            for config in configurations:
                grd_nm = config.get("grdNm", "Без названия")
                grd_cd = config.get("grdCd", "")
                car_count = config.get("count", 0)

                print(
                    f"🔍 DEBUG: Конфигурация {grd_nm} (код: {grd_cd}, количество: {car_count})"
                )

                # Переводим название конфигурации
                translated_grd_nm = translate_phrase(grd_nm)

                # Добавляем только конфигурации с доступными автомобилями
                if car_count > 0:
                    display_text = f"{translated_grd_nm} ({car_count})"
                    callback_data = f"config_kcar_{mnuftr_path}_{model_grp_cd}_{model_cd}_{grd_cd}_{selected_year}"

                    print(
                        f"🔍 DEBUG: Добавляем кнопку: {display_text}, callback: {callback_data}"
                    )

                    markup.add(
                        types.InlineKeyboardButton(
                            display_text, callback_data=callback_data
                        )
                    )

            # Получаем информацию о модели из текста сообщения
            message_text = call.message.text
            brand_line = next(
                (line for line in message_text.split("\n") if "Марка:" in line), ""
            )
            model_line = next(
                (line for line in message_text.split("\n") if "Модель:" in line), ""
            )
            generation_line = next(
                (line for line in message_text.split("\n") if "Поколение:" in line), ""
            )

            brand = brand_line.replace("Марка:", "").strip()
            model = model_line.replace("Модель:", "").strip()
            generation = (
                generation_line.replace("Поколение:", "").strip()
                if generation_line
                else ""
            )

            # Отправляем сообщение с выбором конфигурации
            bot.edit_message_text(
                f"Марка: {brand}\nМодель: {model}\nПоколение: {generation}\nГод: {selected_year}\nВыберите конфигурацию:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup,
            )
            return
        except Exception as e:
            print(f"❌ ERROR при получении конфигураций: {e}")
            bot.answer_callback_query(
                call.id, "Произошла ошибка при получении конфигураций."
            )
            return

    # Если не был выбран KCar, используем общий код для Encar и KBChaChaCha
    print(f"✅ DEBUG user_data after year selection: {user_search_data[user_id]}")

    # Create mileage selection markup
    mileage_markup = types.InlineKeyboardMarkup(row_width=4)
    for value in range(0, 200001, 10000):
        mileage_markup.add(
            types.InlineKeyboardButton(
                f"{value} км",
                callback_data=f"mileage_from_{source}_{selected_year}_{value}",
            )
        )

    # Get the message text to display the selected options
    message_text = call.message.text
    bot.send_message(
        call.message.chat.id,
        f"{message_text}\nГод выпуска: {selected_year}\nТеперь выбери минимальный пробег:",
        reply_markup=mileage_markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("mileage_from_"))
def handle_mileage_from(call):
    parts = call.data.split("_")
    source = parts[2]
    year = int(parts[3])  # Get the selected year
    mileage_from = int(parts[4])  # Get the selected mileage

    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    # Save mileage_from and year
    user_search_data[user_id]["mileage_from"] = mileage_from
    user_search_data[user_id]["year"] = year

    # Create mileage selection markup for maximum mileage
    mileage_markup = types.InlineKeyboardMarkup(row_width=4)
    for value in range(10000, 200001, 10000):
        mileage_markup.add(
            types.InlineKeyboardButton(
                f"{value} км",
                callback_data=f"mileage_to_{source}_{year}_{mileage_from}_{value}",
            )
        )

    # Get the message text to display the selected options
    message_text = call.message.text
    brand_line = next(
        (line for line in message_text.split("\n") if "Марка:" in line), ""
    )
    model_line = next(
        (line for line in message_text.split("\n") if "Модель:" in line), ""
    )

    # Extract values
    brand = brand_line.replace("Марка:", "").strip()
    model = model_line.replace("Модель:", "").strip()

    bot.edit_message_text(
        f"Марка: {brand}\nМодель: {model}\nГод выпуска: {year}\nМинимальный пробег: {mileage_from} км\nТеперь выбери максимальный пробег:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=mileage_markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("mileage_to_"))
def handle_mileage_to(call):
    parts = call.data.split("_")
    source = parts[2]
    year = int(parts[3])
    mileage_from = int(parts[4])
    mileage_to = int(parts[5])

    user_id = call.from_user.id
    user_data = user_search_data.get(user_id, {})

    # Update the user data with mileage values
    updated_data = {
        **user_data,  # Keep all existing data
        "year": year,
        "mileage_from": mileage_from,
        "mileage_to": mileage_to,
    }

    # Create color selection markup
    markup = types.InlineKeyboardMarkup(row_width=2)
    if source == "kbchachacha":
        for kr, color_data in KBCHACHACHA_COLORS.items():
            markup.add(
                types.InlineKeyboardButton(
                    color_data["ru"], callback_data=f"color_{source}_{kr}"
                )
            )
    else:
        for kr, ru in COLOR_TRANSLATIONS.items():
            markup.add(
                types.InlineKeyboardButton(ru, callback_data=f"color_{source}_{kr}")
            )

    user_search_data[user_id] = updated_data

    print(f"✅ DEBUG user_data after mileage selection: {user_search_data[user_id]}")

    bot.edit_message_text(
        f"Марка: {user_data.get('manufacturer_eng', '')} ({user_data.get('manufacturer', '')})\n"
        f"Модель: {user_data.get('model_eng', '')} ({user_data.get('model', '')})\n"
        f"Поколение: {user_data.get('generation', '')} ({user_data.get('generation_kr', '')})\n"
        f"Комплектация: {user_data.get('trim_eng', '')} ({user_data.get('trim', '')})\n"
        f"Год выпуска: {year}\n"
        f"Пробег: от {mileage_from} до {mileage_to} км\n"
        f"Теперь выбери цвет автомобиля:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
    )


def build_encar_url(
    manufacturer, model_group, model, trim, year, mileage_from, mileage_to, color
):
    if not all(
        [manufacturer.strip(), model_group.strip(), model.strip(), trim.strip()]
    ):
        print("❌ Не переданы необходимые параметры для построения URL")
        return ""

    # Строим основной фильтр без цвета и пробега
    core_query = (
        f"(And.Hidden.N._.SellType.일반._."
        f"(C.CarType.A._."
        f"(C.Manufacturer.{manufacturer}._."
        f"(C.ModelGroup.{model_group}._."
        f"(C.Model.{model_group} ({model})._."
        f"(And.BadgeGroup.{trim}._.YearGroup.{year}.))))))"
    )

    # Добавляем фильтры цвета и пробега снаружи
    mileage_part = (
        f"Mileage.range({mileage_from}..{mileage_to})"
        if mileage_from > 0
        else f"Mileage.range(..{mileage_to})"
    )
    extended_query = f"{core_query}_.Color.{color}._.{mileage_part}."

    encoded_query = urllib.parse.quote(extended_query, safe="()_.%")
    url = f"https://api-encar.habsidev.com/api/catalog?count=true&q={encoded_query}&sr=%7CModifiedDate%7C0%7C1"

    print(f"📡 Сформирован URL: {url}")
    return url


@bot.callback_query_handler(func=lambda call: call.data.startswith("color_"))
def handle_color_selection(call):
    parts = call.data.split("_", 2)
    source = parts[1]
    selected_color_kr = parts[2]

    user_id = call.from_user.id
    user_data = user_search_data.get(user_id, {})

    # Update the user data with color selection
    if source == "encar":
        user_data["color"] = selected_color_kr
        color_display = COLOR_TRANSLATIONS.get(selected_color_kr, selected_color_kr)

        # Get all necessary parameters for URL building
        manufacturer = user_data.get("manufacturer", "").strip()
        model_group = user_data.get("model_group", "").strip()
        generation = user_data.get("generation_kr", "").strip()
        if "(" in generation and ")" in generation:
            generation = generation.replace(")", "_)")
        trim = user_data.get("trim", "").strip()
        year = user_data.get("year", "")
        mileage_from = user_data.get("mileage_from", 0)
        mileage_to = user_data.get("mileage_to", 200000)

        # Start car checking in a background thread
        thread = threading.Thread(
            target=check_for_new_cars,
            args=(
                call.message.chat.id,
                manufacturer,
                model_group,
                generation,
                trim,
                year,
                mileage_from,
                mileage_to,
                selected_color_kr,
            ),
            daemon=True,
        )
        thread.start()
        print(f"✅ Started car checking thread for user {user_id}")

    else:  # kbchachacha
        user_data["color_code"] = KBCHACHACHA_COLORS.get(selected_color_kr, {}).get(
            "code", "all"
        )
        color_display = KBCHACHACHA_COLORS.get(selected_color_kr, {}).get(
            "ru", selected_color_kr
        )

    user_search_data[user_id] = user_data

    # Save the request to user_requests
    if str(user_id) not in user_requests:
        user_requests[str(user_id)] = []

    # Create a new request object
    new_request = {
        "manufacturer": f"{user_data.get('manufacturer_eng', '')} ({user_data.get('manufacturer', '')})",
        "model_group": f"{user_data.get('model_group_eng', '')} ({user_data.get('model_group', '')})",
        "model": f"{user_data.get('model_eng', '')} ({user_data.get('model', '')})",
        "generation": f"{user_data.get('generation', '')} ({user_data.get('generation_kr', '')})",
        "trim": f"{user_data.get('trim_eng', '')} ({user_data.get('trim', '')})",
        "year": user_data.get("year"),
        "mileage_from": user_data.get("mileage_from"),
        "mileage_to": user_data.get("mileage_to"),
        "color": color_display,
        "source": source,
    }

    # Add the request to the list
    user_requests[str(user_id)].append(new_request)
    save_requests(user_requests)

    # Create markup for returning to main menu
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="start")
    )

    # Send confirmation message
    bot.edit_message_text(
        f"✅ Запрос сохранён!\n\n"
        f"Марка: {user_data.get('manufacturer_eng', '')} ({user_data.get('manufacturer', '')})\n"
        f"Модель: {user_data.get('model_eng', '')} ({user_data.get('model', '')})\n"
        f"Поколение: {user_data.get('generation', '')} ({user_data.get('generation_kr', '')})\n"
        f"Комплектация: {user_data.get('trim_eng', '')} ({user_data.get('trim', '')})\n"
        f"Год выпуска: {user_data.get('year')}\n"
        f"Пробег: от {user_data.get('mileage_from')} до {user_data.get('mileage_to')} км\n"
        f"Цвет: {color_display}\n\n"
        f"Мы уведомим вас, когда найдём подходящие автомобили.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
    )


def check_for_new_cars(
    chat_id,
    manufacturer,
    model_group,
    model,
    trim,
    year_from,
    mileage_from,
    mileage_to,
    color,
):
    url = build_encar_url(
        manufacturer,
        model_group,
        model,
        trim,
        year_from,
        mileage_from,
        mileage_to,
        color,
    )

    print(url)

    while True:
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})

            if response.status_code != 200:
                print(f"❌ API вернул статус {response.status_code}: {response.text}")
                time.sleep(300)
                continue

            try:
                data = response.json()
            except Exception as json_err:
                print(f"❌ Ошибка парсинга JSON: {json_err}")
                print(f"Ответ: {response.text}")
                time.sleep(300)
                continue

            cars = data.get("SearchResults", [])
            new_cars = [car for car in cars if car["Id"] not in checked_ids]

            for car in new_cars:
                checked_ids.add(car["Id"])
                details_url = f"https://api.encar.com/v1/readside/vehicle/{car['Id']}"
                details_response = requests.get(
                    details_url, headers={"User-Agent": "Mozilla/5.0"}
                )

                if details_response.status_code == 200:
                    details_data = details_response.json()
                    specs = details_data.get("spec", {})
                    displacement = specs.get("displacement", "Не указано")
                    extra_text = f"\nОбъём двигателя: {displacement}cc\n\n👉 <a href='https://fem.encar.com/cars/detail/{car['Id']}'>Ссылка на автомобиль</a>"
                else:
                    extra_text = "\nℹ️ Не удалось получить подробности о машине."

                name = f'{car.get("Manufacturer", "")} {car.get("Model", "")} {car.get("Badge", "")}'
                price = car.get("Price", 0)
                mileage = car.get("Mileage", 0)
                year = car.get("FormYear", "")

                def format_number(n):
                    return f"{int(n):,}".replace(",", " ")

                formatted_mileage = format_number(mileage)
                formatted_price = format_number(price * 10000)

                text = (
                    f"✅ Новое поступление по вашему запросу!\n\n<b>{name}</b> {year} г.\nПробег: {formatted_mileage} км\nЦена: ₩{formatted_price}"
                    + extra_text
                )
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton(
                        "➕ Добавить новый автомобиль в поиск",
                        callback_data="search_car",
                    )
                )
                markup.add(
                    types.InlineKeyboardButton(
                        "🏠 Вернуться в главное меню",
                        callback_data="start",
                    )
                )
                bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

            time.sleep(300)
        except Exception as e:
            print(f"🔧 Общая ошибка при проверке новых авто: {e}")
            time.sleep(300)


def get_kbchachacha_manufacturers():
    url = (
        "https://www.kbchachacha.com/public/search/carMaker.json?page=1&sort=-orderDate"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Combine both domestic and imported manufacturers
            manufacturers = []
            if "국산" in data["result"]:  # Domestic manufacturers
                manufacturers.extend(data["result"]["국산"])
            if "수입" in data["result"]:  # Imported manufacturers
                manufacturers.extend(data["result"]["수입"])

            # Sort by title
            manufacturers.sort(key=lambda x: x.get("makerName", ""))
            return manufacturers
        else:
            print(f"❌ Ошибка при получении производителей: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Ошибка при запросе производителей: {e}")
        return []


def get_kbchachacha_models(maker_code):
    url = f"https://www.kbchachacha.com/public/search/carClass.json?makerCode={maker_code}&page=1&sort=-orderDate"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            models = data.get("result", {}).get("code", [])

            # Sort models by number of cars available (using the sale data)
            sale_data = data.get("result", {}).get("sale", {})
            for model in models:
                class_code = model.get("classCode")
                model["count"] = sale_data.get(class_code, 0)

            models.sort(key=lambda x: x.get("count", 0), reverse=True)
            return models
        else:
            print(f"❌ Ошибка при получении моделей: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Ошибка при запросе моделей: {e}")
        return []


def get_kbchachacha_generations(maker_code, class_code):
    url = f"https://www.kbchachacha.com/public/search/carName.json?makerCode={maker_code}&page=1&sort=-orderDate&classCode={class_code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            generations = data.get("result", {}).get("code", [])

            # Get sale data and convert years
            sale_data = data.get("result", {}).get("sale", {})
            for gen in generations:
                car_code = gen.get("carCode")
                gen["count"] = sale_data.get(car_code, 0)

                # Convert Korean year format to numeric
                if gen.get("toYear") == "현재":
                    gen["toYear"] = str(datetime.now().year)

            # Sort generations by fromYear
            generations.sort(key=lambda x: int(x.get("fromYear", 0)))
            return reversed(generations)
        else:
            print(f"❌ Ошибка при получении поколений: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Ошибка при запросе поколений: {e}")
        return []


def get_kbchachacha_models_by_generation(maker_code, class_code, car_code):
    url = f"https://www.kbchachacha.com/public/search/carModel.json?makerCode={maker_code}&page=1&sort=-orderDate&classCode={class_code}&carCode={car_code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            models = data.get("result", {}).get("codeModel", [])

            # Get sale data for sorting by availability
            sale_data = data.get("result", {}).get("sale", {})
            for model in models:
                model_code = model.get("modelCode")
                model_sales = sale_data.get(model_code, {})
                model["count"] = (
                    model_sales.get("modelCount", 0)
                    if isinstance(model_sales, dict)
                    else 0
                )

                # Add grade information
                grades = [
                    grade
                    for grade in data.get("result", {}).get("codeGrade", [])
                    if grade.get("modelCode") == model_code
                ]
                model["grades"] = grades

            # Sort models by number of available cars
            models.sort(key=lambda x: x.get("count", 0), reverse=True)
            return models
        else:
            print(
                f"❌ Ошибка при получении моделей по поколению: {response.status_code}"
            )
            return []
    except Exception as e:
        print(f"❌ Ошибка при запросе моделей по поколению: {e}")
        return []


def build_kbchachacha_url(
    maker_code, class_code, car_code, model_code, year, color_code
):
    url = (
        f"https://api.kbchachacha.com/api/cars?"
        f"makerCode={maker_code}&"
        f"classCode={class_code}&"
        f"carCode={car_code}&"
        f"modelCode={model_code}&"
        f"modelGradeCode={model_code}|002&"  # Default grade code
        f"fromYear={year}&"
        f"toYear={year}&"
        f"colorCode={color_code}"
    )
    return url


def get_kcar_manufacturers():
    url = "https://api.kcar.com/bc/search/group/mnuftr"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"wr_eq_sell_dcd": "ALL", "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd"}

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            manufacturers = data.get("data", [])
            # Сортируем по названию
            manufacturers.sort(key=lambda x: x.get("mnuftrEnm", ""))
            return manufacturers
        else:
            print(
                f"❌ Ошибка при получении производителей KCar: {response.status_code}"
            )
            return []
    except Exception as e:
        print(f"❌ Ошибка при запросе производителей KCar: {e}")
        return []


# Заменяем функцию получения моделей KCar
def get_kcar_models(mnuftr_cd):
    url = "https://api.kcar.com/bc/search/group/modelGrp"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "wr_eq_sell_dcd": "ALL",
        "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd",
        "wr_eq_mnuftr_cd": mnuftr_cd,
    }

    try:
        print(
            f"DEBUG: Отправка запроса на API KCar для моделей производителя {mnuftr_cd}"
        )
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])
            # Сортируем по количеству доступных автомобилей (в порядке убывания)
            models.sort(key=lambda x: x.get("count", 0), reverse=True)
            print(f"DEBUG: Получено {len(models)} моделей KCar")
            return models
        else:
            print(f"❌ Ошибка при получении моделей KCar: {response.status_code}")
            try:
                print(f"❌ Ответ API: {response.json()}")
            except:
                print(f"❌ Ответ API: {response.text}")
            return []
    except Exception as e:
        print(f"❌ Ошибка при запросе моделей KCar: {e}")
        return []


# Обновляем функцию для получения поколений KCar
def get_kcar_generations(mnuftr_cd, model_grp_cd):
    url = "https://api.kcar.com/bc/search/group/model"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "wr_eq_sell_dcd": "ALL",
        "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd",
        "wr_eq_mnuftr_cd": mnuftr_cd,
        "wr_eq_model_grp_cd": model_grp_cd,
    }

    try:
        print(
            f"DEBUG: Отправка запроса на API KCar для поколений модели {model_grp_cd}"
        )
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            generations = data.get("data", [])
            # Сортируем по количеству доступных автомобилей
            generations.sort(key=lambda x: x.get("count", 0), reverse=True)
            print(f"DEBUG: Получено {len(generations)} поколений KCar")
            return generations
        else:
            print(f"❌ Ошибка при получении поколений KCar: {response.status_code}")
            try:
                print(f"❌ Ответ API: {response.json()}")
            except:
                print(f"❌ Ответ API: {response.text}")
            return []
    except Exception as e:
        print(f"❌ Ошибка при запросе поколений KCar: {e}")
        return []


# Функция для получения конфигураций для выбранного поколения KCar
def get_kcar_configurations(mnuftr_path, model_grp_cd, model_cd):
    url = "https://api.kcar.com/bc/search/group/grd"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "wr_eq_sell_dcd": "ALL",
        "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd",
        "wr_eq_mnuftr_path": mnuftr_path,
        "wr_eq_model_grp_cd": model_grp_cd,
        "wr_eq_model_cd": model_cd,
    }

    try:
        print(f"DEBUG: Отправка запроса на API KCar для конфигураций модели {model_cd}")
        print(f"DEBUG: URL: {url}")
        print(f"DEBUG: Payload: {payload}")

        response = requests.post(url, headers=headers, json=payload)
        print(f"DEBUG: Статус ответа: {response.status_code}")

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"DEBUG: Успешно получен ответ JSON")
                configurations = data.get("data", [])
                # Сортируем по количеству доступных автомобилей
                configurations.sort(key=lambda x: x.get("count", 0), reverse=True)
                print(f"DEBUG: Получено {len(configurations)} конфигураций KCar")

                if len(configurations) > 0:
                    print(f"DEBUG: Первая конфигурация: {configurations[0]}")

                return configurations
            except Exception as json_err:
                print(f"DEBUG: Ошибка парсинга JSON: {json_err}")
                print(f"DEBUG: Текст ответа: {response.text[:500]}")
                return []
        else:
            print(f"❌ Ошибка при получении конфигураций KCar: {response.status_code}")
            try:
                print(f"❌ Ответ API: {response.json()}")
            except:
                print(f"❌ Ответ API: {response.text[:500]}")
            return []
    except Exception as e:
        print(f"❌ Ошибка при запросе конфигураций KCar: {e}")
        return []


# Добавляем обработчик выбора конфигурации для KCar
@bot.callback_query_handler(func=lambda call: call.data.startswith("config_"))
def handle_config_selection(call):
    parts = call.data.split("_")
    source = parts[1]

    if source == "kcar":
        # Для KCar формат: config_kcar_mnuftr_path_model_grp_cd_model_cd_grd_cd_year
        if len(parts) < 7:
            bot.answer_callback_query(call.id, "Неверный формат данных.")
            return

        mnuftr_path = parts[2]
        model_grp_cd = parts[3]
        model_cd = parts[4]
        grd_cd = parts[5]
        selected_year = int(parts[6])

        user_id = call.from_user.id
        if user_id not in user_search_data:
            user_search_data[user_id] = {}

        # Получаем список конфигураций, чтобы найти выбранную
        configurations = get_kcar_configurations(mnuftr_path, model_grp_cd, model_cd)
        selected_config = next(
            (c for c in configurations if c.get("grdCd") == grd_cd), None
        )

        if not selected_config:
            bot.answer_callback_query(call.id, "Конфигурация не найдена.")
            return

        config_name = selected_config.get("grdNm", "")
        translated_config = translate_phrase(config_name)

        # Сохраняем данные о выбранной конфигурации
        user_search_data[user_id].update(
            {
                "grd_cd": grd_cd,
                "config": translated_config,
                "config_kr": config_name,
            }
        )

        print(f"✅ DEBUG user_data after config selection: {user_search_data[user_id]}")

        # Создаем клавиатуру для выбора пробега
        mileage_markup = types.InlineKeyboardMarkup(row_width=4)
        for value in range(0, 200001, 10000):
            mileage_markup.add(
                types.InlineKeyboardButton(
                    f"{value} км",
                    callback_data=f"mileage_from_kcar_{selected_year}_{value}",
                )
            )

        # Получаем информацию о модели из текста сообщения
        message_text = call.message.text
        brand_line = next(
            (line for line in message_text.split("\n") if "Марка:" in line), ""
        )
        model_line = next(
            (line for line in message_text.split("\n") if "Модель:" in line), ""
        )
        generation_line = next(
            (line for line in message_text.split("\n") if "Поколение:" in line), ""
        )

        brand = brand_line.replace("Марка:", "").strip()
        model = model_line.replace("Модель:", "").strip()
        generation = (
            generation_line.replace("Поколение:", "").strip() if generation_line else ""
        )

        bot.edit_message_text(
            f"Марка: {brand}\nМодель: {model}\nПоколение: {generation}\n"
            f"Год: {selected_year}\nКонфигурация: {translated_config}\n"
            f"Выберите минимальный пробег:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=mileage_markup,
        )


if __name__ == "__main__":
    print("Starting Telegram bot...")
    print("Bot username: @{}".format(bot.get_me().username))
    print("Press Ctrl+C to stop the bot")
    try:
        bot.infinity_polling(none_stop=True)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError occurred: {e}")
        sys.exit(1)

        bot.infinity_polling(none_stop=True)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError occurred: {e}")
        sys.exit(1)
