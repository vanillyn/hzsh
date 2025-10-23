import discord
from discord.ext import commands
import config

class UserMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    async def usermod(self, ctx, category: str = ' ', *, value: str = ' '):
        if not category or not value:
            categories = ", ".join(config.USERMOD_CATEGORIES.keys())
            await ctx.send(f"usage: >usermod <category> <value>\navailable categories: {categories}")
            return
        
        category = category.lower()
        value = value.lower().strip()
        
        if category not in config.USERMOD_MAPPINGS:
            await ctx.send(f"unknown category. available: {', '.join(config.USERMOD_CATEGORIES.keys())}")
            return
        
        if value not in config.USERMOD_MAPPINGS[category]:
            available = ", ".join(set(config.USERMOD_MAPPINGS[category].values()))
            await ctx.send(f"unknown value for {category}. available: {available}")
            return
        
        role_name = config.USERMOD_MAPPINGS[category][value]
        guild = ctx.guild
        member = ctx.author
        
        existing_roles = [
            role for role in member.roles 
            if role.name in config.USERMOD_MAPPINGS[category].values()
        ]
        
        target_role = discord.utils.get(guild.roles, name=role_name)
        
        if not target_role:
            target_role = await guild.create_role(
                name=role_name,
                reason=f"{config.USERMOD_CATEGORIES[category]} role created automatically"
            )
        
        if target_role in member.roles:
            await ctx.send(f"you already have the {role_name} role")
            return
        
        if existing_roles:
            await member.remove_roles(*existing_roles)
        
        await member.add_roles(target_role)
        await ctx.send(f"updated {config.USERMOD_CATEGORIES[category]} to {role_name}")

async def setup(bot):
    await bot.add_cog(UserMod(bot))