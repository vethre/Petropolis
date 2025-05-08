# main.py (refactored for latest python-telegram-bot v20+)

import os
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
from telegram.ext import CallbackContext
from keep_alive import keep_alive

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


TOKEN=os.getenv("TOKEN")

# Constants
PET_TYPES = ["Огненный", "Водный", "Земляной", "Воздушный", "Светлый", "Тёмный"]
RARITIES = ["Обычный", "Необычный", "Редкостный", "Эпический", "Легендарный", "Мифический"]
RARITY_CHANCES = {
    "Обычный": 0.50,
    "Необычный": 0.30,
    "Редкостный": 0.15,
    "Эпический": 0.04,
    "Легендарный": 0.009,
    "Мифический": 0.001,
}
RARITY_MULTIPLIERS = {
    "Обычный": 2,
    "Необычный": 4,
    "Редкостный": 6,
    "Эпический": 8,
    "Легендарный": 12,
    "Мифический": 22,
}
EGG_PRICES = {
    "Базовое": 250,
    "Премиальное": 600,
    "Редкостное": 1350,
}
EGG_RARITY_BOOSTS = {
    "Базовое": 0,
    "Премиальное": 0.10,
    "Редкостное": 0.25,
}

# File to store user data
DATA_FILE = "user_data.json"

# Functions to load and save data
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

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
    base_stats = random.randint(5, 13) * multiplier
    return {
        "id": random.randint(10000, 99999),
        "name": f"{rarity} {pet_type}",
        "type": pet_type,
        "rarity": rarity,
        "level": 1,
        "xp": 0,
        "xp_needed": 100,
        "stats": {
            "attack": base_stats + random.randint(-1, 4),
            "defense": base_stats + random.randint(1, 5),
            "health": base_stats * 2 + random.randint(5, 7),
            "speed": base_stats + random.randint(1, 8),
        },
        "coin_rate": 20 + (RARITY_MULTIPLIERS[rarity] // 2),
        "last_collected": None,
    }

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = initialize_user(user_id)
        save_data(data)
        await update.message.reply_text("👋 Добро пожаловать в Петрополис! ВЫ получили 450 монет! Напиши /help_command для большей информации!")
    else:
        await update.message.reply_text(f"👋 Привет опять! У тебя {data[user_id]['coins']} монет. Напиши /help_command для большей информации!")

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
        "/balance - Посмотреть свой баланс\n\n"
        "🔄 <b>Прогресс</b>\n"
        "/merge (цифра первого питомца) (цифра второго) - Скрестить питомцев воедино\n"
        "/train (цифра питомца по счету) (качество) - Тренировать питомца\n\n"
        "⚔️ <b>Бой - в разработке</b>\n"
        "/battle - Сражаться с другими\n"
        "/leaderboard - Лидеры\n\n"
        "🤝 <b>Трэйдинг - в разработке</b>\n"
        "/trade - Обмен питомцами"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)



async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = initialize_user(user_id)
        save_data(data)
    await update.message.reply_text(f"У тебя {data[user_id]['coins']} монет.")

async def buy_egg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"🥚 Базовое - {EGG_PRICES['Basic']} монет", callback_data="buy_Basic"),
         InlineKeyboardButton(f"💠 Премиальное - {EGG_PRICES['Premium']} монет", callback_data="buy_Premium")],
        [InlineKeyboardButton(f"🌟 Редкостное - {EGG_PRICES['Rare']} монет", callback_data="buy_Rare")],
    ]
    await update.message.reply_text("🎰 Выбери, какое яйцо купишь:", reply_markup=InlineKeyboardMarkup(keyboard))

async def buy_egg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    egg_type = query.data.split("_")[1]
    data = load_data()
    if user_id not in data:
        data[user_id] = initialize_user(user_id)

    if data[user_id]["coins"] < EGG_PRICES[egg_type]:
        await query.edit_message_text(f"💸 Недостаточно средств для покупки яйца типа *{egg_type}*.")
        return

    if "eggs" not in data[user_id]:
        data[user_id]["eggs"] = {}
    if egg_type not in data[user_id]["eggs"]:
        data[user_id]["eggs"][egg_type] = 0

    data[user_id]["eggs"][egg_type] += 1
    data[user_id]["coins"] -= EGG_PRICES[egg_type]
    save_data(data)

    await query.edit_message_text(f"🐣 Ты приобрел {egg_type} яйцо за {EGG_PRICES[egg_type]} монет!\nНапиши /hatch, чтобы раскрыть его.")



async def hatch(update: Update, context: CallbackContext):
    """Display available eggs to hatch"""
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        data[user_id] = initialize_user(user_id)
        save_data(data)
        await update.message.reply_text("🥚 У тебя нет яиц для раскрывания. Купи используя комманду /buy_egg!")
        return

    if "eggs" not in data[user_id] or not data[user_id]["eggs"]:
        await update.message.reply_text("🥚 У тебя нет яиц для раскрывания. Купи используя /buy_egg!")
        return

    keyboard = []
    for egg_type, count in data[user_id]["eggs"].items():
        if count > 0:
            keyboard.append([InlineKeyboardButton(f"{egg_type} яйцо ({count})", callback_data=f"hatch_{egg_type}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🥚 Выбери яйцо для раскрытия:", reply_markup=reply_markup)

async def hatch_callback(update: Update, context: CallbackContext):
    """Process egg hatching"""
    query = update.callback_query
    await query.answer()  # Await the answer to the callback query
    
    user_id = str(query.from_user.id)
    egg_type = query.data.split("_")[1]

    data = load_data()

    # Check if user data exists
    if user_id not in data or "eggs" not in data[user_id]:
        await query.edit_message_text("У тебя нет яиц для раскрытия.")
        return

    if egg_type not in data[user_id]["eggs"] or data[user_id]["eggs"][egg_type] <= 0:
        await query.edit_message_text(f"😔 У тебя нет яиц типа *{egg_type}* для раскрытия.")
        return

    pet = generate_random_pet(rarity_boost=EGG_RARITY_BOOSTS[egg_type])
    data[user_id]["eggs"][egg_type] -= 1

    # Initialize "pets" list if not already present
    if "pets" not in data[user_id]:
        data[user_id]["pets"] = []

    data[user_id]["pets"].append(pet)
    save_data(data)

    # Send a message with the pet's details
    await query.edit_message_text(
        f"🥚 Из яйца типа {egg_type} вылупился {pet['rarity']} {pet['type']} питомец!\n\n"
        f"🆔 ID: {pet['id']}\n"
        f"⚔️ Атака: {pet['stats']['attack']}\n"
        f"🛡️ Защита: {pet['stats']['defense']}\n"
        f"❤️ Здоровье: {pet['stats']['health']}\n"
        f"⚡ Скорость: {pet['stats']['speed']}\n\n"
        f"Этот питомец приносит {pet['coin_rate']} монет в час."
    )

async def pets(update: Update, context: CallbackContext):
    """Display user's pets"""
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data:
        data[user_id] = initialize_user(user_id)
        save_data(data)
        await update.message.reply_text("У тебя пока нет питомцев. Купи и вскрой яйцо сначала!")
        return
    
    if "pets" not in data[user_id] or not data[user_id]["pets"]:
        await update.message.reply_text("У тебя пока нет питомцев. Купи и вскрой яйцо сначала!")
        return
    
    pet_list = ""
    for i, pet in enumerate(data[user_id]["pets"], 1):
        pet_list += (
            f"{i}. {pet['name']} (ID: {pet['id']}) - Уровень {pet['level']}\n"
            f"   ⚔️ {pet['stats']['attack']} | 🛡️ {pet['stats']['defense']} | "
            f"❤️ {pet['stats']['health']} | ⚡ {pet['stats']['speed']}\n"
            f"   Приносит {pet['coin_rate']} монет/ч\n\n"
        )
    
    await update.message.reply_text(f"🙈 Твои питомцы:\n\n{pet_list}")

async def daily(update: Update, context: CallbackContext):
    """Claim daily reward"""
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data:
        data[user_id] = initialize_user(user_id)
    
    current_time = time.time()
    last_daily = data[user_id].get("last_daily", 0)
    
    # Check if 20 hours have passed since last claim
    if last_daily and current_time - last_daily < 20 * 3600:
        hours_left = int((20 * 3600 - (current_time - last_daily)) / 3600) + 1
        await update.message.reply_text(f"🕰 Ты сможешь получить вознаграждение через {hours_left} ч.")
        return
    
    # Calculate streak
    streak = data[user_id].get("streak", 0)
    if last_daily and current_time - last_daily < 48 * 3600:  # If claimed within last 48 hours, continue streak
        streak += 1
    else:
        streak = 1  # Reset streak
    
    data[user_id]["streak"] = streak
    data[user_id]["last_daily"] = current_time
    
    # Calculate reward based on streak
    base_reward = 100
    streak_bonus = min(streak * 10, 100)  # Cap streak bonus at 100
    total_reward = base_reward + streak_bonus
    
    data[user_id]["coins"] += total_reward
    save_data(data)
    
    await update.message.reply_text(
        f"🎁 Вознаграждение получено! +{total_reward} монет\n"
        f"🔥 Текущий стрик: {streak} дн (+{streak_bonus} бонус)\n"
        f"💰 Твой баланс {data[user_id]['coins']} монет."
    )

async def collect(update: Update, context: CallbackContext):
    """Collect coins from pets"""
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data:
        data[user_id] = initialize_user(user_id)
        save_data(data)
        await update.message.reply_text("😶 У тебя нет питомцев, которые отдают дань.")
        return
    
    if "pets" not in data[user_id] or not data[user_id]["pets"]:
        await update.message.reply_text("😶 У тебя нет питомцев, которые отдают дань.")
        return
    
    current_time = time.time()
    total_coins = 0
    
    for pet in data[user_id]["pets"]:
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
        data[user_id]["coins"] += total_coins
        save_data(data)
        await update.message.reply_text(f"🐶 Ты собрал {total_coins} монет со своих питомцев! Твой баланс {data[user_id]['coins']} монет.")
    else:
        await update.message.reply_text("😁 Не спеши - денег нет, но ты держись.")

async def merge(update: Update, context: CallbackContext):
    """Merge pets to increase level"""
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data:
        data[user_id] = initialize_user(user_id)
        save_data(data)
        await update.message.reply_text("У тебя нет питомцев для слияния.")
        return
    
    if "pets" not in data[user_id] or len(data[user_id]["pets"]) < 2:
        await update.message.reply_text("Тебе нужно как минимум 2 питомца, чтобы скрестить их.")
        return
    
    # Display user's pets for merging
    pet_list = ""
    for i, pet in enumerate(data[user_id]["pets"], 1):
        pet_list += f"{i}. {pet['name']} (ID: {pet['id']}) - Level {pet['level']}\n"
    
    await update.message.reply_text(
        f"➕ Для того, чтобы скрестить питомцев, укажи каких именно используя: /merge 1 2\n\n"
        f"🐵 Твои питомцы:\n{pet_list}"
    )

async def merge_pets(update: Update, context: CallbackContext):
    """Process pet merging"""
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if not context.args or len(context.args) != 2:
        await update.message.reply_text("❗ Укажи, пожалуйста, двух питомцев, то есть: /merge 1 2")
        return
    
    try:
        # Convert to zero-based indices
        pet1_idx = int(context.args[0]) - 1
        pet2_idx = int(context.args[1]) - 1
        
        if pet1_idx == pet2_idx:
            await update.message.reply_text("😡 Ты не можешь скрестить питомца с им же самим!")
            return
            
        pets = data[user_id]["pets"]
        
        if pet1_idx < 0 or pet1_idx >= len(pets) or pet2_idx < 0 or pet2_idx >= len(pets):
            await update.message.reply_text("Некорректно введено число питомца.")
            return
        
        pet1 = pets[pet1_idx]
        pet2 = pets[pet2_idx]
        
        merge_cost = 140 + 20 * (pet1["level"] + pet2["level"])  # Merging is more expensive with higher level pets
    
        if data[user_id]["coins"] < merge_cost:
            update.message.reply_text(f"У тебя нет достаточно денег для скрещивания. Тебе надо {merge_cost} монет.")
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
        save_data(data)
        
        await update.message.reply_text(
            f"😎 Успешно скрещено питомца в {merged_pet['name']}!\n\n"
            f"⏫ Уровень: {merged_pet['level']}\n"
            f"Статистика: ⚔️ {merged_pet['stats']['attack']} | 🛡️ {merged_pet['stats']['defense']} | "
            f"❤️ {merged_pet['stats']['health']} | ⚡ {merged_pet['stats']['speed']}\n"
            f"😋 Монет приносит: {merged_pet['coin_rate']} монет/ч"
        )
        
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
    rarity_chance = min(0.15 * combined_level, 0.55)  # Max 50% chance
    
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

async def train_pet(update: Update, context: CallbackContext):
    """Process pet training"""
    user_id = str(update.effective_user.id)
    data = load_data()

    # Ensure the command has the correct number of arguments
    if not context.args or len(context.args) != 2:
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

        training_cost = 80 + 10 * data[user_id]["pets"][pet_idx]["level"]  # Scaling cost based on pet level
        
        if data[user_id]["coins"] < training_cost:
            await update.message.reply_text(f"⚠ Тебе надо {training_cost} монет для улучшения!")
            return
        
        pets = data[user_id]["pets"]
        
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
        data[user_id]["coins"] -= 100
        save_data(data)
        
        # Send feedback to the user
        await update.message.reply_text(
            f"🎉 Лвл {pet['name']} {stat} поднят!\n"
            f"{stat.capitalize()}: {old_value} → {pet['stats'][stat]} (+{pet['stats'][stat] - old_value})\n"
            f"💲 Теперь твой баланс {data[user_id]['coins']} монет."
        )
    
    except ValueError:
        await update.message.reply_text("Введи действительное число.")


# Main launcher
if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
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
    application.add_handler(CommandHandler("train_pet", train_pet))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, merge_pets))
    application.add_handler(CallbackQueryHandler(hatch_callback, pattern="^hatch_"))
    application.add_handler(CallbackQueryHandler(buy_egg_callback, pattern="^buy_"))

    application.run_polling()
