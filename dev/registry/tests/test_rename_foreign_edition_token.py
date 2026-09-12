"""Behaviour of the foreign-edition-token collapse.

Every case builds an isolated temporary registry tree and writes only inside it,
so the contributor's working tree is never touched and the rule is proven against
real fragments rather than a patched module.

What is under test is a judgement about the corpus, not a string transform: an
identifier spelling another edition's key is either a copy that was never renamed
or a name whose year is the thing the row is about, and only the surrounding
declarations tell the two apart. So each case states the surrounding
declarations, and the assertion follows from them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..rename_formula_binding_identifiers import (
    apply_foreign_edition_token_collapse,
    plan_foreign_edition_token_collapse,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

MODELO = "210"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8")


def _seed(root: Path, edition: str, family: str, body: str, *, fragment: str = "0001-fragment.toml") -> Path:
    edition_dir = root / MODELO / "revisions" / edition
    _write(edition_dir / "revision.toml", f'[revisions."{edition}"]\nvalid_from = 2025-01-01\n')
    _write(edition_dir / family / fragment, body)
    return edition_dir


def _member(edition: str, family: str, identifier: str, *, unit: str = "code") -> str:
    return f'[[revisions."{edition}".{family}]]\nid = "{identifier}"\ndata_type = "scalar"\nunit = "{unit}"\n\n'


def test_an_identical_member_under_a_foreign_token_is_renamed(tmp_path: Path) -> None:
    """The sibling already declares the edition-free name for the identical member."""
    _seed(tmp_path, "2025", "parameters", _member("2025", "parameters", "m210-tipo-renta-code"))
    _seed(tmp_path, "2026", "parameters", _member("2026", "parameters", "m210-tipo-renta-code-2025"))

    plan = plan_foreign_edition_token_collapse(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {"m210-tipo-renta-code-2025": "m210-tipo-renta-code"}
    assert not plan.refusals
    assert not plan.collisions
    assert plan.renames[0].sibling_edition == "2025"


def test_a_token_sitting_mid_identifier_is_renamed_too(tmp_path: Path) -> None:
    """The corpus spells a foreign edition mid-id as well as trailing; position is not the test."""
    _seed(tmp_path, "2025", "applicability", _member("2025", "applicability", "modelo-210-non-resident-irnr"))
    _seed(tmp_path, "2026", "applicability", _member("2026", "applicability", "modelo-210-2025-non-resident-irnr"))

    plan = plan_foreign_edition_token_collapse(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {"modelo-210-2025-non-resident-irnr": "modelo-210-non-resident-irnr"}


def test_one_differing_field_refuses_and_names_the_field(tmp_path: Path) -> None:
    """Detector teeth: two editions stating different things are two members, not two spellings.

    The refusal names the field, because that is the whole use of it: a reader
    has to know what makes these two different before deciding what to do.
    """
    _seed(tmp_path, "2025", "parameters", _member("2025", "parameters", "m210-tipo-renta-code", unit="code"))
    _seed(tmp_path, "2026", "parameters", _member("2026", "parameters", "m210-tipo-renta-code-2025", unit="percent"))

    plan = plan_foreign_edition_token_collapse(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {}
    assert len(plan.refusals) == 1
    assert "unit" in plan.refusals[0]
    assert "'percent'" in plan.refusals[0]
    assert "'code'" in plan.refusals[0]


def test_a_year_with_no_sibling_spelling_is_content_and_is_left_alone(tmp_path: Path) -> None:
    """Detector teeth for the other direction: the year is what the row is ABOUT.

    Modelo 100's formulas name the ejercicio a negative base came from. Nothing
    declares the edition-free stem, because there is no such member -- the four
    carry-forward rules differ precisely in that year, and collapsing them would
    merge them into one name and lose three.
    """
    _seed(tmp_path, "2025", "formulas", _member("2025", "formulas", "renta-negativa-general-2024-aplicada"))
    _seed(tmp_path, "2026", "formulas", _member("2026", "formulas", "renta-negativa-general-2025-aplicada"))

    plan = plan_foreign_edition_token_collapse(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {}
    assert not plan.refusals
    assert any("is content rather than a stale edition key" in note for note in plan.untouched_content)


def test_a_collapse_onto_a_name_the_edition_already_holds_is_refused_not_suffixed(tmp_path: Path) -> None:
    """Two members of one edition cannot share a name, and an offset or year is not a tiebreaker."""
    _seed(tmp_path, "2025", "parameters", _member("2025", "parameters", "m210-tipo-renta-code"))
    _seed(
        tmp_path,
        "2026",
        "parameters",
        _member("2026", "parameters", "m210-tipo-renta-code-2025")
        + _member("2026", "parameters", "m210-tipo-renta-code"),
    )

    plan = plan_foreign_edition_token_collapse(MODELO, modelos_root=tmp_path)

    assert plan.rename_map == {}
    assert len(plan.collisions) == 1
    assert "refused rather than suffixed" in plan.collisions[0]


def test_the_apply_rewrites_references_and_moves_the_token_bearing_files(tmp_path: Path) -> None:
    """End to end: the declaration, a reference to it, and both files' names all move together."""
    _seed(
        tmp_path,
        "2025",
        "parameters",
        _member("2025", "parameters", "m210-tipo-renta-code"),
        fragment="0004-m210-tipo-renta-code-2025.toml",
    )
    edition_2026 = _seed(
        tmp_path,
        "2026",
        "parameters",
        _member("2026", "parameters", "m210-tipo-renta-code-2025"),
        fragment="0004-m210-tipo-renta-code-2025.toml",
    )
    _write(
        edition_2026 / "formulas" / "0001-formulas.toml",
        '[[revisions."2026".formulas]]\nid = "m210-uses-the-code"\noperands = ["m210-tipo-renta-code-2025"]\n',
    )

    plan = plan_foreign_edition_token_collapse(MODELO, modelos_root=tmp_path)
    manifest: list[dict[str, object]] = []
    touched, hits = apply_foreign_edition_token_collapse(
        plan, modelos_root=tmp_path, mappings_root=tmp_path / "absent", code_files=(), manifest=manifest
    )

    formulas = (edition_2026 / "formulas" / "0001-formulas.toml").read_text(encoding="utf-8")
    assert '"m210-tipo-renta-code"' in formulas
    assert "m210-tipo-renta-code-2025" not in formulas
    # Both editions' files carried the stale label, so both move.
    for edition in ("2025", "2026"):
        parameters = tmp_path / MODELO / "revisions" / edition / "parameters"
        assert (parameters / "0004-m210-tipo-renta-code.toml").is_file()
        assert not (parameters / "0004-m210-tipo-renta-code-2025.toml").exists()
    assert hits >= 2
    assert touched
    assert all("sha256_before" in entry and "sha256_after" in entry for entry in manifest)
