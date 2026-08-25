"""
Оповещение о бампах/лайках сервера + напоминание, когда можно бампнуть снова.

Как это работает:
- Бот слушает сообщения от любых ботов (Disboard, DSMonitoring и т.д.), у которых в эмбеде
  есть фразы вроде "успешно лайкнули", "успешно подняли" (список настраиваемый).
- Как только видит такое сообщение — сразу пишет "Спасибо @имя за бамп!"
- Пытается найти в эмбеде точное время следующего бампа (боты часто сами его указывают).
  Если не находит — использует заданный вручную интервал (по умолчанию 2 часа).
- В нужный момент бот сам напомнит в настроенном канале, что можно бампать снова
  (можно настроить пинг роли).

Работает даже после перезапуска бота — время следующего напоминания хранится в файле,
не в оперативной памяти.
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import re
import time

CONFIG_FILE = "bump_config.json"
DATA_FILE = "bump_data.json"

TIMESTAMP_PATTERN = re.compile(r"<t:(\d+)")

DEFAULT_CONFIG = {
    "channel_id": None,
    "ping_role_id": None,
    "cooldown_hours": 2,
    "success_keywords": [
        "успешно лайкнули", "успешно подняли", "bump done",
        "server bumped", "успешный бамп", "вы подняли сервер",
    ],
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        for key, value in DEFAULT_CONFIG.items():
            data.setdefault(key, value)
        return data


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"next_bump_time": None}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class BumpReminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_loop.start()

    def cog_unload(self):
        self.check_loop.cancel()

    # ---------- Отслеживание успешного бампа ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.author.bot or not message.embeds:
            return

        config = load_config()
        keywords = [k.lower() for k in config.get("success_keywords", [])]

        for embed in message.embeds:
            blob_parts = [embed.description or "", embed.title or ""]
            for field in embed.fields:
                blob_parts.append(field.name or "")
                blob_parts.append(field.value or "")
            blob = " ".join(blob_parts).lower()

            if any(keyword in blob for keyword in keywords):
                await self._handle_bump_success(message, embed, config)
                return

    async def _handle_bump_success(self, message: discord.Message, embed: discord.Embed, config: dict):
        # Кто бампнул — берём из данных о том, кто вызвал слэш-команду (если это ответ на неё)
        bumper = None
        interaction_meta = getattr(message, "interaction_metadata", None) or getattr(message, "interaction", None)
        if interaction_meta:
            bumper = interaction_meta.user

        mention = bumper.mention if bumper else "участник"

        target_channel = message.channel
        if config.get("channel_id"):
            configured_channel = self.bot.get_channel(int(config["channel_id"]))
            if configured_channel:
                target_channel = configured_channel

        await target_channel.send(f"💜 Спасибо {mention} за бамп!")

        # Пытаемся найти точное время следующего бампа в эмбеде (Discord-таймстемп вида <t:12345>)
        next_time = None
        for field in embed.fields:
            match = TIMESTAMP_PATTERN.search(field.value or "")
            if match:
                next_time = int(match.group(1))
                break
        if not next_time and embed.description:
            match = TIMESTAMP_PATTERN.search(embed.description)
            if match:
                next_time = int(match.group(1))

        if not next_time:
            cooldown_hours = config.get("cooldown_hours", 2)
            next_time = int(time.time()) + cooldown_hours * 3600

        data = load_data()
        data["next_bump_time"] = next_time
        save_data(data)

    # ---------- Фоновая проверка: не пора ли напомнить ----------
    @tasks.loop(minutes=1)
    async def check_loop(self):
        data = load_data()
        next_time = data.get("next_bump_time")
        if not next_time:
            return
        if time.time() < next_time:
            return

        config = load_config()
        channel = None
        if config.get("channel_id"):
            channel = self.bot.get_channel(int(config["channel_id"]))
        if not channel:
            data["next_bump_time"] = None
            save_data(data)
            return

        role_mention = ""
        if config.get("ping_role_id"):
            role = channel.guild.get_role(int(config["ping_role_id"]))
            if role:
                role_mention = f" {role.mention}"

        await channel.send(
            f"⏰{role_mention} Сервер уже можно бампнуть снова!",
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

        data["next_bump_time"] = None
        save_data(data)

    @check_loop.before_loop
    async def before_check_loop(self):
        await self.bot.wait_until_ready()

    # ---------- Настройка ----------
    @app_commands.command(name="настроить_бампы", description="Настроить канал и роль для напоминаний о бампе (для администраторов)")
    @app_commands.describe(
        канал="Канал, куда бот будет писать благодарность и напоминания",
        роль_для_пинга="Роль, которую пинговать, когда пора бампать снова (необязательно)",
        резервный_интервал_часов="Если бот не найдёт точное время в ответе бамп-бота — использует этот интервал",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def configure_bumps(
        self,
        interaction: discord.Interaction,
        канал: discord.TextChannel,
        роль_для_пинга: discord.Role = None,
        резервный_интервал_часов: int = 2,
    ):
        config = load_config()
        config["channel_id"] = str(канал.id)
        config["ping_role_id"] = str(роль_для_пинга.id) if роль_для_пинга else None
        config["cooldown_hours"] = резервный_интервал_часов
        save_config(config)

        role_text = f", роль для пинга: {роль_для_пинга.mention}" if роль_для_пинга else ""
        await interaction.response.send_message(
            f"✅ Готово. Канал для напоминаний: {канал.mention}{role_text}, "
            f"резервный интервал: {резервный_интервал_часов} ч.",
            allowed_mentions=discord.AllowedMentions(roles=False),
        )

    @app_commands.command(name="бамп_статус", description="Когда можно будет бампнуть в следующий раз")
    async def bump_status(self, interaction: discord.Interaction):
        data = load_data()
        next_time = data.get("next_bump_time")
        if not next_time:
            await interaction.response.send_message("Сейчас можно бампать сервер!")
            return

        remaining = int(next_time - time.time())
        if remaining <= 0:
            await interaction.response.send_message("Сейчас можно бампать сервер!")
            return

        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await interaction.response.send_message(f"⏳ Следующий бамп будет доступен через {hours} ч {minutes} мин.")

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда только для администраторов.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(BumpReminder(bot))
