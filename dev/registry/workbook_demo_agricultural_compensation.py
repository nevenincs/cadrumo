"""Fictional Modelo 341 examples through the shared registry form compiler."""

from decimal import Decimal

from cadrumo.application.filing.producer_snapshot import (
    FilingElectionFacts,
    GeneralFilingProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from cadrumo.application.storage.calc_sheets.engine import build_template_preview_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_template_preview_form
from cadrumo.application.storage.calc_sheets.records import (
    OperatorInput,
    OperatorInputs,
    SheetExportPlan,
    SheetGuideContent,
    SheetTemplatePreviewMetadata,
)
from cadrumo.application.storage.calc_sheets.template_source import WorkbookTemplateSource
from cadrumo.core.config import override_settings
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.refund_election import RefundElection
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.temporal import select_revision

from .compiler.authority import compiled_bundled_authority
from .workbook_template_source import load_workbook_template_source


def build_agricultural_compensation_plan(
    *, year: int, period: str = "1T"
) -> tuple[WorkbookTemplateSource, SheetExportPlan[SheetTemplatePreviewMetadata]]:
    """Populate explicit example inputs without copying formulas or cell positions."""
    authority = compiled_bundled_authority()
    revision = select_revision(authority.modelo("341"), filing_year=year, period=period)
    source = load_workbook_template_source(
        "341",
        revision_id=revision.id,
        source_ref="boe-modelo-341-2000-form-pdf",
        preview_year=year,
        preview_period=period,
    )
    values: dict[str, Decimal | str] = {
        "decl.ejercicio": Decimal(year),
        "decl.periodo": period,
        "01": Decimal("1500"),
        "02": Decimal("500"),
        "03": Decimal("0"),
        "04": Decimal("12"),
        "05": Decimal("10.5"),
        "06": Decimal("12"),
    }
    if any(item.id == "papel-nombre-completo" for item in revision.casillas):
        values.update(
            {
                "papel-nombre-completo": "Ana Ejemplo",
                "papel-domicilio-tipo-via": "Calle",
                "papel-domicilio-via": "Ejemplo ficticio",
                "papel-domicilio-numero": "10",
                "papel-domicilio-codigo-postal": "08001",
                "papel-domicilio-municipio": "Barcelona",
                "papel-domicilio-provincia": "Barcelona",
            }
        )
    with override_settings(cadrumo_output_language="es"), validating_governed_facts(authority):
        producer = build_filing_producer_snapshot(
            modelo=Modelo("341"),
            taxpayer_tax_id="12345678Z",
            taxpayer_identity=TaxpayerIdentityFacts(
                legal_name=None, given_name="Ana", surnames="Ejemplo", full_name="Ana Ejemplo"
            ),
            presenter=PresenterIdentity(tax_id="00000000T", full_name="Presentador ficticio"),
            model_profile=GeneralFilingProfileFacts(),
            elections=FilingElectionFacts(
                result_disposition=None,
                payment=PaymentElection.INGRESO,
                refund=RefundElection.DEVOLVER,
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
                title=f"Modelo 341 · {year} · {period} · Ejemplo ficticio",
                paragraphs=(
                    "Identidad, domicilio e importes ficticios. No es una declaración presentada.",
                    "Los porcentajes son entradas del ejemplo, no una recomendación fiscal.",
                    "Las compensaciones de las tres filas y su total se recalculan al cambiar las entradas.",
                    "El importe solicitado repite el total. Cuenta bancaria y firma quedan sin dato.",
                ),
            ),
        )
        plan = add_template_preview_form(plan, source, illustrative_producer=producer)
    return source, plan
