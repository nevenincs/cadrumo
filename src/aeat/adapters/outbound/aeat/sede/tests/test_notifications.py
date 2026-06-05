"""Notifications-parser tests against real AEAT HTML captures (identity-redacted).

Fixtures under ``src/aeat/tests/fixtures/aeat-sede/notifications-*.html``
are live captures with NIF and name scrubbed. Pins the parser to the
actual column shape AEAT serves.
"""

from __future__ import annotations

import pytest

from ......core.config import Settings
from ......tests import FIXTURES_DIR
from .._notifications import (
    parse_notifications_query,
    parse_notifications_summary,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"
_AEAT = Settings.external_constants().aeat
_SUMMARY_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.notifications_summary}"
_QUERY_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.notifications_query}"


class TestParseNotificationsSummary:
    """Verify :func:`parse_notifications_summary` against the unread-summary endpoint."""

    def test_extracts_two_rows(self) -> None:
        """Assert the captured fixture yields exactly two rows."""
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        snap = parse_notifications_summary(html, source_url=_SUMMARY_URL)
        # Captured day: 1 unread notification + 1 unread comunicacion.
        assert len(snap.rows) == 2

    def test_first_row_is_pending_notification(self) -> None:
        """Assert the first parsed row is the pending notification with the captured id."""
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        snap = parse_notifications_summary(html, source_url=_SUMMARY_URL)
        first = snap.rows[0]
        assert first.certificado_id == "2699101808461"
        assert first.tipo == "notificacion"
        assert first.fecha_emision.isoformat() == "2026-04-20"
        assert first.mode == "read"

    def test_second_row_is_communication(self) -> None:
        """Assert the second parsed row is the comunicacion with the captured id."""
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        snap = parse_notifications_summary(html, source_url=_SUMMARY_URL)
        second = snap.rows[1]
        assert second.certificado_id == "2596230606502"
        assert "comunic" in second.tipo.lower() or second.tipo == "comunicacion"
        assert second.fecha_emision.isoformat() == "2025-11-24"

    def test_snapshot_carries_source_url(self) -> None:
        """Assert the snapshot records the originating ``source_url`` and ``mode='read'``."""
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        snap = parse_notifications_summary(html, source_url=_SUMMARY_URL)
        assert _SUMMARY_URL in str(snap.source_url)
        assert snap.mode == "read"


class TestParseNotificationsQuery:
    """Verify :func:`parse_notifications_query` against the full ``SvInteresadosQuery`` results."""

    def test_extracts_pending_row(self) -> None:
        """Assert at least one ``pendiente`` row is present and exposes its emission date."""
        html = (_FIXTURE_ROOT / "notifications-query-results.html").read_text(encoding="utf-8")
        snap = parse_notifications_query(html, source_url=_QUERY_URL)
        # The captured snapshot has one pending row (the notification awaiting comparecencia).
        assert len(snap.rows) >= 1
        row = snap.rows[0]
        assert row.certificado_id == "2699101808461"
        assert row.tipo == "pendiente"
        assert row.fecha_emision.isoformat() == "2026-04-20"

    def test_pending_row_has_no_leida_flag(self) -> None:
        """Assert ``pendiente`` rows leave ``leida`` as ``None`` in the query view."""
        html = (_FIXTURE_ROOT / "notifications-query-results.html").read_text(encoding="utf-8")
        snap = parse_notifications_query(html, source_url=_QUERY_URL)
        # Pending rows in the query view leave Leida blank.
        for row in snap.rows:
            if row.tipo == "pendiente":
                assert row.leida is None
                break
        else:  # pragma: no cover — at least one pending row in fixture
            pytest.fail("expected at least one pending row in the query fixture")
