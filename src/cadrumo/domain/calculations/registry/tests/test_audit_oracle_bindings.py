"""Tests for ``audit_oracle_bindings`` and ``audit_registry_oracle_bindings``.

The audit is a pure inspection pass that compares a modelo's
cross-reference bindings against a catalogue under a chosen
environment. It must aggregate failures (never raise on the first
mismatch) and emit failure strings that name every identifier needed
to diagnose the mismatch from the message alone.
"""

from __future__ import annotations

import pytest

from .....tests.aeat_nif_iva_oracle import ORACLE_ID, AeatNifIvaCheckerOracle
from ..live_parity import (
    LiveParityCatalogue,
    OracleEnvironment,
    audit_oracle_bindings,
    audit_registry_oracle_bindings,
)
from ..schema import ModeloDefinition
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_130() -> ModeloDefinition:
    modelo, _catalogues = _committed_modelo("130")
    return modelo


def _bind_oracle_id_on_first_cross_reference(modelo: ModeloDefinition, oracle_id: str) -> ModeloDefinition:
    """Return a copy of the modelo whose first cross-reference binds an oracle."""

    revision = next(iter(modelo.revisions.values()))
    cross_references = list(revision.live_cross_references)
    cross_references[0] = cross_references[0].model_copy(update={"oracle_id": oracle_id})
    new_revision = revision.model_copy(update={"live_cross_references": tuple(cross_references)})
    return modelo.model_copy(update={"revisions": {**modelo.revisions, new_revision.id: new_revision}})


def test_no_bindings_produces_empty_audit() -> None:
    modelo = _modelo_130()
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)

    failures = audit_oracle_bindings(modelo, catalogue, environment=OracleEnvironment.PRODUCTION)

    assert failures == ()


def test_binding_to_production_oracle_passes_under_production() -> None:
    # Override the cross-reference's surface so the (surface, surface_kind)
    # pair is in the compatibility allow-list. The default Modelo 130 first
    # cross-reference is static_official_documentation, which the audit
    # rejects for every oracle by construction.
    modelo = _modelo_130()
    revision = next(iter(modelo.revisions.values()))
    cross_references = list(revision.live_cross_references)
    cross_references[0] = cross_references[0].model_copy(
        update={"oracle_id": ORACLE_ID, "surface": "public_read_surface"},
    )
    new_revision = revision.model_copy(update={"live_cross_references": tuple(cross_references)})
    modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, new_revision.id: new_revision}})

    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)

    failures = audit_oracle_bindings(modelo, catalogue, environment=OracleEnvironment.PRODUCTION)

    assert failures == ()


def test_binding_to_test_environment_oracle_fails_under_production() -> None:
    modelo = _bind_oracle_id_on_first_cross_reference(_modelo_130(), ORACLE_ID)
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.TEST_ENVIRONMENT)

    failures = audit_oracle_bindings(modelo, catalogue, environment=OracleEnvironment.PRODUCTION)

    assert len(failures) == 1
    message = failures[0]
    assert "modelo 130" in message
    assert ORACLE_ID in message
    assert "test_environment" in message


def test_binding_to_unregistered_oracle_fails_with_unknown_oracle_message() -> None:
    modelo = _bind_oracle_id_on_first_cross_reference(_modelo_130(), "absent-oracle")
    catalogue = LiveParityCatalogue()
    # Register an unrelated oracle so the catalogue is non-empty and the audit runs.
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)

    failures = audit_oracle_bindings(modelo, catalogue, environment=OracleEnvironment.PRODUCTION)

    assert len(failures) == 1
    message = failures[0]
    assert "modelo 130" in message
    assert "absent-oracle" in message
    assert "unknown oracle_id" in message


def test_aggregate_audit_collects_failures_across_modelos() -> None:
    modelo_130, _catalogues = _committed_modelo("130")
    modelo_111, _catalogues = _committed_modelo("111")

    bound_130 = _bind_oracle_id_on_first_cross_reference(modelo_130, "missing-130")
    bound_111 = _bind_oracle_id_on_first_cross_reference(modelo_111, "missing-111")

    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)

    failures = audit_registry_oracle_bindings(
        (bound_130, bound_111),
        catalogue,
        environment=OracleEnvironment.PRODUCTION,
    )

    assert len(failures) == 2
    assert any("modelo 130" in m and "missing-130" in m for m in failures)
    assert any("modelo 111" in m and "missing-111" in m for m in failures)


def test_empty_catalogue_reports_bound_oracle_as_unknown() -> None:
    modelo = _bind_oracle_id_on_first_cross_reference(_modelo_130(), "would-fail-if-checked")
    catalogue = LiveParityCatalogue()

    failures = audit_oracle_bindings(modelo, catalogue, environment=OracleEnvironment.PRODUCTION)

    assert len(failures) == 1
    message = failures[0]
    assert "would-fail-if-checked" in message
    assert "unknown oracle_id" in message


def test_aggregate_empty_catalogue_reports_bound_oracles() -> None:
    modelo = _bind_oracle_id_on_first_cross_reference(_modelo_130(), "missing-130")
    catalogue = LiveParityCatalogue()

    failures = audit_registry_oracle_bindings((modelo,), catalogue, environment=OracleEnvironment.PRODUCTION)

    assert len(failures) == 1
    assert "missing-130" in failures[0]
