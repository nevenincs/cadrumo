"""Focused tests for the Settings override seam.

The override mechanism is the foundation that lets call sites stop
reading os.environ directly. These tests pin the four behavioural
guarantees the ADR makes about the helper:

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

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from .config import load_settings, override_settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


def test_override_settings_swaps_scalar_field_inside_block() -> None:
    baseline = load_settings()
    assert baseline.aeat_log_dir is None

    target = Path("/tmp/aeat-test-logs")
    with override_settings(aeat_log_dir=target) as overridden:
        assert overridden.aeat_log_dir == target
        # load_settings inside the block returns the same overridden
        # instance — the ContextVar is honoured, not bypassed.
        assert load_settings().aeat_log_dir == target


def test_override_settings_restores_prior_value_on_normal_exit() -> None:
    baseline = load_settings()
    assert baseline.aeat_log_dir is None

    with override_settings(aeat_log_dir=Path("/tmp/scratch")):
        assert load_settings().aeat_log_dir == Path("/tmp/scratch")

    # On exit the ContextVar is reset; the baseline default is
    # observable again.
    assert load_settings().aeat_log_dir is None


def test_override_settings_restores_prior_value_on_exception() -> None:
    """A user-raised exception inside the block must not leak the override."""

    assert load_settings().aeat_log_dir is None

    with pytest.raises(RuntimeError, match="planned-failure"):
        with override_settings(aeat_log_dir=Path("/tmp/scratch")):
            assert load_settings().aeat_log_dir == Path("/tmp/scratch")
            raise RuntimeError("planned-failure")

    # The finally branch of the context manager restored the prior
    # ContextVar value despite the exception.
    assert load_settings().aeat_log_dir is None


def test_override_settings_rejects_malformed_override_at_entry() -> None:
    """An override that fails Pydantic validation raises before the
    ContextVar is set, so the prior value survives unchanged."""

    baseline = load_settings()
    assert baseline.aeat_log_dir is None

    with pytest.raises(ValidationError):
        with override_settings(aeat_cert_warn_days=-1):  # gt=0 constraint
            pytest.fail("the with-block must not execute when override is invalid")

    assert load_settings().aeat_log_dir is None


def test_override_settings_nested_blocks_compose_lifo() -> None:
    """Nested overrides apply in LIFO order — the inner override wins,
    and exiting the inner block restores the outer override (not the
    pre-outer baseline)."""

    assert load_settings().aeat_log_dir is None

    outer_path = Path("/tmp/outer")
    inner_path = Path("/tmp/inner")

    with override_settings(aeat_log_dir=outer_path):
        assert load_settings().aeat_log_dir == outer_path
        with override_settings(aeat_log_dir=inner_path):
            assert load_settings().aeat_log_dir == inner_path
        # The inner block exited; the outer override is observable
        # again, not the pre-outer baseline.
        assert load_settings().aeat_log_dir == outer_path

    assert load_settings().aeat_log_dir is None


def test_override_settings_preserves_explicit_fields_set_signal() -> None:
    """Call sites that distinguish "operator set this explicitly" from
    "default flowed through" rely on ``model_fields_set``. The override
    helper must report ONLY the override keys plus whatever the source
    instance already had explicit, not every field that flowed through
    the merged dict."""

    baseline = load_settings()
    baseline_explicit = set(baseline.model_fields_set)
    assert "aeat_log_dir" not in baseline_explicit

    with override_settings(aeat_log_dir=Path("/tmp/explicit")):
        overridden = load_settings()
        # The override key is now in the explicit set.
        assert "aeat_log_dir" in overridden.model_fields_set
        # Defaults that were not overridden remain NOT in the explicit
        # set — operator did not touch them in this override block.
        assert "aeat_cert_warn_days" not in overridden.model_fields_set


def test_override_settings_carries_secretstr_through_validation() -> None:
    """The master-key passphrase override travels as a real SecretStr —
    Pydantic accepts a bare string and coerces; the override path must
    produce the same shape callers get from .env."""

    baseline = load_settings()
    assert baseline.aeat_master_key_passphrase is None

    with override_settings(aeat_master_key_passphrase=SecretStr("test-pass")):
        overridden = load_settings()
        assert overridden.aeat_master_key_passphrase is not None
        assert overridden.aeat_master_key_passphrase.get_secret_value() == "test-pass"

    assert load_settings().aeat_master_key_passphrase is None
