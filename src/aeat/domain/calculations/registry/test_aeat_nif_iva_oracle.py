"""Offline contract tests for the AEAT NIF-IVA checker oracle adapter."""

from __future__ import annotations

import pytest

from aeat.core.config import Settings

from ._aeat_nif_iva_oracle import (
    AEAT_NIF_IVA_ENTRY_URL,
    AEAT_NIF_IVA_VERIFICATION_URL,
    ORACLE_ID,
    AeatNifIvaCheckerOracle,
    AeatNifIvaReplayDriver,
    register_default,
)
from ._errors import RegistryValidationError
from ._live_parity import LiveParityCatalogue, LiveParityOracle
from ._remote_state_guard import (
    AEAT_WRITE_FORBIDDEN_ACTIONS,
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _aeat_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="aeat-nif-iva-public",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        # The form servlet lives on www1.agenciatributaria.gob.es; the sede
        # entry point that the live driver visits first lives on
        # sede.agenciatributaria.gob.es. Both must be in the allow-list.
        allowed_hosts=(
            "sede.agenciatributaria.gob.es",
            "www1.agenciatributaria.gob.es",
        ),
        allowed_browser_action_patterns=(
            Settings.external_constants().aeat.live_safety.consult_oracle_browser_action_patterns
        ),
        # AEAT writes are PERMANENTLY FORBIDDEN — the canonical write-class
        # action labels MUST be rejected by the guard before any browser
        # action can run, regardless of how the driver labels its operations.
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def _wrong_host_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="wrong-host",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("www6.agenciatributaria.gob.es",),
        forbidden_actions=AEAT_WRITE_FORBIDDEN_ACTIONS,
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def test_adapter_satisfies_live_parity_oracle_protocol() -> None:
    oracle = AeatNifIvaCheckerOracle()
    assert isinstance(oracle, LiveParityOracle)
    assert oracle.oracle_id == ORACLE_ID
    assert oracle.surface_kind == "vat_id_check"


def test_adapter_urls_stay_inside_aeat_host_pinning_suffix() -> None:
    """Both the entry point and the form servlet are on AEAT-controlled subdomains.

    The remote-state guard's host-pinning policy keys off the
    ``agenciatributaria.gob.es`` suffix; the entry URL is on the sede
    subdomain and the form URL is on the www1 subdomain. Both match.
    """

    assert str(AEAT_NIF_IVA_ENTRY_URL).startswith("https://sede.agenciatributaria.gob.es/")
    assert str(AEAT_NIF_IVA_VERIFICATION_URL).startswith("https://www1.agenciatributaria.gob.es/")


def test_planned_operations_returns_entry_then_form_then_per_nif_then_discard() -> None:
    oracle = AeatNifIvaCheckerOracle()

    operations = oracle.planned_operations(
        b"",
        expected={"FR12345678901": "valid", "DE111222333": "valid"},
    )

    # Expected sequence: GET sede entry, GET form servlet, open-form,
    # check DE111..., check FR123..., discard.
    assert len(operations) == 6
    assert operations[0].kind == "http"
    assert operations[0].method == "GET"
    assert operations[0].url == AEAT_NIF_IVA_ENTRY_URL
    assert operations[1].kind == "http"
    assert operations[1].method == "GET"
    assert operations[1].url == AEAT_NIF_IVA_VERIFICATION_URL
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
    oracle = AeatNifIvaCheckerOracle(driver=AeatNifIvaReplayDriver())
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
    assert catalogue.lookup(ORACLE_ID, environment="production").oracle_id == ORACLE_ID


def test_register_default_test_environment_classification_supported() -> None:
    catalogue = LiveParityCatalogue()
    register_default(catalogue, environment="test_environment")

    assert catalogue.environment_of(ORACLE_ID) == "test_environment"
    with pytest.raises(RegistryValidationError, match=r"environment|production|test_environment|oracle"):
        catalogue.lookup(ORACLE_ID, environment="production")
