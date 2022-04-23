import os
import signal
import stat
import subprocess
import weakref
from datetime import datetime
from functools import partial
from grp import getgrgid
from pwd import getpwuid

import urwid
from humanize import naturalsize
from urwid import ExitMainLoop

from bfm.keys import ExtendedCommandMap
from bfm.vendor.ansi_widget import ANSIWidget

from . import config
from .fs import TreeNavigationMixin
from .keys import CallableCommandsMixin, ClearInputStateMixin


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
        from . import loop

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

    def _on_body_modified(self):
        urwid.emit_signal(self, "focus_changed", self.get_focused_item())

    def _on_item_selected(self, item: ItemWidget):
        if item.entry.is_dir(follow_symlinks=False):
            self.descend(item.entry.name)
        else:
            self.edit_file(item.entry.path)

    def _on_path_changed(self, new_path: str):
        signal_args = (self.body, "modified", self._on_body_modified)
        urwid.disconnect_signal(*signal_args)

        self.body.clear()
        for entry in self.scanpath(new_path):
            w_item = ItemWidget(entry)
            self.body.append(w_item)
            urwid.connect_signal(w_item, "selected", self._on_item_selected)

        urwid.connect_signal(*signal_args)
        if self.body:
            self.set_focus(0)  # Trick to send signal

    # https://github.com/urwid/urwid/issues/305
    def _keypress_max_left(self, *args, **kwargs):
        super()._keypress_max_left(*args, **kwargs)

    # https://github.com/urwid/urwid/issues/305
    def _keypress_max_right(self, *args, **kwargs):
        super()._keypress_max_right(*args, **kwargs)


class FocusableFrameWidget(urwid.Pile):
    def __init__(self, header, body, footer):
        super().__init__([("pack", header), body, ("pack", footer)])
        self.focus_header = partial(self.set_focus, 0)
        self.focus_body = partial(self.set_focus, 1)
        self.focus_footer = partial(self.set_focus, 2)
        self.focus_body()


class CommandWidget(urwid.Edit):
    signals = ["validated"]

    def keypress(self, size, key):
        if key == "enter":
            edit_text = self.get_edit_text()
            self.set_caption("")
            self.set_edit_text("")
            urwid.emit_signal(self, "validated", edit_text)
        else:
            # Mark every key as handled, i.e. always return None.
            # This way, it is not propagated to other widgets.
            super().keypress(size, key)

    def reset(self):
        self.set_caption(":")
        self.set_edit_text("")


class BFMWidget(
    ClearInputStateMixin,
    CallableCommandsMixin,
    urwid.WidgetWrap,
):
    _command_map = ExtendedCommandMap(
        {
            ":": lambda self: self._on_command_edit(),
        },
    )

    def __init__(self, path: str):
        w_path = urwid.Text("")
        w_command = CommandWidget()
        w_header = urwid.Pile([w_path, w_command])

        w_folder = FolderWidget()
        w_preview = ANSIWidget()
        w_body = urwid.Columns([w_folder, w_preview], dividechars=1)

        w_extra = urwid.Text("")

        w_frame = FocusableFrameWidget(w_header, w_body, w_extra)
        w = urwid.Padding(w_frame, left=1, right=1)

        # XXX: are weakrefs necessary?
        self._w_path = weakref.proxy(w_path)
        self._w_command = weakref.proxy(w_command)
        self._w_folder = weakref.proxy(w_folder)
        self._w_preview = weakref.proxy(w_preview)
        self._w_extra = weakref.proxy(w_extra)
        self._w_frame = weakref.proxy(w_frame)

        from . import loop

        self._preview_pipe_fd = loop.watch_pipe(self._add_to_preview)

        # fmt: off
        urwid.connect_signal(w_command, "validated", self._on_command_validated)
        urwid.connect_signal(w_folder, "focus_changed", self._on_folder_focus_changed)  # noqa: E501
        urwid.connect_signal(w_folder, "path_changed", self._on_folder_path_changed)  # noqa: E501
        # fmt: on

        urwid.WidgetWrap.__init__(self, w)

        w_folder.change_path(path)

    def _add_to_preview(self, data):
        self._w_preview.append(data)

    def _on_command_edit(self):
        self._w_frame.focus_header()
        self._w_command.reset()

    def _on_command_validated(self, text):
        self._w_frame.focus_body()

        if text == "q":
            raise ExitMainLoop

        if text.startswith("!"):
            subprocess.call(text[1:], shell=True, cwd=self._w_folder.get_path())

    def _on_folder_focus_changed(self, item: ItemWidget):
        self._w_preview.clear()

        if hasattr(self, "_preview_proc"):
            # [0]: Since `shell=True` is used in `subprocess.Popen(...)`, a
            # simple call to `self._preview_proc.kill()` cannot be used. The
            # process' children would not be killed and could still write to
            # stdout.
            # https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
            os.killpg(os.getpgid(self._preview_proc.pid), signal.SIGTERM)
            del self._preview_proc

        if item:
            extra = item.metadata()

            if item.entry.is_dir(follow_symlinks=False):
                command = config.folder_preview
            else:
                command = config.file_preview
            self._preview_proc = subprocess.Popen(
                command.format(path=item.entry.path),
                shell=True,
                stdout=self._preview_pipe_fd,
                stderr=subprocess.STDOUT,
                close_fds=True,
                preexec_fn=os.setsid,  # see [0]
            )
        else:
            extra = ""

        self._w_extra.set_text(extra)

    def _on_folder_path_changed(self, new_path: str):
        self._w_path.set_text(("path", new_path))
        self._w_preview.clear()
