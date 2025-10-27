import discord
from discord.ext import commands
import asyncio
import config

class Useradd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(aliases=["ua", "connect", "addme"])
    async def useradd(self, ctx):
        guild = ctx.guild
        member = ctx.author
        shell_role = discord.utils.get(guild.roles, name=config.SHELL_ACCESS_ROLE)

        if shell_role in member.roles:
            await ctx.send("you are already connected.")
            return
        
        await member.add_roles(shell_role)

        msg = await ctx.send(f"-# `[ .. ]` creating directory **/home/{member.name}**")
        await asyncio.sleep(2)

        await msg.edit(content=(
            f"-# `[ OK ]` directory **/home/{member.name}** created\n"
            f"-# `[ .. ]` creating user **{member.name}**"
        ))
        await asyncio.sleep(1)

        await msg.edit(content=(
            f"-# `[ OK ]` directory **/home/{member.name}** created\n"
            f"-# `[ OK ]` user **{member.name}** created\n"
            "-# `[ .. ]` connecting..."
        ))
        await asyncio.sleep(1)

        await msg.edit(content=(
            f"-# `[ OK ]` directory **/home/{member.name}** created\n"
            f"-# `[ OK ]` user **{member.name}** created\n"
            "-# `[ .. ]` connecting... .."
        ))
        await asyncio.sleep(1)

        await msg.edit(content=(
            f"-# `[ OK ]` directory **/home/{member.name}** created\n"
            f"-# `[ OK ]` user **{member.name}** created\n"
            "-# `[ .. ]` connecting... .. . ."
        ))
        await asyncio.sleep(5)

        await msg.edit(content=(
            f"-# `[ OK ]` directory **/home/{member.name}** created\n"
            f"-# `[ OK ]` user **{member.name}** created\n"
            "-# `[ .. ]` connecting... .. . .  .    ."
        ))
        await asyncio.sleep(1)

        await msg.edit(content=(
            f"-# `[ OK ]` directory **/home/{member.name}** created\n"
            f"-# `[ OK ]` user **{member.name}** created\n"
            "-# `[ OK ]` connected.\n"
            "// connected to **hazel / shell** successfully.\n"
            "-# `[ INFO ]` start your first session with `>hzsh`"
        ))

async def setup(bot):
    await bot.add_cog(Useradd(bot))
