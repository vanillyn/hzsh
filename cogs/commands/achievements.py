import discord
from discord.ext import commands
import config
import json
from pathlib import Path

class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = Path("data/achievements.json")
        self.xp_file = Path("data/xp.json")
        self.data_file.parent.mkdir(exist_ok=True)
        
        self.user_achievements = self.load_data()
        self.user_xp = self.load_xp()
        self.logger = self.bot.get_cog("Logging").logger if self.bot.get_cog("Logging") else None
    
    def load_data(self):
        if self.data_file.exists():
            with open(self.data_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.user_achievements, f, indent=2)
    
    def load_xp(self):
        if self.xp_file.exists():
            with open(self.xp_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_xp(self):
        with open(self.xp_file, 'w') as f:
            json.dump(self.user_xp, f, indent=2)
    
    def get_user_level(self, xp):
        level = 1
        xp_needed = 100
        
        while xp >= xp_needed:
            xp -= xp_needed
            level += 1
            xp_needed = int(xp_needed * 1.5)
        
        return level, xp, xp_needed
    
    def has_achievement(self, user_id, achievement_id):
        user_id = str(user_id)
        return user_id in self.user_achievements and achievement_id in self.user_achievements[user_id]
    
    async def grant_achievement(self, user_id, achievement_id, guild, channel):
        user_id = str(user_id)
        
        if self.has_achievement(user_id, achievement_id):
            return False
        
        if user_id not in self.user_achievements:
            self.user_achievements[user_id] = []
        
        self.user_achievements[user_id].append(achievement_id)
        self.save_data()
        
        achievement = config.ACHIEVEMENTS[achievement_id]
        xp_gain = config.RARITY_XP[achievement["rarity"]]
        
        if user_id not in self.user_xp:
            self.user_xp[user_id] = 0
        
        old_level, _, _ = self.get_user_level(self.user_xp[user_id])
        self.user_xp[user_id] += xp_gain
        new_level, current_xp, xp_needed = self.get_user_level(self.user_xp[user_id])
        self.save_xp()
        
        member = guild.get_member(int(user_id))
        
        if achievement["role"] and member:
            role = discord.utils.get(guild.roles, name=achievement["role"])
            if not role:
                role = await guild.create_role(
                    name=achievement["role"],
                    reason=f"achievement role for {achievement_id}"
                )
            await member.add_roles(role)
        
        achievements_channel = guild.get_channel(config.ACHIEVEMENTS_CHANNEL)
        if achievements_channel:
            level_msg = f"\n`★` [LVL] {member.mention if member else f'user {user_id}'} is now level {new_level}!" if new_level > old_level else ""
            
            await achievements_channel.send(
                f"`☆` [ACH] {member.mention if member else f'user {user_id}'} unlocked **{achievement['name']}** ({achievement['rarity']}, +{xp_gain} xp)\n"
                f"└─ {achievement['description']}{level_msg}"
            )
        
        if self.logger:
            self.logger.info(f"achievement granted to {user_id}: {achievement_id} (+{xp_gain} xp)")
        
        return True
    
    async def check_command_achievement(self, user_id, command, exit_code, guild, channel):
        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "command":
                if command.startswith(ach_data["trigger_value"]):
                    await self.grant_achievement(user_id, ach_id, guild, channel)
            
            elif ach_data["trigger_type"] == "nonzero_exit":
                if exit_code != 0 and exit_code is not None:
                    await self.grant_achievement(user_id, ach_id, guild, channel)
            
            elif ach_data["trigger_type"] == "file_read":
                if "cat" in command and ach_data["trigger_value"] in command:
                    await self.grant_achievement(user_id, ach_id, guild, channel)
    
    @commands.command()
    async def myachievements(self, ctx):
        user_id = str(ctx.author.id)
        
        if user_id not in self.user_achievements or not self.user_achievements[user_id]:
            await ctx.send("you have no achievements yet")
            return
        
        user_achs = self.user_achievements[user_id]
        xp = self.user_xp.get(user_id, 0)
        level, current_xp, xp_needed = self.get_user_level(xp)
        
        ach_list = []
        for ach_id in user_achs:
            ach = config.ACHIEVEMENTS[ach_id]
            ach_list.append(f"☆ **{ach['name']}** ({ach['rarity']})\n  └─ {ach['description']}")
        
        msg = f"**{ctx.author.display_name}s achievements**\n"
        msg += f"level {level} | {current_xp}/{xp_needed} xp\n\n"
        msg += "\n".join(ach_list)
        
        await ctx.send(msg)
    
    @commands.command()
    async def level(self, ctx, member: discord.Member):
        target = member or ctx.author
        user_id = str(target.id)
        
        xp = self.user_xp.get(user_id, 0)
        level, current_xp, xp_needed = self.get_user_level(xp)
        
        ach_count = len(self.user_achievements.get(user_id, []))
        total_achs = len(config.ACHIEVEMENTS)
        
        await ctx.send(
            f"**{target.display_name}**\n"
            f"level {level} | {current_xp}/{xp_needed} xp\n"
            f"achievements: {ach_count}/{total_achs}"
        )

async def setup(bot):
    await bot.add_cog(Achievements(bot))