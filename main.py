import os
import sys

import urwid


class Item(urwid.WidgetWrap):
    signals = ["selected"]

    @staticmethod
    def _markup(entry: os.DirEntry):
        # TODO: handle symlinks
        if entry.is_dir(follow_symlinks=False):
            attr = "folder"
        elif entry.is_file(follow_symlinks=False):
            attr = "file"
        else:
            attr = "unknown"
        return attr, entry.name

    def __init__(self, entry: os.DirEntry):
        self._entry = entry
        w = urwid.SelectableIcon(self._markup(entry))
        super().__init__(w)

    def keypress(self, size, key):
        if key in ("l", "enter", "right"):
            urwid.emit_signal(self, "selected", self._entry)
            return
        return key


class BFM(urwid.WidgetWrap):
    def __init__(self, path: str):
        self._w_path = header = urwid.Text("")
        body = urwid.ListBox(urwid.SimpleListWalker([]))
        self._w_contents = body.body
        w = urwid.Frame(body, header)
        super().__init__(w)
        self.change_path(path)

    def descend(self, into: str):
        current = self._w_path.text
        new_path = os.path.join(current, into)
        self.change_path(new_path)

    def ascend(self):
        current = self._w_path.text
        new_path = os.path.split(current)[0]
        self.change_path(new_path)

    def change_path(self, new_path: str):
        def sorting_key(entry):
            return (not entry.is_dir(follow_symlinks=False), entry.name.lower())

        def on_item_selected(entry):
            if entry.is_dir(follow_symlinks=False):
                self.descend(entry.name)
            elif entry.is_file(follow_symlinks=False):
                # TODO:
                pass

        self._w_path.set_text(("path", new_path))
        self._w_contents.clear()
        with os.scandir(new_path) as it:
            for entry in sorted(it, key=sorting_key):
                item = Item(entry)
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
