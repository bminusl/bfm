import urwid
from urwid import ExitMainLoop
from urwid.command_map import CommandMap

# Clear all widgets default command map
urwid.command_map._command.clear()


def unhandled_input(key):
    if key == "q":
        raise ExitMainLoop
    elif key == "esc":
        ExtendedCommandMap.input_state.clear()
    else:
        ExtendedCommandMap.input_state.push(key)


class InputState:
    def __init__(self):
        self._queue = []

    def __str__(self):
        return "".join(self._queue)

    def clear(self):
        self._queue.clear()

    def push(self, key: str):
        # TODO: handle non alphabetical keys differently, e.g. <Tab>, <Space>
        self._queue.append(key)


class ExtendedCommandMap(CommandMap):
    input_state = InputState()

    def __init__(self, command_defaults={}, aliases={}):
        self._command_defaults = command_defaults
        self._aliases = aliases
        super().__init__()

    def __getitem__(self, key):
        keys = str(ExtendedCommandMap.input_state) + key
        keys = self._aliases.get(keys, keys)
        return self._command.get(keys, None)


class CallableCommandsMixin:
    def keypress(self, size, key):
        key = super().keypress(size, key)
        if key:
            command = self._command_map[key]
            if callable(command):
                command(self)
                return
        return key
