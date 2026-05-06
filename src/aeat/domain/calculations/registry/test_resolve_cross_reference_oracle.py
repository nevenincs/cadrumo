"""Tests for ``resolve_cross_reference_oracle``.

The resolver is the single gate between a registry-level oracle binding
and the runtime catalogue. It must:

- raise when no binding is declared on the cross-reference,
- name the cross-reference id alongside the oracle id in every error,
- delegate environment-mismatch and unknown-oracle decisions to the
  catalogue while re-framing the resulting message.
"""

from __future__ import annotations

import pytest

from ._aeat_nif_iva_oracle import ORACLE_ID, AeatNifIvaCheckerOracle
from ._errors import RegistryValidationError
from ._live_parity import (
    LiveParityCatalogue,
    LiveParityOracle,
    resolve_cross_reference_oracle,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _catalogue_with_production_oracle() -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment="production")
    return catalogue


def _catalogue_with_test_environment_oracle() -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment="test_environment")
    return catalogue


def test_resolves_registered_oracle_under_matching_environment() -> None:
    catalogue = _catalogue_with_production_oracle()

    resolved = resolve_cross_reference_oracle(
        cross_reference_id="modelo-130-static-official",
        oracle_id=ORACLE_ID,
        catalogue=catalogue,
        environment="production",
    )

    assert isinstance(resolved, LiveParityOracle)
    assert resolved.oracle_id == ORACLE_ID


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
    catalogue = _catalogue_with_test_environment_oracle()

    with pytest.raises(RegistryValidationError) as exc_info:
        resolve_cross_reference_oracle(
            cross_reference_id="modelo-100-test-only-binding",
            oracle_id=ORACLE_ID,
            catalogue=catalogue,
            environment="production",
        )

    message = str(exc_info.value)
    assert "modelo-100-test-only-binding" in message
    assert ORACLE_ID in message
    assert "test_environment" in message


def test_dual_environment_oracle_resolves_under_either_environment() -> None:
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment="both")

    production = resolve_cross_reference_oracle(
        cross_reference_id="xref",
        oracle_id=ORACLE_ID,
        catalogue=catalogue,
        environment="production",
    )
    test_env = resolve_cross_reference_oracle(
        cross_reference_id="xref",
        oracle_id=ORACLE_ID,
        catalogue=catalogue,
        environment="test_environment",
    )

    assert production.oracle_id == ORACLE_ID
    assert test_env.oracle_id == ORACLE_ID
