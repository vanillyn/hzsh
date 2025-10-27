import discord
from discord.ext import commands
import subprocess
import asyncio
from pathlib import Path
import config
import hashlib
import re

class Terminal:
    def __init__(self, width=80, height=24, scrollback=1000):
        self.width = width
        self.height = height
        self.scrollback_limit = scrollback
        self.buffer = [[(' ', '') for _ in range(width)] for _ in range(height)]
        self.scrollback = []
        self.cursor_x = 0
        self.cursor_y = 0
        self.saved_cursor = (0, 0)
        self.current_style = ''
        self.scroll_offset = 0
        
    def clear(self):
        self.buffer = [[(' ', '') for _ in range(self.width)] for _ in range(self.height)]
        self.scrollback = []
        self.cursor_x = 0
        self.cursor_y = 0
        self.scroll_offset = 0
    
    def clear_line(self, mode=0):
        if mode == 0:
            for x in range(self.cursor_x, self.width):
                self.buffer[self.cursor_y][x] = (' ', '')
        elif mode == 1:
            for x in range(0, self.cursor_x + 1):
                self.buffer[self.cursor_y][x] = (' ', '')
        elif mode == 2:
            self.buffer[self.cursor_y] = [(' ', '') for _ in range(self.width)]
    
    def clear_screen(self, mode=0):
        if mode == 0:
            for x in range(self.cursor_x, self.width):
                self.buffer[self.cursor_y][x] = (' ', '')
            for y in range(self.cursor_y + 1, self.height):
                self.buffer[y] = [(' ', '') for _ in range(self.width)]
        elif mode == 1:
            for x in range(0, self.cursor_x + 1):
                self.buffer[self.cursor_y][x] = (' ', '')
            for y in range(0, self.cursor_y):
                self.buffer[y] = [(' ', '') for _ in range(self.width)]
        elif mode == 2:
            self.buffer = [[(' ', '') for _ in range(self.width)] for _ in range(self.height)]
    
    def write_char(self, char):
        if self.cursor_y >= self.height:
            self.scroll_up()
            self.cursor_y = self.height - 1
        
        if self.cursor_x >= self.width:
            self.cursor_x = 0
            self.cursor_y += 1
            if self.cursor_y >= self.height:
                self.scroll_up()
                self.cursor_y = self.height - 1
        
        if self.cursor_y < self.height and self.cursor_x < self.width:
            self.buffer[self.cursor_y][self.cursor_x] = (char, self.current_style)
            self.cursor_x += 1
    
    def newline(self):
        self.cursor_x = 0
        self.cursor_y += 1
        if self.cursor_y >= self.height:
            self.scroll_up()
            self.cursor_y = self.height - 1
    
    def carriage_return(self):
        self.cursor_x = 0
    
    def backspace(self):
        if self.cursor_x > 0:
            self.cursor_x -= 1
    
    def move_cursor(self, x=None, y=None):
        if x is not None:
            self.cursor_x = max(0, min(x, self.width - 1))
        if y is not None:
            self.cursor_y = max(0, min(y, self.height - 1))
    
    def scroll_up(self, lines=1):
        for _ in range(lines):
            self.scrollback.append(self.buffer[0])
            if len(self.scrollback) > self.scrollback_limit:
                self.scrollback.pop(0)
            self.buffer.pop(0)
            self.buffer.append([(' ', '') for _ in range(self.width)])
    
    def scroll_down(self, lines=1):
        for _ in range(lines):
            self.buffer.pop()
            self.buffer.insert(0, [(' ', '') for _ in range(self.width)])
    
    def scroll_view_up(self, lines=1):
        max_offset = len(self.scrollback)
        self.scroll_offset = min(self.scroll_offset + lines, max_offset)
    
    def scroll_view_down(self, lines=1):
        self.scroll_offset = max(self.scroll_offset - lines, 0)
    
    def get_display(self, show_cursor=True):
        if self.scroll_offset > 0:
            offset = self.scroll_offset
            visible_lines = []
            
            if offset <= len(self.scrollback):
                start_idx = len(self.scrollback) - offset
                visible_lines = self.scrollback[start_idx:start_idx + self.height]
                
                remaining = self.height - len(visible_lines)
                if remaining > 0:
                    visible_lines.extend(self.buffer[:remaining])
            else:
                visible_lines = self.buffer
        else:
            visible_lines = self.buffer
        
        lines = []
        for y, line_buffer in enumerate(visible_lines):
            line_parts = []
            current_ansi = ''
            
            for x in range(self.width):
                if x >= len(line_buffer):
                    break
                    
                char, style = line_buffer[x]
                
                show_cursor_here = show_cursor and self.scroll_offset == 0 and y == self.cursor_y and x == self.cursor_x
                
                if show_cursor_here:
                    if current_ansi:
                        line_parts.append(current_ansi)
                        current_ansi = ''
                    line_parts.append('\x1b[7m')
                    line_parts.append(char if char != ' ' else ' ')
                    line_parts.append('\x1b[27m')
                    if style:
                        current_ansi = style
                else:
                    if style != current_ansi:
                        if current_ansi:
                            line_parts.append(current_ansi)
                        current_ansi = style
                    line_parts.append(char)
            
            if current_ansi:
                line_parts.append('\x1b[0m')
            
            line = ''.join(line_parts)
            
            if not line or line.replace('\x1b[0m', '').replace('\x1b[7m', '').replace('\x1b[27m', '').isspace():
                lines.append(' ')
            else:
                lines.append(line)
        
        return lines

class Shell(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.container_name = "hzsh_linux"
        self.home_dir = Path("hazelrun/home")
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
        
        result = await self.execute_command(username, discord_id, f"cd '{new_path}' && pwd")
        
        if "no such file or directory" not in result.lower() and "not a directory" not in result.lower():
            self.working_dirs[discord_id] = result.strip()
            await ctx.send(f"```\n{self.working_dirs[discord_id]}\n```")
        else:
            await ctx.send(f"```\n{result}\n```")
    
    @commands.command(name='hzsh', aliases=['shell', 'bash', 'connect', 'ssh'])
    async def hazelshell(self, ctx):
        if not self.has_shell_access(ctx.author):
            await ctx.send("you are not connected to `hazel / shell`.")
            return
        
        username = ctx.author.name
        discord_id = str(ctx.author.id)
        
        if discord_id in self.sessions:
            await ctx.send("youre already connected")
            return
        
        self.ensure_user_home(username, discord_id)
        
        unix_uid = self.get_unix_uid(discord_id)
        working_dir = self.working_dirs.get(discord_id, f"/home/{username}")
        
        process = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", "-u", str(unix_uid), "-w", working_dir,
            self.container_name, 
            "env", "TERM=xterm", "COLUMNS=80", "LINES=24",
            "script", "-qfc", "bash", "/dev/null",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        screen = Terminal(width=80, height=24, scrollback=1000)
        
        screen_content = "```ansi\n" + "\n".join(screen.get_display(show_cursor=False)) + "\n```"
        screen_msg = await ctx.send(screen_content)
        
        self.sessions[discord_id] = {
            "channel": ctx.channel.id,
            "active": True,
            "username": username,
            "process": process,
            "screen_msg": screen_msg,
            "screen": screen,
            "last_update": 0,
            "buffer": "",
        }
        
        asyncio.create_task(self._read_process_output(discord_id))
    
    async def _read_process_output(self, discord_id):
        if discord_id not in self.sessions:
            return
        
        session = self.sessions[discord_id]
        process = session["process"]
        screen = session["screen"]
        
        try:
            while session["active"]:
                try:
                    chunk = await asyncio.wait_for(
                        process.stdout.read(4096),
                        timeout=0.05
                    )
                    
                    if not chunk:
                        break
                    
                    text = chunk.decode('utf-8', errors='replace')
                    self._process_terminal_output(screen, text)
                    
                    current_time = asyncio.get_event_loop().time()
                    if current_time - session["last_update"] > 0.1:
                        await self._update_screen(discord_id)
                        session["last_update"] = current_time
                    
                except asyncio.TimeoutError:
                    continue
                    
        except Exception as e:
            print(f"error reading process output: {e}")
            if discord_id in self.sessions:
                self.sessions[discord_id]["active"] = False
    
    def _process_terminal_output(self, screen, text):
        i = 0
        while i < len(text):
            char = text[i]
            
            if char == '\r':
                screen.carriage_return()
            elif char == '\n':
                screen.newline()
            elif char == '\b':
                screen.backspace()
            elif char == '\x1b':
                seq_len = self._handle_escape_sequence(screen, text[i:])
                i += seq_len - 1
            elif char == '\x07':
                pass
            elif ord(char) >= 32 or char == '\t':
                if char == '\t':
                    spaces = 8 - (screen.cursor_x % 8)
                    for _ in range(spaces):
                        screen.write_char(' ')
                else:
                    screen.write_char(char)
            
            i += 1
    
    def _handle_escape_sequence(self, screen, text):
        if len(text) < 2:
            return 1
        
        if text[1] == '[':
            match = re.match(r'\x1b\[([0-9;?]*)([a-zA-Z@])', text)
            if match:
                params_str = match.group(1).replace('?', '')
                command = match.group(2)
                params = []
                if params_str:
                    params = [int(p) if p else 0 for p in params_str.split(';')]
                
                if command == 'A':
                    n = params[0] if params else 1
                    screen.move_cursor(y=max(0, screen.cursor_y - n))
                elif command == 'B':
                    n = params[0] if params else 1
                    screen.move_cursor(y=min(screen.height - 1, screen.cursor_y + n))
                elif command == 'C':
                    n = params[0] if params else 1
                    screen.move_cursor(x=min(screen.width - 1, screen.cursor_x + n))
                elif command == 'D':
                    n = params[0] if params else 1
                    screen.move_cursor(x=max(0, screen.cursor_x - n))
                elif command == 'H' or command == 'f':
                    row = (params[0] - 1) if params and params[0] > 0 else 0
                    col = (params[1] - 1) if len(params) > 1 and params[1] > 0 else 0
                    screen.move_cursor(x=col, y=row)
                elif command == 'J':
                    mode = params[0] if params else 0
                    screen.clear_screen(mode)
                elif command == 'K':
                    mode = params[0] if params else 0
                    screen.clear_line(mode)
                elif command == 'S':
                    n = params[0] if params else 1
                    screen.scroll_up(n)
                elif command == 'T':
                    n = params[0] if params else 1
                    screen.scroll_down(n)
                elif command == 'r':
                    pass
                elif command == 'm':
                    if not params:
                        params = [0]
                    
                    ansi_parts = []
                    for param in params:
                        if param == 0:
                            screen.current_style = ''
                        elif param == 1:
                            ansi_parts.append('1')
                        elif param == 2:
                            ansi_parts.append('2')
                        elif param == 3:
                            ansi_parts.append('3')
                        elif param == 4:
                            ansi_parts.append('4')
                        elif param == 5:
                            ansi_parts.append('5')
                        elif param == 7:
                            ansi_parts.append('7')
                        elif 30 <= param <= 37:
                            ansi_parts.append(str(param))
                        elif param == 38:
                            idx = params.index(param)
                            if idx + 2 < len(params) and params[idx + 1] == 5:
                                ansi_parts.append(f'38;5;{params[idx + 2]}')
                            elif idx + 4 < len(params) and params[idx + 1] == 2:
                                ansi_parts.append(f'38;2;{params[idx + 2]};{params[idx + 3]};{params[idx + 4]}')
                        elif param == 39:
                            ansi_parts.append('39')
                        elif 40 <= param <= 47:
                            ansi_parts.append(str(param))
                        elif param == 48:
                            idx = params.index(param)
                            if idx + 2 < len(params) and params[idx + 1] == 5:
                                ansi_parts.append(f'48;5;{params[idx + 2]}')
                            elif idx + 4 < len(params) and params[idx + 1] == 2:
                                ansi_parts.append(f'48;2;{params[idx + 2]};{params[idx + 3]};{params[idx + 4]}')
                        elif param == 49:
                            ansi_parts.append('49')
                        elif 90 <= param <= 97:
                            ansi_parts.append(str(param))
                        elif 100 <= param <= 107:
                            ansi_parts.append(str(param))
                    
                    if ansi_parts:
                        screen.current_style = f'\x1b[{";".join(ansi_parts)}m'
                    else:
                        screen.current_style = ''
                elif command == 's':
                    screen.saved_cursor = (screen.cursor_x, screen.cursor_y)
                elif command == 'u':
                    screen.cursor_x, screen.cursor_y = screen.saved_cursor
                elif command == 'l' or command == 'h':
                    pass
                
                return len(match.group(0))
        
        elif text[1] == ']':
            match = re.match(r'\x1b\][^\x07\x1b]*(\x07|\x1b\\)', text)
            if match:
                return len(match.group(0))
            end = text.find('\x07', 2)
            if end != -1:
                return end + 1
            end = text.find('\x1b\\', 2)
            if end != -1:
                return end + 2
        
        elif text[1] in '>=':
            return 2
        elif text[1] == '(':
            if len(text) > 2:
                return 3
            return 2
        elif text[1] == ')':
            if len(text) > 2:
                return 3
            return 2
        
        return 2
    
    async def _update_screen(self, discord_id):
        if discord_id not in self.sessions:
            return
        
        session = self.sessions[discord_id]
        screen = session["screen"]
        
        lines = screen.get_display(show_cursor=True)
        
        screen_content = "```ansi\n" + "\n".join(lines) + "\n```"
        
        if len(screen_content) > 1990:
            lines = screen.get_display(show_cursor=False)
            screen_content = "```ansi\n" + "\n".join(lines) + "\n```"
            
            if len(screen_content) > 1990:
                truncated_lines = []
                current_length = 12
                
                for line in lines:
                    line_length = len(line) + 1
                    if current_length + line_length > 1980:
                        break
                    truncated_lines.append(line)
                    current_length += line_length
                
                truncated_lines.append("... output truncated, use [PGUP]/[PGDN] to scroll")
                screen_content = "```ansi\n" + "\n".join(truncated_lines) + "\n```"
        
        try:
            await session["screen_msg"].edit(content=screen_content)
        except discord.errors.NotFound:
            session["active"] = False
        except Exception as e:
            print(f"error updating screen: {e}")
    
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
            except Exception:
                process.kill()
            
            if discord_id in self.sessions:
                del self.sessions[discord_id]
            
            await message.channel.send("shell session closed")
            try:
                await message.delete()
            except Exception:
                pass
            return
        
        screen = session["screen"]
        
        if content == '[PGUP]':
            screen.scroll_view_up(12)
            await self._update_screen(discord_id)
            try:
                await message.delete()
            except Exception:
                pass
            return
        
        if content == '[PGDN]':
            screen.scroll_view_down(12)
            await self._update_screen(discord_id)
            try:
                await message.delete()
            except Exception:
                pass
            return
        
        try:
            await message.delete()
        except Exception:
            pass
        
        process = session["process"]
        
        translated = content
        
        translated = translated.replace('[<]', '\b')
        if '[<' in translated and ']' in translated:
            pattern = r'\[<(\d+)\]'
            def replace_backspace(match):
                count = int(match.group(1))
                return '\b' * count
            translated = re.sub(pattern, replace_backspace, translated)
        
        translated = translated.replace('[^C]', '\x03')
        translated = translated.replace('[^D]', 'echo use [EXIT] to leave the shell\n')
        translated = translated.replace('[^Z]', '\x1a')
        translated = translated.replace('[^L]', '\x0c')
        translated = translated.replace('[UP]', '\x1b[A')
        translated = translated.replace('[DOWN]', '\x1b[B')
        translated = translated.replace('[RIGHT]', '\x1b[C')
        translated = translated.replace('[LEFT]', '\x1b[D')
        translated = translated.replace('[HOME]', '\x1b[H')
        translated = translated.replace('[END]', '\x1b[F')
        translated = translated.replace('[PGUP]', '\x1b[5~')
        translated = translated.replace('[PGDN]', '\x1b[6~')
        translated = translated.replace('[]', '\n')
        
        if '[^]' in translated:
            parts = translated.split('[^]')
            for i in range(1, len(parts)):
                if parts[i]:
                    first_char = parts[i][0]
                    if first_char == "D":
                        parts[i] = "echo use [EXIT] to leave the shell\n"
                    elif first_char.isalpha():
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