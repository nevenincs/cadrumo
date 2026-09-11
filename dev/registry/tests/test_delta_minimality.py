"""Real-behaviour tests for the delta-minimality screen.

Every edition in the corpus is a full copy today, so the live corpus proves the
screen can name restatement. It cannot prove the other half - that a correctly
minimal delta edition is NOT named, including one restating its whole
completeness manifest - because no such edition exists yet. Those are
constructed here on copies of real revisions, through the real loaded
definitions, and each defect is shown both present and removed.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.schema import DeclaredPredecessor, ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from dev.registry.compiler.authority import compiled_bundled_authority

from ..analysis.corpus import bundled_modelo_ids
from ..analysis.delta_minimality import (
    EDITION_LOCAL_FIELDS,
    LINEAGE_CLAIM_FIELDS,
    MinimalityVerdict,
    RowJudgement,
    definition_findings,
    edition_predecessors,
    inheritable_value,
    judge_definition,
    minimality_census,
    restatement_differences,
    restating_modelos,
    screen_authority,
    stated_casillas,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A real pair of adjacent editions that both carry a completeness manifest and
#: share lineage-bearing rows, some restated and some genuinely changed.
_MODELO = "131"
_PREDECESSOR = "2024"
_SUCCESSOR = "2025"


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


@pytest.fixture(scope="module")
def pair(authority: ValidatedRegistryAuthority) -> tuple[ModeloDefinition, ModeloRevision, ModeloRevision]:
    definition = authority.modelo(_MODELO)
    return definition, definition.revisions[_PREDECESSOR], definition.revisions[_SUCCESSOR]


def _two_edition_definition(
    definition: ModeloDefinition, predecessor: ModeloRevision, successor: ModeloRevision
) -> ModeloDefinition:
    return definition.model_copy(update={"revisions": {predecessor.id: predecessor, successor.id: successor}})


def _judgements_by_casilla(definition: ModeloDefinition) -> dict[str, RowJudgement]:
    return {
        item.casilla: item for item in judge_definition(definition, modelo_id=_MODELO) if item.revision == _SUCCESSOR
    }


def _minimal_delta(
    definition: ModeloDefinition, predecessor: ModeloRevision, successor: ModeloRevision
) -> tuple[ModeloRevision, dict[str, RowJudgement]]:
    """Return the successor as a delta edition stating only what it changes.

    It declares its predecessor, keeps every row the screen judges a genuine
    change or genuinely new, drops every row it would inherit unchanged, and
    keeps its whole completeness manifest - which is what a migrated edition
    carries, because the manifest does not inherit.
    """
    verdicts = _judgements_by_casilla(_two_edition_definition(definition, predecessor, successor))
    stated = tuple(
        casilla
        for casilla in successor.casillas
        if verdicts[str(casilla.id)].kind in {"stated_difference", "new_in_edition"}
    )
    delta = successor.model_copy(
        update={"predecessor": DeclaredPredecessor(revision_id=predecessor.id), "casillas": stated}
    )
    return delta, verdicts


def test_the_live_corpus_names_modelos_that_restate_their_casillas(authority: ValidatedRegistryAuthority) -> None:
    """Every edition is a full copy today, so a modelo restating rows must be named.

    Held by identity on modelos whose successor rows are measured copies of
    their predecessors, not by a corpus count that would freeze today's backlog
    as a contract.
    """
    findings = screen_authority(authority, ("303", "131"))
    assert set(restating_modelos(findings)) == {"303", "131"}
    restated = [item for item in findings if item.kind == "restated_unchanged"]
    assert all(item.predecessor is not None for item in restated)


def _edition_keyed_pair(
    definition: ModeloDefinition, predecessor_id: str, successor_id: str
) -> tuple[ModeloDefinition, str, str]:
    """Plant a binding identifier re-keyed to each edition on one real restated row pair.

    Binding identifiers in the corpus are edition-free, so a restated row's
    binding is already equal as written. The plant appends each edition's own
    key as a whole identifier segment to the successor row and to the
    predecessor row it continues, which is the form an edition-keyed identifier
    takes. Returns the planted definition, the planted casilla id, and the
    edition-free binding the plant started from.
    """
    predecessor, successor = definition.revisions[predecessor_id], definition.revisions[successor_id]
    chains = {str(item.continuidad_id): item for item in predecessor.casillas if item.continuidad_id}
    restated = {
        item.casilla
        for item in judge_definition(definition, modelo_id=_MODELO)
        if item.revision == successor_id and item.kind == "restated_unchanged"
    }
    row = next(
        item
        for item in successor.casillas
        if str(item.id) in restated
        and item.binding is not None
        and item.continuidad_id is not None
        and chains[str(item.continuidad_id)].binding == item.binding
    )
    inherited = chains[str(row.continuidad_id)]
    binding = row.binding
    assert binding is not None
    assert successor_id not in binding and predecessor_id not in binding, "the chosen binding already embeds an edition"

    def _rekeyed(revision: ModeloRevision, target: str, edition: str) -> ModeloRevision:
        casillas = tuple(
            item.model_copy(update={"binding": f"{binding}-{edition}"}) if str(item.id) == target else item
            for item in revision.casillas
        )
        return revision.model_copy(update={"casillas": casillas})

    planted = definition.model_copy(
        update={
            "revisions": {
                **definition.revisions,
                predecessor.id: _rekeyed(predecessor, str(inherited.id), predecessor_id),
                successor.id: _rekeyed(successor, str(row.id), successor_id),
            }
        }
    )
    return planted, str(row.id), binding


def test_restatement_is_found_through_the_edition_tokens_not_in_spite_of_them(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A row named as restated differs from its inherited row as written.

    Only edition restatement separates them - here a binding identifier carrying
    its own edition key - which is exactly what a raw comparison would have
    reported as a change. The screen names the row; the raw dumps disagree.
    """
    planted, casilla_id, binding = _edition_keyed_pair(authority.modelo(_MODELO), "2019-2023", "2024")
    successor, predecessor = planted.revisions["2024"], planted.revisions["2019-2023"]
    by_id = {str(item.id): item for item in successor.casillas}
    chains = {str(item.continuidad_id): item for item in predecessor.casillas if item.continuidad_id}
    restated = [
        item
        for item in judge_definition(planted, modelo_id=_MODELO)
        if item.revision == "2024" and item.kind == "restated_unchanged"
    ]
    assert restated
    raw_differs = [
        item
        for item in restated
        if (row := by_id[item.casilla]).model_dump() != chains[str(row.continuidad_id)].model_dump()
    ]
    assert raw_differs, "every restated row was already identical as written, so normalisation was never exercised"
    rekeyed = [
        by_id[item.casilla]
        for item in raw_differs
        if by_id[item.casilla].binding != chains[str(by_id[item.casilla].continuidad_id)].binding
    ]
    assert [str(item.id) for item in rekeyed] == [casilla_id], (
        "the restated rows re-keyed to their own edition must be exactly the planted one"
    )
    row = rekeyed[0]
    inherited = chains[str(row.continuidad_id)]
    assert row.binding == f"{binding}-2024"
    assert inherited.binding == f"{binding}-2019-2023"
    assert inheritable_value(row, successor)["binding"] == inheritable_value(inherited, predecessor)["binding"]

    # Normalisation removes the edition token and nothing else: a binding
    # re-pointed at a different identifier is still a change.
    repointed = row.model_copy(update={"binding": f"{row.binding}-otro"})
    assert inheritable_value(repointed, successor)["binding"] != inheritable_value(inherited, predecessor)["binding"]


def test_every_edition_local_field_is_a_real_casilla_field() -> None:
    """A renamed field would silently stop being excluded and report every row changed."""
    assert set(CasillaDefinition.model_fields) >= EDITION_LOCAL_FIELDS | LINEAGE_CLAIM_FIELDS | {"inherited_from"}


def _restated_rows(
    definition: ModeloDefinition, predecessor: ModeloRevision, successor: ModeloRevision
) -> list[CasillaDefinition]:
    verdicts = _judgements_by_casilla(_two_edition_definition(definition, predecessor, successor))
    return [item for item in successor.casillas if verdicts[str(item.id)].kind == "restated_unchanged"]


def test_rows_marked_inherited_are_never_judged_and_the_marker_is_what_spares_them(
    pair: tuple[ModeloDefinition, ModeloRevision, ModeloRevision],
) -> None:
    """A delta edition's loaded rows include what it inherits; only the rows it states are judged.

    The successor declares its predecessor and marks every restated row as
    inherited from it, the shape the loader gives an edition that dropped those
    rows. Without the markers the very same rows are named.
    """
    definition, predecessor, successor = pair
    restated = {str(item.id) for item in _restated_rows(definition, predecessor, successor)}
    assert restated
    declared = successor.model_copy(update={"predecessor": DeclaredPredecessor(revision_id=predecessor.id)})
    marked = declared.model_copy(
        update={
            "casillas": tuple(
                item.model_copy(update={"inherited_from": predecessor.id}) if str(item.id) in restated else item
                for item in declared.casillas
            )
        }
    )

    spared = _two_edition_definition(definition, predecessor, marked)
    assert definition_findings(spared, modelo_id=_MODELO) == ()
    assert {item.casilla for item in judge_definition(spared, modelo_id=_MODELO)}.isdisjoint(restated)

    unmarked = definition_findings(_two_edition_definition(definition, predecessor, declared), modelo_id=_MODELO)
    assert {item.casilla for item in unmarked if item.kind == "restated_unchanged"} == restated


def test_a_stated_lineage_claim_is_a_statement_inheritance_cannot_reproduce(
    pair: tuple[ModeloDefinition, ModeloRevision, ModeloRevision],
) -> None:
    """An inherited row carries no lineage claim, so a row stating one differs even from an identical claim."""
    definition, predecessor, successor = pair
    row = _restated_rows(definition, predecessor, successor)[0]
    inherited = next(item for item in predecessor.casillas if item.continuidad_id == row.continuidad_id)
    claims = {"continuidad_origin": "grounded", "continuidad_evidence": "Diseño de registro, campo 1."}

    assert restatement_differences(row, successor, inherited, predecessor) == ()
    claimed = row.model_copy(update=claims)
    assert restatement_differences(claimed, successor, inherited.model_copy(update=claims), predecessor) == (
        "continuidad_evidence",
        "continuidad_origin",
    )


def test_source_refs_are_compared_net_of_each_editions_default_only_when_both_declare_one(
    pair: tuple[ModeloDefinition, ModeloRevision, ModeloRevision],
) -> None:
    """With both defaults declared, what remains is the row's own additions, and those must match."""
    definition, predecessor, successor = pair
    row = _restated_rows(definition, predecessor, successor)[0]
    own, other = "aeat-instrucciones-own", "aeat-instrucciones-other"
    inherited = next(item for item in predecessor.casillas if item.continuidad_id == row.continuidad_id).model_copy(
        update={"source_refs": ("aeat-dr-2024", own)}
    )
    with_defaults = (
        successor.model_copy(update={"casilla_source_refs": ("aeat-dr-2025",)}),
        predecessor.model_copy(update={"casilla_source_refs": ("aeat-dr-2024",)}),
    )

    def differences(
        successor_row: CasillaDefinition, revisions: tuple[ModeloRevision, ModeloRevision]
    ) -> tuple[str, ...]:
        return restatement_differences(successor_row, revisions[0], inherited, revisions[1])

    assert differences(row.model_copy(update={"source_refs": ("aeat-dr-2025", own)}), with_defaults) == ()
    assert differences(row.model_copy(update={"source_refs": ("aeat-dr-2025", other)}), with_defaults) == (
        "source_refs",
    )
    # Without a default on both sides nothing separates the edition's grounding
    # from the row's, so the references are not compared at all.
    assert differences(row.model_copy(update={"source_refs": ("aeat-dr-2025", other)}), (successor, predecessor)) == ()


def test_a_minimal_delta_restating_its_whole_manifest_is_not_named(
    pair: tuple[ModeloDefinition, ModeloRevision, ModeloRevision],
) -> None:
    """The manifest does not inherit, so restating it must never make an edition non-minimal.

    The planted edition restates its completeness manifest in full - asserted
    first, so the proof cannot pass on an edition that happens to carry none -
    and states only the casilla rows it changes. A screen spanning both
    families would name it; this one must not.
    """
    definition, predecessor, successor = pair
    delta, _ = _minimal_delta(definition, predecessor, successor)
    assert delta.completeness_manifest is not None
    assert delta.completeness_manifest == successor.completeness_manifest
    assert len(delta.casillas) < len(successor.casillas)

    planted = _two_edition_definition(definition, predecessor, delta)
    assert [(item.revision, item.basis) for item in edition_predecessors(planted)] == [
        (_PREDECESSOR, "first_in_order"),
        (_SUCCESSOR, "declared"),
    ]
    findings = definition_findings(planted, modelo_id=_MODELO)
    assert findings == ()
    assert restating_modelos(findings) == ()

    # The sharpest form: a manifest identical to the one it would have
    # inherited, had the manifest inherited at all.
    assert predecessor.completeness_manifest is not None
    copied = delta.model_copy(update={"completeness_manifest": predecessor.completeness_manifest})
    assert copied.completeness_manifest == predecessor.completeness_manifest
    assert definition_findings(_two_edition_definition(definition, predecessor, copied), modelo_id=_MODELO) == ()


def test_a_delta_restating_one_identical_row_is_named_and_stops_when_it_is_removed(
    pair: tuple[ModeloDefinition, ModeloRevision, ModeloRevision],
) -> None:
    """One restated row in an otherwise minimal delta is named, by row, and nothing else is.

    Then both removals of the defect: dropping the row, and changing it so it is
    a genuine statement rather than a copy.
    """
    definition, predecessor, successor = pair
    delta, verdicts = _minimal_delta(definition, predecessor, successor)
    copy_row = next(item for item in successor.casillas if verdicts[str(item.id)].kind == "restated_unchanged")

    defective = delta.model_copy(update={"casillas": (*delta.casillas, copy_row)})
    findings = definition_findings(_two_edition_definition(definition, predecessor, defective), modelo_id=_MODELO)
    assert [(item.revision, item.casilla, item.kind) for item in findings] == [
        (_SUCCESSOR, str(copy_row.id), "restated_unchanged")
    ]
    assert restating_modelos(findings) == (_MODELO,)

    assert definition_findings(_two_edition_definition(definition, predecessor, delta), modelo_id=_MODELO) == ()

    changed_row = copy_row.model_copy(update={"section": (*copy_row.section, "planted")})
    changed = delta.model_copy(update={"casillas": (*delta.casillas, changed_row)})
    planted = _two_edition_definition(definition, predecessor, changed)
    assert definition_findings(planted, modelo_id=_MODELO) == ()
    assert _judgements_by_casilla(planted)[str(copy_row.id)].detail == "differs in section"


def test_a_row_without_lineage_is_unchecked_never_minimal(
    pair: tuple[ModeloDefinition, ModeloRevision, ModeloRevision],
) -> None:
    """Stripping a restated row's lineage turns its verdict to unchecked, not to clean.

    The row is unchanged in every other respect, so the only thing the screen
    lost is the key that says which row it would inherit.
    """
    definition, predecessor, successor = pair
    delta, verdicts = _minimal_delta(definition, predecessor, successor)
    copy_row = next(item for item in successor.casillas if verdicts[str(item.id)].kind == "restated_unchanged")
    unlinked = copy_row.model_copy(update={"continuidad_id": None, "continuidad_origin": None})
    planted = _two_edition_definition(
        definition, predecessor, delta.model_copy(update={"casillas": (*delta.casillas, unlinked)})
    )
    findings = definition_findings(planted, modelo_id=_MODELO)
    assert [(item.casilla, item.kind) for item in findings] == [(str(copy_row.id), "unchecked_no_lineage")]
    assert restating_modelos(findings) == ()


def test_every_unlineaged_successor_row_in_the_corpus_is_reported_unchecked(
    authority: ValidatedRegistryAuthority,
) -> None:
    """No row lacking lineage in a judged edition escapes the report.

    Counted from the loaded definitions independently of the screen: every
    stated row without a ``continuidad_id`` in an edition that has a
    predecessor must surface as unchecked, so an unjudged row can never read as
    a minimal one.
    """
    modelo_ids = bundled_modelo_ids()
    expected = 0
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for edition in edition_predecessors(definition):
            if edition.predecessor is None or edition.basis == "undecidable":
                continue
            expected += sum(
                1 for item in stated_casillas(definition.revisions[edition.revision]) if item.continuidad_id is None
            )
    census = minimality_census(authority, modelo_ids)
    assert expected > 0
    assert census.verdicts[MinimalityVerdict.UNCHECKED_NO_LINEAGE] == expected
    assert census.rows_in_root_editions > 0
    assert census.root_editions > 0


def test_an_ambiguous_chain_in_the_predecessor_is_unchecked(
    pair: tuple[ModeloDefinition, ModeloRevision, ModeloRevision],
) -> None:
    """Two predecessor rows on one chain leave the inherited row undecided."""
    definition, predecessor, successor = pair
    delta, verdicts = _minimal_delta(definition, predecessor, successor)
    copy_row = next(item for item in successor.casillas if verdicts[str(item.id)].kind == "restated_unchanged")
    twin = next(item for item in predecessor.casillas if item.continuidad_id == copy_row.continuidad_id)
    doubled = predecessor.model_copy(
        update={"casillas": (*predecessor.casillas, twin.model_copy(update={"id": f"{twin.id}-twin"}))}
    )
    planted = _two_edition_definition(
        definition, doubled, delta.model_copy(update={"casillas": (*delta.casillas, copy_row)})
    )
    findings = definition_findings(planted, modelo_id=_MODELO)
    assert [(item.casilla, item.kind) for item in findings] == [(str(copy_row.id), "unchecked_ambiguous_lineage")]


def test_an_undeclared_edition_overlapping_its_neighbour_is_unchecked_unless_declared(
    pair: tuple[ModeloDefinition, ModeloRevision, ModeloRevision],
) -> None:
    """Overlapping editions may be parallel variants, so order alone cannot pair them.

    Every row of the undeclaring edition is reported unchecked; declaring the
    predecessor resolves it, and the same full copy is then judged and named.
    """
    definition, predecessor, successor = pair
    overlapping = successor.model_copy(update={"period_selector": predecessor.period_selector})
    planted = _two_edition_definition(definition, predecessor, overlapping)
    findings = definition_findings(planted, modelo_id=_MODELO)
    assert {item.kind for item in findings} == {"unchecked_predecessor_undecidable"}
    assert len(findings) == len(successor.casillas)

    declared = overlapping.model_copy(update={"predecessor": DeclaredPredecessor(revision_id=predecessor.id)})
    resolved = definition_findings(_two_edition_definition(definition, predecessor, declared), modelo_id=_MODELO)
    assert "restated_unchanged" in {item.kind for item in resolved}
    assert "unchecked_predecessor_undecidable" not in {item.kind for item in resolved}


def test_editions_declaring_no_predecessor_are_roots_and_are_not_judged(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A modelo whose editions are parallel variants, each declaring none, has nothing to judge.

    Not applicable rather than clean: no row is judged, and the editions are
    roots rather than minimal deltas.
    """
    definition = authority.modelo("369")
    assert {edition.basis for edition in edition_predecessors(definition)} == {"declared_none"}
    assert judge_definition(definition, modelo_id="369") == ()
