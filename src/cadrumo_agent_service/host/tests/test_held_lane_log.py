"""Every lane the picker serves as not selectable has its cause in the service log."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from cadrumo.tests.log_records import delivered_records

from ...service_support import HeldLaneLog

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _lane(*, selectable: bool, authentication: str, catalog: str = "available") -> dict[str, Any]:
    return {
        "provider_id": "codex_cli",
        "transport": "codex_app_server",
        "health": {
            "configured": "available",
            "transport": "available",
            "authentication": authentication,
            "catalog": catalog,
            "admission": "admitted",
            "selectable": selectable,
            "reasons": ["provider sign-in required"],
        },
        "catalog": {"state": {"status": "stale"}},
    }


def _held_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    records = delivered_records(caplog, "cadrumo_agent_service.service")
    return [record.getMessage() for record in records if "agent picker lane" in record.getMessage()]


def test_a_held_lane_is_logged_with_its_axes_once_per_cause(caplog: pytest.LogCaptureFixture) -> None:
    log = HeldLaneLog()
    with caplog.at_level(logging.INFO):
        log.observe({"providers": [_lane(selectable=False, authentication="unknown")]})
        log.observe({"providers": [_lane(selectable=False, authentication="unknown")]})
        log.observe({"providers": [_lane(selectable=False, authentication="unauthenticated")]})
        log.observe({"providers": [_lane(selectable=True, authentication="authenticated")]})
        log.observe({"providers": [_lane(selectable=True, authentication="authenticated")]})

    lines = _held_lines(caplog)
    assert lines == [
        "agent picker lane held provider=codex_cli transport=codex_app_server configured=available "
        "transport_health=available authentication=unknown catalog=available admission=admitted "
        "catalog_state=stale reasons=provider sign-in required",
        "agent picker lane held provider=codex_cli transport=codex_app_server configured=available "
        "transport_health=available authentication=unauthenticated catalog=available admission=admitted "
        "catalog_state=stale reasons=provider sign-in required",
        "agent picker lane selectable provider=codex_cli transport=codex_app_server",
    ]


def test_a_lane_selectable_from_the_start_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        HeldLaneLog().observe({"providers": [_lane(selectable=True, authentication="authenticated")]})

    assert _held_lines(caplog) == []
