"""Focused unit tests for application.auth.actions.update_auth.

`update_auth` is a pure state-transition helper that mutates AuthState
via WorkflowState.model_copy. Four kwarg-driven branches:

- ``provider`` → sets provider (lowercased + stripped) and stamps
  ``configured_at``.
- ``certificate_path`` → sets certificate_path (empty string becomes
  None) and stamps ``configured_at``.
- ``authenticated`` → sets ``authenticated_at`` (timestamp when True,
  None when False).
- ``subject`` → sets subject (empty string becomes None).

Each kwarg also bumps ``state.updated_at``.

Previously no direct unit-test coverage. The helper is consumed by
every auth-readiness mutation surface; a regression in any branch
would silently corrupt the auth-state contract.

Tests pin each kwarg's documented semantics; assertions are
state-transition-contract assertions, not calculation tautologies.
"""

from __future__ import annotations

import pytest

from ...workflow import WorkflowState
from ..actions import update_auth

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# provider kwarg
# ---------------------------------------------------------------------------


def test_update_auth_provider_lowercases_value() -> None:
    state = WorkflowState()

    updated = update_auth(state, provider="CERTIFICATE")

    assert updated.auth.provider == "certificate"


def test_update_auth_provider_strips_whitespace_and_lowercases() -> None:
    state = WorkflowState()

    updated = update_auth(state, provider="  Cert  ")

    assert updated.auth.provider == "cert"


def test_update_auth_provider_stamps_configured_at() -> None:
    state = WorkflowState()
    assert state.auth.configured_at is None

    updated = update_auth(state, provider="certificate")

    assert updated.auth.configured_at is not None
    assert updated.auth.configured_at.tzinfo is not None, "stamp must be tz-aware"


# ---------------------------------------------------------------------------
# certificate_path kwarg
# ---------------------------------------------------------------------------


def test_update_auth_certificate_path_sets_value() -> None:
    state = WorkflowState()

    updated = update_auth(state, certificate_path="data/certs/operator.pem")

    assert updated.auth.certificate_path == "data/certs/operator.pem"


def test_update_auth_certificate_path_strips_surrounding_whitespace() -> None:
    state = WorkflowState()

    updated = update_auth(state, certificate_path="  data/certs/operator.pem  ")

    assert updated.auth.certificate_path == "data/certs/operator.pem"


def test_update_auth_certificate_path_empty_becomes_none() -> None:
    """Empty string → None — the helper treats `""` as "clear the
    field" so callers can explicitly unset a previously-configured
    certificate path."""
    initial = WorkflowState()
    seeded = update_auth(initial, certificate_path="data/certs/operator.pem")

    updated = update_auth(seeded, certificate_path="")

    assert updated.auth.certificate_path is None


def test_update_auth_certificate_path_stamps_configured_at() -> None:
    state = WorkflowState()
    assert state.auth.configured_at is None

    updated = update_auth(state, certificate_path="data/certs/operator.pem")

    assert updated.auth.configured_at is not None
    assert updated.auth.configured_at.tzinfo is not None, "stamp must be tz-aware"


# ---------------------------------------------------------------------------
# authenticated kwarg
# ---------------------------------------------------------------------------


def test_update_auth_authenticated_true_stamps_authenticated_at() -> None:
    state = WorkflowState()
    assert state.auth.authenticated_at is None

    updated = update_auth(state, authenticated=True)

    assert updated.auth.authenticated_at is not None
    assert updated.auth.authenticated_at.tzinfo is not None, "stamp must be tz-aware"


def test_update_auth_authenticated_false_clears_authenticated_at() -> None:
    """`authenticated=False` is the explicit logout signal — clears the
    timestamp."""
    initial = WorkflowState()
    seeded = update_auth(initial, authenticated=True)
    assert seeded.auth.authenticated_at is not None
    assert seeded.auth.authenticated_at.tzinfo is not None, "stamp must be tz-aware"

    updated = update_auth(seeded, authenticated=False)

    assert updated.auth.authenticated_at is None


# ---------------------------------------------------------------------------
# subject kwarg
# ---------------------------------------------------------------------------


def test_update_auth_subject_sets_value() -> None:
    state = WorkflowState()

    updated = update_auth(state, subject="CN=Operator")

    assert updated.auth.subject == "CN=Operator"


def test_update_auth_subject_strips_surrounding_whitespace() -> None:
    state = WorkflowState()

    updated = update_auth(state, subject="  CN=Operator  ")

    assert updated.auth.subject == "CN=Operator"


def test_update_auth_subject_empty_becomes_none() -> None:
    """Empty string → None, same semantics as certificate_path."""
    initial = WorkflowState()
    seeded = update_auth(initial, subject="CN=Operator")

    updated = update_auth(seeded, subject="")

    assert updated.auth.subject is None


# ---------------------------------------------------------------------------
# combined / pass-through behaviour
# ---------------------------------------------------------------------------


def test_update_auth_no_kwargs_leaves_auth_unchanged_but_bumps_updated_at() -> None:
    """When no kwargs are supplied the auth payload is untouched, but
    state.updated_at always advances (every call bumps the workflow's
    last-modified timestamp)."""
    state = WorkflowState()

    updated = update_auth(state)

    assert updated.auth == state.auth
    assert updated.updated_at >= state.updated_at


def test_update_auth_multiple_kwargs_combined_in_one_call() -> None:
    state = WorkflowState()

    updated = update_auth(
        state,
        provider="certificate",
        certificate_path="data/certs/operator.pem",
        authenticated=True,
        subject="CN=Operator",
    )

    assert updated.auth.provider == "certificate"
    assert updated.auth.certificate_path == "data/certs/operator.pem"
    assert updated.auth.authenticated_at is not None
    assert updated.auth.subject == "CN=Operator"
    assert updated.auth.configured_at is not None


def test_update_auth_preserves_unrelated_auth_fields_when_only_one_kwarg_supplied() -> None:
    """A single-kwarg call only touches the matching field — other
    auth fields retain whatever value they already had."""
    initial = WorkflowState()
    seeded = update_auth(
        initial,
        provider="certificate",
        certificate_path="data/certs/operator.pem",
        subject="CN=Operator",
        authenticated=True,
    )

    only_provider_changed = update_auth(seeded, provider="clave-movil")

    assert only_provider_changed.auth.provider == "clave-movil"
    assert only_provider_changed.auth.certificate_path == "data/certs/operator.pem"
    assert only_provider_changed.auth.subject == "CN=Operator"
    assert only_provider_changed.auth.authenticated_at == seeded.auth.authenticated_at
