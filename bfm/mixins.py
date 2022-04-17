import os


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