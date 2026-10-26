"""The record-design reader keys every row by its whole record heading."""

from pathlib import Path

import pytest

from dev.registry.record_design_labels import read_record_design

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TABLE_HEADER = "Nº | Posic. | Lon | Tipo | Descripción | Validación | Contenido\n"


def test_multi_word_record_headings_stay_distinct_records(tmp_path: Path) -> None:
    sidecar = tmp_path / "design.extracted.md"
    sidecar.write_text(
        "# Pág. 2\n\n"
        + _TABLE_HEADER
        + "1 | 25 | 17 | N | Operaciones - Base imponible [01] |  | \n\n"
        + "# Pág. 2 bis\n\n"
        + _TABLE_HEADER
        + "1 | 25 | 17 | N | Total cuotas IVA [47] |  | \n",
        encoding="utf-8",
    )
    rows = read_record_design(sidecar)
    assert rows[("Pág. 2", 25)].label == "Operaciones - Base imponible [01]"
    assert rows[("Pág. 2 bis", 25)].label == "Total cuotas IVA [47]"
    assert {record for record, _ in rows} == {"Pág. 2", "Pág. 2 bis"}


def test_trailing_whitespace_does_not_change_the_record_key(tmp_path: Path) -> None:
    sidecar = tmp_path / "design.extracted.md"
    sidecar.write_text("# DP30301   \n\n" + _TABLE_HEADER + "1 | 1 | 2 | An | Constante |  | \n", encoding="utf-8")
    assert set(read_record_design(sidecar)) == {("DP30301", 1)}
