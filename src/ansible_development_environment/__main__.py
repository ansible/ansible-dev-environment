"""A runpy entry point for ansible-dev-environment.

This makes it possible to invoke CLI
via :command:`python -m ansible_development_environment`.
"""

from .cli import main


if __name__ == "__main__":
    main()
