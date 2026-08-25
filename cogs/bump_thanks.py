"""
Благодарность за бамп/лайк сервера.

Как это работает технически: когда кто-то использует слэш-команду другого бота (например,
/bump у Disboard или /like у DSMonitoring), Discord прикрепляет к ответному сообщению этого
бота информацию о том, какая именно команда была вызвана и кем — через message.interaction.
Наш бот слушает все сообщения и, если видит, что это ответ на одну из настроенных "бамп-команд",
благодарит того, кто её вызвал, и (по желанию) ставит отложенное напоминание в канале.

⚠️ Напоминания хранятся только в памяти бота, пока он работает: если бот перезапустится
до того, как напоминание должно сработать — оно потеряется. Для простого сервера это
обычно не критично, но имей в виду.
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio

CONFIG_FILE = "bump_config.json"

DEFAULT_CONFIG = {
    "trigger_commands": ["bump", "like", "up"],  # названия слэш-команд, за которые благодарим
    "reminder_hours": None,
    "reminder_channel_id": None,
    "reminder_role_id": None,
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


class BumpThanks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        interaction_ref = getattr(message, "interaction", None)
        if interaction_ref is None:
            return  # это сообщение не было ответом на чью-то слэш-команду

        command_name = (interaction_ref.name or "").lower()
        config = load_config()
        trigger_commands = [c.lower() for c in config.get("trigger_commands", [])]

        if command_name not in trigger_commands:
            return

        user = interaction_ref.user

        embed = discord.Embed(
            description=f"💜 Спасибо {user.mention} за бамп!",
            color=discord.Color.purple(),
        )
        await message.channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))

        reminder_hours = config.get("reminder_hours")
        reminder_channel_id = config.get("reminder_channel_id")
        if reminder_hours and reminder_channel_id:
            asyncio.create_task(self.send_reminder_later(reminder_hours, int(reminder_channel_id), config.get("reminder_role_id")))

    async def send_reminder_later(self, hours: float, channel_id: int, role_id: str = None):
        await asyncio.sleep(hours * 3600)
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        role_mention = ""
        allowed_mentions = discord.AllowedMentions(roles=False)
        if role_id:
            role = channel.guild.get_role(int(role_id))
            if role:
                role_mention = f"{role.mention} "
                allowed_mentions = discord.AllowedMentions(roles=True)

        await channel.send(f"{role_mention}⏰ Сервер снова можно бампнуть!", allowed_mentions=allowed_mentions)

    # ---------- Настройка ----------
    @app_commands.command(name="настроить_бамп_триггеры", description="Задать список команд, за которые бот благодарит (для администраторов)")
    @app_commands.describe(команды="Названия команд через запятую, например: bump, like, up")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def configure_triggers(self, interaction: discord.Interaction, команды: str):
        config = load_config()
        config["trigger_commands"] = [c.strip().lower() for c in команды.split(",") if c.strip()]
        save_config(config)
        await interaction.response.send_message(
            f"✅ Теперь бот благодарит за команды: {', '.join(config['trigger_commands'])}"
        )

    @app_commands.command(name="настроить_бамп_напоминание", description="Настроить отложенное напоминание о следующем бампе (для администраторов)")
    @app_commands.describe(
        часы="Через сколько часов напомнить (например 2)",
        канал="В какой канал слать напоминание",
        роль="Какую роль пинговать в напоминании (необязательно)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def configure_reminder(
        self,
        interaction: discord.Interaction,
        часы: float,
        канал: discord.TextChannel,
        роль: discord.Role = None,
    ):
        config = load_config()
        config["reminder_hours"] = часы
        config["reminder_channel_id"] = str(канал.id)
        config["reminder_role_id"] = str(роль.id) if роль else None
        save_config(config)
        await interaction.response.send_message(
            f"✅ Напоминание настроено: через {часы} ч. в {канал.mention}"
            + (f", с пингом {роль.mention}" if роль else ""),
            allowed_mentions=discord.AllowedMentions(roles=False),
        )

    @app_commands.command(name="выключить_бамп_напоминание", description="Отключить напоминание о бампе (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def disable_reminder(self, interaction: discord.Interaction):
        config = load_config()
        config["reminder_hours"] = None
        config["reminder_channel_id"] = None
        config["reminder_role_id"] = None
        save_config(config)
        await interaction.response.send_message("✅ Напоминание о бампе отключено.")

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда только для администраторов.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(BumpThanks(bot))
