"""A lineage claim has exactly one authored owner: the row or the attestation sidecar."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_MODELO = "038"
_PREDECESSOR = "2024-desde-06"
_SUCCESSOR = "2025-y-siguientes"
_ATTESTED_CONTINUIDAD = "filing-year"

_RESTATED_ROW_WITH_ITS_OWN_CLAIM = f"""[[revisions."{_SUCCESSOR}".casillas]]
id = "decl.ejercicio"
continuidad_id = "{_ATTESTED_CONTINUIDAD}"
continuidad_origin = "seeded"
number = "ejercicio"
section = ["declarante"]
data_type = "year"
semantic_role = "filing_year"
required = true
input_kind = "informational"
legal_refs = ["orden-hac-66-2002:art-1", "ley-58-2003:art-93"]
"""


def _modelo_copy(tmp_path: Path) -> Path:
    return shutil.copytree(bundled_path("registry", "aeat", "modelos", _MODELO), tmp_path / _MODELO)


def test_an_attested_inherited_row_exposes_the_sidecar_claim(tmp_path: Path) -> None:
    successor = load_modelo_directory(_modelo_copy(tmp_path)).revisions[_SUCCESSOR]

    row = next(casilla for casilla in successor.casillas if str(casilla.continuidad_id) == _ATTESTED_CONTINUIDAD)
    attestation = next(
        item for item in successor.lineage_attestations if str(item.continuidad_id) == _ATTESTED_CONTINUIDAD
    )

    assert attestation.from_revision == _PREDECESSOR
    assert row.continuidad_origin == attestation.origin


def test_a_row_restating_an_attested_claim_is_refused_as_duplicate_ownership(tmp_path: Path) -> None:
    modelo_root = _modelo_copy(tmp_path)
    casillas = modelo_root / "revisions" / _SUCCESSOR / "casillas"
    casillas.mkdir()
    (casillas / "0001-declarations.toml").write_text(_RESTATED_ROW_WITH_ITS_OWN_CLAIM, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="duplicates lineage evidence ownership"):
        load_modelo_directory(modelo_root)
