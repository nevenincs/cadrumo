"""Tests for the surface-kind compatibility check inside ``audit_oracle_bindings``.

A binding can be syntactically valid (registered oracle, compatible
environment) yet semantically wrong if the cross-reference's
``surface`` and the oracle's ``surface_kind`` describe different
real-world AEAT services. The audit's compatibility table is the
single source of truth for which pairs are allowed; these tests
exercise both the allow-list and a representative set of rejected
pairs.
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
)
from ._live_parity import _COMPATIBLE_SURFACE_PAIRS
from ._loader import load_registry_tree
from ._remote_state_guard import RemoteOperation, RemoteStateGuardPolicy
from ._schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


class _StubOracle:
    def __init__(self, oracle_id: str, surface_kind: OracleSurfaceKind) -> None:
        self._oracle_id = oracle_id
        self._surface_kind = surface_kind

    @property
    def oracle_id(self) -> str:
        return self._oracle_id

    @property
    def surface_kind(self) -> OracleSurfaceKind:
        return self._surface_kind

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


def _bind_first_cross_reference(
    modelo: ModeloDefinition,
    *,
    oracle_id: str,
    surface: str,
) -> ModeloDefinition:
    """Return a copy of the modelo with the first cross-reference rebound.

    Both ``oracle_id`` (binding) and ``surface`` (registry-side surface)
    are overridden so each test case can pin the exact (surface,
    surface_kind) pair under test.
    """

    revision = next(iter(modelo.revisions.values()))
    cross_references = list(revision.live_cross_references)
    cross_references[0] = cross_references[0].model_copy(update={"oracle_id": oracle_id, "surface": surface})
    new_revision = revision.model_copy(update={"live_cross_references": tuple(cross_references)})
    return modelo.model_copy(update={"revisions": {**modelo.revisions, new_revision.id: new_revision}})


def test_compatible_pair_passes_audit() -> None:
    modelo = _bind_first_cross_reference(_modelo_130(), oracle_id="vat-checker", surface="public_read_surface")
    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle("vat-checker", surface_kind="vat_id_check"), environment="production")

    failures = audit_oracle_bindings(modelo, catalogue, environment="production")

    assert failures == ()


def test_static_official_documentation_surface_rejects_every_oracle() -> None:
    modelo = _bind_first_cross_reference(_modelo_130(), oracle_id="any-oracle", surface="static_official_documentation")
    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle("any-oracle", surface_kind="vat_id_check"), environment="production")

    failures = audit_oracle_bindings(modelo, catalogue, environment="production")

    assert len(failures) == 1
    message = failures[0]
    assert "static_official_documentation" in message
    assert "vat_id_check" in message
    assert "not compatible" in message


def test_authenticated_read_surface_rejects_open_simulator_oracle() -> None:
    modelo = _bind_first_cross_reference(_modelo_130(), oracle_id="sim-oracle", surface="authenticated_read_surface")
    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle("sim-oracle", surface_kind="open_simulator"), environment="production")

    failures = audit_oracle_bindings(modelo, catalogue, environment="production")

    assert len(failures) == 1
    message = failures[0]
    assert "authenticated_read_surface" in message
    assert "open_simulator" in message


def test_lookup_failure_does_not_double_report_surface_incompatibility() -> None:
    """An unknown oracle is reported once; the surface check is skipped."""

    modelo = _bind_first_cross_reference(_modelo_130(), oracle_id="absent", surface="static_official_documentation")
    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle("present", surface_kind="vat_id_check"), environment="production")

    failures = audit_oracle_bindings(modelo, catalogue, environment="production")

    assert len(failures) == 1
    message = failures[0]
    assert "unknown oracle_id" in message
    assert "not compatible" not in message


@pytest.mark.parametrize(
    ("surface", "surface_kind"),
    sorted(_COMPATIBLE_SURFACE_PAIRS),
)
def test_every_allow_listed_pair_passes_audit(surface: str, surface_kind: OracleSurfaceKind) -> None:
    modelo = _bind_first_cross_reference(_modelo_130(), oracle_id="probe", surface=surface)
    catalogue = LiveParityCatalogue()
    catalogue.register(_StubOracle("probe", surface_kind=surface_kind), environment="production")

    failures = audit_oracle_bindings(modelo, catalogue, environment="production")

    assert failures == ()
