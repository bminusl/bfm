import os
import sys

import urwid

from .palette import palette
from .widgets import BFMWidget


def main():
    def exit_on_q(key):
        if key == "q":
            raise urwid.ExitMainLoop

    try:
        path = os.path.abspath(os.path.expanduser(sys.argv[1]))
    except IndexError:
        path = os.getcwd()
    global loop
    loop = urwid.MainLoop(
        BFMWidget(path), palette, unhandled_input=exit_on_q, handle_mouse=False
    )
    loop.run()
