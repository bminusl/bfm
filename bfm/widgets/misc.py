import urwid


class MyEdit(urwid.Edit):
    signals = ["aborted", "validated"]

    def keypress(self, size, key):
        edit_text = self.get_edit_text()
        if key == "esc":
            self.reset()
            urwid.emit_signal(self, "aborted", edit_text)
        elif key == "enter":
            self.reset()
            urwid.emit_signal(self, "validated", edit_text)
        else:
            # NB: Mark every key as handled, i.e. always return None.
            # This way, it is not propagated to other widgets.
            super().keypress(size, key)

    def reset(self):
        self.set_caption("")
        self.set_edit_text("")
