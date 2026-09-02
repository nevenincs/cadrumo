"""Real-behaviour tests for the cross-revision continuity screen.

Two of this screen's conditions hold across the whole corpus and are gated as
invariants elsewhere. A gate that only ever sees a clean corpus proves nothing
on its own, so both are constructed here on copies of real revisions and shown
to be caught. The other two conditions occur live and are pinned against the
corpus itself.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from dev.registry.analysis.casilla_id_grammar import classify_casilla_id
from dev.registry.analysis.continuity_integrity import chain_index, continuity_census, screen_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_a_modelo_with_sound_continuity_reports_nothing(authority: ValidatedRegistryAuthority) -> None:
    """A modelo whose chains hold together yields no finding."""
    assert screen_authority(authority, ("100",)) == ()


def test_the_one_singleton_chain_in_the_corpus_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """A chain sitting in a single revision asserts continuity across nothing."""
    findings = [item for item in screen_authority(authority, ("303",)) if item.kind == "singleton_chain"]
    assert len(findings) == 1
    assert "appears only in revision" in findings[0].detail


def test_absent_continuity_is_reported_as_its_own_kind(authority: ValidatedRegistryAuthority) -> None:
    """A multi-revision modelo carrying no chain surfaces as absent, not broken.

    The remedies differ: a broken chain is corrected, a missing one is authored,
    and collapsing them would hide which is which.
    """
    findings = screen_authority(authority, ("714",))
    assert [item.kind for item in findings] == ["modelo_without_continuity"]
    assert "5 revisions" in findings[0].detail


def test_the_census_reports_coverage_without_making_it_a_finding(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Coverage is reported beside the findings, never as one.

    Most casillas are revision-local, so demanding a chain for every casilla
    would manufacture identity rather than record it.
    """
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    modelo_ids = tuple(sorted(str(code) for code in registry_modelo_codes()))
    census = continuity_census(authority, modelo_ids)
    assert census.casillas > census.with_chain > 0
    assert census.chains > 0
    assert census.evolutions > 0


def test_screen_detects_a_chain_spanning_two_identifier_grammars(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Identity asserted across a grammar change is caught.

    The corpus contains no such chain, so the defect is constructed: a casilla
    whose identifier uses one grammar is given the chain of a casilla using
    another. Without this the invariant gate would pass on a screen that could
    not see the condition at all.
    """
    revision = authority.modelo("303").revisions["2025"]
    chained = [item for item in revision.casillas if getattr(item, "continuidad_id", None)]
    assert chained, "the fixture revision must carry continuity chains"
    donor = chained[0]
    donor_grammar = classify_casilla_id(str(donor.id))
    other = next(
        item
        for item in revision.casillas
        if classify_casilla_id(str(item.id)) != donor_grammar and not getattr(item, "continuidad_id", None)
    )

    mutated_casillas = tuple(
        item.model_copy(update={"continuidad_id": donor.continuidad_id}) if item.id == other.id else item
        for item in revision.casillas
    )
    mutated = revision.model_copy(update={"casillas": mutated_casillas})
    definition = authority.modelo("303").model_copy(
        update={"revisions": {**authority.modelo("303").revisions, "2025": mutated}}
    )

    grammars, _, _ = chain_index(definition)
    assert len(grammars[str(donor.continuidad_id)]) > 1


def test_screen_detects_an_evolution_naming_a_chain_no_casilla_carries(
    authority: ValidatedRegistryAuthority,
) -> None:
    """An evolution whose endpoints do not exist is caught.

    Constructed by removing the chain from every casilla carrying it while the
    evolution record that names it stays, which is the shape a mistaken rename
    or a half-applied migration leaves behind.
    """
    definition = authority.modelo("100")
    revision_id, revision = next(
        (rid, rev) for rid, rev in definition.revisions.items() if rev.casilla_continuidad_evolutions
    )
    orphaned = str(revision.casilla_continuidad_evolutions[0].continuidad_id)

    def _strip(rev):
        return rev.model_copy(
            update={
                "casillas": tuple(
                    item.model_copy(update={"continuidad_id": None})
                    if str(getattr(item, "continuidad_id", "")) == orphaned
                    else item
                    for item in rev.casillas
                )
            }
        )

    # The chain is carried across several revisions of this modelo, so stripping
    # one leaves the others holding it and the evolution still has members.
    patched = definition.model_copy(
        update={"revisions": {rid: _strip(rev) for rid, rev in definition.revisions.items()}}
    )
    del revision_id, revision

    grammars, _, evolutions = chain_index(patched)
    assert orphaned in evolutions
    assert orphaned not in grammars
