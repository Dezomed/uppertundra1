"""
Команда /задонатить — показывает участнику карточку с информацией,
как задонатить (Boosty, сбор в банке и т.д.). Видна только тому, кто вызвал команду.

Технический момент: Discord не даёт боту напрямую узнать, перешёл ли человек по внешней
ссылке — это происходит вне Discord. Поэтому вместо прямой ссылки в карточке — кнопки.
Когда участник нажимает кнопку, бот это видит (это уже действие внутри Discord) и только
после нажатия показывает настоящую ссылку. Это и есть механизм "узнать, что перешёл" —
максимально точный из того, что вообще возможно сделать ботом.
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_FILE = "donate_config.json"

DEFAULT_CONFIG = {
    "title": "💰 Поддержать сервер",
    "description": "Спасибо, что хочешь помочь! Нажми на кнопку нужного способа ниже, чтобы получить ссылку:",
    "links": [],
    "notify_user_id": None,
    "grant_role_id": None,
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


def build_donate_embed(config: dict) -> discord.Embed:
    embed = discord.Embed(
        title=config["title"],
        description=config["description"],
        color=discord.Color.gold(),
    )
    links = config.get("links", [])
    if not links:
        embed.add_field(name="Пока не настроено", value="Администратор ещё не добавил ссылки.", inline=False)
    return embed


class DonateLinkButton(discord.ui.Button):
    def __init__(self, label_text: str, url: str):
        super().__init__(label=label_text, style=discord.ButtonStyle.secondary)
        self.url = url
        self.label_text = label_text

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"🔗 Держи ссылку — **{self.label_text}**:\n{self.url}", ephemeral=True
        )

        config = load_config()
        notify_id = config.get("notify_user_id")

        if notify_id:
            try:
                admin_user = await interaction.client.fetch_user(int(notify_id))
                await admin_user.send(
                    f"💰 {interaction.user} (id: {interaction.user.id}) нажал(а) кнопку доната «{self.label_text}»."
                )
            except (discord.Forbidden, discord.HTTPException):
                pass  # у админа закрыты ЛС или ID больше не существует — не роняем бота


class DonateView(discord.ui.View):
    def __init__(self, links: list):
        super().__init__(timeout=300)  # кнопки будут рабочими 5 минут — этого достаточно, сообщение и так эфемерное
        for link in links:
            self.add_item(DonateLinkButton(link["label"], link["url"]))


class DonateInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="задонатить", description="Посмотреть, как можно поддержать сервер (видно только тебе)")
    async def donate_info(self, interaction: discord.Interaction):
        config = load_config()
        embed = build_donate_embed(config)
        links = config.get("links", [])
        view = DonateView(links) if links else None
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="настроить_донат_текст", description="Задать заголовок и описание карточки доната (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def configure_donate_text(self, interaction: discord.Interaction, заголовок: str, описание: str):
        config = load_config()
        config["title"] = заголовок
        config["description"] = описание
        save_config(config)
        await interaction.response.send_message("✅ Текст карточки доната обновлён.", ephemeral=True)

    @app_commands.command(name="донат_добавить_ссылку", description="Добавить ссылку в карточку доната (для администраторов)")
    @app_commands.describe(название="Например: Boosty, Сбор в банке", ссылка="Полная ссылка (начинается с https://)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def add_donate_link(self, interaction: discord.Interaction, название: str, ссылка: str):
        if not ссылка.startswith("http://") and not ссылка.startswith("https://"):
            await interaction.response.send_message(
                "❌ Ссылка должна начинаться с http:// или https://", ephemeral=True
            )
            return

        config = load_config()
        config.setdefault("links", [])
        config["links"] = [l for l in config["links"] if l["label"].lower() != название.lower()]
        config["links"].append({"label": название, "url": ссылка})
        save_config(config)
        await interaction.response.send_message(f"✅ Ссылка «{название}» добавлена.", ephemeral=True)

    @app_commands.command(name="донат_убрать_ссылку", description="Убрать ссылку из карточки доната (для администраторов)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_donate_link(self, interaction: discord.Interaction, название: str):
        config = load_config()
        before = len(config.get("links", []))
        config["links"] = [l for l in config.get("links", []) if l["label"].lower() != название.lower()]
        save_config(config)
        if len(config["links"]) < before:
            await interaction.response.send_message(f"✅ Ссылка «{название}» убрана.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ссылка «{название}» не найдена.", ephemeral=True)

    @app_commands.command(name="настроить_донат_уведомления", description="Настроить уведомление в ЛС о кликах и роль за донат (для администраторов)")
    @app_commands.describe(
        кого_уведомлять="Кому бот будет писать в ЛС о переходах по кнопкам (можешь указать себя)",
        выдать_роль="Роль, которая будет выдаваться при записи доната через /донат (необязательно)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def configure_donate_notify(
        self,
        interaction: discord.Interaction,
        кого_уведомлять: discord.Member = None,
        выдать_роль: discord.Role = None,
    ):
        config = load_config()
        if кого_уведомлять:
            config["notify_user_id"] = str(кого_уведомлять.id)
        if выдать_роль:
            config["grant_role_id"] = str(выдать_роль.id)
        save_config(config)

        parts = []
        if кого_уведомлять:
            parts.append(f"уведомления о кликах будут приходить {кого_уведомлять.mention} в ЛС")
        if выдать_роль:
            parts.append(f"при записи доната через /донат будет выдаваться роль {выдать_роль.mention}")
        summary = " и ".join(parts) if parts else "настройки не изменены (не указано ни одного параметра)"

        await interaction.response.send_message(
            f"✅ Готово: {summary}.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions(roles=False, users=False),
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда только для администраторов.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(DonateInfo(bot))
