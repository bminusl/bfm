import os
import sys

import urwid

from .keys import unhandled_input
from .palette import palette
from .widgets import BFMWidget


def main():
    urwid.set_encoding("utf8")
    try:
        path = os.path.abspath(os.path.expanduser(sys.argv[1]))
    except IndexError:
        path = os.getcwd()
    global loop
    loop = urwid.MainLoop(
        None,
        palette,
        unhandled_input=unhandled_input,
        handle_mouse=False,
    )
    # BFMWidget needs access to the loop when `__init__`iated.
    loop.widget = BFMWidget(path)
    loop.run()
