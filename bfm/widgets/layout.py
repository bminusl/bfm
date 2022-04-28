from functools import partial

import urwid


class LastRenderedSizeMixin:
    def render(self, size, focus=False):
        self.__size = size
        return super().render(size, focus)


class FocusableFrameWidget(urwid.Pile):
    def __init__(self, header, body, footer):
        super().__init__([("pack", header), body, ("pack", footer)])
        self.focus_header = partial(self.set_focus, 0)
        self.focus_body = partial(self.set_focus, 1)
        self.focus_footer = partial(self.set_focus, 2)
        self.focus_body()
