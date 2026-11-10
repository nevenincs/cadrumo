"""Detector teeth for the binding-order refusals.

Binding declaration order is a merge artefact of the fragment filenames, so a
consumer that reads the binding tuple positionally or takes a first match is
only safe while the declaration it reads is unique. Two such duplicates are
refused at load:

* a second ``prorrata_regularizacion`` binding, because the annual
  regularisation reads its four source roles positionally out of the
  concatenated source casillas of every prorrata binding;
* a second ``bienes_inversion_regularizacion`` binding for one output, because
  the consumer keeps the last binding per output without saying so;
* two row bindings claiming one ``row_field`` of one record, because export
  field derivation keeps the first claimant and silently drops the rest.

A third refusal guards the second: a row binding whose ``record`` or
``row_field`` is present but not a string is unreadable to the uniqueness check
and is refused rather than skipped, so the check cannot be emptied silently.

Each refusal is provoked from a COPY of a live modelo in a temporary tree,
mirroring ``test_validate_bindings``: the bundled corpus is never written, no
production module is patched, and the clean path is asserted in the same suite
as the defect. A fixture that stopped refusing its own planted duplicate would
also have stopped refusing a real one.
"""

from __future__ import annotations

import shutil
import warnings
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_aggregation import binding_aggregation_op
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_bindings import validate_binding_registration_section
from .authored_edition_support import authored_revisions

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_MODELOS_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

_M303_WHOLE_YEAR = [
    revision
    for revision in authored_revisions("303")
    if revision.valid_to is not None
    and (revision.valid_from.month, revision.valid_from.day) == (1, 1)
    and (revision.valid_to.month, revision.valid_to.day) == (12, 31)
][-1]
_M303_REVISION = str(_M303_WHOLE_YEAR.id)
_M303_DESIGN = next(str(ref) for ref in _M303_WHOLE_YEAR.source_refs if str(ref).startswith("aeat-dr-303-"))
_M303_PRORRATA_ID = "modelo-303-prorrata-regularizacion-casilla-44"
_M303_PRORRATA_BLOCK = f'''
[[revisions.{_M303_REVISION}.bindings]]
id = "{_M303_PRORRATA_ID}-planted-duplicate"
provider = {{ kind = "prorrata_regularizacion", source_modelo = "303", source_casilla_ids = \
["iva.prorrata-volumen-con-derecho", "iva.prorrata-volumen-total", \
"iva.prorrata-porcentaje"], source_period_selection = "filer_liquidation_cadence", \
regularizacion_output = "modelo_303_casilla_44" }}
value = {{ data_type = "money", channel = "decimal" }}
legal_refs = ["ley-37-1992:art-104", "ley-37-1992:art-105", "rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"]
source_refs = ["{_M303_DESIGN}", "aeat-modelo-303-procedure", "boe-modelo-303-2008-form"]

[[revisions.{_M303_REVISION}.bindings.source_citations]]
source_ref = "aeat-modelo-303-procedure"
required_text = ["modelo 303"]
'''

_M303_BIENES_ID = "modelo-303-bienes-inversion-regularizacion-casilla-43"
_M303_BIENES_DUPLICATE_ID = f"{_M303_BIENES_ID}-planted-duplicate"


def _bienes_block(*, binding_id: str, output: str) -> str:
    return f'''
[[revisions.{_M303_REVISION}.bindings]]
id = "{binding_id}"
provider = {{ kind = "bienes_inversion_regularizacion", source_modelo = "303", regularizacion_output = "{output}" }}
value = {{ data_type = "money", channel = "decimal" }}
legal_refs = ["ley-37-1992:art-107", "ley-37-1992:art-108", "rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"]
source_refs = ["{_M303_DESIGN}", "aeat-modelo-303-procedure", "boe-modelo-303-2008-form"]

[[revisions.{_M303_REVISION}.bindings.source_citations]]
source_ref = "aeat-modelo-303-procedure"
required_text = ["modelo 303"]
'''


_M720_REVISION = str(open_ended_revision("720").id)
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


def _plant_binding(tree: Path, revision_id: str, block: str) -> None:
    """Plant one binding declaration in the copied revision's ``bindings`` family.

    The fragment filenames are the authoring tree's own, and an edition that
    inherits its bindings states no fragment at all, so the target is resolved
    from the copy rather than named here: a renamed fragment or a revision that
    becomes delta-authored would otherwise silently stop planting anything and
    leave the refusal proven by nothing.
    """
    directory = tree / "revisions" / revision_id / "bindings"
    fragments = sorted(directory.glob("*.toml")) if directory.is_dir() else []
    if fragments:
        target = fragments[-1]
        target.write_text(target.read_text(encoding="utf-8").rstrip("\n") + "\n" + block, encoding="utf-8")
        return
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "0001-bindings.toml").write_text(block.lstrip("\n"), encoding="utf-8")


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
    _plant_binding(tree, _M303_REVISION, _M303_PRORRATA_BLOCK)

    failures = _failures(tree, _M303_REVISION)

    refusals = [f for f in failures if "prorrata_regularizacion bindings are declared" in f]
    assert refusals, f"a second prorrata_regularizacion binding was not refused; failures were {failures}"
    assert _M303_PRORRATA_ID in refusals[0]
    assert f"{_M303_PRORRATA_ID}-planted-duplicate" in refusals[0]
    assert all(f"modelo 303 revision {_M303_REVISION}" in failure for failure in failures)


def test_a_second_bienes_regularizacion_binding_for_one_output_is_refused(tmp_path: Path) -> None:
    """Two bindings for one output leave the surviving one to binding merge order."""
    tree = _copy_modelo(tmp_path, "303")
    _plant_binding(
        tree,
        _M303_REVISION,
        _bienes_block(binding_id=_M303_BIENES_DUPLICATE_ID, output="modelo_303_casilla_43"),
    )

    failures = _failures(tree, _M303_REVISION)

    refusals = [f for f in failures if "bienes_inversion_regularizacion bindings" in f]
    assert len(refusals) == 1, f"a duplicate bienes output was not refused exactly once; failures were {failures}"
    assert _M303_BIENES_ID in refusals[0]
    assert _M303_BIENES_DUPLICATE_ID in refusals[0]
    assert "modelo_303_casilla_43" in refusals[0]


def test_a_bienes_regularizacion_binding_for_a_distinct_output_is_not_a_duplicate(tmp_path: Path) -> None:
    """The control: a different output is a different declaration, not an ambiguity."""
    tree = _copy_modelo(tmp_path, "303")
    _plant_binding(
        tree,
        _M303_REVISION,
        _bienes_block(binding_id=_M303_BIENES_DUPLICATE_ID, output="modelo_390_casilla_63"),
    )

    failures = _failures(tree, _M303_REVISION)

    assert [f for f in failures if "bienes_inversion_regularizacion bindings" in f] == []


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
    _plant_binding(tree, _M720_REVISION, _M720_ROW_BLOCK)

    failures = _failures(tree, _M720_REVISION)

    refusals = [f for f in failures if f"row field '{_M720_ROW_FIELD}'" in f]
    assert refusals, f"a duplicate row_field claimant was not refused; failures were {failures}"
    assert f"record '{_M720_RECORD}'" in refusals[0]
    assert "modelo-720-asset-row-class" in refusals[0]
    assert "modelo-720-asset-row-class-planted-duplicate" in refusals[0]
    assert all(f"modelo 720 revision {_M720_REVISION}" in failure for failure in failures)


class _RowFieldToken(Enum):
    """A non-string ``row_field``, standing in for a later selector schema change."""

    ASSET_CLASS_CODE = "asset_class_code"


def test_a_rows_binding_whose_row_field_is_not_a_string_is_refused(tmp_path: Path) -> None:
    """An unreadable row selector is a finding, never a quiet exemption.

    The uniqueness check reads ``record`` and ``row_field`` off the declared
    selector. Every family types both as a string today, so the defect is
    planted by re-typing one axis of a LIVE binding the way a selector schema
    change would: the provider is the real model, the revision is the real
    compiled Modelo 720, and only the one field is replaced. Skipping such a
    binding instead of refusing it would empty the check corpus-wide the first
    time a family adopts an enum, and the refusal would pass vacuously.
    """
    revision = _revision(_copy_modelo(tmp_path, "720"), _M720_REVISION)
    original = next(
        binding
        for binding in revision.bindings
        if binding_aggregation_op(binding) is BindingAggregationOp.ROWS
        and getattr(binding.provider, "row_field", None) == _M720_ROW_FIELD
    )
    retyped = original.model_copy(
        update={"provider": original.provider.model_copy(update={"row_field": _RowFieldToken.ASSET_CLASS_CODE})},
    )
    defective = revision.model_copy(
        update={"bindings": tuple(retyped if b.id == original.id else b for b in revision.bindings)},
    )

    with warnings.catch_warnings():
        # Dumping the re-typed field is exactly the mismatch being planted, and
        # pydantic says so on the way past; the assertion is about the refusal.
        warnings.simplefilter("ignore")
        failures = validate_binding_registration_section(
            prefix=f"modelo 720 revision {_M720_REVISION}",
            revision=defective,
        )

    refusals = [f for f in failures if "cannot read" in f]
    assert refusals, f"an unreadable row export selector was not refused; failures were {failures}"
    assert original.id in refusals[0]
    assert "row_field=" in refusals[0]
