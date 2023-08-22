"""The installer."""

from __future__ import annotations

import logging
import shutil
import subprocess

from typing import TYPE_CHECKING

from .base import Base
from .constants import Constants as C  # noqa: N817


if TYPE_CHECKING:
    from pathlib import Path

    pass


logger = logging.getLogger(__name__)


class UnInstaller(Base):
    """The uninstaller class."""

    def run(self: UnInstaller) -> None:
        """Run the installer."""
        if self.app.args.collection_specifier not in (self.app.collection_name, "."):
            err = (
                "Invalid requirement: {self.app.args.collection_specifier} ignored -"
                " the uninstall command expects the name of the local collection."
            )
            logger.warning(err)
            err = (
                "You must give at least one requirement"
                f" to uninstall (e.g. {self.app.collection_name})."
            )
            logger.critical(err)

        self._set_interpreter()
        self._set_bindir()
        self._set_site_pkg_path()

        self._pip_uninstall(C.REQUIREMENTS_PY)
        self._pip_uninstall(C.TEST_REQUIREMENTS_PY)
        self._remove_collections()

    def _remove_collections(self: UnInstaller) -> None:  # noqa: C901, PLR0912
        collection_names = [
            *list(self.app.collection_dependencies.keys()),
            self.app.collection_name,
        ]

        collection_namespace_roots = []
        collection_root = self.site_pkg_path / "ansible_collections"

        for collection_name in collection_names:
            namespace, name = collection_name.split(".")
            collection_namespace_root = collection_root / namespace
            collection_namespace_roots.append(collection_namespace_root)

            collection_path = collection_namespace_root / name
            msg = f"Checking {collection_name} at {collection_path}"
            logger.debug(msg)

            if collection_path.exists():
                msg = f"Exists: {collection_path}"
                logger.debug(msg)

                if collection_path.is_symlink():
                    collection_path.unlink()
                else:
                    shutil.rmtree(collection_path)
                msg = f"Removed {collection_name}: {collection_path}"
                logger.info(msg)
            else:
                msg = f"Failed to find {collection_name}: {collection_path}"
                logger.debug(msg)

            if not collection_namespace_root.exists():
                continue

            for entry in collection_root.iterdir():
                if all(
                    (
                        entry.is_dir(),
                        entry.name.startswith(collection_name),
                        entry.suffix == ".info",
                    ),
                ):
                    shutil.rmtree(entry)
                    msg = f"Removed {collection_name}*.info: {entry}"
                    logger.info(msg)

        for collection_namespace_root in collection_namespace_roots:
            try:
                collection_namespace_root.rmdir()
                msg = f"Removed collection namespace root: {collection_namespace_root}"
                logger.info(msg)
            except FileNotFoundError:  # noqa: PERF203
                pass
            except OSError as exc:
                err = f"Failed to remove collection namespace root: {exc}"
                logger.warning(err)

        if not collection_root.exists():
            return
        try:
            collection_root.rmdir()
            msg = f"Removed collection root: {collection_root}"
            logger.info(msg)
        except FileNotFoundError:
            pass
        except OSError as exc:
            msg = f"Failed to remove collection root: {exc}"
            logger.debug(msg)

    def _pip_uninstall(self: UnInstaller, requirements_file: Path) -> None:
        """Uninstall the dependencies."""
        if not requirements_file.exists():
            msg = f"Requirements file {requirements_file} does not exist, skipping"
            logger.info(msg)
            return

        if requirements_file.stat().st_size == 0:
            msg = f"Requirements file {requirements_file} is empty, skipping"
            logger.info(msg)
            return

        command = f"{self.interpreter} -m pip uninstall -r {requirements_file} -y"

        msg = f"Uninstalling python requirements from {requirements_file}"
        logger.info(msg)
        msg = f"Running command: {command}"
        logger.debug(msg)
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=not self.app.args.verbose,
                shell=True,  # noqa: S602
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to uninstall requirements from {requirements_file}: {exc} - {exc.stderr}"
            logger.critical(err)
