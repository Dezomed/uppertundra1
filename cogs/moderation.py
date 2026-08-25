"""
Модуль модерации.
Команды доступны только тем, у кого есть право "Управление сообщениями" / "Кик" / "Бан"
(это настраивается в Discord автоматически по правам роли).
"""

import discord
from discord.ext import commands
from discord import app_commands
import datetime

# Простое хранилище варнов в памяти (при перезапуске бота обнулится).
# Если нужно, чтобы варны сохранялись навсегда - скажи, добавим базу данных.
warns = {}  # {user_id: [список причин]}


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="кик", description="Кикнуть участника с сервера")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, участник: discord.Member, причина: str = "Не указана"):
        await участник.kick(reason=причина)
        await interaction.response.send_message(f"👢 {участник.mention} кикнут. Причина: {причина}")

    @app_commands.command(name="бан", description="Забанить участника")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, участник: discord.Member, причина: str = "Не указана"):
        await участник.ban(reason=причина)
        await interaction.response.send_message(f"🔨 {участник.mention} забанен. Причина: {причина}")

    @app_commands.command(name="разбан", description="Разбанить участника по ID")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        user = await self.bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"✅ {user.mention} разбанен.")

    @app_commands.command(name="мут", description="Замутить участника на N минут")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, участник: discord.Member, минуты: int, причина: str = "Не указана"):
        duration = datetime.timedelta(minutes=минуты)
        await участник.timeout(duration, reason=причина)
        await interaction.response.send_message(f"🔇 {участник.mention} замучен на {минуты} мин. Причина: {причина}")

    @app_commands.command(name="размут", description="Снять мут с участника")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, участник: discord.Member):
        await участник.timeout(None)
        await interaction.response.send_message(f"🔊 С {участник.mention} снят мут.")

    @app_commands.command(name="варн", description="Выдать предупреждение участнику")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, участник: discord.Member, причина: str = "Не указана"):
        warns.setdefault(участник.id, []).append(причина)
        count = len(warns[участник.id])
        await interaction.response.send_message(
            f"⚠️ {участник.mention} получил предупреждение ({count}). Причина: {причина}"
        )

    @app_commands.command(name="варны", description="Посмотреть предупреждения участника")
    async def warns_list(self, interaction: discord.Interaction, участник: discord.Member):
        user_warns = warns.get(участник.id, [])
        if not user_warns:
            await interaction.response.send_message(f"У {участник.mention} нет предупреждений.")
            return
        text = "\n".join(f"{i+1}. {w}" for i, w in enumerate(user_warns))
        await interaction.response.send_message(f"⚠️ Предупреждения {участник.mention}:\n{text}")

    @app_commands.command(name="очистить", description="Удалить N последних сообщений в канале")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, количество: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=количество)
        await interaction.followup.send(f"🧹 Удалено {len(deleted)} сообщений.", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ У тебя нет прав для этой команды.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
