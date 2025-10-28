from discord.ext import commands
import config

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(aliases=['commands', 'cmds', 'h', '?'])
    async def help(self, ctx):
        msg = f"**`{config.NAME}`**\n-# ver {config.VERSION}\n\n"
        msg += f"`>connect` - connect to {config.NAME}\n"
        msg += "`>aw|gw|man [query]` - show information from a linux wiki or manual\n"
        msg += "`>achievements (-u user)` - view achievements\n"
        msg += "`>wp [query] (-t text|embed|container) (-l language) (-i bool) (--link bool) (-s query)` - show content from wikipedia\n"
        msg += "`>leaderboard` - xp leaderboard\n"
        msg += "`>alias [-a|-r|-e|-L] [-n name] [-c \"content\"] [-l language] [-N new_name] - add and manage aliases\n"
        
        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(Help(bot))