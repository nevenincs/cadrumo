"""Censal-consulta parser and no-write tests against a real AEAT HTML capture.

``src/cadrumo/tests/fixtures/aeat-sede/censal-datos-mdcacceso.html`` is a
live capture of the authenticated *Mis Datos Censales* consulta page with
every personal value replaced by synthetic data and the markup left
structurally intact, so the parser is pinned to the shape AEAT serves.

The no-write proof is deliberately grounded in that same capture: the
page really does carry the *Cambio de Domicilio* controls and the M036
filing link, so the guard is shown to refuse the write paths that exist
rather than a hypothetical one.
"""

from __future__ import annotations

import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import override
from urllib.parse import quote, urlsplit

import pytest
from playwright.async_api import Route
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ......application.user_profile.censal_observation import CensalObservation
from ......core.config import Settings
from ......core.period import Period
from ......tests.aeat_literal_fixtures import (
    CENSAL_WRITE_SURFACE_PATH_CANARIES,
    CLAVE_AUTHORIZATION_SELECTOR_HTML_FIXTURE,
    OTHER_APPLICATION_START_PATH_CANARY,
    PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE,
    aeat_url,
)
from ......tests.inventory import FIXTURES_DIR
from ...browser.tests.real_http_boundary import LocalHttpBoundary, open_real_browser_session, real_browser_factory
from ..censal_datos import (
    _FORBIDDEN_LANDING_MARKERS,
    _assert_read_http,
    _assert_read_landing,
    _censal_landing_url,
    censal_datos_url,
    forbidden_censal_landing_marker,
    parse_censal_datos,
)
from ..censal_datos import _navigate_and_parse as read_censal
from ..errors import SedeFailureMode, SedeNavigationError, SedeParseError
from ..iva_compensation_wallet import fetch_iva_compensation_wallet
from .censal_consultation_fixtures import consultation_documents
from .declarations_register_test_support import offline_aeat_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_FIXTURE = FIXTURES_DIR / "aeat-sede" / "censal-datos-mdcacceso.html"
_AEAT = Settings.external_constants().aeat
_CENSAL_URL = f"{_AEAT.domains.sede}{_AEAT.sede_paths.censal_datos}"

# The write surfaces the captured consulta page actually reaches. The two
# domicilio targets are relative in the page's own scripts, so they resolve
# under the consulta's own prefix.
_REAL_WRITE_LANDINGS = tuple(aeat_url("www6", path) for path in CENSAL_WRITE_SURFACE_PATH_CANARIES)


def _fixture_html() -> str:
    """Return the captured censal consulta page."""
    return _FIXTURE.read_text(encoding="utf-8")


def _parsed() -> CensalObservation:
    """Parse the captured page."""
    return parse_censal_datos(_fixture_html(), source_url=_CENSAL_URL)


class TestParseCensalDatos:
    """Pin the parser to the real censal consulta shape."""

    def test_identity_group_is_fully_extracted(self) -> None:
        """Every identity label AEAT renders reaches the typed record."""
        identity = _parsed().identity

        assert identity.nif == "Y0000001Z"
        assert identity.apellidos_y_nombre == "APELLIDO APELLIDO NOMBRE"
        assert identity.administracion_domicilio_fiscal == "28600 - OFICINA EJEMPLO"
        assert identity.lugar_nacimiento == "CIUDAD EJEMPLO Pais: PAIS EJEMPLO"
        assert identity.fecha_nacimiento == date(1980, 1, 1)
        assert identity.sexo == "Mujer"
        assert identity.nacionalidad == "PAIS EJEMPLO"
        assert identity.estado_civil == "No consta"

    def test_blank_cell_is_none_not_empty_string(self) -> None:
        """AEAT renders an unrecorded value as ``&nbsp;``, which is absence."""
        assert _parsed().identity.pasaporte is None

    def test_notification_flags_are_typed_booleans(self) -> None:
        """The two ``Sí``/``No`` cells become booleans, not raw strings."""
        identity = _parsed().identity

        assert identity.obligado_notificaciones_electronicas is False
        assert identity.suscrito_voluntariamente_notificaciones_electronicas is False

    def test_fiscal_address_spans_every_sub_table(self) -> None:
        """The fiscal address is split across six tables; all of them land."""
        fiscal = _parsed().domicilio_fiscal

        # First sub-table.
        assert fiscal.tipo_via == "CALLE"
        assert fiscal.nombre_via == "NOMBRE VIA EJEMPLO"
        assert fiscal.tipo_numero == "NUM"
        assert fiscal.numero_casa == "1"
        # Second sub-table — the columnar shape with mostly-blank cells.
        assert fiscal.planta == "7"
        assert fiscal.puerta == "9"
        assert fiscal.bloque is None
        # Fourth and fifth sub-tables.
        assert fiscal.referencia_catastral == "0000001AA0000A0001AA"
        assert fiscal.indicador_referencia_catastral is not None
        assert fiscal.codigo_postal == "28001"
        assert fiscal.municipio == "28079 - MADRID"
        assert fiscal.provincia == "MADRID"

    def test_notification_address_is_parsed_separately(self) -> None:
        """The notification group is its own record, not merged into the fiscal one."""
        result = _parsed()

        assert result.domicilio_notificacion.codigo_postal == "28001"
        assert result.domicilio_notificacion.provincia == "MADRID"
        # Cadastral data renders only on the fiscal address; the
        # notification group must not inherit it.
        assert result.domicilio_notificacion.referencia_catastral is None
        assert result.domicilio_fiscal.referencia_catastral is not None

    def test_result_is_a_read_mode_record(self) -> None:
        """The boundary-crossing record declares the structural read marker."""
        result = _parsed()

        assert result.mode == "read"
        assert str(result.source_url).startswith(_AEAT.domains.sede)

    def test_every_rendered_label_maps_to_a_field(self) -> None:
        """No AEAT label on the captured page is silently dropped.

        Guards against AEAT adding a censal field that the parser quietly
        ignores, which would under-report the taxpayer's censal state.
        """
        from ..._html import parse_html
        from ..censal_datos import (
            _DOMICILIO_LABELS,
            _IDENTITY_LABELS,
            _fold,
            _section_of,
        )

        soup = parse_html(_fixture_html())
        unmapped: list[str] = []
        for table in soup.find_all("table"):
            section = _section_of(table)
            if section is None:
                continue
            known = _IDENTITY_LABELS if section == "datos identificativos del contribuyente" else _DOMICILIO_LABELS
            for bold in table.find_all("b"):
                label = bold.get_text(" ", strip=True)
                if label and _fold(label) not in known:
                    unmapped.append(label)

        assert unmapped == []

    def test_page_without_a_censal_table_is_refused(self) -> None:
        """A landing carrying no censal table is a shape change, not an empty record."""
        with pytest.raises(SedeParseError):
            parse_censal_datos("<html><body><p>Mantenimiento</p></body></html>", source_url=_CENSAL_URL)


class TestNoWriteSurface:
    """Prove the reader cannot reach a censal modification surface."""

    def test_captured_page_really_carries_write_controls(self) -> None:
        """The hazard is real: the consulta page reaches modification paths.

        Without this the landing guard below would be guarding nothing, and
        the whole no-write proof would be vacuous.
        """
        html = _fixture_html()

        assert "ModifDomiDual" in html
        assert "ModifDomiNotif" in html
        assert "Cambio de Domicilio Fiscal" in html
        assert "Otras Modificaciones Censales" in html

    def test_real_write_paths_do_not_contain_the_token_an_earlier_draft_forbade(self) -> None:
        """``MOD036`` is absent from every real write path.

        This is why the guard keys on the landing path rather than that
        token: a check for ``MOD036`` would pass while the reader sat on
        the modification page.
        """
        for landing in _REAL_WRITE_LANDINGS:
            assert "MOD036" not in landing.upper().replace("-", "")

    @pytest.mark.parametrize("landing", _REAL_WRITE_LANDINGS)
    def test_landing_guard_refuses_every_real_write_path(self, landing: str) -> None:
        """The runtime guard fails closed on each write surface the page reaches."""
        with pytest.raises(SedeNavigationError) as excinfo:
            _assert_read_landing(landing)

        assert excinfo.value.failure_mode == "live_navigation_failed"

    @pytest.mark.parametrize("marker", _FORBIDDEN_LANDING_MARKERS)
    def test_every_declared_marker_is_load_bearing(self, marker: str) -> None:
        """Each declared marker refuses on its own, so none is dead weight."""
        with pytest.raises(SedeNavigationError):
            _assert_read_landing(f"{_CENSAL_URL}{marker}")

    @pytest.mark.parametrize("code", ["G322", "G313", "G323", "G414"])
    def test_landing_guard_refuses_every_procedure_launcher(self, code: str) -> None:
        """The launcher marker is a path prefix, so no procedure code escapes it.

        The consulta page links *Otras Modificaciones Censales* at one of
        these, and a code-literal marker would catch that one door while
        leaving its siblings open — the same defect as the ``MOD036`` token
        this guard replaced.
        """
        launcher = f"{_AEAT.domains.sede}{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}{code}.shtml"

        assert forbidden_censal_landing_marker(launcher) is not None
        with pytest.raises(SedeNavigationError):
            _assert_read_landing(launcher)

    def test_declared_markers_carry_no_empty_string(self) -> None:
        """An empty marker would match every landing and refuse the read itself."""
        assert _FORBIDDEN_LANDING_MARKERS
        assert all(marker.strip() for marker in _FORBIDDEN_LANDING_MARKERS)

    def test_marker_authority_agrees_with_the_raising_guard(self) -> None:
        """The exported marker lookup is the guard's own rule, not a second copy.

        Conformance gates test through this predicate, so a divergence
        would let them pass while the reader refused differently.
        """
        for landing in _REAL_WRITE_LANDINGS:
            assert forbidden_censal_landing_marker(landing) is not None
        safe = censal_datos_url("Y0000001Z", origin=_AEAT.domains.sede)
        assert forbidden_censal_landing_marker(safe) is None

    def test_landing_guard_admits_the_consulta_itself(self) -> None:
        """The guard is not a blanket refusal — the read path still passes.

        Pairs with the refusal cases above: a guard that refused everything
        would make those assertions meaningless.
        """
        _assert_read_landing(censal_datos_url("Y0000001Z", origin=_AEAT.domains.sede))

    def test_read_guard_refuses_a_write_method(self) -> None:
        """No censal navigation may use a mutating HTTP method."""
        from ......domain.calculations.registry.errors import RegistryValidationError

        with pytest.raises(RegistryValidationError):
            _assert_read_http("POST", _CENSAL_URL)

    def test_read_guard_refuses_an_off_aeat_host(self) -> None:
        """A redirect off the AEAT apex fails closed."""
        from ......domain.calculations.registry.errors import RegistryValidationError

        with pytest.raises(RegistryValidationError):
            _assert_read_http("GET", f"https://example.invalid{_AEAT.sede_paths.censal_datos}")

    @pytest.mark.parametrize("origin", ["www1", "www2", "www6", "www12"])
    def test_read_guard_admits_every_numbered_dispatch_host(self, origin: str) -> None:
        """AEAT may redirect a session across its ``www{n}`` pool, so every number is admitted."""
        _assert_read_http("GET", aeat_url(origin, _AEAT.sede_paths.censal_datos))

    def test_url_builder_requires_an_explicit_origin(self) -> None:
        """No caller may build a censal URL against an assumed host.

        The origin once defaulted to the unnumbered sede origin, which let a
        caller address a host that is not known to serve this route while
        believing it was the reader's own address.
        """

        origin = inspect.signature(censal_datos_url).parameters["origin"]

        assert origin.default is inspect.Parameter.empty

    def test_module_exposes_no_submitting_operation(self) -> None:
        """The public surface offers navigation and parsing only."""
        from .. import censal_datos

        forbidden = ("submit", "fill", "click", "press", "modif", "post")
        offenders = [name for name in censal_datos.__all__ if any(token in name.casefold() for token in forbidden)]

        assert offenders == []


class _LandedPage:
    """Carries a landed URL, the one attribute ``_censal_landing_url`` reads off a page."""

    def __init__(self, url: str) -> None:
        self.url = url


class TestCensalLandingIsRefusedWhenUnreadable:
    """An empty or otherwise unreadable landing must be refused, not silently substituted.

    ``_censal_landing_url`` used to fall back to the originally-requested
    URL whenever ``page.url`` was empty (``getattr(page, "url", "") or url``),
    reproducing the exact fail-open bug ``_walker.assert_landed_url_readable``
    already documents fixing: the one case where the navigation outcome
    could not be established was the one case that was not checked.
    """

    def test_a_readable_landing_is_returned_unchanged(self) -> None:
        landed = f"{_AEAT.domains.www12}{_AEAT.sede_paths.censal_datos}"
        assert _censal_landing_url(_LandedPage(landed), requested_url=_CENSAL_URL) == landed

    @pytest.mark.parametrize("landed", ["", "about:blank"])
    def test_an_unreadable_landing_is_refused_not_substituted(self, landed: str) -> None:
        """DISCRIMINATING: reverting the fix produces the requested URL instead of a refusal."""
        page = _LandedPage(landed)
        produced: str | None = None
        try:
            produced = _censal_landing_url(page, requested_url=_CENSAL_URL)
        except SedeNavigationError:
            produced = None
        assert produced != _CENSAL_URL, (
            f"FABRICATED censal landing {produced!r} substituted for an unreadable landing {landed!r}"
        )
        assert produced is None
        with pytest.raises(SedeNavigationError):
            _censal_landing_url(page, requested_url=_CENSAL_URL)

    def test_the_refusal_names_the_requested_url(self) -> None:
        with pytest.raises(SedeNavigationError) as excinfo:
            _censal_landing_url(_LandedPage(""), requested_url=_CENSAL_URL)
        context = excinfo.value.context
        assert context is not None
        assert context["requested_url"] == _CENSAL_URL


# ── Direct authenticated entry, through a real bundled chromium ────────────
#
# The production BrowserSession runs against the credential-free real HTTP
# boundary. Redirects are real HTTP redirects the browser follows through the
# boundary's tunnel; non-document requests are refused so each test serves
# exactly the documents it names. The consulta is the committed capture; the
# selector and dialog pages are synthetic, carrying only what is inspected.

_TAXPAYER = "Y0000001Z"
_SELECTOR_URL = _AEAT.clave_movil.selector_access_url_template.format(
    target=quote(_AEAT.sede_paths.censal_datos, safe=""),
)
# SYNTHETIC: the access selector as an authenticated session sees it. The
# Cl@ve Movil authorize control is in the DOM but not actionable, which is
# what the live capture recorded: the selector rendered and the reader's
# click ran out its timeout with no further navigation.
_AUTHENTICATED_SELECTOR_HTML = CLAVE_AUTHORIZATION_SELECTOR_HTML_FIXTURE
_OTHER_HTML = "<html><head><title>Agencia Tributaria</title></head><body><p>Servicio</p></body></html>"


@dataclass(frozen=True, slots=True)
class _Reply:
    html: str = _OTHER_HTML
    redirect_to: str | None = None


class _SedeDocuments(LocalHttpBoundary):
    """The real HTTP boundary answering each document by its URL, one at a time."""

    def __init__(self, respond: Callable[[str], _Reply]) -> None:
        super().__init__()
        self._respond = respond
        self.documents: list[str] = []

    def _reply_for(self, url: str) -> _Reply:
        reply = self._respond(url)
        self.documents.append(url)
        self.response_html = reply.html
        return reply

    @override
    def record_request(self, requested_url: str) -> str:
        self._reply_for(requested_url)
        return "/success"

    @override
    async def route(self, route: Route) -> None:
        if route.request.resource_type != "document":
            await route.abort()
            return
        reply = self._reply_for(route.request.url)
        if reply.redirect_to is not None:
            await route.fulfill(status=302, headers={"Location": reply.redirect_to})
            return
        response = await route.fetch(url=f"{self.proxy_url}/success", max_redirects=0)
        await route.fulfill(response=response)


def _bouncing_to(location: str, landing_html: str) -> Callable[[str], _Reply]:
    def respond(url: str) -> _Reply:
        if urlsplit(url).path == _AEAT.sede_paths.censal_datos:
            return _Reply(redirect_to=location)
        return _Reply(html=landing_html)

    return respond


async def _read(boundary: _SedeDocuments, profile: str) -> CensalObservation:
    return await read_censal(
        {},
        taxpayer_nif=_TAXPAYER,
        settings=Settings(),
        browser_session_factory=real_browser_factory(boundary=boundary, profile_name=profile),
    )


class TestDirectAuthenticatedEntry:
    """The consulta is requested directly with the stored session; the selector is never driven."""

    @pytest.mark.asyncio
    async def test_direct_entry_reads_the_consulta_without_the_selector(self) -> None:
        documents = consultation_documents(_fixture_html())

        def respond(url: str) -> _Reply:
            path = urlsplit(url).path
            if path == _AEAT.sede_paths.censal_actividades_entry:
                return _Reply(redirect_to=f"{_AEAT.domains.www6}{_AEAT.sede_paths.censal_actividades}")
            return _Reply(html=documents.get(path, _OTHER_HTML))

        boundary = _SedeDocuments(respond)
        try:
            observation = await _read(boundary, "censal-direct-entry")
        finally:
            boundary.close()

        assert observation.identity.nif is not None
        assert {item.kind for item in observation.consultations} == {
            "actividades",
            "situacion_tributaria",
            "obligaciones",
        }
        assert urlsplit(boundary.documents[0]).path == _AEAT.sede_paths.censal_datos
        assert all(urlsplit(url).path != urlsplit(_SELECTOR_URL).path for url in boundary.documents)
        assert urlsplit(boundary.documents[0]).netloc == urlsplit(_AEAT.domains.www6).netloc

    @pytest.mark.asyncio
    async def test_consultation_control_cannot_dispatch_to_a_write_route(self) -> None:
        documents = consultation_documents(_fixture_html())
        write_url = _REAL_WRITE_LANDINGS[0]
        documents[_AEAT.sede_paths.censal_datos] = documents[_AEAT.sede_paths.censal_datos].replace(
            _AEAT.sede_paths.censal_actividades_entry, urlsplit(write_url).path
        )
        boundary = _SedeDocuments(lambda url: _Reply(html=documents.get(urlsplit(url).path, _OTHER_HTML)))
        try:
            with pytest.raises(SedeNavigationError):
                await _read(boundary, "censal-planted-write")
        finally:
            boundary.close()
        assert not any(urlsplit(url).path == urlsplit(write_url).path for url in boundary.documents)

    @pytest.mark.asyncio
    async def test_bounce_to_the_access_selector_is_a_prompt_session_refusal(self) -> None:
        """A selector landing is a typed session refusal, well inside the old click timeout."""
        boundary = _SedeDocuments(_bouncing_to(_SELECTOR_URL, _AUTHENTICATED_SELECTOR_HTML))
        started = time.monotonic()
        try:
            with pytest.raises(SedeNavigationError) as excinfo:
                await _read(boundary, "censal-selector-bounce")
        finally:
            boundary.close()
        elapsed_ms = (time.monotonic() - started) * 1000

        error = excinfo.value
        assert error.failure_mode == SedeFailureMode.AUTH_GATE_DETECTED.value
        assert (error.context or {})["refusal"] == "session_not_accepted"
        assert _TAXPAYER not in str(error)
        assert elapsed_ms < Settings().cadrumo_browser_navigation_timeout_ms / 3
        assert urlsplit(boundary.documents[-1]).path == urlsplit(_SELECTOR_URL).path

    @pytest.mark.asyncio
    async def test_auth_gate_landing_is_a_session_refusal(self) -> None:
        gate = f"{_AEAT.domains.sede}{_AEAT.sede_paths.auth_gate_4033}"
        boundary = _SedeDocuments(_bouncing_to(gate, "<html><title>Error 4033</title></html>"))
        try:
            with pytest.raises(SedeNavigationError) as excinfo:
                await _read(boundary, "censal-auth-gate")
        finally:
            boundary.close()

        assert excinfo.value.failure_mode == SedeFailureMode.AUTH_GATE_DETECTED.value

    @pytest.mark.asyncio
    async def test_representation_dialog_is_refused_without_driving_it(self) -> None:
        dialog = f"{_AEAT.domains.www6}{_AEAT.clave_movil.dialogo_representacion_path}"
        dialog_html = (FIXTURES_DIR / "aeat-sede" / "dialogo-representacion-gate.html").read_text(encoding="utf-8")
        boundary = _SedeDocuments(_bouncing_to(dialog, dialog_html))
        try:
            with pytest.raises(SedeNavigationError) as excinfo:
                await _read(boundary, "censal-representation-dialog")
        finally:
            boundary.close()

        assert (excinfo.value.context or {})["refusal"] == "representation_gate_required"
        assert [url for url in boundary.documents if "representacion=" in url] == []

    @pytest.mark.asyncio
    async def test_unrecognised_landing_is_the_bad_landing_refusal(self) -> None:
        boundary = _SedeDocuments(_bouncing_to(f"{_AEAT.domains.www6}{OTHER_APPLICATION_START_PATH_CANARY}", _OTHER_HTML))
        try:
            with pytest.raises(SedeNavigationError) as excinfo:
                await _read(boundary, "censal-unrecognised")
        finally:
            boundary.close()

        assert (excinfo.value.context or {})["landing_path"] == OTHER_APPLICATION_START_PATH_CANARY

    @pytest.mark.asyncio
    async def test_retired_selector_click_entry_times_out_on_the_authenticated_selector(self) -> None:
        """Detector teeth: the retired entry cannot complete on the page now refused at once.

        Drives the retired sequence -- open the access selector, click the
        Cl@ve Movil authorize button -- against the same selector page. The
        click can only run out its budget, which is the live failure.
        """
        settings = Settings()
        boundary = _SedeDocuments(lambda url: _Reply(html=_AUTHENTICATED_SELECTOR_HTML))
        playwright, session = await open_real_browser_session(
            boundary=boundary,
            settings=settings,
            profile_name="censal-retired-selector-entry",
        )
        try:
            context = await session.create_context(storage_state={})
            page = await context.new_page()
            await page.goto(_SELECTOR_URL)
            with pytest.raises(PlaywrightTimeoutError):
                await page.click(_AEAT.clave_movil.authorize_button_selector, timeout=1_500)
            assert _AEAT.clave_movil.selector_access_path_marker in page.url
            await context.close()
        finally:
            await session.close()
            await playwright.stop()
            boundary.close()


class TestWalletDirectAuthenticatedEntry:
    """The IVA wallet enters Pre303 directly too; its own test module carries others' edits."""

    @pytest.mark.asyncio
    async def test_wallet_bounce_to_the_access_selector_is_a_session_refusal(self) -> None:
        pre303_path = urlsplit(_AEAT.pre303.presentation_service_path).path

        def respond(url: str) -> _Reply:
            if urlsplit(url).path == pre303_path:
                return _Reply(redirect_to=_SELECTOR_URL)
            return _Reply(html=_AUTHENTICATED_SELECTOR_HTML)

        boundary = _SedeDocuments(respond)
        factory = real_browser_factory(boundary=boundary, profile_name="wallet-selector-bounce")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "cadrumo.adapters.outbound.aeat.sede.iva_compensation_wallet.default_browser_session_factory", factory
            )
            patch.setattr(
                "cadrumo.adapters.outbound.aeat.sede.iva_compensation_wallet.storage_state_for_session",
                lambda session: {},
            )
            try:
                with pytest.raises(SedeNavigationError) as excinfo:
                    await fetch_iva_compensation_wallet(
                        offline_aeat_session().model_copy(update={"storage_state_path": Path("stored-session")}),
                        target_year=2026,
                        target_period=Period.from_year_and_code(2026, "2T"),
                    )
            finally:
                boundary.close()

        assert excinfo.value.failure_mode == SedeFailureMode.AUTH_GATE_DETECTED.value
        assert (excinfo.value.context or {})["refusal"] == "session_not_accepted"
        assert urlsplit(boundary.documents[0]).netloc == urlsplit(_AEAT.domains.www6).netloc
