import os
import signal
import subprocess
import weakref

import urwid
from urwid import ExitMainLoop

from bfm import config
from bfm.keys import CallableCommandsMixin, ExtendedCommandMap
from bfm.vendor.ansi_widget import ANSIWidget

from .fs import FolderWidget, ItemWidget
from .layout import FocusableFrameWidget, LastRenderedSizeMixin
from .misc import MyEdit


class RootWidget(
    CallableCommandsMixin,
    LastRenderedSizeMixin,
    urwid.PopUpLauncher,
):
    _command_map = ExtendedCommandMap(
        {
            ":": lambda self: self._on_command_edit(),
        },
    )

    def open_pop_up(self, w_pop_up: urwid.Widget):
        self._pop_up_widget = w_pop_up
        urwid.connect_signal(
            w_pop_up, "close", lambda *args, **kwargs: self.close_pop_up()
        )
        self._invalidate()

    def get_pop_up_parameters(self):
        W, H = self._LastRenderedSizeMixin__size
        w, h = 42, 3
        x, y = W // 2 - w // 2, H // 2 - h // 2
        return {"left": x, "top": y, "overlay_width": w, "overlay_height": h}

    def __init__(self, path: str):
        w_path = urwid.Text("")

        w_folder = FolderWidget()
        w_preview = ANSIWidget()
        w_body = urwid.Columns([w_folder, w_preview], dividechars=1)

        w_extra = urwid.Text("")
        w_command = MyEdit()
        w_footer = urwid.Pile([w_extra, w_command])

        w_frame = FocusableFrameWidget(w_path, w_body, w_footer)

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
        urwid.connect_signal(w_command, "aborted", self._on_command_aborted)
        urwid.connect_signal(w_command, "validated", self._on_command_validated)
        urwid.connect_signal(w_folder, "focus_changed", self._on_folder_focus_changed)  # noqa: E501
        urwid.connect_signal(w_folder, "path_changed", self._on_folder_path_changed)  # noqa: E501
        # fmt: on

        urwid.PopUpLauncher.__init__(self, w_frame)

        w_folder.change_path(path)

    def error(self, message: str):
        self._w_command.set_caption(("error", message))

    def keypress(self, size, key):
        key = super().keypress(size, key)
        # XXX: I am not a fan of putting this logic here.
        # If the following condition is True, this means that the key was
        # handled in a way or another, and the input_state queue can thus be
        # cleared.
        if key is None:
            from bfm.keys import input_state

            input_state.clear()
        return key

    def _on_command_edit(self):
        self._w_frame.focus_footer()
        self._w_command.set_caption(":")

    def _on_command_aborted(self, text: str):
        self._w_frame.focus_body()

    def _on_command_validated(self, text: str):
        self._w_frame.focus_body()

        if text == "q":
            raise ExitMainLoop

        try:
            lineno = int(text)
        except Exception:
            pass
        else:
            # XXX: we do not use self._w_folder.set_focus directly, because it
            # seems to trigger the "modified" signal 3 times instead of once.
            self._w_folder.body.set_focus(lineno)
            return

        if text.startswith("!"):
            subprocess.call(text[1:], shell=True, cwd=self._w_folder.path)
            # TODO: conditionally refresh
            self._w_folder.refresh()
            return

        self.error("Not an editor command: {}".format(text))

    def _on_folder_focus_changed(self, w_item: ItemWidget):
        self._w_preview.clear()

        if hasattr(self, "_preview_proc"):
            # [0]: Since `shell=True` is used in `subprocess.Popen(...)`, a
            # simple call to `self._preview_proc.kill()` cannot be used. The
            # process' children would not be killed and could still write to
            # stdout.
            # https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
            os.killpg(os.getpgid(self._preview_proc.pid), signal.SIGTERM)
            del self._preview_proc

        assert w_item is not None, w_item
        extra = w_item.extra_metadata()
        self._w_extra.set_text(extra)

        if os.path.isdir(w_item.path):
            command = config.folder_preview
        else:
            command = config.file_preview
        self._preview_proc = subprocess.Popen(
            command.format(path=w_item.path),
            shell=True,
            stdout=self._preview_pipe_fd,
            stderr=subprocess.STDOUT,
            close_fds=True,
            preexec_fn=os.setsid,  # see [0]
        )

    def _on_folder_path_changed(self, old_path: str, new_path: str):
        self._w_path.set_text(("path", new_path))
        self._w_preview.clear()
        self._w_extra.set_text("")
