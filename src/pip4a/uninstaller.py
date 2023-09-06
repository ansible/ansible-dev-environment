"""The installer."""

from __future__ import annotations

import logging
import shutil
import subprocess

from typing import TYPE_CHECKING

from .utils import subprocess_run


if TYPE_CHECKING:
    from .config import Config


logger = logging.getLogger(__name__)


class UnInstaller:
    """The uninstaller class."""

    def __init__(self: UnInstaller, config: Config) -> None:
        """Initialize the installer.

        Args:
            config: The application configuration.
        """
        self._config = config

    def run(self: UnInstaller) -> None:
        """Run the uninstaller."""
        if not self._config.collection_cache_dir.exists():
            err = (
                f"Either the collection '{self._config.collection_name}' was"
                " previously uninstalled or was not initially installed using pip4a."
            )
            logger.critical(err)

        self._pip_uninstall()
        self._remove_collections()
        shutil.rmtree(self._config.collection_cache_dir)

    def _remove_collections(self: UnInstaller) -> None:  # noqa: C901, PLR0912, PLR0915
        """Remove the collection and dependencies."""
        if not self._config.installed_collections.exists():
            msg = f"Failed to find {self._config}"
            logger.warning(msg)
            return
        with self._config.installed_collections.open() as f:
            collection_names = f.read().splitlines()

        collection_namespace_roots = []
        collection_root = self._config.site_pkg_path / "ansible_collections"

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
        if not self._config.discovered_python_reqs.exists():
            msg = f"Failed to find {self._config.discovered_python_reqs}"
            logger.warning(msg)
            return

        command = (
            f"{self._config.venv_interpreter} -m pip uninstall"
            f" -r {self._config.discovered_python_reqs} -y"
        )

        msg = f"Uninstalling python requirements from {self._config.discovered_python_reqs}"
        logger.info(msg)
        try:
            subprocess_run(command=command, verbose=self._config.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = (
                f"Failed to uninstall requirements from {self._config.discovered_python_reqs}:"
                f" {exc} - {exc.stderr}"
            )
            logger.critical(err)

        # Repair the core and builder installs if needed.
        msg = "Repairing the core and builder installs if needed."
        logger.info(msg)
        command = f"{self._config.venv_interpreter} -m pip check"
        try:
            subprocess_run(command=command, verbose=self._config.args.verbose)
        except subprocess.CalledProcessError:
            pass
        else:
            return

        command = (
            f"{self._config.venv_interpreter} -m pip install --upgrade"
            " --force-reinstall ansible-core ansible-builder"
        )
        try:
            subprocess_run(command=command, verbose=self._config.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = f"Failed to repair the core and builder installs: {exc}"
            logger.critical(err)
