"""Detector teeth for the annual compensation-partition revision refusal.

Each half of the annual IVA compensation partition may be targeted by at most one
binding, or the half the resolver reads depends on binding fragment merge order.
That is a sibling invariant no per-binding validator can see, so it is owned by
the revision-level validator the compiler calls beside the per-binding gate.

The defect is planted in a COPY of the live Modelo 390 in a temporary tree, and
the clean path is asserted in the same suite: a fixture that stopped refusing its
own planted duplicate would also have stopped refusing a real one.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cadrumo.domain.calculations.registry.bindings import validate_iva_compensation_annual_partition_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions

from ..compiler.loader import load_modelo_directory

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_MODELOS_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"

_M390_REVISION = str(authored_revisions("390")[-1].id)
_PLANTED_ID = "modelo-390-prev-303-compensacion-planted-duplicate"


def _partition_block(partition_output: str) -> str:
    return f'''
[[revisions.{_M390_REVISION}.bindings]]
id = "{_PLANTED_ID}"
provider = {{ kind = "iva_compensation_annual_partition", source_modelo = "303", source_casilla_ids = \
["iva.compensacion-generada-periodo", "iva.compensacion-aplicada-periodo", \
"iva.compensacion-disponible-fin-periodo", "iva.compensacion-pendiente-periodos-posteriores"], \
source_periods = ["1T", "2T", "3T", "4T"], partition_output = "{partition_output}" }}
value = {{ data_type = "money", channel = "decimal" }}
legal_refs = ["ley-37-1992:art-99", "ley-37-1992:art-115", "rd-1624-1992:art-71", "orden-eha-3111-2009:art-1"]
source_refs = ["aeat-modelo-390-procedure", "boe-modelo-390-2009-form"]

[[revisions.{_M390_REVISION}.bindings.source_citations]]
source_ref = "aeat-modelo-390-procedure"
required_text = ["modelo 390"]
'''


def _copy_modelo(tmp_path: Path) -> Path:
    destination = tmp_path / "390"
    shutil.copytree(_MODELOS_ROOT / "390", destination)
    return destination


def _plant_binding(tree: Path, block: str) -> None:
    """Plant one binding in the copied revision's ``bindings`` family, resolved from the copy."""
    directory = tree / "revisions" / _M390_REVISION / "bindings"
    fragments = sorted(directory.glob("*.toml")) if directory.is_dir() else []
    if fragments:
        target = fragments[-1]
        target.write_text(target.read_text(encoding="utf-8").rstrip("\n") + "\n" + block, encoding="utf-8")
        return
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "0001-bindings.toml").write_text(block.lstrip("\n"), encoding="utf-8")


def _revision(tree: Path) -> ModeloRevision:
    return load_modelo_directory(tree).revisions[_M390_REVISION]


def test_the_live_modelo_390_partition_family_passes(tmp_path: Path) -> None:
    assert validate_iva_compensation_annual_partition_revision(_revision(_copy_modelo(tmp_path))) == []


@pytest.mark.parametrize(
    "output",
    ["last_period_amount", "generated_not_in_last_amount", "prior_year_applied_amount"],
)
def test_a_second_binding_for_one_partition_output_is_refused(tmp_path: Path, output: str) -> None:
    """The live revision declares every half once, so any planted binding duplicates one."""
    tree = _copy_modelo(tmp_path)
    _plant_binding(tree, _partition_block(output))

    failures = validate_iva_compensation_annual_partition_revision(_revision(tree))

    assert failures == [f"iva_compensation_annual_partition declares multiple {output} bindings"]
