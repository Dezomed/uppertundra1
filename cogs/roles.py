"""
Модуль ролей: автороль новым участникам + реакции-роли (self-role).
"""

import discord
from discord.ext import commands
from discord import app_commands

# ID роли, которая выдаётся всем новым участникам автоматически.
# Поставь None, если автороль не нужна.
AUTO_ROLE_NAME = None  # например: "Участник"

# Соответствие эмодзи -> название роли для реакции-ролей.
# Настраивается командой /reaction_role_setup (см. ниже).
REACTION_ROLE_MAP = {}  # {message_id: {emoji: role_name}}


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if AUTO_ROLE_NAME:
            role = discord.utils.get(member.guild.roles, name=AUTO_ROLE_NAME)
            if role:
                await member.add_roles(role)

    @app_commands.command(name="выдать_роль", description="Выдать роль участнику")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def give_role(self, interaction: discord.Interaction, участник: discord.Member, роль: discord.Role):
        await участник.add_roles(роль)
        await interaction.response.send_message(f"✅ Роль {роль.mention} выдана {участник.mention}.")

    @app_commands.command(name="забрать_роль", description="Забрать роль у участника")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def remove_role(self, interaction: discord.Interaction, участник: discord.Member, роль: discord.Role):
        await участник.remove_roles(роль)
        await interaction.response.send_message(f"✅ Роль {роль.mention} забрана у {участник.mention}.")

    @app_commands.command(name="роль_по_реакции", description="Создать сообщение для выдачи роли по реакции")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reaction_role_setup(self, interaction: discord.Interaction, эмодзи: str, роль: discord.Role, текст: str):
        message = await interaction.channel.send(f"{текст}\n\nПоставь {эмодзи}, чтобы получить роль {роль.mention}")
        await message.add_reaction(эмодзи)
        REACTION_ROLE_MAP[message.id] = {эмодзи: роль.name}
        await interaction.response.send_message("✅ Сообщение для реакции-роли создано.", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id not in REACTION_ROLE_MAP:
            return
        emoji = str(payload.emoji)
        role_map = REACTION_ROLE_MAP[payload.message_id]
        if emoji not in role_map:
            return

        guild = self.bot.get_guild(payload.guild_id)
        role = discord.utils.get(guild.roles, name=role_map[emoji])
        member = guild.get_member(payload.user_id)
        if role and member and not member.bot:
            await member.add_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id not in REACTION_ROLE_MAP:
            return
        emoji = str(payload.emoji)
        role_map = REACTION_ROLE_MAP[payload.message_id]
        if emoji not in role_map:
            return

        guild = self.bot.get_guild(payload.guild_id)
        role = discord.utils.get(guild.roles, name=role_map[emoji])
        member = guild.get_member(payload.user_id)
        if role and member:
            await member.remove_roles(role)


async def setup(bot):
    await bot.add_cog(Roles(bot))
