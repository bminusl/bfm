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

        w_items = urwid.ListBox(urwid.SimpleListWalker([]))
        w_preview = urwid.WidgetPlaceholder(None)  # XXX: None is hacky
        w_body = urwid.Columns([w_items, w_preview])

        w = urwid.Frame(w_body, w_header)

        self._w_path = weakref.proxy(w_path)
        self._w_command = weakref.proxy(w_command)
        self._w_items = weakref.proxy(w_items)
        self._w_items_contents = weakref.proxy(w_items.body)
        self._w_preview = weakref.proxy(w_preview)

        # Keep focus positions when navigating the tree
        self.focus_cache = {}

        TreeNavigationMixin.__init__(self, path)
        urwid.WidgetWrap.__init__(self, w)

        urwid.connect_signal(
            w_items.body, "modified", self._on_items_contents_modified
        )
        self._on_items_contents_modified()

    def descend(self, *args, **kwargs):
        self.focus_cache[
            self._TreeNavigationMixin__path
        ] = self._w_items.focus_position
        super().descend(*args, **kwargs)
        # BBB: py3.8+ walrus operator
        position = self.focus_cache.get(self._TreeNavigationMixin__path)
        if position:
            self._w_items.set_focus(position)

    def ascend(self, *args, **kwargs):
        if self._w_items_contents:
            self.focus_cache[
                self._TreeNavigationMixin__path
            ] = self._w_items.focus_position
        from_ = super().ascend(*args, **kwargs)
        position = next(
            i
            for i, item in enumerate(self._w_items_contents)
            if item.entry.name == from_
        )
        self._w_items.set_focus(position)

    def _on_items_contents_modified(self):
        if self._w_items_contents:
            item = self._w_items.get_focus()[0]
            if item.entry.is_dir(follow_symlinks=False):
                contents = [Item(e) for e in self.scanpath(item.entry.path)]
                w_new = urwid.ListBox(urwid.SimpleListWalker(contents))
            else:
                # TODO: catch errors, large files, etc
                with open(item.entry.path) as f:
                    w_new = urwid.Text(f.read())
        else:
            w_new = urwid.Text("")
        if isinstance(w_new, urwid.Text):
            w_new = urwid.Filler(w_new, valign="top")
        self._w_preview.original_widget = w_new

    def _on_item_selected(self, item: Item):
        if item.entry.is_dir(follow_symlinks=False):
            self.descend(item.entry.name)
        else:
            self.edit_file(item.entry.path)

    def _on_path_changed(self, new_path: str):
        self._w_path.set_text(("path", new_path))
        self._w_items_contents.clear()

        for entry in self.scanpath():
            item = Item(entry)
            self._w_items_contents.append(item)
            urwid.connect_signal(item, "selected", self._on_item_selected)

    def edit_file(self, path: str):
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
