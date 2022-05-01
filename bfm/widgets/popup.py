from functools import partial

import urwid

from .misc import MyEdit


class PopUpMixin:
    signals = ["close"]

    def close(self, success, *args):
        urwid.emit_signal(self, "close", success, *args)


class EditPopUp(PopUpMixin, urwid.WidgetWrap):
    def __init__(self, title: str, text: str):
        w = MyEdit(edit_text=text)
        urwid.connect_signal(w, "aborted", partial(self.close, False))
        urwid.connect_signal(w, "validated", partial(self.close, True))
        w = urwid.Filler(w)
        w = urwid.LineBox(w, title=title, title_align="left")
        w = urwid.AttrMap(w, "popup")

        urwid.WidgetWrap.__init__(self, w)
