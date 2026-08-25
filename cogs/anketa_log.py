"""
Учёт анкет верификации по транскриптам Ticket Tool.

Как это работает технически:
Файл транскрипта Ticket Tool — это не обычный HTML с текстом, а страница, в которую зашита
base64-закодированная строка с JSON-списком всех сообщений тикета (переменная "messages" в
теге <script>). Бот скачивает файл, декодирует эту строку и разбирает сообщения по отдельности.

Кто засчитывается как "принявший анкету":
1. Автор сообщения, начинающегося с "!пропуск" (это наша же команда пропуска верификации) — 
   именно её пишет верификатор, когда пропускает участника.
2. Дополнительно (как подстраховка) — тот, кто закрыл тикет (Ticket Tool пишет
   "Ticket Closed by <@ID>" в эмбеде).
Если ID автора одного из этих действий есть в списке отслеживаемых — тикету засчитывается +1
анкета для этого человека.

Ты добавляешь верификаторов в отслеживание по ID (через выбор участника, ник не важен) —
/лог_анкет_добавить. В конце месяца — /лог_анкет — отчёт по каждому: первая половина/вторая
половина/итого.
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
import base64
from datetime import datetime, timezone

CONFIG_FILE = "anketa_config.json"
DATA_FILE = "anketa_data.json"

MESSAGES_VAR_PATTERN = re.compile(r'let messages = "([^"]+)"')
TICKET_CLOSED_PATTERN = re.compile(r"Ticket Closed by <@!?(\d+)>")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"tracked_ids": []}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"records": [], "processed_files": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_half_and_month(dt: datetime):
    month_key = dt.strftime("%Y-%m")
    half = "H1" if dt.day <= 15 else "H2"
    return month_key, half


def extract_verifier_ids(html_text: str) -> set:
    """Декодирует транскрипт и находит ID тех, кто, похоже, обработал анкету."""
    found_ids = set()

    match = MESSAGES_VAR_PATTERN.search(html_text)
    if not match:
        return found_ids

    try:
        decoded = base64.b64decode(match.group(1)).decode("utf-8")
        messages = json.loads(decoded)
    except Exception:
        return found_ids

    for msg in messages:
        content = (msg.get("content") or "").strip()

        # Сигнал 1: сообщение начинается с "!пропуск"
        if content.lower().startswith("!пропуск"):
            author_id = msg.get("user_id")
            if author_id:
                found_ids.add(str(author_id))

        # Сигнал 2: эмбед "Ticket Closed by <@ID>"
        for embed in msg.get("embeds", []) or []:
            description = embed.get("description") or ""
            closed_match = TICKET_CLOSED_PATTERN.search(description)
            if closed_match:
                found_ids.add(closed_match.group(1))

    return found_ids


class AnketaLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.attachments:
            return

        html_attachments = [
            a for a in message.attachments
            if a.filename.lower().endswith(".html") and "transcript" in a.filename.lower()
        ]
        if not html_attachments:
            return

        config = load_config()
        tracked_ids = set(config.get("tracked_ids", []))
        if not tracked_ids:
            return

        data = load_data()
        processed = set(data.get("processed_files", []))

        for attachment in html_attachments:
            file_key = f"{message.id}:{attachment.filename}"
            if file_key in processed:
                continue

            try:
                content_bytes = await attachment.read()
                html_text = content_bytes.decode("utf-8", errors="ignore")
            except Exception:
                continue

            found_ids = extract_verifier_ids(html_text)
            matched_ids = found_ids & tracked_ids

            if matched_ids:
                month_key, half = get_half_and_month(message.created_at.astimezone(timezone.utc))
                for user_id in matched_ids:
                    data.setdefault("records", []).append({
                        "verifier_id": user_id,
                        "file": attachment.filename,
                        "month": month_key,
                        "half": half,
                    })

            processed.add(file_key)

        data["processed_files"] = list(processed)
        save_data(data)

    # ---------- Настройка списка отслеживаемых ----------
    @app_commands.command(name="лог_анкет_добавить", description="Добавить верификатора в учёт анкет (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def add_tracked(self, interaction: discord.Interaction, кого_отслеживать: discord.Member):
        config = load_config()
        config.setdefault("tracked_ids", [])
        user_id = str(кого_отслеживать.id)
        if user_id not in config["tracked_ids"]:
            config["tracked_ids"].append(user_id)
            save_config(config)
        await interaction.response.send_message(f"✅ {кого_отслеживать.mention} добавлен(а) в учёт анкет.")

    @app_commands.command(name="лог_анкет_убрать", description="Убрать верификатора из учёта анкет (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_tracked(self, interaction: discord.Interaction, кого_убрать: discord.Member):
        config = load_config()
        user_id = str(кого_убрать.id)
        config["tracked_ids"] = [i for i in config.get("tracked_ids", []) if i != user_id]
        save_config(config)
        await interaction.response.send_message(f"✅ {кого_убрать.mention} убран(а) из учёта анкет.")

    @app_commands.command(name="лог_анкет_список", description="Посмотреть, кого сейчас отслеживает учёт анкет")
    @app_commands.default_permissions(administrator=True)
    async def list_tracked(self, interaction: discord.Interaction):
        config = load_config()
        tracked_ids = config.get("tracked_ids", [])
        if not tracked_ids:
            await interaction.response.send_message("Список отслеживаемых пуст.")
            return
        lines = []
        for user_id in tracked_ids:
            member = interaction.guild.get_member(int(user_id))
            lines.append(member.mention if member else f"(участник {user_id} не найден на сервере)")
        await interaction.response.send_message(
            "📋 Отслеживаются:\n" + "\n".join(lines),
            allowed_mentions=discord.AllowedMentions(users=False),
        )

    # ---------- Отчёт ----------
    @app_commands.command(name="лог_анкет", description="Отчёт по количеству принятых анкет за месяц")
    @app_commands.describe(месяц="Формат ГГГГ-ММ, например 2026-08. По умолчанию — текущий месяц.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def report(self, interaction: discord.Interaction, месяц: str = None):
        month_key = месяц or datetime.now(timezone.utc).strftime("%Y-%m")

        config = load_config()
        tracked_ids = config.get("tracked_ids", [])
        if not tracked_ids:
            await interaction.response.send_message("Список отслеживаемых пуст — добавь через /лог_анкет_добавить.")
            return

        data = load_data()
        records = data.get("records", [])

        lines = []
        for user_id in tracked_ids:
            h1_count = sum(1 for r in records if r["verifier_id"] == user_id and r["month"] == month_key and r["half"] == "H1")
            h2_count = sum(1 for r in records if r["verifier_id"] == user_id and r["month"] == month_key and r["half"] == "H2")
            member = interaction.guild.get_member(int(user_id))
            name = member.mention if member else f"(участник {user_id} не найден)"
            lines.append(f"{name} — 1-15: **{h1_count}**, 16-конец: **{h2_count}**, всего: **{h1_count + h2_count}**")

        embed = discord.Embed(
            title=f"📊 Отчёт по анкетам за {month_key}",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions(users=False))

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда только для администраторов.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AnketaLog(bot))
