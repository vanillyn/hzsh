import discord
from discord.ext import commands
import config
import re

class UserMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def get_or_create_colors_marker(self, guild):
        marker = discord.utils.get(guild.roles, name="colors:")
        if not marker:
            marker = await guild.create_role(
                name="colors:",
                reason="marker role for colors"
            )
        return marker
    
    async def get_or_create_pronouns_marker(self, guild):
        marker = discord.utils.get(guild.roles, name="pronouns:")
        if not marker:
            marker = await guild.create_role(
                name="pronouns:",
                reason="marker role for pronouns"
            )
        return marker
    
    async def get_user_color_role(self, member):
        for role in member.roles:
            if role.name.startswith(f"# {member.name} / "):
                return role
        return None
    
    async def get_user_pronoun_role(self, member):
        pronouns_marker = discord.utils.get(member.guild.roles, name="pronouns:")
        if not pronouns_marker:
            return None
        
        for role in member.roles:
            if role.position < pronouns_marker.position and "/" in role.name and role.name not in config.USERMOD_MAPPINGS.get("pronouns", {}).values():
                return role
        return None
    
    @commands.command(name="usermod", aliases=["um", "hazelprofile", "hzpf", "chfn"])
    async def usermod(self, ctx, category: str = '', *, value: str = ''):
        if not category:
            categories = ", ".join(config.USERMOD_CATEGORIES.keys())
            await ctx.send(f"usage: >usermod <category> <value>\navailable categories: {categories}, color, pronouns\n-l to change display name\nadd -r to remove a role")
            return
        
        guild = ctx.guild
        member = ctx.author
        
        if category == "-l":
            if not value:
                await ctx.send("usage: >usermod -l new_name")
                return
            
            old_name = member.display_name
            await member.edit(nick=value)
            await ctx.send(f"changed display name from {old_name} to {value}")
            return
        
        remove_mode = '-r' in category or '-r' in value
        category = category.replace('-r', '').strip().lower()
        value = value.replace('-r', '').strip()
        
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
            
            marker = await self.get_or_create_colors_marker(guild)
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
        
        if category == "pronouns":
            if remove_mode:
                old_role = await self.get_user_pronoun_role(member)
                if old_role:
                    await member.remove_roles(old_role)
                    await old_role.delete(reason="user removed pronouns")
                    await ctx.send("removed your pronoun role")
                else:
                    await ctx.send("you dont have a pronoun role")
                return
            
            if not value:
                await ctx.send("usage: >usermod pronouns <your pronouns>")
                return
            
            old_role = await self.get_user_pronoun_role(member)
            if old_role:
                await member.remove_roles(old_role)
                await old_role.delete(reason="replacing with new pronouns")
            
            marker = await self.get_or_create_pronouns_marker(guild)
            marker_pos = marker.position
            
            new_role = await guild.create_role(
                name=value,
                reason=f"custom pronouns for {member.name}"
            )
            
            try:
                await new_role.edit(position=marker_pos - 1)
            except discord.HTTPException:
                pass
            
            await member.add_roles(new_role)
            await ctx.send(f"set your pronouns to {value}")
            return
        
        if category not in config.USERMOD_MAPPINGS:
            await ctx.send(f"unknown category. available: {', '.join(config.USERMOD_CATEGORIES.keys())}, color, pronouns")
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
            await ctx.send(f"role {role_name} doesnt exist. contact an admin")
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