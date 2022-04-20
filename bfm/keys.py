from urwid import ExitMainLoop
from urwid.command_map import CommandMap


def unhandled_input(key):
    if key == "q":
        raise ExitMainLoop


class ExtendedCommandMap(CommandMap):
    def __init__(self, command_defaults={}, aliases={}):
        self._command_defaults = command_defaults
        self._aliases = aliases
        super().__init__()

    def __getitem__(self, key):
        key = self._aliases.get(key, key)
        command = self._command.get(key, None)
        return command


class CallableCommandsMixin:
    def keypress(self, size, key):
        key = super().keypress(size, key)
        if key:
            command = self._command_map[key]
            if callable(command):
                command(self)
                return
        return key
