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
        self.buffer = [[(" ", "") for _ in range(width)] for _ in range(height)]
        self.scrollback = []
        self.cursor_x = 0
        self.cursor_y = 0
        self.saved_cursor = (0, 0)
        self.current_style = ""
        self.scroll_offset = 0

    def clear(self):
        self.buffer = [
            [(" ", "") for _ in range(self.width)] for _ in range(self.height)
        ]
        self.scrollback = []
        self.cursor_x = 0
        self.cursor_y = 0
        self.scroll_offset = 0

    def clear_line(self, mode=0):
        if mode == 0:
            for x in range(self.cursor_x, self.width):
                self.buffer[self.cursor_y][x] = (" ", "")
        elif mode == 1:
            for x in range(0, self.cursor_x + 1):
                self.buffer[self.cursor_y][x] = (" ", "")
        elif mode == 2:
            self.buffer[self.cursor_y] = [(" ", "") for _ in range(self.width)]

    def clear_screen(self, mode=0):
        if mode == 0:
            for x in range(self.cursor_x, self.width):
                self.buffer[self.cursor_y][x] = (" ", "")
            for y in range(self.cursor_y + 1, self.height):
                self.buffer[y] = [(" ", "") for _ in range(self.width)]
        elif mode == 1:
            for x in range(0, self.cursor_x + 1):
                self.buffer[self.cursor_y][x] = (" ", "")
            for y in range(0, self.cursor_y):
                self.buffer[y] = [(" ", "") for _ in range(self.width)]
        elif mode == 2:
            self.buffer = [
                [(" ", "") for _ in range(self.width)] for _ in range(self.height)
            ]

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
            self.buffer.append([(" ", "") for _ in range(self.width)])

    def scroll_down(self, lines=1):
        for _ in range(lines):
            self.buffer.pop()
            self.buffer.insert(0, [(" ", "") for _ in range(self.width)])

    def get_display(self, show_cursor=True):
        if self.scroll_offset > 0:
            offset = self.scroll_offset
            if offset <= len(self.scrollback):
                start = len(self.scrollback) - offset
                visible = self.scrollback[start : start + self.height]
                remaining = self.height - len(visible)
                if remaining > 0:
                    visible.extend(self.buffer[:remaining])
            else:
                visible = self.buffer
        else:
            visible = self.buffer

        lines = []
        for y, line_buffer in enumerate(visible):
            parts = []
            current_ansi = ""

            for x in range(self.width):
                if x >= len(line_buffer):
                    break

                char, style = line_buffer[x]
                show_here = (
                    show_cursor
                    and self.scroll_offset == 0
                    and y == self.cursor_y
                    and x == self.cursor_x
                )

                if show_here:
                    if current_ansi:
                        parts.append("\x1b[0m")
                        current_ansi = ""
                    parts.append("\x1b[7m")
                    parts.append(char if char != " " else " ")
                    parts.append("\x1b[27m")
                    if style:
                        parts.append(style)
                        current_ansi = style
                else:
                    if style != current_ansi:
                        if current_ansi:
                            parts.append("\x1b[0m")
                        if style:
                            parts.append(style)
                        current_ansi = style
                    parts.append(char)

            if current_ansi:
                parts.append("\x1b[0m")

            line = "".join(parts)
            lines.append(
                line
                if line
                and not line.replace("\x1b[0m", "")
                .replace("\x1b[7m", "")
                .replace("\x1b[27m", "")
                .isspace()
                else " "
            )

        return lines


class Shell(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.container = "hzsh_linux"
        self.home_dir = Path("hazelrun/home")
        self.working_dirs = {}
        self.sessions = {}
        self.user_id_map = {}

        if not self.home_dir.exists():
            self.home_dir.mkdir(parents=True, exist_ok=True)

    def get_uid(self, discord_id: str):
        if discord_id not in self.user_id_map:
            hash_val = int(hashlib.sha256(discord_id.encode()).hexdigest()[:8], 16)
            self.user_id_map[discord_id] = (hash_val % 2147483147) + 1000
        return self.user_id_map[discord_id]

    def has_access(self, member):
        return (
            discord.utils.get(member.roles, name=config.SHELL_ACCESS_ROLE) is not None
        )

    def ensure_home(self, username: str, discord_id: str):
        # create user home dir and container user if needed
        user_home = self.home_dir / username
        uid = self.get_uid(discord_id)

        if not user_home.exists():
            user_home.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                ["docker", "exec", self.container, "id", "-u", str(uid)],
                capture_output=True,
            )

            if result.returncode != 0:
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        self.container,
                        "useradd",
                        "-u",
                        str(uid),
                        "-m",
                        "-s",
                        "/bin/bash",
                        username,
                    ],
                    capture_output=True,
                )

            subprocess.run(
                [
                    "docker",
                    "exec",
                    self.container,
                    "chown",
                    "-R",
                    f"{uid}:{uid}",
                    f"/home/{username}",
                ],
                capture_output=True,
            )

        if discord_id not in self.working_dirs:
            self.working_dirs[discord_id] = f"/home/{username}"

        return user_home

    async def exec_cmd(self, username: str, discord_id: str, command: str, ctx=None):
        # execute command in container as user
        self.ensure_home(username, discord_id)
        uid = self.get_uid(discord_id)
        wd = self.working_dirs.get(discord_id, f"/home/{username}")

        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "exec",
                "-u",
                str(uid),
                "-w",
                wd,
                self.container,
                "bash",
                "-c",
                f"cd {wd} && {command}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            exit_code = process.returncode

            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")
            result = output + error

            if ctx:
                ach_cog = self.bot.get_cog("Achievements")
                if ach_cog:
                    await ach_cog.check_command_achievement(
                        discord_id, command, exit_code, ctx.guild, ctx.channel
                    )

            return result if result else f"hzsh: {command}: zero code with no output"

        except asyncio.TimeoutError:
            return f"hzsh: {command}: timeout"
        except Exception as e:
            return f"hzsh: {command}: {str(e)}"

    @commands.command(name="hzsh", aliases=["shell", "bash", "ssh"])
    async def hzsh(self, ctx):
        # start interactive shell session
        if not self.has_access(ctx.author):
            await ctx.send(f"you are not connected to `{config.NAME}`.")
            return

        username = ctx.author.name
        discord_id = str(ctx.author.id)

        if discord_id in self.sessions:
            await ctx.send("youre already connected")
            return

        self.ensure_home(username, discord_id)
        uid = self.get_uid(discord_id)
        wd = self.working_dirs.get(discord_id, f"/home/{username}")

        process = await asyncio.create_subprocess_exec(
            "docker",
            "exec",
            "-i",
            "-u",
            str(uid),
            "-w",
            wd,
            self.container,
            "env",
            "TERM=xterm",
            "COLUMNS=80",
            "LINES=24",
            "script",
            "-qfc",
            "bash",
            "/dev/null",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        screen = Terminal(width=80, height=24, scrollback=1000)
        content = (
            "```ansi\n" + "\n".join(screen.get_display(show_cursor=False)) + "\n```"
        )
        msg = await ctx.send(content)

        self.sessions[discord_id] = {
            "channel": ctx.channel.id,
            "active": True,
            "username": username,
            "process": process,
            "screen_msg": msg,
            "screen": screen,
            "last_update": 0,
        }

        asyncio.create_task(self._read_output(discord_id))

    async def _read_output(self, discord_id):
        if discord_id not in self.sessions:
            return

        session = self.sessions[discord_id]
        process = session["process"]
        screen = session["screen"]

        try:
            while session["active"]:
                try:
                    chunk = await asyncio.wait_for(
                        process.stdout.read(4096), timeout=0.05
                    )

                    if not chunk:
                        break

                    text = chunk.decode("utf-8", errors="replace")
                    bell_triggered = self._process_output(screen, text)

                    current = asyncio.get_event_loop().time()
                    if current - session["last_update"] > 0.1:
                        await self._update(discord_id, flash=bell_triggered)
                        session["last_update"] = current
                    elif bell_triggered:
                        await self._update(discord_id, flash=True)
                        session["last_update"] = current

                except asyncio.TimeoutError:
                    continue

        except Exception:
            if discord_id in self.sessions:
                self.sessions[discord_id]["active"] = False

    def _process_output(self, screen, text):
        i = 0
        bell_triggered = False
        while i < len(text):
            char = text[i]

            if char == "\r":
                screen.carriage_return()
            elif char == "\n":
                screen.newline()
            elif char == "\b":
                screen.backspace()
            elif char == "\x1b":
                seq_len = self._handle_escape(screen, text[i:])
                i += seq_len - 1
            elif char == "\x07":
                bell_triggered = True
            elif char == "\x0e":
                pass
            elif char == "\x0f":
                pass
            elif char == "\x00":
                pass
            elif ord(char) >= 32 or char == "\t":
                if char == "\t":
                    spaces = 8 - (screen.cursor_x % 8)
                    for _ in range(spaces):
                        screen.write_char(" ")
                else:
                    screen.write_char(char)

            i += 1

        return bell_triggered

    def _handle_escape(self, screen, text):
        # handle ANSI escape sequences, comment indicates the escape sequences' function/meaning
        if len(text) < 2:
            return 1

        if text[1] == "[":
            match = re.match(r"\x1b\[([0-9;?]*)([a-zA-Z@])", text)
            if match:
                params_str = match.group(1).replace("?", "")
                command = match.group(2)
                params = (
                    [int(p) if p else 0 for p in params_str.split(";")]
                    if params_str
                    else []
                )

                if command == "A":  # cursor up
                    n = params[0] if params else 1
                    screen.move_cursor(y=max(0, screen.cursor_y - n))
                elif command == "B":  # cursor down
                    n = params[0] if params else 1
                    screen.move_cursor(y=min(screen.height - 1, screen.cursor_y + n))
                elif command == "C":  # cursor forward
                    n = params[0] if params else 1
                    screen.move_cursor(x=min(screen.width - 1, screen.cursor_x + n))
                elif command == "D":  # cursor back
                    n = params[0] if params else 1
                    screen.move_cursor(x=max(0, screen.cursor_x - n))
                elif command in ["H", "f"]:  # cursor position
                    row = (params[0] - 1) if params and params[0] > 0 else 0
                    col = (params[1] - 1) if len(params) > 1 and params[1] > 0 else 0
                    screen.move_cursor(x=col, y=row)
                elif command == "J":  # erase display
                    screen.clear_screen(params[0] if params else 0)
                elif command == "K":  # erase line
                    screen.clear_line(params[0] if params else 0)
                elif command == "S":  # scroll up
                    screen.scroll_up(params[0] if params else 1)
                elif command == "T":  # scroll down
                    screen.scroll_down(params[0] if params else 1)
                elif command == "G":  # cursor horizontal absolute
                    col = (params[0] - 1) if params and params[0] > 0 else 0
                    screen.move_cursor(x=col)
                elif command == "d":  # line position absolute
                    row = (params[0] - 1) if params and params[0] > 0 else 0
                    screen.move_cursor(y=row)
                elif command == "r":  # set scroll region (ignore for now)
                    pass
                elif command == "h":  # set mode (ignore most)
                    pass
                elif command == "l":  # reset mode (ignore most)
                    pass
                elif command == "m":  # sgr
                    if not params:
                        params = [0]

                    ansi_parts = []
                    i = 0
                    while i < len(params):
                        param = params[i]
                        if param == 0:
                            screen.current_style = ""
                        elif param in [1, 2, 3, 4, 5, 7, 8, 9]:
                            ansi_parts.append(str(param))
                        elif 30 <= param <= 37 or param == 39:
                            ansi_parts.append(str(param))
                        elif 40 <= param <= 47 or param == 49:
                            ansi_parts.append(str(param))
                        elif 90 <= param <= 97 or 100 <= param <= 107:
                            ansi_parts.append(str(param))
                        elif param == 38:
                            if i + 2 < len(params) and params[i + 1] == 5:
                                ansi_parts.append(f"38;5;{params[i + 2]}")
                                i += 2
                            elif i + 4 < len(params) and params[i + 1] == 2:
                                ansi_parts.append(
                                    f"38;2;{params[i + 2]};{params[i + 3]};{params[i + 4]}"
                                )
                                i += 4
                        elif param == 48:
                            if i + 2 < len(params) and params[i + 1] == 5:
                                ansi_parts.append(f"48;5;{params[i + 2]}")
                                i += 2
                            elif i + 4 < len(params) and params[i + 1] == 2:
                                ansi_parts.append(
                                    f"48;2;{params[i + 2]};{params[i + 3]};{params[i + 4]}"
                                )
                                i += 4
                        i += 1

                    screen.current_style = (
                        f"\x1b[{';'.join(ansi_parts)}m" if ansi_parts else ""
                    )
                elif command == "s":  # save cursor
                    screen.saved_cursor = (screen.cursor_x, screen.cursor_y)
                elif command == "u":  # restore cursor
                    screen.cursor_x, screen.cursor_y = screen.saved_cursor
                elif command == "@":  # insert characters
                    n = params[0] if params else 1
                    for _ in range(n):
                        screen.buffer[screen.cursor_y].insert(
                            screen.cursor_x, (" ", "")
                        )
                        if len(screen.buffer[screen.cursor_y]) > screen.width:
                            screen.buffer[screen.cursor_y].pop()
                elif command == "P":  # delete characters
                    n = params[0] if params else 1
                    for _ in range(n):
                        if screen.cursor_x < len(screen.buffer[screen.cursor_y]):
                            screen.buffer[screen.cursor_y].pop(screen.cursor_x)
                            screen.buffer[screen.cursor_y].append((" ", ""))
                elif command == "L":  # insert lines
                    n = params[0] if params else 1
                    for _ in range(n):
                        screen.buffer.insert(
                            screen.cursor_y, [(" ", "") for _ in range(screen.width)]
                        )
                        if len(screen.buffer) > screen.height:
                            screen.buffer.pop()
                elif command == "M":  # delete lines
                    n = params[0] if params else 1
                    for _ in range(n):
                        if screen.cursor_y < len(screen.buffer):
                            screen.buffer.pop(screen.cursor_y)
                            screen.buffer.append(
                                [(" ", "") for _ in range(screen.width)]
                            )

                return len(match.group(0))

        elif text[1] == "]":  # osc sequences
            match = re.match(r"\x1b\][^\x07\x1b]*(\x07|\x1b\\)", text)
            if match:
                return len(match.group(0))

        elif text[1] in ["7", "8", "M", "D", "E", "H", "c"]:  # single char escapes
            return 2

        return 2

    async def _update(self, discord_id, flash=False):
        if discord_id not in self.sessions:
            return

        session = self.sessions[discord_id]
        screen = session["screen"]

        lines = screen.get_display(show_cursor=True)

        if flash:
            inverted_lines = []
            for line in lines:
                inverted_lines.append(f"\x1b[7m{line}\x1b[27m")
            content = "```ansi\n" + "\n".join(inverted_lines) + "\n```"

            try:
                await session["screen_msg"].edit(content=content)
                await asyncio.sleep(0.15)
            except Exception:
                pass

        content = "```ansi\n" + "\n".join(lines) + "\n```"

        if len(content) > 1990:
            lines = screen.get_display(show_cursor=False)
            content = "```ansi\n" + "\n".join(lines) + "\n```"

            if len(content) > 1990:
                truncated = []
                current_len = 12

                for line in lines:
                    line_len = len(line) + 1
                    if current_len + line_len > 1980:
                        break
                    truncated.append(line)
                    current_len += line_len

                truncated.append("... output truncated, use [PGUP]/[PGDN] to scroll")
                content = "```ansi\n" + "\n".join(truncated) + "\n```"

        try:
            await session["screen_msg"].edit(content=content)
        except discord.errors.NotFound:
            session["active"] = False
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        discord_id = str(message.author.id)

        if discord_id not in self.sessions:
            return

        session = self.sessions[discord_id]

        if not session["active"] or message.channel.id != session["channel"]:
            return

        content = message.content

        if content == "[EXIT]":
            process = session["process"]
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except Exception:
                process.kill()

            screen = session["screen"]
            screen.clear()

            text = "shell session closed"
            row = screen.height // 2
            col = (screen.width - len(text)) // 2

            screen.move_cursor(x=col, y=row)
            for char in text:
                screen.write_char(char)

            lines = screen.get_display(show_cursor=False)
            content = "```ansi\n" + "\n".join(lines) + "\n```"

            try:
                await session["screen_msg"].edit(content=content)
            except Exception:
                pass

            del self.sessions[discord_id]

            try:
                await message.delete()
            except Exception:
                pass
            return

        try:
            await message.delete()
        except Exception:
            pass

        ach_cog = self.bot.get_cog("Achievements")
        if ach_cog:
            await ach_cog.check_command_achievement(
                discord_id, content, None, message.guild, message.channel
            )

        process = session["process"]

        translated = content
        translated = translated.replace("[<]", "\b")
        translated = re.sub(r"\[<(\d+)\]", lambda m: "\b" * int(m.group(1)), translated)
        translated = translated.replace("[^C]", "\x03")
        translated = translated.replace(
            "[^D]", "echo use [EXIT] to close the shell session[]"
        )
        translated = translated.replace("[^Z]", "\x1a")
        translated = translated.replace("[^L]", "\x0c")
        translated = translated.replace("[UP]", "\x1b[A")
        translated = translated.replace("[DOWN]", "\x1b[B")
        translated = translated.replace("[RIGHT]", "\x1b[C")
        translated = translated.replace("[LEFT]", "\x1b[D")
        translated = translated.replace("[HOME]", "\x1b[H")
        translated = translated.replace("[END]", "\x1b[F")
        translated = translated.replace("[PGUP]", "\x1b[5~")
        translated = translated.replace("[PGDN]", "\x1b[6~")
        translated = translated.replace("[]", "\n")

        if "[^]" in translated:
            parts = translated.split("[^]")
            for i in range(1, len(parts)):
                if parts[i]:
                    first = parts[i][0]
                    if first == "D":
                        parts[i] = (
                            "echo use [EXIT] to close the shell session[]"
                            + parts[i][1:]
                        )
                    elif first.isalpha():
                        parts[i] = chr(ord(first.upper()) - 64) + parts[i][1:]
            translated = "".join(parts)

        if "[#]" in translated:
            parts = translated.split("[#]")
            result = [parts[0]]
            for part in parts[1:]:
                if part:
                    result.append(part[0].upper() + part[1:])
            translated = "".join(result)

        try:
            process.stdin.write(translated.encode("utf-8"))
            await process.stdin.drain()
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Shell(bot))
