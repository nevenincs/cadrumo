"""Deadline-window qualifier compiler and fragment-ownership tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.loader import load_modelo_directory
from ..conformance.loader_directory_mode_support import standard_manifest_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon
_REVISION_ID = str(_YEAR)
_QUALIFIED_WINDOW = f"""
[[revisions."{_REVISION_ID}".deadline_windows]]
id = "modelo-999-{_YEAR}-0a-qualified"
filing_year = {_YEAR}
period = "{_YEAR} 0A"
period_kind = "annual"
opens_on = {_YEAR + 1}-01-01
closes_on = {_YEAR + 1}-01-20
resultado_scope = "I"
tipo_renta_scope = ["01", "35"]
legal_refs = ["ley-58-2003:art-29"]
source_refs = ["aeat-manual"]
"""


def _revision_preamble() -> str:
    return (
        f'[revisions."{_REVISION_ID}"]\n'
        f"valid_from = {_YEAR}-01-01\n"
        f'period_selector = {{ years = [{_YEAR}], periods = ["0A"] }}\n'
        'legal_refs = ["ley-58-2003:art-29"]\n'
        'source_refs = ["aeat-manual"]\n'
    )


def _write_deadline_modelo(root: Path, title: str, window_text: str) -> Path:
    modelo_dir = root / "999"
    revision_dir = modelo_dir / "revisions" / _REVISION_ID
    deadline_dir = revision_dir / "deadline_windows"
    deadline_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(standard_manifest_text(title), encoding="utf-8")
    (revision_dir / "revision.toml").write_text(_revision_preamble(), encoding="utf-8")
    (deadline_dir / "0001-deadline-windows.toml").write_text(window_text, encoding="utf-8")
    return modelo_dir


def test_qualified_deadline_window_compiles_its_typed_scopes(tmp_path: Path) -> None:
    modelo_dir = _write_deadline_modelo(tmp_path, "qualified deadline", _QUALIFIED_WINDOW)

    window = load_modelo_directory(modelo_dir).revisions[_REVISION_ID].deadline_windows[0]

    assert window.resultado_scope is ResultDisposition.INGRESO
    assert window.tipo_renta_scope == ("01", "35")


@pytest.mark.parametrize("qualifier", ["resultado_scope", "tipo_renta_scope"])
def test_revision_level_deadline_qualifier_is_refused_outside_deadline_window_rows(
    tmp_path: Path,
    qualifier: str,
) -> None:
    value = '"I"' if qualifier == "resultado_scope" else '["01"]'
    modelo_dir = _write_deadline_modelo(tmp_path, "misplaced qualifier", _QUALIFIED_WINDOW)
    revision_manifest = modelo_dir / "revisions" / _REVISION_ID / "revision.toml"
    revision_manifest.write_text(
        _revision_preamble() + f"{qualifier} = {value}\n",
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
