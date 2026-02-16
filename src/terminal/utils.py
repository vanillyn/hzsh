import discord
from discord.ext import commands

import config
from src.misc import has_shell_access


class hzshUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="sh")
    async def sh(self, ctx, *, command: str):
        shell_cog = self.bot.get_cog("Shell")
        if not shell_cog:
            await ctx.send("shell system unavailable")
            return

        if not has_shell_access(ctx.author):
            await ctx.send(f"you are not connected to `{config.NAME}`.")
            return

        async with ctx.typing():
            result = await shell_cog.exec_cmd(
                ctx.author.name, str(ctx.author.id), command, ctx
            )

        if len(result) > 1900:
            result = result[:1900] + "\n... output truncated"

        await ctx.send(f"```ansi\n{result}\n```")

    @commands.command(name="cd")
    async def cd(self, ctx, *, path: str = "~"):
        shell_cog = self.bot.get_cog("Shell")
        if not shell_cog:
            await ctx.send("shell system unavailable")
            return

        if not has_shell_access(ctx.author):
            await ctx.send(f"you are not connected to `{config.NAME}`.")
            return

        username = ctx.author.name
        discord_id = str(ctx.author.id)
        shell_cog.ensure_home(username, discord_id)

        current = shell_cog.working_dirs.get(discord_id, f"/home/{username}")

        if path == "~":
            new_path = f"/home/{username}"
        elif path.startswith("/"):
            new_path = path
        else:
            new_path = f"{current}/{path}"

        result = await shell_cog.exec_cmd(
            username, discord_id, f"cd '{new_path}' && pwd"
        )

        if (
            "no such file or directory" not in result.lower()
            and "not a directory" not in result.lower()
        ):
            shell_cog.working_dirs[discord_id] = result.strip()
            await ctx.send(f"```\n{shell_cog.working_dirs[discord_id]}\n```")
        else:
            await ctx.send(f"```\n{result}\n```")

    @commands.command()
    async def pwd(self, ctx):
        shell_cog = self.bot.get_cog("Shell")
        if not shell_cog:
            await ctx.send("shell system unavailable")
            return

        shell_role = discord.utils.get(ctx.guild.roles, name=config.SHELL_ACCESS_ROLE)
        if not shell_role or shell_role not in ctx.author.roles:
            await ctx.send(f"you are not connected to `{config.NAME}`.")
            return

        discord_id = str(ctx.author.id)
        username = ctx.author.name
        wd = shell_cog.working_dirs.get(discord_id, f"/home/{username}")

        await ctx.send(f"```\n{wd}\n```")

    @commands.command(aliases=["who", "users", "online"])
    async def w(self, ctx):
        shell_cog = self.bot.get_cog("Shell")
        if not shell_cog:
            await ctx.send("shell system unavailable")
            return

        shell_role = discord.utils.get(ctx.guild.roles, name=config.SHELL_ACCESS_ROLE)
        if not shell_role:
            await ctx.send("no users connected")
            return

        connected = [m for m in ctx.guild.members if shell_role in m.roles]
        active_sessions = shell_cog.sessions

        if not connected:
            await ctx.send("no users connected")
            return

        msg = f"connected users [{len(connected)}]\n"
        msg += f"active sessions: {len(active_sessions)}\n\n"
        msg += f"{'status':<8} {'user':<20} {'directory'}\n"
        msg += "-" * 60 + "\n"

        for member in connected:
            status = "active" if str(member.id) in active_sessions else "idle"
            wd = shell_cog.working_dirs.get(str(member.id), f"/home/{member.name}")
            msg += f"{status:<8} {member.name:<20} {wd}\n"

        await ctx.send(f"```\n{msg}```")


async def setup(bot):
    await bot.add_cog(hzshUtils(bot))
