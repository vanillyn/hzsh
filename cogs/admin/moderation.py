import discord
from discord.ext import commands
import config
import json
from pathlib import Path
from datetime import datetime
import asyncio

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = Path("data/moderation.json")
        self.data_file.parent.mkdir(exist_ok=True)
        
        self.mod_data = self.load_data()
        self.sudo_sessions = {}
        self.logger = self.bot.get_cog("Logging").logger if self.bot.get_cog("Logging") else None
        
        self.mod_log_channel = 1430975629028753569
        self.bot_log_channel = 1430975054518288504
        self.container_name = "hzsh_linux"
    
    def load_data(self):
        if self.data_file.exists():
            with open(self.data_file, 'r') as f:
                return json.load(f)
        return {"warnings": {}, "bans": {}}
    
    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.mod_data, f, indent=2)
    
    def has_staff_role(self, member):
        return discord.utils.get(member.roles, name="staff@hazelrun") is not None
    
    def has_mod_role(self, member):
        return discord.utils.get(member.roles, name="mod@hazelrun") is not None
    
    def is_root(self, user_id):
        return str(user_id) in self.sudo_sessions
    
    async def log_moderation(self, action, moderator, target, reason, duration=None):
        channel = self.bot.get_channel(self.mod_log_channel)
        if not channel:
            return
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = f"[{timestamp}] [{action.upper()}]\n"
        msg += f"moderator: {moderator.name} ({moderator.id})\n"
        msg += f"target: {target.name if hasattr(target, 'name') else target} ({target.id if hasattr(target, 'id') else 'unknown'})\n"
        msg += f"reason: {reason}\n"
        if duration:
            msg += f"duration: {duration}\n"
        
        await channel.send(f"```\n{msg}```")
    
    async def sudo_exec(self, command: str):
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "exec", "-u", "0", "-w", "/root",
                self.container_name, "bash", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0
            )
            
            exit_code = process.returncode
            
            output = stdout.decode('utf-8', errors='replace')
            error = stderr.decode('utf-8', errors='replace')
            
            result = ""
            if output:
                result += output
            if error:
                result += error
            
            return result if result else f"hzsh: {command}: zero code with no output", exit_code
            
        except asyncio.TimeoutError:
            return f"hzsh: {command}: timeout", 124
        except Exception as e:
            return f"hzsh: {command}: {str(e)}", 1
    
    @commands.command(aliases=['doas'])
    async def sudo(self, ctx, *, command: str = ' '):
        if not self.has_staff_role(ctx.author):
            await ctx.send("you lack the required permissions")
            return
        
        if not command:
            await ctx.send("usage: >sudo <command>")
            return
        
        if command.strip() == "su -":
            if self.is_root(ctx.author.id):
                await ctx.send("already in sudo session")
                return
            
            self.sudo_sessions[str(ctx.author.id)] = {
                "channel": ctx.channel.id,
                "started": datetime.now().isoformat()
            }
            
            await ctx.send(f"elevated privileges granted to {ctx.author.mention}")
            await self.log_moderation("sudo_session", ctx.author, ctx.author, "started sudo session")
            
            asyncio.create_task(self._auto_expire_sudo(ctx.author.id))
            return
        
        parts = command.split(maxsplit=2)
        cmd = parts[0].lower()
        
        if cmd == "warn":
            if len(parts) < 3:
                await ctx.send("usage: >sudo warn @user reason")
                return
            
            try:
                member = await commands.MemberConverter().convert(ctx, parts[1])
            except discord.errors.NotFound:
                await ctx.send("user not found")
                return
            
            reason = parts[2]
            
            user_id = str(member.id)
            if user_id not in self.mod_data["warnings"]:
                self.mod_data["warnings"][user_id] = []
            
            warning = {
                "moderator": str(ctx.author.id),
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
            
            self.mod_data["warnings"][user_id].append(warning)
            self.save_data()
            
            try:
                await member.send(f"you have been warned in {ctx.guild.name}\nreason: {reason}")
            except discord.errors.HTTPException:
                await ctx.send(f"warned {member.mention} but could not dm them")
            else:
                await ctx.send(f"warned {member.mention}")
            
            await self.log_moderation("warn", ctx.author, member, reason)
        
        elif cmd == "ban":
            if len(parts) < 3:
                await ctx.send("usage: >sudo ban @user reason [time]")
                return
            
            try:
                member = await commands.MemberConverter().convert(ctx, parts[1])
            except discord.errors.NotFound:
                await ctx.send("user not found")
                return
            
            reason_parts = parts[2].split()
            duration = None
            reason = parts[2]
            
            if len(reason_parts) > 1:
                last_word = reason_parts[-1]
                if any(c.isdigit() for c in last_word) and any(c.isalpha() for c in last_word):
                    duration = last_word
                    reason = " ".join(reason_parts[:-1])
            
            user_id = str(member.id)
            if user_id not in self.mod_data["bans"]:
                self.mod_data["bans"][user_id] = []
            
            ban_entry = {
                "moderator": str(ctx.author.id),
                "reason": reason,
                "duration": duration,
                "timestamp": datetime.now().isoformat()
            }
            
            self.mod_data["bans"][user_id].append(ban_entry)
            self.save_data()
            
            try:
                await member.send(f"you have been banned from {ctx.guild.name}\nreason: {reason}\nduration: {duration if duration else 'permanent'}")
            except discord.errors.HTTPException:
                pass
            
            await ctx.guild.ban(member, reason=reason, delete_message_days=0)
            await ctx.send(f"banned {member.mention}")
            
            await self.log_moderation("ban", ctx.author, member, reason, duration)
        
        elif cmd == "userdel":
            if len(parts) < 2:
                await ctx.send("usage: >sudo userdel @user")
                return
            
            try:
                member = await commands.MemberConverter().convert(ctx, parts[1])
            except discord.errors.NotFound:
                await ctx.send("user not found")
                return
            
            shell_role = discord.utils.get(ctx.guild.roles, name=config.SHELL_ACCESS_ROLE)
            
            if shell_role not in member.roles:
                await ctx.send(f"{member.mention} doesnt have shell access")
                return
            
            await member.remove_roles(shell_role)
            await ctx.send(f"revoked shell access from {member.mention}")
            
            await self.log_moderation("userdel", ctx.author, member, "shell access revoked")
        
        else:
            async with ctx.typing():
                result, exit_code = await self.sudo_exec(command)
            
            if len(result) > 1900:
                result = result[:1900] + "\n... output truncated"
            
            if self.logger:
                self.logger.info(f"root command executed by {ctx.author.name}: {command} (exit: {exit_code})")
            
            await ctx.send(f"```\n{result}\n```")
    
    async def _auto_expire_sudo(self, user_id):
        await asyncio.sleep(1800)
        
        if str(user_id) in self.sudo_sessions:
            del self.sudo_sessions[str(user_id)]
    
    @commands.command()
    async def kick(self, ctx, member: discord.Member, *, reason: str = "no reason provided"):
        if not (self.has_staff_role(ctx.author) or self.has_mod_role(ctx.author)):
            await ctx.send("you lack the required permissions")
            return
        
        try:
            await member.send(f"you have been kicked from {ctx.guild.name}\nreason: {reason}")
        except discord.errors.HTTPException:
            pass
        
        await ctx.guild.kick(member, reason=reason)
        await ctx.send(f"kicked {member.mention}")
        
        await self.log_moderation("kick", ctx.author, member, reason)
    
    @commands.command()
    async def mute(self, ctx, member: discord.Member, *, reason: str = "no reason provided"):
        if not (self.has_staff_role(ctx.author) or self.has_mod_role(ctx.author)):
            await ctx.send("you lack the required permissions")
            return
        
        muted_role = discord.utils.get(ctx.guild.roles, name="| muted")
        
        await member.add_roles(muted_role)
        await ctx.send(f"muted {member.mention}")
        
        await self.log_moderation("mute", ctx.author, member, reason)
    
    @commands.command()
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        if not self.is_root(ctx.author.id):
            await ctx.send("requires sudo session. run >sudo su -")
            return
        
        user_id = str(member.id)
        if user_id not in self.mod_data["warnings"]:
            self.mod_data["warnings"][user_id] = []
        
        warning = {
            "moderator": str(ctx.author.id),
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        self.mod_data["warnings"][user_id].append(warning)
        self.save_data()
        
        try:
            await member.send(f"you have been warned in {ctx.guild.name}\nreason: {reason}")
        except discord.errors.HTTPException:
            await ctx.send(f"warned {member.mention} but could not dm them")
        else:
            await ctx.send(f"warned {member.mention}")
        
        await self.log_moderation("warn", ctx.author, member, reason)
    
    @commands.command()
    async def ban(self, ctx, member: discord.Member, *, reason: str):
        if not self.is_root(ctx.author.id):
            await ctx.send("requires sudo session. run >sudo su -")
            return
        
        reason_parts = reason.split()
        duration = None
        
        if len(reason_parts) > 1:
            last_word = reason_parts[-1]
            if any(c.isdigit() for c in last_word) and any(c.isalpha() for c in last_word):
                duration = last_word
                reason = " ".join(reason_parts[:-1])
        
        user_id = str(member.id)
        if user_id not in self.mod_data["bans"]:
            self.mod_data["bans"][user_id] = []
        
        ban_entry = {
            "moderator": str(ctx.author.id),
            "reason": reason,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }
        
        self.mod_data["bans"][user_id].append(ban_entry)
        self.save_data()
        
        try:
            await member.send(f"you have been banned from {ctx.guild.name}\nreason: {reason}\nduration: {duration if duration else 'permanent'}")
        except discord.errors.HTTPException:
            pass
        
        await ctx.guild.ban(member, reason=reason, delete_message_days=0)
        await ctx.send(f"banned {member.mention}")
        
        await self.log_moderation("ban", ctx.author, member, reason, duration)
    
    @commands.command(aliases=['deletechannel','channeldel'])
    async def rmdir(self, ctx, channel_name: str):
        if not self.is_root(ctx.author.id):
            await ctx.send("requires sudo session. run >sudo su -")
            return
        
        channel = discord.utils.get(ctx.guild.channels, name=channel_name)
        
        if not channel:
            await ctx.send(f"channel {channel_name} not found")
            return
        
        await channel.delete(reason=f"deleted by {ctx.author.name}")
        await ctx.send(f"removed channel {channel_name}")
        
        await self.log_moderation("rmdir", ctx.author, channel, f"deleted channel {channel_name}")
    
    @commands.command()
    async def groupdel(self, ctx, role_name: str):
        if not self.is_root(ctx.author.id):
            await ctx.send("requires sudo session. run >sudo su -")
            return
        
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        
        if not role:
            await ctx.send(f"role {role_name} not found")
            return
        
        await role.delete(reason=f"deleted by {ctx.author.name}")
        await ctx.send(f"removed role {role_name}")
        
        await self.log_moderation("groupdel", ctx.author, role, f"deleted role {role_name}")
    
    @commands.command(aliases=['addgroup', 'newrole', 'createrole'])
    async def groupadd(self, ctx, name: str, color: str = ' '):
        if not self.is_root(ctx.author.id):
            await ctx.send("requires sudo session. run >sudo su -")
            return
        
        role_color = discord.Color.default()
        
        if color:
            try:
                if color.startswith('#'):
                    color = color[1:]
                role_color = discord.Color(int(color, 16))
            except Exception as e:
                print(e)
                await ctx.send("invalid color format. use hex like #ffffff")
                return
        
        role = await ctx.guild.create_role(
            name=name,
            color=role_color,
            reason=f"created by {ctx.author.name}"
        )
        
        await ctx.send(f"created role {name}")
        await self.log_moderation("groupadd", ctx.author, role, f"created role {name}")
    
    @commands.command(aliases=['deluser', 'rmshell', 'shellban'])
    async def userdel(self, ctx, member: discord.Member):
        if not self.is_root(ctx.author.id):
            await ctx.send("requires sudo session. run >sudo su -")
            return
        
        shell_role = discord.utils.get(ctx.guild.roles, name=config.SHELL_ACCESS_ROLE)
        
        if shell_role not in member.roles:
            await ctx.send(f"{member.mention} doesnt have shell access")
            return
        
        await member.remove_roles(shell_role)
        await ctx.send(f"revoked shell access from {member.mention}")
        
        await self.log_moderation("userdel", ctx.author, member, "shell access revoked")
    
    @commands.command(aliases=['lswarns', 'warns'])
    async def warnings(self, ctx, member: discord.Member):
        target = member or ctx.author
        user_id = str(target.id)
        
        if user_id not in self.mod_data["warnings"] or not self.mod_data["warnings"][user_id]:
            await ctx.send(f"{target.mention} has no warnings")
            return
        
        warnings = self.mod_data["warnings"][user_id]
        msg = f"warnings for {target.mention}:\n"
        
        for i, warning in enumerate(warnings, 1):
            timestamp = datetime.fromisoformat(warning["timestamp"]).strftime('%Y-%m-%d %H:%M')
            msg += f"{i}. [{timestamp}] {warning['reason']}\n"
        
        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(Moderation(bot))