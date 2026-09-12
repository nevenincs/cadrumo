"""Behaviour of the modelo-anchored edition-year collapse in the identifier rename tool.

Every case builds an isolated temporary registry tree seeded from a real modelo
-- 232, whose two editions spell the same binding as ``modelo-232-2016.page_01...``
and ``modelo-232-2018.page_01...`` and ground each row in its own edition's
diseno, and 720, whose edition declares ``valid_from = 2012`` while its
identifiers key on 2013 -- so the contributor's working tree is never written and
the detector teeth are proven on real manifests rather than on a patched module.

The manifests are copied verbatim, so the years the rule anchors on and the
horizon an open-ended selector is enumerated to are the ones the registry
actually declares rather than values this test invents.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ..rename_formula_binding_identifiers import (
    REGISTRY_MODELOS_ROOT,
    FamilyDefaultUnsupportedError,
    GeneratedExportTreeStaleError,
    _missing_family_default_fields,
    apply_collapse,
    bootstrap_family_default,
    collapse_edition_year,
    edition_year_set,
    modelo_declarations,
    plan_edition_year_collapse,
    valid_from_years,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

SEED_MODELO = "232"
OLD_EDITION = "2016-2017"
NEW_EDITION = "2018-y-siguientes"
OLD_DISENO = "aeat-dr-232-2016"
NEW_DISENO = "aeat-dr-232-2018"


def _declaration(edition: str, identifier: str, refs: tuple[str, ...]) -> str:
    """Render one binding fragment in the shape modelo 232 authors."""
    rendered = ", ".join(f'"{ref}"' for ref in refs)
    return (
        f'[[revisions."{edition}".bindings]]\n'
        f'id = "{identifier}"\n'
        'provider = { kind = "manual_input", record = "page_01", field = "vinculada-1-nif", '
        'offset = 144, length = 15, data_type = "text" }\n'
        'value = { data_type = "text", channel = "text" }\n'
        'legal_refs = ["orden-hfp-816-2017:art-3"]\n'
        f"source_refs = [{rendered}]\n"
    )


def _seed(tmp_path: Path, modelo: str, editions: tuple[str, ...]) -> Path:
    """Copy a modelo's edition manifests, and the registry's year promise, into an isolated root."""
    registry_root = tmp_path / "aeat"
    (registry_root / "legal").mkdir(parents=True)
    shutil.copy2(
        REGISTRY_MODELOS_ROOT.parent / "legal" / "supported-filing-years.toml",
        registry_root / "legal" / "supported-filing-years.toml",
    )
    for edition in editions:
        edition_dir = registry_root / "modelos" / modelo / "revisions" / edition
        (edition_dir / "bindings").mkdir(parents=True)
        manifest = (REGISTRY_MODELOS_ROOT / modelo / "revisions" / edition / "revision.toml").read_text(
            encoding="utf-8"
        )
        # Any family default the live corpus has since lifted is stripped, so
        # these cases exercise the BOOTSTRAP path whatever state the corpus is
        # in. A fixture that inherits a declared default silently stops testing
        # the inference it was written for; the declared path has its own case
        # below, which puts the key back explicitly.
        manifest = "".join(
            line
            for line in manifest.splitlines(keepends=True)
            if not line.startswith(("binding_source_refs", "formula_source_refs"))
        )
        (edition_dir / "revision.toml").write_text(manifest, encoding="utf-8", newline="\n")
    return registry_root / "modelos"


def _seed_232(tmp_path: Path) -> Path:
    return _seed(tmp_path, SEED_MODELO, (OLD_EDITION, NEW_EDITION))


def _write_row(modelos_root: Path, edition: str, year: str, slug: str, refs: tuple[str, ...]) -> Path:
    """Seed one binding fragment under an edition, returning its path."""
    path = modelos_root / SEED_MODELO / "revisions" / edition / "bindings" / f"{slug}-{year}.toml"
    path.write_text(_declaration(edition, f"modelo-232-{year}.page_01.{slug}", refs), encoding="utf-8")
    return path


def _write_pair(modelos_root: Path, slug: str, *, old: tuple[str, ...], new: tuple[str, ...]) -> None:
    """Seed a 2016/2018 counterpart pair of the same binding."""
    _write_row(modelos_root, OLD_EDITION, "2016", slug, old)
    _write_row(modelos_root, NEW_EDITION, "2018", slug, new)


def test_valid_from_years_come_from_the_manifest_not_the_directory_name(tmp_path: Path) -> None:
    """Modelo 720's edition is named ``2013-y-siguientes`` and declares ``valid_from = 2012``."""
    modelos_root = _seed(tmp_path, "720", ("2013-y-siguientes",))

    assert valid_from_years(modelos_root / "720") == {"2013-y-siguientes": "2012"}


def test_an_admitted_filing_year_joins_the_year_set(tmp_path: Path) -> None:
    """720's open-ended selector admits 2013, so ``modelo-720-2013.*`` is in reach of the collapse."""
    modelos_root = _seed(tmp_path, "720", ("2013-y-siguientes",))

    years = edition_year_set(modelos_root / "720", modelos_root)

    assert "2012" in years and "2013" in years
    assert collapse_edition_year("modelo-720-2013.type_1.1-1.tipo-de-registro", "720", years) == (
        "modelo-720.type_1.1-1.tipo-de-registro"
    )
    # The horizon is a declaration, not the clock: it stops at the last filing
    # year the registry's own promise names.
    assert max(years) == "2026"
    assert "2027" not in years


def test_a_pair_differing_only_in_its_edition_diseno_collapses_and_lifts(tmp_path: Path) -> None:
    """The 232 shape: identical rows whose only difference is each edition's own diseno reference."""
    modelos_root = _seed_232(tmp_path)
    _write_pair(modelos_root, "144-158.vinculada-1-nif", old=(OLD_DISENO,), new=(NEW_DISENO,))
    _write_pair(modelos_root, "159-159.vinculada-1-fjo", old=(OLD_DISENO,), new=(NEW_DISENO,))

    plan = plan_edition_year_collapse(SEED_MODELO, modelos_root)

    assert plan.refusals == []
    assert plan.collapsed_count == 4
    assert plan.renames["modelo-232-2016.page_01.144-158.vinculada-1-nif"] == (
        "modelo-232.page_01.144-158.vinculada-1-nif"
    )
    assert plan.manifest_writes == {
        ("bindings", OLD_EDITION): (OLD_DISENO,),
        ("bindings", NEW_EDITION): (NEW_DISENO,),
    }


def test_a_differing_non_edition_reference_still_refuses(tmp_path: Path) -> None:
    """Lifting removes the edition's own diseno and nothing else, so a further difference still refuses."""
    modelos_root = _seed_232(tmp_path)
    _write_pair(modelos_root, "144-158.vinculada-1-nif", old=(OLD_DISENO,), new=(NEW_DISENO,))
    _write_pair(
        modelos_root,
        "159-159.vinculada-1-fjo",
        old=(OLD_DISENO, "aeat-instruccion-a"),
        new=(NEW_DISENO, "aeat-instruccion-b"),
    )

    plan = plan_edition_year_collapse(SEED_MODELO, modelos_root)

    assert plan.collapsed_count == 2
    assert "modelo-232-2016.page_01.144-158.vinculada-1-nif" in plan.renames
    assert len(plan.refusals) == 1
    assert "modelo-232.page_01.159-159.vinculada-1-fjo" in plan.refusals[0]
    assert "declarations differ after the collapse" in plan.refusals[0]


def test_a_shared_reference_is_not_edition_scoped_and_is_never_lifted(tmp_path: Path) -> None:
    """A reference both editions state is shared vocabulary, not one edition's own grounding."""
    modelos_root = _seed_232(tmp_path)
    _write_pair(modelos_root, "144-158.vinculada-1-nif", old=("aeat-shared",), new=("aeat-shared",))

    declarations = modelo_declarations(modelos_root / SEED_MODELO)

    assert bootstrap_family_default(declarations, OLD_EDITION) is None
    plan = plan_edition_year_collapse(SEED_MODELO, modelos_root)
    assert plan.manifest_writes == {}
    assert plan.collapsed_count == 2


def test_a_legal_norm_year_never_fires(tmp_path: Path) -> None:
    """A year carried by a norm reference rather than by this modelo's own prefix is untouched."""
    modelos_root = _seed_232(tmp_path)
    years = edition_year_set(modelos_root / SEED_MODELO, modelos_root)

    assert collapse_edition_year("ley-35-2006-base-liquidable", SEED_MODELO, years) is None
    assert collapse_edition_year("modelo-232.rd-1624-1992.art-71-importe", SEED_MODELO, years) is None
    assert collapse_edition_year("modelo-232-2016-portal", SEED_MODELO, years) == "modelo-232-portal"


def test_a_year_no_edition_admits_never_fires(tmp_path: Path) -> None:
    """2009 precedes every year modelo 232's editions declare or admit."""
    modelos_root = _seed_232(tmp_path)
    identifier = "modelo-232-2009.page_01.144-158.vinculada-1-nif"
    _write_row(modelos_root, OLD_EDITION, "2009", "144-158.vinculada-1-nif", (OLD_DISENO,))

    years = edition_year_set(modelos_root / SEED_MODELO, modelos_root)

    assert "2009" not in years
    assert collapse_edition_year(identifier, SEED_MODELO, years) is None
    assert identifier not in plan_edition_year_collapse(SEED_MODELO, modelos_root).renames


def test_apply_tracks_whether_the_typed_manifest_field_exists(tmp_path: Path) -> None:
    """A lift is written only once ``ModeloRevision`` declares the key the loader would then read."""
    modelos_root = _seed_232(tmp_path)
    _write_pair(modelos_root, "144-158.vinculada-1-nif", old=(OLD_DISENO,), new=(NEW_DISENO,))
    plan = plan_edition_year_collapse(SEED_MODELO, modelos_root)
    assert plan.manifest_writes

    manifest = modelos_root / SEED_MODELO / "revisions" / OLD_EDITION / "revision.toml"
    if _missing_family_default_fields():
        with pytest.raises(FamilyDefaultUnsupportedError):
            apply_collapse(plan, modelos_root, tmp_path / "mappings")
        assert "binding_source_refs" not in manifest.read_text(encoding="utf-8")
        return

    apply_collapse(plan, modelos_root, tmp_path / "mappings")
    assert f'binding_source_refs = ["{OLD_DISENO}"]' in manifest.read_text(encoding="utf-8")
    fragment = modelos_root / SEED_MODELO / "revisions" / OLD_EDITION / "bindings"
    text = next(iter(sorted(fragment.glob("*.toml")))).read_text(encoding="utf-8")
    assert 'id = "modelo-232.page_01.144-158.vinculada-1-nif"' in text
    assert "source_refs" not in text


def test_a_declared_manifest_default_is_used_and_writes_no_manifest(tmp_path: Path) -> None:
    """Once an edition declares its family default, the lift is a read, not a write."""
    modelos_root = _seed_232(tmp_path)
    _write_pair(modelos_root, "144-158.vinculada-1-nif", old=(OLD_DISENO,), new=(NEW_DISENO,))
    for edition, diseno in ((OLD_EDITION, OLD_DISENO), (NEW_EDITION, NEW_DISENO)):
        manifest = modelos_root / SEED_MODELO / "revisions" / edition / "revision.toml"
        text = manifest.read_text(encoding="utf-8").splitlines(keepends=True)
        text.insert(1, f'binding_source_refs = ["{diseno}"]\n')
        manifest.write_text("".join(text), encoding="utf-8", newline="\n")

    plan = plan_edition_year_collapse(SEED_MODELO, modelos_root)

    assert plan.refusals == []
    assert plan.collapsed_count == 2
    assert plan.family_defaults[("bindings", OLD_EDITION)] == (OLD_DISENO,)
    assert plan.manifest_writes == {}
    # Nothing to lift means nothing to gate on, so this plan applies today.
    touched = apply_collapse(plan, modelos_root, tmp_path / "mappings")
    assert touched


def _export_fragment(modelos_root: Path, edition: str, quoted_binding: str) -> Path:
    """Seed a generated export fragment, in the single-quoted spelling the generator emits."""
    export_dir = modelos_root / SEED_MODELO / "revisions" / edition / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / "0001-fields.toml"
    path.write_text(
        f'[[revisions."{edition}".export_layouts.fields]]\n'
        "id = 'm232-2016.dr23201.f068'\n"
        f"binding = {quoted_binding}\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def test_a_generated_export_tree_quoting_a_renamed_id_refuses_to_apply(tmp_path: Path) -> None:
    """The rename and the republish must land together, so the collapse alone is refused."""
    modelos_root = _seed_232(tmp_path)
    _write_pair(modelos_root, "144-158.vinculada-1-nif", old=(OLD_DISENO,), new=(NEW_DISENO,))
    fragment = _export_fragment(modelos_root, OLD_EDITION, "'modelo-232-2016.page_01.144-158.vinculada-1-nif'")

    plan = plan_edition_year_collapse(SEED_MODELO, modelos_root)

    assert plan.stranded_export_trees == (OLD_EDITION,)
    with pytest.raises(GeneratedExportTreeStaleError) as refusal:
        apply_collapse(plan, modelos_root, tmp_path / "mappings")
    assert OLD_EDITION in str(refusal.value)
    # Nothing was written, including the source the collapse would have renamed.
    assert "modelo-232-2016.page_01.144-158.vinculada-1-nif" in fragment.read_text(encoding="utf-8")
    binding = modelos_root / SEED_MODELO / "revisions" / OLD_EDITION / "bindings"
    assert 'id = "modelo-232-2016.page_01.144-158.vinculada-1-nif"' in (
        next(iter(sorted(binding.glob("*.toml")))).read_text(encoding="utf-8")
    )


def test_an_export_tree_quoting_no_renamed_id_does_not_strand(tmp_path: Path) -> None:
    """The teeth: the gate keys on the tree's actual references, not on the mere presence of a tree."""
    modelos_root = _seed_232(tmp_path)
    _write_pair(modelos_root, "144-158.vinculada-1-nif", old=(OLD_DISENO,), new=(NEW_DISENO,))
    _export_fragment(modelos_root, OLD_EDITION, "'modelo-232-related-party-row-nif'")

    plan = plan_edition_year_collapse(SEED_MODELO, modelos_root)

    assert plan.stranded_export_trees == ()
    assert apply_collapse(plan, modelos_root, tmp_path / "mappings")


def test_acknowledging_the_republish_lets_the_collapse_apply(tmp_path: Path) -> None:
    """The gate is a sequencing guard, not a ban: an acknowledged republish still applies."""
    modelos_root = _seed_232(tmp_path)
    _write_pair(modelos_root, "144-158.vinculada-1-nif", old=(OLD_DISENO,), new=(NEW_DISENO,))
    _export_fragment(modelos_root, OLD_EDITION, "'modelo-232-2016.page_01.144-158.vinculada-1-nif'")

    plan = plan_edition_year_collapse(SEED_MODELO, modelos_root)
    touched = apply_collapse(plan, modelos_root, tmp_path / "mappings", export_republish_acknowledged=True)

    assert touched
    # The generated tree is still never rewritten by this tool; it is regenerated.
    export = modelos_root / SEED_MODELO / "revisions" / OLD_EDITION / "export" / "0001-fields.toml"
    assert "modelo-232-2016.page_01.144-158.vinculada-1-nif" in export.read_text(encoding="utf-8")


def test_a_single_quoted_mapping_entry_is_rewritten(tmp_path: Path) -> None:
    """Semantic maps may spell a binding reference in either quote style; both must be rewritten."""
    modelos_root = _seed_232(tmp_path)
    _write_pair(modelos_root, "144-158.vinculada-1-nif", old=(OLD_DISENO,), new=(NEW_DISENO,))
    mappings_root = tmp_path / "mappings"
    mapping_dir = mappings_root / f"modelo_{SEED_MODELO}"
    mapping_dir.mkdir(parents=True)
    mapping = mapping_dir / "0001-map.toml"
    mapping.write_text(
        "[[fields]]\n"
        "id = 'f068'\n"
        "binding = 'modelo-232-2016.page_01.144-158.vinculada-1-nif'\n"
        '[[fields]]\nid = "f069"\n'
        'binding = "modelo-232-2018.page_01.144-158.vinculada-1-nif"\n',
        encoding="utf-8",
        newline="\n",
    )

    plan = plan_edition_year_collapse(SEED_MODELO, modelos_root)
    assert mapping in apply_collapse(plan, modelos_root, mappings_root)

    rewritten = mapping.read_text(encoding="utf-8")
    assert "binding = 'modelo-232.page_01.144-158.vinculada-1-nif'" in rewritten
    assert 'binding = "modelo-232.page_01.144-158.vinculada-1-nif"' in rewritten
    assert "modelo-232-2016." not in rewritten
    assert "modelo-232-2018." not in rewritten
