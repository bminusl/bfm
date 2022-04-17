import os
import weakref
from subprocess import call

import urwid

from .mixins import TreeNavigationMixin


class Item(urwid.Text):
    signals = ["selected"]
    _selectable = True

    def _markup(self, prefix="", suffix=""):
        # TODO: handle symlinks
        if self.entry.is_dir(follow_symlinks=False):
            attr = "folder"
        else:
            attr = "file"
        # attr = "unknown"
        return attr, prefix + self.entry.name + suffix

    def __init__(self, entry: os.DirEntry):
        self.entry = entry
        super().__init__(self._markup())

    def render(self, size, focus=False):
        prefix = "> " if focus else "  "
        self.set_text(self._markup(prefix))
        return super().render(size, focus)

    def keypress(self, size, key):
        if key in ("l", "enter", "right"):
            urwid.emit_signal(self, "selected", self)
            return
        return key


class BFM(TreeNavigationMixin, urwid.WidgetWrap):
    def __init__(self, path: str):
        w_path = urwid.Text("")
        w_command = urwid.Text("")
        w_header = urwid.Pile([w_path, w_command])
        w_body = urwid.ListBox(urwid.SimpleListWalker([]))
        w = urwid.Frame(w_body, w_header)

        self._w_path = weakref.proxy(w_path)
        self._w_command = weakref.proxy(w_command)
        self._w_body = weakref.proxy(w_body)
        self._w_body_contents = weakref.proxy(w_body.body)

        # Keep focus positions when navigating the tree
        self.focus_cache = {}

        TreeNavigationMixin.__init__(self, path)
        urwid.WidgetWrap.__init__(self, w)

    def descend(self, *args, **kwargs):
        self.focus_cache[
            self._TreeNavigationMixin__path
        ] = self._w_body.focus_position
        super().descend(*args, **kwargs)
        # BBB: py3.8+ walrus operator
        position = self.focus_cache.get(self._TreeNavigationMixin__path)
        if position:
            self._w_body.set_focus(position)

    def ascend(self, *args, **kwargs):
        if self._w_body_contents:
            self.focus_cache[
                self._TreeNavigationMixin__path
            ] = self._w_body.focus_position
        from_ = super().ascend(*args, **kwargs)
        position = next(
            i
            for i, item in enumerate(self._w_body_contents)
            if item.entry.name == from_
        )
        self._w_body.set_focus(position)

    def _on_path_changed(self, new_path: str):
        def on_item_selected(item: Item):
            if item.entry.is_dir(follow_symlinks=False):
                self.descend(item.entry.name)
            else:
                self.edit_file(item.entry.path)

        self._w_path.set_text(("path", new_path))
        self._w_body_contents.clear()

        for entry in self.scan():
            item = Item(entry)
            self._w_body_contents.append(item)
            urwid.connect_signal(item, "selected", on_item_selected)

    def edit_file(self, path):
        from . import loop

        # see https://github.com/urwid/urwid/issues/302
        loop.screen.stop()
        call(["vim", path])
        loop.screen.start()

    def keypress(self, size, key):
        key_to_propagate = key
        if key in ("h", "backspace", "left"):
            self.ascend()
            return
        elif key in ("j", "down"):
            key_to_propagate = "down"
        elif key in ("k", "up"):
            key_to_propagate = "up"
        return super().keypress(size, key_to_propagate)
