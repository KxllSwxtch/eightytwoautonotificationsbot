import json
import time
import telebot
import os
import requests
import urllib.parse
from telebot import types
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
from dotenv import load_dotenv
from datetime import datetime
from translations import translations
from bs4 import BeautifulSoup

# Путь до файла
REQUESTS_FILE = "requests.json"
ACCESS_FILE = "access.json"

# Глобальный словарь всех запросов пользователей
user_requests = {}

# Словарь переводов цветов для KbChaChaCha
KBCHACHA_COLOR_TRANSLATIONS = {
    "검정색": {"ru": "Чёрный", "code": "006001"},
    "흰색": {"ru": "Белый", "code": "006002"},
    "은색": {"ru": "Серебристый", "code": "006003"},
    "진주색": {"ru": "Жемчужный", "code": "006004"},
    "회색": {"ru": "Серый", "code": "006005"},
    "빨간색": {"ru": "Красный", "code": "006006"},
    "파란색": {"ru": "Синий", "code": "006007"},
    "주황색": {"ru": "Оранжевый", "code": "006008"},
    "갈색": {"ru": "Коричневый", "code": "006009"},
    "초록색": {"ru": "Зелёный", "code": "006010jn"},
    "노란색": {"ru": "Жёлтый", "code": "006011"},
    "보라색": {"ru": "Фиолетовый", "code": "006012"},
    "Любой": {"ru": "Любой", "code": ""},
}

# Словарь переводов цветов для KCar
KCAR_COLOR_TRANSLATIONS = {
    "흰색": "Белый",
    "진주색": "Жемчужный",
    "검정색": "Чёрный",
    "검정투톤": "Чёрный (двухцветный)",
    "쥐색": "Тёмно-серый",
    "은색": "Серебристый",
    "은회색": "Серо-серебристый",
    "은색투톤": "Серебристый (двухцветный)",
    "흰색투톤": "Белый (двухцветный)",
    "진주투톤": "Жемчужный (двухцветный)",
    "은하색": "Галактический серый",
    "명은색": "Светло-серебристый",
    "빨간색": "Красный",
    "주황색": "Оранжевый",
    "자주색": "Бордовый",
    "보라색": "Фиолетовый",
    "분홍색": "Розовый",
    "노란색": "Жёлтый",
    "갈대색": "Коричневато-серый",
    "연금색": "Светло-золотистый",
    "갈색": "Коричневый",
    "갈색투톤": "Коричневый (двухцветный)",
    "금색": "Золотистый",
    "금색투톤": "Золотистый (двухцветный)",
    "청색": "Синий",
    "하늘색": "Голубой",
    "담녹색": "Тёмно-зелёный",
    "녹색": "Зелёный",
    "연두색": "Салатовый",
    "청옥색": "Бирюзовый",
    "기타": "Другой",
    "Любой": "Любой",
}


def load_access():
    if os.path.exists(ACCESS_FILE):
        try:
            with open(ACCESS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"⚠️ Не удалось загрузить access.json: {e}")
            return set()
    return set()


def save_access():
    try:
        with open(ACCESS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(ACCESS), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Ошибка при сохранении access.json: {e}")


MANAGER = 56022406

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
    url = "https://encar-proxy-main.onrender.com/api/nav?count=true&q=(And.Hidden.N._.SellType.%EC%9D%BC%EB%B0%98._.CarType.A.)&inav=%7CMetadata%7CSort"
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
    url = f"https://encar-proxy-main.onrender.com/api/nav?count=true&q=(And.Hidden.N._.SellType.%EC%9D%BC%EB%B0%98._.(C.CarType.A._.Manufacturer.{manufacturer}.))&inav=%7CMetadata%7CSort"
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
        if selected_manufacturer:
            return (
                selected_manufacturer.get("Refinements", {})
                .get("Nodes", [])[0]
                .get("Facets", [])
            )
        return []
    except Exception as e:
        print(f"Ошибка при получении моделей для {manufacturer}:", e)
        return []


def get_generations_by_model(manufacturer, model_group):
    url = f"https://encar-proxy-main.onrender.com/api/nav?count=true&q=(And.Hidden.N._.SellType.%EC%9D%BC%EB%B0%98._.(C.CarType.A._.(C.Manufacturer.{manufacturer}._.ModelGroup.{model_group}.)))&inav=%7CMetadata%7CSort"
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
    url = f"https://encar-proxy-main.onrender.com/api/nav?count=true&q=(And.Hidden.N._.(C.CarType.A._.(C.Manufacturer.{manufacturer}._.(C.ModelGroup.{model_group}._.Model.{model}.))))&inav=%7CMetadata%7CSort"
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
            "📢 Телеграм-канал", url="https://t.me/autofromkorea82"
        ),
    )
    # markup.add(
    #     types.InlineKeyboardButton("🌐 Сайт компании", url="https://kga-korea.com/")
    # )

    welcome_text = (
        "👋 Добро пожаловать бот от *82 Auto*!\n\n"
        "С помощью этого бота вы можете:\n"
        "• 🔍 Найти интересующий вас автомобиль\n"
        "• 🧮 Получить расчёт стоимости авто по ссылке\n"
        "• 📬 Подписаться на соцсети и быть в курсе\n\n"
        "*Выберите действие ниже:*"
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
    # Создаем клавиатуру с выбором площадок
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("Encar", callback_data="platform_encar"),
        types.InlineKeyboardButton("KbChaChaCha", callback_data="platform_kbchachacha"),
        types.InlineKeyboardButton("KCar", callback_data="platform_kcar"),
    )

    bot.send_message(
        call.message.chat.id, "Выберите площадку для поиска:", reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("platform_"))
def handle_platform_selection(call):
    platform = call.data.split("_")[1]

    if platform == "encar":
        handle_encar_search(call)
    elif platform == "kbchachacha":
        handle_kbchachacha_search(call)
    elif platform == "kcar":
        handle_kcar_search(call)


def handle_encar_search(call):
    manufacturers = get_manufacturers()
    if not manufacturers:
        bot.answer_callback_query(call.id, "Не удалось загрузить марки.")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for item in manufacturers:  # Удалено ограничение [:10]
        kr_name = item.get("DisplayValue", "Без названия")
        eng_name = item.get("Metadata", {}).get("EngName", [""])[0]
        callback_data = f"brand_{eng_name}_{kr_name}"
        display_text = f"{eng_name}"
        markup.add(
            types.InlineKeyboardButton(display_text, callback_data=callback_data)
        )

    bot.send_message(
        call.message.chat.id, "Выбери марку автомобиля:", reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("brand_"))
def handle_brand_selection(call):
    _, eng_name, kr_name = call.data.split("_", 2)
    models = get_models_by_brand(kr_name)
    if not models:
        bot.answer_callback_query(call.id, "Не удалось загрузить модели.")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for item in models:
        model_kr = item.get("DisplayValue", "Без названия")
        model_eng = item.get("Metadata", {}).get("EngName", [""])[0]
        callback_data = f"model_{model_eng}_{model_kr}"
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


@bot.callback_query_handler(func=lambda call: call.data.startswith("model_"))
def handle_model_selection(call):
    _, model_eng, model_kr = call.data.split("_", 2)
    message_text = call.message.text
    # Получаем марку из предыдущего текста сообщения
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

    generations = get_generations_by_model(brand_kr, model_kr)
    if not generations:
        bot.answer_callback_query(call.id, "Не удалось загрузить поколения.")
        return

    # Отладочный вывод данных о поколениях
    print(f"⚙️ DEBUG [handle_model_selection] - Полученные поколения:")
    for idx, item in enumerate(generations[:3]):  # Ограничимся первыми 3 для краткости
        gen_kr = item.get("DisplayValue", "Без названия")
        gen_eng = item.get("Metadata", {}).get("EngName", [""])[0]
        print(f"  Поколение {idx+1}: gen_kr='{gen_kr}', gen_eng='{gen_eng}'")

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

        callback_data = f"generation_{gen_eng}_{gen_kr}"
        translated_gen_kr = translate_phrase(gen_kr)
        translated_gen_eng = translate_phrase(gen_eng)

        # Отладочная информация о переводе
        print(
            f"⚙️ DEBUG [handle_model_selection] - Перевод: '{gen_kr}' -> '{translated_gen_kr}'"
        )

        # Используем английское название с периодом, без корейского текста
        display_text = f"{gen_eng} {translated_gen_kr} {period}".strip()
        markup.add(
            types.InlineKeyboardButton(display_text, callback_data=callback_data)
        )

    bot.edit_message_text(
        f"Марка: {brand_eng.strip()} ({brand_kr})\nМодель: {model_eng} ({model_kr})\nТеперь выбери поколение:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("generation_"))
def handle_generation_selection(call):
    _, generation_eng, generation_kr = call.data.split("_", 2)
    message_text = call.message.text

    brand_line = next(
        (line for line in message_text.split("\n") if "Марка:" in line), ""
    )
    model_line = next(
        (line for line in message_text.split("\n") if "Модель:" in line), ""
    )

    brand_eng, brand_kr = brand_line.replace("Марка:", "").strip().split(" (")
    brand_kr = brand_kr.rstrip(")")
    model_part = model_line.replace("Модель:", "").strip()
    if " (" in model_part:
        model_eng, model_kr = model_part.split(" (")
        model_kr = model_kr.rstrip(")")
    else:
        model_eng = model_part
        model_kr = ""

    # Получаем поколения для определения дат
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

    # Получаем даты начала и окончания поколения
    start_raw = str(
        selected_generation.get("Metadata", {}).get("ModelStartDate", [""])[0]
    )
    end_raw = str(
        selected_generation.get("Metadata", {}).get("ModelEndDate", [""])[0] or ""
    )

    current_year = datetime.now().year

    # Определяем начальный и конечный год
    raw_start_year = int(start_raw[:4]) if len(start_raw) == 6 else current_year - 10

    # Используем точный год начала поколения без смещения
    start_year = raw_start_year

    if end_raw and end_raw.isdigit():
        end_year = int(end_raw[:4])
    else:
        end_year = current_year

    # --- DEBUGGING --- Выводим полученные даты и рассчитанные годы
    print(f"⚙️ DEBUG [handle_generation_selection] - Raw start_raw: '{start_raw}'")
    print(f"⚙️ DEBUG [handle_generation_selection] - Raw end_raw: '{end_raw}'")
    print(
        f"⚙️ DEBUG [handle_generation_selection] - Original API start_year: {raw_start_year}"
    )
    print(f"⚙️ DEBUG [handle_generation_selection] - Used year_from: {start_year}")
    print(f"⚙️ DEBUG [handle_generation_selection] - Calculated year_to: {end_year}")
    # --- END DEBUGGING ---

    # Получаем комплектации
    trims = get_trims_by_generation(brand_kr, model_kr, generation_kr)
    if not trims:
        bot.answer_callback_query(call.id, "Не удалось загрузить комплектации.")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for item in trims:
        trim_kr = item.get("DisplayValue", "")
        trim_eng = item.get("Metadata", {}).get("EngName", [""])[0]
        callback_data = f"trim_{trim_eng}_{trim_kr}"

        # Используем translate_phrase для перевода названия комплектации
        translated_trim_kr = translate_phrase(trim_kr)
        display_text = translated_trim_kr

        markup.add(
            types.InlineKeyboardButton(display_text, callback_data=callback_data)
        )

    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    # Сохраняем данные о модели и годах
    user_search_data[user_id].update(
        {
            "manufacturer": brand_kr.strip(),
            "model_group": model_kr.strip(),
            "model": generation_kr.strip(),
            "year_from": start_year,
            "year_to": end_year,
        }
    )

    # Используем translate_phrase для перевода названий поколений
    translated_generation_eng = translate_phrase(generation_eng)
    translated_generation_kr = translate_phrase(generation_kr)

    # Отображаем переведенные названия поколений в тексте сообщения
    bot.edit_message_text(
        f"Марка: {brand_eng.strip()} ({brand_kr})\nМодель: {model_eng} ({model_kr})\nПоколение: {translated_generation_eng} ({translated_generation_kr})\nВыберите комплектацию:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("trim_"))
def handle_trim_selection(call):
    parts = call.data.split("_", 2)
    trim_eng = parts[1]
    trim_kr = parts[2] if len(parts) > 2 else parts[1]

    print(f"✅ DEBUG trim selection - raw data:")
    print(f"trim_eng: {trim_eng}")
    print(f"trim_kr: {trim_kr}")

    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    # Получаем годы начала и конца поколения из сохраненных данных
    start_year = user_search_data[user_id].get("year_from", datetime.now().year - 10)
    end_year = user_search_data[user_id].get("year_to", datetime.now().year)

    # --- DEBUGGING --- Добавим вывод для проверки значений годов
    print(
        f"⚙️ DEBUG [handle_trim_selection] - User {user_id} - Retrieved year_from: {start_year}"
    )
    print(
        f"⚙️ DEBUG [handle_trim_selection] - User {user_id} - Retrieved year_to: {end_year}"
    )
    # --- END DEBUGGING ---

    # Сохраняем trim
    user_search_data[user_id]["trim"] = trim_kr.strip()

    print(f"✅ DEBUG user_search_data after trim selection:")
    print(json.dumps(user_search_data[user_id], indent=2, ensure_ascii=False))

    year_markup = types.InlineKeyboardMarkup(row_width=4)
    current_year = datetime.now().year

    # Формируем диапазон лет от начала производства поколения до конца или текущего года
    for y in range(start_year, min(end_year, current_year) + 1):
        year_markup.add(
            types.InlineKeyboardButton(str(y), callback_data=f"year_from_{y}")
        )

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

    brand_eng, brand_kr = brand_line.replace("Марка:", "").strip().split(" (")
    brand_kr = brand_kr.rstrip(")")
    model_part = model_line.replace("Модель:", "").strip()
    if " (" in model_part:
        model_eng, model_kr = model_part.split(" (")
        model_kr = model_kr.rstrip(")")
    else:
        model_eng = model_part
        model_kr = ""

    generation_part = generation_line.replace("Поколение:", "").strip()
    if "(" in generation_part and ")" in generation_part:
        parts = generation_part.rsplit("(", 1)
        generation_eng = parts[0].strip()
        generation_kr = parts[1].replace(")", "").strip()
    else:
        generation_eng = generation_part
        generation_kr = ""

    # Используем translate_phrase для перевода названий комплектаций
    translated_trim_eng = translate_phrase(trim_eng)
    translated_trim_kr = translate_phrase(trim_kr)

    bot.edit_message_text(
        f"Марка: {brand_eng.strip()} ({brand_kr})\nМодель: {model_eng} ({model_kr})\nПоколение: {generation_eng} ({generation_kr})\nКомплектация: {translated_trim_eng} ({translated_trim_kr})\nВыберите начальный год выпуска:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=year_markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("year_from_"))
def handle_year_from_selection(call):
    year_from = int(call.data.split("_")[2])
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    # Сохраняем год начала, сохраняя остальные данные
    user_search_data[user_id].update({"year_from": year_from})

    print(f"✅ DEBUG user_search_data after year_from selection:")
    print(json.dumps(user_search_data[user_id], indent=2, ensure_ascii=False))

    # Получаем конечный год периода выпуска поколения из сохраненных данных
    end_year = user_search_data[user_id].get("year_to", datetime.now().year)
    current_year = datetime.now().year

    # Формируем диапазон лет от выбранного года до конца производства поколения или текущего года
    year_markup = types.InlineKeyboardMarkup(row_width=4)
    for y in range(year_from, min(end_year, current_year) + 1):
        year_markup.add(
            types.InlineKeyboardButton(str(y), callback_data=f"year_to_{year_from}_{y}")
        )

    bot.edit_message_text(
        f"Начальный год: {year_from}\nТеперь выберите конечный год:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=year_markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("year_to_"))
def handle_year_to_selection(call):
    year_from = int(call.data.split("_")[2])
    year_to = int(call.data.split("_")[3])
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    # Сохраняем год окончания, сохраняя остальные данные
    user_search_data[user_id].update({"year_to": year_to})

    print(f"✅ DEBUG user_search_data after year_to selection:")
    print(json.dumps(user_search_data[user_id], indent=2, ensure_ascii=False))

    mileage_markup = types.InlineKeyboardMarkup(row_width=4)
    for value in range(0, 200001, 10000):
        mileage_markup.add(
            types.InlineKeyboardButton(
                f"{value} км", callback_data=f"mileage_from_{value}"
            )
        )

    bot.edit_message_text(
        f"Диапазон годов: {year_from}-{year_to}\nТеперь выберите минимальный пробег:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=mileage_markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("mileage_from_"))
def handle_mileage_from(call):
    mileage_from = int(call.data.split("_")[2])

    print(f"✅ DEBUG user_search_data before mileage_from selection:")
    print(
        json.dumps(
            user_search_data.get(call.from_user.id, {}), indent=2, ensure_ascii=False
        )
    )

    mileage_markup = types.InlineKeyboardMarkup(row_width=4)
    for value in range(mileage_from + 10000, 200001, 10000):
        mileage_markup.add(
            types.InlineKeyboardButton(
                f"{value} км", callback_data=f"mileage_to_{mileage_from}_{value}"
            )
        )

    bot.send_message(
        call.message.chat.id,
        f"Минимальный пробег: {mileage_from} км\nТеперь выберите максимальный пробег:",
        reply_markup=mileage_markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("mileage_to_"))
def handle_mileage_to(call):
    mileage_from = int(call.data.split("_")[2])
    mileage_to = int(call.data.split("_")[3])

    print(f"✅ DEBUG user_search_data before mileage_to selection:")
    print(
        json.dumps(
            user_search_data.get(call.from_user.id, {}), indent=2, ensure_ascii=False
        )
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    for kr, ru in COLOR_TRANSLATIONS.items():
        markup.add(types.InlineKeyboardButton(ru, callback_data=f"color_{kr}"))

    bot.send_message(
        call.message.chat.id,
        f"Пробег: от {mileage_from} км до {mileage_to} км\nТеперь выберите цвет автомобиля:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("color_"))
def handle_color_selection(call):
    selected_color_kr = call.data.split("_", 1)[1]
    message_text = call.message.text
    selected_color_ru = (
        "Любой"
        if selected_color_kr == "all"
        else COLOR_TRANSLATIONS.get(selected_color_kr, "Неизвестно")
    )

    user_id = call.from_user.id
    user_data = user_search_data.get(user_id, {})
    print(f"✅ DEBUG user_data before color selection: {user_data}")

    # Проверяем наличие всех необходимых данных
    required_fields = [
        "manufacturer",
        "model_group",
        "model",
        "trim",
        "year_from",
        "year_to",
    ]
    missing_fields = [field for field in required_fields if field not in user_data]

    if missing_fields:
        print(f"❌ Отсутствуют необходимые поля: {missing_fields}")
        bot.send_message(
            call.message.chat.id,
            "⚠️ Произошла ошибка: не все данные были сохранены. Пожалуйста, начните поиск заново.",
        )
        return

    manufacturer = user_data["manufacturer"]
    model_group = user_data["model_group"]
    model = user_data["model"]
    trim = user_data["trim"]
    year_from = user_data["year_from"]
    year_to = user_data["year_to"]

    mileage_line = next(
        (line for line in message_text.split("\n") if "Пробег:" in line), ""
    )
    mileage_from = int(mileage_line.split("от")[1].split("км")[0].strip())
    mileage_to = int(mileage_line.split("до")[1].split("км")[0].strip())

    print("⚙️ Данные для поиска:")
    print(f"manufacturer: {manufacturer}")
    print(f"model_group: {model_group}")
    print(f"model: {model}")
    print(f"trim: {trim}")
    print(f"year_from: {year_from}")
    print(f"year_to: {year_to}")
    print(f"color: {selected_color_kr}")
    print(f"mileage_from: {mileage_from}")
    print(f"mileage_to: {mileage_to}")

    bot.send_message(
        call.message.chat.id,
        "🔍 Начинаем поиск автомобилей по заданным параметрам. Это может занять некоторое время...",
    )
    # Кнопки после завершения добавления авто
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "➕ Добавить новый автомобиль в поиск", callback_data="search_car"
        )
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="start")
    )
    bot.send_message(
        call.message.chat.id,
        "Хотите добавить ещё один автомобиль в поиск или вернуться в главное меню?",
        reply_markup=markup,
    )

    if user_id not in user_requests:
        user_requests[user_id] = []

    user_requests[user_id].append(
        {
            "manufacturer": manufacturer,
            "model_group": model_group,
            "model": model,
            "trim": trim,
            "year_from": year_from,
            "year_to": year_to,
            "mileage_from": mileage_from,
            "mileage_to": mileage_to,
            "color": selected_color_kr,
        }
    )

    save_requests(user_requests)

    import threading

    threading.Thread(
        target=check_for_new_cars,
        args=(
            call.message.chat.id,
            manufacturer.strip(),
            model_group.strip(),
            model.strip(),
            trim.strip(),
            year_from,
            year_to,
            mileage_from,
            mileage_to,
            selected_color_kr.strip(),
        ),
        daemon=True,
    ).start()


@bot.message_handler(state=CarForm.brand)
def handle_brand(message):
    bot.send_message(message.chat.id, "Отлично! Теперь введи модель:")
    bot.set_state(message.from_user.id, CarForm.model, message.chat.id)


# Обработчик модели
@bot.message_handler(state=CarForm.model)
def handle_model(message):
    bot.send_message(message.chat.id, "Укажи поколение:")
    bot.set_state(message.from_user.id, CarForm.generation, message.chat.id)


checked_ids = set()


def build_encar_url(
    manufacturer,
    model_group,
    model,
    trim,
    year_from,
    year_to,
    mileage_from,
    mileage_to,
    color,
):
    if not all(
        [manufacturer.strip(), model_group.strip(), model.strip(), trim.strip()]
    ):
        print("❌ Не переданы необходимые параметры для построения URL")
        return ""

    # Convert years to format YYYYMM
    year_from_formatted = f"{year_from}00"
    year_to_formatted = f"{year_to}99"

    # Подготавливаем имя модели - добавляем '_' после кода модели
    if "(" in model and ")" in model:
        base_name, code_part = model.rsplit("(", 1)
        code = code_part.rstrip(")")
        # Убираем пробелы перед скобкой для соответствия формату API
        base_name = base_name.rstrip()
        model_formatted = f"{base_name}({code}_)"
    else:
        model_formatted = model

    # Используем urllib.parse.quote только для отдельных значений,
    # оставляя структурные элементы (скобки, точки) как есть
    manufacturer_encoded = urllib.parse.quote(manufacturer)
    model_group_encoded = urllib.parse.quote(model_group)
    model_formatted_encoded = urllib.parse.quote(model_formatted)
    trim_encoded = urllib.parse.quote(trim)
    color_encoded = urllib.parse.quote(color)
    sell_type_encoded = urllib.parse.quote("일반")

    # Формируем URL точно как в рабочем примере
    url = (
        f"https://encar-proxy-main.onrender.com/api/catalog?count=true&q="
        f"(And.Hidden.N._.SellType.{sell_type_encoded}._.Color.{color_encoded}._."
        f"(C.CarType.A._."
        f"(C.Manufacturer.{manufacturer_encoded}._."
        f"(C.ModelGroup.{model_group_encoded}._."
        f"(C.Model.{model_formatted_encoded}._.BadgeGroup.{trim_encoded}.))))_."
        f"Year.range({year_from_formatted}..{year_to_formatted})._."
        f"Mileage.range({mileage_from}..{mileage_to}).)"
        f"&sr=%7CModifiedDate%7C0%7C1"
    )

    print(f"📡 Сформирован URL: {url}")
    return url


def check_for_new_cars(
    chat_id,
    manufacturer,
    model_group,
    model,
    trim,
    year_from,
    year_to,
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
        year_to,
        mileage_from,
        mileage_to,
        color,
    )

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
                    return f"{int(n):,}".replace(",", " ")

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


# Добавленный код для команд userlist и remove_user
@bot.message_handler(commands=["userlist"])
def handle_userlist_command(message):
    if message.from_user.id not in [MANAGER, 604303416, 728438182]:
        bot.reply_to(message, "❌ У вас нет доступа к этой команде.")
        return

    if not ACCESS:
        bot.reply_to(message, "❌ В списке доступа пока нет пользователей.")
        return

    access_list = list(ACCESS)
    text = "📋 Список пользователей с доступом к боту:\n\n"
    for user_id in access_list:
        text += f"• <code>{user_id}</code>\n"

    text += "\nЧтобы удалить пользователя, отправьте команду:\n/remove_user [ID]"

    bot.send_message(message.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=["remove_user"])
def handle_remove_user(message):
    if message.from_user.id not in [MANAGER, 604303416, 728438182]:
        bot.reply_to(message, "❌ У вас нет доступа к этой команде.")
        return

    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "⚠️ Используйте формат: /remove_user [ID]")
            return

        user_id_to_remove = int(parts[1])
        if user_id_to_remove in ACCESS:
            ACCESS.remove(user_id_to_remove)
            save_access()
            bot.reply_to(
                message, f"✅ Пользователь {user_id_to_remove} удалён из доступа."
            )
        else:
            bot.reply_to(message, "⚠️ Этот пользователь не найден в списке доступа.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Ошибка: {e}")


# Функции для работы с KbChaChaCha
def get_kbchachacha_manufacturers():
    """Получение списка производителей с KbChaChaCha"""
    url = (
        "https://www.kbchachacha.com/public/search/carMaker.json?page=1&sort=-orderDate"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        # Получаем список как импортных, так и корейских производителей
        import_manufacturers = data.get("result", {}).get(
            "수입", []
        )  # 수입 = импортные
        korean_manufacturers = data.get("result", {}).get(
            "국산", []
        )  # 국산 = корейские

        # Объединяем списки
        all_manufacturers = korean_manufacturers + import_manufacturers

        # Сортируем по имени производителя
        all_manufacturers.sort(key=lambda x: x.get("makerName", ""))

        return all_manufacturers
    except Exception as e:
        print("Ошибка при получении марок из KbChaChaCha:", e)
        return []


def get_kbchachacha_models(maker_code):
    """Получение списка моделей по ID производителя с KbChaChaCha"""
    url = f"https://www.kbchachacha.com/public/search/carClass.json?makerCode={maker_code}&page=1&sort=-orderDate"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        models = data.get("result", {}).get("code", [])
        # Сортируем по имени модели
        models.sort(key=lambda x: x.get("className", ""))
        return models
    except Exception as e:
        print(f"Ошибка при получении моделей с KbChaChaCha для {maker_code}:", e)
        return []


def get_kbchachacha_generations(maker_code, class_code):
    """Получение списка поколений по коду марки и модели с KbChaChaCha"""
    url = f"https://www.kbchachacha.com/public/search/carName.json?makerCode={maker_code}&page=1&sort=-orderDate&classCode={class_code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        generations = data.get("result", {}).get("code", [])
        # Сортируем по порядку поколений
        generations.sort(key=lambda x: x.get("carOrder", 999))
        return generations
    except Exception as e:
        print(
            f"Ошибка при получении поколений с KbChaChaCha для {maker_code}/{class_code}:",
            e,
        )
        return []


def get_kbchachacha_trims(maker_code, class_code, car_code):
    """Получение списка конфигураций по коду марки, модели и поколения с KbChaChaCha"""
    url = f"https://www.kbchachacha.com/public/search/carModel.json?makerCode={maker_code}&page=1&sort=-orderDate&classCode={class_code}&carCode={car_code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        trims = data.get("result", {}).get("codeModel", [])
        # Сортируем по порядку конфигураций
        trims.sort(key=lambda x: x.get("modelOrder", 999))
        return trims
    except Exception as e:
        print(
            f"Ошибка при получении конфигураций с KbChaChaCha для {maker_code}/{class_code}/{car_code}:",
            e,
        )
        return []


def handle_kbchachacha_search(call):
    # Получаем список производителей
    manufacturers = get_kbchachacha_manufacturers()
    if not manufacturers:
        bot.answer_callback_query(call.id, "Не удалось загрузить марки из KbChaChaCha.")
        return

    # Создаем клавиатуру с марками
    markup = types.InlineKeyboardMarkup(row_width=2)
    for item in manufacturers:
        maker_name = item.get("makerName", "Без названия")
        maker_code = item.get("makerCode", "")

        # Добавляем перевод названия марки, если оно есть в словаре переводов
        translated_name = translations.get(maker_name, maker_name)

        # Используем только английский перевод для отображения
        display_name = translated_name

        # Используем специальный префикс для отличия от других площадок
        callback_data = f"kbcha_brand_{maker_code}_{maker_name}"
        markup.add(
            types.InlineKeyboardButton(display_name, callback_data=callback_data)
        )

    bot.send_message(
        call.message.chat.id,
        "Выберите марку автомобиля:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kbcha_brand_"))
def handle_kbcha_brand_selection(call):
    # Парсим данные из callback_data
    parts = call.data.split("_", 3)
    maker_code = parts[2]
    maker_name = parts[3] if len(parts) > 3 else "Неизвестно"

    # Сохраняем выбранную марку у пользователя для дальнейшего использования
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kbcha_maker_code"] = maker_code
    user_search_data[user_id]["kbcha_maker_name"] = maker_name

    # Получаем перевод названия марки, если оно есть
    translated_maker_name = translations.get(maker_name, maker_name)

    # Получаем список моделей для выбранной марки
    models = get_kbchachacha_models(maker_code)
    if not models:
        bot.send_message(
            call.message.chat.id, f"Не удалось загрузить модели для {maker_name}"
        )
        return

    # Создаем клавиатуру с моделями
    markup = types.InlineKeyboardMarkup(row_width=2)
    for item in models:
        class_name = item.get("className", "Без названия")
        class_code = item.get("classCode", "")

        # Добавляем перевод названия модели, если оно есть в словаре переводов
        translated_name = translations.get(class_name, class_name)

        # Используем только переведенное название для отображения
        display_name = translated_name

        callback_data = f"kbcha_model_{class_code}_{class_name}"
        markup.add(
            types.InlineKeyboardButton(display_name, callback_data=callback_data)
        )

    # Отображаем только переведенное название марки
    display_maker_name = translated_maker_name

    bot.send_message(
        call.message.chat.id,
        f"Марка: {display_maker_name}\nВыберите модель:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kbcha_model_"))
def handle_kbcha_model_selection(call):
    # Парсим данные из callback_data
    parts = call.data.split("_", 3)
    class_code = parts[2]
    class_name = parts[3] if len(parts) > 3 else "Неизвестно"

    # Сохраняем выбранную модель у пользователя для дальнейшего использования
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kbcha_class_code"] = class_code
    user_search_data[user_id]["kbcha_class_name"] = class_name

    # Получаем перевод названия модели, если оно есть
    translated_class_name = translations.get(class_name, class_name)

    # Получаем информацию о марке
    maker_name = user_search_data[user_id].get("kbcha_maker_name", "")
    maker_code = user_search_data[user_id].get("kbcha_maker_code", "")
    translated_maker_name = translations.get(maker_name, maker_name)

    # Получаем список поколений для выбранной модели
    generations = get_kbchachacha_generations(maker_code, class_code)
    if not generations:
        bot.send_message(
            call.message.chat.id, f"Не удалось загрузить поколения для {class_name}"
        )
        return

    # Создаем клавиатуру с поколениями
    markup = types.InlineKeyboardMarkup(row_width=1)
    for item in generations:
        car_name = item.get("carName", "Без названия")
        car_code = item.get("carCode", "")
        from_year = item.get("fromYear", "")
        to_year = item.get("toYear", "")

        # Форматируем период производства
        year_period = f"({from_year}-{to_year})" if from_year and to_year else ""
        if to_year == "현재":  # 현재 = "настоящее время" по-корейски
            year_period = f"({from_year}-н.в.)"

        # Используем translate_phrase для перевода названия поколения, которая разбивает текст на слова
        # и переводит каждое слово отдельно, что позволяет корректно переводить такие фразы как "가솔린 1.0 터보"
        translated_name = translate_phrase(car_name)

        # Используем формат: "Оригинальное название (Перевод) Период" или "Оригинальное название Период"
        if car_name != translated_name:
            display_text = f"{car_name} ({translated_name}) {year_period}"
        else:
            display_text = f"{car_name} {year_period}"

        callback_data = f"kbcha_gen_{car_code}_{car_name}"
        markup.add(
            types.InlineKeyboardButton(display_text, callback_data=callback_data)
        )

    # Форматируем отображаемые названия марки и модели с переводами, если они доступны
    display_maker_name = (
        f"{maker_name} ({translated_maker_name})"
        if maker_name != translated_maker_name
        else maker_name
    )
    display_class_name = (
        f"{class_name} ({translated_class_name})"
        if class_name != translated_class_name
        else class_name
    )

    bot.send_message(
        call.message.chat.id,
        f"Марка: {display_maker_name}\nМодель: {display_class_name}\nВыберите поколение:",
        reply_markup=markup,
    )


def search_kbchachacha_cars(
    maker_code,
    class_code,
    car_code,
    model_code,
    year_from=None,
    year_to=None,
    mileage_from=None,
    mileage_to=None,
    color_code=None,
):
    """
    Поиск автомобилей на KbChaChaCha
    """
    # Базовый URL для поиска
    url = f"https://www.kbchachacha.com/public/search/list.empty?makerCode={maker_code}&page=1&sort=-orderDate&classCode={class_code}&carCode={car_code}&modelCode={model_code}"

    # Добавляем дополнительные параметры, если они указаны
    if year_from and year_to:
        url += f"&regiDay={year_from},{year_to}"

    if mileage_from is not None and mileage_to is not None:
        url += f"&km={mileage_from},{mileage_to}"

    if color_code:
        url += f"&color={color_code}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        print(f"DEBUG: Отправка запроса на URL: {url}")
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        # Ищем все блоки с автомобилями
        car_areas = soup.select("div.list-in.type-wd-list div.area")

        results = []
        for area in car_areas[:5]:  # Ограничиваем до 5 результатов
            try:
                # Извлекаем данные об автомобиле
                car_seq = area.get("data-car-seq", "")
                car_link = f"https://www.kbchachacha.com/public/car/detail.kbc?carSeq={car_seq}"

                # Извлекаем название автомобиля
                car_title = area.select_one("div.con div.item strong.tit")
                title = car_title.text.strip() if car_title else "Неизвестно"

                # Извлекаем данные о годе, пробеге и регионе
                data_line = area.select_one("div.con div.item div.data-line")
                details = (
                    [span.text.strip() for span in data_line.select("span")]
                    if data_line
                    else []
                )
                year = details[0] if len(details) > 0 else "Неизвестно"
                mileage = details[1] if len(details) > 1 else "Неизвестно"
                region = details[2] if len(details) > 2 else "Неизвестно"

                # Извлекаем цену
                price_elem = area.select_one(
                    "div.con div.item div.sort-wrap strong.pay span.price"
                )
                price = price_elem.text.strip() if price_elem else "Неизвестно"

                # Получаем ссылку на изображение
                img_elem = area.select_one("div.thumnail a.item span.item__img img")
                img_url = img_elem.get("src", "") if img_elem else ""

                results.append(
                    {
                        "title": title,
                        "year": year,
                        "mileage": mileage,
                        "region": region,
                        "price": price,
                        "link": car_link,
                        "img_url": img_url,
                    }
                )
            except Exception as e:
                print(f"Ошибка при парсинге автомобиля: {e}")
                continue

        return results
    except Exception as e:
        print(f"Ошибка при поиске автомобилей на KbChaChaCha: {e}")
        return []


@bot.callback_query_handler(func=lambda call: call.data.startswith("kbcha_gen_"))
def handle_kbcha_generation_selection(call):
    # Парсим данные из callback_data
    parts = call.data.split("_", 3)
    car_code = parts[2]
    car_name = parts[3] if len(parts) > 3 else "Неизвестно"

    # Сохраняем выбранное поколение у пользователя для дальнейшего использования
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kbcha_car_code"] = car_code
    user_search_data[user_id]["kbcha_car_name"] = car_name

    # Получаем перевод названия поколения используя функцию translate_phrase
    # которая разбивает текст на слова и переводит каждое слово отдельно
    translated_car_name = translate_phrase(car_name)

    # Получаем информацию о марке и модели
    maker_name = user_search_data[user_id].get("kbcha_maker_name", "")
    maker_code = user_search_data[user_id].get("kbcha_maker_code", "")
    class_name = user_search_data[user_id].get("kbcha_class_name", "")
    class_code = user_search_data[user_id].get("kbcha_class_code", "")

    # Получаем переводы названий марки и модели, если они есть
    translated_maker_name = translations.get(maker_name, maker_name)
    translated_class_name = translations.get(class_name, class_name)

    # Получаем список конфигураций для выбранного поколения
    trims = get_kbchachacha_trims(maker_code, class_code, car_code)
    if not trims:
        bot.send_message(
            call.message.chat.id, f"Не удалось загрузить конфигурации для {car_name}"
        )
        return

    # Создаем клавиатуру с конфигурациями
    markup = types.InlineKeyboardMarkup(row_width=2)
    for item in trims:
        model_name = item.get("modelName", "Без названия")
        model_code = item.get("modelCode", "")

        # Добавляем перевод названия конфигурации используя translate_phrase
        # которая разбивает текст на слова и переводит каждое слово отдельно
        translated_name = translate_phrase(model_name)

        # Используем формат: "Оригинальное название (Перевод)" или просто "Оригинальное название", если перевода нет
        display_name = (
            f"{model_name} ({translated_name})"
            if model_name != translated_name
            else model_name
        )

        callback_data = f"kbcha_trim_{model_code}_{model_name}"
        markup.add(
            types.InlineKeyboardButton(display_name, callback_data=callback_data)
        )

    # Форматируем отображаемые названия с переводами, если они доступны
    display_maker_name = (
        f"{maker_name} ({translated_maker_name})"
        if maker_name != translated_maker_name
        else maker_name
    )
    display_class_name = (
        f"{class_name} ({translated_class_name})"
        if class_name != translated_class_name
        else class_name
    )
    display_car_name = (
        f"{car_name} ({translated_car_name})"
        if car_name != translated_car_name
        else car_name
    )

    bot.send_message(
        call.message.chat.id,
        f"Марка: {display_maker_name}\nМодель: {display_class_name}\nПоколение: {display_car_name}\nВыберите конфигурацию:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kbcha_trim_"))
def handle_kbcha_trim_selection(call):
    # Парсим данные из callback_data
    parts = call.data.split("_", 3)
    model_code = parts[2]
    model_name = parts[3] if len(parts) > 3 else "Неизвестно"

    print(f"✅ DEBUG kbcha_trim_selection - raw data:")
    print(f"model_code: {model_code}")
    print(f"model_name: {model_name}")

    # Сохраняем выбранную конфигурацию у пользователя для дальнейшего использования
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kbcha_model_code"] = model_code
    user_search_data[user_id]["kbcha_model_name"] = model_name

    # Получаем перевод названия конфигурации, используя translate_phrase
    translated_model_name = translate_phrase(model_name)

    # Получаем информацию о предыдущих выборах пользователя
    maker_name = user_search_data[user_id].get("kbcha_maker_name", "")
    maker_code = user_search_data[user_id].get("kbcha_maker_code", "")
    class_name = user_search_data[user_id].get("kbcha_class_name", "")
    class_code = user_search_data[user_id].get("kbcha_class_code", "")
    car_name = user_search_data[user_id].get("kbcha_car_name", "")
    car_code = user_search_data[user_id].get("kbcha_car_code", "")

    # Получаем переводы названий, если они есть
    translated_maker_name = translations.get(maker_name, maker_name)
    translated_class_name = translations.get(class_name, class_name)
    translated_car_name = translate_phrase(car_name)

    # Определяем начальный год для поколения
    # Отладочная информация о названии поколения и извлечении года
    print(f"⚙️ DEBUG kbcha_trim_selection - car_name: '{car_name}'")

    # По умолчанию используем значения
    start_year = datetime.now().year - 5  # По умолчанию 5 лет назад
    end_year = datetime.now().year  # По умолчанию текущий год

    # Пытаемся найти информацию о периоде выпуска поколения в его названии
    if "(" in car_name and ")" in car_name:
        period_part = car_name.split("(")[1].split(")")[0].strip()
        print(f"⚙️ DEBUG kbcha_trim_selection - period_part: '{period_part}'")

        # Проверяем разные форматы разделителей
        if "—" in period_part:
            parts = period_part.split("—")
        elif "-" in period_part:
            parts = period_part.split("-")
        else:
            parts = []

        print(f"⚙️ DEBUG kbcha_trim_selection - split parts: {parts}")

        if len(parts) == 2:
            start_date = parts[0].strip()
            end_date = parts[1].strip()
            print(
                f"⚙️ DEBUG kbcha_trim_selection - start_date: '{start_date}', end_date: '{end_date}'"
            )

            # Извлекаем год из начальной даты (формат может быть "03.2020" или "2020")
            if "." in start_date:
                start_year_str = start_date.split(".")[-1]
                print(
                    f"⚙️ DEBUG kbcha_trim_selection - parsed start_year_str: '{start_year_str}'"
                )
                if start_year_str.isdigit() and len(start_year_str) == 4:
                    start_year = int(start_year_str)
            elif start_date.isdigit() and len(start_date) == 4:
                start_year = int(start_date)

            # Извлекаем год из конечной даты
            if "." in end_date:
                end_year_str = end_date.split(".")[-1]
                print(
                    f"⚙️ DEBUG kbcha_trim_selection - parsed end_year_str: '{end_year_str}'"
                )
                if end_year_str.isdigit() and len(end_year_str) == 4:
                    end_year = int(end_year_str)
            elif end_date.isdigit() and len(end_date) == 4:
                end_year = int(end_date)

    print(
        f"⚙️ DEBUG kbcha_trim_selection - final start_year: {start_year}, end_year: {end_year}"
    )

    # Гарантируем, что start_year не больше текущего года
    current_year = datetime.now().year
    if start_year > current_year:
        start_year = current_year - 5

    # Если end_year < start_year (ошибочные данные), используем current_year
    if end_year < start_year:
        end_year = current_year

    # Сохраняем определенные годы для использования в дальнейшем
    user_search_data[user_id]["kbcha_generation_start_year"] = start_year
    user_search_data[user_id]["kbcha_generation_end_year"] = end_year

    # Формируем список годов для выбора
    markup = types.InlineKeyboardMarkup(row_width=3)

    # Добавляем года от начала производства поколения до его конца или текущего года
    for year in range(start_year, min(end_year, current_year) + 1):
        markup.add(
            types.InlineKeyboardButton(
                f"{year}", callback_data=f"kbcha_year_from_{year}"
            )
        )

    # Форматируем отображаемые названия с переводами, если они доступны
    display_maker_name = (
        f"{maker_name} ({translated_maker_name})"
        if maker_name != translated_maker_name
        else maker_name
    )
    display_class_name = (
        f"{class_name} ({translated_class_name})"
        if class_name != translated_class_name
        else class_name
    )
    display_car_name = (
        f"{car_name} ({translated_car_name})"
        if car_name != translated_car_name
        else car_name
    )
    display_model_name = (
        f"{model_name} ({translated_model_name})"
        if model_name != translated_model_name
        else model_name
    )

    bot.send_message(
        call.message.chat.id,
        f"Марка: {display_maker_name}\nМодель: {display_class_name}\nПоколение: {display_car_name}\nКонфигурация: {display_model_name}\n\nВыберите начальный год выпуска:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kbcha_year_from_"))
def handle_kbcha_year_from_selection(call):
    # Парсим выбранный год
    year_from = call.data.split("_")[3]

    # Сохраняем выбранный год начала
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kbcha_year_from"] = year_from

    # Получаем год окончания производства поколения
    end_year = user_search_data[user_id].get(
        "kbcha_generation_end_year", datetime.now().year
    )
    current_year = datetime.now().year
    year_from_int = int(year_from)

    # Формируем диапазон годов от выбранного года до конца производства поколения или текущего года
    markup = types.InlineKeyboardMarkup(row_width=3)
    for year in range(year_from_int, min(end_year, current_year) + 1):
        markup.add(
            types.InlineKeyboardButton(f"{year}", callback_data=f"kbcha_year_to_{year}")
        )

    bot.send_message(
        call.message.chat.id,
        f"Выбран начальный год: {year_from}\nТеперь выберите конечный год выпуска:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kbcha_year_to_"))
def handle_kbcha_year_to_selection(call):
    # Парсим выбранный год
    year_to = call.data.split("_")[3]

    # Сохраняем выбранный год конца
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kbcha_year_to"] = year_to

    # Показываем выбор пробега от
    markup = types.InlineKeyboardMarkup(row_width=3)
    for mileage in [0, 10000, 20000, 30000, 50000, 70000, 100000]:
        markup.add(
            types.InlineKeyboardButton(
                f"{mileage} км", callback_data=f"kbcha_mileage_from_{mileage}"
            )
        )

    bot.send_message(
        call.message.chat.id,
        f"Выбран диапазон годов: {user_search_data[user_id]['kbcha_year_from']}-{year_to}\nТеперь выберите минимальный пробег:",
        reply_markup=markup,
    )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("kbcha_mileage_from_")
)
def handle_kbcha_mileage_from_selection(call):
    # Парсим выбранный пробег
    mileage_from = call.data.split("_")[3]

    # Сохраняем выбранный минимальный пробег
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kbcha_mileage_from"] = mileage_from

    # Показываем выбор пробега до
    markup = types.InlineKeyboardMarkup(row_width=3)
    mileage_from_int = int(mileage_from)

    for mileage in [50000, 100000, 150000, 200000, 250000, 300000]:
        if mileage > mileage_from_int:
            markup.add(
                types.InlineKeyboardButton(
                    f"{mileage} км", callback_data=f"kbcha_mileage_to_{mileage}"
                )
            )

    bot.send_message(
        call.message.chat.id,
        f"Выбран минимальный пробег: {mileage_from} км\nТеперь выберите максимальный пробег:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kbcha_mileage_to_"))
def handle_kbcha_mileage_to_selection(call):
    # Парсим выбранный пробег
    mileage_to = call.data.split("_")[3]

    # Сохраняем выбранный максимальный пробег
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kbcha_mileage_to"] = mileage_to

    # Показываем выбор цвета
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Добавляем вариант "Любой"
    markup.add(types.InlineKeyboardButton("Любой", callback_data="kbcha_color_Любой"))

    # Добавляем доступные цвета
    for kr_name, info in KBCHACHA_COLOR_TRANSLATIONS.items():
        if kr_name != "Любой":  # Исключаем "Любой", так как мы его уже добавили выше
            markup.add(
                types.InlineKeyboardButton(
                    info["ru"], callback_data=f"kbcha_color_{kr_name}"
                )
            )

    bot.send_message(
        call.message.chat.id,
        f"Выбран диапазон пробега: {user_search_data[user_id]['kbcha_mileage_from']}-{mileage_to} км\nТеперь выберите цвет автомобиля:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kbcha_color_"))
def handle_kbcha_color_selection(call):
    # Парсим выбранный цвет
    color_kr = call.data.split("_")[2]

    # Сохраняем выбранный цвет
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    # Получаем русское название и код цвета
    color_info = KBCHACHA_COLOR_TRANSLATIONS.get(
        color_kr, {"ru": "Неизвестно", "code": ""}
    )
    color_ru = color_info["ru"]
    color_code = color_info["code"]

    user_search_data[user_id]["kbcha_color_kr"] = color_kr
    user_search_data[user_id]["kbcha_color_ru"] = color_ru
    user_search_data[user_id]["kbcha_color_code"] = color_code

    # Получаем информацию о предыдущих выборах пользователя
    maker_name = user_search_data[user_id].get("kbcha_maker_name", "")
    maker_code = user_search_data[user_id].get("kbcha_maker_code", "")
    class_name = user_search_data[user_id].get("kbcha_class_name", "")
    class_code = user_search_data[user_id].get("kbcha_class_code", "")
    car_name = user_search_data[user_id].get("kbcha_car_name", "")
    car_code = user_search_data[user_id].get("kbcha_car_code", "")
    model_name = user_search_data[user_id].get("kbcha_model_name", "")
    model_code = user_search_data[user_id].get("kbcha_model_code", "")
    year_from = user_search_data[user_id].get("kbcha_year_from", "")
    year_to = user_search_data[user_id].get("kbcha_year_to", "")
    mileage_from = user_search_data[user_id].get("kbcha_mileage_from", "")
    mileage_to = user_search_data[user_id].get("kbcha_mileage_to", "")

    # Отправляем сообщение о начале поиска
    bot.send_message(
        call.message.chat.id,
        f"🔍 Ищем {maker_name} {class_name} {car_name} {model_name}, год: {year_from}-{year_to}, пробег: {mileage_from}-{mileage_to} км, цвет: {color_ru}...",
    )

    # Ищем автомобили с выбранными параметрами
    cars = search_kbchachacha_cars(
        maker_code,
        class_code,
        car_code,
        model_code,
        year_from,
        year_to,
        mileage_from,
        mileage_to,
        color_code if color_code else None,
    )

    if not cars:
        # Отправляем сообщение, если автомобили не найдены
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(
                "➕ Добавить новый автомобиль в поиск", callback_data="search_car"
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                "🏠 Вернуться в главное меню", callback_data="start"
            )
        )

        bot.send_message(
            call.message.chat.id,
            f"😔 К сожалению, по вашему запросу ничего не найдено.\n\n"
            f"Марка: {maker_name}\n"
            f"Модель: {class_name}\n"
            f"Поколение: {car_name}\n"
            f"Конфигурация: {model_name}\n"
            f"Год: {year_from}-{year_to}\n"
            f"Пробег: {mileage_from}-{mileage_to} км\n"
            f"Цвет: {color_ru}",
            reply_markup=markup,
        )
        return

    # Отправляем только первый найденный автомобиль
    car = cars[0]
    caption = (
        f"🚗 <b>{car['title']}</b>\n"
        f"📆 Год: {car['year']}\n"
        f"🏁 Пробег: {car['mileage']}\n"
        f"📍 Регион: {car['region']}\n"
        f"💰 Цена: {car['price']}만원\n\n"
        f"🔗 <a href='{car['link']}'>Подробнее на KbChaChaCha</a>"
    )

    # Отправляем изображение если есть, или текст если изображения нет
    if car["img_url"] and car["img_url"] != "":
        try:
            bot.send_photo(
                call.message.chat.id, car["img_url"], caption=caption, parse_mode="HTML"
            )
        except Exception:
            # Если не удалось отправить фото, отправляем только текст
            bot.send_message(call.message.chat.id, caption, parse_mode="HTML")
    else:
        bot.send_message(call.message.chat.id, caption, parse_mode="HTML")

    # Отправляем кнопки для дальнейших действий
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "➕ Добавить новый автомобиль в поиск", callback_data="search_car"
        )
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="start")
    )

    bot.send_message(
        call.message.chat.id,
        f"✅ Показан результат поиска по запросу:\n\n"
        f"Марка: {maker_name}\n"
        f"Модель: {class_name}\n"
        f"Поколение: {car_name}\n"
        f"Конфигурация: {model_name}\n"
        f"Год: {year_from}-{year_to}\n"
        f"Пробег: {mileage_from}-{mileage_to} км\n"
        f"Цвет: {color_ru}",
        reply_markup=markup,
    )


# Функции для работы с KCar
def get_kcar_manufacturers():
    """Получение списка производителей с KCar"""
    url = "https://api.kcar.com/bc/search/group/mnuftr"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Content-Type": "application/json",
    }
    payload = {"wr_eq_sell_dcd": "ALL", "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd"}

    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        manufacturers = data.get("data", [])

        # Сортируем по имени производителя на английском
        manufacturers.sort(key=lambda x: x.get("mnuftrEnm", ""))

        return manufacturers
    except Exception as e:
        print("Ошибка при получении марок из KCar:", e)
        return []


def get_kcar_models(maker_code):
    """Получение списка моделей для выбранной марки с KCar"""
    url = "https://api.kcar.com/bc/search/group/modelGrp"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Content-Type": "application/json",
    }
    payload = {
        "wr_eq_sell_dcd": "ALL",
        "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd",
        "wr_eq_mnuftr_cd": maker_code,
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        models = data.get("data", [])

        # Сортируем по имени модели
        models.sort(key=lambda x: x.get("modelGrpNm", ""))

        # Отфильтровываем модели с count > 0, так как они реально представлены в списке
        models = [model for model in models if model.get("count", 0) > 0]

        return models
    except Exception as e:
        print(f"Ошибка при получении моделей с KCar для {maker_code}:", e)
        return []


def get_kcar_generations(maker_code, model_code):
    """Получение списка поколений для выбранной модели с KCar"""
    url = "https://api.kcar.com/bc/search/group/model"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Content-Type": "application/json",
    }
    payload = {
        "wr_eq_sell_dcd": "ALL",
        "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd",
        "wr_eq_mnuftr_cd": maker_code,
        "wr_eq_model_grp_cd": model_code,
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        generations = data.get("data", [])

        # Сортируем поколения по количеству автомобилей в наличии (по убыванию)
        generations.sort(key=lambda x: x.get("count", 0), reverse=True)

        # Отфильтровываем поколения с count > 0
        generations = [gen for gen in generations if gen.get("count", 0) > 0]

        return generations
    except Exception as e:
        print(
            f"Ошибка при получении поколений с KCar для {maker_code}/{model_code}:", e
        )
        return []


def get_kcar_configurations(maker_code, model_group_code, model_code):
    """Получение списка конфигураций для выбранного поколения с KCar"""
    url = "https://api.kcar.com/bc/search/group/grd"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Content-Type": "application/json",
    }
    payload = {
        "wr_eq_sell_dcd": "ALL",
        "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd",
        "wr_eq_mnuftr_cd": maker_code,
        "wr_eq_model_grp_cd": model_group_code,
        "wr_eq_model_cd": model_code,
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        configurations = data.get("data", [])

        # Сортируем конфигурации по количеству автомобилей в наличии (по убыванию)
        configurations.sort(key=lambda x: x.get("count", 0), reverse=True)

        # Отфильтровываем конфигурации с count > 0
        configurations = [
            config for config in configurations if config.get("count", 0) > 0
        ]

        return configurations
    except Exception as e:
        print(
            f"Ошибка при получении конфигураций с KCar для {maker_code}/{model_group_code}/{model_code}:",
            e,
        )
        return []


def handle_kcar_search(call):
    """Обработчик для поиска автомобилей на KCar"""
    # Получаем список производителей
    manufacturers = get_kcar_manufacturers()
    if not manufacturers:
        bot.answer_callback_query(call.id, "Не удалось загрузить марки с KCar.")
        return

    # Создаем клавиатуру с марками
    markup = types.InlineKeyboardMarkup(row_width=2)
    for item in manufacturers:
        maker_name = item.get("mnuftrEnm", "Без названия")
        maker_code = item.get("mnuftrCd", "")
        # Используем специальный префикс для отличия от других площадок
        callback_data = f"kcar_brand_{maker_code}_{maker_name}"
        markup.add(types.InlineKeyboardButton(maker_name, callback_data=callback_data))

    bot.send_message(
        call.message.chat.id, "Выберите марку автомобиля:", reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kcar_brand_"))
def handle_kcar_brand_selection(call):
    """Обработчик выбора марки автомобиля на KCar"""
    # Парсим данные из callback_data
    parts = call.data.split("_", 3)
    maker_code = parts[2]
    maker_name = parts[3] if len(parts) > 3 else "Неизвестно"

    # Сохраняем выбранную марку у пользователя для дальнейшего использования
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kcar_maker_code"] = maker_code
    user_search_data[user_id]["kcar_maker_name"] = maker_name

    # Получаем список моделей для выбранной марки
    models = get_kcar_models(maker_code)
    if not models:
        bot.send_message(
            call.message.chat.id,
            f"Не удалось загрузить модели для {maker_name} или для этой марки нет доступных моделей.",
        )
        return

    # Создаем клавиатуру с моделями
    markup = types.InlineKeyboardMarkup(row_width=2)
    for item in models:
        model_name = item.get("modelGrpNm", "Без названия")
        model_code = item.get("modelGrpCd", "")
        callback_data = f"kcar_model_{model_code}_{model_name}"
        markup.add(types.InlineKeyboardButton(model_name, callback_data=callback_data))

    bot.send_message(
        call.message.chat.id,
        f"Марка: {maker_name}\nВыберите модель:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kcar_model_"))
def handle_kcar_model_selection(call):
    """Обработчик выбора модели автомобиля на KCar"""
    # Парсим данные из callback_data
    parts = call.data.split("_", 3)
    model_code = parts[2]
    model_name = parts[3] if len(parts) > 3 else "Неизвестно"

    # Сохраняем выбранную модель у пользователя для дальнейшего использования
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kcar_model_code"] = model_code
    user_search_data[user_id]["kcar_model_name"] = model_name

    # Получаем информацию о марке
    maker_name = user_search_data[user_id].get("kcar_maker_name", "")
    maker_code = user_search_data[user_id].get("kcar_maker_code", "")

    # Получаем список поколений для выбранной модели
    generations = get_kcar_generations(maker_code, model_code)
    if not generations:
        bot.send_message(
            call.message.chat.id,
            f"Не удалось загрузить поколения для {model_name} или для этой модели нет доступных поколений.",
        )
        return

    # Создаем клавиатуру с поколениями
    markup = types.InlineKeyboardMarkup(row_width=1)
    for item in generations:
        gen_name = item.get("modelNm", "Без названия")
        gen_year = item.get("prdcnYear", "")
        gen_code = item.get("modelCd", "")

        # Формируем текст кнопки с названием и годами производства
        display_text = f"{gen_name} {gen_year}"
        callback_data = f"kcar_gen_{gen_code}_{gen_name}"

        markup.add(
            types.InlineKeyboardButton(display_text, callback_data=callback_data)
        )

    bot.send_message(
        call.message.chat.id,
        f"Марка: {maker_name}\nМодель: {model_name}\nВыберите поколение:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kcar_gen_"))
def handle_kcar_generation_selection(call):
    """Обработчик выбора поколения автомобиля на KCar"""
    # Парсим данные из callback_data
    parts = call.data.split("_", 3)
    gen_code = parts[2]
    gen_name = parts[3] if len(parts) > 3 else "Неизвестно"

    # Сохраняем выбранное поколение у пользователя для дальнейшего использования
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kcar_gen_code"] = gen_code
    user_search_data[user_id]["kcar_gen_name"] = gen_name

    # Получаем информацию о предыдущих выборах
    maker_name = user_search_data[user_id].get("kcar_maker_name", "")
    maker_code = user_search_data[user_id].get("kcar_maker_code", "")
    model_name = user_search_data[user_id].get("kcar_model_name", "")
    model_code = user_search_data[user_id].get("kcar_model_code", "")

    # Получаем список конфигураций для выбранного поколения
    configurations = get_kcar_configurations(maker_code, model_code, gen_code)
    if not configurations:
        bot.send_message(
            call.message.chat.id,
            f"Не удалось загрузить конфигурации для {gen_name} или для этого поколения нет доступных конфигураций.",
        )
        return

    # Создаем клавиатуру с конфигурациями
    markup = types.InlineKeyboardMarkup(row_width=1)
    for item in configurations:
        config_name = item.get("grdNm", "Без названия")
        config_code = item.get("grdCd", "")
        count = item.get("count", 0)

        # Формируем текст кнопки с названием и количеством автомобилей
        display_text = f"{config_name} ({count} шт.)"
        callback_data = f"kcar_config_{config_code}_{config_name}"

        markup.add(
            types.InlineKeyboardButton(display_text, callback_data=callback_data)
        )

    bot.send_message(
        call.message.chat.id,
        f"Марка: {maker_name}\nМодель: {model_name}\nПоколение: {gen_name}\nВыберите конфигурацию:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kcar_config_"))
def handle_kcar_configuration_selection(call):
    """Обработчик выбора конфигурации автомобиля на KCar"""
    # Парсим данные из callback_data
    parts = call.data.split("_", 3)
    config_code = parts[2]
    config_name = parts[3] if len(parts) > 3 else "Неизвестно"

    print(f"✅ DEBUG kcar_config_selection - raw data:")
    print(f"config_code: {config_code}")
    print(f"config_name: {config_name}")

    # Сохраняем выбранную конфигурацию у пользователя для дальнейшего использования
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kcar_config_code"] = config_code
    user_search_data[user_id]["kcar_config_name"] = config_name

    # Получаем информацию о предыдущих выборах
    maker_name = user_search_data[user_id].get("kcar_maker_name", "")
    model_name = user_search_data[user_id].get("kcar_model_name", "")
    gen_name = user_search_data[user_id].get("kcar_gen_name", "")

    # Отладочная информация о названии поколения
    print(f"⚙️ DEBUG kcar_config_selection - gen_name: '{gen_name}'")

    # По умолчанию используем значения
    start_year = datetime.now().year - 5  # По умолчанию 5 лет назад
    end_year = datetime.now().year  # По умолчанию текущий год

    # Пытаемся извлечь годы производства из названия поколения
    if "(" in gen_name and ")" in gen_name:
        period_part = gen_name.split("(")[1].split(")")[0].strip()
        print(f"⚙️ DEBUG kcar_config_selection - period_part: '{period_part}'")

        # Проверяем разные форматы разделителей
        if "—" in period_part:
            parts = period_part.split("—")
        elif "-" in period_part:
            parts = period_part.split("-")
        else:
            parts = []

        print(f"⚙️ DEBUG kcar_config_selection - split parts: {parts}")

        if len(parts) == 2:
            start_date = parts[0].strip()
            end_date = parts[1].strip()
            print(
                f"⚙️ DEBUG kcar_config_selection - start_date: '{start_date}', end_date: '{end_date}'"
            )

            # Извлекаем год из начальной даты
            if "." in start_date:
                start_year_str = start_date.split(".")[-1]
                print(
                    f"⚙️ DEBUG kcar_config_selection - parsed start_year_str: '{start_year_str}'"
                )
                if start_year_str.isdigit() and len(start_year_str) == 4:
                    start_year = int(start_year_str)
            elif start_date.isdigit() and len(start_date) == 4:
                start_year = int(start_date)

            # Извлекаем год из конечной даты
            if "." in end_date:
                end_year_str = end_date.split(".")[-1]
                print(
                    f"⚙️ DEBUG kcar_config_selection - parsed end_year_str: '{end_year_str}'"
                )
                if end_year_str.isdigit() and len(end_year_str) == 4:
                    end_year = int(end_year_str)
            elif end_date.isdigit() and len(end_date) == 4:
                end_year = int(end_date)

    print(
        f"⚙️ DEBUG kcar_config_selection - final start_year: {start_year}, end_year: {end_year}"
    )

    # Гарантируем, что start_year не больше текущего года
    current_year = datetime.now().year
    if start_year > current_year:
        start_year = current_year - 5

    # Если end_year < start_year (ошибочные данные), используем current_year
    if end_year < start_year:
        end_year = current_year

    # Сохраняем определенные годы для использования в дальнейшем
    user_search_data[user_id]["kcar_generation_start_year"] = start_year
    user_search_data[user_id]["kcar_generation_end_year"] = end_year

    # Показываем выбор года от
    year_markup = types.InlineKeyboardMarkup(row_width=3)

    # Добавляем года от начала производства поколения до его конца или текущего года
    for year in range(start_year, min(end_year, current_year) + 1):
        year_markup.add(
            types.InlineKeyboardButton(
                f"{year}", callback_data=f"kcar_year_from_{year}"
            )
        )

    bot.send_message(
        call.message.chat.id,
        f"Марка: {maker_name}\nМодель: {model_name}\nПоколение: {gen_name}\nКонфигурация: {config_name}\n\nВыберите начальный год выпуска (поколение {start_year}-{end_year}):",
        reply_markup=year_markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kcar_year_from_"))
def handle_kcar_year_from_selection(call):
    """Обработчик выбора начального года для KCar"""
    # Парсим выбранный год
    year_from = call.data.split("_")[3]

    # Сохраняем выбранный начальный год
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kcar_year_from"] = year_from

    # Получаем конечный год периода выпуска поколения из сохраненных данных
    end_year = user_search_data[user_id].get(
        "kcar_generation_end_year", datetime.now().year
    )
    current_year = datetime.now().year
    year_from_int = int(year_from)

    # Формируем диапазон лет от выбранного года до конца производства поколения или текущего года
    year_markup = types.InlineKeyboardMarkup(row_width=3)
    for year in range(year_from_int, min(end_year, current_year) + 1):
        year_markup.add(
            types.InlineKeyboardButton(f"{year}", callback_data=f"kcar_year_to_{year}")
        )

    bot.send_message(
        call.message.chat.id,
        f"Выбран начальный год: {year_from}\nТеперь выберите конечный год выпуска:",
        reply_markup=year_markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kcar_year_to_"))
def handle_kcar_year_to_selection(call):
    """Обработчик выбора конечного года для KCar"""
    # Парсим выбранный год
    year_to = call.data.split("_")[3]

    # Сохраняем выбранный конечный год
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kcar_year_to"] = year_to

    # Показываем выбор минимального пробега
    mileage_markup = types.InlineKeyboardMarkup(row_width=3)
    for mileage in [0, 10000, 20000, 30000, 50000, 70000, 100000]:
        mileage_markup.add(
            types.InlineKeyboardButton(
                f"{mileage} км", callback_data=f"kcar_mileage_from_{mileage}"
            )
        )

    bot.send_message(
        call.message.chat.id,
        f"Выбран диапазон годов: {user_search_data[user_id]['kcar_year_from']}-{year_to}\nТеперь выберите минимальный пробег:",
        reply_markup=mileage_markup,
    )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("kcar_mileage_from_")
)
def handle_kcar_mileage_from_selection(call):
    """Обработчик выбора минимального пробега для KCar"""
    # Парсим выбранный пробег
    mileage_from = call.data.split("_")[3]

    # Сохраняем выбранный минимальный пробег
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kcar_mileage_from"] = mileage_from

    # Показываем выбор максимального пробега
    mileage_markup = types.InlineKeyboardMarkup(row_width=3)
    mileage_from_int = int(mileage_from)

    for mileage in [50000, 100000, 150000, 200000, 250000, 300000]:
        if mileage > mileage_from_int:
            mileage_markup.add(
                types.InlineKeyboardButton(
                    f"{mileage} км", callback_data=f"kcar_mileage_to_{mileage}"
                )
            )

    bot.send_message(
        call.message.chat.id,
        f"Выбран минимальный пробег: {mileage_from} км\nТеперь выберите максимальный пробег:",
        reply_markup=mileage_markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kcar_mileage_to_"))
def handle_kcar_mileage_to_selection(call):
    """Обработчик выбора максимального пробега для KCar"""
    # Парсим выбранный пробег
    mileage_to = call.data.split("_")[3]

    # Сохраняем выбранный максимальный пробег
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    user_search_data[user_id]["kcar_mileage_to"] = mileage_to

    # Показываем выбор цвета
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Добавляем вариант "Любой"
    markup.add(types.InlineKeyboardButton("Любой", callback_data="kcar_color_Любой"))

    # Добавляем доступные цвета
    for kr_name, ru_name in KCAR_COLOR_TRANSLATIONS.items():
        if kr_name != "Любой":  # Исключаем "Любой", так как мы его уже добавили выше
            markup.add(
                types.InlineKeyboardButton(
                    ru_name, callback_data=f"kcar_color_{kr_name}"
                )
            )

    bot.send_message(
        call.message.chat.id,
        f"Выбран диапазон пробега: {user_search_data[user_id]['kcar_mileage_from']}-{mileage_to} км\nТеперь выберите цвет автомобиля:",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("kcar_color_"))
def handle_kcar_color_selection(call):
    """Обработчик выбора цвета для KCar"""
    # Парсим выбранный цвет
    color_kr = call.data.split("_")[2]

    # Сохраняем выбранный цвет
    user_id = call.from_user.id
    if user_id not in user_search_data:
        user_search_data[user_id] = {}

    color_ru = KCAR_COLOR_TRANSLATIONS.get(color_kr, "Неизвестно")

    user_search_data[user_id]["kcar_color_kr"] = color_kr
    user_search_data[user_id]["kcar_color_ru"] = color_ru

    # Получаем все сохраненные данные о выборе пользователя
    maker_name = user_search_data[user_id].get("kcar_maker_name", "")
    maker_code = user_search_data[user_id].get("kcar_maker_code", "")
    model_name = user_search_data[user_id].get("kcar_model_name", "")
    model_code = user_search_data[user_id].get("kcar_model_code", "")
    gen_name = user_search_data[user_id].get("kcar_gen_name", "")
    gen_code = user_search_data[user_id].get("kcar_gen_code", "")
    config_name = user_search_data[user_id].get("kcar_config_name", "")
    config_code = user_search_data[user_id].get("kcar_config_code", "")
    year_from = user_search_data[user_id].get("kcar_year_from", "")
    year_to = user_search_data[user_id].get("kcar_year_to", "")
    mileage_from = user_search_data[user_id].get("kcar_mileage_from", "")
    mileage_to = user_search_data[user_id].get("kcar_mileage_to", "")

    # Отправляем сообщение о завершении выбора параметров
    summary = (
        f"✅ Поиск на KCar с параметрами:\n\n"
        f"Марка: {maker_name}\n"
        f"Модель: {model_name}\n"
        f"Поколение: {gen_name}\n"
        f"Конфигурация: {config_name}\n"
        f"Год: {year_from}-{year_to}\n"
        f"Пробег: {mileage_from}-{mileage_to} км\n"
        f"Цвет: {color_ru}\n\n"
        f"Пожалуйста, подождите, идет поиск автомобилей..."
    )

    message = bot.send_message(
        call.message.chat.id,
        summary,
        parse_mode="HTML",
    )

    # Ищем автомобили с помощью функции парсинга HTML
    cars = search_kcar_cars_by_html(
        maker_code,
        model_code,
        gen_code,
        year_from=year_from,
        year_to=year_to,
        mileage_from=mileage_from,
        mileage_to=mileage_to,
        color=color_kr,  # Передаем корейское название цвета
    )

    if not cars:
        # Если автомобили не найдены
        bot.edit_message_text(
            f"{summary}\n\n❌ К сожалению, автомобили с указанными параметрами не найдены.\n\n"
            f"Вы можете посмотреть автомобили на сайте KCar по ссылке:\n"
            f"https://www.kcar.com/bc/search",
            chat_id=call.message.chat.id,
            message_id=message.message_id,
            parse_mode="HTML",
        )
    else:
        # Формируем сообщение с результатами поиска
        bot.edit_message_text(
            f"{summary}\n\n✅ Найдено автомобилей: {len(cars)}",
            chat_id=call.message.chat.id,
            message_id=message.message_id,
            parse_mode="HTML",
        )

        # Отправляем информацию о каждом автомобиле
        for car in cars:
            car_message = (
                f"🚗 <b>{car['title']}</b>\n\n"
                f"💰 <b>Цена:</b> {car['price']}\n"
                f"📅 <b>Год:</b> {car['year']}\n"
                f"🛣 <b>Пробег:</b> {car['mileage']}\n"
                f"⛽️ <b>Топливо:</b> {car['fuel_type']}\n"
                f"📍 <b>Местоположение:</b> {car['location']}\n"
            )

            if car["description"]:
                car_message += f"\n📝 <b>Описание:</b> {car['description']}\n"

            if car["labels"]:
                labels_text = ", ".join(car["labels"])
                car_message += f"\n🏷 <b>Особенности:</b> {labels_text}\n"

            # Добавляем ссылку на страницу автомобиля
            car_message += f"\n🔎 <a href='{car['link']}'>Подробнее на сайте KCar</a>"

            # Создаем клавиатуру с кнопкой для перехода к автомобилю
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("Открыть на сайте KCar", url=car["link"])
            )

            # Если есть изображение, отправляем фото с описанием
            if car["img_url"]:
                try:
                    bot.send_photo(
                        call.message.chat.id,
                        car["img_url"],
                        caption=car_message,
                        reply_markup=markup,
                        parse_mode="HTML",
                    )
                except Exception as e:
                    print(f"Ошибка при отправке фото: {e}")
                    # Если не удалось отправить фото, отправляем только текст
                    bot.send_message(
                        call.message.chat.id,
                        car_message,
                        reply_markup=markup,
                        parse_mode="HTML",
                    )
            else:
                # Если нет изображения, отправляем только текст
                bot.send_message(
                    call.message.chat.id,
                    car_message,
                    reply_markup=markup,
                    parse_mode="HTML",
                )

    # Кнопки для дальнейших действий
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "➕ Добавить новый автомобиль в поиск", callback_data="search_car"
        )
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="start")
    )

    bot.send_message(
        call.message.chat.id,
        "Что вы хотите сделать дальше?",
        reply_markup=markup,
        parse_mode="HTML",
    )


def search_kcar_cars_by_html(
    mnuftr_cd,
    model_grp_cd,
    model_cd,
    year_from=None,
    year_to=None,
    mileage_from=None,
    mileage_to=None,
    color=None,
):
    """
    Поиск автомобилей на KCar через парсинг HTML страницы

    Параметры:
    mnuftr_cd (str): Код производителя
    model_grp_cd (str): Код группы моделей
    model_cd (str): Код модели
    year_from (str, optional): Начальный год выпуска
    year_to (str, optional): Конечный год выпуска
    mileage_from (str, optional): Минимальный пробег
    mileage_to (str, optional): Максимальный пробег
    color (str, optional): Корейское название цвета

    Возвращает:
    list: Список автомобилей с информацией
    """
    # Базовый поисковый запрос
    base_search_cond = {
        "wr_eq_mnuftr_cd": mnuftr_cd,
        "wr_eq_model_grp_cd": model_grp_cd,
        "wr_eq_model_cd": model_cd,
    }

    # Добавляем дополнительные параметры, если они указаны
    if year_from and year_to:
        base_search_cond["wr_bt_prdcn_year"] = f"{year_from},{year_to}"

    if mileage_from is not None and mileage_to is not None:
        base_search_cond["wr_bt_accent_km"] = f"{mileage_from},{mileage_to}"

    # Добавляем параметр цвета, если выбран конкретный цвет (не "Любой")
    if color and color != "Любой":
        # Находим корейское название цвета среди ключей словаря
        for kr_color, ru_color in KCAR_COLOR_TRANSLATIONS.items():
            if kr_color == color:
                # Здесь предполагается, что код цвета может потребоваться позже
                # Сейчас используем просто корейское название
                base_search_cond["wr_eq_extl_color_nm"] = kr_color
                break

    # Преобразуем словарь в JSON строку и кодируем для URL
    search_cond = urllib.parse.quote(json.dumps(base_search_cond))

    # Формируем URL для запроса
    url = f"https://www.kcar.com/bc/search?searchCond={search_cond}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        print(f"DEBUG: Отправка запроса на URL: {url}")
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"Ошибка при получении страницы: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        # Ищем блок с автомобилями
        car_list_wrap = soup.select_one("div.carListWrap")
        if not car_list_wrap:
            print("Не найден блок с автомобилями (div.carListWrap)")
            return []

        # Извлекаем все блоки с автомобилями
        car_list_boxes = car_list_wrap.select("div.carListBox")
        if not car_list_boxes:
            print("Не найдены блоки с автомобилями (div.carListBox)")
            return []

        results = []
        for box in car_list_boxes[:5]:  # Ограничиваем до 5 результатов
            try:
                # Извлекаем данные об автомобиле
                detail_info = box.select_one("div.detailInfo")
                if not detail_info:
                    continue

                # Название автомобиля
                car_name_elem = box.select_one("div.carName p.carTit a")
                car_name = car_name_elem.text.strip() if car_name_elem else "Неизвестно"

                # Получаем ссылку на автомобиль
                car_link = car_name_elem.get("href", "") if car_name_elem else ""
                if car_link:
                    car_link = f"https://www.kcar.com{car_link}"

                # Цена
                car_exp_elem = box.select_one("div.carExpIn p.carExp")
                car_price = car_exp_elem.text.strip() if car_exp_elem else "Неизвестно"

                # Детали автомобиля (год, пробег, тип топлива)
                car_details_elem = box.select_one("p.detailCarCon")
                car_details = []
                if car_details_elem:
                    for span in car_details_elem.select("span"):
                        car_details.append(span.text.strip())

                year = car_details[0] if len(car_details) > 0 else "Неизвестно"
                mileage = car_details[1] if len(car_details) > 1 else "Неизвестно"
                fuel_type = car_details[2] if len(car_details) > 2 else "Неизвестно"
                location = car_details[3] if len(car_details) > 3 else "Неизвестно"

                # Изображение автомобиля
                img_elem = box.select_one("div.carListImg a img")
                img_url = img_elem.get("src", "") if img_elem else ""

                # Краткое описание автомобиля
                car_desc_elem = box.select_one("div.carSimcDesc")
                car_desc = car_desc_elem.text.strip() if car_desc_elem else ""

                # Получаем дополнительные метки (VIP, 360 и т.д.)
                car_labels = []
                free_delivery = box.select_one("span.stateDlvy")
                if free_delivery:
                    car_labels.append("Бесплатная доставка")

                car_360 = box.select_one("span.car360Img")
                if car_360:
                    car_labels.append("360° обзор")

                results.append(
                    {
                        "title": car_name,
                        "price": car_price,
                        "year": year,
                        "mileage": mileage,
                        "fuel_type": fuel_type,
                        "location": location,
                        "description": car_desc,
                        "link": car_link,
                        "img_url": img_url,
                        "labels": car_labels,
                    }
                )
            except Exception as e:
                print(f"Ошибка при парсинге автомобиля: {e}")
                continue

        return results
    except Exception as e:
        print(f"Ошибка при поиске автомобилей на KCar через HTML: {e}")
        return []


# Запуск бота
if __name__ == "__main__":
    from datetime import datetime

    print("=" * 50)
    print(
        f"🚀 [82 Auto Bot] Запуск бота — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("📦 Загрузка сохранённых запросов пользователей...")
    load_requests()
    print("✅ Запросы успешно загружены.")
    print("🤖 Бот запущен и ожидает команды...")
    print("=" * 50)
    ACCESS = load_access()
    bot.infinity_polling()
