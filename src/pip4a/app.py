"""Application internals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from argparse import Namespace


@dataclass
class App:
    """Application internals."""

    args: Namespace
    collection_name: str
    collection_dependencies: dict[str, str]
