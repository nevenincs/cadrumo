"""Deadline-window qualifier compiler and fragment-ownership tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core import ResultDisposition, freeze_toml, read_toml

from .._errors import RegistryLoadError
from .._loader import _compile_deadline_window_qualifiers, load_modelo_directory, load_modelo_file
from ._loader_directory_mode_support import _standard_manifest_text, _standard_revision_preamble_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_QUALIFIED_WINDOW = """
[[revisions."2025".deadline_windows]]
id = "modelo-999-2025-0a-qualified"
filing_year = 2025
period = "2025 0A"
period_kind = "annual"
opens_on = 2026-01-01
closes_on = 2026-01-20
resultado_scope = "I"
tipo_renta_scope = ["01", "35"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
"""


def test_qualified_deadline_window_loads_identically_from_single_and_fragmented_toml(tmp_path: Path) -> None:
    single = tmp_path / "999.toml"
    single.write_text(
        _standard_manifest_text("qualified deadline") + _standard_revision_preamble_text() + _QUALIFIED_WINDOW,
        encoding="utf-8",
    )

    modelo_dir = tmp_path / "999"
    revision_dir = modelo_dir / "revisions" / "2025"
    deadline_dir = revision_dir / "deadline_windows"
    deadline_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(_standard_manifest_text("qualified deadline"), encoding="utf-8")
    (revision_dir / "revision.toml").write_text(_standard_revision_preamble_text(), encoding="utf-8")
    (deadline_dir / "0001-deadline-windows.toml").write_text(_QUALIFIED_WINDOW, encoding="utf-8")

    from_file = load_modelo_file(single)
    from_fragments = load_modelo_directory(modelo_dir)
    assert from_fragments == from_file
    window = from_fragments.revisions["2025"].deadline_windows[0]
    assert window.resultado_scope is ResultDisposition.INGRESO
    assert window.tipo_renta_scope == ("01", "35")


def test_unqualified_frozen_deadline_row_is_not_rewritten(tmp_path: Path) -> None:
    source = tmp_path / "window.toml"
    source.write_text(
        "[window]\n"
        'id = "legacy"\n'
        'period = "2025 0A"\n'
        'legal_refs = ["legal"]\n',
        encoding="utf-8",
    )
    frozen_row = freeze_toml(read_toml(source, error_factory=RegistryLoadError))["window"]

    assert _compile_deadline_window_qualifiers(source, frozen_row) is frozen_row


@pytest.mark.parametrize("qualifier", ["resultado_scope", "tipo_renta_scope"])
def test_revision_level_deadline_qualifier_is_refused_outside_deadline_window_rows(
    tmp_path: Path,
    qualifier: str,
) -> None:
    source = tmp_path / f"misplaced-{qualifier}.toml"
    value = '"I"' if qualifier == "resultado_scope" else '["01"]'
    source.write_text(
        _standard_manifest_text("misplaced qualifier")
        + _standard_revision_preamble_text()
        + f"{qualifier} = {value}\n",
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="must be declared inside a deadline_windows row"):
        load_modelo_file(source)

