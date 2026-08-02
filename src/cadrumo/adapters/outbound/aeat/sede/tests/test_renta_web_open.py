"""Unit checks for the Renta WEB Open Sede driver."""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlsplit

import pytest

from ......core.config import Settings
from ......domain.calculations.registry import (
    CasillaId,
    RentaWebOpenLivePayload,
    equivalent_renta_web_open_value,
    validated_casilla_id,
)
from ......tests.aeat_literal_fixtures import (
    AEAT_SUFFIX_LOOKALIKE_HOST_CANARY,
    CENSAL_WRITE_SURFACE_PATH_CANARIES,
    PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE,
    aeat_url,
)
from ..._playwright import PlaywrightTimeoutError
from .._errors import SedeFailureMode, SedeNavigationError, SedeParseError
from .._renta_web_open import (
    RentaWebOpenSedeDriver,
    _playwright_stage,
    assert_renta_web_open_read_landing,
    extract_renta_web_open_summary_value,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_APP_TEMPLATE = Settings.external_constants().aeat.oracles.renta_web_open_app_template
_RENTA_RESULTADO_CASILLA: CasillaId = validated_casilla_id("0670", surface="_RENTA_RESULTADO_CASILLA")
_RENTA_MINIMO_ESTATAL_CASILLA: CasillaId = validated_casilla_id("0519", surface="_RENTA_MINIMO_ESTATAL_CASILLA")


def test_renta_web_open_driver_plans_real_app_navigation_and_summary_scrapes() -> None:
    payload = (
        RentaWebOpenLivePayload(
            summary_labels_by_casilla_id={
                _RENTA_RESULTADO_CASILLA: "Resultado de la declaración",
                _RENTA_MINIMO_ESTATAL_CASILLA: "Mínimo personal y familiar",
            },
        )
        .model_dump_json()
        .encode("utf-8")
    )
    plan = RentaWebOpenSedeDriver().planned_operations(
        payload,
        expected={
            _RENTA_RESULTADO_CASILLA: Decimal("0.00"),
            _RENTA_MINIMO_ESTATAL_CASILLA: Decimal("5550.00"),
        },
    )

    _ext = Settings.external_constants()
    expected_app_url = _ext.aeat.oracles.renta_web_open_app_template.format(year=2025)
    assert plan[0].kind == "http"
    assert str(plan[0].url) == expected_app_url
    actions = tuple(operation.action for operation in plan if operation.kind == "browser_action")
    assert "start-open-simulator" in actions
    assert "fill-synthetic-profile" in actions
    assert "accept-identification" in actions
    assert "scrape-summary-field:Resultado de la declaración" in actions


def test_summary_extractor_reads_same_line_and_following_line_amounts() -> None:
    body_text = "Resultado de la declaración\t0,00\nMínimo personal y familiar. Parte estatal\n5.550,00\n"

    assert extract_renta_web_open_summary_value(body_text, "Resultado de la declaración") == "0,00"
    assert extract_renta_web_open_summary_value(body_text, "Mínimo personal y familiar. Parte estatal") == "5.550,00"


def test_spanish_numeric_output_matches_decimal_expected_value() -> None:
    assert equivalent_renta_web_open_value("5550.00", "5.550,00") is True
    assert equivalent_renta_web_open_value("0.00", "0,00") is True
    assert equivalent_renta_web_open_value("849.99", "850,00") is False


@pytest.mark.asyncio
async def test_renta_web_open_expected_element_timeout_reports_shape_drift() -> None:
    """Expected-control timeouts should surface as explicit Sede shape drift."""

    async def missing_element() -> None:
        raise PlaywrightTimeoutError("selector was not visible")

    with pytest.raises(SedeParseError, match="expected page element") as excinfo:
        await _playwright_stage(
            missing_element(),
            stage="start-open-simulator",
            description="Nueva declaración modal button",
            timeout_ms=250,
            timeout_is_shape_change=True,
        )

    assert excinfo.value.failure_mode == SedeFailureMode.EXTERNAL_SHAPE_CHANGED
    assert excinfo.value.context is not None
    assert excinfo.value.context["failure_mode"] == SedeFailureMode.EXTERNAL_SHAPE_CHANGED
    assert excinfo.value.context["stage"] == "start-open-simulator"


class TestRentaWebOpenLandingRefusal:
    """The page being FILLED must be the anonymous simulator.

    ``app_url`` is a field on the caller-supplied live payload, so the URL
    this driver navigates to is external input. The click guard blocks a
    *presentar* click and the page safety net blocks a forbidden
    navigation, but neither establishes that the page receiving a
    synthetic identification profile is the simulator -- and a synthetic
    profile typed into a real declaration is already damage, whether or
    not the submit that follows is blocked.

    The tests drive the driver's own exported rule, not a copy of it.
    """

    def test_the_open_simulator_app_is_admitted(self) -> None:
        assert_renta_web_open_read_landing(_APP_TEMPLATE.format(year=2025))

    def test_a_sibling_page_inside_the_open_app_is_admitted(self) -> None:
        """The simulator is a ZK app; the driver navigates within it."""
        assert_renta_web_open_read_landing(_APP_TEMPLATE.format(year=2025).replace("index.zul", "resumen.zul"))

    def test_the_rule_does_not_key_on_the_zul_extension(self) -> None:
        """The censal reader's marker list forbids .zul; this surface cannot.

        The simulator is served from ``index.zul``, so reusing that
        denylist here would refuse the very page this driver exists to
        read. This asserts the two surfaces genuinely need different
        rules rather than one shared list.
        """
        admitted = _APP_TEMPLATE.format(year=2025)
        assert admitted.endswith(".zul") or ".zul" in admitted
        assert_renta_web_open_read_landing(admitted)

    def test_a_sibling_application_outside_the_open_directory_is_refused(self) -> None:
        """The allow-list is the OPEN directory, not its parent.

        A non-anonymous sibling under the same application root is the
        landing that matters most here, and it carries no write verb, so
        the path allow-list is the only thing that refuses it.
        """
        aeat = Settings.external_constants().aeat
        open_dir = urlsplit(_APP_TEMPLATE).path.rsplit("/", 1)[0]
        parent_root = open_dir.rsplit("/", 1)[0]
        with pytest.raises(SedeNavigationError):
            assert_renta_web_open_read_landing(f"{aeat.domains.www2}{parent_root}/index.zul")

    @pytest.mark.parametrize("write_path", CENSAL_WRITE_SURFACE_PATH_CANARIES)
    def test_a_real_aeat_write_surface_is_refused(self, write_path: str) -> None:
        with pytest.raises(SedeNavigationError):
            assert_renta_web_open_read_landing(aeat_url("www2", write_path))

    def test_the_procedure_launcher_family_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_renta_web_open_read_landing(aeat_url("www2", f"{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}G322.shtml"))

    def test_an_off_aeat_payload_app_url_is_refused(self) -> None:
        """app_url is external input, so an off-AEAT host must not be navigated and filled."""
        with pytest.raises(SedeNavigationError):
            assert_renta_web_open_read_landing(
                f"https://{AEAT_SUFFIX_LOOKALIKE_HOST_CANARY}{urlsplit(_APP_TEMPLATE).path}",
            )

    def test_an_unreadable_landing_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_renta_web_open_read_landing("")
