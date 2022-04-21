import os
import stat
import subprocess
import weakref
from datetime import datetime
from grp import getgrgid
from pwd import getpwuid

import urwid

from bfm.keys import ExtendedCommandMap
from bfm.util import mydefaultdict
from bfm.vendor.ansi_widget import ANSIWidget

from . import config
from .keys import CallableCommandsMixin
from .mixins import TreeNavigationMixin


class ItemWidget(CallableCommandsMixin, urwid.WidgetWrap):
    signals = ["selected"]
    _command_map = ExtendedCommandMap(
        {
            "l": lambda self: urwid.emit_signal(self, "selected", self),
        },
        aliases={"enter": "l", "right": "l"},
    )

    def __init__(self, number: int, entry: os.DirEntry):
        self.entry = entry

        text = entry.name
        # TODO: handle symlinks
        if self.entry.is_dir():
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


class FolderWidget(urwid.ListBox):
    signals = ["focus_changed"]
    _command_map = ExtendedCommandMap(
        {
            "j": "cursor down",
            "k": "cursor up",
            "gg": "cursor max left",
            "G": "cursor max right",
        },
        aliases={"down": "j", "up": "k"},
    )

    def __init__(self, items):
        super().__init__(urwid.SimpleListWalker(items))
        urwid.connect_signal(self.body, "modified", self._on_body_modified)

    def get_focused_item(self) -> ItemWidget:
        return self.get_focus()[0] if self.body else None

    def _on_body_modified(self):
        urwid.emit_signal(self, "focus_changed", self.get_focused_item())

    # https://github.com/urwid/urwid/issues/305
    def _keypress_max_left(self, *args, **kwargs):
        super()._keypress_max_left(*args, **kwargs)

    # https://github.com/urwid/urwid/issues/305
    def _keypress_max_right(self, *args, **kwargs):
        super()._keypress_max_right(*args, **kwargs)


class BFMWidget(CallableCommandsMixin, TreeNavigationMixin, urwid.WidgetWrap):
    _command_map = ExtendedCommandMap(
        {
            "h": lambda self: self.ascend(),
        },
        aliases={"backspace": "h", "left": "h"},
    )

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

        # Cache FolderWidget instances when navigating the tree to reuse them
        # later
        self._folders = mydefaultdict(self.create_folder)

        self._w_path = weakref.proxy(w_path)
        self._w_command = weakref.proxy(w_command)
        self._w_folder_placeholder = weakref.proxy(w_folder_placeholder)
        self._w_preview_placeholder = weakref.proxy(w_preview_placeholder)
        self._w_extra = weakref.proxy(w_extra)

        TreeNavigationMixin.__init__(self, path)
        urwid.WidgetWrap.__init__(self, w)

    def ascend(self, *args, **kwargs):
        from_ = super().ascend(*args, **kwargs)
        # Patch to focus the correct item when ascending
        folder = self._w_folder_placeholder.original_widget
        for i, item in enumerate(folder.body):
            if item.entry.name == from_:
                folder.set_focus(i)
                break

    def create_folder(self, path: str) -> FolderWidget:
        w = FolderWidget(
            [ItemWidget(*args) for args in enumerate(self.scanpath(path))]
        )
        for item in w.body:
            urwid.connect_signal(item, "selected", self._on_item_selected)
        urwid.connect_signal(w, "focus_changed", self._on_folder_focus_changed)
        return w

    def edit_file(self, path: str):
        from . import loop

        # see https://github.com/urwid/urwid/issues/302
        loop.screen.stop()
        subprocess.call(config.editor.format(path=path), shell=True)
        loop.screen.start()

    def keypress(self, size, key):
        key = super().keypress(size, key)
        # XXX: find another place to do this
        if key is None:
            ExtendedCommandMap.input_state.clear()
        return key

    def _on_folder_focus_changed(self, item: ItemWidget):
        if item:
            path = item.entry.path
            if item.entry.is_dir():
                command = config.folder_preview
            else:
                command = config.file_preview
            # TODO: catch errors
            text = subprocess.run(
                command.format(path=path), shell=True, capture_output=True
            ).stdout.decode()

            self._w_extra.set_text(item.meta())
        else:
            text = ""

        w = ANSIWidget(text)
        self._w_preview_placeholder.original_widget = w

    def _on_item_selected(self, item: ItemWidget):
        if item.entry.is_dir():
            self.descend(item.entry.name)
        else:
            self.edit_file(item.entry.path)

    def _on_path_changed(self, new_path: str):
        self._w_path.set_text(("path", new_path))
        folder = self._folders[new_path]
        self._w_folder_placeholder.original_widget = folder
        self._on_folder_focus_changed(folder.get_focused_item())  # Trick
