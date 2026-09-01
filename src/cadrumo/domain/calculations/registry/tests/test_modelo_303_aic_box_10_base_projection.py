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

from .....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....iva.deduction_facts import IvaDeductionClassificationProvenance
from ....iva.flow import IvaFlowDirection
from ....iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ..ledger_iva_bindings import (
    IvaLedgerObservation,
    iva_ledger_selector,
    resolve_ledger_iva_aggregation_binding_values,
)
from ..loader import load_registry_tree
from ._gate_support import fragment_declaring

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2025"
_CASILLA_BASE = "iva.autorepercutido.intracomunitaria.devengado.base"
_BINDING_BASE = "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base"
_FORMULA_BOX_10 = "modelo-303-dr303-10-projection"
_AIC_BINDING_IDS = (
    "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota",
    _BINDING_BASE,
    "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota",
)


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
        deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT,
            source_locator="test-ledger:aic-goods-1",
            evidence_digest="a" * 64,
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    resolved = dict(resolve_ledger_iva_aggregation_binding_values(revision, (aic_row,)))

    assert resolved[_BINDING_BASE] == Decimal("2500.00")
    assert resolved["modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota"] == Decimal("525.00")


def test_zero_rate_aic_row_reaches_box_10_base_and_every_aic_binding_admits_it() -> None:
    """A zero-rate acquisition still declares its official AIC base.

    The official box records the acquisition's base even when its cuota is
    zero.  The base is intentionally distinct from zero so this proves the
    live resolver selected the AIC row rather than merely observing the cuota.
    """
    revision = _m303_revision(_bundled_registry_root())
    aic_row = IvaLedgerObservation(
        ledger_id="aic-goods-zero",
        transaction_date=date(2025, 5, 10),
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        rate_kind=IvaRateKind.ZERO,
        applied_rate=Decimal("0.00"),
        flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        base_amount=Decimal("1739.25"),
        iva_amount=Decimal("0.00"),
        deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT,
            source_locator="test-ledger:aic-goods-zero",
            evidence_digest="a" * 64,
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    resolved = dict(resolve_ledger_iva_aggregation_binding_values(revision, (aic_row,)))

    assert resolved[_BINDING_BASE] == Decimal("1739.25")
    bindings = {binding.id: binding for binding in revision.bindings}
    for binding_id in _AIC_BINDING_IDS:
        assert IvaRateKind.ZERO in iva_ledger_selector(bindings[binding_id]).rate_kinds


def test_mutation_removing_zero_from_aic_base_selector_reds_the_zero_rate_gate(tmp_path: Path) -> None:
    """Removing zero on a scratch registry makes the real base assertion fail."""
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

    bindings_path = fragment_declaring(
        scratch_root / "modelos" / "303" / "revisions" / _REVISION_ID / "bindings",
        f'id = "{_BINDING_BASE}"',
    )
    original = bindings_path.read_text(encoding="utf-8")
    mutated = original.replace(
        "\n".join(
            (
                'categories = ["intra_community_acquisition_reverse_charge", "intra_community_service_acquisition_reverse_charge"]',
                'rate_kinds = ["zero", "general", "reduced", "super_reduced"]',
                'flow_direction = "inversion_sujeto_pasivo"',
                'fact = "base_amount_sum"',
            )
        ),
        "\n".join(
            (
                'categories = ["intra_community_acquisition_reverse_charge", "intra_community_service_acquisition_reverse_charge"]',
                'rate_kinds = ["general", "reduced", "super_reduced"]',
                'flow_direction = "inversion_sujeto_pasivo"',
                'fact = "base_amount_sum"',
            )
        ),
        1,
    )
    assert mutated != original, "the mutation target string was not found -- test is stale"
    bindings_path.write_text(mutated, encoding="utf-8")

    aic_row = IvaLedgerObservation(
        ledger_id="aic-goods-zero-mutant",
        transaction_date=date(2025, 5, 10),
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        rate_kind=IvaRateKind.ZERO,
        applied_rate=Decimal("0.00"),
        flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        base_amount=Decimal("1739.25"),
        iva_amount=Decimal("0.00"),
        deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT,
            source_locator="test-ledger:aic-goods-zero-mutant",
            evidence_digest="a" * 64,
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )
    mutated_resolved = dict(resolve_ledger_iva_aggregation_binding_values(_m303_revision(scratch_root), (aic_row,)))

    assert mutated_resolved[_BINDING_BASE] != Decimal("1739.25")


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
