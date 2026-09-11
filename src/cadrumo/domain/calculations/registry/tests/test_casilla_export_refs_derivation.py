"""A casilla's export references are derived from the export fields that resolve to it.

The loader computes ``export_refs`` from the edition's own layouts and refuses
an authored value. Every test here writes a small directory-mode modelo to disk
and drives the real directory loader over it; each accepted shape is paired
with the defect it must detect, so no test can pass because the derivation
never ran.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from test_support.registry_authoring import load_modelo_directory

from ..errors import RegistryLoadError
from ..schema import ModeloRevision
from ._loader_directory_mode_support import _write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ARTICLE: Final = "ley-58-2003:art-29"
_SOURCE: Final = "aeat-manual"
_ROW_BINDING: Final = "modelo-999-contraparte-row-nif"
_ROW_SLOT: Final = "party_tax_id"


def _casilla(revision_id: str, casilla_id: str, *, extra: str = "") -> str:
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{casilla_id}"\n'
        'section = ["liquidacion"]\n'
        f'continuidad_id = "m999-{casilla_id}"\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        f'source_refs = ["{_SOURCE}"]\n'
        f"{extra}\n"
    )


def _field(
    revision_id: str, field_id: str, offset: int, *, casilla_id: str | None = None, binding: str | None = None
) -> str:
    target = f'kind = "casilla"\ncasilla_id = "{casilla_id}"\n' if casilla_id is not None else ""
    if binding is not None:
        target = f'kind = "binding"\nbinding = "{binding}"\n'
    return (
        f'[[revisions."{revision_id}".export_layouts.records.fields]]\n'
        f'id = "{field_id}"\n'
        f"offset = {offset}\n"
        "length = 1\n"
        f"{target}"
        'data_type = "text"\n'
        "required = false\n"
        'padding = "right_space"\n'
        'justification = "left"\n'
        "signed = false\n"
        f'legal_refs = ["{_ARTICLE}"]\n'
        f'source_refs = ["{_SOURCE}"]\n\n'
    )


def _layout(
    revision_id: str,
    layout_id: str,
    fields: str,
    *,
    order: int = 0,
    record_extra: str = "",
    row_map: str = "",
) -> str:
    row_table = (
        f'[revisions."{revision_id}".export_layouts.records.row_field_casilla_ids]\n{row_map}\n' if row_map else ""
    )
    return (
        f'[[revisions."{revision_id}".export_layouts]]\n'
        f'id = "{layout_id}"\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        f'source_refs = ["{_SOURCE}"]\n\n'
        f'[[revisions."{revision_id}".export_layouts.records]]\n'
        f'id = "{layout_id}-record"\n'
        'record_type = "1"\n'
        f"order = {order}\n"
        'encoding = "iso-8859-1"\n'
        'line_ending = "none"\n'
        "required = true\n"
        f"{record_extra}\n"
        f"{fields}"
        f"{row_table}"
    )


def _row_binding(revision_id: str) -> str:
    return (
        f'[[revisions."{revision_id}".bindings]]\n'
        f'id = "{_ROW_BINDING}"\n'
        'source = "m347_third_party_operation"\n'
        f'selector = {{ fact = "row_field", row_field = "{_ROW_SLOT}", grouping = "contraparte_clave", '
        'claves = [], rectification_scope = "any" }\n'
        'aggregation = { op = "rows" }\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        f'source_refs = ["{_SOURCE}"]\n\n'
    )


def _write_edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    year: int,
    casillas: str,
    layouts: tuple[str, ...] = (),
    bindings: str = "",
    manifest_extra: str = "",
) -> None:
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_ARTICLE}"]\n'
        f'source_refs = ["{_SOURCE}"]\n'
        f"{manifest_extra}",
        encoding="utf-8",
        newline="\n",
    )
    if casillas:
        (revision_dir / "casillas").mkdir()
        (revision_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8", newline="\n")
    if layouts:
        (revision_dir / "export_layouts").mkdir()
        for index, layout in enumerate(layouts, start=1):
            (revision_dir / "export_layouts" / f"{index:04d}-layout.toml").write_text(
                layout, encoding="utf-8", newline="\n"
            )
    if bindings:
        (revision_dir / "bindings").mkdir()
        (revision_dir / "bindings" / "0001-bindings.toml").write_text(bindings, encoding="utf-8", newline="\n")


def _modelo(root: Path) -> Path:
    modelo_dir = root / "999"
    modelo_dir.mkdir(parents=True)
    _write_standard_manifest(modelo_dir, "Test")
    return modelo_dir


def _single(root: Path, *, casillas: str, layouts: tuple[str, ...], bindings: str = "") -> ModeloRevision:
    modelo_dir = _modelo(root)
    _write_edition(modelo_dir, "2025", year=2025, casillas=casillas, layouts=layouts, bindings=bindings)
    return load_modelo_directory(modelo_dir).revisions["2025"]


def _refs(revision: ModeloRevision) -> dict[str, tuple[str, ...]]:
    return {str(casilla.id): tuple(casilla.export_refs) for casilla in revision.casillas}


_TWO_CASILLAS: Final = _casilla("2025", "01") + _casilla("2025", "02")


def test_refs_follow_the_layout_in_field_order_and_a_moved_field_leaves_no_stale_reference(tmp_path: Path) -> None:
    before = _single(
        tmp_path / "before",
        casillas=_TWO_CASILLAS,
        layouts=(
            _layout(
                "2025",
                "l",
                _field("2025", "m999.r.f002", 2, casilla_id="01") + _field("2025", "m999.r.f001", 1, casilla_id="01"),
            ),
        ),
    )
    # Declared out of offset order: the value follows the layout's emission order, not the file.
    assert _refs(before) == {"01": ("m999.r.f001", "m999.r.f002"), "02": ()}

    after = _single(
        tmp_path / "after",
        casillas=_TWO_CASILLAS,
        layouts=(
            _layout(
                "2025",
                "l",
                _field("2025", "m999.r.f002", 2, casilla_id="02") + _field("2025", "m999.r.f001", 1, casilla_id="01"),
            ),
        ),
    )
    assert _refs(after) == {"01": ("m999.r.f001",), "02": ("m999.r.f002",)}


def test_refs_follow_record_order_before_field_offset(tmp_path: Path) -> None:
    second_record = (
        '[[revisions."2025".export_layouts.records]]\n'
        'id = "l-record-first"\n'
        'record_type = "0"\n'
        "order = 0\n"
        'encoding = "iso-8859-1"\n'
        'line_ending = "none"\n'
        "required = true\n\n" + _field("2025", "m999.first.f009", 9, casilla_id="01")
    )
    revision = _single(
        tmp_path,
        casillas=_TWO_CASILLAS,
        layouts=(_layout("2025", "l", _field("2025", "m999.r.f001", 1, casilla_id="01"), order=1) + second_record,),
    )

    assert _refs(revision)["01"] == ("m999.first.f009", "m999.r.f001")


def test_an_inherited_row_takes_its_successors_layout_never_its_predecessors(tmp_path: Path) -> None:
    modelo_dir = _modelo(tmp_path)
    _write_edition(
        modelo_dir,
        "2024",
        year=2024,
        casillas=_casilla("2024", "01"),
        layouts=(_layout("2024", "l24", _field("2024", "m999-2024.r.f001", 1, casilla_id="01")),),
    )
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        casillas="",
        layouts=(_layout("2025", "l25", _field("2025", "m999-2025.r.f001", 1, casilla_id="01")),),
        manifest_extra='predecessor = "2024"\n',
    )

    revisions = load_modelo_directory(modelo_dir).revisions

    assert _refs(revisions["2024"]) == {"01": ("m999-2024.r.f001",)}
    assert _refs(revisions["2025"]) == {"01": ("m999-2025.r.f001",)}


def test_two_layouts_addressing_one_casilla_are_refused_rather_than_merged(tmp_path: Path) -> None:
    one_layout = _single(
        tmp_path / "one",
        casillas=_TWO_CASILLAS,
        layouts=(_layout("2025", "la", _field("2025", "m999.a.f001", 1, casilla_id="01")),),
    )
    assert _refs(one_layout)["01"] == ("m999.a.f001",)

    with pytest.raises(RegistryLoadError, match=r"export layouts 'la' and 'lb' both address casilla '01'"):
        _single(
            tmp_path / "two",
            casillas=_TWO_CASILLAS,
            layouts=(
                _layout("2025", "la", _field("2025", "m999.a.f001", 1, casilla_id="01")),
                _layout("2025", "lb", _field("2025", "m999.b.f001", 1, casilla_id="01")),
            ),
        )


def test_a_field_resolving_to_a_casilla_the_materialised_edition_lacks_is_refused(tmp_path: Path) -> None:
    modelo_dir = _modelo(tmp_path)
    _write_edition(modelo_dir, "2024", year=2024, casillas=_casilla("2024", "01"))
    _write_edition(
        modelo_dir,
        "2025",
        year=2025,
        casillas="",
        layouts=(_layout("2025", "l", _field("2025", "m999.r.f001", 1, casilla_id="01")),),
        manifest_extra='predecessor = "2024"\n',
    )
    # The inherited row is part of the materialised edition, so addressing it loads.
    assert _refs(load_modelo_directory(modelo_dir).revisions["2025"]) == {"01": ("m999.r.f001",)}

    layout_path = modelo_dir / "revisions" / "2025" / "export_layouts" / "0001-layout.toml"
    layout_path.write_text(
        _layout("2025", "l", _field("2025", "m999.r.f001", 1, casilla_id="99")), encoding="utf-8", newline="\n"
    )
    with pytest.raises(RegistryLoadError, match=r"resolve to casillas \['99'\], which the edition does not declare"):
        load_modelo_directory(modelo_dir)


def test_an_authored_export_refs_key_is_refused(tmp_path: Path) -> None:
    layouts = (_layout("2025", "l", _field("2025", "m999.r.f001", 1, casilla_id="01")),)
    derived = _single(tmp_path / "derived", casillas=_casilla("2025", "01"), layouts=layouts)
    assert _refs(derived) == {"01": ("m999.r.f001",)}

    with pytest.raises(RegistryLoadError, match=r"casillas \['01'\] declare export_refs"):
        _single(
            tmp_path / "authored",
            casillas=_casilla("2025", "01", extra='export_refs = ["m999.r.f001"]\n'),
            layouts=layouts,
        )


def _row_record(fields: str, *, binding_record: bool, slot_casilla: str = "01") -> str:
    record_extra = 'repeat = "binding_rows"\n' + ('binding_record = "contraparte"\n' if binding_record else "")
    return _layout("2025", "l", fields, record_extra=record_extra, row_map=f'{_ROW_SLOT} = "{slot_casilla}"')


def test_a_row_mapped_binding_field_derives_the_back_reference_of_the_casilla_its_slot_names(tmp_path: Path) -> None:
    binding_field = _field("2025", "m999.r.f005", 1, binding=_ROW_BINDING)
    mapped = _single(
        tmp_path / "mapped",
        casillas=_TWO_CASILLAS,
        layouts=(_row_record(binding_field, binding_record=False),),
        bindings=_row_binding("2025"),
    )
    assert _refs(mapped) == {"01": ("m999.r.f005",), "02": ()}

    # The edge is the record's row mapping, not the field: remapping the slot moves it.
    remapped = _single(
        tmp_path / "remapped",
        casillas=_TWO_CASILLAS,
        layouts=(_row_record(binding_field, binding_record=False, slot_casilla="02"),),
        bindings=_row_binding("2025"),
    )
    assert _refs(remapped) == {"01": (), "02": ("m999.r.f005",)}


def test_a_binding_record_row_template_contributes_no_casilla_edge(tmp_path: Path) -> None:
    fields = _field("2025", "m999.r.f001", 1, casilla_id="01") + _field("2025", "m999.r.f002", 2, binding=_ROW_BINDING)
    template = _single(
        tmp_path / "template",
        casillas=_TWO_CASILLAS,
        layouts=(_row_record(fields, binding_record=True),),
        bindings=_row_binding("2025"),
    )
    assert _refs(template) == {"01": (), "02": ()}

    # The same record without binding_record takes its positions from the design, so both fields are edges.
    design = _single(
        tmp_path / "design",
        casillas=_TWO_CASILLAS,
        layouts=(_row_record(fields, binding_record=False),),
        bindings=_row_binding("2025"),
    )
    assert _refs(design) == {"01": ("m999.r.f001", "m999.r.f002"), "02": ()}
