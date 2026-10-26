"""Deadline-window qualifier compiler and fragment-ownership tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import (
    standard_manifest_text as _standard_manifest_text,
)
from ..conformance.loader_directory_mode_support import (
    standard_revision_preamble_text as _standard_revision_preamble_text,
)

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


def _write_deadline_modelo(root: Path, title: str, window_text: str) -> Path:
    modelo_dir = root / "999"
    revision_dir = modelo_dir / "revisions" / "2025"
    deadline_dir = revision_dir / "deadline_windows"
    deadline_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(_standard_manifest_text(title), encoding="utf-8")
    (revision_dir / "revision.toml").write_text(_standard_revision_preamble_text(), encoding="utf-8")
    (deadline_dir / "0001-deadline-windows.toml").write_text(window_text, encoding="utf-8")
    return modelo_dir


def test_qualified_deadline_window_compiles_its_typed_scopes(tmp_path: Path) -> None:
    modelo_dir = _write_deadline_modelo(tmp_path, "qualified deadline", _QUALIFIED_WINDOW)

    window = load_modelo_directory(modelo_dir).revisions["2025"].deadline_windows[0]

    assert window.resultado_scope is ResultDisposition.INGRESO
    assert window.tipo_renta_scope == ("01", "35")


@pytest.mark.parametrize("qualifier", ["resultado_scope", "tipo_renta_scope"])
def test_revision_level_deadline_qualifier_is_refused_outside_deadline_window_rows(
    tmp_path: Path,
    qualifier: str,
) -> None:
    value = '"I"' if qualifier == "resultado_scope" else '["01"]'
    modelo_dir = _write_deadline_modelo(tmp_path, "misplaced qualifier", _QUALIFIED_WINDOW)
    revision_manifest = modelo_dir / "revisions" / "2025" / "revision.toml"
    revision_manifest.write_text(
        _standard_revision_preamble_text() + f"{qualifier} = {value}\n",
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="Extra inputs are not permitted"):
        load_modelo_directory(modelo_dir)


def test_invalid_resultado_scope_is_refused_by_the_schema(tmp_path: Path) -> None:
    invalid_window = _QUALIFIED_WINDOW.replace('resultado_scope = "I"', 'resultado_scope = "invented"')
    modelo_dir = _write_deadline_modelo(tmp_path, "invalid deadline", invalid_window)

    with pytest.raises(RegistryLoadError) as exc_info:
        load_modelo_directory(modelo_dir)

    message = str(exc_info.value)
    assert "1 validation error" in message
    assert "resultado_scope" in message
