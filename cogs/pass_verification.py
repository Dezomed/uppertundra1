"""
Команда /пропуск — пропускает участника верификацию: убирает одну роль и выдаёт другую.
Роли настраиваются один раз командой /настроить_пропуск (по умолчанию — "новый гость" и "участник").
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_FILE = "pass_config.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"remove_role_id": None, "add_role_id": None}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class PassVerification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="настроить_пропуск", description="Настроить, какие роли меняет /пропуск (для администраторов)")
    @app_commands.describe(убрать_роль="Роль, которая будет сниматься", выдать_роль="Роль, которая будет выдаваться")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def configure_pass(self, interaction: discord.Interaction, убрать_роль: discord.Role, выдать_роль: discord.Role):
        config = {"remove_role_id": str(убрать_роль.id), "add_role_id": str(выдать_роль.id)}
        save_config(config)
        await interaction.response.send_message(
            f"✅ Теперь /пропуск снимает {убрать_роль.mention} и выдаёт {выдать_роль.mention}.",
            allowed_mentions=discord.AllowedMentions(roles=False),
        )

    # ---------- !пропуск — обычная текстовая команда, НЕ слэш-команда ----------
    # Специально сделано так, чтобы обычные участники не видели её в списке слэш-команд.
    # Вызывается как: !пропуск @участник
    @commands.command(name="пропуск")
    @commands.has_permissions(manage_roles=True)
    async def pass_member(self, ctx: commands.Context, участник: discord.Member):
        config = load_config()
        remove_role_id = config.get("remove_role_id")
        add_role_id = config.get("add_role_id")

        if not remove_role_id or not add_role_id:
            await ctx.send("❌ Пропуск ещё не настроен. Сначала выполни /настроить_пропуск.")
            return

        remove_role = ctx.guild.get_role(int(remove_role_id))
        add_role = ctx.guild.get_role(int(add_role_id))

        if not remove_role or not add_role:
            await ctx.send("❌ Одна из настроенных ролей больше не существует. Настрой заново через /настроить_пропуск.")
            return

        if remove_role in участник.roles:
            await участник.remove_roles(remove_role)
        await участник.add_roles(add_role)

        embed = discord.Embed(
            description=f"✅ {участник.mention} пропущен на сервер! Добро пожаловать!",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))

    @pass_member.error
    async def pass_member_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Для этой команды нужны права управления ролями.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Не нашёл такого участника. Убедись, что упомянул его через @.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Использование: `!пропуск @участник`")
        else:
            await ctx.send(f"❌ Ошибка: {error}")

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Для этой команды нужны права управления ролями.", ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(PassVerification(bot))
