import urwid


class EditableMixin:
    signals = ["aborted", "validated"]

    def keypress(self, size, key):
        if key == "esc":
            urwid.emit_signal(self, "aborted")
            self.reset()
        elif key == "enter":
            w_edit = getattr(self, "w_edit", self)
            edit_text = w_edit.get_edit_text()
            urwid.emit_signal(self, "validated", edit_text)
            self.reset()
        else:
            # NB: Mark every key as handled, i.e. always return None.
            # This way, it is not propagated to other widgets.
            super().keypress(size, key)

    def reset(self):
        w_edit = getattr(self, "w_edit", self)
        w_edit.set_caption("")
        w_edit.set_edit_text("")
