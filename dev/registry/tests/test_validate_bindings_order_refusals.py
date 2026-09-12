"""Detector teeth for the two binding-order refusals.

Binding declaration order is a merge artefact of the fragment filenames, so a
consumer that reads the binding tuple positionally or takes a first match is
only safe while the declaration it reads is unique. Two such duplicates are
refused at load:

* a second ``prorrata_regularizacion`` binding, because the annual
  regularisation reads its four source roles positionally out of the
  concatenated source casillas of every prorrata binding;
* two row bindings claiming one ``row_field`` of one record, because export
  field derivation keeps the first claimant and silently drops the rest.

Each refusal is provoked by editing a COPY of a live modelo in a temporary
tree, mirroring ``test_validate_bindings``: the bundled corpus is never
written, no production module is patched, and the clean path is asserted in the
same suite as the defect. A fixture that stopped refusing its own planted
duplicate would also have stopped refusing a real one.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_bindings import validate_binding_registration_section

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

_M303_REVISION = "2025"
_M303_BINDINGS = f"revisions/{_M303_REVISION}/bindings/0001-bindings.toml"
_M303_PRORRATA_ID = "modelo-303-prorrata-regularizacion-casilla-44"
_M303_PRORRATA_BLOCK = f'''
[[revisions.{_M303_REVISION}.bindings]]
id = "{_M303_PRORRATA_ID}-planted-duplicate"
provider = {{ kind = "prorrata_regularizacion", source_modelo = "303", source_casilla_ids = \
["iva.cuota-deducible-total", "iva.prorrata-volumen-con-derecho", "iva.prorrata-volumen-total", \
"iva.prorrata-porcentaje"], source_periods = ["1T", "2T", "3T", "4T"], \
regularizacion_output = "modelo_303_casilla_44" }}
value = {{ data_type = "money", channel = "decimal" }}
legal_refs = ["ley-37-1992:art-104", "ley-37-1992:art-105", "rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"]
source_refs = ["aeat-dr-303-2025", "aeat-modelo-303-procedure", "boe-modelo-303-2008-form"]

[[revisions.{_M303_REVISION}.bindings.source_citations]]
source_ref = "aeat-modelo-303-procedure"
required_text = ["modelo 303"]
'''

_M720_REVISION = "2013-y-siguientes"
_M720_BINDINGS = f"revisions/{_M720_REVISION}/bindings/0002-bindings.toml"
_M720_ROW_FIELD = "asset_class_code"
_M720_RECORD = "bien"
_M720_ROW_BLOCK = f'''
[[revisions."{_M720_REVISION}".bindings]]
id = "modelo-720-asset-row-class-planted-duplicate"
provider = {{ kind = "foreign_asset", fact = "row_field", row_field = "{_M720_ROW_FIELD}", \
grouping = "per_foreign_asset", record = "{_M720_RECORD}", data_type = "text" }}
value = {{ data_type = "text", channel = "row_set", row_grouping = "foreign_asset" }}
aggregation = {{ op = "rows" }}
legal_refs = ["orden-hap-72-2013:art-1", "rd-1065-2007:art-42-bis", "rd-1065-2007:art-42-ter", "ley-58-2003:art-93"]
source_refs = ["aeat-dr-720", "aeat-modelo-720-procedure"]

[[revisions."{_M720_REVISION}".bindings.source_citations]]
source_ref = "aeat-modelo-720-procedure"
required_text = ["bienes y derechos situados en el extranjero"]
'''


def _copy_modelo(tmp_path: Path, modelo_id: str) -> Path:
    """Copy one live modelo directory into an isolated temporary tree."""
    destination = tmp_path / modelo_id
    shutil.copytree(_MODELOS_ROOT / modelo_id, destination)
    return destination


def _append(tree: Path, relative: str, block: str) -> None:
    """Append one planted binding declaration to a copied fragment."""
    path = tree / relative
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n" + block, encoding="utf-8")


def _revision(tree: Path, revision_id: str) -> ModeloRevision:
    """Compile the copied tree and return one revision."""
    return load_modelo_directory(tree).revisions[revision_id]


def _failures(tree: Path, revision_id: str) -> list[str]:
    return validate_binding_registration_section(
        prefix=f"modelo {tree.name} revision {revision_id}",
        revision=_revision(tree, revision_id),
    )


def test_the_live_modelo_303_revision_passes_the_order_refusals(tmp_path: Path) -> None:
    assert _failures(_copy_modelo(tmp_path, "303"), _M303_REVISION) == []


def test_a_second_prorrata_regularizacion_binding_is_refused(tmp_path: Path) -> None:
    """Two prorrata bindings make the positional source roles merge-order dependent."""
    tree = _copy_modelo(tmp_path, "303")
    _append(tree, _M303_BINDINGS, _M303_PRORRATA_BLOCK)

    failures = _failures(tree, _M303_REVISION)

    refusals = [f for f in failures if "prorrata_regularizacion bindings are declared" in f]
    assert refusals, f"a second prorrata_regularizacion binding was not refused; failures were {failures}"
    assert _M303_PRORRATA_ID in refusals[0]
    assert f"{_M303_PRORRATA_ID}-planted-duplicate" in refusals[0]
    assert all(f"modelo 303 revision {_M303_REVISION}" in failure for failure in failures)


def test_the_live_modelo_720_revision_passes_the_order_refusals(tmp_path: Path) -> None:
    """Six row bindings on one record pass, because they claim six distinct slots.

    This is the negative half of the row-field refusal: a check that counted row
    bindings per record, rather than per slot, would pass the duplicate test
    below while refusing every legitimate multi-field repeated record. The
    Modelo 720 ``bien`` record is exactly that shape.
    """
    assert _failures(_copy_modelo(tmp_path, "720"), _M720_REVISION) == []


def test_two_row_bindings_claiming_one_row_field_are_refused(tmp_path: Path) -> None:
    """Only the first claimant of a row slot contributes a derived export field."""
    tree = _copy_modelo(tmp_path, "720")
    _append(tree, _M720_BINDINGS, _M720_ROW_BLOCK)

    failures = _failures(tree, _M720_REVISION)

    refusals = [f for f in failures if f"row field '{_M720_ROW_FIELD}'" in f]
    assert refusals, f"a duplicate row_field claimant was not refused; failures were {failures}"
    assert f"record '{_M720_RECORD}'" in refusals[0]
    assert "modelo-720-asset-row-class" in refusals[0]
    assert "modelo-720-asset-row-class-planted-duplicate" in refusals[0]
    assert all(f"modelo 720 revision {_M720_REVISION}" in failure for failure in failures)
