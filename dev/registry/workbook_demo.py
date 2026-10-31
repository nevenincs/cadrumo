"""Generate explicitly fictional form demonstrations from current registry source.

Run ``python -m dev.registry.workbook_demo --output-directory PATH``. This is
development tooling: it neither publishes authority nor reads a taxpayer profile.
The shared compiler and materializers own all layout, formulas and formatting.
"""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path

from cadrumo.adapters.outbound.workbook.calc_sheets_xlsx import materialize_export_plan
from cadrumo.application.filing.producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    GeneralFilingProfileFacts,
    Modelo111ProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from cadrumo.application.storage.calc_sheets.engine import build_export_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_form_workbook
from cadrumo.application.storage.calc_sheets.human_layout import guide_paragraph_height
from cadrumo.application.storage.calc_sheets.layout import plan_layout
from cadrumo.application.storage.calc_sheets.records import (
    OperatorInputs,
    SheetCellAddress,
    SheetExportPlan,
    SheetGuideContent,
    SheetValueCell,
    TabName,
)
from cadrumo.application.storage.calc_sheets.theme import StyleRole
from cadrumo.core.config import override_settings
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.period import calculation_filing_date

from .compiler.authority import compiled_bundled_authority
from .workbook_demo_cases import DEMO_CASES, DemoCase
from .workbook_demo_inputs import demonstration_inputs
from .workbook_demo_intracommunity import intracommunity_records
from .workbook_demo_m303 import m303_demonstration_facts
from .workbook_demo_members import contribution_member_records
from .workbook_demo_notice import demonstration_notice
from .workbook_demo_records import (
    annual_capital_records,
    annual_employment_records,
    annual_rent_records,
    financial_asset_records,
    member_attribution_records,
)
from .workbook_demo_third_parties import third_party_records


def demonstration_snapshot(case: DemoCase) -> RegistrySnapshot:
    """Validate mutable development source in memory, without installing it."""
    return compiled_bundled_authority().snapshot(
        case.modelo,
        filing_year=case.filing_year,
        period=case.period,
        revision_id=case.revision,
        grade=case.authority_grade,
    )


def demonstration_records(snapshot: RegistrySnapshot) -> CalculationRevision | None:
    """Two fictional saved detail rows exercise the existing record replay path."""
    if snapshot.modelo.id == "347":
        return third_party_records(snapshot)
    if snapshot.modelo.id == "156":
        return contribution_member_records(snapshot)
    if snapshot.modelo.id == "194":
        return financial_asset_records(snapshot)
    if snapshot.modelo.id == "193":
        return annual_capital_records(snapshot)
    if snapshot.modelo.id == "190":
        return annual_employment_records(snapshot)
    if snapshot.modelo.id == "180":
        return annual_rent_records(snapshot)
    if snapshot.modelo.id == "184":
        return member_attribution_records(snapshot)
    if snapshot.modelo.id == "349":
        return intracommunity_records(snapshot)
    return None


def demonstration_producer(case: DemoCase) -> FilingProducerSnapshot | None:
    """Supply fictional typed filing facts, without reading a taxpayer profile."""
    if case.modelo not in {
        "111",
        "115",
        "117",
        "122",
        "123",
        "126",
        "128",
        "130",
        "131",
        "180",
        "184",
        "190",
        "193",
        "194",
        "156",
        "216",
        "347",
        "349",
        "308",
        "309",
        "322",
    }:
        return None
    entity_name = {
        "322": "Entidad ficticia del grupo Ejemplo",
        "184": "Comunidad ficticia Ejemplo",
        "190": "Empresa ficticia Ejemplo",
        "193": "Empresa ficticia Ejemplo",
        "194": "Entidad financiera ficticia Ejemplo",
        "156": "Mutualidad ficticia Ejemplo",
        "347": "Empresa ficticia Ejemplo",
        "349": "Empresa ficticia Ejemplo",
    }.get(case.modelo)
    return build_filing_producer_snapshot(
        modelo=Modelo(case.modelo),
        taxpayer_tax_id={
            "322": "B12345674",
            "156": "B12345674",
            "184": "E00000000",
            "190": "B12345674",
            "193": "B12345674",
            "194": "B12345674",
            "347": "B12345674",
            "349": "B12345674",
        }.get(case.modelo, "12345678Z"),
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=entity_name,
            given_name=None if (entity_name is not None and entity_name) else "Ana",
            surnames=None if (entity_name is not None and entity_name) else "Ejemplo",
            full_name=entity_name or "Ana Ejemplo",
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Presentador ficticio"),
        model_profile=Modelo111ProfileFacts(colegio_concertado=False)
        if case.modelo == "111"
        else GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.INGRESO,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


def _build_form_plan(
    snapshot: RegistrySnapshot, case: DemoCase, inputs: OperatorInputs, bindings: dict[str, Decimal]
) -> SheetExportPlan:
    """Build the form with fictional inputs inside the governed registry scope."""
    with (
        override_settings(cadrumo_output_language="es"),
        validating_governed_facts(compiled_bundled_authority()),
    ):
        plan = build_export_plan(snapshot, operator_inputs=inputs)
        anchor = (
            calculation_filing_date(snapshot.filing_period)
            if snapshot.filing_period
            else date(case.filing_year, 12, 31)
        )
        layout = plan_layout(snapshot.revision, bracket_filter_date=anchor)
        by_address: dict[SheetCellAddress, Decimal | str] = {
            (layout.binding_cells[key] if key in layout.binding_cells else layout.relation_cells[key]): value
            for key, value in bindings.items()
        }
        if case.modelo == "131":
            activity_values: dict[str, Decimal | str] = {
                "epigrafe": "659.4",
                "rendimiento-neto": Decimal("20000"),
                "porcentaje": Decimal("2"),
                "resultado": Decimal("400"),
            }
            by_address.update(
                {
                    layout.binding_cells[f"modelo-131.page1.actividad-1-{key}"]: value
                    for key, value in activity_values.items()
                }
            )
        cells = tuple(
            cell.model_copy(update={"value": by_address[cell.address]}) if cell.address in by_address else cell
            for cell in plan.value_cells
        )
        plan = SheetExportPlan.model_validate({**dict(plan), "value_cells": cells})
        saved, producer = (
            m303_demonstration_facts(snapshot)
            if case.modelo == "303"
            else (demonstration_records(snapshot), demonstration_producer(case))
        )
        plan = add_form_workbook(
            plan,
            snapshot,
            revision=saved,
            producer_snapshot=producer,
        )
    return plan


def _mark_form_titles(plan: SheetExportPlan) -> tuple[SheetValueCell, ...]:
    """Identify the workbook as a fictional demonstration."""
    title_regions = {(s.tab, s.start_row, s.start_column) for s in plan.styled_ranges if s.role == StyleRole.TITLE}
    return tuple(
        cell.model_copy(update={"value": f"{cell.value} · EJEMPLO FICTICIO"})
        if cell.address.tab == TabName.FORM
        and (cell.address.tab, cell.address.row, cell.address.column) in title_regions
        else cell
        for cell in plan.value_cells
    )


def _annotate_demonstration(plan: SheetExportPlan, case: DemoCase) -> SheetExportPlan:
    """Mark fictional titles and install the scenario disclosure."""
    cells = _mark_form_titles(plan)
    notice = demonstration_notice(case)
    cells = tuple(
        cell.model_copy(update={"value": notice})
        if cell.address.tab is TabName.GUIDE and cell.address.row == 3
        else cell
        for cell in cells
    )
    guide = SheetGuideContent(
        title=f"Modelo {case.modelo} · Ejemplo ficticio · {case.period} {case.filing_year}",
        paragraphs=(
            notice,
            "Edite las entradas azules de la hoja Entradas para explorar este escenario independiente.",
        ),
    )
    heights = tuple(
        height.model_copy(update={"height_pixels": guide_paragraph_height(notice)})
        if height.tab is TabName.GUIDE and height.row == 3
        else height
        for height in plan.row_heights
    )
    return SheetExportPlan.model_validate({**dict(plan), "value_cells": cells, "guide": guide, "row_heights": heights})


def build_demonstration_plan(case: DemoCase) -> tuple[RegistrySnapshot, SheetExportPlan]:
    """Use the same typed form compiler for each modelo and preserve its formulas."""
    snapshot = demonstration_snapshot(case)
    with validating_governed_facts(compiled_bundled_authority()):
        inputs, bindings = demonstration_inputs(snapshot, case)
    plan = _build_form_plan(snapshot, case, inputs, bindings)
    return snapshot, _annotate_demonstration(plan, case)


def main() -> None:
    """Write XLSX and diagnostic JSON to an explicit destination.

    JSON is an inspection artifact, not a lossless plan reload contract:
    numeric-looking strings and serialized Decimals share its string shape.
    Materializers consume the original typed plan.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output_directory.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for case in DEMO_CASES:
        _, plan = build_demonstration_plan(case)
        stem = f"modelo-{case.modelo}-{case.filing_year}-{case.period}-ejemplo"
        json_path = destination / f"{stem}.json"
        xlsx_path = destination / f"{stem}.xlsx"
        if json_path.exists() or xlsx_path.exists():
            raise FileExistsError(f"Refusing to replace a prior demonstration: {stem}")
        json_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        xlsx_path.write_bytes(materialize_export_plan(plan))
        print(xlsx_path)


if __name__ == "__main__":
    main()
