"""Notifications-parser tests against real AEAT HTML captures (identity-redacted).

Fixtures under ``tests/fixtures/aeat-sede/notifications-*.html`` are
live captures (2026-04-24) with NIF and name scrubbed. Locks the
parser to the actual column shape AEAT serves.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ._notifications import (
    parse_notifications_query,
    parse_notifications_summary,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_FIXTURE_ROOT = Path(__file__).resolve().parents[6] / "tests" / "fixtures" / "aeat-sede"
_SUMMARY_URL = "https://www6.agenciatributaria.gob.es/wlpl/GNNO-JDIT/ResumenInteresados"
_QUERY_URL = "https://www6.agenciatributaria.gob.es/wlpl/GNNO-JDIT/SvInteresadosQuery?VEZ=BUSCAR1"


class TestParseNotificationsSummary:
    """Verify the unread-summary endpoint parser."""

    def test_extracts_two_rows(self) -> None:
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        snap = parse_notifications_summary(html, source_url=_SUMMARY_URL)
        # Captured day: Kent had 1 unread notification + 1 unread comunicacion.
        assert len(snap.rows) == 2

    def test_first_row_is_pending_notification(self) -> None:
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        snap = parse_notifications_summary(html, source_url=_SUMMARY_URL)
        first = snap.rows[0]
        assert first.certificado_id == "2699101808461"
        assert first.tipo == "notificacion"
        assert first.fecha_emision.isoformat() == "2026-04-20"
        assert first.mode == "read"

    def test_second_row_is_communication(self) -> None:
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        snap = parse_notifications_summary(html, source_url=_SUMMARY_URL)
        second = snap.rows[1]
        assert second.certificado_id == "2596230606502"
        assert "comunic" in second.tipo.lower() or second.tipo == "comunicacion"
        assert second.fecha_emision.isoformat() == "2025-11-24"

    def test_snapshot_carries_source_url(self) -> None:
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        snap = parse_notifications_summary(html, source_url=_SUMMARY_URL)
        assert _SUMMARY_URL in str(snap.source_url)
        assert snap.mode == "read"


class TestParseNotificationsQuery:
    """Verify the full SvInteresadosQuery results-table parser."""

    def test_extracts_pending_row(self) -> None:
        html = (_FIXTURE_ROOT / "notifications-query-results.html").read_text(encoding="utf-8")
        snap = parse_notifications_query(html, source_url=_QUERY_URL)
        # Kent's snapshot has one pending row (the notification awaiting comparecencia).
        assert len(snap.rows) >= 1
        row = snap.rows[0]
        assert row.certificado_id == "2699101808461"
        assert row.tipo == "pendiente"
        assert row.fecha_emision.isoformat() == "2026-04-20"

    def test_pending_row_has_no_leida_flag(self) -> None:
        html = (_FIXTURE_ROOT / "notifications-query-results.html").read_text(encoding="utf-8")
        snap = parse_notifications_query(html, source_url=_QUERY_URL)
        # Pending rows in the query view leave Leida blank.
        for row in snap.rows:
            if row.tipo == "pendiente":
                assert row.leida is None
                break
        else:  # pragma: no cover — at least one pending row in fixture
            pytest.fail("expected at least one pending row in the query fixture")
