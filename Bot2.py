import discord
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, ConversationHandler, MessageHandler, Filters
import asyncio
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Токены и настройки
DISCORD_TOKEN = os.getenv("MTMzODkxMjg1MzU3MDM1NTI0MA.Geegu_.4l83_oK9kKxwAHDdUZyrbwno7gT2WbEevVXhfc")
TELEGRAM_TOKEN = os.getenv("T7831688575:AAFLq01R57y0iFkDABmO8va9FKYeuLOeB4k")
DISCORD_SERVER_ID = int(os.getenv("1317856700828483604"))
DISCORD_CLIENT_ID = os.getenv("1338912853570355240")
DISCORD_CLIENT_SECRET = os.getenv("1LaUj6hHQ1nwcFm30tMIqMvdBPr7U1Ba")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

# Инициализация Discord-клиента
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.presences = True
discord_client = discord.Client(intents=intents)

# Хранилище для времени входа в голосовой канал
voice_time = {}
# Хранилище для времени в голосовых каналах (часы)
voice_hours = {}
# Хранилище для времени в играх (часы)
game_hours = {}
# Хранилище для времени начала игры
game_start_time = {}
# Хранилище для подписчиков на уведомления
notifications = set()
# Хранилище для пользователей, которые уже согласились с правилами
agreed_users = set()
# Хранилище для связанных аккаунтов
linked_accounts = {}

# Состояния для диалога авторизации
AUTHORIZE, LINK_ACCOUNT = range(2)

# Событие при изменении голосового статуса
@discord_client.event
async def on_voice_state_update(member, before, after):
    now = datetime.now()
    # Пользователь зашел в канал
    if after.channel and (before.channel != after.channel):
        voice_time[member.id] = now
        # Отправляем уведомления подписчикам
        if notifications:
            message = f"🔊 {member.display_name} зашел в голосовой канал {after.channel.name}."
            for chat_id in notifications:
                await send_telegram_message(chat_id, message)
    # Пользователь вышел из канала
    elif before.channel and not after.channel:
        entry_time = voice_time.get(member.id)
        if entry_time:
            delta = now - entry_time
            hours = delta.total_seconds() / 3600
            voice_hours[member.id] = voice_hours.get(member.id, 0) + hours
            voice_time.pop(member.id, None)

# Событие при изменении активности (игры)
@discord_client.event
async def on_member_update(before, after):
    now = datetime.now()
    for activity in after.activities:
        if activity.type == discord.ActivityType.playing:
            if not any(a.type == discord.ActivityType.playing for a in before.activities):
                game_start_time[after.id] = now
                game_hours[after.id] = game_hours.get(after.id, 0)
            break
    else:
        for activity in before.activities:
            if activity.type == discord.ActivityType.playing:
                game_end_time = now
                game_duration = game_end_time - game_start_time.get(after.id, now)
                game_hours[after.id] += game_duration.total_seconds() / 3600
                game_start_time.pop(after.id, None)
                break

# Функция для получения информации о голосовых каналах
async def get_voice_channels_info(guild_id):
    guild = discord_client.get_guild(guild_id)
    if not guild:
        return None
    channels_info = []
    for channel in guild.voice_channels:
        members = channel.members
        if members:
            members_data = []
            for member in members:
                entry_time = voice_time.get(member.id)
                duration = "Неизвестно"
                if entry_time:
                    delta = datetime.now() - entry_time
                    hours, remainder = divmod(delta.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    duration = f"{hours}ч {minutes}м"
                members_data.append({
                    "name": member.display_name,
                    "duration": duration
                })
            channels_info.append({
                "name": channel.name,
                "members": members_data
            })
    return channels_info

# Функция для получения информации об играх
async def get_games_info(guild_id):
    guild = discord_client.get_guild(guild_id)
    if not guild:
        return None
    games = {}
    for member in guild.members:
        for activity in member.activities:
            if activity.type == discord.ActivityType.playing:
                game_name = activity.name
                games[game_name] = games.get(game_name, 0) + 1
    return games

# Функция для получения информации об участниках
async def get_members_info(guild_id):
    guild = discord_client.get_guild(guild_id)
    if not guild:
        return None
    members_info = []
    for member in guild.members:
        members_info.append({
            "name": member.display_name,
            "joined_at": member.joined_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    return members_info

# Функция для получения информации о профиле пользователя
async def get_user_profile(user_id, guild_id):
    guild = discord_client.get_guild(guild_id)
    if not guild:
        return None
    member = guild.get_member(user_id)
    if not member:
        return None
    joined_at = member.joined_at.strftime("%Y-%m-%d %H:%M:%S")
    voice_hrs = round(voice_hours.get(user_id, 0), 2)
    game_hrs = round(game_hours.get(user_id, 0), 2)
    profile_info = {
        "name": member.display_name,
        "joined_at": joined_at,
        "voice_hours": voice_hrs,
        "game_hours": game_hrs
    }
    return profile_info

# Функция для отправки сообщений в Telegram
async def send_telegram_message(chat_id, text, parse_mode=None):
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    bot = updater.bot
    await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)

# Команда /start для Telegram
def start(update: Update, context: CallbackContext):
    if update.message.chat_id in agreed_users:
        main_menu(update, context)
    else:
        rules_text = """
        📜 *Правила сервера:*
        - Не оскорбляйте друг друга.
        - Уважайте других участников.
        - Не материтесь в чатах.
        - Не распространяйте неприемлемый контент.
        
        Нажмите кнопку ниже, чтобы подтвердить, что вы согласны с правилами.
        """
        keyboard = [[InlineKeyboardButton("Согласен", callback_data='agree')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(rules_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# Главное меню после согласия с правилами
def main_menu(update: Update, context: CallbackContext):
    welcome_text = """
    🎮 *Добро пожаловать в бота Discord-сервера!* 🎮
    Здесь вы можете:
    - Узнать, кто сейчас в голосовых каналах
    - Посмотреть, в какие игры играют участники
    - Получить список участников сервера
    - Включить уведомления о входе в голосовые каналы
    - Узнать свой профиль (необязательно)
    - Получить ссылки на группы и сайты
    """
    update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

    keyboard = [
        [InlineKeyboardButton("Состояние Голосового Канала", callback_data='voice')],
        [InlineKeyboardButton("Игры", callback_data='games')],
        [InlineKeyboardButton("Участники", callback_data='members')],
        [InlineKeyboardButton("Уведомления", callback_data='notifications')],
        [InlineKeyboardButton("Профиль", callback_data='profile')],
        [InlineKeyboardButton("Ссылки", callback_data='links')],
        [InlineKeyboardButton("Авторизация через Discord", callback_data='authorize')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Что вас интересует?", reply_markup=reply_markup)

# Обработчик кнопок
def button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    async def handle_request():
        if query.data == 'agree':
            agreed_users.add(query.message.chat_id)
            query.edit_message_text(text="Вы успешно согласились с правилами. Теперь вы можете использовать бота.")
            main_menu(update, context)
        elif query.data in ['voice', 'games', 'members', 'notifications', 'profile', 'links', 'authorize']:
            if query.message.chat_id not in agreed_users:
                query.edit_message_text(text="Пожалуйста, сначала согласитесь с правилами.")
                return

            if query.data == 'voice':
                channels_info = await get_voice_channels_info(DISCORD_SERVER_ID)
                response = "**Голосовые каналы:**\n\n"
                for channel in channels_info:
                    response += f"🔊 **{channel['name']}**\n"
                    response += f"👥 Участников: {len(channel['members'])}\n"
                    for member in channel['members']:
                        response += f"— {member['name']} — в канале {member['duration']}\n"
                    response += "\n"
                query.edit_message_text(text=response, parse_mode=ParseMode.MARKDOWN)

            elif query.data == 'games':
                games_info = await get_games_info(DISCORD_SERVER_ID)
                response = "**Игры на сервере:**\n\n"
                for game, count in games_info.items():
                    response += f"🎮 {game}: {count} игроков\n"
                query.edit_message_text(text=response, parse_mode=ParseMode.MARKDOWN)

            elif query.data == 'members':
                members_info = await get_members_info(DISCORD_SERVER_ID)
                response = "**Участники сервера:**\n\n"
                for member in members_info:
                    response += f"👤 {member['name']} — присоединился {member['joined_at']}\n"
                query.edit_message_text(text=response, parse_mode=ParseMode.MARKDOWN)

            elif query.data == 'notifications':
                keyboard = [
                    [InlineKeyboardButton("Включить уведомления", callback_data='enable_notifications')],
                    [InlineKeyboardButton("Отключить уведомления", callback_data='disable_notifications')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                query.edit_message_text(text="Управление уведомлениями:", reply_markup=reply_markup)

            elif query.data == 'enable_notifications':
                notifications.add(query.message.chat_id)
                query.edit_message_text(text="✅ Уведомления включены.")

            elif query.data == 'disable_notifications':
                notifications.discard(query.message.chat_id)
                query.edit_message_text(text="❌ Уведомления отключены.")

            elif query.data == 'profile':
                user_id = query.from_user.id
                if user_id not in linked_accounts:
                    query.edit_message_text(text="Вы ещё не связали свой аккаунт Discord. Хотите это сделать?")
                    keyboard = [
                        [InlineKeyboardButton("Авторизоваться через Discord", callback_data='authorize')],
                        [InlineKeyboardButton("Отмена", callback_data='cancel')]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    query.edit_message_text(text="Выберите действие:", reply_markup=reply_markup)
                    return
                discord_user_id = linked_accounts[user_id]
                profile_info = await get_user_profile(discord_user_id, DISCORD_SERVER_ID)
                if not profile_info:
                    query.edit_message_text(text="Не удалось получить информацию о профиле.")
                    return
                response = f"""
                **Профиль пользователя: {profile_info['name']}**

                - Дата присоединения: {profile_info['joined_at']}
                - Время в голосовых каналах: {profile_info['voice_hours']} часов
                - Время в играх: {profile_info['game_hours']} часов
                """
                query.edit_message_text(text=response, parse_mode=ParseMode.MARKDOWN)

            elif query.data == 'links':
                keyboard = [
                    [InlineKeyboardButton("Телеграм группа", url="https://t.me/gamecommunityuzb")],
                    [InlineKeyboardButton("Discord сервер", url="https://discord.gg/aqCKCXEB8V")],
                    [InlineKeyboardButton("Сайт сервера", callback_data='website')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                query.edit_message_text(text="Выберите ссылку:", reply_markup=reply_markup)

            elif query.data == 'website':
                query.edit_message_text(text="Скоро...")

            elif query.data == 'authorize':
                auth_url = (
                    f"https://discord.com/api/oauth2/authorize?"
                    f"client_id={DISCORD_CLIENT_ID}&"
                    f"redirect_uri={DISCORD_REDIRECT_URI}&"
                    f"response_type=code&"
                    f"scope=identify%20guilds.join&"
                    f"state={query.from_user.id}"  # Передача Telegram user_id в state
                )
                keyboard = [[InlineKeyboardButton("Авторизоваться", url=auth_url)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                query.edit_message_text(text="Перейдите по ссылке для авторизации:", reply_markup=reply_markup)

            elif query.data == 'cancel':
                query.edit_message_text(text="Действие отменено.")
                main_menu(update, context)

    asyncio.run(handle_request())

# Обработчик кода авторизации
def handle_auth_code(update: Update, context: CallbackContext):
    code = update.message.text
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "scope": "identify guilds.join"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    if response.status_code != 200:
        update.message.reply_text("Ошибка при авторизации. Попробуйте снова.")
        return ConversationHandler.END
    tokens = response.json()
    access_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    user_response = requests.get("https://discord.com/api/users/@me", headers=headers)
    if user_response.status_code != 200:
        update.message.reply_text("Ошибка при получении информации о пользователе. Попробуйте снова.")
        return ConversationHandler.END
    user_info = user_response.json()
    discord_user_id = user_info["id"]
    telegram_user_id = update.message.from_user.id
    linked_accounts[telegram_user_id] = discord_user_id
    update.message.reply_text("Аккаунты успешно связаны!")
    return ConversationHandler.END

# Отмена диалога авторизации
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Авторизация отменена.")
    return ConversationHandler.END

# Запуск ботов
def run_bots():
    # Запускаем Discord-бота в отдельном потоке
    import threading
    discord_thread = threading.Thread(target=discord_client.run, args=(DISCORD_TOKEN,))
    discord_thread.start()

    # Запускаем Telegram-бота
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_click))
    dp.add_handler(
        ConversationHandler(
            entry_points=[CallbackQueryHandler(authorize, pattern='^authorize$')],
            states={
                AUTHORIZE: [MessageHandler(Filters.text & ~Filters.command, handle_auth_code)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
    )
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    run_bots()