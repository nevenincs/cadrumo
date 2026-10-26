"""Edition-level source defaults for the binding and formula families.

An edition declares its bindings' and formulas' shared source grounding once, as
``binding_source_refs`` and ``formula_source_refs`` in its manifest, exactly as
it already declares its casillas' as ``casilla_source_refs``. The loader fills
each into the rows of its OWN family that state no ``source_refs``; a row
stating ``additional_source_refs`` takes the default followed by those
additions; a row stating ``source_refs`` keeps them whole.

The three defaults are independent by design, because the three families are
grounded in different documents, so every accepted shape here is paired with the
proof that a family is never defaulted from another family's key -- and with the
refusal it replaces, so a test cannot pass because the defaults were never
consulted.

Every test drives the real directory loader over an on-disk TOML tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest as _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID: Final = "999"
_REVISION: Final = "2025"
_ARTICLE: Final = "ley-58-2003:art-29"
_ORDEN: Final = "orden-hac-200-2024:art-1"
_CASILLA_SOURCE: Final = "aeat-dr-999-2025"
_BINDING_SOURCE: Final = "aeat-dr-999-2025-registros"
_FORMULA_SOURCE: Final = "aeat-instrucciones-999-2025"
_OWN_SOURCE: Final = "aeat-nota-999"


def _row(family: str, identifier: str, body: str, refs: str) -> str:
    return f'[[revisions."{_REVISION}".{family}]]\nid = "{identifier}"\n{body}{refs}\n'


def _binding(identifier: str, refs: str) -> str:
    body = (
        'provider = { kind = "manual_input", record = "page_01", field = "f", '
        'offset = 1, length = 5, data_type = "text" }\n'
        'value = { data_type = "text", channel = "text" }\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
    )
    return _row("bindings", identifier, body, refs)


def _formula(identifier: str, refs: str) -> str:
    body = (
        'target_casilla_id = "03"\n'
        'expression = { op = "add", args = [{ casilla_id = "01" }, { casilla_id = "02" }] }\n'
        'rounding = "integer"\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
    )
    return _row("formulas", identifier, body, refs)


def _stated(key: str, refs: tuple[str, ...]) -> str:
    return f"{key} = {json.dumps(list(refs))}\n"


def _casilla(casilla_id: str) -> str:
    return (
        f'[[revisions."{_REVISION}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{casilla_id}"\n'
        'section = ["liquidacion"]\n'
        f'continuidad_id = "linaje-{casilla_id}"\n'
    )


def _tree(
    root: Path,
    *,
    bindings: str,
    formulas: str,
    binding_default: tuple[str, ...] | None = (_BINDING_SOURCE,),
    formula_default: tuple[str, ...] | None = (_FORMULA_SOURCE,),
) -> Path:
    modelo_dir = root / _MODELO_ID
    modelo_dir.mkdir(parents=True)
    _write_standard_manifest(modelo_dir, "Test")
    revision_dir = modelo_dir / "revisions" / _REVISION
    for family in ("casillas", "bindings", "formulas"):
        (revision_dir / family).mkdir(parents=True)
    defaults = _stated("casilla_source_refs", (_CASILLA_SOURCE,))
    if binding_default is not None:
        defaults += _stated("binding_source_refs", binding_default)
    if formula_default is not None:
        defaults += _stated("formula_source_refs", formula_default)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{_REVISION}"]\n'
        "valid_from = 2025-01-01\n"
        "valid_to = 2025-12-31\n"
        'period_selector = { years = [2025], periods = ["0A"] }\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        'source_refs = ["aeat-manual"]\n'
        f'orden_aplicabilidad = ["{_ORDEN}"]\n'
        f"{defaults}",
        encoding="utf-8",
        newline="\n",
    )
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(
        _casilla("01") + _casilla("02") + _casilla("03"), encoding="utf-8", newline="\n"
    )
    (revision_dir / "bindings" / "0001-bindings.toml").write_text(bindings, encoding="utf-8", newline="\n")
    (revision_dir / "formulas" / "0001-formulas.toml").write_text(formulas, encoding="utf-8", newline="\n")
    return modelo_dir


def _source_refs(revision: ModeloRevision, family: str, identifier: str) -> tuple[str, ...]:
    (member,) = (item for item in getattr(revision, family) if item.id == identifier)
    return tuple(str(ref) for ref in member.source_refs)


def _populated(root: Path) -> Path:
    bindings = (
        _binding("b-silente", "")
        + _binding("b-propia", _stated("source_refs", (_OWN_SOURCE,)))
        + _binding("b-adicional", _stated("additional_source_refs", (_OWN_SOURCE,)))
    )
    formulas = _formula("f-silente", "") + _formula("f-adicional", _stated("additional_source_refs", (_OWN_SOURCE,)))
    return _tree(root, bindings=bindings, formulas=formulas)


def test_each_family_takes_its_own_declared_default(tmp_path: Path) -> None:
    """A binding takes ``binding_source_refs`` and a formula ``formula_source_refs`` -- never each other's."""
    revision = load_modelo_directory(_populated(tmp_path)).revisions[_REVISION]

    assert _source_refs(revision, "bindings", "b-silente") == (_BINDING_SOURCE,)
    assert _source_refs(revision, "formulas", "f-silente") == (_FORMULA_SOURCE,)
    assert revision.binding_source_refs == (_BINDING_SOURCE,)
    assert revision.formula_source_refs == (_FORMULA_SOURCE,)
    # The casilla default is a third, independent fact and reaches neither.
    assert revision.casilla_source_refs == (_CASILLA_SOURCE,)
    assert _CASILLA_SOURCE not in _source_refs(revision, "bindings", "b-silente")
    assert _CASILLA_SOURCE not in _source_refs(revision, "formulas", "f-silente")


def test_a_stated_value_survives_whole_and_additions_extend_the_default(tmp_path: Path) -> None:
    """The casilla member-side rule exactly: replace, or extend, never merge."""
    revision = load_modelo_directory(_populated(tmp_path)).revisions[_REVISION]

    assert _source_refs(revision, "bindings", "b-propia") == (_OWN_SOURCE,)
    assert _source_refs(revision, "bindings", "b-adicional") == (_BINDING_SOURCE, _OWN_SOURCE)
    assert _source_refs(revision, "formulas", "f-adicional") == (_FORMULA_SOURCE, _OWN_SOURCE)


def test_without_a_declared_family_default_a_row_stating_no_source_is_refused(tmp_path: Path) -> None:
    """The teeth of the proofs above: nothing is inferred when the edition declares no default."""
    tree = _tree(tmp_path, bindings=_binding("b-silente", ""), formulas=_formula("f-silente", ""), binding_default=None)

    with pytest.raises(RegistryLoadError, match=r"(?s)invalid revision '2025'.*bindings\.0\.source_refs"):
        load_modelo_directory(tree)


def test_additions_name_their_own_familys_manifest_key_when_no_default_exists(tmp_path: Path) -> None:
    """The refusal must name ``binding_source_refs``, not the casilla key it was generalised from."""
    tree = _tree(
        tmp_path,
        bindings=_binding("b-adicional", _stated("additional_source_refs", (_OWN_SOURCE,))),
        formulas=_formula("f-silente", ""),
        binding_default=None,
    )

    with pytest.raises(RegistryLoadError, match=r"the edition declares no binding_source_refs for them to extend"):
        load_modelo_directory(tree)


def test_stating_both_keys_is_refused_for_a_family_row(tmp_path: Path) -> None:
    """One of the two, never both: the row cannot both replace and extend the default."""
    tree = _tree(
        tmp_path,
        bindings=_binding(
            "b-ambas", _stated("source_refs", (_OWN_SOURCE,)) + _stated("additional_source_refs", (_OWN_SOURCE,))
        ),
        formulas=_formula("f-silente", ""),
    )

    with pytest.raises(RegistryLoadError, match=r"replaces the edition's binding_source_refs whole"):
        load_modelo_directory(tree)
