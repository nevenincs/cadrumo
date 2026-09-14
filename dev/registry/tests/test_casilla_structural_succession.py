"""Split/merge declarations withdraw identities without inheriting across them."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

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

from ..compiler._validate_cross_revision_evolution import strict_continuity_evolution_failures
from ..compiler._validate_revision_closure import validate_revision_reference_surfaces
from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ..compiler.validate_evidence import EvidenceValidator
from ..compiler.validate_semantic_roles import semantic_role_consistency_failures
from .test_revision_edition_materialisation import _casilla, _modelo_root, _retirement, _write_edition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _relation(
    *, kind: str = "split", sources: tuple[str, ...] = ("combined",), targets: tuple[str, ...] = ("surname", "given")
) -> str:
    def quoted(values: tuple[str, ...]) -> str:
        return ", ".join(f'"{value}"' for value in values)

    return (
        '[[revisions."2025".casilla_structural_successions]]\n'
        'id = "name-structure"\n'
        f'kind = "{kind}"\n'
        'from_revision = "2024"\nto_revision = "2025"\n'
        f"source_lineages = [{quoted(sources)}]\ntarget_lineages = [{quoted(targets)}]\n"
        'legal_refs = ["ley-58-2003:art-29"]\n'
        'from_source_refs = ["aeat-before"]\nto_source_refs = ["aeat-after"]\n'
        'evidence = "Paired official designs replace the combined surface with separately declared fields."\n'
    )


def _tree(tmp_path: Path, *, delta: bool = True, merge: bool = False, relation: str | None = None) -> Path:
    root = _modelo_root(tmp_path)
    sources = ("surname", "given") if merge else ("combined",)
    targets = ("combined",) if merge else ("surname", "given")
    _write_edition(
        root,
        "2024",
        year=2024,
        casillas="".join(
            _casilla("2024", f"old-{index}", number=str(index), lineage=lineage)
            for index, lineage in enumerate(sources, 1)
        ),
        manifest_extra='continuidad_validation = "strict"\n',
    )
    _write_edition(
        root,
        "2025",
        year=2025,
        casillas="".join(
            _casilla("2025", f"new-{index}", number=str(index), lineage=lineage)
            for index, lineage in enumerate(targets, 1)
        ),
        manifest_extra='predecessor = "2024"\n' if delta else "",
    )
    directory = root / "revisions" / "2025" / "casilla_structural_successions"
    directory.mkdir()
    (directory / "0001-declarations.toml").write_text(
        relation
        if relation is not None
        else _relation(kind="merge" if merge else "split", sources=sources, targets=targets),
        encoding="utf-8",
    )
    return root


@pytest.mark.parametrize("merge", [False, True])
@pytest.mark.parametrize("delta", [False, True])
def test_structural_boundary_serializes_and_resolves_without_identity_inheritance(
    tmp_path: Path, merge: bool, delta: bool
) -> None:
    root = _tree(tmp_path, merge=merge, delta=delta)
    modelo = load_modelo_directory(root)
    successor = modelo.revisions["2025"]
    assert len(successor.casillas) == (1 if merge else 2)
    assert all(row.inherited_from is None for row in successor.casillas)
    assert unresolved_successor_rows(modelo) == ()
    assert strict_continuity_evolution_failures(modelo) == ()
    relation = successor.casilla_structural_successions[0]
    assert CasillaStructuralSuccession.model_validate_json(relation.model_dump_json()) == relation
    # New identities cannot borrow the source's occurrence or continuity locale.
    for row in successor.casillas:
        assert "2024" not in str(row.localization_keys)
        forbidden = "combined" if not merge else "surname"
        assert forbidden not in str(row.localization_keys)


@pytest.mark.parametrize(
    "replacement",
    [
        ('source_lineages = ["combined"]', 'source_lineages = ["unknown"]'),
        ('target_lineages = ["surname", "given"]', 'target_lineages = ["surname", "unknown"]'),
        ('from_revision = "2024"', 'from_revision = "2025"'),
        ('to_revision = "2025"', 'to_revision = "2026"'),
        ('source_lineages = ["combined"]', 'source_lineages = ["combined", "combined"]'),
        ('target_lineages = ["surname", "given"]', 'target_lineages = ["combined", "given"]'),
        ('kind = "split"', 'kind = "merge"'),
        ('from_source_refs = ["aeat-before"]', "from_source_refs = []"),
        ('to_source_refs = ["aeat-after"]', "to_source_refs = []"),
    ],
)
def test_invalid_boundary_or_endpoint_refuses(tmp_path: Path, replacement: tuple[str, str]) -> None:
    root = _tree(tmp_path, relation=_relation().replace(*replacement))
    with pytest.raises((RegistryError, ValueError)):
        load_modelo_directory(root)


def test_overlapping_ownership_refuses(tmp_path: Path) -> None:
    root = _tree(tmp_path, relation=_relation() + _relation().replace('id = "name-structure"', 'id = "duplicate"'))
    with pytest.raises(RegistryError, match="overlapping"):
        load_modelo_directory(root)


def test_retirement_cannot_duplicate_structural_withdrawal(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    directory = root / "revisions" / "2025" / "casilla_continuidad_evolutions"
    directory.mkdir()
    (directory / "0001-declarations.toml").write_text(
        _retirement("2025", lineage="combined", from_revision="2024"), encoding="utf-8"
    )
    with pytest.raises(RegistryError, match="conflicting single-chain"):
        load_modelo_directory(root)


@pytest.mark.parametrize("origin", ["grounded", "seeded", "new_on_form", "predecessor_edition_silent"])
def test_structural_target_cannot_claim_continuation_or_novelty(tmp_path: Path, origin: str) -> None:
    root = _tree(tmp_path)
    fragment = root / "revisions" / "2025" / "casillas" / "0001-casillas.toml"
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
    root = _tree(tmp_path)
    _write_edition(root, "2026", year=2026, casillas="", manifest_extra='predecessor = "2025"\n')
    modelo = load_modelo_directory(root)
    assert modelo.revisions["2026"].casilla_structural_successions == ()
    assert len(modelo.revisions["2026"].casillas) == 2
    assert unresolved_successor_rows(modelo) == ()


def test_one_to_one_and_many_to_many_are_not_structural_shapes() -> None:
    payload = dict(
        id="invalid",
        kind="split",
        from_revision="2024",
        to_revision="2025",
        source_lineages=("a",),
        target_lineages=("b",),
        legal_refs=("ley-58-2003:art-29",),
        from_source_refs=("aeat-before",),
        to_source_refs=("aeat-after",),
        evidence="Evidence",
    )
    with pytest.raises(RegistryError, match="one-to-many"):
        CasillaStructuralSuccession.model_validate(payload)
    payload.update(source_lineages=("a", "c"), target_lineages=("b", "d"))
    with pytest.raises(RegistryError, match="one-to-many"):
        CasillaStructuralSuccession.model_validate(payload)


def test_source_cannot_reappear_and_target_cannot_preexist(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    modelo = load_modelo_directory(root)
    old, new = modelo.revisions["2024"], modelo.revisions["2025"]
    continued = new.model_copy(update={"casillas": (*new.casillas, old.casillas[0])})
    invalid = modelo.model_copy(update={"revisions": {**modelo.revisions, "2025": continued}})
    assert any("must end" in failure for failure in structural_succession_failures(invalid))
    assert unresolved_successor_rows(invalid)
    existing = old.model_copy(update={"casillas": (*old.casillas, new.casillas[0])})
    invalid = modelo.model_copy(update={"revisions": {**modelo.revisions, "2024": existing}})
    assert any("must begin" in failure for failure in structural_succession_failures(invalid))


def test_relationship_does_not_select_a_predecessor(tmp_path: Path) -> None:
    root = _tree(tmp_path, delta=False)
    modelo = load_modelo_directory(root)
    assert modelo.revisions["2025"].predecessor is None
    _write_edition(root, "2023", year=2023, casillas="")
    manifest = root / "revisions" / "2025" / "revision.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + 'predecessor = "2023"\n', encoding="utf-8")
    with pytest.raises(RegistryError):
        load_modelo_directory(root)


def test_committed_309_structural_membership_and_country_wire_width() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "309"))
    assert len(modelo.revisions["2016-2017"].casilla_structural_successions) == 3
    assert unresolved_successor_rows(modelo) == ()
    assert semantic_role_consistency_failures((modelo,)) == ()
    old = modelo.revisions["2004-2015"]
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
    revision = modelo.revisions["2016-2017"]
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
    assert any("2018-2022" in failure and "data_type" in failure for failure in failures)
    assert any("2023-y-siguientes" in failure and "data_type" in failure for failure in failures)


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
    revision = modelo.revisions["2004-2015"]
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
    revision = modelo.revisions["2016-2017"]
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
        sources["aeat-dr-309-2016"] = sources["aeat-dr-309-2016"].model_copy(
            update={
                "period_selector": PeriodSelector(years=(2016, 2017), periods=("0A",)),
            }
        )
    elif defect == "multi-edition":
        # One genuine spanning document can ground both sides; publication
        # need not equal either edition's date. Keep the enrolled source id.
        sources["aeat-dr-309-2004"] = sources["aeat-dr-309-2004"].model_copy(
            update={
                "applies_from": date(2004, 1, 1),
                "applies_to": date(2017, 12, 31),
                "published_at": date(2003, 12, 1),
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
        prefix="309/2016-2017",
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
