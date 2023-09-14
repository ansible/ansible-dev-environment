"""An ascii tree generator."""
from __future__ import annotations

from typing import Union

from .utils import Ansi, TermFeatures, term_link


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
        term_features: TermFeatures,
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
        self.links: dict[str, str] = {}
        self.term_features = term_features

    def in_color(self: Tree, val: ScalarVal) -> str:
        """Colorize the string.

        Args:
            val: The thing to colorize

        Returns:
            The colorized string
        """
        if not self.term_features.color:
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
        val_str = str(val)
        for ansi in ansis:
            matches = getattr(self, ansi)
            if val_str in [str(match) for match in matches]:
                start += getattr(Ansi, ansi.upper())
        if val_str in self.links:
            val_str = term_link(
                uri=self.links[val_str],
                term_features=self.term_features,
                label=val_str,
            )

        if start:
            return f"{start}{val_str}{Ansi.RESET}"

        return val_str

    @staticmethod
    def is_scalar(obj: JSONVal) -> bool:
        """Check if the object is a scalar."""
        return isinstance(obj, (str, int, float, bool)) or obj is None

    def _print_tree(  # noqa: C901, PLR0913, PLR0912
        self: Tree,
        obj: JSONVal,
        is_last: bool,  # noqa: FBT001
        is_root: bool,  # noqa: FBT001
        was_list: bool,  # noqa: FBT001
        prefix: str = "",
    ) -> None:
        """Print the tree.

        Args:
            obj: The object to print
            is_last: Whether the object is the last in the list | dict
            is_root: Whether the object is the root of the tree
            was_list: Whether the object was a list
            prefix: The prefix to use

        Raises:
            TypeError: If the object is not a dict, list, or scalar
        """
        # pylint: disable=R0914
        if isinstance(obj, dict):
            for i, (key, value) in enumerate(obj.items()):
                is_last = i == len(obj) - 1
                key_repr = f"{Ansi.ITALIC}{key}{Ansi.RESET}" if was_list else key
                if is_root:
                    decorator = ""
                elif is_last:
                    decorator = self.ELBOW
                else:
                    decorator = self.TEE
                self.append(f"{prefix}{decorator}{self.in_color(key_repr)}")

                if is_root:
                    prefix_rev = prefix
                elif is_last:
                    prefix_rev = prefix + self.SPACE_PREFIX
                else:
                    prefix_rev = prefix + self.PIPE_PREFIX
                self._print_tree(
                    obj=value,
                    prefix=prefix_rev,
                    is_last=self.is_scalar(value),
                    is_root=False,
                    was_list=False,
                )

        elif isinstance(obj, list):
            is_complex = any(isinstance(item, (dict, list)) for item in obj)
            is_long = len(obj) > 1
            if is_complex and is_long:
                repr_obj = {str(i): item for i, item in enumerate(obj)}
                self._print_tree(
                    obj=repr_obj,
                    prefix=prefix,
                    is_last=is_last,
                    is_root=False,
                    was_list=True,
                )
            else:
                for i, item in enumerate(obj):
                    is_last = i == len(obj) - 1
                    self._print_tree(
                        obj=item,
                        prefix=prefix,
                        is_last=is_last,
                        is_root=False,
                        was_list=False,
                    )

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
        # if not isinstance(self.obj, dict):
        self._print_tree(self.obj, is_last=False, is_root=True, was_list=False)
        return "\n".join(self._lines) + "\n"
