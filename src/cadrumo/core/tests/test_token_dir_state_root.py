"""Focused tests for the `cadrumo_token_dir` one-state-root contract.

The profile-state aggregate contract requires every profile store -
token and lock files included - is rooted under
`cadrumo_local_storage_root`. The `cadrumo_token_dir` model validator
enforces this: when the field is not explicitly supplied, it derives
`<cadrumo_local_storage_root>/tokens`; an explicit `CADRUMO_TOKEN_DIR`
override still wins.

These tests construct real `Settings` instances and exercise the real
validator chain - no mocks, no fakes. Inputs are injected via
constructor kwargs (highest priority in ``pydantic-settings``) so the
tests do not depend on or mutate the ambient environment. A small
`_without_token_dir_env` scope helper guards the derive-default branch
against an ambient `CADRUMO_TOKEN_DIR` leaking in via env precedence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ...tests.env_scope import scoped_env_var
from ..config import Settings
from ..paths import resolve_project_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"tokens"})
"""Taxonomy-vocabulary literals this module deliberately pins.

``storage_root / "tokens"`` is the independent oracle for what
``cadrumo_token_dir`` defaults to when unoverridden. Re-deriving it from the
taxonomy accessor would compare the settings derivation against itself.
"""


def _without_token_dir_env():
    """Suppress an ambient ``CADRUMO_TOKEN_DIR`` for the with-block.

    The validator-derives-default branch must observe an unset
    ``cadrumo_token_dir``. Constructor kwargs win against env, but the
    tests that want the *derived* path pass no kwarg, so env precedence
    would surface here. Delegates to the centralized
    :func:`cadrumo.tests.env_scope.scoped_env_var` helper.
    """
    return scoped_env_var("CADRUMO_TOKEN_DIR", None)


def test_token_dir_defaults_under_storage_root(tmp_path: Path) -> None:
    """With no explicit `CADRUMO_TOKEN_DIR`, the token directory resolves
    to `<cadrumo_local_storage_root>/tokens` for any storage-root shape.
    """

    cases: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("simple-root", ("state-root",)),
        ("nested-root", ("another", "root")),
    )

    for case_id, storage_root_parts in cases:
        storage_root = tmp_path.joinpath(*storage_root_parts)
        with _without_token_dir_env():
            settings = Settings(cadrumo_local_storage_root=storage_root)

        assert settings.cadrumo_token_dir == storage_root / "tokens", case_id
        # The token directory is genuinely nested under the storage root,
        # not merely a sibling that happens to share a prefix.
        assert settings.cadrumo_local_storage_root in settings.cadrumo_token_dir.parents, case_id


def test_explicit_token_dir_constructor_override_wins(tmp_path: Path) -> None:
    """A value passed directly to the `Settings` constructor registers
    in `model_fields_set` and wins over the derived default, the same
    way an `override_settings` block does."""

    storage_root = tmp_path / "state-root"
    explicit_token_dir = tmp_path / "constructor-tokens"
    settings = Settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_token_dir=explicit_token_dir,
    )

    assert settings.cadrumo_token_dir == resolve_project_path(explicit_token_dir)
    assert settings.cadrumo_token_dir != storage_root / "tokens"


def test_token_dir_default_is_not_the_repo_root(tmp_path: Path) -> None:
    """The placeholder `PROJECT_ROOT` field default must never survive
    construction: the validator always replaces it with the rooted
    path. This guards against the validator silently not firing."""

    storage_root = tmp_path / "state-root"
    with _without_token_dir_env():
        settings = Settings(cadrumo_local_storage_root=storage_root)

    assert settings.cadrumo_token_dir != resolve_project_path(Path())
    assert settings.cadrumo_token_dir.name == "tokens"
