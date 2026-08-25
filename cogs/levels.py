"""
Модуль системы уровней/активности сервера.
Отслеживает три метрики по каждому участнику:
  - XP / уровень — начисляется за сообщения (с кулдауном)
  - время в войсе — накапливается, пока участник сидит в голосовом канале
  - печеньки — начисляются автору сообщения, когда кто-то ставит реакцию 🍪

Все данные хранятся в levels_data.json (создаётся автоматически).
Совет: если решишь перенести старые уровни с другого бота (например, Juniper) —
пришли мне список участников с их XP/уровнем, и я напишу отдельный скрипт
для одноразового импорта в этот файл.
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import io
import time
import random
from PIL import Image, ImageDraw, ImageFont, ImageOps

DATA_FILE = "levels_data.json"

# Пути к шрифтам, которые бот попробует найти по очереди (Windows/macOS/Linux).
# Если ни один не найдётся, будет использован стандартный шрифт Pillow (менее красивый, но рабочий).
FONT_PATHS_BOLD = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_PATHS_REGULAR = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(paths, size):
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

XP_PER_MESSAGE = (5, 15)      # случайный диапазон XP за одно засчитанное сообщение
MESSAGE_COOLDOWN_SECONDS = 60  # не чаще одного начисления XP в минуту с человека
COOKIE_EMOJI = "🍪"             # эмодзи, которое считается "печенькой"
ALLOW_SELF_COOKIE = False      # можно ли поставить печеньку самому себе


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_user(data, user_id: str, name: str):
    data.setdefault(user_id, {"name": name, "xp": 0, "voice_seconds": 0, "cookies": 0})
    data[user_id]["name"] = name
    return data[user_id]


def xp_to_level(xp: int) -> int:
    level = 0
    while xp >= (level + 1) ** 2 * 50:
        level += 1
    return level


def format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours:
        return f"{hours} ч {minutes} мин"
    return f"{minutes} мин"


async def generate_profile_card(member: discord.Member, user_data: dict) -> io.BytesIO:
    """Рисует карточку профиля картинкой (уровень, XP-полоска, войс, печеньки)."""
    W, H = 900, 300
    bg_color = (35, 39, 62)
    accent_color = (114, 137, 218)  # фирменный "дискордовский" синий/фиолетовый
    bar_bg_color = (60, 64, 90)
    text_color = (255, 255, 255)
    muted_color = (170, 175, 200)

    card = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(card)

    # --- Аватарка (круглая, слева) ---
    avatar_size = 180
    avatar_bytes = await member.display_avatar.replace(size=256).read()
    avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((avatar_size, avatar_size))
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
    avatar_pos = (60, (H - avatar_size) // 2)
    card.paste(avatar_img, avatar_pos, mask)
    # Обводка вокруг аватарки
    draw.ellipse(
        [avatar_pos[0] - 4, avatar_pos[1] - 4, avatar_pos[0] + avatar_size + 4, avatar_pos[1] + avatar_size + 4],
        outline=accent_color, width=4,
    )

    # --- Шрифты ---
    font_name = _load_font(FONT_PATHS_BOLD, 40)
    font_label = _load_font(FONT_PATHS_REGULAR, 24)
    font_stat = _load_font(FONT_PATHS_BOLD, 28)

    text_x = avatar_pos[0] + avatar_size + 40

    # --- Имя ---
    draw.text((text_x, 40), member.display_name, font=font_name, fill=text_color)

    # --- Уровень (справа сверху) ---
    xp = user_data.get("xp", 0)
    level = xp_to_level(xp)
    level_text = f"Уровень {level}"
    lw = draw.textlength(level_text, font=font_stat)
    draw.text((W - 60 - lw, 40), level_text, font=font_stat, fill=accent_color)

    # --- Полоска прогресса XP ---
    bar_x, bar_y, bar_w, bar_h = text_x, 110, W - text_x - 60, 28
    current_base = 50 * level ** 2
    next_base = 50 * (level + 1) ** 2
    progress = 0.0
    if next_base > current_base:
        progress = max(0.0, min(1.0, (xp - current_base) / (next_base - current_base)))

    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=bar_h // 2, fill=bar_bg_color)
    if progress > 0:
        filled_w = int(bar_w * progress)
        filled_w = max(filled_w, bar_h) if progress > 0 else 0  # не даём полоске "обрезаться" в кружок
        draw.rounded_rectangle([bar_x, bar_y, bar_x + filled_w, bar_y + bar_h], radius=bar_h // 2, fill=accent_color)

    xp_text = f"{xp} / {next_base} XP"
    draw.text((bar_x, bar_y + bar_h + 8), xp_text, font=font_label, fill=muted_color)

    # --- Войс и печеньки ---
    stats_y = 200
    voice_text = f"🎙️ {format_duration(user_data.get('voice_seconds', 0))}"
    cookies_text = f"🍪 {user_data.get('cookies', 0)}"
    draw.text((text_x, stats_y), voice_text, font=font_stat, fill=text_color)
    draw.text((text_x + 260, stats_y), cookies_text, font=font_stat, fill=text_color)

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_cooldowns = {}
        self.voice_join_times = {}  # {user_id: timestamp когда зашёл в войс}

    # ---------- XP за сообщения ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        now = time.time()
        user_id = str(message.author.id)
        last = self.message_cooldowns.get(user_id, 0)
        if now - last < MESSAGE_COOLDOWN_SECONDS:
            return
        self.message_cooldowns[user_id] = now

        data = load_data()
        user = ensure_user(data, user_id, str(message.author))
        user["xp"] += random.randint(*XP_PER_MESSAGE)
        save_data(data)
        # Раньше здесь отправлялось сообщение о повышении уровня в чат — убрано по просьбе,
        # уровень по-прежнему считается и доступен через /профиль и /лидеры.

    # ---------- Время в войсе ----------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        user_id = str(member.id)

        # Зашёл в войс (или из одного канала в другой, если раньше не был нигде)
        if before.channel is None and after.channel is not None:
            self.voice_join_times[user_id] = time.time()

        # Вышел из войса полностью
        elif before.channel is not None and after.channel is None:
            join_time = self.voice_join_times.pop(user_id, None)
            if join_time:
                elapsed = int(time.time() - join_time)
                data = load_data()
                user = ensure_user(data, user_id, str(member))
                user["voice_seconds"] += elapsed
                save_data(data)

    # ---------- Печеньки за реакцию 🍪 ----------
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != COOKIE_EMOJI:
            return
        if payload.member and payload.member.bot:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if message.author.bot:
            return
        if not ALLOW_SELF_COOKIE and message.author.id == payload.user_id:
            return

        data = load_data()
        user = ensure_user(data, str(message.author.id), str(message.author))
        user["cookies"] += 1
        save_data(data)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != COOKIE_EMOJI:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if message.author.bot:
            return
        if not ALLOW_SELF_COOKIE and message.author.id == payload.user_id:
            return

        data = load_data()
        user_id = str(message.author.id)
        if user_id in data and data[user_id]["cookies"] > 0:
            data[user_id]["cookies"] -= 1
            save_data(data)

    # ---------- Команды ----------
    @app_commands.command(name="профиль", description="Показать карточку профиля: уровень, войс, печеньки")
    async def profile(self, interaction: discord.Interaction, участник: discord.Member = None):
        member = участник or interaction.user
        await interaction.response.defer()

        data = load_data()
        user = data.get(str(member.id), {"xp": 0, "voice_seconds": 0, "cookies": 0})

        card_buffer = await generate_profile_card(member, user)
        file = discord.File(card_buffer, filename="profile_card.png")
        await interaction.followup.send(file=file)

    @app_commands.command(name="лидеры", description="Таблица лидеров сервера")
    @app_commands.describe(тип="По какому параметру показать топ")
    @app_commands.choices(тип=[
        app_commands.Choice(name="Уровень / XP", value="xp"),
        app_commands.Choice(name="Время в войсе", value="voice"),
        app_commands.Choice(name="Печеньки", value="cookies"),
    ])
    async def leaderboard_cmd(self, interaction: discord.Interaction, тип: app_commands.Choice[str] = None):
        data = load_data()
        if not data:
            await interaction.response.send_message("Пока нет данных об активности.")
            return

        key = тип.value if тип else "xp"

        if key == "xp":
            sorted_users = sorted(data.values(), key=lambda x: x["xp"], reverse=True)[:10]
            text = "\n".join(
                f"{i+1}. {u['name']} — уровень {xp_to_level(u['xp'])} ({u['xp']} XP)"
                for i, u in enumerate(sorted_users)
            )
            title = "🏆 Топ по уровню"
        elif key == "voice":
            sorted_users = sorted(data.values(), key=lambda x: x.get("voice_seconds", 0), reverse=True)[:10]
            text = "\n".join(
                f"{i+1}. {u['name']} — {format_duration(u.get('voice_seconds', 0))}"
                for i, u in enumerate(sorted_users)
            )
            title = "🎙️ Топ по времени в войсе"
        else:
            sorted_users = sorted(data.values(), key=lambda x: x.get("cookies", 0), reverse=True)[:10]
            text = "\n".join(
                f"{i+1}. {u['name']} — 🍪 {u.get('cookies', 0)}"
                for i, u in enumerate(sorted_users)
            )
            title = "🍪 Топ по печенькам"

        embed = discord.Embed(title=title, description=text or "Пока нет данных.", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="выдать_опыт", description="Выдать участнику XP вручную (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def give_xp(self, interaction: discord.Interaction, участник: discord.Member, количество: int):
        data = load_data()
        user = ensure_user(data, str(участник.id), str(участник))
        user["xp"] = max(0, user["xp"] + количество)
        save_data(data)
        await interaction.response.send_message(
            f"✅ {участник.mention}: XP изменён на {количество}. Текущий XP: {user['xp']} (уровень {xp_to_level(user['xp'])})."
        )

    @give_xp.error
    async def give_xp_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда только для администраторов.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)

    @app_commands.command(name="уровень", description="Выставить участнику конкретный уровень (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def set_level(self, interaction: discord.Interaction, участник: discord.Member, уровень: int):
        if уровень < 0:
            await interaction.response.send_message("❌ Уровень не может быть отрицательным.", ephemeral=True)
            return

        data = load_data()
        user = ensure_user(data, str(участник.id), str(участник))
        user["xp"] = 50 * уровень ** 2  # минимальный XP, соответствующий этому уровню
        save_data(data)

        await interaction.response.send_message(
            f"✅ {участник.mention} теперь имеет уровень **{уровень}** (XP выставлен на {user['xp']})."
        )

    @set_level.error
    async def set_level_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда только для администраторов.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Levels(bot))
