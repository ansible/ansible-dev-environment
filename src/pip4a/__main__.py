"""A runpy entry point for pipc.

This makes it possible to invoke CLI
via :command:`python -m pipac`.
"""

from .cli import main


if __name__ == "__main__":
    main()
