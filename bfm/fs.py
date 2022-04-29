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
    def ascend(self):
        new_path, from_ = os.path.split(self.__path)
        self.change_path(new_path)
        return from_

    def change_path(self, new_path: str):
        self.__path = new_path
        self._on_path_changed(self.__path)
        # XXX: the child class needs to manually define this signal
        urwid.emit_signal(self, "path_changed", new_path)

    def descend(self, into: str):
        new_path = os.path.join(self.__path, into)
        self.change_path(new_path)

    def get_path(self):
        return self.__path

    def scanpath(self, path=None):
        with os.scandir(path or self.__path) as it:
            for entry in sorted(it, key=self.__sorting_key):
                yield entry.path

    @staticmethod
    def __sorting_key(entry: os.DirEntry):
        return (not os.path.isdir(entry.path), entry.name.lower())
