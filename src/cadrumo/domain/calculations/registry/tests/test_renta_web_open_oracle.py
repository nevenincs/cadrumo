"""Contract tests for the Renta WEB Open parity oracle adapter."""

from __future__ import annotations

import json
from decimal import Decimal
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.config import Settings
from .....tests.aeat_literal_fixtures import aeat_host
from ..errors import RegistryValidationError
from ..live_parity import ParityFieldComparison
from ..remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
    remote_state_policy_from_cross_reference,
)
from ..renta_web_open_oracle import (
    RentaWebOpenOracle,
    _overall_verdict,
    _parse_decimal_text,
    equivalent_renta_web_open_value,
    serialize_renta_web_open_replay_decimal,
    validate_renta_web_open_expected_casilla_ids,
)
from ..schema_base import EvidenceTier
from ..schema_verification import LiveCrossReferenceDecision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEDE_HOST = aeat_host("sede")
_WWW2_HOST = aeat_host("www2")
_RENTA_TRABAJO_CASILLA: CasillaId = validated_casilla_id("0180", surface="_RENTA_TRABAJO_CASILLA")
_RENTA_COTIZACIONES_CASILLA: CasillaId = validated_casilla_id("0224", surface="_RENTA_COTIZACIONES_CASILLA")
_RENTA_REDUCCION_CASILLA: CasillaId = validated_casilla_id("0235", surface="_RENTA_REDUCCION_CASILLA")
_RENTA_RESULTADO_CASILLA: CasillaId = validated_casilla_id("0670", surface="_RENTA_RESULTADO_CASILLA")
_RENTA_OVERRIDE_CASILLA: CasillaId = validated_casilla_id("0511", surface="_RENTA_OVERRIDE_CASILLA")
_RENTA_SCRAPE_CASILLA: CasillaId = validated_casilla_id("0695", surface="_RENTA_SCRAPE_CASILLA")
_RENTA_OVERRIDE_DISPLAY_NUMBER = "0528"
_RENTA_SCRAPE_DISPLAY_NUMBER = "0695"


def _casilla_id_from_payload(value: object) -> CasillaId:
    return validated_casilla_id(value, surface="test casilla id")


def _open_simulator_policy() -> RemoteStateGuardPolicy:
    decision = LiveCrossReferenceDecision(
        id="modelo-100-renta-web-open",
        evidence_tier=EvidenceTier.EXECUTABLE_PARITY_EVIDENCE,
        surface="open_simulator",
        guard_policy_id="modelo-100-renta-web-open-read-only",
        oracle_id="modelo-100-renta-web-open",
        allowed_hosts=(_SEDE_HOST, _WWW2_HOST),
        allowed_methods=("GET", "POST"),
        forbidden_actions=(
            "authenticated-renta-web",
            "fiscal-data-read",
            "borrador-read",
            "filed-declaration-read",
            "server-side-save",
            "signing",
            "presentation",
            "payment",
            "amendment",
            "cancellation",
            "document-submission",
            "declaration-submission",
        ),
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
        legal_refs=("ley-35-2006:art-99",),
        source_refs=("aeat-renta-2025-manual-parte1",),
    )
    return remote_state_policy_from_cross_reference(decision)


def test_oracle_id_is_stable_and_documented() -> None:
    assert RentaWebOpenOracle().oracle_id == "modelo-100-renta-web-open"


def test_oracle_surface_kind_is_open_simulator() -> None:
    assert RentaWebOpenOracle().surface_kind == "open_simulator"


def test_landing_url_targets_aeat_sede_documentation() -> None:
    _ext = Settings.external_constants()
    landing_url = f"{_ext.aeat.domains.sede}{_ext.aeat.help_pages.renta_web_open_landing}"
    assert urlparse(landing_url).hostname == _SEDE_HOST
    assert "renta-web-open" in landing_url


def test_planned_operations_lists_get_navigate_fill_scrape_and_discard() -> None:
    oracle = RentaWebOpenOracle()
    expected = {
        _RENTA_TRABAJO_CASILLA: object(),
        _RENTA_COTIZACIONES_CASILLA: object(),
        _RENTA_REDUCCION_CASILLA: object(),
    }
    plan = oracle.planned_operations(b"", expected=expected)
    actions = tuple(op.action for op in plan if op.action is not None)
    assert actions == ("requires-renta-web-open-driver",)
    http_operations = tuple(op for op in plan if op.kind == "http")
    assert len(http_operations) == 1
    assert http_operations[0].method == "GET"


def test_live_driver_plans_casilla_override_and_scrape_navigation() -> None:
    from .....adapters.outbound.aeat.sede.renta_web_open import RentaWebOpenSedeDriver

    payload = json.dumps(
        {
            "display_overrides_by_casilla_id": {
                _RENTA_OVERRIDE_CASILLA: {
                    "display_number": _RENTA_OVERRIDE_DISPLAY_NUMBER,
                    "value": "5000,00",
                },
            },
            "scrape_display_numbers_by_casilla_id": {
                _RENTA_SCRAPE_CASILLA: _RENTA_SCRAPE_DISPLAY_NUMBER,
            },
        },
    ).encode()
    plan = RentaWebOpenSedeDriver().planned_operations(payload, expected={_RENTA_SCRAPE_CASILLA: object()})
    actions = tuple(op.action for op in plan if op.kind == "browser_action")

    assert f"navigate-to-display-number:{_RENTA_OVERRIDE_DISPLAY_NUMBER}" in actions
    assert f"apply-display-override:{_RENTA_OVERRIDE_CASILLA}" in actions
    assert "navigate-to-resumen" in actions
    assert f"navigate-to-display-number:{_RENTA_SCRAPE_DISPLAY_NUMBER}" in actions


def test_live_driver_refuses_payload_without_canonical_scrape_map() -> None:
    from .....adapters.outbound.aeat.sede.renta_web_open import RentaWebOpenSedeDriver

    with pytest.raises(RegistryValidationError, match=r"keyed by canonical casilla\.id"):
        RentaWebOpenSedeDriver().planned_operations(b"{}", expected={_RENTA_TRABAJO_CASILLA: object()})


def test_live_driver_refuses_expected_casilla_not_declared_for_scraping() -> None:
    from .....adapters.outbound.aeat.sede.renta_web_open import RentaWebOpenSedeDriver

    payload = json.dumps(
        {
            "scrape_display_numbers_by_casilla_id": {
                _RENTA_SCRAPE_CASILLA: _RENTA_SCRAPE_DISPLAY_NUMBER,
            },
        },
    ).encode()

    with pytest.raises(RegistryValidationError, match=r"does not declare scrape coordinates"):
        RentaWebOpenSedeDriver().planned_operations(payload, expected={_RENTA_TRABAJO_CASILLA: object()})


def test_renta_policy_rejects_unclassified_browser_action() -> None:
    policy = _open_simulator_policy()

    assert (
        "requires-renta-web-open-driver"
        in Settings.external_constants().aeat.live_safety.renta_web_open_browser_action_patterns
    )
    assert_remote_operation_allowed(
        policy,
        RemoteOperation(kind="browser_action", action="requires-renta-web-open-driver"),
    )
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(kind="browser_action", action="new-unreviewed-renta-click"),
        )


def test_planned_operations_rejects_empty_expected_mapping() -> None:
    with pytest.raises(RegistryValidationError, match="at least one expected casilla"):
        RentaWebOpenOracle().planned_operations(b"", expected={})


def test_expected_casilla_validator_rejects_non_string_keys() -> None:
    with pytest.raises(RegistryValidationError):
        validate_renta_web_open_expected_casilla_ids({1: Decimal("0")})


def test_planned_operations_rejects_label_keyed_expected_mapping() -> None:
    with pytest.raises(RegistryValidationError, match="canonical casilla\\.id"):
        RentaWebOpenOracle().planned_operations(
            b"",
            expected={"Resultado de la declaracion": "0,00"},
        )


def test_verify_payload_without_driver_is_unverifiable_not_live_implementation() -> None:
    oracle = RentaWebOpenOracle()
    policy = _open_simulator_policy()
    result = oracle.verify_payload(policy, b"", expected={_RENTA_TRABAJO_CASILLA: object()})

    assert result.verdict == "unverifiable"
    assert "browser driver is not configured" in result.narrative


def test_verify_payload_rejects_label_keyed_expected_mapping_before_replay() -> None:
    from ..renta_web_open_oracle import RentaWebOpenReplayDriver

    raw = json.dumps(
        {
            "observed": {"Resultado de la declaracion": "0,00"},
            "observed_by_casilla_id": {_RENTA_RESULTADO_CASILLA: "0,00"},
        },
    ).encode()
    oracle = RentaWebOpenOracle(driver=RentaWebOpenReplayDriver())

    with pytest.raises(RegistryValidationError, match="canonical casilla\\.id"):
        oracle.verify_payload(
            _open_simulator_policy(),
            raw,
            expected={"Resultado de la declaracion": "0,00"},
        )


# ---------------------------------------------------------------------------
# _parse_decimal_text — Spanish-locale-aware decimal parser
# ---------------------------------------------------------------------------


def test_parse_decimal_text_handles_spanish_locale_and_invalid_inputs() -> None:
    """AEAT Renta WEB Open renders amounts as ``1.234,56`` (Spanish locale).
    The parser must drop ``.`` thousands separators, treat ``,`` as the
    decimal point, and tolerate NBSP separators while rejecting malformed text."""

    for raw, expected in (
        ("", None),
        ("   ", None),
        ("1234", Decimal("1234")),
        ("1234.56", Decimal("1234.56")),
        ("1.234,56", Decimal("1234.56")),
        ("1\xa0234,56", Decimal("1234.56")),
        ("not-a-number", None),
        ("12,34,56", None),
        ("1.234.567,89", Decimal("1234567.89")),
    ):
        assert _parse_decimal_text(raw) == expected, raw


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "sNaN", "  Infinity  "])
def test_parse_decimal_text_refuses_non_finite_tokens(token: str) -> None:
    """``Decimal`` accepts these; no captured tax amount may carry them.

    Calling ``Decimal`` directly let the tokens through as if they were amounts,
    so the parser now routes through the canonical finite coercion.
    """
    assert _parse_decimal_text(token) is None


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_tokens_are_never_a_parity_match(token: str) -> None:
    """Identical non-finite strings must not certify a corrupt magnitude."""
    assert equivalent_renta_web_open_value(token, token) is False
    assert equivalent_renta_web_open_value("1234.56", token) is False
    assert equivalent_renta_web_open_value(token, "1234.56") is False


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_replay_serialization_never_emits_a_non_finite_token(token: str) -> None:
    """A refused amount must not be written back out as a replay expectation."""
    assert serialize_renta_web_open_replay_decimal(token) is None


def test_finite_locale_controls_survive_the_non_finite_refusal() -> None:
    """The positive control: the refusal must not narrow ordinary parsing.

    Without this, every refusal above would still pass if the parser had simply
    stopped accepting amounts altogether.
    """
    assert _parse_decimal_text("1.234,56") == Decimal("1234.56")
    assert _parse_decimal_text("1\xa0234,56") == Decimal("1234.56")
    assert equivalent_renta_web_open_value("5550.00", "5.550,00") is True
    assert serialize_renta_web_open_replay_decimal("5.550,00") == "5550.00"


def test_replay_decimal_serialization_reuses_production_parser_rules() -> None:
    """Capture expectations retain the same NBSP, blank, and malformed policy as replay."""
    for raw, expected in (
        ("5\xa0956.65", "5956.65"),
        ("1.234,56", "1234.56"),
        ("", None),
        ("not-a-number", None),
    ):
        assert serialize_renta_web_open_replay_decimal(raw) == expected, raw


# ---------------------------------------------------------------------------
# equivalent_renta_web_open_value — match dot-vs-comma renderings
# ---------------------------------------------------------------------------


def test_equivalent_renta_web_open_value_compares_rendered_amounts() -> None:
    """Registry-side produces ``1234.56``; Renta WEB Open returns
    ``1.234,56``. Both must compare as equivalent so true matches do not
    surface as spurious mismatches."""

    for expected, observed, equivalent in (
        ("1234.56", "1234.56", True),
        ("1234.56", "1.234,56", True),
        ("0.00", "0", True),
        ("1234.56", "1234.57", False),
        ("1234.56", "no-such-amount", False),
        ("no-such-amount", "1234.56", False),
    ):
        assert equivalent_renta_web_open_value(expected, observed) is equivalent, (expected, observed)


# ---------------------------------------------------------------------------
# _overall_verdict — composes per-field verdicts into a single verdict
# ---------------------------------------------------------------------------


_MATCH_FIELD = ParityFieldComparison(name="probe", expected="x", observed="x", verdict="match")
_MISMATCH_FIELD = ParityFieldComparison(name="probe", expected="x", observed="y", verdict="mismatch")
_UNVERIFIABLE_FIELD = ParityFieldComparison(name="probe", expected="x", observed="", verdict="unverifiable")


def test_overall_verdict_applies_match_unverifiable_mismatch_precedence() -> None:
    """Mismatch outranks unverifiable in the precedence chain."""

    for fields, expected_verdict in (
        ((_MATCH_FIELD,), "match"),
        ((_MATCH_FIELD, _MATCH_FIELD), "match"),
        ((_MATCH_FIELD, _UNVERIFIABLE_FIELD), "unverifiable"),
        ((_UNVERIFIABLE_FIELD,), "unverifiable"),
        ((_MATCH_FIELD, _MISMATCH_FIELD), "mismatch"),
        ((_UNVERIFIABLE_FIELD, _MISMATCH_FIELD), "mismatch"),
        ((_MATCH_FIELD, _UNVERIFIABLE_FIELD, _MISMATCH_FIELD), "mismatch"),
    ):
        assert _overall_verdict(fields) == expected_verdict, fields


# ---------------------------------------------------------------------------
# contract — ReplayPayload roundtrip: validate strictly + round-trip through driver
# ---------------------------------------------------------------------------


def test_replay_payload_roundtrip_via_renta_web_open_driver() -> None:
    """ReplayPayload.model_validate accepts the canonical JSON shape and the
    Renta WEB Open replay driver round-trips the same envelope faithfully."""

    from ..live_parity import ReplayPayload
    from ..renta_web_open_oracle import RentaWebOpenReplayDriver

    raw = json.dumps(
        {
            "observed": {"Resultado de la declaracion": "legacy-label-value"},
            "observed_by_casilla_id": {
                _RENTA_TRABAJO_CASILLA: "12345.67",
                _RENTA_COTIZACIONES_CASILLA: "0.00",
            },
            "raw_evidence_locator": "corpus/aeat_official/renta_web_open/sample.json",
        },
    ).encode()

    # Direct schema validation — strict, frozen, extra=forbid.
    payload = ReplayPayload.model_validate(json.loads(raw))
    expected_by_casilla: dict[CasillaId, str] = {
        _RENTA_TRABAJO_CASILLA: "12345.67",
        _RENTA_COTIZACIONES_CASILLA: "0.00",
    }
    assert payload.observed == {"Resultado de la declaracion": "legacy-label-value"}
    assert {
        _casilla_id_from_payload(casilla_id): value for casilla_id, value in payload.observed_by_casilla_id.items()
    } == expected_by_casilla
    assert payload.raw_evidence_locator == "corpus/aeat_official/renta_web_open/sample.json"

    # Drive through the production reader path.
    driver = RentaWebOpenReplayDriver()
    observation = driver.collect_observation(raw, expected={})

    assert {
        _casilla_id_from_payload(casilla_id): value for casilla_id, value in observation.values.items()
    } == expected_by_casilla
    assert observation.raw_evidence_locator == payload.raw_evidence_locator


def test_renta_web_open_replay_driver_requires_observed_by_casilla_id() -> None:
    from ..renta_web_open_oracle import RentaWebOpenReplayDriver

    raw = json.dumps(
        {
            "observed": {"Resultado de la declaracion": "0,00"},
            "raw_evidence_locator": "corpus/aeat_official/renta_web_open/sample.json",
        },
    ).encode()

    with pytest.raises(RegistryValidationError, match="observed_by_casilla_id"):
        RentaWebOpenReplayDriver().collect_observation(raw, expected={})


def test_replay_payload_strict_rejects_extra_fields_renta_web_open() -> None:
    """extra=forbid on ReplayPayload raises ValidationError for unknown keys."""

    from ..live_parity import ReplayPayload

    with pytest.raises(ValidationError, match="Extra"):
        ReplayPayload.model_validate({"observed": {}, "stray_key": "oops"})


def test_live_payload_strict_rejects_legacy_scrape_field_names() -> None:
    from ..renta_web_open_oracle import parse_renta_web_open_live_payload

    raw = json.dumps(
        {
            "casilla_overrides": {"0528": "5000,00"},
            "scrape_casillas": ["0695"],
        },
    ).encode()

    with pytest.raises(ValidationError, match="Extra"):
        parse_renta_web_open_live_payload(raw)


def test_live_payload_rejects_display_number_keyed_overrides() -> None:
    from ..renta_web_open_oracle import parse_renta_web_open_live_payload

    raw = json.dumps(
        {
            "display_overrides": {"0528": "5000,00"},
            "scrape_display_numbers_by_casilla_id": {"0695": "0695"},
        },
    ).encode()

    with pytest.raises(ValidationError, match="Extra"):
        parse_renta_web_open_live_payload(raw)


def test_replay_payload_strict_rejects_non_string_value_in_observed_renta_web_open() -> None:
    """Mapping[str, str] under strict mode rejects non-string values."""

    from ..live_parity import ReplayPayload

    with pytest.raises(ValidationError):
        ReplayPayload.model_validate({"observed": {"Resultado de la declaracion": 12345.67}})
