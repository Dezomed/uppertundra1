"""
Экономика сервера: валюта "тундрики".
- За сообщения начисляется случайное количество (1-50), раз в минуту с человека.
- /собрать — раз в сутки, только если у участника есть настроенная роль.
- /зарплата — админ настраивает сумму на роль, потом одной командой платит всем сразу.
- Магазин — админ добавляет товары (можно с выдачей роли при покупке), участники покупают за тундрики.
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
import random

DATA_FILE = "currency_data.json"
CONFIG_FILE = "currency_config.json"

MESSAGE_REWARD_MIN = 1
MESSAGE_REWARD_MAX = 50
MESSAGE_COOLDOWN_SECONDS = 60
DAY_SECONDS = 24 * 60 * 60
CURRENCY_NAME = "тундриков"  # склонение под "N тундриков" — если нужно другое, поправь тут


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"salaries": {}, "shop": [], "daily_role_id": None, "daily_amount": 2000}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def ensure_user(data, user_id: str, name: str):
    data.setdefault(user_id, {"name": name, "balance": 0, "last_claim": 0})
    data[user_id]["name"] = name
    return data[user_id]


class Currency(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_cooldowns = {}

    # ---------- Начисление за сообщения ----------
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
        reward = random.randint(MESSAGE_REWARD_MIN, MESSAGE_REWARD_MAX)
        user["balance"] += reward
        save_data(data)

    # ---------- Баланс и топ ----------
    @app_commands.command(name="баланс", description=f"Посмотреть баланс {CURRENCY_NAME}")
    async def balance(self, interaction: discord.Interaction, участник: discord.Member = None):
        member = участник or interaction.user
        data = load_data()
        user = data.get(str(member.id), {"balance": 0})
        await interaction.response.send_message(
            f"💰 У {member.mention} на счету: **{user['balance']}** {CURRENCY_NAME}."
        )

    @app_commands.command(name="топ_тундриков", description="Таблица лидеров по балансу")
    async def top_currency(self, interaction: discord.Interaction):
        data = load_data()
        if not data:
            await interaction.response.send_message("Пока ни у кого нет тундриков.")
            return
        sorted_users = sorted(data.values(), key=lambda x: x.get("balance", 0), reverse=True)[:10]
        text = "\n".join(f"{i+1}. {u['name']} — {u.get('balance', 0)}" for i, u in enumerate(sorted_users))
        embed = discord.Embed(title=f"🏆 Топ по {CURRENCY_NAME}", description=text, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    # ---------- /собрать — раз в сутки, только с нужной ролью ----------
    @app_commands.command(name="собрать", description="Собрать ежедневную награду (нужна определённая роль)")
    async def daily_claim(self, interaction: discord.Interaction):
        config = load_config()
        role_id = config.get("daily_role_id")
        amount = config.get("daily_amount", 2000)

        if not role_id:
            await interaction.response.send_message(
                "❌ Ежедневный сбор ещё не настроен. Попроси администратора выполнить /настроить_сбор.",
                ephemeral=True,
            )
            return

        member = interaction.user
        has_role = any(role.id == int(role_id) for role in member.roles)
        if not has_role:
            role_obj = interaction.guild.get_role(int(role_id))
            role_name = role_obj.name if role_obj else "нужная роль"
            await interaction.response.send_message(
                f"❌ Для сбора нужна роль **{role_name}**, у тебя её нет.", ephemeral=True
            )
            return

        data = load_data()
        user = ensure_user(data, str(member.id), str(member))
        now = time.time()
        elapsed = now - user.get("last_claim", 0)

        if elapsed < DAY_SECONDS:
            remaining = int(DAY_SECONDS - elapsed)
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            await interaction.response.send_message(
                f"⏳ Ты уже собирал(а) сегодня. Приходи через {hours} ч {minutes} мин.", ephemeral=True
            )
            return

        user["balance"] += amount
        user["last_claim"] = now
        save_data(data)
        await interaction.response.send_message(
            f"✅ {member.mention} собрал(а) **{amount}** {CURRENCY_NAME}! Баланс: {user['balance']}."
        )

    @app_commands.command(name="настроить_сбор", description="Настроить роль и сумму для /собрать (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def configure_daily(self, interaction: discord.Interaction, роль: discord.Role, сумма: int = 2000):
        config = load_config()
        config["daily_role_id"] = str(роль.id)
        config["daily_amount"] = сумма
        save_config(config)
        await interaction.response.send_message(
            f"✅ Теперь /собрать даёт **{сумма}** {CURRENCY_NAME} участникам с ролью {роль.mention}, раз в сутки."
        )

    # ---------- Зарплата ----------
    @app_commands.command(name="настроить_зарплату", description="Задать сумму зарплаты для роли (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def configure_salary(self, interaction: discord.Interaction, роль: discord.Role, сумма: int):
        config = load_config()
        config.setdefault("salaries", {})
        config["salaries"][str(роль.id)] = сумма
        save_config(config)
        await interaction.response.send_message(
            f"✅ Зарплата для роли {роль.mention} установлена: {сумма} {CURRENCY_NAME}. "
            f"Выплата будет происходить по команде /зарплата."
        )

    @app_commands.command(name="убрать_зарплату", description="Убрать зарплату для роли (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_salary(self, interaction: discord.Interaction, роль: discord.Role):
        config = load_config()
        config.get("salaries", {}).pop(str(роль.id), None)
        save_config(config)
        await interaction.response.send_message(f"✅ Зарплата для роли {роль.mention} убрана.")

    @app_commands.command(name="зарплата", description="Выплатить настроенные зарплаты всем участникам (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def pay_salary(self, interaction: discord.Interaction):
        config = load_config()
        salaries = config.get("salaries", {})
        if not salaries:
            await interaction.response.send_message(
                "❌ Зарплаты ещё не настроены. Используй /настроить_зарплату.", ephemeral=True
            )
            return

        await interaction.response.defer()

        data = load_data()
        paid_count = 0
        total_paid = 0

        for member in interaction.guild.members:
            if member.bot:
                continue
            member_role_ids = {str(role.id) for role in member.roles}
            earned = sum(amount for role_id, amount in salaries.items() if role_id in member_role_ids)
            if earned > 0:
                user = ensure_user(data, str(member.id), str(member))
                user["balance"] += earned
                paid_count += 1
                total_paid += earned

        save_data(data)
        await interaction.followup.send(
            f"✅ Зарплата выплачена {paid_count} участникам, всего {total_paid} {CURRENCY_NAME}."
        )

    @app_commands.command(name="список_зарплат", description="Посмотреть текущие настройки зарплат")
    async def list_salaries(self, interaction: discord.Interaction):
        config = load_config()
        salaries = config.get("salaries", {})
        if not salaries:
            await interaction.response.send_message("Зарплаты пока не настроены.")
            return
        lines = []
        for role_id, amount in salaries.items():
            role = interaction.guild.get_role(int(role_id))
            role_name = role.mention if role else f"(роль {role_id} удалена)"
            lines.append(f"{role_name} — {amount} {CURRENCY_NAME}")
        await interaction.response.send_message(
            "💼 Настроенные зарплаты:\n" + "\n".join(lines),
            allowed_mentions=discord.AllowedMentions(roles=False),
        )

    # ---------- Магазин ----------
    def build_shop_embed(self, guild: discord.Guild) -> discord.Embed:
        config = load_config()
        items = config.get("shop", [])

        embed = discord.Embed(
            title="🛒 Магазин сервера",
            description="Чтобы купить, напиши `/купить название:<название товара>`" if items else None,
            color=discord.Color.green(),
        )
        if not items:
            embed.description = "Магазин пока пуст."
            return embed

        for item in items:
            desc = item.get("description", "")
            role_note = ""
            if item.get("role_id"):
                role = guild.get_role(int(item["role_id"]))
                if role:
                    role_note = f" (выдаёт роль {role.mention})"
                    role_desc = item.get("role_description", "")
                    if role_desc:
                        role_note += f" — {role_desc}"
            embed.add_field(
                name=f"{item['name']} — {item['price']} {CURRENCY_NAME}",
                value=(desc + role_note) or "—",
                inline=False,
            )
        return embed

    @app_commands.command(name="магазин", description="Посмотреть товары магазина")
    async def shop(self, interaction: discord.Interaction):
        embed = self.build_shop_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions(roles=False))

    @app_commands.command(name="опубликовать_магазин", description="Опубликовать магазин одним объявлением в канал (для администраторов)")
    @app_commands.describe(канал="В какой канал опубликовать (по умолчанию — текущий)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def publish_shop(self, interaction: discord.Interaction, канал: discord.TextChannel = None):
        target_channel = канал or interaction.channel
        embed = self.build_shop_embed(interaction.guild)

        try:
            await target_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(roles=False))
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ У бота нет прав писать в {target_channel.mention}.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Магазин опубликован в {target_channel.mention}.\n\n"
            f"⚠️ Учти: это разовый снимок магазина. Если позже добавишь или уберёшь товары через "
            f"/магазин_добавить или /магазин_удалить, это сообщение само не обновится — "
            f"нужно будет опубликовать заново.",
            ephemeral=True,
        )

    @app_commands.command(name="магазин_добавить", description="Добавить товар в магазин (для администраторов)")
    @app_commands.describe(
        название="Название товара",
        цена="Цена в тундриках",
        описание="Описание товара",
        роль="Роль, которая выдаётся при покупке (необязательно)",
        описание_роли="Что даёт эта роль (необязательно, показывается в магазине)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def shop_add(self, interaction: discord.Interaction, название: str, цена: int, описание: str = "", роль: discord.Role = None, описание_роли: str = ""):
        config = load_config()
        config.setdefault("shop", [])
        config["shop"] = [i for i in config["shop"] if i["name"].lower() != название.lower()]
        config["shop"].append({
            "name": название,
            "price": цена,
            "description": описание,
            "role_id": str(роль.id) if роль else None,
            "role_description": описание_роли,
        })
        save_config(config)
        await interaction.response.send_message(f"✅ Товар «{название}» добавлен в магазин за {цена} {CURRENCY_NAME}.")

    @app_commands.command(name="магазин_удалить", description="Удалить товар из магазина (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def shop_remove(self, interaction: discord.Interaction, название: str):
        config = load_config()
        before = len(config.get("shop", []))
        config["shop"] = [i for i in config.get("shop", []) if i["name"].lower() != название.lower()]
        save_config(config)
        if len(config["shop"]) < before:
            await interaction.response.send_message(f"✅ Товар «{название}» удалён из магазина.")
        else:
            await interaction.response.send_message(f"❌ Товар «{название}» не найден.", ephemeral=True)

    @app_commands.command(name="купить", description="Купить товар в магазине")
    async def buy(self, interaction: discord.Interaction, название: str):
        config = load_config()
        item = next((i for i in config.get("shop", []) if i["name"].lower() == название.lower()), None)
        if not item:
            await interaction.response.send_message(f"❌ Товар «{название}» не найден в магазине.", ephemeral=True)
            return

        data = load_data()
        user = ensure_user(data, str(interaction.user.id), str(interaction.user))

        if user["balance"] < item["price"]:
            await interaction.response.send_message(
                f"❌ Не хватает {CURRENCY_NAME}. Нужно {item['price']}, у тебя {user['balance']}.", ephemeral=True
            )
            return

        user["balance"] -= item["price"]
        save_data(data)

        role_message = ""
        if item.get("role_id"):
            role = interaction.guild.get_role(int(item["role_id"]))
            if role:
                await interaction.user.add_roles(role)
                role_message = f" Тебе выдана роль {role.mention}."
                role_desc = item.get("role_description", "")
                if role_desc:
                    role_message += f" ({role_desc})"

        await interaction.response.send_message(
            f"✅ Куплено: «{item['name']}» за {item['price']} {CURRENCY_NAME}.{role_message} Остаток: {user['balance']}.",
            allowed_mentions=discord.AllowedMentions(roles=False),
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда только для администраторов.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Currency(bot))
