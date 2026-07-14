"""Storage-session regression coverage for operator auth services."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage import has_active_bucket_session
from ....application.wizard import WIZARD_FLOWS
from ....domain.contribuyente import required_profile_keys
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile import (
    profile_create_storage_span,
    profile_storage_session,
    register_minimal_profile,
)
from ...workflow import workflow_state_repository
from .._operator import clear_operator_auth, configure_operator_auth

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


def test_clear_operator_auth_reopens_profile_storage_session_when_pointer_is_active(
    tmp_path: Path,
) -> None:
    """Operator auth clear must work after profile creation closes its storage span.

    The active-profile pointer can remain selected after the per-process
    master-key session is closed. In that production-shaped state,
    workflow-state reads and writes must be performed through the
    operator auth service's own profile storage session.
    """

    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert WIZARD_FLOWS
        assert required_profile_keys()
        with profile_create_storage_span(_PROFILE_ID):
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID))
            configure_operator_auth("certificate")

        assert has_active_bucket_session() is False

        result = clear_operator_auth(provider="certificate")

        assert result.cleared_workflow_state is True
        assert has_active_bucket_session() is False
        with profile_storage_session(_PROFILE_ID):
            state = workflow_state_repository().load()
        assert state.auth.provider is None


def _setup_certificate_profile() -> None:
    """Register a minimal profile and configure the certificate provider.

    The caller holds the open :func:`isolated_profile_storage_root`.
    """
    assert WIZARD_FLOWS
    assert required_profile_keys()
    with profile_create_storage_span(_PROFILE_ID):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID))
        configure_operator_auth("certificate")


def test_clear_operator_auth_sessions_mode_requires_no_provider(tmp_path: Path) -> None:
    """``auth clear --sessions`` sweeps every session-bearing provider with no ``--provider``.

    Regression for the spurious "unknown provider" refusal: the provider-independent
    ``--sessions`` mode must not require ``--provider``. It iterates only the
    providers that persist a session, so a session-less provider (Cl@ve
    Permanente) no longer raises ``KeyError`` on the way through.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _setup_certificate_profile()

        result = clear_operator_auth(sessions=True)

        assert result.cleared_workflow_state is True
        assert result.removed_sessions == 0  # no live browser session is persisted in this fixture


def test_clear_operator_auth_locks_mode_requires_no_provider(tmp_path: Path) -> None:
    """``auth clear --locks`` clears acquisition-lock state without a ``--provider``."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _setup_certificate_profile()

        result = clear_operator_auth(locks=True)

        assert result.cleared_workflow_state is True
        assert result.cleared_locks == 0  # no acquisition lock is held in this fixture


def test_clear_operator_auth_all_mode_requires_no_provider(tmp_path: Path) -> None:
    """``auth clear --all`` clears every provider's session and lock state at once."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _setup_certificate_profile()

        result = clear_operator_auth(all_providers=True)

        assert result.cleared_workflow_state is True
        assert result.removed_sessions == 0
        assert result.cleared_locks == 0


def test_clear_operator_auth_unknown_provider_still_refuses(tmp_path: Path) -> None:
    """A genuinely-unknown ``--provider`` still refuses (the instructive-refusal path is preserved).

    The fix removed the SPURIOUS ``KeyError`` from sweeping a session-less provider,
    but the CLI's unknown-provider refusal rides a real ``KeyError`` from the
    provider catalogue; an unknown provider id must still raise it.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _setup_certificate_profile()

        with pytest.raises(KeyError):
            clear_operator_auth(provider="not-a-real-provider")
