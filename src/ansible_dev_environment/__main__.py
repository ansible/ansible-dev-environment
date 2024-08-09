"""A runpy entry point for ansible-dev-environment.

This makes it possible to invoke CLI
via :command:`python -m ansible_dev_environment`.
"""
from __future__ import annotations

from ansible_dev_environment.cli import main


if __name__ == "__main__":
    main()
