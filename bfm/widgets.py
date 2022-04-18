import os
import stat
import subprocess
import weakref
from datetime import datetime
from grp import getgrgid
from pwd import getpwuid
from subprocess import call

import urwid

from bfm.util import mydefaultdict
from bfm.vendor.ansi_widget import ANSIWidget

from .mixins import TreeNavigationMixin


class Item(urwid.WidgetWrap):
    signals = ["selected"]

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

        stats = str(entry.stat().st_size)

        w_name = urwid.Text(text)
        w_stats = urwid.Text(stats)
        w = urwid.Columns([w_name, ("pack", w_stats)])
        w._selectable = True  # XXX: which widget should be selectable?
        w = urwid.Padding(w, left=1, right=1)
        w = urwid.AttrMap(w, attr, focus_map="focus")
        super().__init__(w)

    def keypress(self, size, key):
        if key in ("l", "enter", "right"):
            urwid.emit_signal(self, "selected", self)
            return
        return key

    def meta(self):
        stats = self.entry.stat()
        mode = stat.filemode(stats.st_mode)
        nlink = stats.st_nlink
        user = getpwuid(stats.st_uid).pw_name
        group = getgrgid(stats.st_gid).gr_name
        mtime = datetime.utcfromtimestamp(stats.st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return " ".join(map(str, [mode, nlink, user, group, mtime]))


class Folder(urwid.ListBox):
    signals = ["focus_changed"]

    def __init__(self, items):
        super().__init__(urwid.SimpleListWalker(items))
        urwid.connect_signal(self.body, "modified", self._on_body_modified)

    def _on_body_modified(self):
        urwid.emit_signal(self, "focus_changed", self.get_focused_item())

    def keypress(self, size, key):
        key_to_propagate = key
        if key in ("j", "down"):
            key_to_propagate = "down"
        elif key in ("k", "up"):
            key_to_propagate = "up"
        return super().keypress(size, key_to_propagate)

    def get_focused_item(self) -> Item:
        return self.get_focus()[0] if self.body else None


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
        w_preview_placeholder = urwid.WidgetPlaceholder(w_empty)
        w_body = urwid.Columns(
            [w_folder_placeholder, w_preview_placeholder], dividechars=1
        )

        w_extra = urwid.Text("")

        w = urwid.Frame(w_body, w_header, w_extra)
        w = urwid.Padding(w, left=1, right=1)

        # Cache Folder instances when navigating the tree to reuse them later
        self._folders = mydefaultdict(lambda key: self.create_folder(key))

        self._w_path = weakref.proxy(w_path)
        self._w_command = weakref.proxy(w_command)
        self._w_folder_placeholder = weakref.proxy(w_folder_placeholder)
        self._w_preview_placeholder = weakref.proxy(w_preview_placeholder)
        self._w_extra = weakref.proxy(w_extra)

        TreeNavigationMixin.__init__(self, path)
        urwid.WidgetWrap.__init__(self, w)

    def create_folder(self, path: str):
        w = Folder([Item(*args) for args in enumerate(self.scanpath(path))])
        for item in w.body:
            urwid.connect_signal(item, "selected", self._on_item_selected)
        urwid.connect_signal(w, "focus_changed", self._on_folder_focus_changed)
        return w

    def _on_folder_focus_changed(self, item: Item):
        if item:
            path = item.entry.path
            if item.entry.is_dir(follow_symlinks=False):
                command = 'tree -C -a -L 1 -F "{path}"'
            else:
                command = 'bat --color=always --style=numbers --line-range=:500 "{path}"'  # noqa:E501
            # TODO: catch errors
            text = subprocess.run(
                command.format(path=path), shell=True, capture_output=True
            ).stdout.decode()

            self._w_extra.set_text(item.meta())
        else:
            text = ""

        w = ANSIWidget(text)
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
        folder = self._folders[new_path]
        self._w_folder_placeholder.original_widget = folder
        self._on_folder_focus_changed(folder.get_focused_item())  # Trick

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
