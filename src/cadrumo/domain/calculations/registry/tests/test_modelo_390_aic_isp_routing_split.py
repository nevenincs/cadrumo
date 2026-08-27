"""Modelo 390 box [26]/[28] used to conflate two different LIVA hechos imponibles.

Before this module's fix, ALL adquisiciones intracomunitarias (AIC) money --
bienes and servicios, every rate -- was aggregated by the single rate-blind
``iva.anual.autorepercutido.intracomunitaria`` casilla and exported to page 02
offset 1492, the box the bundled Diseño de Registros itself labels "IVA
deveng. invers. sujeto pasivo - Cuota [28]" -- the DOMESTIC reverse-charge
line (LIVA art. 84.Uno.2), a different hecho imponible from AIC (LIVA art.
13/85). Modelo 303 already files the identical AIC ledger categories on its
own AIC-labelled boxes (11/13), so the two modelos disagreed about where the
same money goes.

This module pins the fix from the casilla and export-layout end: box [26]
("Adquis. intracomunit. bienes - Tipo 21% - Cuota") is now fed by a
rate-specific AIC casilla, box [28] is now fed by a genuine domestic-ISP
casilla, and the original rate-blind AIC casilla keeps aggregating everything
for the annual total but no longer carries an export reference at all.

Real-behaviour: this loads the actual on-disk TOML fragments through the raw
compiler (``load_registry_tree``), and separately resolves real ledger
observations through the production ``resolve_ledger_iva_aggregation_binding_
values`` resolver -- no mocks, stubs, skips or xfail. The mutation proof below
reverts the export-layout repointing on an isolated scratch copy (never the
tracked tree) and confirms the position assertions catch the reintroduced
defect.
"""

from __future__ import annotations

import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....core import IvaDeductionFactKind
from ....iva import IvaCategory, IvaFlowDirection, IvaLedgerObservationRole, IvaRateKind
from ..ledger_bindings import IvaLedgerObservation, iva_ledger_selector, resolve_ledger_iva_aggregation_binding_values
from ..loader import load_registry_tree
from ._gate_support import fragment_declaring
from ._ledger_iva_aggregation_support import _deduction_provenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The revision-span split replaced the open-ended `2010-y-siguientes` revision
#: with one revision per bundled diseno year, so this names the current one. The
#: constant also builds the scratch-tree paths the mutation gates below copy, so
#: it has to be a revision that exists on disk, not just one that resolves.
_REVISION_ID = "2025"
_CASILLA_BOX_26 = "iva.anual.aic.bienes.tipo-21.cuota"
_CASILLA_BOX_28 = "iva.anual.autorepercutido.interior.cuota"
_CASILLA_AIC_BLIND = "iva.anual.autorepercutido.intracomunitaria"
_AIC_ZERO_BASE_BINDING = "modelo-390-iva-aic-bienes-tipo-0-base"
_AIC_ZERO_CUOTA_BINDING = "modelo-390-iva-aic-bienes-tipo-0-cuota"


def _m390_revision(root: Path):
    modelos, _catalogues = load_registry_tree(root)
    m390 = next(m for m in modelos if m.id == "390")
    return m390.revisions[_REVISION_ID]


def _bundled_registry_root() -> Path:
    return Path(__file__).resolve().parents[4] / "_data" / "registry" / "aeat"


def _export_field(revision, *, record_id: str, offset: int):
    for layout in revision.export_layouts:
        for record in layout.records:
            if record.id != record_id:
                continue
            for field in record.fields:
                if getattr(field, "offset", None) == offset:
                    return field
    raise AssertionError(f"no field at {record_id}:{offset}")


def test_box_26_and_box_28_are_distinct_casillas_at_their_official_positions() -> None:
    revision = _m390_revision(_bundled_registry_root())
    casillas = {c.id: c for c in revision.casillas}

    box_26 = casillas[_CASILLA_BOX_26]
    box_28 = casillas[_CASILLA_BOX_28]
    blind = casillas[_CASILLA_AIC_BLIND]

    assert box_26.number == "26"
    assert box_28.number == "28"
    assert box_26.id != box_28.id

    field_26 = _export_field(revision, record_id="modelo-390-page-02", offset=1220)
    field_28 = _export_field(revision, record_id="modelo-390-page-02", offset=1492)

    assert field_26.casilla_id == _CASILLA_BOX_26
    assert field_28.casilla_id == _CASILLA_BOX_28

    # The rate-blind AIC total layer keeps aggregating (for the annual total)
    # but no longer owns any export position -- the two-layer shape the
    # rate-box design mandates.
    assert blind.export_refs == ()


def test_box_27_is_domestic_isp_base_not_aic() -> None:
    revision = _m390_revision(_bundled_registry_root())
    casillas = {c.id: c for c in revision.casillas}
    box_27 = casillas["iva.anual.autorepercutido.interior.base"]
    assert box_27.number == "27"

    field_27 = _export_field(revision, record_id="modelo-390-page-02", offset=1475)
    assert field_27.casilla_id == "iva.anual.autorepercutido.interior.base"


def test_aic_and_domestic_isp_ledger_rows_resolve_to_different_bindings() -> None:
    """Real-behaviour proof: an AIC row and a domestic-ISP row never merge.

    A row classified as ``intra_community_acquisition_reverse_charge`` at 21%
    must resolve into the AIC box-layer binding and NOT into the domestic ISP
    binding, and vice versa -- proving the split is real at the resolution
    layer, not merely a casilla-naming exercise.
    """
    revision = _m390_revision(_bundled_registry_root())

    aic_row = IvaLedgerObservation(
        ledger_id="aic-bienes-21",
        transaction_date=date(2025, 6, 15),
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        rate_kind=IvaRateKind.GENERAL,
        applied_rate=Decimal("0.21"),
        flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        base_amount=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        deduction_provenance=_deduction_provenance(
            IvaDeductionFactKind.INTRA_EU_CURRENT,
            source_locator="self-assessment:aic-bienes-21",
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )
    domestic_isp_row = IvaLedgerObservation(
        ledger_id="domestic-isp",
        transaction_date=date(2025, 6, 15),
        category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        base_amount=Decimal("500.00"),
        iva_amount=Decimal("105.00"),
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        deduction_provenance=_deduction_provenance(
            IvaDeductionFactKind.DOMESTIC_CURRENT,
            source_locator="invoice:domestic-isp",
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    resolved = dict(resolve_ledger_iva_aggregation_binding_values(revision, (aic_row, domestic_isp_row)))

    assert resolved["modelo-390-iva-aic-bienes-tipo-21-base"] == Decimal("1000.00")
    assert resolved["modelo-390-iva-aic-bienes-tipo-21-cuota"] == Decimal("210.00")
    assert resolved["modelo-390-iva-autorepercutido-interior-base"] == Decimal("500.00")
    assert resolved["modelo-390-iva-autorepercutido-interior-cuota"] == Decimal("105.00")

    # Neither binding leaks the other row's money.
    assert (
        resolved["modelo-390-iva-aic-bienes-tipo-21-base"] != resolved["modelo-390-iva-autorepercutido-interior-base"]
    )
    assert resolved["modelo-390-iva-autorepercutido-intracomunitaria-cuota"] == Decimal("210.00")


def test_zero_rate_aic_base_reaches_its_own_official_box_layer() -> None:
    """A zero-rate AIC base is still declared in the zero-rate AIC box."""
    revision = _m390_revision(_bundled_registry_root())
    aic_row = IvaLedgerObservation(
        ledger_id="aic-bienes-zero",
        transaction_date=date(2025, 6, 15),
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        rate_kind=IvaRateKind.ZERO,
        applied_rate=Decimal("0.00"),
        flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        base_amount=Decimal("1739.25"),
        iva_amount=Decimal("0.00"),
        deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        deduction_provenance=_deduction_provenance(
            IvaDeductionFactKind.INTRA_EU_CURRENT,
            source_locator="self-assessment:aic-bienes-zero",
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    resolved = dict(resolve_ledger_iva_aggregation_binding_values(revision, (aic_row,)))

    assert resolved[_AIC_ZERO_BASE_BINDING] == Decimal("1739.25")
    bindings = {binding.id: binding for binding in revision.bindings}
    assert IvaRateKind.ZERO in iva_ledger_selector(bindings[_AIC_ZERO_BASE_BINDING]).rate_kinds
    assert IvaRateKind.ZERO in iva_ledger_selector(bindings[_AIC_ZERO_CUOTA_BINDING]).rate_kinds


def test_mutation_removing_zero_from_m390_aic_base_selector_reds_the_gate(tmp_path: Path) -> None:
    """Removing zero on a scratch registry makes the AIC base assertion fail."""
    bundled_root = _bundled_registry_root()
    scratch_root = tmp_path / "registry-mutant" / "aeat"
    (scratch_root / "modelos").mkdir(parents=True)
    shutil.copytree(bundled_root / "modelos" / "390", scratch_root / "modelos" / "390")
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
        scratch_root / "modelos" / "390" / "revisions" / _REVISION_ID / "bindings",
        f'id = "{_AIC_ZERO_BASE_BINDING}"',
    )
    original = bindings_path.read_text(encoding="utf-8")
    mutated = original.replace(
        'rate_kinds = ["zero"], applied_rates = ["0.00"]',
        'rate_kinds = ["general"], applied_rates = ["0.00"]',
        1,
    )
    assert mutated != original, "the mutation target string was not found -- test is stale"
    bindings_path.write_text(mutated, encoding="utf-8")

    aic_row = IvaLedgerObservation(
        ledger_id="aic-bienes-zero-mutant",
        transaction_date=date(2025, 6, 15),
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        rate_kind=IvaRateKind.ZERO,
        applied_rate=Decimal("0.00"),
        flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        base_amount=Decimal("1739.25"),
        iva_amount=Decimal("0.00"),
        deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        deduction_provenance=_deduction_provenance(
            IvaDeductionFactKind.INTRA_EU_CURRENT,
            source_locator="self-assessment:aic-bienes-zero-mutant",
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )
    mutated_resolved = dict(resolve_ledger_iva_aggregation_binding_values(_m390_revision(scratch_root), (aic_row,)))

    assert mutated_resolved[_AIC_ZERO_BASE_BINDING] != Decimal("1739.25")


def test_mutation_repointing_box_28_to_the_aic_blind_casilla_reds_the_gate(tmp_path: Path) -> None:
    """Re-introduce the exact original defect on an isolated scratch copy of
    the registry tree (never the tracked file) and confirm the position test
    above would have caught it.
    """
    bundled_root = _bundled_registry_root()
    scratch_root = tmp_path / "registry-mutant" / "aeat"
    (scratch_root / "modelos").mkdir(parents=True)
    shutil.copytree(bundled_root / "modelos" / "390", scratch_root / "modelos" / "390")
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

    export_layout_path = fragment_declaring(
        scratch_root / "modelos" / "390" / "revisions" / _REVISION_ID / "export_layouts",
        'casilla_id = "iva.anual.autorepercutido.interior.cuota"',
    )
    original = export_layout_path.read_text(encoding="utf-8")
    mutated = original.replace(
        'casilla_id = "iva.anual.autorepercutido.interior.cuota"',
        'casilla_id = "iva.anual.autorepercutido.intracomunitaria"',
        1,
    )
    assert mutated != original, "the mutation target string was not found -- test is stale"
    export_layout_path.write_text(mutated, encoding="utf-8")

    mutated_revision = _m390_revision(scratch_root)
    mutated_field_28 = _export_field(mutated_revision, record_id="modelo-390-page-02", offset=1492)

    assert mutated_field_28.casilla_id != _CASILLA_BOX_28
    assert mutated_field_28.casilla_id == _CASILLA_AIC_BLIND
