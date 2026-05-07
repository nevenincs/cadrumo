"""Offline contract tests for the GROI Spanish-ROI registry oracle.

Mirrors :mod:`test_aeat_nif_iva_oracle`: exercises the LiveParityOracle
Protocol conformance, planned-operations enumeration, replay-driver
JSON round-trip, oracle-with-replay verify_payload returning the
expected ParityResult shape, oracle-without-driver returning
``unverifiable``, and policy-blocked returning ``blocked``.

The replay payloads use the same JSON shape the IXVI replay adapter
uses so a calculation engine can drive both oracles uniformly.
"""

from __future__ import annotations

import pytest

from ._errors import RegistryValidationError
from ._groi_oracle import (
    AEAT_GROI_URL,
    GROI_ORACLE_ID,
    GroiObservation,
    GroiOracle,
    GroiReplayDriver,
    register_default,
)
from ._live_parity import LiveParityCatalogue, LiveParityOracle
from ._remote_state_guard import RemoteStateGuardPolicy

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _aeat_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="modelo-349-groi-spanish-roi-check",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("www2.agenciatributaria.gob.es",),
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def _wrong_host_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="wrong-host",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("sede.agenciatributaria.gob.es",),
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def test_oracle_satisfies_live_parity_oracle_protocol() -> None:
    oracle = GroiOracle()
    assert isinstance(oracle, LiveParityOracle)
    assert oracle.oracle_id == GROI_ORACLE_ID
    assert oracle.surface_kind == "vat_id_check"


def test_oracle_url_stays_inside_aeat_host_pinning_suffix() -> None:
    """The form URL is on www2.agenciatributaria.gob.es; suffix-pinning still covers it."""

    assert str(AEAT_GROI_URL).startswith("https://www2.agenciatributaria.gob.es/")
    assert str(AEAT_GROI_URL).endswith("/wlpl/GROI-JDIT/ConsultaOperadorSedeGroiServlet")


def test_planned_operations_returns_form_open_per_nif_then_discard() -> None:
    oracle = GroiOracle()
    operations = oracle.planned_operations(
        b"",
        expected={"A28015865": "valid", "B12345678": "invalid"},
    )

    # Five steps: form GET, open-form, two per-NIF checks (sorted), discard.
    assert len(operations) == 5
    assert operations[0].kind == "http"
    assert operations[0].method == "GET"
    assert operations[0].url == AEAT_GROI_URL
    assert operations[1].kind == "browser_action"
    assert operations[1].action == "open-groi-form"
    assert operations[2].action == "check-nif-A28015865"
    assert operations[3].action == "check-nif-B12345678"
    assert operations[4].action == "discard-session"


def test_planned_operations_rejects_empty_expected() -> None:
    oracle = GroiOracle()
    with pytest.raises(RegistryValidationError, match="at least one expected NIF"):
        oracle.planned_operations(b"", expected={})


def test_verify_payload_without_driver_returns_unverifiable_after_guard_preflight() -> None:
    oracle = GroiOracle()
    policy = _aeat_policy()

    result = oracle.verify_payload(policy, b"", expected={"A28015865": "valid"})

    assert result.verdict == "unverifiable"
    assert result.oracle_id == GROI_ORACLE_ID
    assert result.cross_reference_id == policy.id
    assert "no executable driver configured" in result.narrative


def test_verify_payload_reports_guard_block_when_aeat_host_not_in_policy() -> None:
    oracle = GroiOracle()
    policy = _wrong_host_policy()

    result = oracle.verify_payload(policy, b"", expected={"A28015865": "valid"})

    assert result.verdict == "blocked"
    assert result.cross_reference_id == policy.id
    assert "blocked by remote-state guard" in result.narrative


def test_verify_payload_compares_replay_observations_to_expected_verdicts() -> None:
    """Replay driver round-trips JSON; oracle compares per-NIF and emits match/mismatch."""

    oracle = GroiOracle(driver=GroiReplayDriver())
    policy = _aeat_policy()
    payload = (
        b'{"observed": {"A28015865": "valid", "B12345678": "invalid"}, '
        b'"raw_evidence_locator": "corpus/aeat_official/groi_response_samples/valid_telefonica_a28015865.txt"}'
    )

    result = oracle.verify_payload(
        policy,
        payload,
        expected={"A28015865": "valid", "B12345678": "valid"},
    )

    assert result.verdict == "mismatch"
    assert result.raw_evidence_locator == ("corpus/aeat_official/groi_response_samples/valid_telefonica_a28015865.txt")
    assert [(field.name, field.verdict) for field in result.fields] == [
        ("A28015865", "match"),
        ("B12345678", "mismatch"),
    ]


def test_verify_payload_match_when_all_observations_agree() -> None:
    oracle = GroiOracle(driver=GroiReplayDriver())
    policy = _aeat_policy()
    payload = b'{"observed": {"A28015865": "valid"}}'

    result = oracle.verify_payload(policy, payload, expected={"A28015865": "valid"})

    assert result.verdict == "match"
    assert len(result.fields) == 1
    assert result.fields[0].verdict == "match"


def test_verify_payload_unverifiable_when_replay_payload_is_malformed() -> None:
    oracle = GroiOracle(driver=GroiReplayDriver())
    policy = _aeat_policy()

    result = oracle.verify_payload(policy, b"not-json", expected={"A28015865": "valid"})

    assert result.verdict == "unverifiable"
    assert "could not produce comparable observations" in result.narrative


def test_replay_driver_rejects_payload_without_observed_object() -> None:
    driver = GroiReplayDriver()
    with pytest.raises(RegistryValidationError, match="observed object"):
        driver.collect_observation(b'{"raw_evidence_locator": "x"}', expected={})


def test_replay_driver_rejects_non_string_observed_values() -> None:
    driver = GroiReplayDriver()
    with pytest.raises(RegistryValidationError, match="string-keyed strings"):
        driver.collect_observation(b'{"observed": {"A28015865": 1}}', expected={})


def test_observation_model_normalises_nif_uppercase_and_verdict_lowercase() -> None:
    observation = GroiObservation(values={"a28015865": "VALID"})
    assert observation.values == {"A28015865": "valid"}


def test_observation_model_rejects_blank_keys_or_values() -> None:
    with pytest.raises(ValueError, match="blank"):
        GroiObservation(values={"": "valid"})


def test_register_default_under_production_environment() -> None:
    catalogue = LiveParityCatalogue()
    register_default(catalogue)

    assert catalogue.is_registered(GROI_ORACLE_ID)
    assert catalogue.environment_of(GROI_ORACLE_ID) == "production"
    assert catalogue.lookup(GROI_ORACLE_ID, environment="production").oracle_id == GROI_ORACLE_ID


def test_register_default_test_environment_classification_supported() -> None:
    catalogue = LiveParityCatalogue()
    register_default(catalogue, environment="test_environment")

    assert catalogue.environment_of(GROI_ORACLE_ID) == "test_environment"
    with pytest.raises(RegistryValidationError):
        catalogue.lookup(GROI_ORACLE_ID, environment="production")
