"""An exact lease is admitted only while live, undenied and, for API keys, granted."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from ...user_profile.access_contracts import (
    AccessDenialCode,
    AccessScope,
    AuthorityState,
    Availability,
    ProfileAccessStatus,
)
from ..profile_access import status_admits_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AT = datetime(2026, 6, 1, 12, tzinfo=UTC)
_PROFILE = UUID(int=1)
_SESSION = UUID(int=2)


def _status(**overrides: object) -> ProfileAccessStatus:
    fields: dict[str, object] = {
        "connected": True,
        "credential_authenticated": True,
        "profile_id": _PROFILE,
        "session_id": _SESSION,
        "session_expires_at": _AT + timedelta(minutes=5),
        "grant_state": None,
        "grant_expires_at": None,
        "grant_valid": False,
        "profile_bound": True,
        "storage": Availability.AVAILABLE,
        "automation_custody": Availability.NOT_REQUIRED,
        "published_authority": Availability.AVAILABLE,
        "provider": Availability.NOT_REQUIRED,
        "effective_scope": AccessScope(
            operations=frozenset(),
            actions=frozenset(),
            disclosures=frozenset(),
            periods=frozenset(),
            allow_period_independent=False,
            allow_delegation=False,
        ),
        "denial": None,
    }
    fields.update(overrides)
    return ProfileAccessStatus.model_validate(fields)


def _granted(**overrides: object) -> ProfileAccessStatus:
    granted: dict[str, object] = {
        "grant_state": AuthorityState.ACTIVE,
        "grant_expires_at": _AT + timedelta(days=1),
        "grant_valid": True,
    }
    return _status(**{**granted, **overrides})


def _admits(status: ProfileAccessStatus, *, grant: bool) -> bool:
    return status_admits_session(
        status, profile_id=_PROFILE, session_id=_SESSION, at=_AT, requires_automation_grant=grant
    )


def test_human_lease_without_a_grant_is_admitted() -> None:
    assert _admits(_status(), grant=False)


def test_api_key_lease_requires_an_active_unexpired_grant() -> None:
    assert _admits(_granted(), grant=True)
    assert not _admits(_status(), grant=True)
    assert not _admits(_granted(grant_valid=False), grant=True)
    assert not _admits(_granted(grant_state=AuthorityState.SUSPENDED), grant=True)
    assert not _admits(_granted(grant_expires_at=_AT), grant=True)
    assert not _admits(_granted(grant_expires_at=None), grant=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"connected": False},
        {"credential_authenticated": False},
        {"profile_bound": False},
        {"profile_id": uuid4()},
        {"session_id": uuid4()},
        {"session_id": None},
        {"session_expires_at": None},
        {"session_expires_at": _AT},
        {"denial": AccessDenialCode.SESSION_EXPIRED},
    ],
)
@pytest.mark.parametrize("grant", [False, True])
def test_any_failed_lease_axis_refuses_admission(overrides: dict[str, object], grant: bool) -> None:
    assert not _admits(_granted(**overrides), grant=grant)
