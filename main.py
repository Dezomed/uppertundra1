import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "cogs.moderation",
    "cogs.roles",
    "cogs.economy",
    "cogs.fun",
]


@bot.event
async def on_ready():
    print(f"✅ Бот запущен как {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Синхронизировано {len(synced)} слэш-команд")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {e}")


async def main():
    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            print(f"📦 Загружен модуль: {cog}")
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit(
            "❌ Не найден DISCORD_TOKEN. Добавь его в .env файл (см. .env.example)"
        )
    asyncio.run(main())
