import os
import signal
import subprocess
import weakref

import urwid
from urwid import ExitMainLoop

from bfm import config
from bfm.keys import (
    CallableCommandsMixin,
    ClearInputStateMixin,
    ExtendedCommandMap,
)
from bfm.vendor.ansi_widget import ANSIWidget

from .fs import FolderWidget, ItemWidget
from .layout import FocusableFrameWidget, LastRenderedSizeMixin


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
    LastRenderedSizeMixin,
    urwid.PopUpLauncher,
):
    _command_map = ExtendedCommandMap(
        {
            ":": lambda self: self._on_command_edit(),
            "o": lambda self: self.open_pop_up(),
        },
    )

    def create_pop_up(self):
        w = urwid.Text("test")
        w = urwid.Filler(w)
        w = urwid.LineBox(w, title="foo", title_align="left")
        return w

    def get_pop_up_parameters(self):
        w, h = self._LastRenderedSizeMixin__size
        return {
            "left": w // 4,
            "top": h // 4,
            "overlay_width": w // 2,
            "overlay_height": h // 2,
        }

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

        from bfm import loop

        self._preview_pipe_fd = loop.watch_pipe(self._w_preview.append)

        # fmt: off
        urwid.connect_signal(w_command, "validated", self._on_command_validated)
        urwid.connect_signal(w_folder, "focus_changed", self._on_folder_focus_changed)  # noqa: E501
        urwid.connect_signal(w_folder, "path_changed", self._on_folder_path_changed)  # noqa: E501
        # fmt: on

        urwid.PopUpLauncher.__init__(self, w)

        w_folder.change_path(path)

    def _on_command_edit(self):
        self._w_frame.focus_header()
        self._w_command.reset()

    def _on_command_validated(self, text):
        self._w_frame.focus_body()

        if text == "q":
            raise ExitMainLoop

        try:
            lineno = int(text)
            self._w_folder.set_focus(lineno)
            return
        except Exception:
            pass

        if text.startswith("!"):
            subprocess.call(text[1:], shell=True, cwd=self._w_folder.get_path())

        self._w_folder.refresh()

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