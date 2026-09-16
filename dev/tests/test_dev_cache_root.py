"""The development caches resolve through one configurable root.

Seven caches once each resolved their own home-directory path, so there was no
single answer to "where does derived output go" and no single place to change
it. The resolver these tests cover is that answer: an explicit root wins, and
the fallback is the checkout's own ignored ``.cache``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var
from dev._paths import REPO_ROOT
from dev.cache_root import DEFAULT_DEV_CACHE_ROOT, DEV_CACHE_ROOT_ENV, dev_cache_dir, dev_cache_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_default_root_is_the_checkouts_own_ignored_cache_directory() -> None:
    with scoped_env_var(DEV_CACHE_ROOT_ENV, None):
        assert dev_cache_root() == REPO_ROOT / ".cache"
    assert DEFAULT_DEV_CACHE_ROOT == REPO_ROOT / ".cache"


def test_an_explicit_root_relocates_every_cache(tmp_path: Path) -> None:
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(tmp_path / "elsewhere")):
        assert dev_cache_root() == tmp_path / "elsewhere"
        assert dev_cache_dir("corpus-text") == tmp_path / "elsewhere" / "corpus-text"


def test_a_blank_root_is_treated_as_unset() -> None:
    """An exported-but-empty variable must not resolve the caches to the CWD."""
    with scoped_env_var(DEV_CACHE_ROOT_ENV, "   "):
        assert dev_cache_root() == DEFAULT_DEV_CACHE_ROOT


def test_resolving_a_cache_creates_nothing(tmp_path: Path) -> None:
    with scoped_env_var(DEV_CACHE_ROOT_ENV, str(tmp_path / "untouched")):
        resolved = dev_cache_dir("record-design")
    assert not resolved.exists()
    assert not (tmp_path / "untouched").exists()


@pytest.mark.parametrize("name", ["", "   ", " padded", "nested/name", "..", ".", "a\\b"])
def test_a_name_that_is_not_one_segment_is_refused(name: str) -> None:
    with pytest.raises(ValueError, match="cache name must be"):
        dev_cache_dir(name)


def test_the_env_template_documents_the_root() -> None:
    """A setting nobody can discover is not configurable in practice."""
    template = (REPO_ROOT / "env" / ".env.example").read_text(encoding="utf-8")
    assert f"{DEV_CACHE_ROOT_ENV}=" in template
