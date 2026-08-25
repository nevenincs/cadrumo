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
from datetime import date

import pytest

from ......application.user_profile.censal_observation import CensalObservation
from ......core.config import Settings
from ......core.i18n import tr
from ......tests import FIXTURES_DIR
from ......tests.aeat_literal_fixtures import (
    CENSAL_WRITE_SURFACE_PATH_CANARIES,
    PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE,
    aeat_url,
)
from .._censal_datos import (
    _FORBIDDEN_LANDING_MARKERS,
    _assert_read_http,
    _assert_read_landing,
    _censal_landing_url,
    _resolve_dispatched_origin,
    censal_datos_url,
    forbidden_censal_landing_marker,
    is_forbidden_censal_landing,
    landed_on_censal_path,
    parse_censal_datos,
)
from ..errors import SedeFailureMode, SedeNavigationError, SedeParseError

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
        from bs4 import Tag

        from ..._html import parse_html
        from .._censal_datos import (
            _DOMICILIO_LABELS,
            _IDENTITY_LABELS,
            _fold,
            _section_of,
        )

        soup = parse_html(_fixture_html())
        unmapped: list[str] = []
        for table in soup.find_all("table"):
            if not isinstance(table, Tag):
                continue
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

        assert is_forbidden_censal_landing(launcher)
        with pytest.raises(SedeNavigationError):
            _assert_read_landing(launcher)

    def test_declared_markers_carry_no_empty_string(self) -> None:
        """An empty marker would match every landing and refuse the read itself."""
        assert _FORBIDDEN_LANDING_MARKERS
        assert all(marker.strip() for marker in _FORBIDDEN_LANDING_MARKERS)

    def test_public_predicate_agrees_with_the_raising_guard(self) -> None:
        """The exported predicate is the guard's own rule, not a second copy.

        Conformance gates test through this predicate, so a divergence
        would let them pass while the reader refused differently.
        """
        for landing in _REAL_WRITE_LANDINGS:
            assert is_forbidden_censal_landing(landing)
            assert forbidden_censal_landing_marker(landing) is not None
        safe = censal_datos_url("Y0000001Z", origin=_AEAT.domains.sede)
        assert not is_forbidden_censal_landing(safe)
        assert forbidden_censal_landing_marker(safe) is None

    def test_landing_guard_admits_the_consulta_itself(self) -> None:
        """The guard is not a blanket refusal — the read path still passes.

        Pairs with the refusal cases above: a guard that refused everything
        would make those assertions meaningless.
        """
        _assert_read_landing(censal_datos_url("Y0000001Z", origin=_AEAT.domains.sede))

    def test_read_guard_refuses_a_write_method(self) -> None:
        """No censal navigation may use a mutating HTTP method."""
        from cadrumo.domain.calculations.registry.errors import RegistryValidationError

        with pytest.raises(RegistryValidationError):
            _assert_read_http("POST", _CENSAL_URL)

    def test_read_guard_refuses_an_off_aeat_host(self) -> None:
        """A redirect off the AEAT apex fails closed."""
        from cadrumo.domain.calculations.registry.errors import RegistryValidationError

        with pytest.raises(RegistryValidationError):
            _assert_read_http("GET", f"https://example.invalid{_AEAT.sede_paths.censal_datos}")

    @pytest.mark.parametrize("origin", ["www1", "www2", "www6", "www12"])
    def test_read_guard_admits_every_numbered_dispatch_host(self, origin: str) -> None:
        """``www{n}`` is assigned per session, so no number may be privileged.

        Pins the no-pinned-host decision: the reader enters through the
        host-agnostic selector and must accept whichever number AEAT
        dispatches to.
        """
        _assert_read_http("GET", aeat_url(origin, _AEAT.sede_paths.censal_datos))

    def test_no_numbered_host_is_pinned_in_the_reader(self) -> None:
        """The module must not bind itself to one load-balancer host."""
        from pathlib import Path

        from .. import _censal_datos

        source = Path(_censal_datos.__file__).read_text(encoding="utf-8")
        pinned = [name for name in ("www1", "www2", "www3", "www6", "www12") if f"domains.{name}" in source]

        assert pinned == []

    def test_dispatch_predicate_recognises_the_censal_landing(self) -> None:
        """The wait and the judgement that follows it read one condition.

        They previously disagreed: a wait expiring on a page that HAD landed
        made the reader log a dispatch failure, which reads as the fallback
        having fired when it had not.
        """
        assert landed_on_censal_path(censal_datos_url("Y0000001Z", origin=_AEAT.domains.sede))
        assert landed_on_censal_path(aeat_url("www6", _AEAT.sede_paths.censal_datos))
        assert not landed_on_censal_path(f"{_AEAT.domains.sede}{_AEAT.sede_paths.expedientes_resumen}")
        assert not landed_on_censal_path("")

    def test_dispatch_predicate_is_host_agnostic(self) -> None:
        """The landing judgement keys on the path, so any dispatch host counts."""
        for origin in ("www1", "www2", "www6", "www12"):
            assert landed_on_censal_path(aeat_url(origin, _AEAT.sede_paths.censal_datos))

    def test_url_builder_requires_an_explicit_origin(self) -> None:
        """No caller may build a censal URL against an assumed host.

        The origin once defaulted to the unnumbered sede origin, which let a
        caller address a host that is not known to serve this route while
        believing it was the reader's own address.
        """
        import inspect

        origin = inspect.signature(censal_datos_url).parameters["origin"]

        assert origin.default is inspect.Parameter.empty

    def test_dispatch_failure_refuses_rather_than_degrading(self) -> None:
        """A selector that does not dispatch is refused, not retried elsewhere.

        Falling back to the unnumbered origin produced an illegible failure:
        that origin returns a genuine 404 on a sibling sede route, and a 404
        body carries no censal table, so the dispatch failure resurfaced as a
        page-shape change blaming AEAT or as a prompt to re-authenticate.
        """
        source = inspect.getsource(_resolve_dispatched_origin)

        assert "return _SEDE_ORIGIN" not in source
        assert "SedeNavigationError" in source

    def test_dispatch_refusal_names_its_cause_and_is_localised(self) -> None:
        """The refusal must be legible: a typed failure mode and a translated message."""
        with pytest.raises(SedeNavigationError) as excinfo:
            raise SedeNavigationError(
                "probe",
                failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
                translated_message=tr("adapters.sede.errors.censal_no_dispatch"),
            )

        assert excinfo.value.failure_mode == "live_navigation_failed"
        assert excinfo.value.translated_message
        assert "adapters.sede.errors" not in excinfo.value.translated_message

    def test_module_exposes_no_submitting_operation(self) -> None:
        """The public surface offers navigation and parsing only."""
        from .. import _censal_datos

        forbidden = ("submit", "fill", "click", "press", "modif", "post")
        offenders = [name for name in _censal_datos.__all__ if any(token in name.casefold() for token in forbidden)]

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
