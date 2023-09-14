# cspell:ignore mkey, mfour
"""Test the tree generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pip4a.tree import Tree


if TYPE_CHECKING:
    import pytest

    from pip4a.tree import JSONVal


sample_1: JSONVal = {
    "key_one": "one",
    "key_two": 42,
    "key_three": True,
    "key_four": None,
    "key_five": ["one", "two", "three"],
    "key_six": {
        "key_one": "one",
        "key_two": 42,
        "key_three": True,
        "key_four": None,
        "key_five": ["one", "two", "three"],
        "key_six": {
            "key_one": "one",
            "key_two": 42,
            "key_three": True,
            "key_four": None,
            "key_five": ["one", "two", "three"],
            "key_six": {
                "key_one": "one",
                "key_two": 42,
                "key_three": True,
                "key_four": None,
                "key_five": ["one", "two", "three"],
            },
        },
    },
    "key_seven": [{"foo": [1, 2, 3]}],
    "key_eight": [1, 2, 3],
}

result = r"""key_one
└──one
key_two
└──42
key_three
└──True
key_four
└──None
key_five
├──one
├──two
└──three
key_six
├──key_one
│  └──one
├──key_two
│  └──42
├──key_three
│  └──True
├──key_four
│  └──None
├──key_five
│  ├──one
│  ├──two
│  └──three
└──key_six
   ├──key_one
   │  └──one
   ├──key_two
   │  └──42
   ├──key_three
   │  └──True
   ├──key_four
   │  └──None
   ├──key_five
   │  ├──one
   │  ├──two
   │  └──three
   └──key_six
      ├──key_one
      │  └──one
      ├──key_two
      │  └──42
      ├──key_three
      │  └──True
      ├──key_four
      │  └──None
      └──key_five
         ├──one
         ├──two
         └──three
key_seven
└──foo
   ├──1
   ├──2
   └──3
key_eight
├──1
├──2
└──3
"""


def test_tree_large(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the tree generator."""
    monkeypatch.setenv("NO_COLOR", "true")

    assert Tree(sample_1).render() == result


sample_2: JSONVal = {
    "key_one": True,
    "key_two": 42,
    "key_three": None,
    "key_four": "four",
    "key_five": [{"a": 1}, {"b": 2}],
}

expected = [
    "\x1b[34mkey_one\x1b[0m",
    "└──\x1b[32mTrue\x1b[0m",
    "\x1b[34mkey_two\x1b[0m",
    "└──\x1b[32m42\x1b[0m",
    "\x1b[34mkey_three\x1b[0m",
    "└──\x1b[32mNone\x1b[0m",
    "\x1b[34mkey_four\x1b[0m",
    "└──\x1b[32mfour\x1b[0m",
    "key_five",
    "├──\x1b[3m0\x1b[0m",
    "│  └──a",
    "│     └──1",
    "└──\x1b[3m1\x1b[0m",
    "   └──b",
    "      └──2",
]


def test_tree_color() -> None:
    """Test the tree generator."""
    tree = Tree(sample_2)
    tree.blue = ["key_one", "key_two", "key_three", "key_four"]
    tree.green = [True, 42, None, "four"]
    rendered = tree.render().splitlines()
    assert rendered == expected