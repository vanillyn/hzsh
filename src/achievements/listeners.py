from discord.ext import commands

import config
from src.achievements.utils import get_achievement_system
from src.misc import CogHelper


class Achievements(CogHelper, commands.Cog):
    """achievement event listeners"""

    def __init__(self, bot):
        super().__init__(bot)
        self.ach_system = get_achievement_system()

    @commands.Cog.listener()
    async def on_message(self, message):
        """check message-based achievements"""
        if message.author.bot or not message.guild:
            return

        if message.guild.id == config.GUILD_ID:
            await self.ach_system.check_message_achievements(
                str(message.author.id), message.content, message.guild
            )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """check achievements on member join"""
        if member.guild.id == config.GUILD_ID:
            await self.check_mutual_servers(member)

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        """check presence-based achievements"""
        if after.guild.id != config.GUILD_ID:
            return

        if before.activities != after.activities:
            for activity in after.activities:
                await self.ach_system.check_presence_achievements(after, activity)

    async def check_mutual_servers(self, member):
        """check if user is in both servers for neopolita achievement"""
        if not self.ach_system.has_achievement(member.id, "neopolita"):
            other_guild = self.bot.get_guild(config.NEO_POLITA)
            if other_guild and other_guild.get_member(member.id):
                await self.ach_system.grant_achievement(
                    str(member.id), "neopolita", member.guild, None
                )
                self.log_info(f"neopolita achievement granted to {member.id}")


async def setup(bot):
    await bot.add_cog(Achievements(bot))
