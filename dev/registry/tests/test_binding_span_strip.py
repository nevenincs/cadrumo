"""Behaviour and refusals of the fixed-width span strip on binding identifiers.

Every case builds an isolated temporary registry tree seeded from modelo 131's
real span-bearing shape, so the contributor's working tree is never mutated and
each refusal is proven against real files rather than a patched module. The
normal path and the defect proofs pass in the same suite, per
``aeat-quality-gates``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.registry.rename_formula_binding_identifiers import (
    apply_span_strip,
    plan_span_strip,
    provider_address,
    restore_truncated_field_slot,
    span_runs,
    strip_span_segment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "131"
_REVISION = "2019-2023"

_MANIFEST = """\
[revisions."2019-2023"]
valid_from = 2019-01-01
"""

# Copied in shape from modelo 131's 0003-page1-fields.toml: an id that names the
# slot AND the fixed-width address its own provider already declares.
_BINDINGS = """\
[[revisions."2019-2023".bindings]]
id = "modelo-131.page1.109-112.actividad-1-epigrafe"
provider = { kind = "manual_input", field = "actividad-1-epigrafe", offset = 109, length = 4 }
value = { data_type = "text", channel = "text" }

[[revisions."2019-2023".bindings]]
id = "modelo-131.page1.113-129.actividad-1-rendimiento-neto"
provider = { kind = "manual_input", field = "actividad-1-rendimiento-neto", offset = 113, length = 17 }
value = { data_type = "money", channel = "decimal" }

[[revisions."2019-2023".bindings]]
id = "modelo-131.page1.total-ingresos"
provider = { kind = "manual_input", field = "total-ingresos", offset = 200, length = 17 }
value = { data_type = "money", channel = "decimal" }
"""

# A reference site of each kind the strip must follow: a casilla binding, a
# formula operand, and a construct member.
_REFERENCES = """\
[[revisions."2019-2023".casillas]]
id = "01"
binding = "modelo-131.page1.109-112.actividad-1-epigrafe"
alternate_bindings = ["modelo-131.page1.113-129.actividad-1-rendimiento-neto"]

[[revisions."2019-2023".formulas]]
id = "modelo-131.suma"
operands = ["modelo-131.page1.113-129.actividad-1-rendimiento-neto"]

[[revisions."2019-2023".constructs]]
id = "modelo-131.actividad-1"
binding_refs = ["modelo-131.page1.109-112.actividad-1-epigrafe"]
"""


def _seed(root: Path, bindings: str = _BINDINGS, references: str = _REFERENCES) -> Path:
    """Write an isolated modelos tree carrying one modelo and one revision."""
    revision = root / _MODELO / "revisions" / _REVISION
    (revision / "bindings").mkdir(parents=True)
    (revision / "casillas").mkdir(parents=True)
    (revision / "revision.toml").write_text(_MANIFEST, encoding="utf-8")
    (revision / "bindings" / "0001-bindings.toml").write_text(bindings, encoding="utf-8")
    (revision / "casillas" / "0001-refs.toml").write_text(references, encoding="utf-8")
    return root


def test_span_runs_and_strip_agree_on_the_boundary() -> None:
    """A span is only the separator-bounded run, and one adjacent separator leaves with it."""
    identifier = "modelo-131.page1.109-112.actividad-1-epigrafe"
    runs = span_runs(identifier)
    assert [(low, high) for _start, _end, low, high in runs] == [(109, 112)]
    start, end, _low, _high = runs[0]
    assert strip_span_segment(identifier, start, end) == "modelo-131.page1.actividad-1-epigrafe"


def test_provider_address_is_offset_through_offset_plus_length_minus_one() -> None:
    """The address a span must equal is the inclusive last byte, not the exclusive end."""
    assert provider_address({"provider": {"offset": 109, "length": 4}}) == (109, 112)
    assert provider_address({"provider": {"offset": 109}}) is None
    assert provider_address({"provider": {"offset": 109, "length": 0}}) is None


def test_strip_fires_and_every_reference_follows(tmp_path: Path) -> None:
    """The declaration loses its span and each reference site is rewritten with it."""
    modelos_root = _seed(tmp_path / "modelos")
    plan = plan_span_strip(_MODELO, modelos_root)

    assert plan.refusals == []
    assert plan.collisions == []
    assert plan.rename_map == {
        "modelo-131.page1.109-112.actividad-1-epigrafe": "modelo-131.page1.actividad-1-epigrafe",
        "modelo-131.page1.113-129.actividad-1-rendimiento-neto": "modelo-131.page1.actividad-1-rendimiento-neto",
    }

    touched, hits = apply_span_strip(
        plan,
        modelos_root,
        tmp_path / "mappings",
        code_files=(),
    )
    assert len(touched) == 2
    # Two declarations plus one casilla binding, one alternate binding, one
    # formula operand and one construct member.
    assert hits == 6

    references = (modelos_root / _MODELO / "revisions" / _REVISION / "casillas" / "0001-refs.toml").read_text(
        encoding="utf-8"
    )
    assert "109-112" not in references
    assert "113-129" not in references
    assert 'binding = "modelo-131.page1.actividad-1-epigrafe"' in references
    assert 'alternate_bindings = ["modelo-131.page1.actividad-1-rendimiento-neto"]' in references
    assert 'operands = ["modelo-131.page1.actividad-1-rendimiento-neto"]' in references
    assert 'binding_refs = ["modelo-131.page1.actividad-1-epigrafe"]' in references


def test_a_non_span_dotted_id_is_untouched(tmp_path: Path) -> None:
    """An id with no span-shaped run is not a candidate and is left exactly as authored."""
    modelos_root = _seed(tmp_path / "modelos")
    plan = plan_span_strip(_MODELO, modelos_root)

    assert "modelo-131.page1.total-ingresos" not in plan.rename_map

    apply_span_strip(plan, modelos_root, tmp_path / "mappings", code_files=())
    bindings = (modelos_root / _MODELO / "revisions" / _REVISION / "bindings" / "0001-bindings.toml").read_text(
        encoding="utf-8"
    )
    assert 'id = "modelo-131.page1.total-ingresos"' in bindings


def test_a_span_the_provider_does_not_declare_is_refused(tmp_path: Path) -> None:
    """The id spells 109-112 while its provider addresses 109-115; the strip refuses it."""
    mismatched = _BINDINGS.replace(
        'field = "actividad-1-epigrafe", offset = 109, length = 4',
        'field = "actividad-1-epigrafe", offset = 109, length = 7',
    )
    modelos_root = _seed(tmp_path / "modelos", bindings=mismatched)
    plan = plan_span_strip(_MODELO, modelos_root)

    assert "modelo-131.page1.109-112.actividad-1-epigrafe" not in plan.rename_map
    assert any("109-112" in refusal and "109-115" in refusal for refusal in plan.refusals)
    # The sibling whose span does match still strips: the refusal is per row.
    assert "modelo-131.page1.113-129.actividad-1-rendimiento-neto" in plan.rename_map


def test_a_within_revision_collision_refuses_the_whole_modelo(tmp_path: Path) -> None:
    """Two members of one edition collapsing onto one name withdraw every rename."""
    colliding = (
        _BINDINGS
        + """
[[revisions."2019-2023".bindings]]
id = "modelo-131.page1.300-304.actividad-1-epigrafe"
provider = { kind = "manual_input", field = "otro", offset = 300, length = 5 }
value = { data_type = "text", channel = "text" }
"""
    )
    modelos_root = _seed(tmp_path / "modelos", bindings=colliding)
    plan = plan_span_strip(_MODELO, modelos_root)

    assert plan.refused_modelo is True
    assert plan.rename_map == {}
    assert any("modelo-131.page1.actividad-1-epigrafe" in collision for collision in plan.collisions)
    # Both contenders are named, so the resolving step knows which rows to look at.
    collision = next(c for c in plan.collisions if "modelo-131.page1.actividad-1-epigrafe" in c)
    assert "109-112" in collision
    assert "300-304" in collision

    touched, hits = apply_span_strip(plan, modelos_root, tmp_path / "mappings", code_files=())
    assert (touched, hits) == ([], 0)
    references = (modelos_root / _MODELO / "revisions" / _REVISION / "casillas" / "0001-refs.toml").read_text(
        encoding="utf-8"
    )
    assert "109-112" in references


_TRUNCATED_MANIFEST = """[revisions."2021"]
valid_from = 2021-01-01
"""


def _seed_edition(root: Path, modelo: str, bindings: str, references: str = "") -> Path:
    """Write an isolated modelos tree for one modelo's 2021 edition."""
    revision = root / modelo / "revisions" / "2021"
    (revision / "bindings").mkdir(parents=True)
    (revision / "casillas").mkdir(parents=True)
    (revision / "revision.toml").write_text(_TRUNCATED_MANIFEST, encoding="utf-8")
    (revision / "bindings" / "0001-bindings.toml").write_text(bindings, encoding="utf-8")
    (revision / "casillas" / "0001-refs.toml").write_text(references, encoding="utf-8")
    return root


# Two members of one repeated record block, copied in shape from modelo 714's
# 714-03 titular block. Each id's slot dropped the trailing repetition segment,
# so the plain strip alone would land both members on one name.
_REPEATED_BLOCK = """[[revisions."2021".bindings]]
id = "modelo-714.714-03.1115-1119.bloque-porcentaje-tit-usu"
provider = { kind = "manual_input", field = "bloque-porcentaje-tit-usu-1", offset = 1115, length = 5 }
value = { data_type = "text", channel = "text" }

[[revisions."2021".bindings]]
id = "modelo-714.714-03.1191-1195.bloque-porcentaje-tit-usu"
provider = { kind = "manual_input", field = "bloque-porcentaje-tit-usu-2", offset = 1191, length = 5 }
value = { data_type = "text", channel = "text" }
"""

_REPEATED_BLOCK_REFS = """[[revisions."2021".casillas]]
id = "01"
binding = "modelo-714.714-03.1115-1119.bloque-porcentaje-tit-usu"
"""


def test_a_truncated_slot_is_restored_from_its_providers_field(tmp_path: Path) -> None:
    """Repeated-block members survive the strip apart, named by their field's own index."""
    modelos_root = _seed_edition(tmp_path / "modelos", "714", _REPEATED_BLOCK, _REPEATED_BLOCK_REFS)
    plan = plan_span_strip("714", modelos_root)

    assert plan.refused_modelo is False
    assert plan.collisions == []
    assert plan.rename_map == {
        "modelo-714.714-03.1115-1119.bloque-porcentaje-tit-usu": "modelo-714.714-03.bloque-porcentaje-tit-usu-1",
        "modelo-714.714-03.1191-1195.bloque-porcentaje-tit-usu": "modelo-714.714-03.bloque-porcentaje-tit-usu-2",
    }
    # The address the ids restated is gone from both surviving names.
    assert not any("1115" in new_id or "1191" in new_id for new_id in plan.rename_map.values())


def test_the_restored_names_reach_the_reference_sites(tmp_path: Path) -> None:
    """A casilla quoting a restored id is rewritten to the indexed name."""
    modelos_root = _seed_edition(tmp_path / "modelos", "714", _REPEATED_BLOCK, _REPEATED_BLOCK_REFS)
    plan = plan_span_strip("714", modelos_root)
    apply_span_strip(plan, modelos_root, tmp_path / "mappings", code_files=())

    references = (modelos_root / "714" / "revisions" / "2021" / "casillas" / "0001-refs.toml").read_text(
        encoding="utf-8"
    )
    assert "modelo-714.714-03.bloque-porcentaje-tit-usu-1" in references
    assert "1115-1119" not in references


# The slot breaks MID-WORD ("simplific" of "simplificado"), copied in shape from
# modelo 390's page_5. The remainder names no repetition, so the rule must not
# read it as a dropped segment.
_MIDWORD_TRUNCATION = """[[revisions."2021".bindings]]
id = "modelo-390.page_5.712-728.act-1-cuota-deriv-regimen-simplific"
provider = { kind = "manual_input", field = "act-1-cuota-deriv-regimen-simplificado-k1", offset = 712, length = 17 }
value = { data_type = "money", channel = "decimal" }
"""


def test_a_midword_truncated_slot_keeps_the_plain_strip(tmp_path: Path) -> None:
    """A display cap is not a dropped repetition segment, so the slot is left alone."""
    modelos_root = _seed_edition(tmp_path / "modelos", "390", _MIDWORD_TRUNCATION)
    plan = plan_span_strip("390", modelos_root)

    assert plan.rename_map == {
        "modelo-390.page_5.712-728.act-1-cuota-deriv-regimen-simplific": (
            "modelo-390.page_5.act-1-cuota-deriv-regimen-simplific"
        )
    }


_UNTRUNCATED = """[[revisions."2021".bindings]]
id = "modelo-131.page1.109-112.actividad-1-epigrafe"
provider = { kind = "manual_input", field = "actividad-1-epigrafe", offset = 109, length = 4 }
value = { data_type = "text", channel = "text" }
"""


def test_an_untruncated_slot_is_unaffected(tmp_path: Path) -> None:
    """The ordinary case -- the slot already equals the field -- strips exactly as before."""
    modelos_root = _seed_edition(tmp_path / "modelos", "131", _UNTRUNCATED)
    plan = plan_span_strip("131", modelos_root)

    assert plan.rename_map == {"modelo-131.page1.109-112.actividad-1-epigrafe": "modelo-131.page1.actividad-1-epigrafe"}


@pytest.mark.parametrize(
    ("slot", "declared", "expected"),
    [
        ("a-b", "a-b-1", "modelo-x.p.a-b-1"),
        ("a-b", "a-b", "modelo-x.p.a-b"),
        ("a-b", "a-bc", "modelo-x.p.a-b"),
        ("a-b", "other", "modelo-x.p.a-b"),
    ],
)
def test_restoration_requires_a_separator_bounded_extension(slot: str, declared: str, expected: str) -> None:
    """Only a whole dropped segment restores; a mid-word or unrelated field does not."""
    member = {"provider": {"field": declared}}

    assert restore_truncated_field_slot(f"modelo-x.p.{slot}", slot, member) == expected
