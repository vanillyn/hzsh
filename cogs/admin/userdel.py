import discord
from discord.ext import commands
import config

class UserDel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def userdel(self, ctx, member: discord.Member):
        shell_role = discord.utils.get(ctx.guild.roles, name=config.SHELL_ACCESS_ROLE)
        
        if shell_role not in member.roles:
            await ctx.send(f"{member.mention} doesnt have shell access")
            return
        
        await member.remove_roles(shell_role)
        await ctx.send(f"revoked shell access from {member.mention}")

async def setup(bot):
    await bot.add_cog(UserDel(bot))