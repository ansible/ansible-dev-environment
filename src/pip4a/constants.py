"""Constants, for now, for pip4a."""

from pathlib import Path


class Constants:
    """Constants, for now, for pip4a."""

    TEST_REQUIREMENTS_PY = Path("./test-requirements.txt").resolve()
    REQUIREMENTS_PY = Path("./requirements.txt").resolve()
    COLLECTION_BUILD_DIR = Path("./build").resolve()
