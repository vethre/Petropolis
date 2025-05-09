# main.py (refactored for latest python-telegram-bot v20+)

import os
from dotenv import load_dotenv
import random
import json
import logging
from datetime import datetime
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
                          ContextTypes, MessageHandler, ConversationHandler, filters)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from keep_alive import keep_alive
import pymongo

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

# Храним временные трейды в памяти
active_trades = {}  # {user_id: {"partner": partner_id, "offer": pet_index, "status": "waiting"|"confirmed"}}
user_states = {}
load_dotenv()
TOKEN=os.getenv("TOKEN")
MONGO_URI=os.getenv("MONGO_URI")
client = pymongo.MongoClient(MONGO_URI)
db = client["petropolis"]
users_collection = db["users"]

# Constants
PET_TYPES = ["Огненный", "Водный", "Земляной", "Воздушный", "Светлый", "Тёмный"]
RARITIES = ["Обычный", "Необычный", "Редкостный", "Эпический", "Легендарный", "Мифический"]
RARITY_CHANCES = {
    "Обычный": 0.35,
    "Необычный": 0.30,
    "Редкостный": 0.20,
    "Эпический": 0.10,
    "Легендарный": 0.04,
    "Мифический": 0.01,
}
RARITY_MULTIPLIERS = {
    "Обычный": 50,
    "Необычный": 100,
    "Редкостный": 250,
    "Эпический": 500,
    "Легендарный": 1500,
    "Мифический": 3000,
}
EGG_PRICES = {
    "Базовое": 150,
    "Премиум": 600,
    "Редкостное": 1200,
}
EGG_RARITY_BOOSTS = {
    "Базовое": 0,
    "Премиум": 0.30,
    "Редкостное": 0.45,
}

# File to store user data
DATA_FILE = "user_data.json"

# Functions to load and save data
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            # If the file is not found or the JSON is broken, return a default structure
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def get_user(user_id):
    """Retrieve user data from MongoDB or create a new user if not found."""
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "coins": 450,
            "eggs": {},
            "pets": [],
            "last_daily": None,
            "streak": 0
        }
        users_collection.insert_one(user)
    return user

def save_user(user):
    """Save or update user data in MongoDB."""
    users_collection.update_one(
        {"user_id": user["user_id"]},
        {"$set": user},
        upsert=True
    )

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    pets = user.get("pets", [])
    pet_summary = ", ".join([p["name"] for p in pets]) or "нет"

    text = (
        f"👤 Профиль\n"
        f"💰 Монеты: {user['coins']}\n"
        f"🥚 Яйца: {len(user['eggs'])}\n"
        f"🙈 Питомцы: {len(pets)}\n"
        f"🔥 Стрик: {user.get('streak', 0)} дн"
    )
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>Комманды Петрополиса:</b>\n\n"
        "🥚 <b>Яйца & Питомцы</b>\n"
        "/buy_egg - Купить яйцо\n"
        "/hatch - Вскрыть купленное яйцо\n"
        "/pets - Посмотреть свою коллекцию питомцев\n\n"
        "💰 <b>Экономика</b>\n"
        "/collect - Собрать доход с питомцев\n"
        "/daily - Получить дневное вознаграждение\n"
        "/profile - Посмотреть свой профиль\n"
        "/balance - Посмотреть свой баланс\n\n"
        "🔄 <b>Прогресс</b>\n"
        "/merge <цифра первого питомца> <цифра второго> - Скрестить питомцев воедино\n"
        "/train <цифра питомца по счету> <качество> - Тренировать питомца\n\n"
        "🤝 <b>Трэйдинг</b>\n"
        "/myid - Узнать своё ID\n"
        "/trade <ID пользователя> - Обмен питомцами\n\n"
        "⚔️ <b>Бой - в разработке</b>\n"
        "/battle <ID пользователя> - Сражаться с другими\n"
        "/leaderboard - Лидеры"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

# User init
def initialize_user(user_id):
    return {
        "coins": 450,
        "pets": [],
        "last_claim": None,
        "streak": 0,
        "last_daily": None,
    }

# Pet generation
def determine_rarity(rarity_boost=0):
    roll = random.random() - rarity_boost
    if roll < RARITY_CHANCES["Мифический"]:
        return "Мифический"
    elif roll < sum(RARITY_CHANCES[r] for r in ["Легендарный", "Мифический"]):
        return "Легендарный"
    elif roll < sum(RARITY_CHANCES[r] for r in ["Эпический", "Легендарный", "Мифический"]):
        return "Эпический"
    elif roll < sum(RARITY_CHANCES[r] for r in ["Редкостный", "Эпический", "Легендарный", "Мифический"]):
        return "Редкостный"
    elif roll < sum(RARITY_CHANCES[r] for r in ["Необычный", "Редкостный", "Эпический", "Легендарный", "Мифический"]):
        return "Необычный"
    return "Обычный"

def generate_random_pet(pet_type=None, rarity_boost=0):
    if pet_type is None:
        pet_type = random.choice(PET_TYPES)
    rarity = determine_rarity(rarity_boost)
    multiplier = RARITY_MULTIPLIERS[rarity]
    base_stats = random.randint(5, 12) * multiplier
    return {
        "id": random.randint(10000, 99999),
        "name": f"{rarity} {pet_type}",
        "type": pet_type,
        "rarity": rarity,
        "level": 1,
        "xp": 0,
        "xp_needed": 100,
        "stats": {
            "attack": base_stats + random.randint(-1, 5),
            "defense": base_stats + random.randint(1, 5),
            "health": base_stats * 2 + random.randint(5, 7),
            "speed": base_stats + random.randint(1, 8),
        },
        "coin_rate": 20 + (RARITY_MULTIPLIERS[rarity] // 2),
        "last_collected": None,
    }

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    await update.message.reply_text(f"👋 Привет! У тебя {user['coins']} монет. Напиши /help для большей информации!")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    await update.message.reply_text(f"💸 У тебя {user['coins']} монет.")

async def buy_egg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"🥚 Базовое - {EGG_PRICES['Базовое']} монет", callback_data="buy_Базовое"),
         InlineKeyboardButton(f"💠 Премиум - {EGG_PRICES['Премиум']} монет", callback_data="buy_Премиум")],
        [InlineKeyboardButton(f"🌟 Редкостное - {EGG_PRICES['Редкостное']} монет", callback_data="buy_Редкостное")],
    ]
    await update.message.reply_text("🎰 Выбери яйцо для покупки:", reply_markup=InlineKeyboardMarkup(keyboard))

async def buy_egg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    egg_type = query.data.split("_")[1]
    user = get_user(user_id)

    if user["coins"] < EGG_PRICES[egg_type]:
        await query.edit_message_text(f"💸 Недостаточно монет для покупки яйца типа {egg_type}.")
        return

    if "eggs" not in user:
        user["eggs"] = {}
    if egg_type not in user["eggs"]:
        user["eggs"][egg_type] = 0

    user["eggs"][egg_type] += 1
    user["coins"] -= EGG_PRICES[egg_type]
    save_user(user)

    await query.edit_message_text(f"🐣 Вы купили {egg_type} яйцо за {EGG_PRICES[egg_type]} монет!")

async def hatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display available eggs to hatch"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if "eggs" not in user or not user["eggs"]:
        await update.message.reply_text("🥚 У тебя нет яиц для вскрытия. Купи их через /buy_egg!")
        return

    keyboard = []
    for egg_type, count in user["eggs"].items():
        if count > 0:
            keyboard.append([InlineKeyboardButton(f"{egg_type} яйцо ({count})", callback_data=f"hatch_{egg_type}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🥚 Выбери яйцо для вскрытия:", reply_markup=reply_markup)

async def hatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process egg hatching"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    egg_type = query.data.split("_")[1]
    user = get_user(user_id)

    if egg_type not in user["eggs"] or user["eggs"][egg_type] <= 0:
        await query.edit_message_text(f"😔 У тебя нет яиц типа *{egg_type}* для вскрытия.")
        return

    pet = generate_random_pet(rarity_boost=EGG_RARITY_BOOSTS[egg_type])
    user["eggs"][egg_type] -= 1

    if "pets" not in user:
        user["pets"] = []

    user["pets"].append(pet)
    save_user(user)

    await query.edit_message_text(
        f"🥚 Из {egg_type} яйца вылупился {pet['rarity']} {pet['type']} питомец!\n\n"
        f"🆔 ID: {pet['id']}\n"
        f"⚔️ Атака: {pet['stats']['attack']}\n"
        f"🛡️ Защита: {pet['stats']['defense']}\n"
        f"❤️ Здоровье: {pet['stats']['health']}\n"
        f"⚡ Скорость: {pet['stats']['speed']}\n\n"
        f"Этот питомец приносит {pet['coin_rate']} монет/час."
    )

async def pets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display user's pets"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user.get("pets"):
        await update.message.reply_text("😉 У тебя пока нет питомцев. Купи и вскрой яйцо сначала!")
        return

    pet_list = ""
    for i, pet in enumerate(user["pets"], 1):
        pet_list += (
            f"{i}. {pet['name']} (ID: {pet['id']}) - Уровень {pet['level']}\n"
            f"   ⚔️ {pet['stats']['attack']} | 🛡️ {pet['stats']['defense']} | "
            f"❤️ {pet['stats']['health']} | ⚡ {pet['stats']['speed']}\n"
            f"   Приносит {pet['coin_rate']} монет/ч\n\n"
        )

    await update.message.reply_text(f"🙈 Твои питомцы:\n\n{pet_list}")

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim daily reward"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    current_time = time.time()
    last_daily = user.get("last_daily", 0)

    # Check if 20 hours have passed since last claim
    if last_daily and current_time - last_daily < 20 * 3600:
        hours_left = int((20 * 3600 - (current_time - last_daily)) / 3600) + 1
        await update.message.reply_text(f"🕰 Ты сможешь получить вознаграждение через {hours_left} ч.")
        return

    # Calculate streak
    streak = user.get("streak", 0)
    if last_daily and current_time - last_daily < 48 * 3600:  # If claimed within last 48 hours, continue streak
        streak += 1
    else:
        streak = 1  # Reset streak

    user["streak"] = streak
    user["last_daily"] = current_time

    # Calculate reward based on streak
    base_reward = 120
    streak_bonus = min(streak * 10, 3000)  # Cap streak bonus at 100
    total_reward = base_reward + streak_bonus

    user["coins"] += total_reward
    save_user(user)

    await update.message.reply_text(
        f"🎁 Вознаграждение получено! +{total_reward} монет\n"
        f"🔥 Текущий стрик: {streak} дн (+{streak_bonus} бонус)\n"
        f"💰 Твой баланс {user['coins']} монет."
    )

async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect coins from pets"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user.get("pets"):
        await update.message.reply_text("😶 У тебя нет питомцев, которые отдают дань.")
        return

    current_time = time.time()
    total_coins = 0

    for pet in user["pets"]:
        last_collected = pet.get("last_collected", 0)
        if last_collected is None:
            last_collected = 0

        # Calculate hours since last collection (max 24 hours to prevent massive accumulation)
        hours_passed = min(24, (current_time - last_collected) / 3600) if last_collected > 0 else 1

        if hours_passed >= 1:
            coins_earned = int(pet["coin_rate"] * hours_passed)
            total_coins += coins_earned
            pet["last_collected"] = current_time

    if total_coins > 0:
        user["coins"] += total_coins
        save_user(user)
        await update.message.reply_text(f"🐶 Ты собрал {total_coins} монет со своих питомцев! Твой баланс {user['coins']} монет.")
    else:
        await update.message.reply_text("😁 Не спеши - денег нет, но ты держись.")

async def merge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Merge pets to increase level"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user.get("pets") or len(user["pets"]) < 2:
        await update.message.reply_text("❗ Тебе нужно как минимум 2 питомца, чтобы скрестить их.")
        return

    # Display user's pets for merging
    pet_list = ""
    for i, pet in enumerate(user["pets"], 1):
        pet_list += f"{i}. {pet['name']} (ID: {pet['id']}) - Level {pet['level']}\n"

    await update.message.reply_text(
        f"➕ Для того, чтобы скрестить питомцев, укажи каких именно используя: /merge 1 2\n\n"
        f"🐵 Твои питомцы:\n{pet_list}"
    )

async def merge_pets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process pet merging"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not context.args or len(context.args) != 2:
        application.pending_merges[user_id] = True
        user_states[user_id] = "merge"
        await update.message.reply_text("❗ Укажи, пожалуйста, двух питомцев, то есть: /merge 1 2")
        return

    try:
        # Convert to zero-based indices
        pet1_idx = int(context.args[0]) - 1
        pet2_idx = int(context.args[1]) - 1

        if pet1_idx == pet2_idx:
            await update.message.reply_text("😡 Ты не можешь скрестить питомца с им же самим!")
            return

        pets = user["pets"]

        if pet1_idx < 0 or pet1_idx >= len(pets) or pet2_idx < 0 or pet2_idx >= len(pets):
            await update.message.reply_text("Некорректно введено число питомца.")
            return

        pet1 = pets[pet1_idx]
        pet2 = pets[pet2_idx]

        merge_cost = 140 + 20 * (pet1["level"] + pet2["level"])  # Merging is more expensive with higher level pets

        if user["coins"] < merge_cost:
            update.message.reply_text(f"😟 У тебя нет достаточно денег для скрещивания. Тебе надо {merge_cost} монет.")
            return

        # Check if pets are of the same type
        if pet1["type"] != pet2["type"]:
            await update.message.reply_text("‼ Ты можешь скрестить питомцев ТОЛЬКО одного вида.")
            return

        # Create the merged pet
        merged_pet = merge_pet_stats(pet1, pet2)

        # Remove the old pets
        if pet1_idx > pet2_idx:
            pets.pop(pet1_idx)
            pets.pop(pet2_idx)
        else:
            pets.pop(pet2_idx)
            pets.pop(pet1_idx)

        # Add the new merged pet
        pets.append(merged_pet)
        save_user(user)

        await update.message.reply_text(
            f"😎 Успешно скрещено питомца в {merged_pet['name']}!\n\n"
            f"⏫ Уровень: {merged_pet['level']}\n"
            f"Статистика: ⚔️ {merged_pet['stats']['attack']} | 🛡️ {merged_pet['stats']['defense']} | "
            f"❤️ {merged_pet['stats']['health']} | ⚡ {merged_pet['stats']['speed']}\n"
            f"😋 Монет приносит: {merged_pet['coin_rate']} монет/ч"
        )

        application.pending_merges.pop(user_id, None)
        user_states.pop(user_id, None)

    except ValueError:
        await update.message.reply_text("Введи дейвствительное число питомца.")

def merge_pet_stats(pet1, pet2):
    """Merge two pets' stats and potentially increase rarity"""
    # Determine which pet has higher level/rarity for base
    rarities_order = {r: i for i, r in enumerate(RARITIES)}

    # Use the higher level pet as the base
    base_pet = pet1 if pet1["level"] >= pet2["level"] else pet2
    other_pet = pet2 if base_pet == pet1 else pet1

    # Create a new pet based on the higher level one
    merged_pet = base_pet.copy()
    merged_pet["id"] = random.randint(10000, 99999)  # New ID

    # Increase level
    merged_pet["level"] = base_pet["level"] + 1

    # Merge stats (base + 50% of other pet's stats)
    for stat in ["attack", "defense", "health", "speed"]:
        bonus = other_pet["stats"][stat] * 0.5
        merged_pet["stats"][stat] = int(base_pet["stats"][stat] + bonus)

    # Chance to increase rarity based on combined levels
    combined_level = pet1["level"] + pet2["level"]
    rarity_chance = min(0.30 * combined_level, 0.60)  # Max 50% chance

    current_rarity_idx = rarities_order[base_pet["rarity"]]
    if current_rarity_idx < len(RARITIES) - 1 and random.random() < rarity_chance:
        new_rarity = RARITIES[current_rarity_idx + 1]
        merged_pet["rarity"] = new_rarity

        # Bonus stats from rarity increase
        rarity_mult = RARITY_MULTIPLIERS[new_rarity] / RARITY_MULTIPLIERS[base_pet["rarity"]]
        for stat in merged_pet["stats"]:
            merged_pet["stats"][stat] = int(merged_pet["stats"][stat] * rarity_mult)

    # Update name and coin rate
    merged_pet["name"] = f"{merged_pet['rarity']} {merged_pet['type']}"
    merged_pet["coin_rate"] = 1 + (RARITY_MULTIPLIERS[merged_pet["rarity"]] // 2)

    # Reset collection time
    merged_pet["last_collected"] = None

    return merged_pet

async def train_pet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process pet training"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    # Ensure the command has the correct number of arguments
    if not context.args or len(context.args) != 2:
        user_states[user_id] = "train"
        await update.message.reply_text("‼ Введи число питомца и что нужно прокачать, то есть: /train_pet 1 attack")
        return

    try:
        # Convert to zero-based index
        pet_idx = int(context.args[0]) - 1
        stat = context.args[1].lower()

        # Check if the stat is valid
        if stat not in ["attack", "defense", "health", "speed"]:
            await update.message.reply_text("😮 О чем ты?. Выбери одно из: attack, defense, health, speed.")
            return

        training_cost = 80 + 10 * user["pets"][pet_idx]["level"]  # Scaling cost based on pet level

        if user["coins"] < training_cost:
            await update.message.reply_text(f"⚠ Тебе надо {training_cost} монет для улучшения!")
            return

        pets = user["pets"]

        # Check if the pet index is valid
        if pet_idx < 0 or pet_idx >= len(pets):
            await update.message.reply_text("Неверное число питомца.")
            return

        pet = pets[pet_idx]

        # Increase the stat
        increase = 1 + (RARITY_MULTIPLIERS[pet["rarity"]] // 2)
        old_value = pet["stats"][stat]

        if stat == "health":
            pet["stats"][stat] += increase * 2  # Health increases more
        else:
            pet["stats"][stat] += increase

        # Deduct coins for the training
        user["coins"] -= training_cost
        save_user(user)

        # Send feedback to the user
        await update.message.reply_text(
            f"🎉 Лвл {pet['name']} {stat} поднят!\n"
            f"{stat.capitalize()}: {old_value} → {pet['stats'][stat]} (+{pet['stats'][stat] - old_value})\n"
            f"💲 Теперь твой баланс {user['coins']} монет."
        )

        user_states.pop(user_id, None)

    except ValueError:
        await update.message.reply_text("Введи действительное число.")

async def trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Напиши: /trade <user_id>")
        return

    partner_id = context.args[0]
    user_id = str(update.effective_user.id)

    if user_id == partner_id:
        await update.message.reply_text("Ты не можешь торговать сам с собой.")
        return

    partner = get_user(partner_id)
    if not partner:
        await update.message.reply_text("Такой пользователь не найден.")
        return

    user_pets = get_user(user_id).get("pets", [])
    if not user_pets:
        await update.message.reply_text("У тебя нет питомцев для обмена.")
        return

    # Выбор питомца
    keyboard = []
    for i, pet in enumerate(user_pets):
        keyboard.append([
            InlineKeyboardButton(f"{pet['name']} ({pet['rarity']})", callback_data=f"offer_{partner_id}_{i}")
        ])

    await update.message.reply_text(
        f"Выбери питомца, которого ты хочешь предложить @{partner_id}:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def offer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    _, partner_id, pet_index = query.data.split("_")
    pet_index = int(pet_index)

    user_data = get_user(user_id)
    if pet_index >= len(user_data.get("pets", [])):
        await query.edit_message_text("Неверный выбор питомца.")
        return

    active_trades[user_id] = {
        "partner": partner_id,
        "offer": pet_index,
        "status": "waiting"
    }

    await query.edit_message_text("Предложение отправлено. Ожидаем ответа второго игрока.")

    # Уведомим второго игрока
    partner_data = get_user(partner_id)
    offered_pet = user_data["pets"][pet_index]
    await context.bot.send_message(
        chat_id=int(partner_id),
        text=f"Тебе предложили обмен: {offered_pet['name']} ({offered_pet['rarity']}). Хочешь предложить ответного питомца?\nНапиши /respond {user_id}"
    )

async def respond_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Напиши: /respond <user_id>")
        return

    proposer_id = context.args[0]
    user_id = str(update.effective_user.id)

    if proposer_id not in active_trades:
        await update.message.reply_text("Нет активного предложения от этого пользователя.")
        return

    # Выбор ответного питомца
    user_pets = get_user(user_id).get("pets", [])
    if not user_pets:
        await update.message.reply_text("У тебя нет питомцев для обмена.")
        return

    keyboard = []
    for i, pet in enumerate(user_pets):
        keyboard.append([
            InlineKeyboardButton(f"{pet['name']} ({pet['rarity']})", callback_data=f"respond_{proposer_id}_{i}")
        ])

    await update.message.reply_text(
        f"Выбери, какого питомца ты отдашь в обмен:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def respond_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    _, proposer_id, pet_index = query.data.split("_")
    pet_index = int(pet_index)

    if proposer_id not in active_trades:
        await query.edit_message_text("Предложение устарело.")
        return

    # Данные обеих сторон
    proposer_data = get_user(proposer_id)
    responder_data = get_user(user_id)
    trade = active_trades[proposer_id]

    # Проверки
    if trade["partner"] != user_id:
        await query.edit_message_text("Это не твой трейд.")
        return

    # Обмен
    proposer_pet = proposer_data["pets"].pop(trade["offer"])
    responder_pet = responder_data["pets"].pop(pet_index)

    proposer_data["pets"].append(responder_pet)
    responder_data["pets"].append(proposer_pet)

    save_user(proposer_data)
    save_user(responder_data)
    del active_trades[proposer_id]

    # Подтверждения
    await query.edit_message_text("🎉 Обмен успешно завершён! Питомцы поменялись.")
    await context.bot.send_message(chat_id=int(proposer_id), text="🎉 Пользователь согласился! Питомцы обменяны.")

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"Твій Telegram ID: `{user_id}`", parse_mode=ParseMode.MARKDOWN)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    user_states.pop(user_id, None)
    active_trades.pop(user_id, None)

    if hasattr(context.application, "pending_merges"):
        context.application.pending_merges.pop(user_id, None)

    await update.message.reply_text("⚠ Отмена всех инструкций.")

async def fallback_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    state = user_states.get(user_id)

    if not state:
        return

    if state == "merge":
        await update.message.reply_text("❗ Введите номера двух питомцев, например: /merge 1 2 или напишите /cancel")
    elif state == "train":
        await update.message.reply_text("❗ Введите номер питомца и аргумент прокачки: /train 1 attack или напишите /cancel")
    else:
        await update.message.reply_text("🤐 Я не понял. Воспользуйся командами или напиши /help.")

# Main launcher
if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.pending_merges = {}
    keep_alive()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("buy_egg", buy_egg))
    application.add_handler(CommandHandler("hatch", hatch))
    application.add_handler(CommandHandler("pets", pets))
    application.add_handler(CommandHandler("daily", daily))
    application.add_handler(CommandHandler("collect", collect))
    application.add_handler(CommandHandler("merge", merge_pets))
    application.add_handler(CommandHandler("train", train_pet))
    application.add_handler(CommandHandler("trade", trade_command))
    application.add_handler(CommandHandler("respond", respond_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("profile", profile))
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), fallback_message))
    application.add_handler(CallbackQueryHandler(offer_callback, pattern=r"^offer_"))
    application.add_handler(CallbackQueryHandler(respond_callback, pattern=r"^respond_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, merge_pets))
    application.add_handler(CallbackQueryHandler(hatch_callback, pattern="^hatch_"))
    application.add_handler(CallbackQueryHandler(buy_egg_callback, pattern="^buy_"))

    application.run_polling()
