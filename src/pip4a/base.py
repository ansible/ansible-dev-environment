"""A base class for pip4a."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .app import App

logger = logging.getLogger(__name__)


class Base:
    """A base class for pip4a."""

    def __init__(self: Base, app: App) -> None:
        """Initialize the installer.

        Arguments:
            app: The app instance
        """
        self.app: App = app
        self.bindir: Path
        self.interpreter: Path
        self.site_pkg_path: Path
        self.python_path: Path

    def _set_interpreter(  # noqa: PLR0912
        self: Base,
        create: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Set the interpreter."""
        venv = None
        if self.app.args.venv:
            venv = Path(self.app.args.venv).resolve()
        else:
            venv_str = os.environ.get("VIRTUAL_ENV")
            if venv_str:
                venv = Path(venv_str).resolve()
        if venv:
            if not venv.exists():
                if create:
                    if not venv.relative_to(Path.cwd()):
                        err = "Virtual environment must relative to cwd to create it."
                        logger.critical(err)
                    msg = f"Creating virtual environment: {venv}"
                    logger.info(msg)
                    command = f"python -m venv {venv}"
                    msg = f"Running command: {command}"
                    logger.debug(msg)
                    try:
                        subprocess.run(
                            command,
                            check=True,
                            shell=True,  # noqa: S602
                            capture_output=self.app.args.verbose,
                        )
                    except subprocess.CalledProcessError as exc:
                        err = f"Failed to create virtual environment: {exc}"
                        logger.critical(err)
                else:
                    err = f"Cannot find virtual environment: {venv}."
                    logger.critical(err)
            msg = f"Virtual environment: {venv}"
            logger.info(msg)
            interpreter = venv / "bin" / "python"
            if not interpreter.exists():
                err = f"Cannot find interpreter: {interpreter}."
                logger.critical(err)

            msg = f"Using specified interpreter: {interpreter}"
            logger.info(msg)
            self.interpreter = interpreter
        else:
            self.interpreter = Path(sys.executable)
            msg = f"Using current interpreter: {self.interpreter}"
            logger.info(msg)

        command = "python -c 'import sys; print(sys.executable)'"
        msg = f"Running command: {command}"
        logger.debug(msg)
        try:
            proc = subprocess.run(
                command,
                check=True,
                capture_output=True,
                shell=True,  # noqa: S602
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to find interpreter in use: {exc}"
            logger.critical(err)

        self.python_path = Path(proc.stdout.strip())

    def _set_bindir(self: Base) -> None:
        """Set the bindir."""
        self.bindir = self.interpreter.parent
        if not self.bindir.exists():
            err = f"Cannot find bindir: {self.bindir}."
            logger.critical(err)

    def _set_site_pkg_path(self: Base) -> None:
        """USe the interpreter to find the site packages path."""
        command = (
            f"{self.interpreter} -c"
            " 'import json,site; print(json.dumps(site.getsitepackages()))'"
        )
        msg = f"Running command: {command}"
        logger.debug(msg)
        try:
            proc = subprocess.run(
                command,
                check=True,
                capture_output=True,
                shell=True,  # noqa: S602
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to find site packages path: {exc}"
            logger.critical(err)

        try:
            site_pkg_dirs = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            err = f"Failed to decode json: {exc}"
            logger.critical(err)

        if not site_pkg_dirs:
            err = "Failed to find site packages path."
            logger.critical(err)

        msg = f"Found site packages path: {site_pkg_dirs[0]}"
        logger.debug(msg)

        self.site_pkg_path = Path(site_pkg_dirs[0])
