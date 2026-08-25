"""Deadline-window qualifier compiler and fragment-ownership tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core import ResultDisposition
from ..errors import RegistryLoadError
from ..loader import load_modelo_directory, load_modelo_file
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

    with pytest.raises(RegistryLoadError, match="Extra inputs are not permitted"):
        load_modelo_file(source)


def test_invalid_resultado_receives_same_schema_verdict_from_both_public_load_paths(tmp_path: Path) -> None:
    invalid_window = _QUALIFIED_WINDOW.replace('resultado_scope = "I"', 'resultado_scope = "invented"')
    single = tmp_path / "999.toml"
    single.write_text(
        _standard_manifest_text("invalid deadline") + _standard_revision_preamble_text() + invalid_window,
        encoding="utf-8",
    )
    modelo_dir = tmp_path / "999"
    revision_dir = modelo_dir / "revisions" / "2025"
    deadline_dir = revision_dir / "deadline_windows"
    deadline_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(_standard_manifest_text("invalid deadline"), encoding="utf-8")
    (revision_dir / "revision.toml").write_text(_standard_revision_preamble_text(), encoding="utf-8")
    (deadline_dir / "0001-deadline-windows.toml").write_text(invalid_window, encoding="utf-8")

    verdicts: list[str] = []
    for load in (lambda: load_modelo_file(single), lambda: load_modelo_directory(modelo_dir)):
        with pytest.raises(RegistryLoadError) as exc_info:
            load()
        verdicts.append("1 validation error" + str(exc_info.value).split("1 validation error", maxsplit=1)[1])
    assert verdicts[0] == verdicts[1]
    assert "resultado_scope" in verdicts[0]
