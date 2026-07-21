"""Notifications-parser tests against real AEAT HTML captures (identity-redacted).

Fixtures under ``src/cadrumo/tests/fixtures/aeat-sede/notifications-*.html``
are live captures with NIF and name scrubbed. Pins the parser to the
actual column shape AEAT serves.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from ......core.config import Settings
from ......tests import FIXTURES_DIR
from ...browser.tests.real_http_boundary import opened_http_boundary, real_browser_factory
from .._errors import SedeNavigationError
from .._notifications import (
    _RESUMEN_URL,
    _navigate_and_parse,
    parse_notifications_query,
    parse_notifications_summary,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"
_INTERSTITIAL = FIXTURES_DIR / "site_health" / "mantenimiento" / "interstitial.html"
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


class TestNavigateAndParseLandingGuard:
    """Verify the driver distinguishes a genuine empty inbox from a bad landing."""

    @pytest.mark.asyncio
    async def test_returns_rows_on_real_capture_with_warmup(self) -> None:
        """A real populated capture parses to its rows; warm-up precedes the primary goto."""
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        async with opened_http_boundary() as boundary:
            boundary.configure_html(html)
            snap = await _navigate_and_parse(
                {},
                url=_SUMMARY_URL,
                parser=parse_notifications_summary,
                settings=Settings(),
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="notifications-populated",
                ),
            )
            assert boundary.requested_urls.index(_RESUMEN_URL) < boundary.requested_urls.index(_SUMMARY_URL)
        assert len(snap.rows) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_snapshot_on_genuine_empty_but_valid_page(self) -> None:
        """Marker PRESENT + zero rows is a legitimate empty inbox — must NOT raise.

        The heading text is verbatim from the real query capture; a genuinely
        empty page still renders it, so the driver returns an empty snapshot.
        """
        empty_html = (
            "<html><head><title>Consulta de notificaciones y comunicaciones</title></head>"
            "<body><h1>Consulta de notificaciones y comunicaciones</h1>"
            "<p>No se han encontrado resultados.</p></body></html>"
        )
        async with opened_http_boundary() as boundary:
            boundary.configure_html(empty_html)
            snap = await _navigate_and_parse(
                {},
                url=_QUERY_URL,
                parser=parse_notifications_query,
                settings=Settings(),
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="notifications-empty",
                ),
            )
        assert snap.rows == ()
        assert snap.mode == "read"

    @pytest.mark.asyncio
    async def test_raises_instructive_diagnostic_on_marker_absent_landing(self) -> None:
        """Marker ABSENT + zero rows (real maintenance interstitial served in place) raises."""
        interstitial = _INTERSTITIAL.read_text(encoding="utf-8")
        async with opened_http_boundary() as boundary:
            boundary.configure_html(interstitial)
            with pytest.raises(SedeNavigationError) as exc_info:
                await _navigate_and_parse(
                    {},
                    url=_QUERY_URL,
                    parser=parse_notifications_query,
                    settings=Settings(),
                    browser_session_factory=real_browser_factory(
                        boundary=boundary,
                        profile_name="notifications-maintenance",
                    ),
                )
        context = exc_info.value.context or {}
        assert context["marker_present"] is False
        assert context["row_count"] == 0
        assert context["landing_path"] == urlsplit(_QUERY_URL).path
