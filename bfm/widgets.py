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


class ItemList(urwid.ListBox):
    def __init__(self, body):
        super().__init__(urwid.SimpleListWalker(body))

    def keypress(self, size, key):
        key_to_propagate = key
        if key in ("j", "down"):
            key_to_propagate = "down"
        elif key in ("k", "up"):
            key_to_propagate = "up"
        return super().keypress(size, key_to_propagate)


class BFM(TreeNavigationMixin, urwid.WidgetWrap):
    def __init__(self, path: str):
        w_path = urwid.Text("")
        w_command = urwid.Text("")
        w_header = urwid.Pile([w_path, w_command])

        # IMPORTANT:
        # The original_widget parameter passed to urwid.WidgetPlaceholder MUST
        # be selectable.
        # If not, it will not work properly when we want to replace it with a
        # selectable one, i.e. `placeholder.original_widget = new_widget`.
        # This seems to be a bug/non-documented behaviour. urwid.SelectableIcon
        # is thus used as a workaround/trick. See this discussion[0].
        # [0]: https://gitter.im/urwid/community?at=5f90305cea6bfb0a9a4bd0ac
        w_empty = urwid.Filler(urwid.SelectableIcon(""), valign="top")
        w_item_list_placeholder = urwid.WidgetPlaceholder(w_empty)
        w_preview_placeholder = urwid.WidgetPlaceholder(w_empty)
        w_body = urwid.Columns([w_item_list_placeholder, w_preview_placeholder])

        w = urwid.Frame(w_body, w_header)

        # Cache ItemList instances when navigating the tree to reuse them later
        # XXX/TODO: need a better name?
        self.cache = {}

        self._w_path = weakref.proxy(w_path)
        self._w_command = weakref.proxy(w_command)
        self._w_item_list_placeholder = weakref.proxy(w_item_list_placeholder)
        self._w_preview_placeholder = weakref.proxy(w_preview_placeholder)

        TreeNavigationMixin.__init__(self, path)
        urwid.WidgetWrap.__init__(self, w)

    def _get_item_list_by_path(self, path: str):
        w = self.cache.get(path)
        if w is None:
            w = ItemList([Item(entry) for entry in self.scanpath(path)])
            for item in w.body:
                urwid.connect_signal(item, "selected", self._on_item_selected)
            urwid.connect_signal(w.body, "modified", self._update_preview)
            self.cache[path] = w
        return w

    def _update_preview(self):
        def get_focused_item():
            w_item_list = self._w_item_list_placeholder.original_widget
            if w_item_list.body:
                return w_item_list.get_focus()[0]

        def preview_file(path):
            # TODO: catch errors, large files, etc
            with open(path) as f:
                w = urwid.Text(f.read())
                w = urwid.Filler(w, valign="top")
                return w

        # BBB: py3.8+ walrus operator
        item = get_focused_item()
        if item:
            path = item.entry.path
            if item.entry.is_dir(follow_symlinks=False):
                w = self._get_item_list_by_path(path)
            else:
                w = preview_file(path)
        else:
            w = urwid.Text("")
            w = urwid.Filler(w, valign="top")
        self._w_preview_placeholder.original_widget = w

    def _on_item_selected(self, item: Item):
        if item.entry.is_dir(follow_symlinks=False):
            self.descend(item.entry.name)
        else:
            self.edit_file(item.entry.path)

    def _on_path_changed(self, new_path: str):
        self._w_path.set_text(("path", new_path))
        self._w_item_list_placeholder.original_widget = (
            self._get_item_list_by_path(new_path)
        )
        self._update_preview()

    def edit_file(self, path: str):
        from . import loop

        # see https://github.com/urwid/urwid/issues/302
        loop.screen.stop()
        call(["vim", path])
        loop.screen.start()

    def keypress(self, size, key):
        if key in ("h", "backspace", "left"):
            self.ascend()
            return
        return super().keypress(size, key)
