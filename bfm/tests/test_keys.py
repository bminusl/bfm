import unittest
from string import ascii_letters

from bfm.keys import escape


class TestEscape(unittest.TestCase):
    def test_ascii_letters(self):
        for char in ascii_letters:
            self.assertEqual(escape(char), char)

    def test_chevrons(self):
        self.assertEqual(escape("<"), r"\<")
        self.assertEqual(escape(">"), r"\>")

    def test_special(self):
        # Non exhaustive list
        escapes = {
            "backspace": "<backspace>",
            "down": "<down>",
            "enter": "<enter>",
            "left": "<left>",
            "right": "<right>",
            "up": "<up>",
        }
        for k, v in escapes.items():
            self.assertEqual(escape(k), v)
