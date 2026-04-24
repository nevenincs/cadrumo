"""Unit tests for :mod:`aeat.remote._status`."""

from __future__ import annotations

import logging

import pytest

from ._status import RemoteFilingStatus, classify_status

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Presentada", RemoteFilingStatus.PRESENTADA),
        ("presentada", RemoteFilingStatus.PRESENTADA),
        ("  Presentada  ", RemoteFilingStatus.PRESENTADA),
        ("En tramitacion", RemoteFilingStatus.EN_TRAMITACION),
        ("En tramitación", RemoteFilingStatus.EN_TRAMITACION),
        ("Rechazada", RemoteFilingStatus.RECHAZADA),
        ("Subsanada", RemoteFilingStatus.SUBSANADA),
        ("Complementaria", RemoteFilingStatus.COMPLEMENTARIA),
        ("Anulada", RemoteFilingStatus.ANULADA),
    ],
)
def test_classify_status_maps_known_strings(raw: str, expected: RemoteFilingStatus) -> None:
    assert classify_status(raw) is expected


def test_classify_status_falls_back_to_unknown_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="aeat.remote._status"):
        resolved = classify_status("Revolucionado", modelo="303", period="2025-1T")
    assert resolved is RemoteFilingStatus.UNKNOWN
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert warnings, "expected a warning log record when falling back to UNKNOWN"
    assert any("Revolucionado" in record.getMessage() for record in warnings)
    assert any("303" in record.getMessage() for record in warnings)
    assert any("2025-1T" in record.getMessage() for record in warnings)


def test_remote_filing_status_is_closed_enum() -> None:
    members = {member.value for member in RemoteFilingStatus}
    assert members == {
        "presentada",
        "en_tramitacion",
        "rechazada",
        "subsanada",
        "complementaria",
        "anulada",
        "unknown",
    }


def test_remote_filing_status_round_trips_via_constructor() -> None:
    for member in RemoteFilingStatus:
        assert RemoteFilingStatus(member.value) is member
