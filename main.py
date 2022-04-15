import os
import sys

import urwid


def scandir(path):
    def sorting_key(entry):
        return (not entry.is_dir(follow_symlinks=False), entry.name.lower())

    def markup(entry):
        # TODO: handle symlinks
        if entry.is_dir(follow_symlinks=False):
            attr = "folder"
        elif entry.is_file(follow_symlinks=False):
            attr = "file"
        else:
            attr = "unknown"
        return attr, entry.name

    with os.scandir(path) as it:
        for entry in sorted(it, key=sorting_key):
            yield urwid.SelectableIcon(markup(entry))


class BFM(urwid.WidgetWrap):
    def __init__(self, path):
        header = urwid.Text(("path", path))
        body_contents = list(scandir(path))
        body = urwid.ListBox(urwid.SimpleListWalker(body_contents))

        w = urwid.Frame(body, header)
        super().__init__(w)


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
