from discord.ext import commands

import config
from src.misc import is_staff


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["commands", "cmds", "h", "?"])
    async def help(self, ctx):
        msg = f"**`{config.NAME}`**\n-# ver {config.VERSION}\n\n"

        msg += "**shell**\n"
        msg += f"`>connect` - connect to {config.NAME}\n"
        msg += "`>hzsh` - run the shell\n"
        msg += "`>fetch [--os|--kernel|--host|--uptime|--cpu|--memory|--disk|--user|--stats|--all]`\n\n"

        msg += "**wiki**\n"
        msg += "`>aw|gw|man [query]` - linux wiki or manual\n"
        msg += (
            "`>wp [query] (-t type) (-l lang) (-i bool) (--link bool)` - wikipedia\n\n"
        )

        msg += "**moderation**\n"
        if is_staff(ctx.author):
            msg += "`>ban {-d dur} {-q|-s|-p} [@user] {res}`\n"
            msg += "`>kick [@user] {res}`\n"
            msg += "`>mute [-d dur] {-s} [@user] {res}`\n"
            msg += "`>warn [@user] [res]`\n"
            msg += "`>userinfo [@user]`\n"
            msg += "`>pardon [@user] [-b|-m|-r] {res}`\n"
            msg += "`>slowmode [duration]`\n"
            msg += "`>tickets archive [name]`\n"
        msg += "`>tickets new [name] {@extra}`\n"
        msg += "`>tickets remove [name]`\n"
        msg += "`>tickets modify [name] [(add/remove)(rename)] [target]`\n\n"

        msg += "**social**\n"
        msg += "`>achievements -a|-v` - view achievements\n"
        msg += '`>alias [-a|-r|-e|-L] [-n name] [-c "content"]` - manage aliases\n'

        await ctx.send(msg)


async def setup(bot):
    await bot.add_cog(Help(bot))
