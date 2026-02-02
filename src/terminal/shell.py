import asyncio
import re
from pathlib import Path

import discord
from discord.ext import commands

import config
from src.achievements.utils import get_achievement_system
from src.misc import CogHelper, has_shell_access
from src.terminal import get_docker_service
from src.terminal.terminal import Terminal


class Shell(CogHelper, commands.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.docker = get_docker_service()
        self.achievements = get_achievement_system()
        self.home_dir = Path("hazelrun/home")
        self.working_dirs = {}
        self.sessions = {}

        if not self.home_dir.exists():
            self.home_dir.mkdir(parents=True, exist_ok=True)

    async def exec_cmd(self, username: str, discord_id: str, command: str, ctx=None):
        """execute command in container as user"""
        await self.docker.ensure_user_exists(username, discord_id, self.home_dir)

        wd = self.working_dirs.get(discord_id, f"/home/{username}")

        output, exit_code = await self.docker.exec_command(
            f"cd {wd} && {command}",
            username=username,
            discord_id=discord_id,
            working_dir=wd,
            timeout=30.0,
        )

        if ctx:
            await self.achievements.check_command_achievement(
                discord_id, command, exit_code, ctx.guild, ctx.channel
            )

        return output if output else f"hzsh: {command}: zero code with no output"

    @commands.command(name="hzsh", aliases=["shell", "bash", "ssh"])
    async def hzsh(self, ctx):
        """start interactive shell session"""
        if not has_shell_access(ctx.author):
            await ctx.send(f"you are not connected to `{config.NAME}`.")
            return

        username = ctx.author.name
        discord_id = str(ctx.author.id)

        if discord_id in self.sessions:
            await ctx.send("youre already connected")
            return

        await self.docker.ensure_user_exists(username, discord_id, self.home_dir)

        uid = self.docker.get_uid(discord_id)
        wd = self.working_dirs.get(discord_id, f"/home/{username}")

        process = await asyncio.create_subprocess_exec(
            "docker",
            "exec",
            "-i",
            "-u",
            str(uid),
            "-w",
            wd,
            self.docker.container_name,
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

        await self.achievements.grant_achievement(
            discord_id, "thestart", ctx.guild, ctx.channel
        )

    async def _read_output(self, discord_id):
        """read output from shell process"""
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

        except Exception as e:
            self.log_error(f"error reading shell output: {e}")
            if discord_id in self.sessions:
                self.sessions[discord_id]["active"] = False

    def _process_output(self, screen, text):
        """process terminal output - same as before"""
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
            elif char in ["\x0e", "\x0f", "\x00"]:
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
        """handle ANSI escape sequences - same as before"""
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

                if command == "A":
                    n = params[0] if params else 1
                    screen.move_cursor(y=max(0, screen.cursor_y - n))
                elif command == "B":
                    n = params[0] if params else 1
                    screen.move_cursor(y=min(screen.height - 1, screen.cursor_y + n))
                elif command == "C":
                    n = params[0] if params else 1
                    screen.move_cursor(x=min(screen.width - 1, screen.cursor_x + n))
                elif command == "D":
                    n = params[0] if params else 1
                    screen.move_cursor(x=max(0, screen.cursor_x - n))
                elif command in ["H", "f"]:
                    row = (params[0] - 1) if params and params[0] > 0 else 0
                    col = (params[1] - 1) if len(params) > 1 and params[1] > 0 else 0
                    screen.move_cursor(x=col, y=row)

                elif command == "J":
                    screen.clear_screen(params[0] if params else 0)
                elif command == "K":
                    screen.clear_line(params[0] if params else 0)

                elif command == "S":
                    screen.scroll_up(params[0] if params else 1)
                elif command == "T":
                    screen.scroll_down(params[0] if params else 1)

                elif command == "m":
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

                elif command == "s":
                    screen.saved_cursor = (screen.cursor_x, screen.cursor_y)
                elif command == "u":
                    screen.cursor_x, screen.cursor_y = screen.saved_cursor

                return len(match.group(0))

        elif text[1] == "]":
            match = re.match(r"\x1b\][^\x07\x1b]*(\x07|\x1b\\)", text)
            if match:
                return len(match.group(0))

        elif text[1] in ["7", "8", "M", "D", "E", "H", "c"]:
            return 2

        return 2

    async def _update(self, discord_id, flash=False):
        """update the displayed terminal"""
        if discord_id not in self.sessions:
            return

        session = self.sessions[discord_id]
        screen = session["screen"]

        lines = screen.get_display(show_cursor=True)

        if flash:
            inverted_lines = [f"\x1b[7m{line}\x1b[27m" for line in lines]
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
        except Exception as e:
            self.log_error(f"error updating terminal display: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """handle interactive shell input"""
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
            content_msg = "```ansi\n" + "\n".join(lines) + "\n```"

            try:
                await session["screen_msg"].edit(content=content_msg)
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

        await self.achievements.check_command_achievement(
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
        except Exception as e:
            self.log_error(f"error writing to shell stdin: {e}")


async def setup(bot):
    await bot.add_cog(Shell(bot))
