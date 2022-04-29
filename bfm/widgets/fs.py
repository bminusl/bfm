import os
import stat
import subprocess
from datetime import datetime
from grp import getgrgid
from pwd import getpwuid

import urwid
from humanize import naturalsize

from bfm import config
from bfm.fs import TreeNavigationMixin, pretty_name
from bfm.keys import CallableCommandsMixin, ExtendedCommandMap


class ItemWidget(CallableCommandsMixin, urwid.WidgetWrap):
    signals = ["popup", "selected"]
    _command_map = ExtendedCommandMap(
        {
            "l": lambda self: urwid.emit_signal(self, "selected", self),
            "m": lambda self: self.move(),
        },
        aliases={"<enter>": "l", "<right>": "l"},
    )

    def __init__(self, path: str):
        self.path = path
        w = self.generate_widget()
        super().__init__(w)

    def generate_widget(self) -> urwid.Widget:
        metadata = naturalsize(
            os.stat(self.path, follow_symlinks=False).st_size, gnu=True
        )
        if os.path.islink(self.path):
            attr = "symlink"
            metadata = "-> {} {}".format(
                pretty_name(os.readlink(self.path), basename=False), metadata
            )
        elif os.path.isdir(self.path):
            attr = "folder"
        else:
            attr = "file"

        w_name = urwid.Text(pretty_name(self.path))
        w_metadata = urwid.Text(metadata)
        w = urwid.Columns([w_name, ("pack", w_metadata)])
        w._selectable = True  # XXX: which widget should be selectable?
        w = urwid.Padding(w, left=1, right=1)
        w = urwid.AttrMap(w, attr, focus_map="focus")
        return w

    def extra_metadata(self) -> str:
        stats = os.stat(self.path, follow_symlinks=False)
        mode = stat.filemode(stats.st_mode)
        nlink = stats.st_nlink
        user = getpwuid(stats.st_uid).pw_name
        group = getgrgid(stats.st_gid).gr_name
        mtime = datetime.utcfromtimestamp(stats.st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return " ".join(map(str, [mode, nlink, user, group, mtime]))

    def move(self):
        title = "Move to"
        text = os.path.basename(self.path)
        callback = self._on_move_validated
        urwid.emit_signal(self, "popup", title, text, callback)

    def _on_move_validated(self, new_name: str):
        src = self.path
        dirname = os.path.dirname(src)
        dst = os.path.join(dirname, new_name)
        try:
            os.rename(src, dst)
        except Exception:
            # TODO:
            return

        self.path = dst
        self._w = self.generate_widget()  # XXX: is it ok to modify `self._w`?


class FolderWidget(CallableCommandsMixin, TreeNavigationMixin, urwid.ListBox):
    signals = ["focus_changed", "item_created", "path_changed"]
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
        for path in self.scanpath():
            w_item = ItemWidget(path)
            self.body.append(w_item)
            urwid.connect_signal(w_item, "selected", self._on_item_selected)
            urwid.emit_signal(self, "item_created", w_item)

        urwid.connect_signal(*signal_args)
        if self.body:
            self.set_focus(0)  # Trick to send signal

    def _on_body_modified(self):
        urwid.emit_signal(self, "focus_changed", self.get_focused_item())

    def _on_item_selected(self, w_item: ItemWidget):
        if os.path.isdir(w_item.path):
            self.descend(os.path.basename(w_item.path))
        else:
            self.edit_file(w_item.path)

    def _on_path_changed(self, new_path: str):
        self.refresh()

    # https://github.com/urwid/urwid/issues/305
    def _keypress_max_left(self, *args, **kwargs):
        super()._keypress_max_left(*args, **kwargs)

    # https://github.com/urwid/urwid/issues/305
    def _keypress_max_right(self, *args, **kwargs):
        super()._keypress_max_right(*args, **kwargs)
