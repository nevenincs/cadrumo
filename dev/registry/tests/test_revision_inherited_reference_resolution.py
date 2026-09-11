"""Formula and binding references on an inherited casilla resolve to the successor's own declarations.

Every edition declares its formulas and bindings in full, and their identifiers
may embed the declaring edition's key. A casilla row a successor inherits
arrives naming its stating edition's declarations; the loader points each
reference at the successor's declaration of the same lineage and refuses one
the successor does not declare, so no inherited row keeps a pointer into
another edition.

Every test drives the real directory loader over an on-disk TOML tree, with
nothing mocked. The positive proofs compare against the stating edition's own
identifiers, so they fail if the references were carried over unresolved.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.identifier_lineage import EDITION_PLACEHOLDER, identifier_lineage
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest as _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID: Final = "999"
_LEGAL_REF: Final = "ley-58-2003:art-29"
_SOURCE_REF: Final = "aeat-manual"
_SHARED_BINDING: Final = "modelo-999-comun"
"""A binding identifier embedding no edition key, which is its own lineage."""


def _casilla(revision_id: str, casilla_id: str, *, lineage: str, references: str) -> str:
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{casilla_id}"\n'
        'section = ["liquidacion"]\n'
        'data_type = "money"\n'
        f'continuidad_id = "{lineage}"\n'
        f"{references}"
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _bound(binding: str, *alternates: str) -> str:
    alternate_line = f"alternate_bindings = {list(alternates)!r}\n".replace("'", '"') if alternates else ""
    return f'input_kind = "bound"\nbinding = "{binding}"\n{alternate_line}'


def _computed(formula: str) -> str:
    return f'input_kind = "computed"\nformula = "{formula}"\n'


def _formula(revision_id: str, formula_id: str, *, target: str) -> str:
    return (
        f'[[revisions."{revision_id}".formulas]]\n'
        f'id = "{formula_id}"\n'
        f'target_casilla_id = "{target}"\n'
        'expression = { literal = "0" }\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _binding(revision_id: str, binding_id: str, *, offset: int) -> str:
    return (
        f'[[revisions."{revision_id}".bindings]]\n'
        f'id = "{binding_id}"\n'
        'source = "manual_input"\n'
        f'selector = {{ record = "page_1", field = "campo-{offset}", offset = {offset}, length = 1, '
        'data_type = "text" }\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
    )


def _declarations(revision_id: str, *, formula_key: str, binding_keys: dict[str, str]) -> tuple[str, str]:
    """One formula and the bindings of an edition, each identifier embedding its given key."""
    formulas = _formula(revision_id, f"modelo-999-{formula_key}-cuota", target="02")
    bindings = "".join(
        _binding(revision_id, f"modelo-999-{key}-{name}", offset=offset)
        for offset, (name, key) in enumerate(binding_keys.items(), start=1)
    ) + _binding(revision_id, _SHARED_BINDING, offset=99)
    return formulas, bindings


def _write_edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    casillas: str,
    formulas: str,
    bindings: str,
    predecessor: str | None = None,
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    predecessor_line = f'predecessor = "{predecessor}"\n' if predecessor is not None else ""
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n'
        f"{predecessor_line}",
        encoding="utf-8",
        newline="\n",
    )
    for section, text in (("casillas", casillas), ("formulas", formulas), ("bindings", bindings)):
        if text:
            (revision_dir / section).mkdir()
            (revision_dir / section / f"0001-{section}.toml").write_text(text, encoding="utf-8", newline="\n")


def _modelo_root(root: Path) -> Path:
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    _write_standard_manifest(modelo_dir, "Test")
    return modelo_dir


def _root_edition(modelo_dir: Path) -> None:
    """2024 states a bound row with two alternates, one of them edition-free, and a computed row."""
    formulas, bindings = _declarations("2024", formula_key="2024", binding_keys={"base": "2024", "alterna": "2024"})
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        casillas=(
            _casilla(
                "2024",
                "01",
                lineage="base",
                references=_bound("modelo-999-2024-base", "modelo-999-2024-alterna", _SHARED_BINDING),
            )
            + _casilla("2024", "02", lineage="cuota", references=_computed("modelo-999-2024-cuota"))
        ),
        formulas=formulas,
        bindings=bindings,
    )


def _references(revision: ModeloRevision, casilla_id: str) -> tuple[str | None, str | None, tuple[str, ...]]:
    (casilla,) = (item for item in revision.casillas if item.id == casilla_id)
    return casilla.formula, casilla.binding, tuple(casilla.alternate_bindings)


def _declared_ids(revision: ModeloRevision) -> frozenset[str]:
    return frozenset({*(formula.id for formula in revision.formulas), *(binding.id for binding in revision.bindings)})


def _inheriting_edition(modelo_dir: Path, *, alterna_key: str = "2025", stated: str = "") -> None:
    formulas, bindings = _declarations(
        "2025", formula_key="2025", binding_keys={"base": "2025", "alterna": alterna_key}
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        predecessor="2024",
        casillas=stated,
        formulas=formulas,
        bindings=bindings,
    )


def test_an_inherited_row_resolves_its_formula_and_bindings_to_the_successors_declarations(tmp_path: Path) -> None:
    """2025 states no rows; both of 2024's rows arrive naming 2025's declarations, and 2024 keeps its own."""
    modelo_dir = _modelo_root(tmp_path)
    _root_edition(modelo_dir)
    _inheriting_edition(modelo_dir)

    definition = load_modelo_directory(modelo_dir)
    predecessor, successor = definition.revisions["2024"], definition.revisions["2025"]

    assert _references(successor, "01") == (None, "modelo-999-2025-base", ("modelo-999-2025-alterna", _SHARED_BINDING))
    assert _references(successor, "02") == ("modelo-999-2025-cuota", None, ())
    assert _references(predecessor, "01") == (
        None,
        "modelo-999-2024-base",
        ("modelo-999-2024-alterna", _SHARED_BINDING),
    )
    assert _references(predecessor, "02") == ("modelo-999-2024-cuota", None, ())
    for casilla_id in ("01", "02"):
        formula, binding, alternates = _references(successor, casilla_id)
        assert {ref for ref in (formula, binding, *alternates) if ref is not None} <= _declared_ids(successor)


def test_a_row_carried_down_a_chain_resolves_against_the_edition_it_now_sits_in(tmp_path: Path) -> None:
    """2026 inherits 2024's rows through 2025; the lineage is taken against 2024, the stating edition."""
    modelo_dir = _modelo_root(tmp_path)
    _root_edition(modelo_dir)
    _inheriting_edition(modelo_dir)
    formulas, bindings = _declarations("2026", formula_key="2026", binding_keys={"base": "2026", "alterna": "2026"})
    _write_edition(modelo_dir, "2026", year=2026, predecessor="2025", casillas="", formulas=formulas, bindings=bindings)

    successor = load_modelo_directory(modelo_dir).revisions["2026"]

    assert _references(successor, "01") == (None, "modelo-999-2026-base", ("modelo-999-2026-alterna", _SHARED_BINDING))
    assert _references(successor, "02") == ("modelo-999-2026-cuota", None, ())


def test_an_inherited_reference_the_successor_does_not_declare_is_refused(tmp_path: Path) -> None:
    """2025 declares its alternate binding under 2024's key, so no 2025 declaration carries the lineage.

    The refusal names the row, the field, the reference, and the edition searched.
    """
    modelo_dir = _modelo_root(tmp_path)
    _root_edition(modelo_dir)
    _inheriting_edition(modelo_dir, alterna_key="otra")

    expected = (
        "revision '2025': inherited casilla '01' alternate_bindings reference 'modelo-999-2024-alterna', stated in "
        f"revision '2024', has lineage 'modelo-999-{EDITION_PLACEHOLDER}-alterna', and revision '2025' carries no "
        "bindings declaration of that lineage"
    )
    with pytest.raises(RegistryLoadError, match=re.escape(expected)):
        load_modelo_directory(modelo_dir)


def test_an_inherited_edition_free_reference_must_be_declared_by_the_successor_itself(tmp_path: Path) -> None:
    """An identifier embedding no key is its own lineage, so the successor must declare exactly that identifier."""
    modelo_dir = _modelo_root(tmp_path)
    _root_edition(modelo_dir)
    _inheriting_edition(modelo_dir)
    bindings = modelo_dir / "revisions" / "2025" / "bindings" / "0001-bindings.toml"
    bindings.write_text(
        bindings.read_text(encoding="utf-8").replace(f'"{_SHARED_BINDING}"', '"modelo-999-otro-comun"'),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(RegistryLoadError, match=re.escape(f"reference '{_SHARED_BINDING}', stated in revision '2024'")):
        load_modelo_directory(modelo_dir)


def test_a_stated_row_keeps_its_references_as_authored(tmp_path: Path) -> None:
    """A stated row is left to reference validation, even one naming a predecessor's identifier.

    Row 03 names 2024's formula, which 2025 does not declare. Resolution would
    rewrite that to 2025's formula were the row inherited; stated, it reaches
    the compiled model exactly as written, while the inherited rows beside it
    are still resolved.
    """
    modelo_dir = _modelo_root(tmp_path)
    _root_edition(modelo_dir)
    _inheriting_edition(
        modelo_dir, stated=_casilla("2025", "03", lineage="propia", references=_computed("modelo-999-2024-cuota"))
    )

    successor = load_modelo_directory(modelo_dir).revisions["2025"]

    assert [casilla.id for casilla in successor.casillas] == ["01", "02", "03"]
    assert _references(successor, "03") == ("modelo-999-2024-cuota", None, ())
    assert _references(successor, "02") == ("modelo-999-2025-cuota", None, ())


def test_edition_free_identifiers_resolve_to_themselves(tmp_path: Path) -> None:
    """Once no identifier embeds its edition's key, resolution is the identity on every inherited reference."""
    modelo_dir = _modelo_root(tmp_path)
    for revision_id, year, predecessor in (("2024", 2024, None), ("2025", 2025, "2024")):
        _write_edition(
            modelo_dir,
            revision_id,
            year=year,
            predecessor=predecessor,
            casillas=(
                _casilla(revision_id, "01", lineage="base", references=_bound("modelo-999-base", _SHARED_BINDING))
                + _casilla(revision_id, "02", lineage="cuota", references=_computed("modelo-999-cuota"))
            )
            if predecessor is None
            else "",
            formulas=_formula(revision_id, "modelo-999-cuota", target="02"),
            bindings=_binding(revision_id, "modelo-999-base", offset=1)
            + _binding(revision_id, _SHARED_BINDING, offset=2),
        )

    definition = load_modelo_directory(modelo_dir)

    for revision_id in ("2024", "2025"):
        revision = definition.revisions[revision_id]
        assert _references(revision, "01") == (None, "modelo-999-base", (_SHARED_BINDING,))
        assert _references(revision, "02") == ("modelo-999-cuota", None, ())


@pytest.mark.parametrize(
    ("identifier", "revision_id", "lineage"),
    [
        pytest.param("modelo-131-2019-2023-cuota", "2019-2023", f"modelo-131-{EDITION_PLACEHOLDER}-cuota", id="inner"),
        pytest.param("modelo-131-2024.page1.109", "2024", f"modelo-131-{EDITION_PLACEHOLDER}.page1.109", id="dotted"),
        pytest.param("renta-2025", "2025", f"renta-{EDITION_PLACEHOLDER}", id="trailing"),
        pytest.param("modelo-131-cuota", "2024", "modelo-131-cuota", id="edition-free"),
        pytest.param("modelo-131-20245-cuota", "2024", "modelo-131-20245-cuota", id="not-a-whole-segment"),
        pytest.param("modelo-131-2023-cuota", "2024", "modelo-131-2023-cuota", id="another-editions-key"),
    ],
)
def test_lineage_replaces_only_the_declaring_editions_key_as_a_whole_segment(
    identifier: str, revision_id: str, lineage: str
) -> None:
    assert identifier_lineage(identifier, revision_id) == lineage
