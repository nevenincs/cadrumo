"""Real-behaviour tests for the cross-revision continuity screen.

Two of this screen's conditions hold across the whole corpus and are gated as
invariants elsewhere. A gate that only ever sees a clean corpus proves nothing
on its own, so both are constructed here on copies of real revisions and shown
to be caught. The singleton and absent-continuity conditions are constructed the
same way, so their proofs survive the corpus being repaired.
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


def test_a_singleton_chain_is_reported_by_name(authority: ValidatedRegistryAuthority) -> None:
    """A chain sitting in a single revision asserts continuity across nothing.

    Constructed on a copy of a modelo whose chains hold together: one chain
    carried across several revisions is stripped from all but one, the
    shape a sibling deleted by mistake leaves behind. The screen must report that
    chain, by name and by the one revision holding it, and nothing else. Held by
    identity rather than by count, and constructed rather than taken from the
    corpus, so repairing every live singleton leaves the proof standing.
    """
    definition = authority.modelo("100")
    assert definition_findings(definition, modelo_id="100") == (), "the constructed singleton must be the only one"
    _, revisions, _ = chain_index(definition)
    chain = min(name for name, seen in revisions.items() if len(seen) > 1)
    kept = min(revisions[chain])

    def _strip(revision_id, revision):
        if revision_id == kept:
            return revision
        return revision.model_copy(
            update={
                "casillas": tuple(
                    item.model_copy(update={"continuidad_id": None})
                    if str(getattr(item, "continuidad_id", "")) == chain
                    else item
                    for item in revision.casillas
                )
            }
        )

    planted = definition.model_copy(
        update={"revisions": {rid: _strip(str(rid), rev) for rid, rev in definition.revisions.items()}}
    )

    findings = definition_findings(planted, modelo_id="100")
    assert [(item.kind, item.detail) for item in findings] == [
        ("singleton_chain", f"chain {chain} appears only in revision {kept}")
    ]


def test_absent_continuity_is_reported_as_its_own_kind(authority: ValidatedRegistryAuthority) -> None:
    """A multi-revision modelo carrying no chain surfaces as absent, not broken.

    The remedies differ: a broken chain is corrected, a missing one is authored,
    and collapsing them would hide which is which. Constructed on a copy of a
    real multi-revision modelo with every chain removed, so the proof does not
    depend on some modelo still lacking continuity.
    """
    definition = authority.modelo("303")
    assert len(definition.revisions) > 1
    assert "modelo_without_continuity" not in {item.kind for item in definition_findings(definition, modelo_id="303")}
    stripped = definition.model_copy(
        update={
            "revisions": {
                revision_id: revision.model_copy(
                    update={
                        "casillas": tuple(
                            item.model_copy(update={"continuidad_id": None}) for item in revision.casillas
                        ),
                        "casilla_continuidad_evolutions": (),
                    }
                )
                for revision_id, revision in definition.revisions.items()
            }
        }
    )
    findings = definition_findings(stripped, modelo_id="303")
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
    other = next(item for item in revision.casillas if classify_casilla_id(str(item.id)) != donor_grammar)

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
