"""Tests for deny-by-default AEAT remote-state guard policy."""

from __future__ import annotations

import pytest
from pydantic import AnyUrl

from ._errors import RegistryValidationError
from ._remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
    evaluate_remote_operation,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _open_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="m303-open",
        classification="open_simulator",
        allowed_hosts=("sede.agenciatributaria.gob.es",),
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def test_remote_state_guard_allows_read_only_open_simulator_get() -> None:
    result = assert_remote_operation_allowed(
        _open_policy(),
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl("https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ZZ08.shtml"),
        ),
    )

    assert result.decision == "allowed"


def test_remote_state_guard_blocks_post_even_on_allowed_host() -> None:
    with pytest.raises(RegistryValidationError, match="remote write method"):
        assert_remote_operation_allowed(
            _open_policy(),
            RemoteOperation(
                kind="http",
                method="POST",
                url=AnyUrl("https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ZZ08.shtml"),
            ),
        )


def test_remote_state_guard_blocks_stateful_tokens_in_browser_actions() -> None:
    result = evaluate_remote_operation(
        _open_policy(),
        RemoteOperation(kind="browser_action", action="Presentar declaracion"),
    )

    assert result.decision == "blocked"
    assert "presentar" in result.reason


def test_remote_state_guard_blocks_unknown_aeat_host() -> None:
    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        assert_remote_operation_allowed(
            _open_policy(),
            RemoteOperation(
                kind="http",
                method="GET",
                url=AnyUrl("https://www2.agenciatributaria.gob.es/wlpl/some/path"),
            ),
        )


def test_remote_state_guard_allows_local_workbook_for_static_policy() -> None:
    policy = RemoteStateGuardPolicy(
        id="static-docs",
        classification="static_official_only",
        allowed_hosts=(),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )

    result = assert_remote_operation_allowed(policy, RemoteOperation(kind="local_workbook"))

    assert result.decision == "allowed"


def test_remote_state_guard_rejects_static_policy_live_http() -> None:
    policy = RemoteStateGuardPolicy(
        id="static-docs",
        classification="static_official_only",
        allowed_hosts=(),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )

    result = evaluate_remote_operation(
        policy,
        RemoteOperation(
            kind="http",
            method="GET",
            url=AnyUrl("https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro.html"),
        ),
    )

    assert result.decision == "blocked"
    assert "static_official_only" in result.reason
