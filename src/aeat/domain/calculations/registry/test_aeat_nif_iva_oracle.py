"""Offline contract tests for the AEAT NIF-IVA checker oracle adapter."""

from __future__ import annotations

import pytest

from ._aeat_nif_iva_oracle import (
    AEAT_NIF_IVA_VERIFICATION_URL,
    ORACLE_ID,
    AeatNifIvaCheckerOracle,
    register_default,
)
from ._errors import RegistryValidationError
from ._live_parity import LiveParityCatalogue, LiveParityOracle
from ._remote_state_guard import RemoteStateGuardPolicy

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _aeat_policy() -> RemoteStateGuardPolicy:
    return RemoteStateGuardPolicy(
        id="aeat-nif-iva-public",
        evidence_tier="executable_parity_evidence",
        classification="open_simulator",
        allowed_hosts=("sede.agenciatributaria.gob.es",),
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
        synthetic_data_allowed=True,
        requires_authentication=False,
        requires_aeat_authorization=False,
    )


def test_adapter_satisfies_live_parity_oracle_protocol() -> None:
    oracle = AeatNifIvaCheckerOracle()
    assert isinstance(oracle, LiveParityOracle)
    assert oracle.oracle_id == ORACLE_ID
    assert oracle.surface_kind == "vat_id_check"


def test_adapter_targets_public_aeat_sede_host() -> None:
    """Confirms the adapter URL stays inside the AEAT host-pinning policy."""

    assert str(AEAT_NIF_IVA_VERIFICATION_URL).startswith("https://sede.agenciatributaria.gob.es/")


def test_planned_operations_returns_landing_then_form_then_per_nif_then_discard() -> None:
    oracle = AeatNifIvaCheckerOracle()

    operations = oracle.planned_operations(
        b"",
        expected={"FR12345678901": "valid", "DE111222333": "valid"},
    )

    # Expected sequence: GET, open-form, check DE111..., check FR123..., discard.
    assert len(operations) == 5
    assert operations[0].kind == "http"
    assert operations[0].method == "GET"
    assert operations[0].url == AEAT_NIF_IVA_VERIFICATION_URL
    assert operations[1].kind == "browser_action"
    assert operations[1].action == "open-nif-iva-form"
    assert operations[2].kind == "browser_action"
    assert operations[2].action == "check-nif-DE111222333"
    assert operations[3].kind == "browser_action"
    assert operations[3].action == "check-nif-FR12345678901"
    assert operations[4].kind == "browser_action"
    assert operations[4].action == "discard-session"


def test_planned_operations_rejects_empty_expected() -> None:
    oracle = AeatNifIvaCheckerOracle()
    with pytest.raises(RegistryValidationError, match="at least one expected NIF"):
        oracle.planned_operations(b"", expected={})


def test_verify_payload_pre_flights_through_guard_before_raising_not_implemented() -> None:
    oracle = AeatNifIvaCheckerOracle()
    policy = _aeat_policy()

    with pytest.raises(NotImplementedError, match="Playwright driver is not implemented"):
        oracle.verify_payload(policy, b"", expected={"DE111": "valid"})


def test_verify_payload_blocked_by_guard_when_aeat_host_not_in_policy() -> None:
    oracle = AeatNifIvaCheckerOracle()
    policy = _wrong_host_policy()

    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        oracle.verify_payload(policy, b"", expected={"DE111": "valid"})


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
    with pytest.raises(RegistryValidationError):
        catalogue.lookup(ORACLE_ID, environment="production")
