"""Legacy-layout refusal tests for the AEAT runtime entrypoint guard.

`assert_no_legacy_layout` fires `LegacyLayoutDetectedError` when
``<aeat-root>/var/`` exists alongside an absent
``<aeat-root>/buckets/`` directory. A fresh install (no `var/`
under the root) and a fully migrated install (only `buckets/`)
must not trigger the refusal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.bucket._errors import LegacyLayoutDetectedError
from aeat.application._bootstrap import assert_no_legacy_layout, detect_legacy_layout
from aeat.core.config import override_settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_detects_legacy_layout_when_var_alone_is_present(tmp_path: Path) -> None:
    """`<aeat-root>/var/` without `<aeat-root>/buckets/` is the refusal case."""

    (tmp_path / "var").mkdir()

    with override_settings(aeat_local_storage_root=tmp_path):
        assert detect_legacy_layout() is True


def test_no_refusal_on_fresh_root(tmp_path: Path) -> None:
    """A root with neither `var/` nor `buckets/` is a fresh install."""

    with override_settings(aeat_local_storage_root=tmp_path):
        assert detect_legacy_layout() is False
        assert_no_legacy_layout()


def test_no_refusal_when_buckets_directory_exists(tmp_path: Path) -> None:
    """`buckets/` alongside `var/` means the migration is complete."""

    (tmp_path / "var").mkdir()
    (tmp_path / "buckets").mkdir()

    with override_settings(aeat_local_storage_root=tmp_path):
        assert detect_legacy_layout() is False
        assert_no_legacy_layout()


def test_assert_raises_on_legacy_layout(tmp_path: Path) -> None:
    """The guard raises a typed error against the legacy-only tree."""

    (tmp_path / "var").mkdir()

    with override_settings(aeat_local_storage_root=tmp_path):
        with pytest.raises(LegacyLayoutDetectedError):
            assert_no_legacy_layout()
