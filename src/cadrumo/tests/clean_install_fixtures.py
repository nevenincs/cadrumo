"""Canonical clean-install fixture for cross-surface language tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ..core.external_constants import OUTPUT_LANGUAGE_ENV_VAR
from ..core.i18n.render import clear_output_language_cache
from .env_scope import scoped_env_var
from .secure_sql import isolated_sessionless_storage_root


@pytest.fixture
def _clean_install(tmp_path: Path) -> Iterator[None]:
    with scoped_env_var(OUTPUT_LANGUAGE_ENV_VAR, None), isolated_sessionless_storage_root(tmp_path=tmp_path):
        clear_output_language_cache()
        try:
            yield
        finally:
            clear_output_language_cache()


__all__ = ["_clean_install"]
