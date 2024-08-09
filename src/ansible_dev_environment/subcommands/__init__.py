"""The subcommands module contains all the subcommands for ansible-dev-environment."""

# ruff: noqa: F401
from __future__ import annotations

from .checker import Checker as Check
from .inspector import Inspector as Inspect
from .installer import Installer as Install
from .lister import Lister as List
from .treemaker import TreeMaker as Tree
from .uninstaller import UnInstaller as Uninstall
