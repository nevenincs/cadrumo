"""Registry loader cache predicates."""

from __future__ import annotations


def registry_disk_cache_enabled() -> bool:
    """Whether the cross-process ``/tmp`` registry pickle is read/written.

    Disabled under pytest, including collection before ``PYTEST_CURRENT_TEST``
    is set: the pickle is keyed by file mtime and shared across pytest-xdist
    workers, so a parallel run could serve a stale compiled registry from one
    worker to another. Production loads the registry once at startup with no
    concurrent edits, so it keeps the disk cache.
    """
    import os
    import sys

    if "pytest" in sys.modules:
        return False
    return (
        "PYTEST_CURRENT_TEST" not in os.environ
        and "PYTEST_XDIST_WORKER" not in os.environ
        and "PYTEST_VERSION" not in os.environ
    )
