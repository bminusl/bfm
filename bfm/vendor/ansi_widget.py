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

# fmt: off
# flake8: noqa

from typing import Any, Iterable, List, Optional, Tuple

import urwid


class ANSICanvas(urwid.canvas.Canvas):
    def __init__(self, size: Tuple[int, int], text_lines: List[str]) -> None:
        super().__init__()

        self.maxcols, self.maxrows = size

        self.text_lines = text_lines

    def cols(self) -> int:
        return self.maxcols

    def rows(self) -> int:
        return self.maxrows

    def content(
        self,
        trim_left: int = 0, trim_top: int = 0,
        cols: Optional[int] = None, rows: Optional[int] = None,
        attr_map: Optional[Any] = None
    ) -> Iterable[List[Tuple[None, str, bytes]]]:
        assert cols is not None
        assert rows is not None

        for i in range(rows):
            if i < len(self.text_lines):
                text = self.text_lines[i].encode('utf-8')
            else:
                text = b''

            padding = bytes().rjust(max(0, cols - len(text)))
            line = [(None, 'U', text + padding)]

            yield line


class ANSIWidget(urwid.Widget):
    _sizing = frozenset([urwid.widget.BOX])

    def __init__(self, text: str = '') -> None:
        self.text = text

    def append(self, text: str = '') -> None:
        self.text += text
        self._invalidate()

    def clear(self) -> None:
        self.text = ""
        self._invalidate()

    def render(
        self,
        size: Tuple[int, int], focus: bool = False
    ) -> urwid.canvas.Canvas:
        canvas = ANSICanvas(size, self.text.split("\n"))

        return canvas


if __name__ == '__main__':
    txt = '\x1b[34;47mHello World\x1b[0m'

    urwid.MainLoop(urwid.Pile([
        urwid.Filler(urwid.Text(f'TextWidget: {txt}')),
        ANSIWidget(f'ANSIWidget: {txt}'),
    ])).run()
