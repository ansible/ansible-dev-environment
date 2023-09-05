"""The installer."""

from __future__ import annotations

import logging
import shutil
import subprocess

from .base import Base
from .constants import Constants as C  # noqa: N817


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

        if not C.WORKING_DIR.exists():
            msg = f"Failed to find working directory '{C.WORKING_DIR}', nothing to do."
            logger.warning(msg)
            return

        self._set_interpreter()
        self._set_bindir()
        self._set_site_pkg_path()

        self._pip_uninstall()
        self._remove_collections()
        shutil.rmtree(C.WORKING_DIR, ignore_errors=True)

    def _remove_collections(self: UnInstaller) -> None:  # noqa: C901, PLR0912, PLR0915
        """Remove the collection and dependencies."""
        if not C.INSTALLED_COLLECTIONS.exists():
            msg = f"Failed to find {C.INSTALLED_COLLECTIONS}"
            logger.warning(msg)
            return
        with C.INSTALLED_COLLECTIONS.open() as f:
            collection_names = f.read().splitlines()

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

    def _pip_uninstall(self: UnInstaller) -> None:
        """Uninstall the dependencies."""
        if not C.DISCOVERED_PYTHON_REQS.exists():
            msg = f"Failed to find {C.DISCOVERED_PYTHON_REQS}"
            logger.warning(msg)
            return

        command = (
            f"{self.interpreter} -m pip uninstall -r {C.DISCOVERED_PYTHON_REQS} -y"
        )

        msg = f"Uninstalling python requirements from {C.DISCOVERED_PYTHON_REQS}"
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
            err = (
                f"Failed to uninstall requirements from {C.DISCOVERED_PYTHON_REQS}:"
                f" {exc} - {exc.stderr}"
            )
            logger.critical(err)

        # Repair the core and builder installs if needed.
        msg = "Repairing the core and builder installs if needed."
        logger.info(msg)
        command = f"{self.interpreter} -m pip check"
        msg = f"Running command: {command}"
        logger.debug(msg)
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                shell=True,  # noqa: S602
                text=True,
            )
        except subprocess.CalledProcessError:
            pass
        else:
            return

        command = (
            f"{self.interpreter} -m pip install --upgrade"
            " --force-reinstall ansible-core ansible-builder"
        )
        msg = f"Running command: {command}"
        logger.debug(msg)
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                shell=True,  # noqa: S602
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to repair the core and builder installs: {exc}"
            logger.critical(err)
