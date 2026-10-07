"""Fictional Modelo 353 data rendered by the registry's shared form compiler."""

from decimal import Decimal

from cadrumo.application.filing.producer_snapshot import (
    FilingElectionFacts,
    Modelo353ProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from cadrumo.application.storage.calc_sheets.engine import build_template_preview_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_template_preview_form
from cadrumo.application.storage.calc_sheets.layout import plan_layout
from cadrumo.application.storage.calc_sheets.records import (
    OperatorInput,
    OperatorInputs,
    SheetCellAddress,
    SheetExportPlan,
    SheetGuideContent,
    SheetTemplatePreviewMetadata,
)
from cadrumo.application.storage.calc_sheets.template_source import WorkbookTemplateSource
from cadrumo.core.config import override_settings
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.period import calculation_filing_date

from .compiler.authority import compiled_bundled_authority
from .workbook_template_source import load_workbook_template_source


def build_group_aggregate_plan(
    *, year: int, period: str
) -> tuple[WorkbookTemplateSource, SheetExportPlan[SheetTemplatePreviewMetadata]]:
    """Populate declared inputs; obtain every cell and calculation from the compiler."""
    authority = compiled_bundled_authority()
    revision = select_revision(authority.modelo("353"), filing_year=year, period=period)
    source = load_workbook_template_source(
        "353",
        revision_id=revision.id,
        source_ref=revision.form_layouts[0].design_sources[0].source_ref,
        preview_year=year,
        preview_period=period,
    )
    values: dict[str, Decimal | str] = {
        "decl.ejercicio": Decimal(year),
        "decl.periodo": period,
        "02": Decimal("500"),
        "08": Decimal("200"),
        "04": Decimal("0"),
    }
    if any(c.id == "10" for c in revision.casillas):
        values["10"] = Decimal("150")
    dominant = "modelo-353.page_01.entidad-dominante-entidad-dominante-"
    bindings: dict[str, Decimal | str] = {
        dominant + "n-i-f": "B12345674",
        dominant + "resultado": Decimal("1800"),
        dominant + "numero-de-justificante": "0000000000001",
        "modelo-353-prev-322-resultado-regimen-general": Decimal("2100"),
    }
    for index, tax_id, result, share in (
        (1, "B00000000", "400", "100"),
        (2, "B00000018", "-100", "75.25"),
    ):
        prefix = f"modelo-353.page_01.entidad-{index}-"
        bindings.update(
            {
                prefix + "entidades-dependientes-n-i-f": tax_id,
                prefix + "entidades-dependientes-resultado": Decimal(result),
                prefix + "ent-depndtes-de-participac-al-final-del": Decimal(share),
                prefix + "entidades-dependientes-numero-de-justifi": f"{index + 1:013d}",
            }
        )
    with override_settings(cadrumo_output_language="es"), validating_governed_facts(authority):
        producer = build_filing_producer_snapshot(
            modelo=Modelo("353"),
            taxpayer_tax_id="B12345674",
            taxpayer_identity=TaxpayerIdentityFacts(
                legal_name="Grupo ficticio Ejemplo", full_name="Grupo ficticio Ejemplo", given_name=None, surnames=None
            ),
            presenter=PresenterIdentity(tax_id="00000000T", full_name="Presentador ficticio"),
            model_profile=Modelo353ProfileFacts(
                numero_grupo="0000000001",
                regimen_especial_avanzado_elected="2",
                regimen_especial_inscrito_redeme="2",
                sin_actividad=None,
                grupo_normativa_foral=None,
            ),
            elections=FilingElectionFacts(
                result_disposition=ResultDisposition.INGRESO,
                payment=PaymentElection.INGRESO,
                refund=RefundElection.COMPENSAR,
                prior_domiciliation=PriorDomiciliationElection.KEEP,
            ),
            amendment_evidence=None,
            refund_account=None,
            charge_account=None,
            m303_filing_facts=None,
        )
        plan = build_template_preview_plan(
            source,
            operator_inputs=OperatorInputs(
                values=tuple(OperatorInput(casilla_id=key, value=value) for key, value in values.items())
            ),
            guide=SheetGuideContent(
                title=f"Modelo 353 · {year}-{period} · Ejemplo ficticio",
                paragraphs=(
                    "Datos y justificantes ficticios. No es una declaración presentada.",
                    "El total del grupo procede de las declaraciones individuales. En este ejemplo es 2.100 €.",
                    "Cambiar una fila de entidades no actualiza ese total: requiere incorporar sus declaraciones.",
                    "Las casillas de liquidación se recalculan. "
                    "Los importes de ingreso y devolución no se eligen automáticamente.",
                ),
            ),
        )
        layout = plan_layout(
            revision, bracket_filter_date=calculation_filing_date(Period.from_year_and_code(year, period))
        )
        addresses: dict[SheetCellAddress, Decimal | str] = {}
        for key, value in bindings.items():
            if key in layout.binding_cells:
                addresses[layout.binding_cells[key]] = value
                continue
            owners = [casilla for casilla in revision.casillas if casilla.binding == key]
            if not owners:
                raise ValueError("fictional binding has no declared workbook owner")
            for owner in owners:
                addresses[layout.entradas_cells[owner.id]] = value
        cells = tuple(
            cell.model_copy(update={"value": addresses[cell.address]}) if cell.address in addresses else cell
            for cell in plan.value_cells
        )
        plan = SheetExportPlan[SheetTemplatePreviewMetadata].model_validate({**dict(plan), "value_cells": cells})
        plan = add_template_preview_form(plan, source, illustrative_producer=producer)
    return source, plan
