"""
Модуль "казны" сервера: донаты, баланс, топ донатеров.
Хранит данные в JSON-файле economy_data.json (простое решение для старта,
позже можно перевести на нормальную базу данных).
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os

DATA_FILE = "economy_data.json"
DONATE_CONFIG_FILE = "donate_config.json"  # общий файл с настройками из cogs/donate_info.py


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"treasury_total": 0, "donations": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_donate_grant_role_id():
    """Читает ID роли, настроенной через /настроить_донат_уведомления (cogs/donate_info.py)."""
    if not os.path.exists(DONATE_CONFIG_FILE):
        return None
    with open(DONATE_CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config.get("grant_role_id")


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="донат", description="Записать донат в казну сервера (только для администраторов)")
    @app_commands.describe(
        участник="Кто задонатил",
        сумма="Сумма доната",
        валюта="Валюта (по умолчанию RUB)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def donate(self, interaction: discord.Interaction, участник: discord.Member, сумма: float, валюта: str = "RUB"):
        if сумма <= 0:
            await interaction.response.send_message("❌ Сумма должна быть больше нуля.", ephemeral=True)
            return

        data = load_data()
        user_id = str(участник.id)
        data["donations"].setdefault(user_id, {"name": str(участник), "total": 0, "history": []})
        data["donations"][user_id]["total"] += сумма
        data["donations"][user_id]["history"].append({
            "amount": сумма,
            "currency": валюта,
            "recorded_by": str(interaction.user),
        })
        data["treasury_total"] += сумма
        save_data(data)

        role_message = ""
        role_id = get_donate_grant_role_id()
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            if role and role not in участник.roles:
                await участник.add_roles(role)
                role_message = f" Выдана роль {role.mention}."

        await interaction.response.send_message(
            f"💰 Записан донат от {участник.mention}: {сумма} {валюта} "
            f"(внёс(ла) в базу: {interaction.user.mention}).{role_message}\n"
            f"Общий вклад {участник.mention}: {data['donations'][user_id]['total']} (в записанных единицах).",
            allowed_mentions=discord.AllowedMentions(roles=False),
        )

    @donate.error
    async def donate_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Эту команду может использовать только администратор сервера.", ephemeral=True
            )
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)

    @app_commands.command(name="казна", description="Показать текущее состояние казны")
    async def treasury(self, interaction: discord.Interaction):
        data = load_data()
        embed = discord.Embed(title="💰 Казна сервера", color=discord.Color.gold())
        embed.add_field(name="Всего собрано (по номиналу)", value=str(data["treasury_total"]), inline=False)
        embed.add_field(name="Участников-донатеров", value=str(len(data["donations"])), inline=False)
        embed.set_footer(text="Суммы в разных валютах суммируются по номиналу — учитывай это при использовании.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="топ_донатеров", description="Топ донатеров сервера")
    async def top_donators(self, interaction: discord.Interaction):
        data = load_data()
        if not data["donations"]:
            await interaction.response.send_message("Пока никто не донатил.")
            return

        sorted_donors = sorted(data["donations"].values(), key=lambda x: x["total"], reverse=True)[:10]
        text = "\n".join(
            f"{i+1}. {d['name']} — {d['total']}" for i, d in enumerate(sorted_donors)
        )
        embed = discord.Embed(title="🏆 Топ донатеров", description=text, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="мои_донаты", description="Показать твою историю донатов")
    async def my_donations(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        if user_id not in data["donations"]:
            await interaction.response.send_message("У тебя пока нет записанных донатов.")
            return

        history = data["donations"][user_id]["history"]
        text = "\n".join(f"• {h['amount']} {h['currency']}" for h in history[-10:])
        await interaction.response.send_message(
            f"Твоя история донатов (последние 10):\n{text}\n\n"
            f"Всего: {data['donations'][user_id]['total']}",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Economy(bot))
