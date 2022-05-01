import os

import urwid


def pretty_name(path: str, basename: bool = True):
    output = os.path.basename(path) if basename else path
    if os.path.isdir(path):
        output += "/"
    elif os.access(path, os.X_OK):
        # Mark executable files
        output += "*"
    return output


class TreeNavigationMixin:
    def __init__(self):
        self.path = None
        urwid.connect_signal(self, "path_changed", self._on_path_changed)

    def ascend(self):
        new_path, from_ = os.path.split(self.path)
        self.change_path(new_path)
        return from_

    def change_path(self, new_path: str):
        old_path = self.path
        self.path = new_path
        # XXX: the child class needs to manually define this signal
        urwid.emit_signal(self, "path_changed", old_path, new_path)

    def descend(self, into: str):
        new_path = os.path.join(self.path, into)
        self.change_path(new_path)

    def scanpath(self, path=None):
        with os.scandir(path or self.path) as it:
            for entry in sorted(it, key=self.__sorting_key):
                yield entry.path

    @staticmethod
    def __sorting_key(entry: os.DirEntry):
        return (not os.path.isdir(entry.path), entry.name.lower())
