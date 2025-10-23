import discord
from discord.ext import commands
import subprocess
import asyncio
from pathlib import Path
import config
import hashlib

class Shell(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.container_name = "hzsh_linux"
        self.home_dir = Path("root/home")
        self.working_dirs = {}
        self.sessions = {}
        self.user_id_map = {}
        self.username_map = {}
        
        if not self.home_dir.exists():
            self.home_dir.mkdir(parents=True, exist_ok=True)
    
    def get_unix_uid(self, discord_id: str):
        if discord_id not in self.user_id_map:
            hash_val = int(hashlib.sha256(discord_id.encode()).hexdigest()[:8], 16)
            unix_uid = (hash_val % 2147483147) + 1000
            self.user_id_map[discord_id] = unix_uid
        return self.user_id_map[discord_id]
    
    def has_shell_access(self, member):
        return discord.utils.get(member.roles, name=config.SHELL_ACCESS_ROLE) is not None
    
    def ensure_user_home(self, username: str, discord_id: str):
        self.username_map[discord_id] = username
        user_home = self.home_dir / username
        unix_uid = self.get_unix_uid(discord_id)
        
        if not user_home.exists():
            user_home.mkdir(parents=True, exist_ok=True)
            
            result = subprocess.run([
                "docker", "exec", self.container_name,
                "id", "-u", str(unix_uid)
            ], capture_output=True)
            
            if result.returncode != 0:
                subprocess.run([
                    "docker", "exec", self.container_name,
                    "useradd", "-u", str(unix_uid), "-m", "-s", "/bin/bash", username
                ], capture_output=True)
            
            subprocess.run([
                "docker", "exec", self.container_name,
                "chown", "-R", f"{unix_uid}:{unix_uid}", f"/home/{username}"
            ], capture_output=True)
        
        if discord_id not in self.working_dirs:
            self.working_dirs[discord_id] = f"/home/{username}"
        
        return user_home
    
    async def execute_command(self, username: str, discord_id: str, command: str, ctx=None):
        self.ensure_user_home(username, discord_id)
        
        unix_uid = self.get_unix_uid(discord_id)
        working_dir = self.working_dirs.get(discord_id, f"/home/{username}")
        
        full_command = f"cd {working_dir} && {command}"
        
        exit_code = None
        
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "exec", "-u", str(unix_uid), "-w", working_dir,
                self.container_name, "bash", "-c", full_command,
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
            
            logging_cog = self.bot.get_cog("EnhancedLogging")
            if logging_cog and ctx:
                log_msg = "shell command\n"
                log_msg += f"user: {username} ({discord_id})\n"
                log_msg += f"command: {command}\n"
                log_msg += f"exit code: {exit_code}\n"
                log_msg += f"working dir: {working_dir}"
                await logging_cog.log_to_channel(log_msg, "SHELL")
            
            if ctx:
                achievements_cog = self.bot.get_cog("Achievements")
                if achievements_cog:
                    await achievements_cog.check_command_achievement(
                        discord_id, command, exit_code, ctx.guild, ctx.channel
                    )
            
            return result if result else f"hzsh: {command}: zero code with no output"
            
        except asyncio.TimeoutError:
            return f"hzsh: {command}: timeout"
        except Exception as e:
            return f"hzsh: {command}: {str(e)}"
    
    @commands.command(name='sh')
    async def shell_command(self, ctx, *, command: str):
        if not self.has_shell_access(ctx.author):
            await ctx.send("you are not connected to `hazel / shell`.")
            return
        
        username = ctx.author.name
        discord_id = str(ctx.author.id)
        
        async with ctx.typing():
            result = await self.execute_command(username, discord_id, command, ctx)
        
        if len(result) > 1900:
            result = result[:1900] + "\n... output truncated"
        
        await ctx.send(f"```\n{result}\n```")
    
    @commands.command(name='cd')
    async def change_directory(self, ctx, *, path: str = "~"):
        if not self.has_shell_access(ctx.author):
            await ctx.send("you are not connected to `hazel / shell`.")
            return
        
        username = ctx.author.name
        discord_id = str(ctx.author.id)
        self.ensure_user_home(username, discord_id)
        
        current = self.working_dirs.get(discord_id, f"/home/{username}")
        
        if path == "~":
            new_path = f"/home/{username}"
        elif path.startswith("/"):
            new_path = path
        else:
            new_path = f"{current}/{path}"
        
        result = await self.execute_command(username, discord_id, f"cd '{new_path}' && pwd", ctx)
        
        if "no such file or directory" not in result.lower() and "not a directory" not in result.lower():
            self.working_dirs[discord_id] = result.strip()
            await ctx.send(f"```\n{self.working_dirs[discord_id]}\n```")
        else:
            await ctx.send(f"```\n{result}\n```")
    
    @commands.command(name='hzsh')
    async def interactive_shell(self, ctx):
        if not self.has_shell_access(ctx.author):
            await ctx.send("you are not connected to `hazel / shell`.")
            return
        
        username = ctx.author.name
        discord_id = str(ctx.author.id)
        
        if discord_id in self.sessions:
            await ctx.send("you're already connected")
            return
        
        self.ensure_user_home(username, discord_id)
        
        unix_uid = self.get_unix_uid(discord_id)
        working_dir = self.working_dirs.get(discord_id, f"/home/{username}")
        
        logging_cog = self.bot.get_cog("EnhancedLogging")
        if logging_cog:
            log_msg = "interactive shell started\n"
            log_msg += f"user: {username} ({discord_id})\n"
            log_msg += f"working dir: {working_dir}"
            await logging_cog.log_to_channel(log_msg, "SHELL")
        
        process = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", "-u", str(unix_uid), "-w", working_dir,
            self.container_name, "script", "-qfc", "bash", "/dev/null",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        screen_lines = ["" for _ in range(17)]
        
        screen_content = "```\n" + "\n".join(line.ljust(57) for line in screen_lines) + "\n```"
        screen_msg = await ctx.send(screen_content)
        
        self.sessions[discord_id] = {
            "channel": ctx.channel.id,
            "active": True,
            "username": username,
            "process": process,
            "screen_msg": screen_msg,
            "screen_lines": screen_lines,
            "current_line": "",
            "cursor_col": 0
        }
        
        asyncio.create_task(self._read_process_output(discord_id))
    
    async def _read_process_output(self, discord_id):
        if discord_id not in self.sessions:
            return
        
        session = self.sessions[discord_id]
        process = session["process"]
        
        try:
            while session["active"]:
                try:
                    chunk = await asyncio.wait_for(
                        process.stdout.read(256),
                        timeout=0.05
                    )
                    
                    if not chunk:
                        break
                    
                    text = chunk.decode('utf-8', errors='replace')
                    await self._process_output(discord_id, text)
                    
                except asyncio.TimeoutError:
                    continue
                    
        except Exception as e:
            print(f"error reading process output: {e}")
            if discord_id in self.sessions:
                self.sessions[discord_id]["active"] = False
    
    async def _process_output(self, discord_id, text):
        if discord_id not in self.sessions:
            return
        
        session = self.sessions[discord_id]
        screen_lines = session["screen_lines"]
        current_line = session["current_line"]
        cursor_col = session["cursor_col"]
        
        i = 0
        while i < len(text):
            char = text[i]
            
            if char == '\r':
                cursor_col = 0
            elif char == '\n':
                screen_lines.append(current_line)
                if len(screen_lines) > 17:
                    screen_lines.pop(0)
                current_line = ""
                cursor_col = 0
            elif char == '\b':
                if cursor_col > 0:
                    cursor_col -= 1
                    current_line = current_line[:cursor_col] + current_line[cursor_col+1:]
            elif char == '\x1b':
                if i + 1 < len(text) and text[i + 1] == '[':
                    seq_end = i + 2
                    while seq_end < len(text) and text[seq_end] not in 'ABCDEFGHJKSTfmhlsu':
                        seq_end += 1
                    if seq_end < len(text):
                        seq = text[i+2:seq_end+1]
                        if seq.endswith('K'):
                            if seq == 'K' or seq == '0K':
                                current_line = current_line[:cursor_col]
                            elif seq == '1K':
                                current_line = ' ' * cursor_col + current_line[cursor_col:]
                            elif seq == '2K':
                                current_line = ""
                                cursor_col = 0
                        elif seq.endswith('D'):
                            n = int(seq[:-1]) if seq[:-1] else 1
                            cursor_col = max(0, cursor_col - n)
                        elif seq.endswith('C'):
                            n = int(seq[:-1]) if seq[:-1] else 1
                            cursor_col = min(len(current_line), cursor_col + n)
                        i = seq_end
                    else:
                        i += 1
                else:
                    i += 1
            elif ord(char) >= 32:
                if cursor_col >= len(current_line):
                    current_line += char
                else:
                    current_line = current_line[:cursor_col] + char + current_line[cursor_col+1:]
                cursor_col += 1
            
            i += 1
        
        session["current_line"] = current_line
        session["cursor_col"] = cursor_col
        
        display_lines = screen_lines.copy()
        if current_line or cursor_col > 0:
            display_line = current_line[:57]
            if cursor_col < 57:
                display_line = display_line[:cursor_col] + '█' + display_line[cursor_col+1:]
            display_lines.append(display_line)
        
        if len(display_lines) > 17:
            display_lines = display_lines[-17:]
        
        screen_content = "```\n" + "\n".join(line.ljust(57)[:57] for line in display_lines) + "\n```"
        
        try:
            await session["screen_msg"].edit(content=screen_content)
        except Exception as e:
            print(e)
            pass
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        discord_id = str(message.author.id)
        
        if discord_id not in self.sessions:
            return
        
        session = self.sessions[discord_id]
        
        if not session["active"]:
            return
        
        if message.channel.id != session["channel"]:
            return
        
        content = message.content
        
        if content == '[EXIT]':
            process = session["process"]
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except Exception as e:
                print(e)
                process.kill()
            
            logging_cog = self.bot.get_cog("EnhancedLogging")
            if logging_cog:
                log_msg = "interactive shell closed\n"
                log_msg += f"user: {session['username']} ({discord_id})"
                await logging_cog.log_to_channel(log_msg, "SHELL")
            
            if discord_id in self.sessions:
                del self.sessions[discord_id]
            
            await message.channel.send("shell session closed")
            try:
                await message.delete()
            except Exception as e:
                print (e)
                pass
            return
        
        try:
            await message.delete()
        except Exception as e:
            print(e)
            pass
        
        process = session["process"]
        
        translated = content.replace('[^] C', '\x03')
        translated = translated.replace('[^] D', '\x04')
        translated = translated.replace('[^] Z', '\x1a')
        translated = translated.replace('[UP]', '\x1b[A')
        translated = translated.replace('[DOWN]', '\x1b[B')
        translated = translated.replace('[RIGHT]', '\x1b[C')
        translated = translated.replace('[LEFT]', '\x1b[D')
        translated = translated.replace('[]', '\n')
        
        if '[^]' in translated:
            parts = translated.split('[^]')
            for i in range(1, len(parts)):
                if parts[i]:
                    first_char = parts[i][0]
                    if first_char.isalpha():
                        ctrl_char = chr(ord(first_char.upper()) - 64)
                        parts[i] = ctrl_char + parts[i][1:]
            translated = ''.join(parts)
        
        if '[#]' in translated:
            parts = translated.split('[#]')
            result = [parts[0]]
            for part in parts[1:]:
                if part:
                    result.append(part[0].upper() + part[1:])
            translated = ''.join(result)
        
        try:
            process.stdin.write(translated.encode('utf-8'))
            await process.stdin.drain()
        except Exception as e:
            print(f"error writing to stdin: {e}")

async def setup(bot):
    await bot.add_cog(Shell(bot))