import os
import sys

import urwid


class Item(urwid.WidgetWrap):
    signals = ["selected"]

    @staticmethod
    def _markup(name: str, is_dir: bool):
        # TODO: handle symlinks
        if is_dir:
            attr = "folder"
        else:
            attr = "file"
        # attr = "unknown"
        return attr, name

    def __init__(self, name: str, is_dir: bool):
        self.name = name
        self.is_dir = is_dir
        w = urwid.SelectableIcon(self._markup(name, is_dir))
        super().__init__(w)

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
        self.__path = os.path.split(self.__path)[0]
        self._on_path_changed(self.__path)

    @staticmethod
    def __sorting_key(entry):
        return (not entry.is_dir(follow_symlinks=False), entry.name.lower())

    def scan(self):
        with os.scandir(self.__path) as it:
            for entry in sorted(it, key=self.__sorting_key):
                yield entry.name, entry.is_dir(follow_symlinks=False)


class BFM(TreeNavigationMixin, urwid.WidgetWrap):
    def __init__(self, path: str):
        self._w_path = header = urwid.Text("")
        body = urwid.ListBox(urwid.SimpleListWalker([]))
        self._w_contents = body.body
        w = urwid.Frame(body, header)

        TreeNavigationMixin.__init__(self, path)
        urwid.WidgetWrap.__init__(self, w)

    def _on_path_changed(self, new_path: str):
        def on_item_selected(item: Item):
            if item.is_dir:
                self.descend(item.name)

        self._w_path.set_text(("path", new_path))
        self._w_contents.clear()

        for args in self.scan():
            item = Item(*args)
            self._w_contents.append(item)
            urwid.connect_signal(item, "selected", on_item_selected)

    def keypress(self, size, key):
        key_to_propagate = key
        if key in ("h", "delete", "left"):
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
    loop = urwid.MainLoop(BFM(path), palette, unhandled_input=exit_on_q)
    loop.run()


if __name__ == "__main__":
    main()
