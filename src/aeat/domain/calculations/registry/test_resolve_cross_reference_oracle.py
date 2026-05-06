"""Tests for ``resolve_cross_reference_oracle``.

The resolver is the single gate between a registry-level oracle binding
and the runtime catalogue. It must:

- raise when no binding is declared on the cross-reference,
- name the cross-reference id alongside the oracle id in every error,
- delegate environment-mismatch and unknown-oracle decisions to the
  catalogue while re-framing the resulting message.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ._errors import RegistryValidationError
from ._live_parity import (
    LiveParityCatalogue,
    LiveParityOracle,
    OracleSurfaceKind,
    ParityResult,
    resolve_cross_reference_oracle,
)
from ._remote_state_guard import RemoteOperation, RemoteStateGuardPolicy

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class _StubOracle:
    """Minimal protocol-conforming oracle for resolver tests."""

    def __init__(self, oracle_id: str) -> None:
        self._oracle_id = oracle_id

    @property
    def oracle_id(self) -> str:
        return self._oracle_id

    @property
    def surface_kind(self) -> OracleSurfaceKind:
        return "vat_id_check"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        del payload, expected
        return ()

    def verify_payload(
        self,
        policy: RemoteStateGuardPolicy,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> ParityResult:
        del policy, payload, expected
        raise NotImplementedError


def _catalogue_with_production_oracle(oracle_id: str = "stub-prod") -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle(oracle_id), environment="production")
    return catalogue


def _catalogue_with_test_environment_oracle(oracle_id: str = "stub-test") -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle(oracle_id), environment="test_environment")
    return catalogue


def test_resolves_registered_oracle_under_matching_environment() -> None:
    catalogue = _catalogue_with_production_oracle()

    resolved = resolve_cross_reference_oracle(
        cross_reference_id="modelo-130-static-official",
        oracle_id="stub-prod",
        catalogue=catalogue,
        environment="production",
    )

    assert isinstance(resolved, LiveParityOracle)
    assert resolved.oracle_id == "stub-prod"


def test_raises_when_cross_reference_has_no_binding() -> None:
    catalogue = _catalogue_with_production_oracle()

    with pytest.raises(RegistryValidationError, match="has no oracle binding to resolve"):
        resolve_cross_reference_oracle(
            cross_reference_id="modelo-130-static-official",
            oracle_id=None,
            catalogue=catalogue,
            environment="production",
        )


def test_unknown_oracle_error_names_cross_reference_and_oracle() -> None:
    catalogue = LiveParityCatalogue()  # empty

    with pytest.raises(RegistryValidationError) as exc_info:
        resolve_cross_reference_oracle(
            cross_reference_id="modelo-349-nif-iva-check",
            oracle_id="aeat-nif-iva-checker",
            catalogue=catalogue,
            environment="production",
        )

    message = str(exc_info.value)
    assert "modelo-349-nif-iva-check" in message
    assert "aeat-nif-iva-checker" in message


def test_environment_mismatch_error_names_cross_reference_and_oracle() -> None:
    catalogue = _catalogue_with_test_environment_oracle("stub-test")

    with pytest.raises(RegistryValidationError) as exc_info:
        resolve_cross_reference_oracle(
            cross_reference_id="modelo-100-test-only-binding",
            oracle_id="stub-test",
            catalogue=catalogue,
            environment="production",
        )

    message = str(exc_info.value)
    assert "modelo-100-test-only-binding" in message
    assert "stub-test" in message
    assert "test_environment" in message


def test_dual_environment_oracle_resolves_under_either_environment() -> None:
    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle("stub-both"), environment="both")

    production = resolve_cross_reference_oracle(
        cross_reference_id="xref",
        oracle_id="stub-both",
        catalogue=catalogue,
        environment="production",
    )
    test_env = resolve_cross_reference_oracle(
        cross_reference_id="xref",
        oracle_id="stub-both",
        catalogue=catalogue,
        environment="test_environment",
    )

    assert production.oracle_id == "stub-both"
    assert test_env.oracle_id == "stub-both"
