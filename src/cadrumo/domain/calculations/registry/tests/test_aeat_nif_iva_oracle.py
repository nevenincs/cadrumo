"""Offline contract tests for the AEAT NIF-IVA checker oracle adapter."""

from __future__ import annotations

import json
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

from .....core.config import Settings
from .....tests.aeat_literal_fixtures import aeat_host
from .._aeat_nif_iva_oracle import (
    ORACLE_ID,
    AeatNifIvaCheckerOracle,
    register_default,
)
from .._checker_oracle_flow import CheckerReplayDriver
from ..errors import RegistryValidationError
from .._live_parity import LiveParityCatalogue, LiveParityOracle, OracleEnvironment
from .._remote_state_guard import (
    AEAT_WRITE_FORBIDDEN_ACTIONS,
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEDE_HOST = aeat_host("sede")
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


def _aeat_policy() -> RemoteStateGuardPolicy:
    # AEAT-hosted policies must not advertise synthetic input per
    # the no-synthetic-sede-live-surfaces rule.
    return RemoteStateGuardPolicy(
        id="aeat-nif-iva-public",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        # The form servlet lives on www1.agenciatributaria.gob.es; the sede
        # entry point that the live driver visits first lives on
        # sede.agenciatributaria.gob.es. Both must be in the allow-list.
        allowed_hosts=(
            _SEDE_HOST,
            _WWW1_HOST,
        ),
        allowed_browser_action_patterns=(
            Settings.external_constants().aeat.live_safety.consult_oracle_browser_action_patterns
        ),
        # AEAT writes are PERMANENTLY FORBIDDEN — the canonical write-class
        # action labels MUST be rejected by the guard before any browser
        # action can run, regardless of how the driver labels its operations.
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def _wrong_host_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="wrong-host",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=(_WWW6_HOST,),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=False,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def test_adapter_satisfies_live_parity_oracle_protocol() -> None:
    oracle = AeatNifIvaCheckerOracle()
    assert isinstance(oracle, LiveParityOracle)
    assert oracle.oracle_id == ORACLE_ID
    assert oracle.surface_kind == "iva_id_check"


def test_adapter_urls_stay_inside_aeat_host_pinning_suffix() -> None:
    """Both the entry point and the form servlet are on AEAT-controlled subdomains.

    The remote-state guard's host-pinning policy keys off the
    configured AEAT host suffix; the entry URL is on the Sede
    subdomain and the form URL is on the www1 subdomain. Both match.
    """

    _ext = Settings.external_constants()
    entry_url = f"{_ext.aeat.domains.sede}{_ext.aeat.help_pages.nif_iva_landing}"
    verification_url = _ext.aeat.oracles.nif_iva_verification
    assert urlparse(entry_url).hostname == _SEDE_HOST
    assert urlparse(verification_url).hostname == _WWW1_HOST


def test_planned_operations_returns_entry_then_form_then_per_nif_then_discard() -> None:
    oracle = AeatNifIvaCheckerOracle()

    operations = oracle.planned_operations(
        b"",
        expected={"FR12345678901": "valid", "DE111222333": "valid"},
    )

    # Expected sequence: GET sede entry, GET form servlet, open-form,
    # check DE111..., check FR123..., discard.
    assert len(operations) == 6
    _ext = Settings.external_constants()
    assert operations[0].kind == "http"
    assert operations[0].method == "GET"
    assert str(operations[0].url) == f"{_ext.aeat.domains.sede}{_ext.aeat.help_pages.nif_iva_landing}"
    assert operations[1].kind == "http"
    assert operations[1].method == "GET"
    assert str(operations[1].url) == _ext.aeat.oracles.nif_iva_verification
    assert operations[2].kind == "browser_action"
    assert operations[2].action == "open-nif-iva-form"
    assert operations[3].kind == "browser_action"
    assert operations[3].action == "check-nif-DE111222333"
    assert operations[4].kind == "browser_action"
    assert operations[4].action == "check-nif-FR12345678901"
    assert operations[5].kind == "browser_action"
    assert operations[5].action == "discard-session"


def test_planned_operations_rejects_empty_expected() -> None:
    oracle = AeatNifIvaCheckerOracle()
    with pytest.raises(RegistryValidationError, match="at least one expected NIF"):
        oracle.planned_operations(b"", expected={})


def test_verify_payload_without_driver_returns_unverifiable_after_guard_preflight() -> None:
    oracle = AeatNifIvaCheckerOracle()
    policy = _aeat_policy()

    result = oracle.verify_payload(policy, b"", expected={"DE111": "valid"})

    assert result.verdict == "unverifiable"
    assert result.oracle_id == ORACLE_ID
    assert "no executable driver configured" in result.narrative


def test_nif_iva_policy_rejects_unclassified_browser_action() -> None:
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        assert_remote_operation_allowed(
            _aeat_policy(),
            RemoteOperation(kind="browser_action", action="new-unreviewed-nif-iva-click"),
        )


def test_verify_payload_reports_guard_block_when_aeat_host_not_in_policy() -> None:
    oracle = AeatNifIvaCheckerOracle()
    policy = _wrong_host_policy()

    result = oracle.verify_payload(policy, b"", expected={"DE111": "valid"})

    assert result.verdict == "blocked"
    assert "not in allowed read-only hosts" in result.narrative


def test_verify_payload_compares_replay_observations() -> None:
    oracle = AeatNifIvaCheckerOracle(
        driver=CheckerReplayDriver(surface_label="AEAT NIF-IVA replay", replay_action="parse-aeat-nif-iva-replay"),
    )
    policy = _aeat_policy()

    result = oracle.verify_payload(
        policy,
        b'{"observed": {"DE111": "valid", "FR123": "invalid"}, "raw_evidence_locator": "corpus/nif-iva.json"}',
        expected={"DE111": "valid", "FR123": "valid"},
    )

    assert result.verdict == "mismatch"
    assert result.raw_evidence_locator == "corpus/nif-iva.json"
    assert [(field.name, field.verdict) for field in result.fields] == [
        ("DE111", "match"),
        ("FR123", "mismatch"),
    ]


def test_register_default_under_production_environment() -> None:
    catalogue = LiveParityCatalogue()
    register_default(catalogue)

    assert catalogue.is_registered(ORACLE_ID)
    assert catalogue.environment_of(ORACLE_ID) == "production"
    assert catalogue.lookup(ORACLE_ID, environment=OracleEnvironment.PRODUCTION).oracle_id == ORACLE_ID


def test_register_default_test_environment_classification_supported() -> None:
    catalogue = LiveParityCatalogue()
    register_default(catalogue, environment=OracleEnvironment.TEST_ENVIRONMENT)

    assert catalogue.environment_of(ORACLE_ID) == "test_environment"
    with pytest.raises(RegistryValidationError, match=r"environment|production|test_environment|oracle"):
        catalogue.lookup(ORACLE_ID, environment=OracleEnvironment.PRODUCTION)


# ---------------------------------------------------------------------------
# contract — ReplayPayload roundtrip: validate strictly + round-trip through driver
# ---------------------------------------------------------------------------


def test_replay_payload_roundtrip_via_nif_iva_driver() -> None:
    """ReplayPayload.model_validate accepts the canonical JSON shape and the
    NIF-IVA replay driver round-trips the same envelope faithfully."""

    from .._live_parity import ReplayPayload

    raw = json.dumps(
        {
            "observed": {"DE111222333": "valid", "FR12345678901": "invalid"},
            "raw_evidence_locator": "corpus/aeat_official/nif_iva/sample.json",
        },
    ).encode()

    # Direct schema validation — strict, frozen, extra=forbid.
    payload = ReplayPayload.model_validate(json.loads(raw))
    assert payload.observed == {"DE111222333": "valid", "FR12345678901": "invalid"}
    assert payload.raw_evidence_locator == "corpus/aeat_official/nif_iva/sample.json"

    # Drive through the production reader path.
    driver = CheckerReplayDriver(surface_label="AEAT NIF-IVA replay", replay_action="parse-aeat-nif-iva-replay")
    observation = driver.collect_observation(raw, expected={})

    # Driver normalises keys to upper-case and values to lower-case.
    assert observation.values["DE111222333"] == "valid"
    assert observation.values["FR12345678901"] == "invalid"
    assert observation.raw_evidence_locator == payload.raw_evidence_locator


def test_replay_payload_strict_rejects_extra_fields_nif_iva() -> None:
    """extra=forbid on ReplayPayload raises ValidationError for unknown keys."""

    from .._live_parity import ReplayPayload

    with pytest.raises(ValidationError, match="Extra"):
        ReplayPayload.model_validate({"observed": {}, "unexpected_key": True})


def test_replay_payload_strict_rejects_non_string_value_in_observed_nif_iva() -> None:
    """Mapping[str, str] under strict mode rejects non-string values."""

    from .._live_parity import ReplayPayload

    with pytest.raises(ValidationError):
        ReplayPayload.model_validate({"observed": {"DE111222333": 42}})
