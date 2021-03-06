import os
import stat
import subprocess
from datetime import datetime
from functools import wraps
from grp import getgrgid
from pwd import getpwuid

import urwid
from humanize import naturalsize
from send2trash import send2trash

from bfm import config
from bfm.fs import TreeNavigationMixin, pretty_name
from bfm.keys import CallableCommandsMixin, ExtendedCommandMap
from bfm.vendor.bisect import insort_left

from .popup import EditPopUp


class ItemWidget(CallableCommandsMixin, urwid.WidgetWrap):
    signals = ["require_refresh", "selected"]
    _command_map = ExtendedCommandMap(
        {
            "l": lambda self: urwid.emit_signal(self, "selected", self),
            "m": lambda self: self.move(),
            "dd": lambda self: self.delete(),
        },
        aliases={"<enter>": "l", "<right>": "l"},
    )

    def _preverify_path(factory=lambda: None):
        # ItemWidget can potentially represent an item that no longer exists
        # (e.g. deleted by an external action in the meantime). This decorator
        # can thus be used to check if `self.path` is still valid. If not, it
        # returns `factory()`.
        # XXX: This is probably not 100% error proof, but I think it is good
        # enough.
        def decorator(f):
            @wraps(f)
            def wrapper(self, *args, **kwargs):
                # XXX: This won't detect broken symlinks on some platforms
                if os.path.lexists(self.path):
                    return f(self, *args, **kwargs)
                else:
                    from bfm import w_root

                    w_root.error(
                        "'{}': No such file or directory".format(self.path)
                    )
                    return factory()

            return wrapper

        return decorator

    def __init__(self, path: str):
        self.path = path
        w = self.generate_widget()
        super().__init__(w)

    # @_preverify_path()
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

    @_preverify_path(factory=str)
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

    def update_widget(self):
        self._w = self.generate_widget()

    @_preverify_path()
    def delete(self):
        # BUG found: send2trash raises an Exception is we try to delete a broken
        # symlink. It seems to correctly delete a valid symlink though.
        send2trash(self.path)
        urwid.emit_signal(self, "require_refresh")

    @_preverify_path()
    def move(self):
        def on_close(success: bool, text: str):
            if not success:
                return
            src = self.path
            dst = text
            try:
                os.renames(src, dst)
            except Exception:
                # TODO: display error
                return
            urwid.emit_signal(self, "require_refresh", dst)

        from bfm import w_root

        w_pop_up = EditPopUp(title="Move to", text=self.path)
        urwid.connect_signal(w_pop_up, "close", on_close)
        w_root.open_pop_up(w_pop_up)


class FolderWidget(CallableCommandsMixin, TreeNavigationMixin, urwid.ListBox):
    signals = ["focus_changed", "path_changed", "refreshed"]
    _command_map = ExtendedCommandMap(
        {
            "h": lambda self: self.ascend(),
            "j": "cursor down",
            "k": "cursor up",
            "gg": "cursor max left",
            "G": "cursor max right",
            "r": lambda self: self.refresh(True),
        },
        aliases={
            "<backspace>": "h",
            "<left>": "h",
            "<down>": "j",
            "<up>": "k",
        },
    )

    @staticmethod
    def sorting_key(w_item: ItemWidget):
        path = w_item.path
        return (not os.path.isdir(path), os.path.basename(path).lower())

    def __init__(self):
        TreeNavigationMixin.__init__(self)
        urwid.ListBox.__init__(self, urwid.SimpleListWalker([]))

        self._focus_cache = {}
        urwid.connect_signal(self, "focus_changed", self._on_focus_changed)

    def ascend(self):
        new_path, from_ = os.path.split(self.path)
        self._focus_cache[new_path] = self.path
        self.change_path(new_path)
        return from_

    def create_item(self, path: str):
        w_item = ItemWidget(path)
        urwid.connect_signal(w_item, "require_refresh", self.refresh)
        urwid.connect_signal(w_item, "selected", self._on_item_selected)
        return w_item

    def open_in_editor(self, path: str):
        from bfm import loop

        # see https://github.com/urwid/urwid/issues/302
        loop.screen.stop()
        subprocess.call(config.editor.format(path=path), shell=True)
        loop.screen.start()
        self.refresh()

    def focus_item_by_path(self, target_path: str):
        if not self.body:
            return
        if target_path:
            for i, w_item in enumerate(self.body):
                if w_item.path == target_path:
                    break
            else:
                # TODO: display error message
                return
        else:
            i = 0
        # XXX: we do not use self.set_focus directly, because it seems to
        # trigger the "modified" signal 3 times instead of once.
        self.body.set_focus(i)

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

    def refresh(self, change_focus: bool = False):
        # NB: change_focus can be:
        # a boolean: if True, it will focus the item based on `_focus_cache`.
        # a path (str): it will focus the item corresponding to that path.
        signal_args = (self.body, "modified", self._on_body_modified)
        urwid.disconnect_signal(*signal_args)

        paths = list(self.scanpath())
        # Remove items that no longer belong here
        for w_item in list(self.body):
            if w_item.path in paths:
                w_item.update_widget()
                paths.remove(w_item.path)
            else:
                self.body.remove(w_item)
        # Add missing items
        for path in paths:
            w_item = self.create_item(path)
            insort_left(self.body, w_item, key=self.sorting_key)

        if change_focus:
            if change_focus is True:
                target_path = self._focus_cache.get(self.path)
            else:
                target_path = change_focus
            self.focus_item_by_path(target_path)

        urwid.connect_signal(*signal_args)

        urwid.emit_signal(self, "refreshed")

    def _on_body_modified(self):
        urwid.emit_signal(self, "focus_changed", self.get_focused_item())

    def _on_focus_changed(self, w_item: ItemWidget):
        self._focus_cache[self.path] = w_item.path

    def _on_item_selected(self, w_item: ItemWidget):
        if os.path.isdir(w_item.path):
            self.change_path(w_item.path)
        else:
            self.open_in_editor(w_item.path)

    def _on_path_changed(self, old_path: str, new_path: str):
        self.refresh(True)

    # https://github.com/urwid/urwid/issues/305
    def _keypress_max_left(self, *args, **kwargs):
        super()._keypress_max_left(*args, **kwargs)

    # https://github.com/urwid/urwid/issues/305
    def _keypress_max_right(self, *args, **kwargs):
        super()._keypress_max_right(*args, **kwargs)
