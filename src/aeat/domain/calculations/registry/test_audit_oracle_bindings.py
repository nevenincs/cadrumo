"""Tests for ``audit_oracle_bindings`` and ``audit_registry_oracle_bindings``.

The audit is a pure inspection pass that compares a modelo's
cross-reference bindings against a catalogue under a chosen
environment. It must aggregate failures (never raise on the first
mismatch), short-circuit when the catalogue is empty, and emit
failure strings that name every identifier needed to diagnose the
mismatch from the message alone.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._live_parity import (
    LiveParityCatalogue,
    OracleSurfaceKind,
    ParityResult,
    audit_oracle_bindings,
    audit_registry_oracle_bindings,
)
from ._loader import load_registry_tree
from ._remote_state_guard import RemoteOperation, RemoteStateGuardPolicy
from ._schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


class _StubOracle:
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


def _modelo_130() -> ModeloDefinition:
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    return next(m for m in modelos if m.id == "130")


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
    catalogue.register(_StubOracle("any-oracle"), environment="production")

    failures = audit_oracle_bindings(modelo, catalogue, environment="production")

    assert failures == ()


def test_binding_to_production_oracle_passes_under_production() -> None:
    modelo = _bind_oracle_id_on_first_cross_reference(_modelo_130(), "stub-prod")
    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle("stub-prod"), environment="production")

    failures = audit_oracle_bindings(modelo, catalogue, environment="production")

    assert failures == ()


def test_binding_to_test_environment_oracle_fails_under_production() -> None:
    modelo = _bind_oracle_id_on_first_cross_reference(_modelo_130(), "stub-test")
    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle("stub-test"), environment="test_environment")

    failures = audit_oracle_bindings(modelo, catalogue, environment="production")

    assert len(failures) == 1
    message = failures[0]
    assert "modelo 130" in message
    assert "stub-test" in message
    assert "test_environment" in message


def test_binding_to_unregistered_oracle_fails_with_unknown_oracle_message() -> None:
    modelo = _bind_oracle_id_on_first_cross_reference(_modelo_130(), "absent-oracle")
    catalogue = LiveParityCatalogue()
    # Register an unrelated oracle so the catalogue is non-empty and the audit runs.
    catalogue.register(_StubOracle("present-oracle"), environment="production")

    failures = audit_oracle_bindings(modelo, catalogue, environment="production")

    assert len(failures) == 1
    message = failures[0]
    assert "modelo 130" in message
    assert "absent-oracle" in message
    assert "unknown oracle_id" in message


def test_aggregate_audit_collects_failures_across_modelos() -> None:
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    modelo_130 = next(m for m in modelos if m.id == "130")
    modelo_111 = next(m for m in modelos if m.id == "111")

    bound_130 = _bind_oracle_id_on_first_cross_reference(modelo_130, "missing-130")
    bound_111 = _bind_oracle_id_on_first_cross_reference(modelo_111, "missing-111")

    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle("unrelated-oracle"), environment="production")

    failures = audit_registry_oracle_bindings((bound_130, bound_111), catalogue, environment="production")

    assert len(failures) == 2
    assert any("modelo 130" in m and "missing-130" in m for m in failures)
    assert any("modelo 111" in m and "missing-111" in m for m in failures)


def test_empty_catalogue_short_circuits_to_empty_audit() -> None:
    """An empty catalogue means adapter rollout is in flight; audit silently passes."""

    modelo = _bind_oracle_id_on_first_cross_reference(_modelo_130(), "would-fail-if-checked")
    catalogue = LiveParityCatalogue()

    failures = audit_oracle_bindings(modelo, catalogue, environment="production")

    assert failures == ()


def test_aggregate_empty_catalogue_short_circuits_to_empty_audit() -> None:
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    catalogue = LiveParityCatalogue()

    failures = audit_registry_oracle_bindings(modelos, catalogue, environment="production")

    assert failures == ()
