import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import asyncio
import random

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix='>',
    intents=intents,
    help_command=None
)

STATUS_LIST = [
    {"type": "playing", "name": "in Arch Linux"},
    {"type": "playing", "name": "with /dev/null"},
    {"type": "playing", "name": "in the terminal"},
    {"type": "listening", "name": "kernel messages"},
    {"type": "listening", "name": "system calls"},
    {"type": "listening", "name": "grep output"},
    {"type": "watching", "name": "processes"},
    {"type": "watching", "name": "/var/log"},
    {"type": "watching", "name": "system resources"},
]

@tasks.loop(minutes=10)
async def rotate_status():
    status = random.choice(STATUS_LIST)
    
    activity_type = {
        "playing": discord.ActivityType.playing,
        "listening": discord.ActivityType.listening,
        "watching": discord.ActivityType.watching,
    }.get(status["type"], discord.ActivityType.playing)
    print(f'\x1b[38;21m[{discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] [STATUS] {status["type"]} {status["name"]}\x1b[0m')
    activity = discord.Activity(type=activity_type, name=status["name"])
    await bot.change_presence(activity=activity, status=discord.Status.idle)

async def load_cogs():
    import os
    from pathlib import Path
    
    cogs_dir = Path('cogs')
    
    if not cogs_dir.exists():
        print('cogs directory not found')
        return
    
    for root, dirs, files in os.walk(cogs_dir):
        for file in files:
            if file.endswith('.py') and not file.startswith('_'):
                path = Path(root) / file[:-3]
                module = str(path).replace(os.sep, '.')
                
                try:
                    await bot.load_extension(module)
                except Exception as e:
                    print(f'failed to load {module}: {e}')

async def main():
    async with bot:
        await load_cogs()
        token = os.getenv('DISCORD_TOKEN')
        
        if not token:
            print('DISCORD_TOKEN not found in environment variables')
            exit(1)
        
        print('[XXXX-XX-XX XX:XX:XX] [HZSH] connecting...  ..   .     .          .                    .')
        
        @bot.event
        async def on_ready():
            if not rotate_status.is_running():
                rotate_status.start()
        
        await bot.start(token)

if __name__ == '__main__':
    asyncio.run(main())