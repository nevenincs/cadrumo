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

from ..analysis.casilla_id_grammar import classify_casilla_id
from ..analysis.continuity_integrity import chain_index, continuity_census, definition_findings, screen_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_a_modelo_with_sound_continuity_reports_nothing(authority: ValidatedRegistryAuthority) -> None:
    """A modelo whose chains hold together yields no finding."""
    assert screen_authority(authority, ("100",)) == ()


def test_a_singleton_chain_in_the_corpus_is_reported_by_name(authority: ValidatedRegistryAuthority) -> None:
    """A chain sitting in a single revision asserts continuity across nothing.

    Held by chain identity rather than by how many exist. A count here fails
    when a second singleton appears, which is the screen succeeding, and the
    reader who repairs it by raising the number has been taught to absorb the
    finding instead of reading it.

    Pinned to a live declaration: chain `dr303-112` sits alone in one revision.
    When it gains a sibling or is retired this test fails on that name, which is
    the correction; name another singleton the screen reports, or construct one
    if none remains, because the condition must keep a proof either way.
    """
    findings = [item for item in screen_authority(authority, ("303",)) if item.kind == "singleton_chain"]
    assert findings, "the singleton condition lost its live proof"
    assert any("dr303-112" in item.detail for item in findings)
    assert all("appears only in revision" in item.detail for item in findings)


def test_absent_continuity_is_reported_as_its_own_kind(authority: ValidatedRegistryAuthority) -> None:
    """A multi-revision modelo carrying no chain surfaces as absent, not broken.

    The remedies differ: a broken chain is corrected, a missing one is authored,
    and collapsing them would hide which is which.
    """
    findings = screen_authority(authority, ("714",))
    assert [item.kind for item in findings] == ["modelo_without_continuity"]
    # The detail carries the revision count, which is a live figure: asserting
    # it here would fail the day this modelo gains a revision, though nothing
    # about the absent continuity would have changed. The kind is the claim.
    assert "and no casilla carries a chain" in findings[0].detail


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

    # Assert what the SCREEN reports, not only what the index underneath shows.
    # The index seeing two grammars is the precondition; the finding is the
    # claim, and this test was named for the screen while only reaching the
    # precondition.
    kinds = {finding.kind for finding in definition_findings(definition, modelo_id="303")}
    assert "chain_crosses_grammar" in kinds


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

    findings = definition_findings(patched, modelo_id="100")
    reported = [finding for finding in findings if finding.kind == "evolution_without_members"]
    assert [finding.detail for finding in reported] == [f"evolution names chain {orphaned} that no casilla carries"]
