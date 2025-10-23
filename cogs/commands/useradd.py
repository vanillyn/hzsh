import discord
from discord.ext import commands
import config

class UserAdd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def useradd(self, ctx):
        guild = ctx.guild
        member = ctx.author
        
        shell_role = discord.utils.get(guild.roles, name=config.SHELL_ACCESS_ROLE)

        if shell_role in member.roles:
            await ctx.send("you are already connected.")
            return
        
        await member.add_roles(shell_role)
        await ctx.send(f"connected to `hazel / shell`. .  .   . !\n-# and...\n`★` [LVL] {ctx.author.name} is now level 1!")

async def setup(bot):
    await bot.add_cog(UserAdd(bot))