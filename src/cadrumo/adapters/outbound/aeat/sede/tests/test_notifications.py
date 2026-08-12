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
    _notifications_landing_url,
    _recorded_landing_url,
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

    def test_neutral_concept_in_communications_table_is_a_communication(self) -> None:
        """The table heading classifies summary rows that have no type cue."""
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        neutral_html = html.replace("COMUNICACIÓN", "AVISO GENERAL", 1)

        snap = parse_notifications_summary(neutral_html, source_url=_SUMMARY_URL)

        communication = next(row for row in snap.rows if row.certificado_id == "2596230606502")
        assert communication.concepto == "AVISO GENERAL"
        assert communication.tipo == "comunicacion"

    def test_snapshot_carries_source_url(self) -> None:
        """Assert the snapshot records the originating ``source_url`` and ``mode='read'``."""
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        snap = parse_notifications_summary(html, source_url=_SUMMARY_URL)
        assert _SUMMARY_URL in str(snap.source_url)
        assert snap.mode == "read"

    def test_sibling_landing_host_is_preserved_in_snapshot_and_row_provenance(self) -> None:
        """A valid AEAT dispatch host, rather than www6, is the recorded source."""
        html = (_FIXTURE_ROOT / "notifications-summary-resumen.html").read_text(encoding="utf-8")
        landed_url = f"{_AEAT.domains.www12}{_AEAT.sede_paths.notifications_summary}"
        recorded_url = _recorded_landing_url(landed_url, fallback_url=_SUMMARY_URL)

        snap = parse_notifications_summary(html, source_url=recorded_url)

        assert str(snap.source_url) == landed_url
        assert {str(row.source_url) for row in snap.rows} == {landed_url}


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


class _LandedPage:
    """Carries a landed URL, the one attribute ``_notifications_landing_url`` reads off a page."""

    def __init__(self, url: str) -> None:
        self.url = url


class TestNotificationsLandingIsRefusedWhenUnreadable:
    """An empty or otherwise unreadable landing must be refused, not silently substituted.

    ``_notifications_landing_url`` used to fall back to the originally-
    requested URL whenever ``page.url`` was empty
    (``getattr(page, "url", "") or url``), reproducing the exact fail-open
    bug ``_walker.assert_landed_url_readable`` already documents fixing: the
    one case where the navigation outcome could not be established was the
    one case that was not checked.
    """

    def test_a_readable_landing_is_returned_unchanged(self) -> None:
        landed = f"{_AEAT.domains.www12}{_AEAT.sede_paths.notifications_summary}"
        assert _notifications_landing_url(_LandedPage(landed), requested_url=_SUMMARY_URL) == landed

    @pytest.mark.parametrize("landed", ["", "about:blank"])
    def test_an_unreadable_landing_is_refused_not_substituted(self, landed: str) -> None:
        """DISCRIMINATING: reverting the fix produces the requested URL instead of a refusal."""
        page = _LandedPage(landed)
        produced: str | None = None
        try:
            produced = _notifications_landing_url(page, requested_url=_SUMMARY_URL)
        except SedeNavigationError:
            produced = None
        assert produced != _SUMMARY_URL, (
            f"FABRICATED notifications landing {produced!r} substituted for an unreadable landing {landed!r}"
        )
        assert produced is None
        with pytest.raises(SedeNavigationError):
            _notifications_landing_url(page, requested_url=_SUMMARY_URL)

    def test_the_refusal_names_the_requested_url(self) -> None:
        with pytest.raises(SedeNavigationError) as excinfo:
            _notifications_landing_url(_LandedPage(""), requested_url=_SUMMARY_URL)
        context = excinfo.value.context
        assert context is not None
        assert context["requested_url"] == _SUMMARY_URL


def _query_table(date_headers: tuple[str, str], modo_header: str) -> str:
    """Return a minimal query-results table using the supplied column labels.

    Only the header labels vary between calls; the body is identical, so a row
    that parses under one spelling and vanishes under another isolates the
    column indexer rather than anything about the data.
    """
    return f"""
    <html><body><table>
      <thead><tr>
        <th>Nº Certificado</th><th>Concepto</th><th>Tipo</th>
        <th>Titular</th><th>Destinatario</th>
        <th>{date_headers[0]}</th><th>{date_headers[1]}</th><th>{modo_header}</th>
      </tr></thead>
      <tbody><tr>
        <td>2699101808461</td><td>Requerimiento</td><td>Notificación</td>
        <td>X0000000Z TITULAR PRUEBA</td><td>X0000000Z TITULAR PRUEBA</td>
        <td>01-07-2026</td><td>05-07-2026</td><td>Comparecencia electrónica</td>
      </tr></tbody>
    </table></body></html>
    """


class TestQueryColumnLabelsAcrossBothSedeSpellings:
    """AEAT labels these columns differently on its two notification surfaces.

    The summary renders "Fecha de emisión"; the query surface renders "Fecha
    emisión", with no article. The indexer matched only the "de" spelling, and
    because an unresolved ``fecha_emision`` makes ``_row_from_cells`` classify
    the row as unusable, the mismatch did not drop a FIELD -- it dropped every
    ROW. ``notifications pull`` reported a clean zero against a populated AEAT
    inbox: no error, no warning, no partial row.

    The bundled query fixture still carries the "de" spelling and a ``Leída``
    column the live surface no longer serves, which is why the existing suite
    stayed green while production returned nothing. These cases pin the labels
    directly so a fixture that lags the sede cannot hide the same defect again.
    """

    def test_the_de_less_spelling_the_query_surface_serves_yields_a_row(self) -> None:
        """The live query spelling. This is the case that was returning zero."""
        html = _query_table(("Fecha emisión", "Fecha notificación"), "Modo notificación")

        snapshot = parse_notifications_query(html, source_url=_QUERY_URL)

        assert len(snapshot.rows) == 1, (
            "the query surface's own column spelling parsed to zero rows; an unindexed date "
            "column silently drops every row rather than leaving a field empty"
        )
        assert snapshot.rows[0].fecha_emision.isoformat() == "2026-07-01"
        assert snapshot.rows[0].fecha_notificacion is not None

    def test_the_de_spelling_the_summary_surface_serves_still_yields_a_row(self) -> None:
        """The other spelling must keep working; the fix widens, never swaps."""
        html = _query_table(("Fecha de emisión", "Fecha de notificación"), "Modo de notificación")

        snapshot = parse_notifications_query(html, source_url=_QUERY_URL)

        assert len(snapshot.rows) == 1
        assert snapshot.rows[0].fecha_emision.isoformat() == "2026-07-01"

    def test_modo_still_claims_its_column_rather_than_the_notificacion_date(self) -> None:
        """Anti-regression on the matcher ORDER, not just its patterns.

        "Modo notificación" contains the same ``notificaci`` stem the date branch
        now keys on. If the date branch were ever reordered above ``modo``, it
        would capture the modo column and the notification date would go
        unindexed -- a silent field loss that no row count would reveal.
        """
        html = _query_table(("Fecha emisión", "Fecha notificación"), "Modo notificación")

        row = parse_notifications_query(html, source_url=_QUERY_URL).rows[0]

        assert row.modo_notificacion == "Comparecencia electrónica"
        assert row.fecha_notificacion is not None
        assert row.fecha_notificacion.isoformat() == "2026-07-05"

    def test_an_unlabelled_date_column_still_drops_the_row(self) -> None:
        """ANTI-TAUTOLOGY: prove the tests above measure the indexer.

        If the parser had begun accepting rows regardless of whether the date
        column resolved, every assertion above would pass while proving nothing.
        A header the indexer genuinely cannot key on must still produce zero
        rows -- that is the behaviour whose trigger was too narrow, not
        behaviour that was wrong.
        """
        html = _query_table(("Expedida el", "Entregada el"), "Modo notificación")

        snapshot = parse_notifications_query(html, source_url=_QUERY_URL)

        assert len(snapshot.rows) == 0, (
            "a row with no resolvable emission-date column parsed anyway, so the cases above "
            "would pass even with the column indexer removed"
        )
