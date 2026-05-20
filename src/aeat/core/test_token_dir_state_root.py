"""Focused tests for the `aeat_token_dir` one-state-root contract.

The profile-state aggregate ADR mandates that every profile store -
token and lock files included - is rooted under
`aeat_local_storage_root`. The `aeat_token_dir` model validator
enforces this: when the field is not explicitly supplied, it derives
`<aeat_local_storage_root>/tokens`; an explicit `AEAT_TOKEN_DIR`
override still wins.

These tests construct real `Settings` instances and exercise the real
validator chain - no mocks, no fakes. Environment isolation via
`monkeypatch.setenv` is the accepted idiom: `BaseSettings` re-reads the
environment on every instantiation, so each test sees only the
variables it sets.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .config import Settings
from .paths import resolve_project_path

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


def test_token_dir_defaults_under_storage_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With no explicit `AEAT_TOKEN_DIR`, the token directory resolves
    to `<aeat_local_storage_root>/tokens` - the one-state-root contract.
    """

    monkeypatch.delenv("AEAT_TOKEN_DIR", raising=False)
    storage_root = tmp_path / "state-root"
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(storage_root))

    settings = Settings()

    assert settings.aeat_token_dir == storage_root / "tokens"
    # The token directory is genuinely nested under the storage root,
    # not merely a sibling that happens to share a prefix.
    assert (
        settings.aeat_local_storage_root
        in settings.aeat_token_dir.parents
    )


def test_token_dir_tracks_a_different_storage_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The derived default follows whatever `aeat_local_storage_root`
    is - it is not pinned to a single hard-coded location."""

    monkeypatch.delenv("AEAT_TOKEN_DIR", raising=False)
    other_root = tmp_path / "another" / "root"
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(other_root))

    settings = Settings()

    assert settings.aeat_token_dir == other_root / "tokens"


def test_explicit_token_dir_override_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An explicit `AEAT_TOKEN_DIR` env var overrides the derived
    default: the validator only computes the rooted path when the field
    was left unset."""

    storage_root = tmp_path / "state-root"
    explicit_token_dir = tmp_path / "operator-chosen-tokens"
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(explicit_token_dir))

    settings = Settings()

    assert settings.aeat_token_dir == explicit_token_dir
    assert settings.aeat_token_dir != storage_root / "tokens"


def test_explicit_token_dir_constructor_override_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A value passed directly to the `Settings` constructor registers
    in `model_fields_set` and wins over the derived default, the same
    way an `override_settings` block does."""

    monkeypatch.delenv("AEAT_TOKEN_DIR", raising=False)
    storage_root = tmp_path / "state-root"
    explicit_token_dir = tmp_path / "constructor-tokens"
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(storage_root))

    settings = Settings(aeat_token_dir=explicit_token_dir)

    assert settings.aeat_token_dir == resolve_project_path(explicit_token_dir)
    assert settings.aeat_token_dir != storage_root / "tokens"


def test_token_dir_default_is_not_the_repo_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The placeholder `PROJECT_ROOT` field default must never survive
    construction: the validator always replaces it with the rooted
    path. This guards against the validator silently not firing."""

    monkeypatch.delenv("AEAT_TOKEN_DIR", raising=False)
    storage_root = tmp_path / "state-root"
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(storage_root))

    settings = Settings()

    assert settings.aeat_token_dir != resolve_project_path(Path())
    assert settings.aeat_token_dir.name == "tokens"
