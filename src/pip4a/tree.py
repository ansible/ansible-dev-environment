"""An ascii tree generator."""
from __future__ import annotations

import os

from typing import Union


class Ansi:
    """ANSI escape codes."""

    BLUE = "\x1B[34m"
    BOLD = "\x1B[1m"
    CYAN = "\x1B[36m"
    GREEN = "\x1B[32m"
    ITALIC = "\x1B[3m"
    MAGENTA = "\x1B[35m"
    RED = "\x1B[31m"
    RESET = "\x1B[0m"
    REVERSED = "\x1B[7m"
    UNDERLINE = "\x1B[4m"
    WHITE = "\x1B[37m"
    YELLOW = "\x1B[33m"


ScalarVal = Union[bool, str, float, int, None]
JSONVal = Union[ScalarVal, list["JSONVal"], dict[str, "JSONVal"]]


class Tree:  # pylint: disable=R0902
    """Renderer for the tree."""

    PIPE = "│"
    ELBOW = "└──"
    TEE = "├──"
    PIPE_PREFIX = "│  "
    SPACE_PREFIX = "   "

    def __init__(
        self: Tree,
        obj: JSONVal,
    ) -> None:
        """Initialize the renderer."""
        self.obj = obj
        self._lines: list[str] = []
        self.blue: list[ScalarVal] = []
        self.bold: list[ScalarVal] = []
        self.cyan: list[ScalarVal] = []
        self.green: list[ScalarVal] = []
        self.italic: list[ScalarVal] = []
        self.magenta: list[ScalarVal] = []
        self.red: list[ScalarVal] = []
        self.reversed: list[ScalarVal] = []
        self.underline: list[ScalarVal] = []
        self.white: list[ScalarVal] = []
        self.yellow: list[ScalarVal] = []

    def in_color(self: Tree, val: ScalarVal) -> str:
        """Colorize the string.

        Args:
            val: The thing to colorize

        Returns:
            The colorized string
        """
        if os.environ.get("NO_COLOR"):
            return str(val)
        ansis = (
            "blue",
            "bold",
            "cyan",
            "green",
            "italic",
            "magenta",
            "red",
            "reversed",
            "underline",
            "white",
            "yellow",
        )
        start = ""
        if val == "four":
            pass
        for ansi in ansis:
            matches = getattr(self, ansi)
            try:
                index = matches.index(val)
            except ValueError:
                continue

            if isinstance(val, type(matches[index])):
                start += getattr(Ansi, ansi.upper())

        return f"{start}{val}{Ansi.RESET}"

    @staticmethod
    def is_scalar(obj: JSONVal) -> bool:
        """Check if the object is a scalar."""
        return isinstance(obj, (str, int, float, bool)) or obj is None

    def _print_tree(  # noqa: C901
        self: Tree,
        obj: JSONVal,
        prefix: str = "",
        is_last: bool = True,  # noqa: FBT001, FBT002
        was_list: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        if isinstance(obj, dict):
            if len(obj) > 1:
                for key, value in list(obj.items())[:-1]:
                    _key = f"{Ansi.ITALIC}{key}{Ansi.RESET}" if was_list else key
                    self.append(f"{prefix}{self.TEE}{self.in_color(_key)}")
                    self._print_tree(
                        obj=value,
                        prefix=prefix + self.PIPE_PREFIX,
                        is_last=not isinstance(value, (dict, list)),
                    )
            key, value = list(obj.items())[-1]
            if was_list:
                key = f"{Ansi.ITALIC}{key}{Ansi.RESET}"
            self.append(f"{prefix}{self.ELBOW}{self.in_color(key)}")
            self._print_tree(
                obj=value,
                prefix=prefix + self.SPACE_PREFIX,
                is_last=True,
            )
        elif isinstance(obj, list):
            if any(isinstance(item, (dict, list)) for item in obj) and len(obj) > 1:
                repl_obj = {str(i): item for i, item in enumerate(obj)}
                self._print_tree(
                    obj=repl_obj,
                    prefix=prefix,
                    is_last=is_last,
                    was_list=True,
                )
            elif isinstance(obj[0], (dict, list)):
                self._print_tree(obj=obj[0], prefix=prefix, is_last=True)
            elif isinstance(obj[0], (str, int, float, bool)):
                for i, item in enumerate(obj):
                    is_last = i == len(obj) - 1
                    _item = str(item)
                    self.append(
                        f"{prefix}{self.ELBOW if is_last else self.TEE}{self.in_color(_item)}",
                    )
            else:
                err = f"Invalid type in list {type(obj[0])}"
                raise TypeError(err)

        elif self.is_scalar(obj):
            self.append(
                f"{prefix}{self.ELBOW if is_last else self.TEE}{self.in_color(obj)}",
            )
        else:
            err = f"Invalid type {type(obj)}"
            raise TypeError(err)

    def append(self: Tree, string: str) -> None:
        """Append a line to the output."""
        self._lines.append(string)

    def render(self: Tree) -> str:
        """Render the root of the tree."""
        if not isinstance(self.obj, dict):
            msg = "The root of the tree must be a dict"
            raise TypeError(msg)
        for k, v in list(self.obj.items())[:-1]:
            if isinstance(v, (dict, list)):
                self.append(self.in_color(k))
                self._print_tree(v, is_last=not isinstance(v, (dict, list)))
            else:
                self.append(self.in_color(k))
                self.append(f"{self.ELBOW}{self.in_color(v)}")
        k, v = list(self.obj.items())[-1]
        if isinstance(v, (dict, list)):
            self.append(self.in_color(k))
            self._print_tree(v, is_last=not isinstance(v, (dict, list)))
        else:
            self.append(self.in_color(k))
            self.append(f"{self.ELBOW}{self.in_color(v)}")
        return "\n".join(self._lines) + "\n"
