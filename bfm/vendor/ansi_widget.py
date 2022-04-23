# https://github.com/kpj/pdftty/blob/master/pdftty/ansi_widget.py
# commit 345436ef27a9264b9039b414af59c14bb1f8bbe4

"""
MIT License

Copyright (c) 2021 Kim Philipp Jablonski

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import re
from typing import Any, Iterable, List, Optional, Tuple

import urwid

# https://thewebdev.info/2022/04/10/how-to-remove-the-ansi-escape-sequences-from-a-string-in-python-2/
ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")


# XXX: ugly name, ugly code
def ansi_truncate_and_fill(string: bytes, width: int):
    string = string.decode()
    output = ""
    total_len = 0

    texts = ansi_escape.split(string)
    codes = [""] + ansi_escape.findall(string)

    for code, text in zip(codes, texts):
        remaining = width - total_len
        text = text[:remaining]
        output += code + text
        total_len += len(text)

    padding = " " * max(0, width - total_len)

    return (output + padding).encode()


class ANSICanvas(urwid.canvas.Canvas):
    def __init__(self, size: Tuple[int, int], text: bytes) -> None:
        super().__init__()
        self.maxcols, self.maxrows = size
        self.text_lines = text.splitlines()

    def cols(self) -> int:
        return self.maxcols

    def rows(self) -> int:
        return self.maxrows

    def content(
        self,
        trim_left: int = 0,
        trim_top: int = 0,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
        attr_map: Optional[Any] = None,
    ) -> Iterable[List[Tuple[None, str, bytes]]]:
        assert cols is not None
        assert rows is not None

        lines = iter(self.text_lines)

        for _ in range(rows):
            line = next(lines, b"")
            text = ansi_truncate_and_fill(line, width=cols)
            yield [(None, "U", text)]


class ANSIWidget(urwid.Widget):
    _sizing = frozenset([urwid.widget.BOX])

    def __init__(self, text: bytes = b"") -> None:
        self.text = text

    def append(self, text: bytes = b"") -> None:
        self.text += text
        self._invalidate()

    def clear(self) -> None:
        self.text = b""
        self._invalidate()

    def render(
        self, size: Tuple[int, int], focus: bool = False
    ) -> urwid.canvas.Canvas:
        return ANSICanvas(size, self.text)
