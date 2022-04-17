import os
import sys

import urwid

from .widgets import BFM


def main():
    def exit_on_q(key):
        if key == "q":
            raise urwid.ExitMainLoop

    palette = [
        ("path", "light cyan", "", "bold"),
        ("folder", "light cyan", ""),
        ("file", "", ""),
        ("unknown", "", "light magenta"),
    ]
    try:
        path = os.path.abspath(os.path.expanduser(sys.argv[1]))
    except IndexError:
        path = os.getcwd()
    global loop
    loop = urwid.MainLoop(
        BFM(path), palette, unhandled_input=exit_on_q, handle_mouse=False
    )
    loop.run()
