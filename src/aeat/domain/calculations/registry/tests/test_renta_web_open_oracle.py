"""Contract tests for the Renta WEB Open parity oracle adapter."""

from __future__ import annotations

import json
from decimal import Decimal
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

from .....core.config import Settings
from .....tests.aeat_literal_fixtures import aeat_host
from .._errors import RegistryValidationError
from .._live_parity import ParityFieldComparison
from .._remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
    remote_state_policy_from_cross_reference,
)
from .._renta_web_open_oracle import (
    RentaWebOpenOracle,
    _overall_verdict,
    _parse_decimal_text,
    equivalent_renta_web_open_value,
)
from .._schema import LiveCrossReferenceDecision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEDE_HOST = aeat_host("sede")
_WWW2_HOST = aeat_host("www2")


def _open_simulator_policy() -> RemoteStateGuardPolicy:
    decision = LiveCrossReferenceDecision(
        id="modelo-100-renta-web-open",
        evidence_tier="executable_parity_evidence",
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
    expected = {"0180": object(), "0224": object(), "0235": object()}
    plan = oracle.planned_operations(b"", expected=expected)
    actions = tuple(op.action for op in plan if op.action is not None)
    assert actions == ("requires-renta-web-open-driver",)
    http_operations = tuple(op for op in plan if op.kind == "http")
    assert len(http_operations) == 1
    assert http_operations[0].method == "GET"


def test_live_driver_plans_casilla_override_and_scrape_navigation() -> None:
    from .....adapters.outbound.aeat.sede._renta_web_open import RentaWebOpenSedeDriver

    payload = b'{"casilla_overrides": {"0528": "5000,00"}, "scrape_casillas": ["0695"]}'
    plan = RentaWebOpenSedeDriver().planned_operations(payload, expected={"0180": object()})
    actions = tuple(op.action for op in plan if op.kind == "browser_action")

    assert "navigate-to-casilla:0528" in actions
    assert "apply-casilla-override:0528" in actions
    assert "navigate-to-resumen" in actions
    assert "navigate-to-casilla:0695" in actions


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
    with pytest.raises(Exception, match="at least one expected casilla"):
        RentaWebOpenOracle().planned_operations(b"", expected={})


def test_verify_payload_without_driver_is_unverifiable_not_live_implementation() -> None:
    oracle = RentaWebOpenOracle()
    policy = _open_simulator_policy()
    result = oracle.verify_payload(policy, b"", expected={"0180": object()})

    assert result.verdict == "unverifiable"
    assert "browser driver is not configured" in result.narrative


# ---------------------------------------------------------------------------
# _parse_decimal_text — Spanish-locale-aware decimal parser
# ---------------------------------------------------------------------------


def test_parse_decimal_text_returns_none_for_empty_input() -> None:
    assert _parse_decimal_text("") is None
    assert _parse_decimal_text("   ") is None


def test_parse_decimal_text_parses_plain_integer() -> None:
    assert _parse_decimal_text("1234") == Decimal("1234")


def test_parse_decimal_text_parses_dot_decimal() -> None:
    assert _parse_decimal_text("1234.56") == Decimal("1234.56")


def test_parse_decimal_text_parses_comma_decimal_with_thousands_separator() -> None:
    """AEAT Renta WEB Open renders amounts as ``1.234,56`` (Spanish locale).
    The parser must drop ``.`` thousands separators and treat ``,`` as the
    decimal point."""
    assert _parse_decimal_text("1.234,56") == Decimal("1234.56")


def test_parse_decimal_text_strips_non_breaking_space() -> None:
    """AEAT's rendering uses ``\\xa0`` (NBSP) before the EUR suffix and
    sometimes as a thousands separator."""
    assert _parse_decimal_text("1\xa0234,56") == Decimal("1234.56")


def test_parse_decimal_text_returns_none_for_malformed_input() -> None:
    assert _parse_decimal_text("not-a-number") is None
    assert _parse_decimal_text("12,34,56") is None


def test_parse_decimal_text_tolerates_multiple_dot_thousands_groups() -> None:
    """When a comma is present, every ``.`` is stripped before parsing,
    so multi-group thousands renderings like ``1.234.567,89`` parse
    cleanly (and so do degenerate inputs the parser opts to accept)."""
    assert _parse_decimal_text("1.234.567,89") == Decimal("1234567.89")


# ---------------------------------------------------------------------------
# equivalent_renta_web_open_value — match dot-vs-comma renderings
# ---------------------------------------------------------------------------


def test_equivalent_renta_web_open_value_matches_identical_strings() -> None:
    assert equivalent_renta_web_open_value("1234.56", "1234.56") is True


def test_equivalent_renta_web_open_value_matches_dot_vs_comma_rendering() -> None:
    """Registry-side produces ``1234.56``; Renta WEB Open returns
    ``1.234,56``. Both must compare as equivalent so true matches do not
    surface as spurious mismatches."""
    assert equivalent_renta_web_open_value("1234.56", "1.234,56") is True


def test_equivalent_renta_web_open_value_matches_scale_normalisation() -> None:
    """Decimal normalises trailing zeros so ``0.00`` equals ``0``."""
    assert equivalent_renta_web_open_value("0.00", "0") is True


def test_equivalent_renta_web_open_value_returns_false_for_distinct_values() -> None:
    assert equivalent_renta_web_open_value("1234.56", "1234.57") is False


def test_equivalent_renta_web_open_value_returns_false_when_either_side_unparseable() -> None:
    assert equivalent_renta_web_open_value("1234.56", "no-such-amount") is False
    assert equivalent_renta_web_open_value("no-such-amount", "1234.56") is False


# ---------------------------------------------------------------------------
# _overall_verdict — composes per-field verdicts into a single verdict
# ---------------------------------------------------------------------------


_MATCH_FIELD = ParityFieldComparison(name="probe", expected="x", observed="x", verdict="match")
_MISMATCH_FIELD = ParityFieldComparison(name="probe", expected="x", observed="y", verdict="mismatch")
_UNVERIFIABLE_FIELD = ParityFieldComparison(name="probe", expected="x", observed="", verdict="unverifiable")


def test_overall_verdict_match_when_all_fields_match() -> None:
    assert _overall_verdict((_MATCH_FIELD,)) == "match"
    assert _overall_verdict((_MATCH_FIELD, _MATCH_FIELD)) == "match"


def test_overall_verdict_unverifiable_when_some_fields_unverifiable_and_none_mismatched() -> None:
    assert _overall_verdict((_MATCH_FIELD, _UNVERIFIABLE_FIELD)) == "unverifiable"
    assert _overall_verdict((_UNVERIFIABLE_FIELD,)) == "unverifiable"


def test_overall_verdict_mismatch_when_any_field_mismatched_even_with_unverifiable_present() -> None:
    """Mismatch outranks unverifiable in the precedence chain."""
    assert _overall_verdict((_MATCH_FIELD, _MISMATCH_FIELD)) == "mismatch"
    assert _overall_verdict((_UNVERIFIABLE_FIELD, _MISMATCH_FIELD)) == "mismatch"
    assert _overall_verdict((_MATCH_FIELD, _UNVERIFIABLE_FIELD, _MISMATCH_FIELD)) == "mismatch"


# ---------------------------------------------------------------------------
# contract — ReplayPayload roundtrip: validate strictly + round-trip through driver
# ---------------------------------------------------------------------------


def test_replay_payload_roundtrip_via_renta_web_open_driver() -> None:
    """ReplayPayload.model_validate accepts the canonical JSON shape and the
    Renta WEB Open replay driver round-trips the same envelope faithfully."""

    from .._live_parity import ReplayPayload
    from .._renta_web_open_oracle import RentaWebOpenReplayDriver

    raw = json.dumps(
        {
            "observed": {"0180": "12345.67", "0224": "0.00"},
            "raw_evidence_locator": "corpus/aeat_official/renta_web_open/sample.json",
        },
    ).encode()

    # Direct schema validation — strict, frozen, extra=forbid.
    payload = ReplayPayload.model_validate(json.loads(raw))
    assert payload.observed == {"0180": "12345.67", "0224": "0.00"}
    assert payload.raw_evidence_locator == "corpus/aeat_official/renta_web_open/sample.json"

    # Drive through the production reader path.
    driver = RentaWebOpenReplayDriver()
    observation = driver.collect_observation(raw, expected={})

    assert observation.values == {"0180": "12345.67", "0224": "0.00"}
    assert observation.raw_evidence_locator == payload.raw_evidence_locator


def test_replay_payload_strict_rejects_extra_fields_renta_web_open() -> None:
    """extra=forbid on ReplayPayload raises ValidationError for unknown keys."""

    from .._live_parity import ReplayPayload

    with pytest.raises(ValidationError, match="Extra"):
        ReplayPayload.model_validate({"observed": {}, "stray_key": "oops"})


def test_replay_payload_strict_rejects_non_string_value_in_observed_renta_web_open() -> None:
    """Mapping[str, str] under strict mode rejects non-string values."""

    from .._live_parity import ReplayPayload

    with pytest.raises(ValidationError):
        ReplayPayload.model_validate({"observed": {"0180": 12345.67}})
