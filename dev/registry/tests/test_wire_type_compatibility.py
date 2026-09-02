"""Real-behaviour tests for the casilla-to-wire type transition screen.

Every test drives the bundled registry through the validated authority. The
detector case mutates a copy of a real revision rather than a mock, so the
screen under test walks the same typed objects it walks in production.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.export import resolved_export_endpoints
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from dev.registry.analysis.wire_type_compatibility import transitions_for_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


@pytest.fixture(scope="module")
def revision(authority: ValidatedRegistryAuthority) -> ModeloRevision:
    return authority.modelo("303").revisions["2025"]


def test_identity_transitions_are_not_reported_divergent(revision: ModeloRevision) -> None:
    """A casilla rendered as its own declared type is an identity transition."""
    transitions = transitions_for_revision(revision, modelo_id="303")
    identities = [item for item in transitions if item.casilla_type == item.wire_type]
    assert identities, "the corpus must contain at least one identity transition"
    assert all(not item.divergent for item in identities)


def test_divergent_transitions_are_reported(revision: ModeloRevision) -> None:
    """The known money-to-decimal narrowing is present and flagged divergent."""
    transitions = transitions_for_revision(revision, modelo_id="303")
    narrowings = [item for item in transitions if item.casilla_type == "money" and item.wire_type == "decimal"]
    assert narrowings, "modelo 303 renders money casillas as decimal wire fields"
    assert all(item.divergent for item in narrowings)


def test_row_mapped_endpoints_are_excluded_not_mispaired(authority: ValidatedRegistryAuthority) -> None:
    """Row-mapped endpoints carry no rendered field, so they yield no transition.

    Dropping them silently and pairing them against a type they do not have are
    both wrong; this pins the exclusion so a later change cannot turn one into
    the other unnoticed. Modelo 347 is the row-mapping case: its declarado
    record maps a repeated counterparty row onto casillas, and reading that
    edge without the mapping is what produced two wrong figures before.
    """
    revision = authority.modelo("347").revisions["2025-y-siguientes"]
    endpoints = resolved_export_endpoints(revision)
    row_mapped = [item for item in endpoints if item.path == "row_field"]
    assert row_mapped, "modelo 347 carries row-mapped endpoints"
    assert all(item.field is None for item in row_mapped)

    transitions = transitions_for_revision(revision, modelo_id="347")
    typed_endpoints = [item for item in endpoints if item.field is not None]
    assert len(transitions) <= len(typed_endpoints)

    row_only = {item.casilla_id for item in row_mapped} - {item.casilla_id for item in endpoints if item.field}
    assert row_only, "at least one casilla must be reachable only through the row mapping"
    assert row_only.isdisjoint({item.casilla_id for item in transitions})


def test_screen_detects_a_newly_divergent_declaration(revision: ModeloRevision) -> None:
    """Changing one casilla's declared type flips its transition to divergent.

    This is the screen's detector teeth: the defect is introduced on a copy of a
    real revision through the same typed model the loader produces, and the
    working tree is never mutated.
    """
    transitions = transitions_for_revision(revision, modelo_id="303")
    identity = next(item for item in transitions if not item.divergent)

    mutated_casillas = tuple(
        casilla.model_copy(update={"data_type": "boolean"}) if casilla.id == identity.casilla_id else casilla
        for casilla in revision.casillas
    )
    mutated = revision.model_copy(update={"casillas": mutated_casillas})

    after = {item.casilla_id: item for item in transitions_for_revision(mutated, modelo_id="303")}
    assert after[identity.casilla_id].divergent, "a changed declared type must surface as a divergent transition"
    assert after[identity.casilla_id].casilla_type == "boolean"
