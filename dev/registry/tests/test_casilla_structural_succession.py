"""Split/merge declarations withdraw identities without inheriting across them."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage_totality import unresolved_successor_rows
from cadrumo.domain.calculations.registry.casilla_structural_succession import (
    CasillaStructuralSuccession,
    structural_succession_failures,
)
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaConstraints
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    authored_revisions_where,
    filing_year_envelope,
)

from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ..compiler.validate_cross_revision_evolution import strict_continuity_evolution_failures
from ..compiler.validate_evidence import EvidenceValidator
from ..compiler.validate_revision_closure import validate_revision_reference_surfaces
from ..compiler.validate_semantic_roles import semantic_role_consistency_failures
from .test_revision_edition_materialisation import casilla, modelo_root, retirement, write_edition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Four consecutive planted editions, oldest first: the synthetic trees label them by their year.
_Y0, _Y1, _Y2, _Y3 = range(filing_year_envelope().horizon - 3, filing_year_envelope().horizon + 1)
_R0, _R1, _R2, _R3 = map(str, (_Y0, _Y1, _Y2, _Y3))

# Modelo 309 declares its structural successions on one authored edition: the one that follows the
# oldest design and precedes the editions that carry the representation change forward.
_M309_IDS = tuple(str(revision.id) for revision in authored_revisions("309"))
_M309_STRUCTURAL = str(
    authored_revisions_where("309", lambda revision: bool(revision.casilla_structural_successions))[0].id
)
_M309_BEFORE = _M309_IDS[_M309_IDS.index(_M309_STRUCTURAL) - 1]
_M309_AFTER = _M309_IDS[_M309_IDS.index(_M309_STRUCTURAL) + 1 :]


def casilla_structural_succession_relation(
    *, kind: str = "split", sources: tuple[str, ...] = ("combined",), targets: tuple[str, ...] = ("surname", "given")
) -> str:
    def quoted(values: tuple[str, ...]) -> str:
        return ", ".join(f'"{value}"' for value in values)

    return (
        f'[[revisions."{_R2}".casilla_structural_successions]]\n'
        'id = "name-structure"\n'
        f'kind = "{kind}"\n'
        f'from_revision = "{_R1}"\nto_revision = "{_R2}"\n'
        f"source_lineages = [{quoted(sources)}]\ntarget_lineages = [{quoted(targets)}]\n"
        'legal_refs = ["ley-58-2003:art-29"]\n'
        'from_source_refs = ["aeat-before"]\nto_source_refs = ["aeat-after"]\n'
        'evidence = "Paired official designs replace the combined surface with separately declared fields."\n'
    )


def tree(tmp_path: Path, *, delta: bool = True, merge: bool = False, relation: str | None = None) -> Path:
    root = modelo_root(tmp_path)
    sources = ("surname", "given") if merge else ("combined",)
    targets = ("combined",) if merge else ("surname", "given")
    write_edition(
        root,
        _R1,
        year=_Y1,
        casillas="".join(
            casilla(_R1, f"old-{index}", number=str(index), lineage=lineage) for index, lineage in enumerate(sources, 1)
        ),
        manifest_extra='continuidad_validation = "strict"\n',
    )
    write_edition(
        root,
        _R2,
        year=_Y2,
        casillas="".join(
            casilla(_R2, f"new-{index}", number=str(index), lineage=lineage) for index, lineage in enumerate(targets, 1)
        ),
        manifest_extra=f'predecessor = "{_R1}"\n' if delta else "",
    )
    directory = root / "revisions" / _R2 / "casilla_structural_successions"
    directory.mkdir()
    (directory / "0001-declarations.toml").write_text(
        relation
        if relation is not None
        else casilla_structural_succession_relation(
            kind="merge" if merge else "split", sources=sources, targets=targets
        ),
        encoding="utf-8",
    )
    return root


@pytest.mark.parametrize("merge", [False, True])
@pytest.mark.parametrize("delta", [False, True])
def test_structural_boundary_serializes_and_resolves_without_identity_inheritance(
    tmp_path: Path, merge: bool, delta: bool
) -> None:
    root = tree(tmp_path, merge=merge, delta=delta)
    modelo = load_modelo_directory(root)
    successor = modelo.revisions[_R2]
    assert len(successor.casillas) == (1 if merge else 2)
    assert all(row.inherited_from is None for row in successor.casillas)
    assert unresolved_successor_rows(modelo) == ()
    assert strict_continuity_evolution_failures(modelo) == ()
    relation = successor.casilla_structural_successions[0]
    assert CasillaStructuralSuccession.model_validate_json(relation.model_dump_json()) == relation
    # New identities cannot borrow the source's occurrence or continuity locale.
    for row in successor.casillas:
        assert _R1 not in str(row.localization_keys)
        forbidden = "combined" if not merge else "surname"
        assert forbidden not in str(row.localization_keys)


@pytest.mark.parametrize(
    "replacement",
    [
        ('source_lineages = ["combined"]', 'source_lineages = ["unknown"]'),
        ('target_lineages = ["surname", "given"]', 'target_lineages = ["surname", "unknown"]'),
        (f'from_revision = "{_R1}"', f'from_revision = "{_R2}"'),
        (f'to_revision = "{_R2}"', f'to_revision = "{_R3}"'),
        ('source_lineages = ["combined"]', 'source_lineages = ["combined", "combined"]'),
        ('target_lineages = ["surname", "given"]', 'target_lineages = ["combined", "given"]'),
        ('kind = "split"', 'kind = "merge"'),
        ('from_source_refs = ["aeat-before"]', "from_source_refs = []"),
        ('to_source_refs = ["aeat-after"]', "to_source_refs = []"),
    ],
)
def test_invalid_boundary_or_endpoint_refuses(tmp_path: Path, replacement: tuple[str, str]) -> None:
    root = tree(tmp_path, relation=casilla_structural_succession_relation().replace(*replacement))
    with pytest.raises((RegistryError, ValueError)):
        load_modelo_directory(root)


def test_overlapping_ownership_refuses(tmp_path: Path) -> None:
    root = tree(
        tmp_path,
        relation=casilla_structural_succession_relation()
        + casilla_structural_succession_relation().replace('id = "name-structure"', 'id = "duplicate"'),
    )
    with pytest.raises(RegistryError, match="overlapping"):
        load_modelo_directory(root)


def test_retirement_cannot_duplicate_structural_withdrawal(tmp_path: Path) -> None:
    root = tree(tmp_path)
    directory = root / "revisions" / _R2 / "casilla_continuidad_evolutions"
    directory.mkdir()
    (directory / "0001-declarations.toml").write_text(
        retirement(_R2, lineage="combined", from_revision=_R1), encoding="utf-8"
    )
    with pytest.raises(RegistryError, match="conflicting single-chain"):
        load_modelo_directory(root)


@pytest.mark.parametrize("origin", ["grounded", "seeded", "new_on_form", "predecessor_edition_silent"])
def test_structural_target_cannot_claim_continuation_or_novelty(tmp_path: Path, origin: str) -> None:
    root = tree(tmp_path)
    fragment = root / "revisions" / _R2 / "casillas" / "0001-casillas.toml"
    fragment.write_text(
        fragment.read_text(encoding="utf-8").replace(
            'continuidad_id = "surname"',
            f'continuidad_id = "surname"\ncontinuidad_origin = "{origin}"\ncontinuidad_evidence = "Evidence"',
        ),
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="structural targets"):
        load_modelo_directory(root)


def test_relationship_never_inherits_into_grandchild(tmp_path: Path) -> None:
    root = tree(tmp_path)
    write_edition(root, _R3, year=_Y3, casillas="", manifest_extra=f'predecessor = "{_R2}"\n')
    modelo = load_modelo_directory(root)
    assert modelo.revisions[_R3].casilla_structural_successions == ()
    assert len(modelo.revisions[_R3].casillas) == 2
    assert unresolved_successor_rows(modelo) == ()


def test_one_to_one_and_many_to_many_are_not_structural_shapes() -> None:
    payload: dict[str, object] = dict(
        id="invalid",
        kind="split",
        from_revision=_R1,
        to_revision=_R2,
        source_lineages=("a",),
        target_lineages=("b",),
        legal_refs=("ley-58-2003:art-29",),
        from_source_refs=("aeat-before",),
        to_source_refs=("aeat-after",),
        evidence="Evidence",
    )
    with pytest.raises(ValidationError, match="one-to-many"):
        CasillaStructuralSuccession.model_validate(payload)
    payload.update({"source_lineages": ("a", "c"), "target_lineages": ("b", "d")})
    with pytest.raises(ValidationError, match="one-to-many"):
        CasillaStructuralSuccession.model_validate(payload)


def test_source_cannot_reappear_and_target_cannot_preexist(tmp_path: Path) -> None:
    root = tree(tmp_path)
    modelo = load_modelo_directory(root)
    old, new = modelo.revisions[_R1], modelo.revisions[_R2]
    continued = new.model_copy(update={"casillas": (*new.casillas, old.casillas[0])})
    invalid = modelo.model_copy(update={"revisions": {**modelo.revisions, _R2: continued}})
    assert any("must end" in failure for failure in structural_succession_failures(invalid))
    assert unresolved_successor_rows(invalid)
    existing = old.model_copy(update={"casillas": (*old.casillas, new.casillas[0])})
    invalid = modelo.model_copy(update={"revisions": {**modelo.revisions, _R1: existing}})
    assert any("must begin" in failure for failure in structural_succession_failures(invalid))


def test_relationship_does_not_select_a_predecessor(tmp_path: Path) -> None:
    root = tree(tmp_path, delta=False)
    modelo = load_modelo_directory(root)
    assert modelo.revisions[_R2].predecessor is None
    write_edition(root, _R0, year=_Y0, casillas="")
    manifest = root / "revisions" / _R2 / "revision.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + f'predecessor = "{_R0}"\n', encoding="utf-8")
    with pytest.raises(RegistryError):
        load_modelo_directory(root)


def test_committed_309_structural_membership_and_country_wire_width() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "309"))
    assert len(modelo.revisions[_M309_STRUCTURAL].casilla_structural_successions) == 3
    assert unresolved_successor_rows(modelo) == ()
    assert semantic_role_consistency_failures((modelo,)) == ()
    old = modelo.revisions[_M309_BEFORE]
    field = next(
        field
        for layout in old.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla_id == "wire.transmitente-pais-texto"
    )
    assert field.length == 14
    assert render_fixed_width_export_field(field, "FRANCIA") == "FRANCIA       "
    with pytest.raises(RegistryError, match="exceeds length 14"):
        render_fixed_width_export_field(field, "X" * 15)


def test_representation_path_requires_every_changed_edge() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "309"))
    assert semantic_role_consistency_failures((modelo,)) == ()
    revision = modelo.revisions[_M309_STRUCTURAL]
    ungrounded = revision.model_copy(
        update={
            "casilla_continuidad_evolutions": tuple(
                evolution
                for evolution in revision.casilla_continuidad_evolutions
                if evolution.evolution_kind != "representation_evolved"
            )
        }
    )
    invalid = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: ungrounded}})
    failures = semantic_role_consistency_failures((invalid,))
    for later in _M309_AFTER:
        assert any(later in failure and "data_type" in failure for failure in failures)


@pytest.mark.parametrize(
    "constraint",
    [
        {"sign": "non_negative"},
        {"min_value": "0"},
        {"max_value": "100"},
        {"pattern": "^[A-Z]+$"},
        {"enum": ("FR", "DE")},
        {"max_length": 14},
    ],
)
def test_representation_does_not_waive_value_constraints(constraint: dict[str, object]) -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "309"))
    revision = modelo.revisions[_M309_BEFORE]
    constraints = CasillaConstraints.model_validate(
        {**constraint, "legal_refs": ("ley-37-1992:art-161",), "source_refs": ("aeat-dr-309-2004",)}
    )
    changed = revision.model_copy(
        update={
            "casillas": tuple(
                row.model_copy(update={"constraints": constraints})
                if row.continuidad_id == "transmitente-pais"
                else row
                for row in revision.casillas
            )
        }
    )
    invalid = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: changed}})
    assert any("constraints incompatible" in failure for failure in semantic_role_consistency_failures((invalid,)))


@pytest.mark.parametrize("defect", ["none", "swapped", "unrelated-modelo", "wrong-period", "multi-edition"])
def test_structural_endpoint_sources_match_their_own_context(defect: str) -> None:
    root = bundled_path("registry", "aeat")
    modelo = load_modelo_directory(root / "modelos" / "309")
    catalogues = load_shared_catalogues(root)
    revision = modelo.revisions[_M309_STRUCTURAL]
    relations = revision.casilla_structural_successions
    sources = dict(catalogues.sources)
    if defect == "swapped":
        relations = tuple(
            relation.model_copy(
                update={
                    "from_source_refs": relation.to_source_refs,
                    "to_source_refs": relation.from_source_refs,
                }
            )
            for relation in relations
        )
    elif defect == "unrelated-modelo":
        relations = tuple(
            relation.model_copy(update={"to_source_refs": ("aeat-dr-390-2021",)}) for relation in relations
        )
    elif defect == "wrong-period":
        # An open-ended edition is still in force, so it serves every exercise up to the support horizon.
        last_exercise = filing_year_envelope().horizon if revision.valid_to is None else revision.valid_to.year
        sources["aeat-dr-309-2016"] = sources["aeat-dr-309-2016"].model_copy(
            update={
                # The structural edition serves 1T-4T, 01-12 and 0A; an instalment clave is none of them.
                "period_selector": PeriodSelector(
                    years=tuple(range(revision.valid_from.year, last_exercise + 1)), periods=("1P",)
                ),
            }
        )
    elif defect == "multi-edition":
        # One genuine spanning document can ground both sides; publication
        # need not equal either edition's date. Keep the enrolled source id.
        sources["aeat-dr-309-2004"] = sources["aeat-dr-309-2004"].model_copy(
            update={
                "applies_from": modelo.revisions[_M309_BEFORE].valid_from,
                "applies_to": revision.valid_to,
                "published_at": modelo.revisions[_M309_BEFORE].valid_from - timedelta(days=31),
            }
        )
        relations = tuple(
            relation.model_copy(update={"to_source_refs": relation.from_source_refs}) for relation in relations
        )
    changed = revision.model_copy(update={"casilla_structural_successions": relations})
    candidate = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: changed}})
    failures: list[str] = []
    validate_revision_reference_surfaces(
        failures,
        prefix=f"309/{_M309_STRUCTURAL}",
        modelo=candidate,
        revision=changed,
        legal_refs=catalogues.legal,
        source_refs=sources,
        evidence=EvidenceValidator(legal_refs=catalogues.legal, source_refs=sources, source_root=bundled_path()),
    )
    if defect in {"none", "multi-edition"}:
        assert failures == []
    elif defect == "swapped":
        assert sum("validity window" in failure for failure in failures) == 6
    elif defect == "unrelated-modelo":
        assert any("not enrolled for this modelo" in failure for failure in failures)
    else:
        assert any("filing periods" in failure for failure in failures)
