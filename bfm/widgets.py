import os
import weakref
from subprocess import call

import urwid

from bfm.util import mydefaultdict

from .mixins import TreeNavigationMixin


class Item(urwid.WidgetWrap):
    signals = ["selected"]
    _selectable = True

    def __init__(self, number: int, entry: os.DirEntry):
        self.entry = entry

        text = entry.name
        # TODO: handle symlinks
        if self.entry.is_dir(follow_symlinks=False):
            attr = "folder"
            text += "/"
        else:
            attr = "file"
        # attr = "unknown"

        w = urwid.Text(text)
        w._selectable = True
        w = urwid.Padding(w, left=1, right=1)
        w = urwid.AttrMap(w, attr, focus_map="focus")
        super().__init__(w)

    def keypress(self, size, key):
        if key in ("l", "enter", "right"):
            urwid.emit_signal(self, "selected", self)
            return
        return key


class Folder(urwid.ListBox):
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
        w_folder_placeholder = urwid.WidgetPlaceholder(w_empty)
        w_preview_placeholder = AlwaysFocusedWidgetPlaceholder(w_empty)
        w_body = urwid.Columns([w_folder_placeholder, w_preview_placeholder])

        w = urwid.Frame(w_body, w_header)

        # Cache Folder instances when navigating the tree to reuse them later
        self._folders = mydefaultdict(lambda key: self.create_folder(key))

        self._w_path = weakref.proxy(w_path)
        self._w_command = weakref.proxy(w_command)
        self._w_folder_placeholder = weakref.proxy(w_folder_placeholder)
        self._w_preview_placeholder = weakref.proxy(w_preview_placeholder)

        TreeNavigationMixin.__init__(self, path)
        urwid.WidgetWrap.__init__(self, w)

    def create_folder(self, path: str):
        w = Folder([Item(*args) for args in enumerate(self.scanpath(path))])
        for item in w.body:
            urwid.connect_signal(item, "selected", self._on_item_selected)
        urwid.connect_signal(w.body, "modified", self._update_preview)
        return w

    def _update_preview(self):
        def get_focused_item():
            w_folder = self._w_folder_placeholder.original_widget
            if w_folder.body:
                return w_folder.get_focus()[0]

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
                w = self._folders[path]
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

    def ascend(self, *args, **kwargs):
        from_ = super().ascend(*args, **kwargs)
        # Patch to focus the correct item when ascending
        folder = self._w_folder_placeholder.original_widget
        for i, item in enumerate(folder.body):
            if item.entry.name == from_:
                folder.set_focus(i)
                break

    def _on_path_changed(self, new_path: str):
        self._w_path.set_text(("path", new_path))
        self._w_folder_placeholder.original_widget = self._folders[new_path]
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


class AlwaysFocusedWidgetPlaceholder(urwid.WidgetPlaceholder):
    def render(self, size, focus=False):
        return super().render(size, True)
