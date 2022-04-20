import os
import sys

import urwid

from .keys import unhandled_input
from .palette import palette
from .widgets import BFMWidget


def main():
    try:
        path = os.path.abspath(os.path.expanduser(sys.argv[1]))
    except IndexError:
        path = os.getcwd()
    global loop
    loop = urwid.MainLoop(
        BFMWidget(path),
        palette,
        unhandled_input=unhandled_input,
        handle_mouse=False,
    )
    loop.run()
