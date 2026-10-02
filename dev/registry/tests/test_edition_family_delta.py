"""The keyed-family collapse writes the smallest delta the loader reproduces, and nothing else.

Every test builds a small modelo on disk, runs the real collapse into a copy
and loads both through the real directory loader: the collapse itself refuses
a candidate that hydrates differently from its source, so each test states
what the delta must hold and the loader proves it means the same thing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.toml import parse_toml

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import write_standard_manifest
from ..edition_delta_migration import assess_migration_state
from ..edition_family_delta import collapse_keyed_families, restates_stated_whole_sequence

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REF: Final = "ley-58-2003:art-29"
_SOURCE: Final = "aeat-manual"
_FORMULAS: Final = ("modelo-999-a", "modelo-999-b", "modelo-999-c", "modelo-999-d")


def _formula(revision_id: str, formula_id: str, target: str) -> str:
    return (
        f'[[revisions."{revision_id}".formulas]]\nid = "{formula_id}"\ntarget_casilla_id = "{target}"\n'
        f'expression = {{ literal = "0" }}\nlegal_refs = ["{_REF}"]\nsource_refs = ["{_SOURCE}"]\n\n'
    )


def _casillas(revision_id: str) -> str:
    return "".join(
        f'[[revisions."{revision_id}".casillas]]\nid = "000{index}"\nnumber = "{index}"\n'
        f'section = ["liquidacion"]\ncontinuidad_id = "linaje-{index}"\n'
        f'legal_refs = ["{_REF}"]\nsource_refs = ["{_SOURCE}"]\n\n'
        for index in range(1, 5)
    )


def _window(revision_id: str, year: int) -> str:
    return (
        f'[[revisions."{revision_id}".deadline_windows]]\nid = "modelo-999-{year}-0a"\nfiling_year = {year}\n'
        f'period = "{year} 0A"\nperiod_kind = "annual"\nopens_on = {year + 1}-01-01\n'
        f'closes_on = {year + 1}-01-31\nlegal_refs = ["{_REF}"]\nsource_refs = ["{_SOURCE}"]\n\n'
    )


def _layout(revision_id: str, *records: str) -> str:
    text = (
        f'[[revisions."{revision_id}".export_layouts]]\nid = "fichero-boe"\n'
        f'legal_refs = ["{_REF}"]\nsource_refs = ["{_SOURCE}"]\n\n'
    )
    for order, record in enumerate(records):
        text += (
            f'[[revisions."{revision_id}".export_layouts.records]]\nid = "{record}"\nrecord_type = "{record}"\n'
            f'order = {order}\nencoding = "iso-8859-1"\nline_ending = "none"\n\n'
        )
    return text


def _edition(
    modelo_dir: Path,
    revision_id: str,
    *,
    manifest_extra: str = "",
    sections: dict[str, str],
) -> Path:
    year = int(revision_id)
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    (revision_dir / "revision.toml").write_text(
        f'[revisions."{revision_id}"]\nvalid_from = {year}-01-01\nvalid_to = {year}-12-31\n'
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_REF}"]\nsource_refs = ["{_SOURCE}"]\n' + manifest_extra,
        encoding="utf-8",
        newline="\n",
    )
    for section, text in sections.items():
        (revision_dir / section).mkdir()
        (revision_dir / section / "0001-declarations.toml").write_text(text, encoding="utf-8", newline="\n")
    return revision_dir


def _modelo(root: Path) -> Path:
    modelo_dir = root / "999"
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Collapse fixture")
    return modelo_dir


def _manifest(candidate: Path, revision_id: str) -> dict[str, object]:
    document = parse_toml((candidate / "revisions" / revision_id / "revision.toml").read_text(encoding="utf-8"))
    return dict(document["revisions"][revision_id])


def _operations(candidate: Path, revision_id: str, name: str, family: str) -> list[dict[str, object]]:
    raw = _manifest(candidate, revision_id).get(name, ())
    if not isinstance(raw, list | tuple):
        return []
    return [dict(item) for item in raw if isinstance(item, dict) and item.get("family") == family]


def test_a_declared_position_is_kept_and_no_greedy_position_is_appended(tmp_path: Path) -> None:
    """The order ``b c d a`` needs one move; declared, it stays the family's only position.

    The successor restates ``b`` unchanged, which is what sends the collapse
    over the family. A greedy scan from the merge order moved ``b``, ``c`` and
    ``d`` into place and appended those three moves after the one already
    declared, so the family carried four positions for one move.
    """
    source = _modelo(tmp_path / "source")
    _edition(
        source,
        "2024",
        sections={
            "casillas": _casillas("2024"),
            "formulas": "".join(
                _formula("2024", formula_id, f"000{index}") for index, formula_id in enumerate(_FORMULAS, start=1)
            ),
        },
    )
    _edition(
        source,
        "2025",
        manifest_extra=(
            'predecessor = "2024"\n'
            '[[revisions."2025".family_positions]]\nfamily = "formulas"\nid = "modelo-999-a"\nposition = 3\n'
        ),
        sections={"formulas": _formula("2025", "modelo-999-b", "0002")},
    )
    expected = ("modelo-999-b", "modelo-999-c", "modelo-999-d", "modelo-999-a")
    assert tuple(item.id for item in load_modelo_directory(source).revisions["2025"].formulas) == expected
    candidate = tmp_path / "candidate" / "999"

    collapse_keyed_families(source, candidate)

    positions = _operations(candidate, "2025", "family_positions", "formulas")
    assert [(item["id"], item["position"]) for item in positions] == [("modelo-999-a", 3)]
    assert tuple(item.id for item in load_modelo_directory(candidate).revisions["2025"].formulas) == expected


def test_the_order_is_restored_with_one_move_per_member_out_of_place(tmp_path: Path) -> None:
    """With no position declared the collapse emits the minimal set: one move, not three."""
    source = _modelo(tmp_path / "source")
    _edition(
        source,
        "2024",
        sections={
            "casillas": _casillas("2024"),
            "formulas": "".join(
                _formula("2024", formula_id, f"000{index}") for index, formula_id in enumerate(_FORMULAS, start=1)
            ),
        },
    )
    # A restated family carries its members in exactly the order it states them.
    _edition(
        source,
        "2025",
        manifest_extra=(
            'predecessor = "2024"\n'
            'restated_families = [{ family = "formulas", cause = "official_structure_differs", '
            'reason = "The design lists the first formula last." }]\n'
        ),
        sections={
            "formulas": "".join(
                _formula("2025", formula_id, f"000{index}")
                for index, formula_id in (
                    (2, "modelo-999-b"),
                    (3, "modelo-999-c"),
                    (4, "modelo-999-d"),
                    (1, "modelo-999-a"),
                )
            )
        },
    )
    candidate = tmp_path / "candidate" / "999"

    collapse_keyed_families(source, candidate)

    positions = _operations(candidate, "2025", "family_positions", "formulas")
    assert [(item["id"], item["position"]) for item in positions] == [("modelo-999-a", 3)]
    assert tuple(item.id for item in load_modelo_directory(candidate).revisions["2025"].formulas) == (
        "modelo-999-b",
        "modelo-999-c",
        "modelo-999-d",
        "modelo-999-a",
    )


def test_a_casilla_storage_baseline_declared_alone_leaves_the_families_as_authored(tmp_path: Path) -> None:
    """Reusing casilla storage is a decision about casillas; the families are not given a baseline for it."""
    source = _modelo(tmp_path / "source")
    formulas = "".join(
        _formula("{rev}", formula_id, f"000{index}") for index, formula_id in enumerate(_FORMULAS, start=1)
    )
    _edition(source, "2024", sections={"casillas": _casillas("2024"), "formulas": formulas.replace("{rev}", "2024")})
    _edition(
        source,
        "2025",
        manifest_extra='casilla_storage_baseline = "2024"\n',
        sections={"formulas": formulas.replace("{rev}", "2025")},
    )
    assert not assess_migration_state(source).minimal, "the fixture must send the collapse over its families"
    candidate = tmp_path / "candidate" / "999"

    collapse_keyed_families(source, candidate)

    manifest = _manifest(candidate, "2025")
    assert "family_storage_baseline" not in manifest
    assert "family_overrides" not in manifest
    assert (candidate / "revisions" / "2025" / "formulas" / "0001-declarations.toml").read_text(
        encoding="utf-8"
    ) == formulas.replace("{rev}", "2025")


def test_a_family_baseline_the_author_declared_is_still_used(tmp_path: Path) -> None:
    """Detector teeth: the same restatement under a declared family baseline is collapsed."""
    source = _modelo(tmp_path / "source")
    formulas = "".join(
        _formula("{rev}", formula_id, f"000{index}") for index, formula_id in enumerate(_FORMULAS, start=1)
    )
    _edition(source, "2024", sections={"casillas": _casillas("2024"), "formulas": formulas.replace("{rev}", "2024")})
    _edition(
        source,
        "2025",
        manifest_extra='casilla_storage_baseline = "2024"\nfamily_storage_baseline = "2024"\n',
        sections={"formulas": formulas.replace("{rev}", "2025")},
    )
    candidate = tmp_path / "candidate" / "999"

    collapse_keyed_families(source, candidate)

    assert not (candidate / "revisions" / "2025" / "formulas").exists()
    assert len(load_modelo_directory(candidate).revisions["2025"].formulas) == len(_FORMULAS)


def _layout_findings(modelo_dir: Path) -> list[object]:
    return [
        item
        for item in assess_migration_state(modelo_dir).unresolved_duplication
        if item.get("family") == "export_layouts"
    ]


def _layout_modelo(root: Path, *, successor_layout: str, successor_extra: str = "") -> Path:
    """A 2024 layout and a 2025 edition storing its families against 2024.

    The 2025 edition restates its casillas in full, which is what sends the
    collapse over it; the layout is the family under test.
    """
    source = _modelo(root)
    _edition(
        source,
        "2024",
        sections={"casillas": _casillas("2024"), "export_layouts": _layout("2024", "cabecera", "detalle")},
    )
    sections = {"export_layouts": successor_layout} if successor_layout else {}
    _edition(
        source,
        "2025",
        manifest_extra='family_storage_baseline = "2024"\nscoped_families = ["export_layouts"]\n' + successor_extra,
        sections={"casillas": _casillas("2025"), **sections},
    )
    return source


def test_a_layout_whose_records_differ_stays_stated_whole(tmp_path: Path) -> None:
    """An export layout is a per-edition statement: it is never folded into a record-replacing override."""
    source = _layout_modelo(tmp_path / "source", successor_layout=_layout("2025", "cabecera-2025", "detalle-2025"))
    candidate = tmp_path / "candidate" / "999"

    collapse_keyed_families(source, candidate)

    assert _operations(candidate, "2025", "family_overrides", "export_layouts") == []
    stated = (candidate / "revisions" / "2025" / "export_layouts" / "0001-declarations.toml").read_text(
        encoding="utf-8"
    )
    assert 'id = "cabecera-2025"' in stated
    assert 'id = "detalle-2025"' in stated
    assert not _layout_findings(candidate)


def test_an_identical_layout_is_still_inherited(tmp_path: Path) -> None:
    """The normal path: a layout the edition restates unchanged is dropped and inherited through its scope."""
    source = _layout_modelo(tmp_path / "source", successor_layout=_layout("2025", "cabecera", "detalle"))
    candidate = tmp_path / "candidate" / "999"

    collapse_keyed_families(source, candidate)

    assert not (candidate / "revisions" / "2025" / "export_layouts").exists()
    (layout,) = load_modelo_directory(candidate).revisions["2025"].export_layouts
    assert [record.id for record in layout.records] == ["cabecera", "detalle"]


def test_a_record_folding_override_is_reported_and_stated_again(tmp_path: Path) -> None:
    """An existing override that removes the baseline's records and re-adds them is turned back into the layout."""
    folded = (
        '[[revisions."2025".family_overrides]]\nfamily = "export_layouts"\n'
        'selector = { revision = "2024", id = "fichero-boe" }\n'
        "sequence_removals = { records = [0, 1] }\n"
        'sequence_additions = { records = [{ id = "cabecera-2025", record_type = "cabecera-2025", order = 0, '
        'encoding = "iso-8859-1", line_ending = "none" }, { id = "detalle-2025", record_type = "detalle-2025", '
        'order = 1, encoding = "iso-8859-1", line_ending = "none" }] }\n'
    )
    source = _layout_modelo(tmp_path / "source", successor_layout="", successor_extra=folded)
    operation = _operations(source, "2025", "family_overrides", "export_layouts")[0]
    assert restates_stated_whole_sequence("export_layouts", operation)
    assert _layout_findings(source)
    candidate = tmp_path / "candidate" / "999"

    collapse_keyed_families(source, candidate)

    assert _operations(candidate, "2025", "family_overrides", "export_layouts") == []
    (layout,) = load_modelo_directory(candidate).revisions["2025"].export_layouts
    assert [record.id for record in layout.records] == ["cabecera-2025", "detalle-2025"]
    assert not _layout_findings(candidate)


def _window_modelo(root: Path, *, successor_extra: str) -> Path:
    source = _modelo(root)
    _edition(source, "2024", sections={"casillas": _casillas("2024"), "deadline_windows": _window("2024", 2024)})
    _edition(
        source,
        "2025",
        manifest_extra='family_storage_baseline = "2024"\n' + successor_extra,
        sections={"casillas": _casillas("2025"), "deadline_windows": _window("2025", 2025)},
    )
    return source


def test_a_storage_baseline_never_carries_another_periods_window(tmp_path: Path) -> None:
    """The loader withholds a window of a period the edition does not file on a storage edge too."""
    source = _window_modelo(tmp_path, successor_extra="")

    windows = load_modelo_directory(source).revisions["2025"].deadline_windows

    assert [window.id for window in windows] == ["modelo-999-2025-0a"]


def test_a_removal_of_another_periods_window_is_redundant_and_dropped(tmp_path: Path) -> None:
    """An explicit removal of a window the edition's period never inherits is dropped, and none is written."""
    removal = (
        '[[revisions."2025".family_removals]]\nfamily = "deadline_windows"\n'
        'selector = { revision = "2024", id = "modelo-999-2024-0a" }\n'
    )
    # A restated casilla row sends the collapse over the edition at all.
    source = _window_modelo(tmp_path / "source", successor_extra=removal)
    candidate = tmp_path / "candidate" / "999"

    collapse_keyed_families(source, candidate)

    assert _operations(candidate, "2025", "family_removals", "deadline_windows") == []
    windows = load_modelo_directory(candidate).revisions["2025"].deadline_windows
    assert [window.id for window in windows] == ["modelo-999-2025-0a"]
