"""Tests for the M130 retenciones output-casilla cross-domain snapshot check.

Mirrors ``test_first_slice_routing.py``'s coverage of the sibling
``CrossDomainSnapshotCheck`` registration: the registration side effect
lands, the check function itself fires correctly in isolation, and every
committed M130 revision's real snapshot build passes it.
"""

from __future__ import annotations

import pytest

from ....core.modelo import Modelo
from ...calculations.registry.authority import bundled_authority
from ..retenciones_routing_integrity import (
    RENTA_130_RETENCIONES_BINDING_ID,
    RENTA_130_RETENCIONES_OUTPUT_CASILLA,
    check_m130_retenciones_output_casilla,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_output_casilla_is_the_registry_validated_casilla_id() -> None:
    """The constant is a real, validated casilla id -- "06", not a bare string literal."""
    assert RENTA_130_RETENCIONES_OUTPUT_CASILLA == "06"


def test_retenciones_check_is_registered_with_the_registry_validator() -> None:
    """Importing ``renta`` registers the retenciones cross-domain check.

    The registry validator depends only on the abstract
    ``CrossDomainSnapshotCheck`` Protocol. The concrete renta check is
    injected at ``renta`` package import time. This test confirms the
    registration side effect landed (importing this test module imports
    ``renta``).
    """
    from ...calculations.registry._validate_references import _CROSS_DOMAIN_SNAPSHOT_CHECKS

    assert check_m130_retenciones_output_casilla in _CROSS_DOMAIN_SNAPSHOT_CHECKS


def test_check_fires_only_when_the_declared_binding_has_nowhere_to_report() -> None:
    """The check's own logic, exercised directly without a real snapshot.

    Three conditions must hold together for a failure, and each is tested
    alone so a change that drops one cannot pass: the modelo is 130, the
    revision DECLARES the retenciones binding, and its output casilla is
    absent.

    The binding condition is the load-bearing one. The requirement exists
    only because a binding redirects its resolved value onto casilla 06, so
    a revision declaring no such binding has nothing to protect. Asserting
    it for every modelo-130 revision fired on synthetic revisions built to
    exercise unrelated referential-integrity properties, which legitimately
    carry a minimal casilla set.

    The third Protocol parameter (the first-slice check's own concern) is
    passed through unused, so an empty and a populated value must produce
    the same result.
    """
    unrelated_targets = frozenset({"0183"})
    declared = frozenset({RENTA_130_RETENCIONES_BINDING_ID})

    # All three conditions hold -- exactly one failure, naming both halves.
    failures = check_m130_retenciones_output_casilla("130", frozenset(), unrelated_targets, declared)
    assert len(failures) == 1
    assert RENTA_130_RETENCIONES_OUTPUT_CASILLA in failures[0]
    assert RENTA_130_RETENCIONES_BINDING_ID in failures[0]

    # The first-slice parameter is genuinely unused: same verdict either way.
    assert check_m130_retenciones_output_casilla("130", frozenset(), frozenset(), declared) == failures

    # Casilla present -- the binding has somewhere to report.
    assert check_m130_retenciones_output_casilla("130", frozenset({"06"}), unrelated_targets, declared) == []

    # Binding absent -- no redirect runs, so casilla 06 is not required.
    assert check_m130_retenciones_output_casilla("130", frozenset(), unrelated_targets, frozenset()) == []
    assert (
        check_m130_retenciones_output_casilla("130", frozenset(), unrelated_targets, frozenset({"some-other-binding"}))
        == []
    )

    # A non-130 modelo is outside this check's scope even when both hold.
    assert check_m130_retenciones_output_casilla("100", frozenset(), unrelated_targets, declared) == []
    assert check_m130_retenciones_output_casilla("303", frozenset(), unrelated_targets, declared) == []


def test_modelo_130_revisions_declare_the_output_casilla() -> None:
    """Every committed Modelo 130 revision declares the retenciones output casilla.

    Domain-layer mirror of the snapshot-time gate: every revision's own
    casilla set must contain :data:`RENTA_130_RETENCIONES_OUTPUT_CASILLA`. A
    regression that drops or renumbers casilla 06 without updating this
    constant reproduces the exact defect the registered check guards
    against.
    """
    modelo_130 = bundled_authority().modelo("130")

    for revision_id, revision in modelo_130.revisions.items():
        casilla_ids = {casilla.id for casilla in revision.casillas}
        assert RENTA_130_RETENCIONES_OUTPUT_CASILLA in casilla_ids, (
            f"revision {revision_id!r} is missing casilla {RENTA_130_RETENCIONES_OUTPUT_CASILLA!r}"
        )


def test_modelo_130_snapshot_builds_cleanly_for_every_quarter() -> None:
    """The real end-to-end proof: building a Modelo 130 snapshot must not raise.

    Building a snapshot exercises the full registered cross-domain check
    set via ``_check_all_id_references``; a regression that silently broke
    the retenciones referential-integrity wiring would surface here as a
    ``RegistryValidationError`` at snapshot build, not as a runtime redirect
    to a non-existent casilla.
    """
    authority = bundled_authority()
    for period in ("1T", "2T", "3T", "4T"):
        snapshot = authority.snapshot(Modelo.M130, filing_year=2026, period=period)
        assert snapshot.revision.id == "2019-y-siguientes"
