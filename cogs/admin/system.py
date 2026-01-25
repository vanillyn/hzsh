import discord
from discord.ext import commands, tasks
import subprocess
from pathlib import Path
from datetime import datetime
import shutil


class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = (
            self.bot.get_cog("Logging").logger if self.bot.get_cog("Logging") else None
        )
        self.container = "hzsh_linux"
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)

        self.cleanup_sessions.start()
        self.health_check.start()
        self.auto_backup.start()

    async def cog_unload(self):
        self.cleanup_sessions.cancel()
        self.health_check.cancel()
        self.auto_backup.cancel()

    def is_root(self, member):
        return discord.utils.get(member.roles, name="root@hazelrun") is not None

    async def check_container_health(self):
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", self.container],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and "true" in result.stdout
        except Exception:
            return False

    @tasks.loop(minutes=30)
    async def cleanup_sessions(self):
        shell_cog = self.bot.get_cog("Shell")
        if not shell_cog:
            return

        to_remove = []
        for discord_id, session in shell_cog.sessions.items():
            if not session["active"]:
                to_remove.append(discord_id)
                continue

            process = session.get("process")
            if process and process.returncode is not None:
                to_remove.append(discord_id)

        for discord_id in to_remove:
            if self.logger:
                self.logger.info(f"cleaning up stale session for {discord_id}")
            del shell_cog.sessions[discord_id]

    @tasks.loop(minutes=5)
    async def health_check(self):
        healthy = await self.check_container_health()

        if not healthy and self.logger:
            self.logger.error("container health check failed")

            mod_cog = self.bot.get_cog("Moderation")
            if mod_cog:
                channel = self.bot.get_channel(mod_cog.bot_log_channel)
                if channel:
                    await channel.send(
                        "```\ncontainer health check failed\ncontainer may be down or unresponsive\n```"
                    )

    @tasks.loop(hours=6)
    async def auto_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(exist_ok=True)

        try:
            data_dir = Path("data")
            if data_dir.exists():
                shutil.copytree(data_dir, backup_path / "data")

            old_backups = sorted(self.backup_dir.glob("backup_*"))
            if len(old_backups) > 10:
                for old in old_backups[:-10]:
                    shutil.rmtree(old)

            if self.logger:
                self.logger.info(f"backup created: {backup_path}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"backup failed: {e}")

    @cleanup_sessions.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    @health_check.before_loop
    async def before_health(self):
        await self.bot.wait_until_ready()

    @auto_backup.before_loop
    async def before_backup(self):
        await self.bot.wait_until_ready()

    @commands.command()
    async def reload(self, ctx, cog: str):
        if not self.is_root(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        try:
            await self.bot.reload_extension(cog)
            await ctx.send(f"reloaded {cog}")

            if self.logger:
                self.logger.info(f"cog reloaded: {cog} by {ctx.author.name}")

        except Exception as e:
            await ctx.send(f"failed to reload: {str(e)}")

    @commands.command()
    async def quota(self, ctx, member: discord.Member):
        target = member or ctx.author

        shell_cog = self.bot.get_cog("Shell")
        if not shell_cog:
            await ctx.send("shell system unavailable")
            return

        try:
            result = subprocess.run(
                ["docker", "exec", self.container, "du", "-sh", f"/home/{target.name}"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                size = result.stdout.split()[0]
                await ctx.send(f"```\n{target.name}: {size} used\n```")
            else:
                await ctx.send("failed to check quota")

        except Exception as e:
            await ctx.send(f"error: {str(e)}")

    @commands.command()
    async def backup(self, ctx):
        if not self.is_root(ctx.author):
            await ctx.send("you lack the required permissions")
            return

        async with ctx.typing():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"manual_{timestamp}"
            backup_path.mkdir(exist_ok=True)

            try:
                data_dir = Path("data")
                if data_dir.exists():
                    shutil.copytree(data_dir, backup_path / "data")

                await ctx.send(f"backup created: {backup_path.name}")

                if self.logger:
                    self.logger.info(f"manual backup by {ctx.author.name}")

            except Exception as e:
                await ctx.send(f"backup failed: {str(e)}")

    @commands.command()
    async def health(self, ctx):
        healthy = await self.check_container_health()

        shell_cog = self.bot.get_cog("Shell")
        active_sessions = len(shell_cog.sessions) if shell_cog else 0

        msg = "system health\n"
        msg += f"container: {'running' if healthy else 'down'}\n"
        msg += f"active sessions: {active_sessions}\n"
        msg += f"latency: {round(self.bot.latency * 1000)}ms\n"

        try:
            result = subprocess.run(
                ["docker", "exec", self.container, "df", "-h", "/home"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        msg += f"disk: {parts[4]} used\n"
        except Exception:
            pass

        await ctx.send(f"```\n{msg}```")


async def setup(bot):
    await bot.add_cog(System(bot))
