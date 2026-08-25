"""
Модуль развлечений: мини-команды для разнообразия в чате.
Система уровней/войса/печенек вынесена в cogs/levels.py.
"""

import discord
from discord.ext import commands
from discord import app_commands
import random


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="кубик", description="Бросить кубик (по умолчанию d6)")
    async def dice(self, interaction: discord.Interaction, грани: int = 6):
        result = random.randint(1, грани)
        await interaction.response.send_message(f"🎲 Выпало: **{result}** (из {грани})")

    @app_commands.command(name="монетка", description="Подбросить монетку")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Орёл 🦅", "Решка 🪙"])
        await interaction.response.send_message(result)

    @app_commands.command(name="опрос", description="Создать простой опрос да/нет")
    async def poll(self, interaction: discord.Interaction, вопрос: str):
        embed = discord.Embed(title="📊 Опрос", description=вопрос, color=discord.Color.blue())
        embed.set_footer(text=f"Создал {interaction.user}")
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction("👍")
        await message.add_reaction("👎")


async def setup(bot):
    await bot.add_cog(Fun(bot))
