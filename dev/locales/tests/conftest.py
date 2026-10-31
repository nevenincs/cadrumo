"""Fixtures shared by the locale gates that read the committed tree."""

from __future__ import annotations

import pytest

from .._paths import LOCALE_SOURCE_EXTRA_DIRS, LOCALES_DIR, SRC_DIR
from ..manager import LocaleManager


@pytest.fixture(scope="session")
def committed_locale_manager() -> LocaleManager:
    """One manager over the committed tree, so the codebase-key scan runs once.

    ``get_codebase_keys`` is the 9-15 s walk and the manager memoises it per
    instance. Tests that plant their own source tree build their own manager;
    this one is only for tests whose input is the committed tree, and they
    only read from it (``audit`` and ``get_codebase_keys`` hand back fresh or
    frozen results and write nothing).
    """
    return LocaleManager(src_dir=SRC_DIR, locales_dir=LOCALES_DIR, extra_src_dirs=LOCALE_SOURCE_EXTRA_DIRS)
