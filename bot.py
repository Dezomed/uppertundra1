"""
Главный файл бота.
Здесь бот запускается и подключает все модули (cogs) из папки cogs/.
Тебе не нужно ничего менять в этом файле.
"""

import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Загружаем токен из файла .env (см. .env.example)
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Intents — это разрешения, что боту можно "видеть" и "слышать" на сервере.
# message_content и members нужно ОБЯЗАТЕЛЬНО включить в настройках бота
# на сайте Discord Developer Portal (Privileged Gateway Intents), иначе бот не запустится.
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=commands.DefaultHelpCommand())


@bot.event
async def on_ready():
    print(f"✅ Бот запущен как {bot.user} (id: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Синхронизировано {len(synced)} слэш-команд")
    except Exception as e:
        print(f"⚠️ Ошибка синхронизации слэш-команд: {e}")


async def load_cogs():
    """Загружает все модули из папки cogs/"""
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and not filename.startswith("_"):
            extension = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(extension)
                print(f"✅ Загружен модуль: {filename}")
            except Exception as e:
                print(f"❌ Ошибка загрузки {filename}: {e}")


async def main():
    if not TOKEN:
        print("❌ Не найден DISCORD_TOKEN. Проверь файл .env")
        return
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
