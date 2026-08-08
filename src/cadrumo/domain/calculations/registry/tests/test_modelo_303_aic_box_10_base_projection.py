"""Modelo 303 official box 10 was a bare manual field with no derivation.

Box 10 ("Adquisiciones intracomunitarias de bienes y servicios - Base
imponible") is the base-imponible counterpart of box 11 (its cuota sibling),
which was already computed via a projection formula from the AIC devengado
parity casilla. Box 10 carried no binding, no formula, and no semantic
casilla at all -- a taxpayer's AIC base went undeclared on that box even when
the ledger held the rows, an asymmetry invisible to any test asserting only
box 11.

This module pins the fix: a base-imponible parity casilla
(``iva.autorepercutido.intracomunitaria.devengado.base``), a
``base_amount_sum`` binding mirroring the existing cuota binding's selector,
and a projection formula wiring box 10 to that casilla -- the same shape
Modelo 303 already uses for every other official box (Stage 2 projections).

Real-behaviour: real ledger observations through the production
``resolve_ledger_iva_aggregation_binding_values`` resolver, and the actual
on-disk TOML fragments through the raw compiler (``load_registry_tree``). No
mocks, stubs, skips or xfail. The mutation proof reverts box 10 to its
original bare-manual state on an isolated scratch copy (never the tracked
tree) and confirms the position assertion catches the reintroduced defect.
"""

from __future__ import annotations

import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....iva import IvaCategory, IvaFlowDirection, IvaRateKind
from .. import IvaLedgerObservation, resolve_ledger_iva_aggregation_binding_values
from .._loader import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2023-y-siguientes"
_CASILLA_BASE = "iva.autorepercutido.intracomunitaria.devengado.base"
_BINDING_BASE = "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base"
_FORMULA_BOX_10 = "modelo-303-dr303-10-projection"


def _m303_revision(root: Path):
    modelos, _catalogues = load_registry_tree(root)
    m303 = next(m for m in modelos if m.id == "303")
    return m303.revisions[_REVISION_ID]


def _bundled_registry_root() -> Path:
    return Path(__file__).resolve().parents[4] / "_data" / "registry" / "aeat"


def test_box_10_is_computed_from_the_base_parity_casilla() -> None:
    revision = _m303_revision(_bundled_registry_root())
    casillas = {c.id: c for c in revision.casillas}

    box_10 = casillas["10"]
    box_11 = casillas["11"]

    assert box_10.input_kind == "computed", "box 10 is still a bare manual field"
    assert box_10.formula == _FORMULA_BOX_10
    assert box_11.input_kind == "computed", "box 11's own shape must stay the reference"

    formulas = {f.id: f for f in revision.formulas}
    formula = formulas[_FORMULA_BOX_10]
    assert formula.expression.casilla_id == _CASILLA_BASE

    assert _CASILLA_BASE in casillas
    assert casillas[_CASILLA_BASE].binding == _BINDING_BASE


def test_aic_row_feeds_box_10_base_and_box_11_cuota_from_the_same_row() -> None:
    """Real-behaviour proof: one AIC row resolves both the base and the cuota.

    A resolver that dropped the base fact, resolved the wrong category, or
    mixed up base/cuota would fail this on value, not merely on wiring.
    """
    revision = _m303_revision(_bundled_registry_root())

    aic_row = IvaLedgerObservation(
        ledger_id="aic-goods-1",
        transaction_date=date(2025, 5, 10),
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        rate_kind=IvaRateKind.GENERAL,
        applied_rate=Decimal("0.21"),
        flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        base_amount=Decimal("2500.00"),
        iva_amount=Decimal("525.00"),
    )

    resolved = dict(resolve_ledger_iva_aggregation_binding_values(revision, (aic_row,)))

    assert resolved[_BINDING_BASE] == Decimal("2500.00")
    assert resolved["modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota"] == Decimal("525.00")


def test_mutation_reverting_box_10_to_manual_reds_the_gate(tmp_path: Path) -> None:
    """Re-introduce the exact original defect on an isolated scratch copy of
    the registry tree (never the tracked file) and confirm the position test
    above would have caught it.
    """
    bundled_root = _bundled_registry_root()
    scratch_root = tmp_path / "registry-mutant" / "aeat"
    (scratch_root / "modelos").mkdir(parents=True)
    shutil.copytree(bundled_root / "modelos" / "303", scratch_root / "modelos" / "303")
    for catalogue_dir in (
        "apoderamientos",
        "authorization.d",
        "calendars",
        "categories",
        "iva",
        "legal",
        "topics",
        "treaties",
    ):
        source = bundled_root / catalogue_dir
        if source.is_dir():
            shutil.copytree(source, scratch_root / catalogue_dir)
        elif source.exists():
            shutil.copy2(source, scratch_root / catalogue_dir)

    casillas_path = (
        scratch_root
        / "modelos"
        / "303"
        / "revisions"
        / _REVISION_ID
        / "casillas"
        / "civa.repercutido.general__c21.toml"
    )
    original = casillas_path.read_text(encoding="utf-8")
    mutated = original.replace(
        'input_kind = "computed"\nformula = "modelo-303-dr303-10-projection"',
        'input_kind = "manual"',
        1,
    )
    assert mutated != original, "the mutation target string was not found -- test is stale"
    casillas_path.write_text(mutated, encoding="utf-8")

    mutated_revision = _m303_revision(scratch_root)
    mutated_box_10 = {c.id: c for c in mutated_revision.casillas}["10"]

    assert mutated_box_10.input_kind != "computed"
    assert mutated_box_10.input_kind == "manual"
