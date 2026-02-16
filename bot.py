import asyncio
import logging
import os
import platform
import random

import discord
import psutil
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = True

bot = commands.Bot(command_prefix=">", intents=intents, help_command=None)


def get_status():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    memory_usage = memory.percent
    system = platform.system()
    release = platform.release()

    return [
        f"using {cpu_usage}% cpu",
        f"using {memory_usage}% memory",
        f"kernel: {system} {release}",
        "listening to journalctl",
        "playing in the terminal",
        "watching system resources",
        "super rare status!",
        "the very best discord server",
    ]


@tasks.loop(minutes=10)
async def rotate_status():
    STATUS_LIST = get_status()
    status = random.choice(STATUS_LIST)
    activity_type = discord.ActivityType.playing
    activity = discord.Activity(type=activity_type, name=status)
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
        "src.terminal.utils",
        "src.commands.guides",
        "src.commands.alias",
        "src.commands.help",
        "src.commands.man",
        "src.commands.usermod",
        "src.commands.wikipedia",
        "src.commands.cookies",
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
