import discord
from discord.ext import commands
import config
import re

class UserMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def get_user_color_role(self, member):
        for role in member.roles:
            if role.name.startswith(f"# {member.name} / "):
                return role
        return None
    
    @commands.command(name="usermod", aliases=["um", "hazelprofile", "hzpf", "chfn"])
    async def usermod(self, ctx, category: str = '', *, value: str = ''):
        if not category or not value:
            categories = ", ".join(config.USERMOD_CATEGORIES.keys())
            await ctx.send(f"usage: >usermod <category> <value>\navailable categories: {categories}, color\nadd -r to remove a role")
            return
        
        remove_mode = '-r' in category or '-r' in value
        category = category.replace('-r', '').strip().lower()
        value = value.replace('-r', '').strip()
        
        guild = ctx.guild
        member = ctx.author
        
        if category == "color" or category == "colour":
            if remove_mode:
                old_role = await self.get_user_color_role(member)
                if old_role:
                    await member.remove_roles(old_role)
                    await old_role.delete(reason="user removed color")
                    await ctx.send("removed your color role")
                else:
                    await ctx.send("you dont have a color role")
                return
            
            hex_match = re.match(r'^#?([0-9a-fA-F]{6})$', value)
            if not hex_match:
                await ctx.send("invalid hex color. use format: #xxxxxx or xxxxxx")
                return
            
            hex_code = hex_match.group(1).upper()
            color_value = int(hex_code, 16)
            
            old_role = await self.get_user_color_role(member)
            if old_role:
                await member.remove_roles(old_role)
                await old_role.delete(reason="replacing with new color")
            
            marker = discord.utils.get(guild.roles, name="colors:")
            if not marker:
                await ctx.send("colors marker role not found")
                return
            
            marker_pos = marker.position
            
            new_role = await guild.create_role(
                name=f"# {member.name} / {hex_code}",
                color=discord.Color(color_value),
                reason=f"custom color for {member.name}"
            )
            
            try:
                await new_role.edit(position=marker_pos - 1)
            except discord.HTTPException:
                pass
            
            await member.add_roles(new_role)
            await ctx.send(f"set your color to #{hex_code}")
            return
        
        if category not in config.USERMOD_MAPPINGS:
            await ctx.send(f"unknown category. available: {', '.join(config.USERMOD_CATEGORIES.keys())}, color")
            return
        
        value_lower = value.lower()
        
        if value_lower not in config.USERMOD_MAPPINGS[category]:
            available = ", ".join(set(config.USERMOD_MAPPINGS[category].values()))
            await ctx.send(f"unknown value for {category}. available: {available}")
            return
        
        role_name = config.USERMOD_MAPPINGS[category][value_lower]
        
        existing_roles = [
            role for role in member.roles 
            if role.name in config.USERMOD_MAPPINGS[category].values()
        ]
        
        target_role = discord.utils.get(guild.roles, name=role_name)
        
        if not target_role:
            await ctx.send(f"role {role_name} not found")
            return
        
        if remove_mode:
            if target_role in member.roles:
                await member.remove_roles(target_role)
                await ctx.send(f"removed {role_name}")
            else:
                await ctx.send(f"you dont have the {role_name} role")
            return
        
        if target_role in member.roles:
            await ctx.send(f"you already have the {role_name} role")
            return
        
        if category == "ping":
            await member.add_roles(target_role)
            await ctx.send(f"added {role_name}")
        else:
            if existing_roles:
                await member.remove_roles(*existing_roles)
            
            await member.add_roles(target_role)
            await ctx.send(f"updated {config.USERMOD_CATEGORIES[category]} to {role_name}")

async def setup(bot):
    await bot.add_cog(UserMod(bot))