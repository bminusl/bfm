import os
import sys
import weakref
from subprocess import call

import urwid


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


class TreeNavigationMixin:
    def __init__(self, path: str):
        self.__path = path
        self._on_path_changed(self.__path)

    def descend(self, into: str):
        self.__path = os.path.join(self.__path, into)
        self._on_path_changed(self.__path)

    def ascend(self):
        self.__path, from_ = os.path.split(self.__path)
        self._on_path_changed(self.__path)
        return from_

    @staticmethod
    def __sorting_key(entry: os.DirEntry):
        return (not entry.is_dir(follow_symlinks=False), entry.name.lower())

    def scan(self):
        with os.scandir(self.__path) as it:
            for entry in sorted(it, key=self.__sorting_key):
                yield entry


class BFM(TreeNavigationMixin, urwid.WidgetWrap):
    def __init__(self, path: str):
        w_path = urwid.Text("")
        w_command = urwid.Text("")
        w_header = urwid.Pile([w_path, w_command])
        w_body = urwid.ListBox(urwid.SimpleListWalker([]))
        w = urwid.Frame(w_body, w_header)

        self._w_path = weakref.proxy(w_path)
        self._w_command = weakref.proxy(w_command)
        self._w_body = weakref.proxy(w_body)
        self._w_body_contents = weakref.proxy(w_body.body)

        # Keep focus positions when navigating the tree
        self.focus_cache = {}

        TreeNavigationMixin.__init__(self, path)
        urwid.WidgetWrap.__init__(self, w)

    def descend(self, *args, **kwargs):
        self.focus_cache[
            self._TreeNavigationMixin__path
        ] = self._w_body.focus_position
        super().descend(*args, **kwargs)
        # BBB: py3.8+ walrus operator
        position = self.focus_cache.get(self._TreeNavigationMixin__path)
        if position:
            self._w_body.set_focus(position)

    def ascend(self, *args, **kwargs):
        if self._w_body_contents:
            self.focus_cache[
                self._TreeNavigationMixin__path
            ] = self._w_body.focus_position
        from_ = super().ascend(*args, **kwargs)
        position = next(
            i
            for i, item in enumerate(self._w_body_contents)
            if item.entry.name == from_
        )
        self._w_body.set_focus(position)

    def _on_path_changed(self, new_path: str):
        def on_item_selected(item: Item):
            if item.entry.is_dir(follow_symlinks=False):
                self.descend(item.entry.name)
            else:
                self.edit_file(item.entry.path)

        self._w_path.set_text(("path", new_path))
        self._w_body_contents.clear()

        for entry in self.scan():
            item = Item(entry)
            self._w_body_contents.append(item)
            urwid.connect_signal(item, "selected", on_item_selected)

    def edit_file(self, path):
        # see https://github.com/urwid/urwid/issues/302
        loop.screen.stop()
        call(["vim", path])
        loop.screen.start()

    def keypress(self, size, key):
        key_to_propagate = key
        if key in ("h", "backspace", "left"):
            self.ascend()
            return
        elif key in ("j", "down"):
            key_to_propagate = "down"
        elif key in ("k", "up"):
            key_to_propagate = "up"
        return super().keypress(size, key_to_propagate)


def main():
    def exit_on_q(key):
        if key == "q":
            raise urwid.ExitMainLoop

    palette = [
        ("path", "light cyan", "", "bold"),
        ("folder", "light cyan", ""),
        ("file", "", ""),
        ("unknown", "", "light magenta"),
    ]
    try:
        path = os.path.abspath(os.path.expanduser(sys.argv[1]))
    except IndexError:
        path = os.getcwd()
    global loop
    loop = urwid.MainLoop(BFM(path), palette, unhandled_input=exit_on_q)
    loop.run()


if __name__ == "__main__":
    main()
