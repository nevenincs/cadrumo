"""Tests for the surface-kind compatibility check inside ``audit_oracle_bindings``.

A binding can be syntactically valid (registered oracle, compatible
environment) yet semantically wrong if the cross-reference's
``surface`` and the oracle's ``surface_kind`` describe different
real-world AEAT services. The audit's compatibility table is the
single source of truth for which pairs are allowed; these tests
exercise both the allow-list and a representative set of rejected
pairs using the concrete oracle adapters registered in production.
"""

from __future__ import annotations

import pytest

from ..aeat_nif_iva_oracle import ORACLE_ID, AeatNifIvaCheckerOracle
from ..groi_oracle import GROI_ORACLE_ID, GroiOracle
from ..live_parity import (
    _COMPATIBLE_SURFACE_PAIRS,
    LiveParityCatalogue,
    OracleEnvironment,
    audit_oracle_bindings,
)
from .._renta_web_open_oracle import RentaWebOpenOracle
from ..schema import ModeloDefinition
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Concrete (oracle_id, surface) inputs paired with the registered
# production adapter that supplies the surface_kind. Every entry sits
# inside ``_COMPATIBLE_SURFACE_PAIRS``; the audit must accept all of
# them. Each adapter is a real production oracle — no stub layer.
_COMPATIBLE_BEHAVIOURAL_CASES: tuple[tuple[str, str, str], ...] = (
    (ORACLE_ID, "public_read_surface", "iva_id_check"),
    (GROI_ORACLE_ID, "authenticated_simulator", "iva_id_check"),
    ("modelo-100-renta-web-open", "open_simulator", "open_simulator"),
)


def _build_catalogue() -> LiveParityCatalogue:
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)
    catalogue.register(GroiOracle(), environment=OracleEnvironment.PRODUCTION)
    catalogue.register(RentaWebOpenOracle(), environment=OracleEnvironment.PRODUCTION)
    return catalogue


def _modelo_130() -> ModeloDefinition:
    modelo, _catalogues = _committed_modelo("130")
    return modelo


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
    modelo = _bind_first_cross_reference(_modelo_130(), oracle_id=ORACLE_ID, surface="public_read_surface")

    failures = audit_oracle_bindings(modelo, _build_catalogue(), environment=OracleEnvironment.PRODUCTION)

    assert failures == ()


def test_static_official_documentation_surface_rejects_every_oracle() -> None:
    modelo = _bind_first_cross_reference(_modelo_130(), oracle_id=ORACLE_ID, surface="static_official_documentation")

    failures = audit_oracle_bindings(modelo, _build_catalogue(), environment=OracleEnvironment.PRODUCTION)

    assert len(failures) == 1
    message = failures[0]
    assert "static_official_documentation" in message
    assert "iva_id_check" in message
    assert "not compatible" in message


def test_authenticated_read_surface_rejects_open_simulator_oracle() -> None:
    modelo = _bind_first_cross_reference(
        _modelo_130(),
        oracle_id="modelo-100-renta-web-open",
        surface="authenticated_read_surface",
    )

    failures = audit_oracle_bindings(modelo, _build_catalogue(), environment=OracleEnvironment.PRODUCTION)

    assert len(failures) == 1
    message = failures[0]
    assert "authenticated_read_surface" in message
    assert "open_simulator" in message


def test_lookup_failure_does_not_double_report_surface_incompatibility() -> None:
    """An unknown oracle is reported once; the surface check is skipped."""

    modelo = _bind_first_cross_reference(_modelo_130(), oracle_id="absent", surface="static_official_documentation")

    failures = audit_oracle_bindings(modelo, _build_catalogue(), environment=OracleEnvironment.PRODUCTION)

    assert len(failures) == 1
    message = failures[0]
    assert "unknown oracle_id" in message
    assert "not compatible" not in message


@pytest.mark.parametrize(
    ("oracle_id", "surface", "surface_kind"),
    _COMPATIBLE_BEHAVIOURAL_CASES,
)
def test_real_oracle_compatible_pair_passes_audit(oracle_id: str, surface: str, surface_kind: str) -> None:
    """Each registered production oracle's (surface, surface_kind) pair
    is accepted by the audit when bound to a real cross-reference."""

    assert (surface, surface_kind) in _COMPATIBLE_SURFACE_PAIRS
    modelo = _bind_first_cross_reference(_modelo_130(), oracle_id=oracle_id, surface=surface)

    failures = audit_oracle_bindings(modelo, _build_catalogue(), environment=OracleEnvironment.PRODUCTION)

    assert failures == ()


def test_compatibility_allow_list_matches_documented_pairs() -> None:
    """The allow-list is the single source of truth for which (surface,
    surface_kind) pairs an oracle binding may declare. The audit
    consults this set verbatim — any drift here is a silent change to
    every binding decision."""

    assert (
        frozenset(
            {
                ("open_simulator", "open_simulator"),
                ("integration_test_service", "integration_test_service"),
                ("public_read_surface", "iva_id_check"),
                ("public_read_surface", "file_validator"),
                ("authenticated_read_surface", "pre_filing_validator"),
                ("authenticated_simulator", "iva_id_check"),
            },
        )
        == _COMPATIBLE_SURFACE_PAIRS
    )
