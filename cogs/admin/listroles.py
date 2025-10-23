from discord.ext import commands

class RoleLister(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="lsgroup")
    @commands.has_permissions(manage_roles=True)
    async def list_roles(self, ctx):
        if not ctx.guild.me.guild_permissions.manage_roles:
            await ctx.send("i lack the manage roles permission, mortal")
            return

        roles = ctx.guild.roles
        role_names = [r.name for r in roles if r.name != "@everyone"]

        msg = "\n".join(role_names)
        if len(msg) > 2000:
            await ctx.send("noooo")
        else:
            await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(RoleLister(bot))
