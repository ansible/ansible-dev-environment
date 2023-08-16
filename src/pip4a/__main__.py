"""A runpy entry point for pip4a.

This makes it possible to invoke CLI
via :command:`python -m pip4a`.
"""

from .cli import main


if __name__ == "__main__":
    main()
