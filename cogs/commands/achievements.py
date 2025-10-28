import discord
from discord.ext import commands
import config
import json
from pathlib import Path

class AchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = Path("data/achievements.json")
        self.xp_file = Path("data/xp.json")
        self.data_file.parent.mkdir(exist_ok=True)
        
        self.user_achievements = self.load_data()
        self.user_xp = self.load_xp()
        self.logger = self.bot.get_cog("Logger").logger if self.bot.get_cog("Logger") else None
    
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
    
    def get_level(self, xp):
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
    
    def is_staff(self, member):
        return discord.utils.get(member.roles, name="staff@hazelrun") is not None
    
    async def grant_achievement(self, user_id, achievement_id, guild, channel):
        # grant achievement to user and give xp
        user_id = str(user_id)
        
        if self.has_achievement(user_id, achievement_id):
            return False
        
        if achievement_id not in config.ACHIEVEMENTS:
            return False
        
        if user_id not in self.user_achievements:
            self.user_achievements[user_id] = []
        
        self.user_achievements[user_id].append(achievement_id)
        self.save_data()
        
        achievement = config.ACHIEVEMENTS[achievement_id]
        xp_gain = config.RARITY_XP[achievement["rarity"]]
        
        if user_id not in self.user_xp:
            self.user_xp[user_id] = 0
        
        self.user_xp[user_id] += xp_gain
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
        
        
        if self.logger:
            self.logger.info(f"achievement granted to {user_id}: {achievement_id} (+{xp_gain} xp)")
        
        return True
    
    async def revoke_achievement(self, user_id, achievement_id, guild):
        # revoke achievement from user and remove xp
        user_id = str(user_id)
        
        if not self.has_achievement(user_id, achievement_id):
            return False
        
        if achievement_id not in config.ACHIEVEMENTS:
            return False
        
        self.user_achievements[user_id].remove(achievement_id)
        self.save_data()
        
        achievement = config.ACHIEVEMENTS[achievement_id]
        xp_loss = config.RARITY_XP[achievement["rarity"]]
        
        if user_id in self.user_xp:
            self.user_xp[user_id] = max(0, self.user_xp[user_id] - xp_loss)
            self.save_xp()
        
        member = guild.get_member(int(user_id))
        
        if achievement["role"] and member:
            role = discord.utils.get(guild.roles, name=achievement["role"])
            if role and role in member.roles:
                await member.remove_roles(role)
        
        if self.logger:
            self.logger.info(f"achievement revoked from {user_id}: {achievement_id} (-{xp_loss} xp)")
        
        return True
    
    async def check_command_achievement(self, user_id, command, exit_code, guild, channel):
        # check if command triggers any achievements
        for ach_id, ach_data in config.ACHIEVEMENTS.items():
            if ach_data["trigger_type"] == "command":
                trigger = ach_data["trigger_value"]
                if isinstance(trigger, list):
                    if any(command.startswith(t) for t in trigger):
                        await self.grant_achievement(user_id, ach_id, guild, channel)
                elif command.startswith(trigger):
                    await self.grant_achievement(user_id, ach_id, guild, channel)
            
            elif ach_data["trigger_type"] == "nonzero_exit":
                if exit_code != 0 and exit_code is not None:
                    await self.grant_achievement(user_id, ach_id, guild, channel)
            
            elif ach_data["trigger_type"] == "file_read":
                if "cat" in command and ach_data["trigger_value"] in command:
                    await self.grant_achievement(user_id, ach_id, guild, channel)
    
    def should_show(self, ach_id, user_has_it):
        # determine if achievement should be visible
        rarity = config.ACHIEVEMENTS[ach_id]["rarity"]
        if rarity in ["master", "legendary"]:
            return user_has_it
        return True
    
    @commands.command(aliases=['achs', 'achievement', 'ach', 'quests'])
    async def achievements(self, ctx, *args):
        if not args:
            # show only user's achievements
            user_id = str(ctx.author.id)
            user_achs = self.user_achievements.get(user_id, [])
            xp = self.user_xp.get(user_id, 0)
            level, current_xp, xp_needed = self.get_level(xp)
            
            if not user_achs:
                await ctx.send(f"**{ctx.author.display_name}s achievements**\nlevel {level} | {current_xp}/{xp_needed} xp\n\nno achievements unlocked yet")
                return
            
            msg = f"**{ctx.author.display_name}s achievements**\n"
            msg += f"level {level} | {current_xp}/{xp_needed} xp\n\n"
            msg += f"**unlocked: {len(user_achs)}**\n\n"
            
            for ach_id in user_achs:
                if ach_id not in config.ACHIEVEMENTS:
                    continue
                ach = config.ACHIEVEMENTS[ach_id]
                msg += f"`☆` **{ach['name']}** ({ach['rarity']})\n  ⋱ {ach['description']}\n"
            
            await ctx.send(msg)
            return
        
        if args[0] in ["-a", "--all"]:
            # show all achievements with spoilers
            user_id = str(ctx.author.id)
            user_achs = self.user_achievements.get(user_id, [])
            xp = self.user_xp.get(user_id, 0)
            level, current_xp, xp_needed = self.get_level(xp)
            
            visible_count = sum(1 for ach_id in config.ACHIEVEMENTS 
                              if config.ACHIEVEMENTS[ach_id]["rarity"] not in ["master", "legendary"])
            visible_count += sum(1 for ach_id in user_achs 
                               if ach_id in config.ACHIEVEMENTS and config.ACHIEVEMENTS[ach_id]["rarity"] in ["master", "legendary"])
            
            msg = f"**{ctx.author.display_name}s achievements**\n"
            msg += f"level {level} | {current_xp}/{xp_needed} xp\n\n"
            msg += f"**unlocked: {len(user_achs)}/{visible_count}**\n\n"
            
            for ach_id in config.ACHIEVEMENTS:
                ach = config.ACHIEVEMENTS[ach_id]
                user_has = ach_id in user_achs
                
                # dont show master/legendary unless unlocked
                if ach["rarity"] in ["master", "legendary"] and not user_has:
                    continue
                
                if user_has:
                    msg += f"`☆` **{ach['name']}** ({ach['rarity']})\n  ⋱ {ach['description']}\n"
                else:
                    if ach["rarity"] == "rare":
                        msg += f"`☆` ||**{ach['name']}**|| ({ach['rarity']})\n  ⋱ ||{ach['description']}||\n"
                    else:
                        msg += f"`☆` **{ach['name']}** ({ach['rarity']})\n  ⋱ {ach['description']}\n"
            
            await ctx.send(msg)
            return
        
        if args[0] in ["-g", "--grant"]:
            if not self.is_staff(ctx.author):
                await ctx.send("you lack the required permissions")
                return
            
            if len(args) < 3 or args[1] not in ["-u"]:
                await ctx.send("usage: >achievements -g -u user achievement_name")
                return
            
            try:
                member = await commands.MemberConverter().convert(ctx, args[2])
            except discord.errors.NotFound:
                await ctx.send("user not found")
                return
            
            achievement_name = " ".join(args[3:]) if len(args) > 3 else args[2]
            
            ach_id = None
            for aid, adata in config.ACHIEVEMENTS.items():
                if aid == achievement_name or adata["name"].lower() == achievement_name.lower():
                    ach_id = aid
                    break
                
            if not ach_id:
                await ctx.send(f"achievement not found: {achievement_name}")
                return
            
            success = await self.grant_achievement(str(member.id), ach_id, ctx.guild, ctx.channel)
            await ctx.send(f"granted achievement {ach_id} to {member.mention}" if success else f"{member.mention} already has this achievement")
        
        elif args[0] in ["-r", "--revoke"]:
            if not self.is_staff(ctx.author):
                await ctx.send("you lack the required permissions")
                return
            
            if len(args) < 3 or args[1] not in ["-u"]:
                await ctx.send("usage: >achievements -r -u user achievement_name")
                return
            
            try:
                member = await commands.MemberConverter().convert(ctx, args[2])
            except discord.errors.NotFound:
                await ctx.send("user not found")
                return
            
            achievement_name = " ".join(args[3:]) if len(args) > 3 else args[2]
            
            ach_id = None
            for aid, adata in config.ACHIEVEMENTS.items():
                if aid == achievement_name or adata["name"].lower() == achievement_name.lower():
                    ach_id = aid
                    break
                
            if not ach_id:
                await ctx.send(f"achievement not found: {achievement_name}")
                return
            
            success = await self.revoke_achievement(str(member.id), ach_id, ctx.guild)
            await ctx.send(f"revoked achievement {ach_id} from {member.mention}" if success else f"{member.mention} doesnt have this achievement")
        
        elif args[0] in ["-u"]:
            if len(args) < 2:
                await ctx.send("usage: >achievements -u user")
                return
            
            try:
                member = await commands.MemberConverter().convert(ctx, args[1])
            except discord.errors.NotFound:
                await ctx.send("user not found")
                return
            
            user_id = str(member.id)
            user_achs = self.user_achievements.get(user_id, [])
            xp = self.user_xp.get(user_id, 0)
            level, current_xp, xp_needed = self.get_level(xp)
            
            if not user_achs:
                await ctx.send(f"**{member.display_name}s achievements**\nlevel {level} | {current_xp}/{xp_needed} xp\n\nno achievements unlocked yet")
                return
            
            msg = f"**{member.display_name}s achievements**\n"
            msg += f"level {level} | {current_xp}/{xp_needed} xp\n\n"
            msg += f"**unlocked: {len(user_achs)}**\n\n"
            
            for ach_id in user_achs:
                if ach_id not in config.ACHIEVEMENTS:
                    continue
                ach = config.ACHIEVEMENTS[ach_id]
                msg += f"`☆` **{ach['name']}** ({ach['rarity']})\n  ⋱ {ach['description']}\n"
            
            await ctx.send(msg)
    
    @commands.command()
    async def leaderboard(self, ctx, page: int = 1):
        sorted_users = sorted(self.user_xp.items(), key=lambda x: x[1], reverse=True)

        if not sorted_users:
            await ctx.send("no users on the leaderboard yet")
            return

        user_rank = None
        user_xp_val = self.user_xp.get(str(ctx.author.id), 0)
        for i, (uid, xp) in enumerate(sorted_users, 1):
            if uid == str(ctx.author.id):
                user_rank = i
                break
            
        per_page = 10
        total_pages = (len(sorted_users) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        msg = f"**xp leaderboard** (page {page}/{total_pages})\n"
        if user_rank:
            level, _, _ = self.get_level(user_xp_val)
            msg += f"-# your rank: #{user_rank} | level {level} | {user_xp_val} xp\n\n"
        else:
            msg += "\n"

        for i, (user_id, xp) in enumerate(sorted_users[start_idx:end_idx], start_idx + 1):
            level, current_xp, xp_needed = self.get_level(xp)
            member = ctx.guild.get_member(int(user_id))
            username = member.display_name if member else f"user {user_id}"

            if i <= 3 and page == 1:
                medals = ["# [1] ", "## [2] ", "### [3] "]
                msg += f"{medals[i-1]}{i}. **{username}** - level {level} ({xp} xp)\n"
            else:
                msg += f"{i}. **{username}** - level {level} ({xp} xp)\n"

        if total_pages > 1:
            msg += "\n-# use >leaderboard <page> to view other pages"

        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(AchCommands(bot))