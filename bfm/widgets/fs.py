import os
import stat
import subprocess
from datetime import datetime
from grp import getgrgid
from pwd import getpwuid

import urwid
from humanize import naturalsize

from bfm import config
from bfm.fs import TreeNavigationMixin
from bfm.keys import CallableCommandsMixin, ExtendedCommandMap


class ItemWidget(CallableCommandsMixin, urwid.WidgetWrap):
    signals = ["selected"]
    _command_map = ExtendedCommandMap(
        {
            "l": lambda self: urwid.emit_signal(self, "selected", self),
        },
        aliases={"<enter>": "l", "<right>": "l"},
    )

    def __init__(self, entry: os.DirEntry):
        self.entry = entry

        text = entry.name
        meta = naturalsize(entry.stat(follow_symlinks=False).st_size, gnu=True)
        if self.entry.is_symlink():
            attr = "symlink"
            meta = "-> {destination} {base}".format(
                destination=os.readlink(entry.path), base=meta
            )
        elif self.entry.is_dir(follow_symlinks=False):
            attr = "folder"
            text += "/"
        else:
            attr = "file"
            if os.access(entry.path, os.X_OK):
                text += "*"

        w_name = urwid.Text(text)
        w_stats = urwid.Text(meta)
        w = urwid.Columns([w_name, ("pack", w_stats)])
        w._selectable = True  # XXX: which widget should be selectable?
        w = urwid.Padding(w, left=1, right=1)
        w = urwid.AttrMap(w, attr, focus_map="focus")
        super().__init__(w)

    def metadata(self) -> str:
        stats = self.entry.stat(follow_symlinks=False)
        mode = stat.filemode(stats.st_mode)
        nlink = stats.st_nlink
        user = getpwuid(stats.st_uid).pw_name
        group = getgrgid(stats.st_gid).gr_name
        mtime = datetime.utcfromtimestamp(stats.st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return " ".join(map(str, [mode, nlink, user, group, mtime]))


class FolderWidget(CallableCommandsMixin, TreeNavigationMixin, urwid.ListBox):
    signals = ["focus_changed", "path_changed"]
    _command_map = ExtendedCommandMap(
        {
            "h": lambda self: self.ascend(),
            "j": "cursor down",
            "k": "cursor up",
            "gg": "cursor max left",
            "G": "cursor max right",
            "r": lambda self: self.refresh(),
        },
        aliases={
            "<backspace>": "h",
            "<left>": "h",
            "<down>": "j",
            "<up>": "k",
        },
    )

    def __init__(self):
        urwid.ListBox.__init__(self, urwid.SimpleListWalker([]))

    def edit_file(self, path: str):
        from bfm import loop

        # see https://github.com/urwid/urwid/issues/302
        loop.screen.stop()
        subprocess.call(config.editor.format(path=path), shell=True)
        loop.screen.start()

    def get_focused_item(self) -> ItemWidget:
        return self.get_focus()[0] if self.body else None

    def keypress(self, size, key):
        key = super().keypress(size, key)

        # When pressing `j` at the bottom most item, or `k` a the top most one,
        # the default behaviour is to mark them as unhandled. We modify this
        # behaviour and always mark "j" and "k" as handled.
        if key in ["j", "k"]:
            return

        return key

    def refresh(self):
        signal_args = (self.body, "modified", self._on_body_modified)
        urwid.disconnect_signal(*signal_args)

        self.body.clear()
        for entry in self.scanpath():
            w_item = ItemWidget(entry)
            self.body.append(w_item)
            urwid.connect_signal(w_item, "selected", self._on_item_selected)

        urwid.connect_signal(*signal_args)
        if self.body:
            self.set_focus(0)  # Trick to send signal

    def _on_body_modified(self):
        urwid.emit_signal(self, "focus_changed", self.get_focused_item())

    def _on_item_selected(self, item: ItemWidget):
        if item.entry.is_dir(follow_symlinks=False):
            self.descend(item.entry.name)
        else:
            self.edit_file(item.entry.path)

    def _on_path_changed(self, new_path: str):
        self.refresh()

    # https://github.com/urwid/urwid/issues/305
    def _keypress_max_left(self, *args, **kwargs):
        super()._keypress_max_left(*args, **kwargs)

    # https://github.com/urwid/urwid/issues/305
    def _keypress_max_right(self, *args, **kwargs):
        super()._keypress_max_right(*args, **kwargs)
