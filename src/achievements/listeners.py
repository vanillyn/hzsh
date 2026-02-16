from discord.ext import commands

import config
from src.achievements.utils import get_achievement_system
from src.misc import CogHelper


class Achievements(CogHelper, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.ach_system = get_achievement_system()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if message.guild.id == config.GUILD_ID:
            await self.ach_system.check_message_achievements(
                str(message.author.id), message.content, message.guild, message.channel
            )
            await self.ach_system.check_inactivity_achievement(
                str(message.author.id), message.guild
            )

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        if thread.guild.id != config.GUILD_ID:
            return

        if not thread.parent or not hasattr(thread.parent, "type"):
            return

        import discord

        if thread.parent.type == discord.ChannelType.forum:
            starter_message = None
            async for msg in thread.history(limit=1, oldest_first=True):
                starter_message = msg
                break

            if starter_message and starter_message.author:
                await self.ach_system.check_forum_achievements(
                    str(starter_message.author.id), thread.parent.id, thread.guild
                )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id != config.GUILD_ID or payload.member.bot:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        await self.ach_system.check_reaction_achievements(
            str(payload.user_id), payload.emoji, guild
        )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id == config.GUILD_ID:
            await self.check_mutual_servers(member)

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if after.guild.id != config.GUILD_ID:
            return

        if before.activities != after.activities:
            await self.ach_system.check_presence_achievements(
                str(after.id), after, after.guild
            )

    async def check_mutual_servers(self, member):
        if not self.ach_system.has_achievement(str(member.id), "neopolita"):
            other_guild = self.bot.get_guild(config.NEO_POLITA)
            if other_guild and other_guild.get_member(member.id):
                await self.ach_system.grant_achievement(
                    str(member.id), "neopolita", member.guild, None
                )
                self.log_info(f"neopolita achievement granted to {member.id}")

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return

        other_guild = self.bot.get_guild(config.NEO_POLITA)
        if not other_guild:
            return

        for member in guild.members:
            if not member.bot and not self.ach_system.has_achievement(
                str(member.id), "neopolita"
            ):
                if other_guild.get_member(member.id):
                    await self.ach_system.grant_achievement(
                        str(member.id), "neopolita", guild, None
                    )
                    self.log_info(
                        f"neopolita achievement granted to {member.id} (existing member)"
                    )


async def setup(bot):
    await bot.add_cog(Achievements(bot))
