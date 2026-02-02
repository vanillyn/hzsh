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
        """clear the entire terminal"""
        self.buffer = [
            [(" ", "") for _ in range(self.width)] for _ in range(self.height)
        ]
        self.scrollback = []
        self.cursor_x = 0
        self.cursor_y = 0
        self.scroll_offset = 0

    def clear_line(self, mode=0):
        """clear line (0=cursor to end, 1=start to cursor, 2=entire line)"""
        if mode == 0:
            for x in range(self.cursor_x, self.width):
                self.buffer[self.cursor_y][x] = (" ", "")
        elif mode == 1:
            for x in range(0, self.cursor_x + 1):
                self.buffer[self.cursor_y][x] = (" ", "")
        elif mode == 2:
            self.buffer[self.cursor_y] = [(" ", "") for _ in range(self.width)]

    def clear_screen(self, mode=0):
        """clear screen (0=cursor to end, 1=start to cursor, 2=entire screen)"""
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
        """write a single character at cursor position"""
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
        """move to next line"""
        self.cursor_x = 0
        self.cursor_y += 1
        if self.cursor_y >= self.height:
            self.scroll_up()
            self.cursor_y = self.height - 1

    def carriage_return(self):
        """move cursor to start of line"""
        self.cursor_x = 0

    def backspace(self):
        """move cursor back one position"""
        if self.cursor_x > 0:
            self.cursor_x -= 1

    def move_cursor(self, x=None, y=None):
        """move cursor to specific position"""
        if x is not None:
            self.cursor_x = max(0, min(x, self.width - 1))
        if y is not None:
            self.cursor_y = max(0, min(y, self.height - 1))

    def scroll_up(self, lines=1):
        """scroll buffer up by lines"""
        for _ in range(lines):
            self.scrollback.append(self.buffer[0])
            if len(self.scrollback) > self.scrollback_limit:
                self.scrollback.pop(0)
            self.buffer.pop(0)
            self.buffer.append([(" ", "") for _ in range(self.width)])

    def scroll_down(self, lines=1):
        """scroll buffer down by lines"""
        for _ in range(lines):
            self.buffer.pop()
            self.buffer.insert(0, [(" ", "") for _ in range(self.width)])

    def get_display(self, show_cursor=True):
        """get the current display as list of strings"""
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
