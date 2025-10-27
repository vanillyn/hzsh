import discord
from discord.ext import commands
import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import sys

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.setup_logging()
        self.bot_log = 1430975054518288504
        
    def setup_logging(self):
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        logger = logging.getLogger('discord_bot')
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(self.colored_formatter())
        
        file_handler = RotatingFileHandler(
            'logs/bot.log',
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        
        error_handler = RotatingFileHandler(
            'logs/errors.log',
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_format)
        
        logger.addHandler(console)
        logger.addHandler(file_handler)
        logger.addHandler(error_handler)

        discord_logger = logging.getLogger('discord')
        discord_logger.setLevel(logging.INFO)
        discord_logger.handlers.clear()
        discord_logger.addHandler(file_handler)
        discord_logger.addHandler(error_handler)
        
        return logger
    
    def colored_formatter(self):
        class ColoredFormatter(logging.Formatter):
            grey = '\x1b[38;21m'
            blue = '\x1b[38;5;39m'
            yellow = '\x1b[38;5;226m'
            red = '\x1b[38;5;196m'
            bold_red = '\x1b[31;1m'
            reset = '\x1b[0m'
            
            def __init__(self):
                super().__init__()
                fmt = '[%(asctime)s] [%(levelname)s] %(message)s'
                self.formats = {
                    logging.DEBUG: self.grey + fmt + self.reset,
                    logging.INFO: self.blue + fmt + self.reset,
                    logging.WARNING: self.yellow + fmt + self.reset,
                    logging.ERROR: self.red + fmt + self.reset,
                    logging.CRITICAL: self.bold_red + fmt + self.reset
                }
            
            def format(self, record):
                log_fmt = self.formats.get(record.levelno)
                formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
                return formatter.format(record)
        
        return ColoredFormatter()
    
    async def log_to_channel(self, message, level="INFO"):
        # log important events to discord channel
        channel = self.bot.get_channel(self.bot_log)
        if not channel:
            return
        
        timestamp = discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        log_msg = f"```\n[{timestamp}] [{level}] {message}\n```"
        
        try:
            await channel.send(log_msg)
        except Exception:
            pass
    
    def get_container_users(self):
        try:
            result = subprocess.run([
                "docker", "exec", "hzsh_linux",
                "bash", "-c", "getent passwd | awk -F: '$3 >= 1000 {print $1}'"
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                return [u for u in result.stdout.strip().split('\n') if u]
            return []
        except Exception:
            return []
    
    def get_container_kernel(self):
        try:
            result = subprocess.run([
                "docker", "exec", "hzsh_linux", "uname", "-r"
            ], capture_output=True, text=True, timeout=5)
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info('hazel / shell ver 1.0 connected.')
        
        latency = round(self.bot.latency * 1000)
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        kernel_version = self.get_container_kernel()
        users = self.get_container_users()
        
        startup_msg = "bot startup\n"
        startup_msg += f"latency: {latency}ms\n"
        startup_msg += f"python: {python_version}\n"
        startup_msg += f"container kernel: {kernel_version}\n"
        startup_msg += f"users in container: {len(users)}\n"
        
        if users:
            startup_msg += f"user list: {', '.join(users)}"
        
        await self.log_to_channel(startup_msg, "STARTUP")
    
    @commands.Cog.listener()
    async def on_command(self, ctx):
        cmd_msg = f"command: {ctx.command.name}\n"
        cmd_msg += f"user: {ctx.author.name} ({ctx.author.id})\n"
        cmd_msg += f"channel: {ctx.channel.name if hasattr(ctx.channel, 'name') else 'dm'}\n"
        cmd_msg += f"content: {ctx.message.content}"
        
        await self.log_to_channel(cmd_msg, "COMMAND")
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        self.logger.error(f'error in command {ctx.command}: {str(error)}', exc_info=error)
        
        error_msg = f"command error: {ctx.command.name if ctx.command else 'unknown'}\n"
        error_msg += f"user: {ctx.author.name} ({ctx.author.id})\n"
        error_msg += f"error: {str(error)}"
        
        await self.log_to_channel(error_msg, "ERROR")
        
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send('you lack the required permissions...')
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'i need a {error.param.name}...')
        elif isinstance(error, commands.BadArgument):
            await ctx.send('what do i do with this...')
        else:
            await ctx.send('something went wrong... <@1033539983161708554>')
            self.logger.exception(f'unhandled error in {ctx.command}')
    
    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        self.logger.exception(f'{event} / ')
        await self.log_to_channel(f"event error: {event}", "ERROR")
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        join_msg = "user connected\n"
        join_msg += f"user: {member.name} ({member.id})\n"
        join_msg += f"account created: {member.created_at.strftime('%Y-%m-%d')}"
        
        await self.log_to_channel(join_msg, "JOIN")
        
        channel = member.guild.get_channel(1429677645783764994)
        if channel:
            await channel.send(
                f"`→` {member.mention} connected to hazel / run\n"
                f"-# process id: {member.id}"
            )
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        leave_msg = "user disconnected\n"
        leave_msg += f"user: {member.name} ({member.id})\n"
        leave_msg += f"roles: {', '.join([r.name for r in member.roles if r.name != '@everyone'])}"
        
        await self.log_to_channel(leave_msg, "LEAVE")
        
        channel = member.guild.get_channel(1429677645783764994)
        if channel:
            await channel.send(
                f"`←` {member.name} disconnected from hazel / run\n"
                f"-# process terminated: {member.id}"
            )
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.premium_since is None and after.premium_since is not None:
            boost_msg = "server boosted\n"
            boost_msg += f"user: {after.name} ({after.id})\n"
            boost_msg += f"boost time: {after.premium_since.strftime('%Y-%m-%d %H:%M:%S')}"
            
            await self.log_to_channel(boost_msg, "BOOST")
            
            channel = after.guild.get_channel(1429677645783764994)
            if channel:
                await channel.send(
                    f"`★` {after.mention} gave us a boost...\n"
                    f"-# resource allocation increased"
                )

async def setup(bot):
    await bot.add_cog(Logger(bot))