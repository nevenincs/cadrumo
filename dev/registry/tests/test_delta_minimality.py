"""Real-behaviour tests for the delta-minimality screen.

No edition in the corpus restates an inherited row today, so the live corpus
cannot prove that the screen names restatement. The restating edition is built
here instead, and built by the loader rather than by hand: modelo 131's 2025
edition overrides every row it inherits, so dropping one override from a copy of
its authored source makes the loader materialise the row that edition would
inherit. Stating that materialised row verbatim is restatement, exactly as the
loader defines it; leaving it inherited is the minimal delta. Each defect is
shown both present and removed.

The same copy carries the other half: 131's 2025 overrides cite the orden that
approves the 2025 edition where 2024 cites the orden that approved its own, and
the loader proves that dropping such an override hydrates the predecessor's
citation. Such an override is a statement inheritance cannot reproduce, never a
restatement.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..analysis.corpus import bundled_modelo_ids
from ..analysis.delta_minimality import (
    EDITION_LOCAL_FIELDS,
    MinimalityVerdict,
    RowJudgement,
    definition_findings,
    definitions_census,
    edition_predecessors,
    inheritable_value,
    judge_definition,
    minimality_census,
    restatement_differences,
    restating_modelos,
    screen_authority,
    stated_casillas,
    storage_reused_casillas,
)
from ..compiler.authority import compiled_bundled_authority
from ..compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A real pair of adjacent editions that both carry a completeness manifest and
#: share lineage-bearing rows, every one of them overridden by the successor.
_MODELO = "131"
_PREDECESSOR = "2024"
_SUCCESSOR = "2025"

#: One real row of that pair, whose 2025 override states nothing but the legal
#: references that cite the orden approving the 2025 edition.
_ROW = "modulos-epigrafe"

#: The authored text the copies remove, each asserted present before removal so
#: a corpus edit retires the proof loudly rather than silently weakening it.
_OVERRIDE = (
    '[[revisions."2025".casilla_overrides]]\n'
    'selector = { revision = "2024", id = "modulos-epigrafe" }\n'
    'fields = { legal_refs = ["ley-35-2006:art-31", "orden-hac-1347-2024:art-4"] }\n'
    "removed_fields = []\n\n"
)
_ROOT = "2019-2023"
_ROOT_NEXT_ROW = '[[revisions."2019-2023".casillas]]\nid = "modulos-1-unidades"'
_ROOT_LEGAL_REFS = (
    f'legal_refs = ["ley-35-2006:art-31", "orden-hfp-1335-2021:art-4", "orden-hfp-1172-2022:art-4"]\n\n{_ROOT_NEXT_ROW}'
)
_NEXT_OVERRIDE = (
    'removed_fields = []\n\n[[revisions."2024".casilla_overrides]]\n'
    'selector = { revision = "2019-2023", id = "modulos-1-unidades" }'
)
_PREDECESSOR_LEGAL_REFS = (
    f'continuidad_origin = "grounded", legal_refs = ["ley-35-2006:art-31", "orden-hfp-1359-2023:art-4"]}}\n'
    f"{_NEXT_OVERRIDE}"
)
_PREDECESSOR_WITHOUT_LEGAL_REFS = f'continuidad_origin = "grounded"}}\n{_NEXT_OVERRIDE}'


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


@pytest.fixture(scope="module")
def pair(authority: ValidatedRegistryAuthority) -> tuple[ModeloDefinition, ModeloRevision, ModeloRevision]:
    definition = authority.modelo(_MODELO)
    return definition, definition.revisions[_PREDECESSOR], definition.revisions[_SUCCESSOR]


def _partial_tree(destination: Path) -> Path:
    """Copy the one modelo and the catalogues it loads against, and return its directory."""
    bundled_root = Path(bundled_path("registry", "aeat"))
    registry_root = destination / "aeat"
    for catalogue in ("facts", "legal"):
        shutil.copytree(bundled_root / catalogue, registry_root / catalogue)
    shutil.copytree(bundled_root / "modelos" / _MODELO, registry_root / "modelos" / _MODELO)
    return registry_root / "modelos" / _MODELO


def _rewrite(path: Path, old: str, new: str) -> None:
    current = path.read_text(encoding="utf-8")
    assert old in current, f"{path} no longer states {old!r}"
    path.write_text(current.replace(old, new, 1), encoding="utf-8")


@dataclass(frozen=True, slots=True)
class _Inheritance:
    """Modelo 131 as the loader materialises it once the 2025 override is dropped.

    ``delta`` is the minimal form: its 2025 edition inherits the row. ``row`` is
    the row the loader materialised for it, the value a restating edition would
    have to state. ``redefaulted`` is the same tree with the row's own
    ``legal_refs`` dropped too -- from the 2019-2023 edition that states it and
    from the 2024 override that cites 2024's orden -- so the 2024 row takes its
    edition's ordenes and the inheriting edition re-defaults it to its own.
    """

    delta: ModeloDefinition
    row: CasillaDefinition
    redefaulted: ModeloDefinition
    redefaulted_row: CasillaDefinition


def _row_of(definition: ModeloDefinition, revision_id: str, casilla_id: str) -> CasillaDefinition:
    return next(item for item in definition.revisions[revision_id].casillas if str(item.id) == casilla_id)


@pytest.fixture(scope="module")
def inheritance(tmp_path_factory: pytest.TempPathFactory) -> _Inheritance:
    modelo_dir = _partial_tree(tmp_path_factory.mktemp("registry"))
    _rewrite(modelo_dir / "revisions" / _SUCCESSOR / "revision.toml", _OVERRIDE, "")
    delta = load_modelo_directory(modelo_dir)

    root_rows = modelo_dir / "revisions" / _ROOT / "casillas" / "0001-declarations.toml"
    _rewrite(root_rows, _ROOT_LEGAL_REFS, _ROOT_NEXT_ROW)
    _rewrite(
        modelo_dir / "revisions" / _PREDECESSOR / "revision.toml",
        _PREDECESSOR_LEGAL_REFS,
        _PREDECESSOR_WITHOUT_LEGAL_REFS,
    )
    redefaulted = load_modelo_directory(modelo_dir)
    return _Inheritance(
        delta=delta,
        row=_row_of(delta, _SUCCESSOR, _ROW),
        redefaulted=redefaulted,
        redefaulted_row=_row_of(redefaulted, _SUCCESSOR, _ROW),
    )


def _stating(definition: ModeloDefinition, row: CasillaDefinition) -> ModeloDefinition:
    """Return the definition with its 2025 edition stating ``row`` instead of inheriting it."""
    successor = definition.revisions[_SUCCESSOR]
    stated = row.model_copy(update={"inherited_from": None})
    return _with_rows(definition, tuple(stated if str(item.id) == str(row.id) else item for item in successor.casillas))


def _with_rows(definition: ModeloDefinition, rows: tuple[CasillaDefinition, ...]) -> ModeloDefinition:
    successor = definition.revisions[_SUCCESSOR].model_copy(update={"casillas": rows})
    return definition.model_copy(update={"revisions": {**definition.revisions, _SUCCESSOR: successor}})


def _successor_judgements(definition: ModeloDefinition) -> dict[str, RowJudgement]:
    return {
        item.casilla: item for item in judge_definition(definition, modelo_id=_MODELO) if item.revision == _SUCCESSOR
    }


def test_the_loader_proves_the_inherited_row_and_the_screen_names_the_edition_that_restates_it(
    inheritance: _Inheritance,
) -> None:
    """The row the loader materialises by inheritance, stated verbatim, is named restatement.

    The minimal form - the same tree, the row left inherited - is named nothing,
    so the marker on one row is the whole difference between the two verdicts.
    """
    assert inheritance.row.inherited_from == _PREDECESSOR
    assert definition_findings(inheritance.delta, modelo_id=_MODELO) == ()

    restating = _stating(inheritance.delta, inheritance.row)
    findings = definition_findings(restating, modelo_id=_MODELO)
    assert [(item.revision, item.casilla, item.kind) for item in findings] == [(_SUCCESSOR, _ROW, "restated_unchanged")]
    assert restating_modelos(findings) == (_MODELO,)


def test_an_override_citing_this_editions_orden_is_a_statement_inheritance_cannot_reproduce(
    pair: tuple[ModeloDefinition, ModeloRevision, ModeloRevision], inheritance: _Inheritance
) -> None:
    """131's 2025 legal-reference overrides are differences, because dropping them changes the row.

    The loader settles it: without the override the row hydrates the 2024
    orden, so the stated value is the only thing that puts the 2025 orden on the
    row. The schema has no additive legal-reference form, so an inherited row
    carries the predecessor's array whole.
    """
    definition, _predecessor, _successor = pair
    stated = _row_of(definition, _SUCCESSOR, _ROW)
    inherited = inheritance.row
    assert "orden-hac-1347-2024:art-4" in stated.legal_refs
    assert "orden-hfp-1359-2023:art-4" in inherited.legal_refs
    assert set(stated.legal_refs) != set(inherited.legal_refs)

    judgement = _successor_judgements(definition)[_ROW]
    assert judgement.kind == "stated_difference"
    assert judgement.detail == "differs in legal_refs"
    assert restating_modelos(definition_findings(definition, modelo_id=_MODELO)) == ()


def test_the_live_corpus_carries_no_edition_restating_an_inherited_row(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Held by identity: no modelo restates, and 131's judged rows are differences, not copies."""
    findings = screen_authority(authority, ("303", _MODELO))
    assert restating_modelos(findings) == ()
    kinds = {item.kind for item in judge_definition(authority.modelo(_MODELO), modelo_id=_MODELO)}
    assert "restated_unchanged" not in kinds
    assert "stated_difference" in kinds


def test_a_predecessor_row_taking_its_editions_ordenes_re_defaults_on_inheriting(
    inheritance: _Inheritance,
) -> None:
    """A row that stated no legal references takes the ordenes of the edition it lands in.

    The loader proves it on the same tree: with the 2024 row's own references
    dropped it carries 2024's ordenes, and the row 2025 inherits carries 2025's.
    Stating that re-defaulted value is therefore restatement, while stating the
    predecessor's ordenes is a difference.
    """
    predecessor = inheritance.redefaulted.revisions[_PREDECESSOR]
    successor = inheritance.redefaulted.revisions[_SUCCESSOR]
    inherited = _row_of(inheritance.redefaulted, _PREDECESSOR, _ROW)
    row = inheritance.redefaulted_row
    assert inherited.legal_refs == predecessor.orden_aplicabilidad
    assert row.legal_refs == successor.orden_aplicabilidad
    assert row.legal_refs != inherited.legal_refs

    findings = definition_findings(_stating(inheritance.redefaulted, row), modelo_id=_MODELO)
    assert [(item.casilla, item.kind) for item in findings] == [(_ROW, "restated_unchanged")]

    kept = row.model_copy(update={"legal_refs": inherited.legal_refs})
    assert restatement_differences(kept, successor, inherited, predecessor) == ("legal_refs",)


def test_restatement_is_found_through_the_edition_tokens_not_in_spite_of_them(
    inheritance: _Inheritance,
) -> None:
    """A row named as restated may differ from its inherited row as written.

    Only edition restatement separates them - here a binding identifier carrying
    its own edition key - which is exactly what a raw comparison would have
    reported as a change. The screen names the row; the raw dumps disagree.
    """
    definition = inheritance.delta
    binding = inheritance.row.binding or "modelo-131-planted-binding"
    assert _SUCCESSOR not in binding and _PREDECESSOR not in binding, "the chosen binding already embeds an edition"

    predecessor = definition.revisions[_PREDECESSOR].model_copy(
        update={
            "casillas": tuple(
                item.model_copy(update={"binding": f"{binding}-{_PREDECESSOR}"}) if str(item.id) == _ROW else item
                for item in definition.revisions[_PREDECESSOR].casillas
            )
        }
    )
    row = inheritance.row.model_copy(update={"binding": f"{binding}-{_SUCCESSOR}", "inherited_from": None})
    planted = _with_rows(
        definition.model_copy(update={"revisions": {**definition.revisions, _PREDECESSOR: predecessor}}),
        tuple(row if str(item.id) == _ROW else item for item in definition.revisions[_SUCCESSOR].casillas),
    )
    successor = planted.revisions[_SUCCESSOR]
    planted_inherited = _row_of(planted, _PREDECESSOR, _ROW)

    assert row.model_dump() != planted_inherited.model_dump(), "the rows were already identical as written"
    assert _successor_judgements(planted)[_ROW].kind == "restated_unchanged"
    assert (
        inheritable_value(row, successor, inheriting=successor)["binding"]
        == inheritable_value(planted_inherited, predecessor, inheriting=successor)["binding"]
    )

    # Normalisation removes the edition token and nothing else: a binding
    # re-pointed at a different identifier is still a change.
    repointed = row.model_copy(update={"binding": f"{row.binding}-otro"})
    assert restatement_differences(repointed, successor, planted_inherited, predecessor) == ("binding",)


def test_every_edition_local_field_is_a_real_casilla_field() -> None:
    """A renamed field would silently stop being excluded and report every row changed."""
    assert set(CasillaDefinition.model_fields) >= EDITION_LOCAL_FIELDS | LINEAGE_CLAIM_FIELDS | {"inherited_from"}


def test_rows_marked_inherited_are_never_judged_and_the_marker_is_what_spares_them(
    inheritance: _Inheritance,
) -> None:
    """A delta edition's loaded rows include what it inherits; only the rows it states are judged."""
    successor = inheritance.delta.revisions[_SUCCESSOR]
    assert len(stated_casillas(successor)) == len(successor.casillas) - 1
    assert _ROW not in _successor_judgements(inheritance.delta)

    restating = _stating(inheritance.delta, inheritance.row)
    assert _successor_judgements(restating)[_ROW].kind == "restated_unchanged"


def test_a_stated_lineage_claim_is_a_statement_inheritance_cannot_reproduce(
    inheritance: _Inheritance,
) -> None:
    """An inherited row carries no lineage claim, so a row stating one differs even from an identical claim."""
    definition = inheritance.delta
    successor, predecessor = definition.revisions[_SUCCESSOR], definition.revisions[_PREDECESSOR]
    row = inheritance.row.model_copy(update={"inherited_from": None})
    inherited = _row_of(definition, _PREDECESSOR, _ROW)
    claims = {
        "continuidad_origin": CasillaLineageOrigin.GROUNDED,
        "continuidad_evidence": "Diseño de registro, campo 1.",
    }

    assert restatement_differences(row, successor, inherited, predecessor) == ()
    claimed = row.model_copy(update=claims)
    assert restatement_differences(claimed, successor, inherited.model_copy(update=claims), predecessor) == (
        "continuidad_evidence",
        "continuidad_origin",
    )


def test_source_refs_are_compared_net_of_each_editions_default_only_when_both_declare_one(
    inheritance: _Inheritance,
) -> None:
    """With both defaults declared, what remains is the row's own additions, and those must match."""
    definition = inheritance.delta
    row = inheritance.row.model_copy(update={"inherited_from": None})
    own, other = "aeat-instrucciones-own", "aeat-instrucciones-other"
    inherited = _row_of(definition, _PREDECESSOR, _ROW).model_copy(update={"source_refs": ("aeat-dr-2024", own)})
    with_defaults = (
        definition.revisions[_SUCCESSOR].model_copy(update={"casilla_source_refs": ("aeat-dr-2025",)}),
        definition.revisions[_PREDECESSOR].model_copy(update={"casilla_source_refs": ("aeat-dr-2024",)}),
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
    without_defaults = (
        definition.revisions[_SUCCESSOR].model_copy(update={"casilla_source_refs": ()}),
        definition.revisions[_PREDECESSOR].model_copy(update={"casilla_source_refs": ()}),
    )
    assert differences(row.model_copy(update={"source_refs": ("aeat-dr-2025", other)}), without_defaults) == ()


def test_a_minimal_delta_restating_its_whole_manifest_is_not_named(
    inheritance: _Inheritance,
) -> None:
    """The manifest does not inherit, so restating it must never make an edition non-minimal.

    The delta edition restates its completeness manifest in full - asserted
    first, so the proof cannot pass on an edition that happens to carry none -
    and inherits the one row it does not change. A screen spanning both families
    would name it; this one must not.
    """
    definition = inheritance.delta
    successor, predecessor = definition.revisions[_SUCCESSOR], definition.revisions[_PREDECESSOR]
    assert successor.completeness_manifest is not None
    assert len(stated_casillas(successor)) < len(successor.casillas)
    assert [(item.revision, item.basis) for item in edition_predecessors(definition)][1:3] == [
        (_PREDECESSOR, "declared"),
        (_SUCCESSOR, "declared"),
    ]
    assert definition_findings(definition, modelo_id=_MODELO) == ()

    # The sharpest form: a manifest identical to the one it would have
    # inherited, had the manifest inherited at all.
    assert predecessor.completeness_manifest is not None
    copied = successor.model_copy(update={"completeness_manifest": predecessor.completeness_manifest})
    planted = definition.model_copy(update={"revisions": {**definition.revisions, _SUCCESSOR: copied}})
    assert definition_findings(planted, modelo_id=_MODELO) == ()


def test_a_delta_restating_one_identical_row_is_named_and_stops_when_it_is_removed(
    inheritance: _Inheritance,
) -> None:
    """One restated row in an otherwise minimal delta is named, by row, and nothing else is.

    Then both removals of the defect: inheriting the row again, and changing it
    so it is a genuine statement rather than a copy.
    """
    restating = _stating(inheritance.delta, inheritance.row)
    findings = definition_findings(restating, modelo_id=_MODELO)
    assert [(item.revision, item.casilla, item.kind) for item in findings] == [(_SUCCESSOR, _ROW, "restated_unchanged")]
    assert definition_findings(inheritance.delta, modelo_id=_MODELO) == ()

    changed = _stating(inheritance.delta, inheritance.row.model_copy(update={"section": ("planted",)}))
    assert definition_findings(changed, modelo_id=_MODELO) == ()
    assert _successor_judgements(changed)[_ROW].detail == "differs in section"


def test_a_row_without_lineage_is_unchecked_never_minimal(inheritance: _Inheritance) -> None:
    """Stripping a restated row's lineage turns its verdict to unchecked, not to clean."""
    unlinked = inheritance.row.model_copy(update={"continuidad_id": None, "continuidad_origin": None})
    findings = definition_findings(_stating(inheritance.delta, unlinked), modelo_id=_MODELO)
    assert [(item.casilla, item.kind) for item in findings] == [(_ROW, "unchecked_no_lineage")]
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
    # The corpus compacts editions through storage baselines, and no row is
    # counted twice or dropped from the four row counts.
    assert census.rows_storage_reused > 0
    loaded = sum(
        len(revision.casillas)
        for modelo_id in modelo_ids
        for revision in authority.modelo(modelo_id).revisions.values()
    )
    assert loaded == (
        census.rows_in_root_editions + census.rows_storage_reused + census.rows_inherited + census.rows_judged
    )


def test_an_ambiguous_chain_in_the_predecessor_is_unchecked(inheritance: _Inheritance) -> None:
    """Two predecessor rows on one chain leave the inherited row undecided."""
    definition = inheritance.delta
    twin = _row_of(definition, _PREDECESSOR, _ROW)
    doubled = definition.revisions[_PREDECESSOR].model_copy(
        update={
            "casillas": (
                *definition.revisions[_PREDECESSOR].casillas,
                twin.model_copy(update={"id": f"{twin.id}-twin"}),
            )
        }
    )
    planted = _stating(
        definition.model_copy(update={"revisions": {**definition.revisions, _PREDECESSOR: doubled}}), inheritance.row
    )
    findings = definition_findings(planted, modelo_id=_MODELO)
    assert [(item.casilla, item.kind) for item in findings] == [(_ROW, "unchecked_ambiguous_lineage")]


def test_an_undeclared_edition_overlapping_its_neighbour_is_unchecked_unless_declared(
    inheritance: _Inheritance,
) -> None:
    """Overlapping editions may be parallel variants, so order alone cannot pair them.

    Every row the undeclaring edition states is reported unchecked; declaring
    the predecessor resolves it, and the restated row is then named.
    """
    restating = _stating(inheritance.delta, inheritance.row)
    predecessor, successor = restating.revisions[_PREDECESSOR], restating.revisions[_SUCCESSOR]
    # Simultaneity needs both a shared period and an intersecting validity window.
    overlapping = successor.model_copy(
        update={
            "predecessor": None,
            "period_selector": predecessor.period_selector,
            "valid_from": predecessor.valid_from,
            "valid_to": predecessor.valid_to,
        }
    )
    planted = restating.model_copy(update={"revisions": {**restating.revisions, _SUCCESSOR: overlapping}})
    undecidable = [item for item in definition_findings(planted, modelo_id=_MODELO) if item.revision == _SUCCESSOR]
    assert {item.kind for item in undecidable} == {"unchecked_predecessor_undecidable"}
    assert len(undecidable) == len(stated_casillas(successor))

    declared = overlapping.model_copy(update={"predecessor": DeclaredPredecessor(revision_id=predecessor.id)})
    resolved = definition_findings(
        restating.model_copy(update={"revisions": {**restating.revisions, _SUCCESSOR: declared}}), modelo_id=_MODELO
    )
    assert {item.kind for item in resolved} == {"restated_unchanged"}


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


#: A real modelo whose middle edition names no predecessor and hydrates every
#: casilla from its storage baseline, followed by an edition that inherits from
#: it by lineage. The storage edition authors no casilla of its own on disk.
_STORAGE_MODELO = "038"
_STORAGE_BASELINE = "2022-hasta-2024-05"
_STORAGE_EDITION = "2024-desde-06"
_LINEAGE_EDITION = "2025-y-siguientes"
_REUSED_ROW = "decl.ejercicio"
_OVERRIDDEN_ROW = "decl.tipo-declaracion"
_AUTHORED_ROW = "decl.planted-sin-continuidad"


def _storage_tree(destination: Path, *, overridden_section: str) -> Path:
    """Copy modelo 038 and make its storage edition author one row and override another.

    The override sets ``section`` on a baseline row, to the baseline's own value
    or to a different one; the authored row carries no ``continuidad_id``.
    Every other row the edition holds stays storage-reused.
    """
    bundled_root = Path(bundled_path("registry", "aeat"))
    registry_root = destination / "aeat"
    for catalogue in ("facts", "legal"):
        shutil.copytree(bundled_root / catalogue, registry_root / catalogue)
    modelo_dir = registry_root / "modelos" / _STORAGE_MODELO
    shutil.copytree(bundled_root / "modelos" / _STORAGE_MODELO, modelo_dir)
    edition_dir = modelo_dir / "revisions" / _STORAGE_EDITION
    manifest = edition_dir / "revision.toml"
    authored = manifest.read_text(encoding="utf-8")
    assert f'casilla_storage_baseline = "{_STORAGE_BASELINE}"' in authored, "the edition no longer reuses storage"
    assert "casilla_overrides" not in authored, "the storage edition now overrides casillas"
    assert not (edition_dir / "casillas").exists(), "the storage edition now authors casillas on disk"
    override = (
        f'\n[[revisions."{_STORAGE_EDITION}".casilla_overrides]]\n'
        f'selector = {{ revision = "{_STORAGE_BASELINE}", id = "{_OVERRIDDEN_ROW}" }}\n'
        f'fields = {{ section = ["{overridden_section}"] }}\n'
        "removed_fields = []\n"
    )
    manifest.write_text(authored + override, encoding="utf-8", newline="\n")
    (edition_dir / "casillas").mkdir()
    (edition_dir / "casillas" / "0001-declarations.toml").write_text(
        f'[[revisions."{_STORAGE_EDITION}".casillas]]\n'
        f'id = "{_AUTHORED_ROW}"\n'
        'number = "planted"\n'
        'section = ["declarante"]\n'
        'data_type = "text"\n'
        'input_kind = "informational"\n'
        'legal_refs = ["orden-hac-66-2002:art-1", "ley-58-2003:art-93"]\n',
        encoding="utf-8",
        newline="\n",
    )
    return modelo_dir


@dataclass(frozen=True, slots=True)
class _StorageReuse:
    """Modelo 038 as the loader materialises it with an authored row and an override on its storage edition.

    ``restating`` overrides the baseline row with the value it already has;
    ``changing`` overrides it with a different one.
    """

    restating: ModeloDefinition
    changing: ModeloDefinition


@pytest.fixture(scope="module")
def storage_reuse(tmp_path_factory: pytest.TempPathFactory) -> _StorageReuse:
    return _StorageReuse(
        restating=load_modelo_directory(
            _storage_tree(tmp_path_factory.mktemp("same"), overridden_section="declarante")
        ),
        changing=load_modelo_directory(_storage_tree(tmp_path_factory.mktemp("changed"), overridden_section="planted")),
    )


def _storage_edition_judgements(definition: ModeloDefinition) -> dict[str, RowJudgement]:
    return {
        item.casilla: item
        for item in judge_definition(definition, modelo_id=_STORAGE_MODELO)
        if item.revision == _STORAGE_EDITION
    }


def test_the_storage_edition_is_paired_with_its_baseline_by_validity_order(storage_reuse: _StorageReuse) -> None:
    """The edition names no predecessor, so the screen pairs it with the adjacent earlier edition."""
    definition = storage_reuse.restating
    revision = definition.revisions[_STORAGE_EDITION]
    assert not isinstance(revision.predecessor, DeclaredPredecessor)
    assert str(revision.casilla_storage_baseline) == _STORAGE_BASELINE
    assert [(item.revision, item.predecessor, item.basis) for item in edition_predecessors(definition)] == [
        (_STORAGE_BASELINE, None, "first_in_order"),
        (_STORAGE_EDITION, _STORAGE_BASELINE, "adjacent_in_order"),
        (_LINEAGE_EDITION, _STORAGE_EDITION, "declared"),
    ]


def test_a_storage_reused_row_is_never_judged_and_is_counted_as_storage_reused(storage_reuse: _StorageReuse) -> None:
    """A baseline row the edition neither authors nor overrides is carried, not stated."""
    definition = storage_reuse.restating
    revision = definition.revisions[_STORAGE_EDITION]
    reused = _row_of(definition, _STORAGE_EDITION, _REUSED_ROW)
    assert reused.inherited_from == _STORAGE_BASELINE
    assert [str(item.id) for item in storage_reused_casillas(revision)] == [_REUSED_ROW]
    assert _REUSED_ROW not in {str(item.id) for item in stated_casillas(revision)}
    assert _REUSED_ROW not in _storage_edition_judgements(definition)


def test_a_row_the_storage_edition_authors_is_judged_and_unlineaged_is_unchecked(
    storage_reuse: _StorageReuse,
) -> None:
    """Storage reuse spares only what the edition carries; a row it writes itself is judged."""
    definition = storage_reuse.restating
    authored = _row_of(definition, _STORAGE_EDITION, _AUTHORED_ROW)
    assert authored.inherited_from is None
    assert authored.continuidad_id is None
    judgement = _storage_edition_judgements(definition)[_AUTHORED_ROW]
    assert judgement.kind == "unchecked_no_lineage"
    assert judgement in definition_findings(definition, modelo_id=_STORAGE_MODELO)


def test_an_override_on_top_of_the_storage_baseline_is_judged_as_a_stated_row(storage_reuse: _StorageReuse) -> None:
    """The loader treats a patched baseline row as stated, so the screen judges it.

    Overriding a field with the value the baseline row already has states
    nothing new, and is named; overriding it with a different value is a
    legitimate statement.
    """
    for definition in (storage_reuse.restating, storage_reuse.changing):
        overridden = _row_of(definition, _STORAGE_EDITION, _OVERRIDDEN_ROW)
        assert overridden.inherited_from is None
        assert _OVERRIDDEN_ROW not in {
            str(item.id) for item in storage_reused_casillas(definition.revisions[_STORAGE_EDITION])
        }

    restated = _storage_edition_judgements(storage_reuse.restating)[_OVERRIDDEN_ROW]
    assert restated.kind == "restated_unchanged"
    assert restating_modelos(definition_findings(storage_reuse.restating, modelo_id=_STORAGE_MODELO)) == (
        _STORAGE_MODELO,
    )

    changed = _storage_edition_judgements(storage_reuse.changing)[_OVERRIDDEN_ROW]
    assert changed.kind == "stated_difference"
    assert changed.detail == "differs in section"


def test_the_census_counts_storage_reused_rows_apart_from_inherited_and_judged_rows(
    storage_reuse: _StorageReuse,
) -> None:
    """Every loaded row lands in exactly one count, and storage reuse is not lineage inheritance.

    The expected counts follow from the tree as built: the root edition's two
    rows; the storage edition's one carried row, its override and its authored
    row; and the lineage edition carrying all three of those down its declared
    predecessor.
    """
    definition = storage_reuse.restating
    census = definitions_census({_STORAGE_MODELO: definition})
    assert storage_reused_casillas(definition.revisions[_LINEAGE_EDITION]) == ()
    assert (census.editions, census.root_editions, census.declared_predecessor_editions) == (3, 1, 1)
    assert census.rows_in_root_editions == 2
    assert census.rows_storage_reused == 1
    assert census.rows_judged == 2
    assert census.rows_inherited == 3
    assert census.verdicts == {
        MinimalityVerdict.RESTATED_UNCHANGED: 1,
        MinimalityVerdict.UNCHECKED_NO_LINEAGE: 1,
    }
    loaded = sum(len(revision.casillas) for revision in definition.revisions.values())
    assert loaded == (
        census.rows_in_root_editions + census.rows_storage_reused + census.rows_inherited + census.rows_judged
    )
