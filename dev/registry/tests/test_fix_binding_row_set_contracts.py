"""Behaviour of the row-producing binding value-contract normaliser.

Every case builds an isolated temporary registry tree seeded from one small
authored modelo, so the contributor's working tree is never mutated and the
detector teeth (a refused row, an untouched file, a dry run) are proven on real
files rather than on a patched module.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest

from ..fix_binding_row_set_contracts import (
    REGISTRY_MODELOS_ROOT,
    FixReport,
    RowSetRefusalError,
    fix_modelo,
    row_set_value_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


SEED_MODELO = "151"
REVISION = "2025-y-siguientes"
BASE_TAIL = 'legal_refs = ["ley-35-2006:art-93"]\nsource_refs = ["aeat-modelo-151-procedure"]\n'


def _seed_tree(tmp_path: Path) -> Path:
    modelos_root = tmp_path / "modelos"
    modelos_root.mkdir()
    shutil.copytree(REGISTRY_MODELOS_ROOT / SEED_MODELO, modelos_root / SEED_MODELO)
    return modelos_root


def _bindings_file(modelos_root: Path) -> Path:
    directory = modelos_root / SEED_MODELO / "revisions" / REVISION / "bindings"
    return next(iter(sorted(directory.glob("*.toml"))))


def _row(fields: str) -> str:
    return f'[[revisions."{REVISION}".bindings]]\n{fields}\n'


def _rows(path: Path) -> list[dict[str, Any]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return list(data["revisions"][REVISION]["bindings"])


def _run(modelos_root: Path, *, apply: bool = True) -> FixReport:
    report = FixReport()
    fix_modelo(SEED_MODELO, report, apply=apply, modelos_root=modelos_root)
    return report


_WITHHOLDING_PROVIDER = (
    'provider = { kind = "withholding", fact = "row_field", row_field = "perceptor_tax_id", '
    'grouping = "per_perceptor_clave", record = "perceptor", data_type = "text" }\n'
)


def test_the_retired_rows_data_type_becomes_the_provider_element_type(tmp_path: Path) -> None:
    """``data_type = "rows"`` is replaced by the per-row element type the provider carries."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    path.write_text(
        _row(
            'id = "m151-row-nif"\n'
            + _WITHHOLDING_PROVIDER
            + 'value = { data_type = "rows", channel = "row_set", row_grouping = "withholding" }\n'
            'aggregation = { op = "rows" }\n' + BASE_TAIL
        ),
        encoding="utf-8",
    )

    report = _run(modelos_root)

    assert report.refusals == []
    assert report.rows_fixed_by_modelo[SEED_MODELO] == 1
    assert _rows(path)[0]["value"] == {
        "data_type": "text",
        "channel": "row_set",
        "row_grouping": "withholding",
    }


def test_a_scalar_channelled_row_family_moves_onto_the_row_set_channel(tmp_path: Path) -> None:
    """A row-producing binding authored on a scalar channel keeps its element type and gains the transport."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    provider = _WITHHOLDING_PROVIDER.replace(', data_type = "text" }', " }")
    path.write_text(
        _row(
            'id = "m151-row-scalar-channel"\n'
            + provider
            + 'value = { data_type = "text", channel = "text" }\naggregation = { op = "rows" }\n'
            + BASE_TAIL
        ),
        encoding="utf-8",
    )

    report = _run(modelos_root)

    assert report.refusals == []
    assert _rows(path)[0]["value"] == {
        "data_type": "text",
        "channel": "row_set",
        "row_grouping": "withholding",
    }


def test_a_provider_native_row_family_gains_the_channel_but_no_grouping(tmp_path: Path) -> None:
    """A row-producing source outside the grouped row-assembly axis declares no grouping, never an invented one."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    path.write_text(
        _row(
            'id = "m151-profile-rows"\n'
            'provider = { kind = "profile", profile_model = "RentaFamilyProfile", collection = "descendants", '
            'field = "display_name", repeating = true }\n'
            'value = { data_type = "text", channel = "text" }\naggregation = { op = "rows" }\n' + BASE_TAIL
        ),
        encoding="utf-8",
    )

    report = _run(modelos_root)

    assert report.refusals == []
    assert _rows(path)[0]["value"] == {"data_type": "text", "channel": "row_set"}


def test_a_row_already_on_the_row_set_shape_is_left_alone(tmp_path: Path) -> None:
    """An already-correct contract counts as such and produces no rewrite."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    original = _row(
        'id = "m151-row-done"\n'
        + _WITHHOLDING_PROVIDER
        + 'value = { data_type = "text", channel = "row_set", row_grouping = "withholding" }\n'
        'aggregation = { op = "rows" }\n' + BASE_TAIL
    )
    path.write_text(original, encoding="utf-8")

    report = _run(modelos_root)

    assert report.refusals == []
    assert report.rows_fixed == 0
    assert report.rows_already_correct == 1
    assert path.read_text(encoding="utf-8") == original


def test_a_dry_run_reports_the_rewrite_without_writing_it(tmp_path: Path) -> None:
    """The preview counts the same rows the apply run would rewrite and writes no byte."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    original = _row(
        'id = "m151-row-nif"\n'
        + _WITHHOLDING_PROVIDER
        + 'value = { data_type = "rows", channel = "row_set", row_grouping = "withholding" }\n'
        'aggregation = { op = "rows" }\n' + BASE_TAIL
    )
    path.write_text(original, encoding="utf-8")

    report = _run(modelos_root, apply=False)

    assert report.rows_fixed_by_modelo[SEED_MODELO] == 1
    assert path.read_text(encoding="utf-8") == original


def test_a_row_with_no_derivable_element_type_is_refused() -> None:
    """Neither the provider nor the value stating an element type is a refusal, not a guess."""
    with pytest.raises(RowSetRefusalError, match="no per-row element data type"):
        row_set_value_for(
            {
                "id": "m151-elementless",
                "provider": {"kind": "withholding", "fact": "row_field"},
                "value": {"data_type": "rows", "channel": "row_set", "row_grouping": "withholding"},
            },
        )


def test_a_non_rows_binding_is_never_touched(tmp_path: Path) -> None:
    """A scalar-folding binding keeps its scalar contract."""
    modelos_root = _seed_tree(tmp_path)
    path = _bindings_file(modelos_root)
    original = _row(
        'id = "m151-scalar"\n'
        'provider = { kind = "ledger_impatriado_income_aggregation", modelo = "151", '
        'target_casilla_id = "impatriado.base-liquidable-general", fact = "ingresos_integros_sum" }\n'
        'value = { data_type = "money", channel = "decimal" }\naggregation = { op = "sum" }\n' + BASE_TAIL
    )
    path.write_text(original, encoding="utf-8")

    report = _run(modelos_root)

    assert report.refusals == []
    assert report.rows_fixed == 0
    assert path.read_text(encoding="utf-8") == original
