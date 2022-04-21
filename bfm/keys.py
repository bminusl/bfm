import urwid
from urwid import ExitMainLoop
from urwid.command_map import CommandMap

# Clear all widgets default command map
urwid.command_map._command.clear()


def unhandled_input(key):
    if key == "q":
        raise ExitMainLoop
    elif key == "esc":
        input_state.clear()
    else:
        input_state.push(key)
        if not any(
            keys.startswith(str(input_state))
            for keys in ExtendedCommandMap.all_command_keys
        ):
            input_state.clear()


class InputState:
    def __init__(self):
        self._queue = []
        self._alarm_handle = None

    def __str__(self):
        return "".join(self._queue)

    def clear(self):
        self._queue.clear()

    def push(self, key: str):
        from . import loop

        loop.remove_alarm(self._alarm_handle)
        # TODO: handle non alphabetical keys differently, e.g. <Tab>, <Space>
        self._queue.append(key)
        self._alarm_handle = loop.set_alarm_in(1, lambda *_: self.clear())


input_state = InputState()


class ExtendedCommandMap(CommandMap):
    all_command_keys = []

    def __init__(self, command_defaults={}, aliases={}):
        self._command_defaults = command_defaults
        self._aliases = aliases
        ExtendedCommandMap.all_command_keys.extend(command_defaults.keys())
        ExtendedCommandMap.all_command_keys.extend(aliases.keys())
        super().__init__()

    def __getitem__(self, key):
        keys = str(input_state) + key
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
