import discord
from discord.ext import commands
import logging
from logging.handlers import RotatingFileHandler
import os

class ColoredFormatter(logging.Formatter):
    grey = '\x1b[38;21m'
    blue = '\x1b[38;5;39m'
    yellow = '\x1b[38;5;226m'
    red = '\x1b[38;5;196m'
    bold_red = '\x1b[31;1m'
    reset = '\x1b[0m'
    
    def __init__(self, fmt):
        super().__init__()
        self.fmt = fmt
        self.FORMATS = {
            logging.DEBUG: self.grey + self.fmt + self.reset,
            logging.INFO: self.blue + self.fmt + self.reset,
            logging.WARNING: self.yellow + self.fmt + self.reset,
            logging.ERROR: self.red + self.fmt + self.reset,
            logging.CRITICAL: self.bold_red + self.fmt + self.reset
        }
    
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.setup_logging()
        
    def setup_logging(self):
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        logger = logging.getLogger('discord_bot')
        logger.setLevel(logging.DEBUG)
        
        logger.handlers.clear()
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredFormatter('[%(asctime)s] [%(levelname)s] %(message)s'))
        
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
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.addHandler(error_handler)

        discord_logger = logging.getLogger('discord')
        discord_logger.setLevel(logging.INFO)
        discord_logger.handlers.clear()
        discord_logger.addHandler(file_handler)
        discord_logger.addHandler(error_handler)
        
        return logger
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info('hazel / shell ver 0.1-pre connected.')
        
        await self.bot.change_presence(
            activity=discord.Game(name="in the shell."),
            status=discord.Status.online
        )
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        self.logger.error(f'Hey boss someone messed up, {ctx.command}: {str(error)}', exc_info=error)
        
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send('Hey! Don\'t do that! I didn\'t give you permission!')
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'H-hey.. you forgot {error.param.name}...')
        elif isinstance(error, commands.BadArgument):
            await ctx.send('I don\'t know what to do with this...!')
        else:
            await ctx.send('I\'m sorry...')
            self.logger.exception(f'unhandled error in {ctx.command}')
    
    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        self.logger.exception(f'{event} / ')

async def setup(bot):
    await bot.add_cog(Logging(bot))