"""Constants, for now, for pip4a."""

from pathlib import Path


class Constants:
    """Constants, for now, for pip4a."""

    TEST_REQUIREMENTS_PY = Path("./test-requirements.txt").resolve()
    WORKING_DIR = Path("./.pip4a_cache").resolve()
    COLLECTION_BUILD_DIR = WORKING_DIR / "src"
    DISCOVERED_PYTHON_REQS = WORKING_DIR / "discovered_requirements.txt"
    DISCOVERED_BINDEP_REQS = WORKING_DIR / "discovered_bindep.txt"
    INSTALLED_COLLECTIONS = WORKING_DIR / "installed_collections.txt"
