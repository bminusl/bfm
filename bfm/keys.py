import urwid
from urwid import ExitMainLoop
from urwid.command_map import CommandMap

# Clear all widgets default command map
urwid.command_map._command.clear()


def unhandled_input(key):
    if key == "q":
        raise ExitMainLoop
    elif key == "esc":
        ExtendedCommandMap.keyqueue = ""
    else:
        # TODO: handle non alphabetical keys differently, e.g. <Tab>, <Space>
        ExtendedCommandMap.keyqueue += key


class ExtendedCommandMap(CommandMap):
    # Cache unhandled keys to handle multiple-keys bindings
    keyqueue = ""

    def __init__(self, command_defaults={}, aliases={}):
        self._command_defaults = command_defaults
        self._aliases = aliases
        super().__init__()

    def __getitem__(self, key):
        key = ExtendedCommandMap.keyqueue + key
        key = self._aliases.get(key, key)
        return self._command.get(key, None)


class CallableCommandsMixin:
    def keypress(self, size, key):
        key = super().keypress(size, key)
        if key:
            command = self._command_map[key]
            if callable(command):
                command(self)
                return
        return key
