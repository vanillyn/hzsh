import discord
from discord.ext import commands
from datetime import datetime, timedelta
from collections import defaultdict

class RateLimit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.command_usage = defaultdict(lambda: defaultdict(list))
        
        self.limits = {
            "sh": (5, 60),
            "wp": (10, 120),
            "man": (10, 120),
            "aw": (10, 120),
            "gw": (10, 120),
            "hazelfetch": (10, 300),
        }
    
    def check_limit(self, user_id, command_name):
        if command_name not in self.limits:
            return True
        
        max_uses, window = self.limits[command_name]
        now = datetime.now()
        cutoff = now - timedelta(seconds=window)
        
        recent = [t for t in self.command_usage[user_id][command_name] if t > cutoff]
        self.command_usage[user_id][command_name] = recent
        
        if len(recent) >= max_uses:
            return False
        
        self.command_usage[user_id][command_name].append(now)
        return True
    
    def get_cooldown(self, user_id, command_name):
        if command_name not in self.limits:
            return 0
        
        max_uses, window = self.limits[command_name]
        recent = self.command_usage[user_id][command_name]
        
        if not recent:
            return 0
        
        oldest = min(recent)
        now = datetime.now()
        elapsed = (now - oldest).total_seconds()
        
        return max(0, window - elapsed)
    
    @commands.Cog.listener()
    async def on_command(self, ctx):
        if ctx.author.bot:
            return
        
        staff_role = discord.utils.get(ctx.author.roles, name="staff@hazelrun")
        if staff_role:
            return
        
        command_name = ctx.command.name
        
        if not self.check_limit(ctx.author.id, command_name):
            cooldown = self.get_cooldown(ctx.author.id, command_name)
            await ctx.send(f"rate limit exceeded. try again in {int(cooldown)} seconds")
            raise commands.CommandError("rate limited")

async def setup(bot):
    await bot.add_cog(RateLimit(bot))