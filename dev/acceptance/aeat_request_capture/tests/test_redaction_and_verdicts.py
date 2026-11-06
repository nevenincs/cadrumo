"""Redaction shapes and the real guard's answers, on synthetic URLs that are never requested."""

from __future__ import annotations

import pytest

from cadrumo.adapters.outbound.aeat.auth.clave_movil_support import auth_browser_action_policy
from cadrumo.adapters.outbound.aeat.sede.groi_check import READ_GUARD_POLICY as GROI_READ_POLICY
from cadrumo.core.config import Settings
from dev.acceptance.aeat_request_capture.guard_verdicts import ALLOW, guard_verdict
from dev.acceptance.aeat_request_capture.live_flows import declarations_read_policy
from dev.acceptance.aeat_request_capture.recorder import CaptureLeakError, CaptureRecorder, report_bytes
from dev.acceptance.aeat_request_capture.redaction import redact_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SEDE = "https://www6.agenciatributaria.gob.es"
DECLARATIONS_READ_POLICY = declarations_read_policy()


@pytest.mark.parametrize(
    ("segment", "kind"),
    [
        ("12345678Z", "tax-id"),
        ("12345678z", "tax-id"),
        ("X0001500M", "tax-id"),
        ("A00015016", "tax-id"),
        ("recibo-12345678Z.pdf", "tax-id"),
        ("2024123456", "digits"),
        ("1980-02-29", "digits"),
        ("nif%3D12345678Z", "tax-id"),
        ("%31%32%33", "encoded"),
        ("ana@example.test", "encoded"),
        ("a1b2c3d4e5f6a7b8", "token"),
        ("3f2504e0-4f89-41d3-9a0c-0305e82c3301", "token"),
        ("aBcDeFgHiJkLmNoPqRsT", "token"),
        ("x" * 65, "token"),
    ],
)
def test_a_segment_that_could_hold_private_data_is_replaced_and_counted(segment: str, kind: str) -> None:
    target = redact_target(f"{_SEDE}/wlpl/SCEJ-MANT/{segment}/consulta")

    assert target.path == f"/wlpl/SCEJ-MANT/{{{kind}}}/consulta"
    assert target.placeholders == (kind,)
    assert segment not in target.path


@pytest.mark.parametrize(
    "path",
    [
        "/wlpl/OVCT-CXEW/DialogoRepresentacion",
        "/wlpl/MOVI-P24H/AutenticaDniNieContrasteh",
        "/wlpl/MOVI-P24H/CancelarClaveMovil",
        "/wlpl/GROI-JDIT/ConsultaOperadorSedeGroiServlet",
        "/wlpl/SCEJ-MANT/zkau/web/zul/css/zk.wcs",
        "/static/2024/app.js",
        "/",
    ],
)
def test_a_route_name_survives_exactly_so_it_can_be_declared(path: str) -> None:
    target = redact_target(f"{_SEDE}{path}")

    assert target.path == path
    assert target.placeholders == ()


def test_a_session_path_parameter_is_replaced_but_stays_visible_as_part_of_the_path() -> None:
    target = redact_target(f"{_SEDE}/wlpl/SCEJ-MANT/consulta;jsessionid=PLANTEDSESSION42!99")

    assert target.path == "/wlpl/SCEJ-MANT/consulta;{session}"
    assert target.placeholders == ("session",)


def test_only_host_and_path_survive_a_url_with_every_other_part_planted() -> None:
    target = redact_target("https://operator:hunter2@www6.agenciatributaria.gob.es:8443/ruta?nif=12345678Z#frag")

    assert (target.host, target.path) == ("www6.agenciatributaria.gob.es", "/ruta")


@pytest.mark.parametrize("url", ["data:text/html,12345678Z", "blob:12345678Z", "about:blank", "not a url", "http://["])
def test_a_target_that_is_not_a_web_url_is_written_as_opaque(url: str) -> None:
    target = redact_target(url)

    assert (target.host, target.path) == ("", "{opaque-target}")


def test_the_guard_refuses_the_login_landing_for_the_token_inside_representacion() -> None:
    policy = auth_browser_action_policy(Settings())

    verdict = guard_verdict(policy, "GET", f"{_SEDE}/wlpl/OVCT-CXEW/DialogoRepresentacion?nif=12345678Z")

    assert verdict == "refuse:token:presentacion@path"


def test_a_token_only_in_the_query_is_told_apart_from_one_in_the_path() -> None:
    verdict = guard_verdict(DECLARATIONS_READ_POLICY, "GET", f"{_SEDE}/wlpl/SCEJ-MANT/consulta?accion=enviar")

    assert verdict == "refuse:token:enviar@query"


def test_a_static_get_is_allowed_and_a_zk_post_refused_by_method() -> None:
    assert guard_verdict(DECLARATIONS_READ_POLICY, "GET", f"{_SEDE}/wlpl/SCEJ-MANT/zkau/web/zk.wcs") == ALLOW
    assert guard_verdict(DECLARATIONS_READ_POLICY, "POST", f"{_SEDE}/wlpl/SCEJ-MANT/zkau") == "refuse:method"


def test_a_foreign_host_is_refused_without_its_name_entering_the_verdict() -> None:
    verdict = guard_verdict(GROI_READ_POLICY, "GET", "https://12345678Z.example.test/ruta")

    assert verdict == "refuse:host"


def test_the_recorder_deduplicates_and_names_the_declaration_a_refused_request_needs() -> None:
    declared = auth_browser_action_policy(Settings())
    other = DECLARATIONS_READ_POLICY
    recorder = CaptureRecorder((declared, other))
    recorder.register_flow("login", (declared.id,))
    recorder.begin_flow("login")
    for nif in ("12345678Z", "X0001502F"):
        recorder.observe("browser", "GET", f"{_SEDE}/wlpl/OVCT-CXEW/DialogoRepresentacion?nif={nif}")
    recorder.observe("browser", "POST", f"{_SEDE}/wlpl/OVCT-CXEW/DialogoRepresentacion")
    recorder.end_flow("login", "completed")

    report = recorder.report()
    needed = report["declarations_needed"]

    assert isinstance(needed, list)
    assert [(item["method"], item["path"], item["refused_count"], item["write_shaped_method"]) for item in needed] == [
        ("GET", "/wlpl/OVCT-CXEW/DialogoRepresentacion", 2, False),
        ("POST", "/wlpl/OVCT-CXEW/DialogoRepresentacion", 1, True),
    ]
    assert needed[0]["refusals"] == {declared.id: {"refuse:token:presentacion@path": 2}}
    assert b"12345678Z" not in report_bytes(report)
    assert b"X0001502F" not in report_bytes(report)


def test_a_request_allowed_by_another_flows_policy_still_needs_a_declaration_here() -> None:
    recorder = CaptureRecorder((DECLARATIONS_READ_POLICY, GROI_READ_POLICY))
    recorder.register_flow("groi", (GROI_READ_POLICY.id,))
    recorder.begin_flow("groi")
    recorder.observe("browser", "POST", f"{_SEDE}/wlpl/GROI-JDIT/ConsultaOperadorSedeGroiServlet")
    recorder.end_flow("groi", "completed")

    report = recorder.report()

    assert report["declarations_needed"] != []


@pytest.mark.parametrize("planted", ["12345678Z", "12345678z", " 12345678Z "])
def test_a_report_holding_a_configured_private_value_is_refused(planted: str) -> None:
    with pytest.raises(CaptureLeakError) as refused:
        report_bytes({"path": "/ruta/12345678Z"}, forbidden_values=(planted,))

    assert "12345678" not in str(refused.value)


def test_an_empty_forbidden_value_does_not_refuse_every_report() -> None:
    assert report_bytes({"path": "/ruta"}, forbidden_values=("", "  "))
