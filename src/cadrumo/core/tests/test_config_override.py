"""Focused tests for the Settings override seam.

The override mechanism is the foundation that lets call sites stop
reading os.environ directly. These tests pin the four behavioural
guarantees the helper provides:

- Scalar overrides take effect inside the with-block.
- The prior Settings value is restored on normal exit.
- The prior Settings value is restored on exception.
- A malformed override fails at entry with the same Pydantic
  ValidationError shape callers get from constructing Settings
  directly.

Tests construct real Settings instances and exercise the real
ContextVar; no mocks, no fakes, no monkeypatch of the override seam
itself.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from ..config import (
    Settings,
    coerce_output_language_setting,
    load_settings,
    override_settings,
    reset_settings_cache,
)
from ..external_constants import OutputLanguage
from ..paths import resolve_project_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Synthetic in-test path prefix. Never written or read on disk; the
# tests only assert how the override helper carries Path values through
# pydantic validation. Using a sentinel keeps Bandit B108 (probable
# insecure /tmp usage) quiet for this pure-data flow.
_NONEXISTENT_PATH_PREFIX = "non-existent-sentinel"


def test_public_output_language_coercer_normalises_only_supported_catalogue_codes() -> None:
    """The configuration facade is the one coercion boundary for language codes."""
    assert coerce_output_language_setting(" EN ") is OutputLanguage.EN
    assert coerce_output_language_setting("hu") is OutputLanguage.HU
    assert coerce_output_language_setting("xx") is None


def _expected_path(*parts: str) -> Path:
    """Return a sentinel path normalised the way the Settings path
    validator normalises every configured path (drive-anchored,
    resolved), so assertions stay portable across POSIX and Windows."""

    return resolve_project_path(Path(_NONEXISTENT_PATH_PREFIX, *parts))


def test_override_settings_swaps_scalar_field_inside_block() -> None:
    baseline_log_dir = load_settings().cadrumo_log_dir

    target = Path(_NONEXISTENT_PATH_PREFIX, "aeat-test-logs")
    expected = _expected_path("aeat-test-logs")
    with override_settings(cadrumo_log_dir=target) as overridden:
        assert overridden.cadrumo_log_dir == expected
        # load_settings inside the block returns the same overridden
        # instance — the ContextVar is honoured, not bypassed.
        assert load_settings().cadrumo_log_dir == expected
    assert load_settings().cadrumo_log_dir == baseline_log_dir


def test_override_settings_restores_prior_value_on_exception() -> None:
    """A user-raised exception inside the block must not leak the override."""

    baseline_log_dir = load_settings().cadrumo_log_dir

    scratch = Path(_NONEXISTENT_PATH_PREFIX, "scratch")
    with pytest.raises(RuntimeError, match="planned-failure"), override_settings(cadrumo_log_dir=scratch):
        assert load_settings().cadrumo_log_dir == _expected_path("scratch")
        raise RuntimeError("planned-failure")

    # The finally branch of the context manager restored the prior
    # ContextVar value despite the exception.
    assert load_settings().cadrumo_log_dir == baseline_log_dir


def test_override_settings_rejects_malformed_override_at_entry() -> None:
    """An override that fails Pydantic validation raises before the
    ContextVar is set, so the prior value survives unchanged."""

    baseline_log_dir = load_settings().cadrumo_log_dir

    with pytest.raises(ValidationError), override_settings(cadrumo_cert_warn_days=-1):  # gt=0 constraint
        pytest.fail("the with-block must not execute when override is invalid")

    assert load_settings().cadrumo_log_dir == baseline_log_dir


def test_override_settings_nested_blocks_compose_lifo() -> None:
    """Nested overrides apply in LIFO order — the inner override wins,
    and exiting the inner block restores the outer override (not the
    pre-outer baseline)."""

    baseline_log_dir = load_settings().cadrumo_log_dir

    outer_path = Path(_NONEXISTENT_PATH_PREFIX, "outer")
    inner_path = Path(_NONEXISTENT_PATH_PREFIX, "inner")

    with override_settings(cadrumo_log_dir=outer_path):
        assert load_settings().cadrumo_log_dir == _expected_path("outer")
        with override_settings(cadrumo_log_dir=inner_path):
            assert load_settings().cadrumo_log_dir == _expected_path("inner")
        # The inner block exited; the outer override is observable
        # again, not the pre-outer baseline.
        assert load_settings().cadrumo_log_dir == _expected_path("outer")

    assert load_settings().cadrumo_log_dir == baseline_log_dir


def test_override_settings_preserves_explicit_fields_set_signal() -> None:
    """Call sites that distinguish "operator set this explicitly" from
    "default flowed through" rely on ``model_fields_set``. The override
    helper must report ONLY the override keys plus whatever the source
    instance already had explicit, not every field that flowed through
    the merged dict."""

    baseline = load_settings()
    baseline_explicit = set(baseline.model_fields_set)
    assert "cadrumo_log_dir" not in baseline_explicit

    with override_settings(cadrumo_log_dir=Path(f"{_NONEXISTENT_PATH_PREFIX}/explicit")):
        overridden = load_settings()
        # The override key is now in the explicit set.
        assert "cadrumo_log_dir" in overridden.model_fields_set
        # Defaults that were not overridden remain NOT in the explicit
        # set — operator did not touch them in this override block.
        assert "cadrumo_cert_warn_days" not in overridden.model_fields_set


@contextmanager
def _absent_env_var(name: str) -> Iterator[None]:
    """Remove ``name`` from the process environment for the scope, then restore it.

    A local context manager rather than the pytest ``monkeypatch`` fixture, per
    this package's no-monkeypatch discipline.

    ``_constructed_settings`` is lru_cached, so settings built earlier in this
    process would answer from before the removal and the variable would look
    inert; the cache is dropped on both edges. ``override_settings`` is
    deliberately NOT used to establish the absence — it would prove the
    override mechanism, which is the very thing under test, instead of the
    ambient state the assertions read.
    """
    previous = os.environ.get(name)
    os.environ.pop(name, None)
    reset_settings_cache()
    try:
        yield
    finally:
        if previous is not None:
            os.environ[name] = previous
        reset_settings_cache()


def test_override_settings_carries_secretstr_through_validation() -> None:
    """The master-key passphrase override travels as a real SecretStr —
    Pydantic accepts a bare string and coerces; the override path must
    produce the same shape callers get from .env.

    The absent-passphrase baseline is established rather than assumed. The
    pytest harness bridges the operator's local ``env/.env`` into the process
    environment so integration paths see real configuration, and that file
    carries a real ``CADRUMO_SECRET_PASSPHRASE`` on a developer machine.

    Removing the variable is necessary but NOT sufficient, which is what this
    test used to get wrong. ``conftest`` wraps the whole session in an outermost
    ``override_settings`` for the KDF calibration flag, and that snapshots the
    environment ONCE at session start. From then on ``load_settings`` answers
    from the snapshot, so a later ``os.environ.pop`` plus a cache clear cannot
    reach it and the baseline still carried the developer's passphrase.

    The baseline is therefore read from a directly constructed ``Settings``,
    which consults the live environment and no context-local override. That
    keeps the absence ambient rather than asserted through the very mechanism
    under test, which is what the round-trip below exercises.
    """

    with _absent_env_var("CADRUMO_SECRET_PASSPHRASE"):
        _assert_secretstr_override_round_trip()


def _assert_secretstr_override_round_trip() -> None:
    """Assert the override installs a real SecretStr and restores absence."""
    assert Settings().cadrumo_secret_passphrase is None, (
        "the environment still supplies a passphrase, so the absent baseline is not established"
    )

    with override_settings(cadrumo_secret_passphrase=SecretStr("test-pass")):
        overridden = load_settings()
        assert overridden.cadrumo_secret_passphrase is not None
        assert overridden.cadrumo_secret_passphrase.get_secret_value() == "test-pass"

    assert Settings().cadrumo_secret_passphrase is None
