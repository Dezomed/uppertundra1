"""
Утилитарные команды для администрации.
"""

import discord
from discord.ext import commands
from discord import app_commands


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="сказать", description="Отправить сообщение от имени бота (для администраторов)")
    @app_commands.describe(
        текст="Текст сообщения",
        канал="В какой канал отправить (по умолчанию — текущий)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def say(self, interaction: discord.Interaction, текст: str, канал: discord.TextChannel = None):
        target_channel = канал or interaction.channel

        try:
            await target_channel.send(текст)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ У бота нет прав писать в {target_channel.mention}.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Сообщение отправлено в {target_channel.mention}.", ephemeral=True
        )

    @app_commands.command(name="объявление", description="Отправить оформленное объявление от имени бота (для администраторов)")
    @app_commands.describe(
        заголовок="Заголовок объявления",
        текст="Текст объявления",
        канал="В какой канал отправить (по умолчанию — текущий)",
        картинка="Картинка, которая будет прикреплена снизу объявления (необязательно)",
        цвет="Цвет полоски слева, HEX-код без решётки, например FF5733 (необязательно)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def announce(
        self,
        interaction: discord.Interaction,
        заголовок: str,
        текст: str,
        канал: discord.TextChannel = None,
        картинка: discord.Attachment = None,
        цвет: str = None,
    ):
        target_channel = канал or interaction.channel

        embed_color = discord.Color.blurple()
        if цвет:
            try:
                embed_color = discord.Color(int(цвет.lstrip("#"), 16))
            except ValueError:
                await interaction.response.send_message(
                    "❌ Неверный формат цвета. Пример правильного: FF5733 (без #, 6 символов 0-9/A-F).",
                    ephemeral=True,
                )
                return

        embed = discord.Embed(title=заголовок, description=текст, color=embed_color)
        if картинка:
            embed.set_image(url=картинка.url)

        try:
            await target_channel.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ У бота нет прав писать в {target_channel.mention}.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Объявление отправлено в {target_channel.mention}.", ephemeral=True
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Эта команда только для администраторов.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Ошибка: {error}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Utility(bot))
