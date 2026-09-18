"""Keep the documentation engine's process pins inside the test that caused them.

The engine deliberately re-points product storage and diagnostic logging at its
own scratch directories for the lifetime of the process it runs in
(``dev.docs.build.ensure_isolated_storage_root``), so a build never reads the
workstation's real store and never writes the shared ``cadrumo.log``. That is
correct for a build process, whose lifetime IS the build.

A pytest worker outlives the test, so the same pin silently becomes the
environment of every test that follows it on that worker. It was doing exactly
that: ``CADRUMO_LOG_DIR`` stayed set, which made ``cadrumo_log_dir`` read as an
explicitly overridden setting rather than one derived from the storage root, and
``dev/ci/tests/test_core_storage_taxonomy.py`` then failed in whole-tree runs
while passing in every scoped run anyone tried.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from cadrumo.tests.env_scope import scoped_product_storage_environment


@pytest.fixture(autouse=True)
def _contain_docs_engine_storage_pins() -> Iterator[None]:
    """Restore the product storage environment after each documentation test."""
    with scoped_product_storage_environment():
        yield
