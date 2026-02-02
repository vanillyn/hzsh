import asyncio
import logging
import os
import random

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = True

bot = commands.Bot(command_prefix=">", intents=intents, help_command=None)

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

    activity = discord.Activity(type=activity_type, name=status["name"])
    await bot.change_presence(activity=activity, status=discord.Status.idle)


@rotate_status.before_loop
async def before_rotate_status():
    await bot.wait_until_ready()


async def load_cogs():
    cogs_to_load = [
        "src.achievements.commands",
        "src.achievements.listeners",
        "src.terminal.shell",
        "src.terminal.connect",
        "src.terminal.fetch",
        "src.commands.alias",
        "src.commands.help",
        "src.commands.man",
        "src.commands.usermod",
        "src.commands.wikipedia",
        "src.moderation.commands",
        "src.moderation.tickets",
        "src.moderation.userinfo",
        "src.misc.limits",
        "src.misc.logging",
    ]

    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            print(f"[ OK ] loaded {cog}")
        except Exception as e:
            print(f"[FAIL] {cog}: {e}")


async def main():
    async with bot:
        await load_cogs()
        rotate_status.start()

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            logging.error("DISCORD_TOKEN not found")
            exit(1)

        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
