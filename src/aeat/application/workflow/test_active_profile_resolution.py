"""Precedence-chain tests for the active-profile resolver.

The resolver lives at
`aeat.application.workflow._models.resolve_active_bucket_id`. It
consults two precedence rungs in order:

1. `Settings.aeat_active_profile` (`AEAT_ACTIVE_PROFILE` env var, or
   an `override_settings(aeat_active_profile=...)` context manager).
2. The plaintext `<aeat-root>/active-profile` pointer file written
   by `register_active_profile` / `select_profile`.

A missing pointer + missing env override returns `None` so callers
that surface it to the operator can refuse with a typed
`NoActiveProfileError`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.application.workflow._bucket_pointer import BucketPointer
from aeat.application.workflow._bucket_pointer_io import write_pointer
from aeat.application.workflow._models import resolve_active_bucket_id
from aeat.core.config import override_settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_resolver_returns_none_when_no_rung_resolves(tmp_path: Path) -> None:
    """A fresh root with no env override + no pointer yields None."""

    with override_settings(aeat_active_profile=None, aeat_local_storage_root=tmp_path):
        assert resolve_active_bucket_id() is None


def test_pointer_file_wins_when_only_rung_two_is_set(tmp_path: Path) -> None:
    """With no env override, the pointer file is the canonical default."""

    write_pointer(tmp_path, BucketPointer(bucket_id="catering", schema_version=1))

    with override_settings(aeat_active_profile=None, aeat_local_storage_root=tmp_path):
        assert resolve_active_bucket_id() == "catering"


def test_settings_override_wins_over_pointer_file(tmp_path: Path) -> None:
    """Rung one (Settings) takes precedence over rung two (pointer)."""

    write_pointer(tmp_path, BucketPointer(bucket_id="catering", schema_version=1))

    with override_settings(aeat_active_profile="translation", aeat_local_storage_root=tmp_path):
        assert resolve_active_bucket_id() == "translation"


def test_empty_settings_override_falls_through_to_pointer(tmp_path: Path) -> None:
    """An empty override (whitespace) does not block rung two."""

    write_pointer(tmp_path, BucketPointer(bucket_id="catering", schema_version=1))

    with override_settings(aeat_active_profile="   ", aeat_local_storage_root=tmp_path):
        assert resolve_active_bucket_id() == "catering"
