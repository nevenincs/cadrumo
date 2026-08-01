"""Wizard auth fields agree with the canonical readiness authority.

``build_wizard_status`` used to read ``state.auth`` directly: it copied the
persisted provider selector verbatim and treated any non-null
``authenticated_at`` as a live session. Both readings are unsafe for the same
reason -- they describe what was *written* rather than what is *usable*. An
unrecognised selector was republished as though it named a real provider, and
a certificate selection whose certificate no longer exists reported "session
ready".

The canonical :func:`build_auth_readiness` fails closed on both counts and
never echoes an invalid selector. These pin the wizard to that verdict.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....tests.secure_sql import isolated_profile_storage_root
from ...state_projection import build_auth_readiness
from ...workflow import WorkflowState
from .._status import build_wizard_status

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AUTHENTICATED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _file_backed_profile_store(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _state_with_auth(provider: str | None) -> WorkflowState:
    return WorkflowState.model_validate(
        {"auth": {"provider": provider, "authenticated_at": _AUTHENTICATED_AT}},
    )


def _canonical(state: WorkflowState):
    return build_auth_readiness(
        state,
        provider_kind=None,
        provider_kind_is_authoritative=False,
        requested_provider=None,
        probe_live_backend=False,
        credential_bucket_id=None,
        certificate_credentials=None,
    )


def test_unknown_provider_is_not_reported_as_a_ready_session() -> None:
    """The audit's probe: persisted ``provider="bogus"`` with a timestamp."""
    state = _state_with_auth("bogus")

    report = build_wizard_status(state)

    assert report.login_ready is False
    assert report.auth_provider == ""


def test_unknown_provider_value_is_never_echoed_back() -> None:
    """Failing closed includes not republishing the invalid selector."""
    report = build_wizard_status(_state_with_auth("bogus"))

    assert "bogus" not in report.auth_provider
    assert "bogus" not in report.next_action


def test_a_certificate_selection_without_a_certificate_is_not_ready() -> None:
    """``authenticated_at`` alone does not make an unusable provider usable."""
    report = build_wizard_status(_state_with_auth("certificate"))

    assert report.login_ready is False


@pytest.mark.parametrize("provider", ["bogus", "certificate", "", None, "CERTIFICATE", "clave"])
def test_wizard_auth_fields_match_the_canonical_projection(provider: str | None) -> None:
    """The invariant as a relation, so the two cannot drift apart again."""
    state = _state_with_auth(provider)
    canonical = _canonical(state)

    report = build_wizard_status(state)

    assert report.auth_provider == canonical.provider, provider
    assert report.login_ready is canonical.authenticated, provider


def test_no_auth_state_still_directs_the_operator_to_configure() -> None:
    """The unconfigured path keeps its setup-specific next action."""
    report = build_wizard_status(WorkflowState())

    assert report.auth_provider == ""
    assert report.login_ready is False
