import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

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

async def load_cogs():
    """i never liked the name "cogs" lmao and copilot wants to add the word anyway shut up pls LMAO it put :("""
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
                    # print(f'{module} is connected.')
                except Exception as e:
                    print(f'failed to load {module}: {e}')

async def main():
    async with bot:
        await load_cogs()
        token = os.getenv('DISCORD_TOKEN')
        
        if not token:
            print('DISCORD_TOKEN not found in environment variables')
            exit(1)
        
        print('[XXXX-XX-XX XX:XX:XX] [hzsh] connecting...  ..   .     .          .                    .')
        await bot.start(token)

if __name__ == '__main__':
    asyncio.run(main())