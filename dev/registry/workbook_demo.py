"""Generate explicitly fictional form demonstrations from current registry source.

Run ``python -m dev.registry.workbook_demo --output-directory PATH``. This is
development tooling: it neither publishes authority nor reads a taxpayer profile.
The shared compiler and materializers own all layout, formulas and formatting.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime
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
from cadrumo.application.storage.calc_sheets.layout import plan_layout
from cadrumo.application.storage.calc_sheets.records import (
    OperatorInput,
    OperatorInputs,
    SheetCellAddress,
    SheetExportPlan,
    SheetGuideContent,
    TabName,
)
from cadrumo.application.storage.calc_sheets.theme import StyleRole
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.withholding_bindings import resolve_withholding_binding_values
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.row_models import Modelo349OperadorRow
from cadrumo.domain.period import calculation_filing_date

from .compiler.authority import compiled_bundled_authority
from .workbook_demo_members import contribution_member_records, contribution_members
from .workbook_demo_nonperiodic import nonperiodic_vat_inputs
from .workbook_demo_records import (
    annual_capital_records,
    annual_employment_records,
    annual_rent_records,
    financial_asset_observations,
    financial_asset_records,
    member_attribution_records,
)
from .workbook_demo_refunds import refund_inputs
from .workbook_demo_third_parties import third_party_records, third_party_summary


@dataclass(frozen=True)
class DemoCase:
    """A scenario coordinate; no form coordinates or copied fiscal formulas."""

    modelo: str
    revision: str
    result_casilla: str | None
    expected_result: Decimal | None
    filing_year: int = 2025
    authority_grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING
    period: str = "4T"


DEMO_CASES = (
    DemoCase("130", "2019-y-siguientes", "19", Decimal("6373")),
    DemoCase("303", "2025", "71", Decimal("1680")),
    DemoCase("349", "2020-y-siguientes", None, None),
    DemoCase("347", "2011-2024", None, None, filing_year=2024, period="0A"),
    DemoCase("347", "2025-y-siguientes", None, None, period="0A"),
    DemoCase("131", "2019-2023", "15", Decimal("580"), filing_year=2023),
    DemoCase("131", "2024", "15", Decimal("580"), filing_year=2024),
    DemoCase("131", "2025", "15", Decimal("580")),
    DemoCase("131", "2026", "15", Decimal("580"), filing_year=2026, period="2T"),
    DemoCase("131", "2026-3t-4t", "15", Decimal("580"), filing_year=2026),
    DemoCase("180", "2019-2022", "decl.retenciones-total", Decimal("3420"), filing_year=2022, period="0A"),
    DemoCase("180", "2023-y-siguientes", "decl.retenciones-total", Decimal("3420"), period="0A"),
    DemoCase("184", "2023-2024", None, None, filing_year=2024, period="0A"),
    DemoCase("184", "2025-y-siguientes", None, None, period="0A"),
    DemoCase("185", "2025-y-siguientes", None, None, filing_year=2026, period="03"),
    DemoCase("188", "2023-y-siguientes", None, None, period="0A", authority_grade=RegistryAuthorityGrade.APPLICABILITY),
    DemoCase(
        "189", "2022", None, None, filing_year=2022, period="0A", authority_grade=RegistryAuthorityGrade.APPLICABILITY
    ),
    DemoCase("189", "2023", None, None, filing_year=2023, period="0A"),
    DemoCase("189", "2024", None, None, filing_year=2024, period="0A"),
    DemoCase("189", "2025", None, None, period="0A"),
    DemoCase("193", "2022", "decl.retenciones-total", Decimal("570"), filing_year=2022, period="0A"),
    DemoCase("193", "2023", "decl.retenciones-total", Decimal("570"), filing_year=2023, period="0A"),
    DemoCase("193", "2024", "decl.retenciones-total", Decimal("570"), filing_year=2024, period="0A"),
    DemoCase("193", "2025-y-siguientes", "decl.retenciones-total", Decimal("570"), filing_year=2025, period="0A"),
    DemoCase("190", "2022", "decl.retenciones-total", Decimal("4200"), filing_year=2022, period="0A"),
    DemoCase("190", "2023", "decl.retenciones-total", Decimal("4200"), filing_year=2023, period="0A"),
    DemoCase("190", "2024", "decl.retenciones-total", Decimal("4200"), filing_year=2024, period="0A"),
    DemoCase("190", "2025-y-siguientes", "decl.retenciones-total", Decimal("4200"), period="0A"),
    DemoCase(
        "188", "2022", None, None, filing_year=2022, period="0A", authority_grade=RegistryAuthorityGrade.APPLICABILITY
    ),
    DemoCase("181", "2022-y-siguientes", None, None, period="0A", authority_grade=RegistryAuthorityGrade.APPLICABILITY),
    DemoCase("111", "2019-y-siguientes", "30", Decimal("1150")),
    DemoCase("115", "2019-y-siguientes", "05", Decimal("1900")),
    DemoCase("123", "2019-2023", "08", Decimal("1900"), filing_year=2023),
    DemoCase("123", "2024-y-siguientes", "14", Decimal("1900")),
    DemoCase("126", "2019-y-siguientes", "12", Decimal("1900"), authority_grade=RegistryAuthorityGrade.CALCULATION),
    DemoCase("128", "2019-y-siguientes", "07", Decimal("1900"), authority_grade=RegistryAuthorityGrade.CALCULATION),
    DemoCase("117", "2019-y-siguientes", "11", Decimal("2100"), authority_grade=RegistryAuthorityGrade.CALCULATION),
    DemoCase("216", "2024-y-siguientes", "21", Decimal("1800")),
    DemoCase(
        "122",
        "2017-y-siguientes",
        "resultado.a-ingresar",
        Decimal("300"),
        authority_grade=RegistryAuthorityGrade.APPLICABILITY,
        period="0A",
    ),
    DemoCase("136", "2022-2025", "07", Decimal("12000"), authority_grade=RegistryAuthorityGrade.CALCULATION),
    DemoCase(
        "136",
        "2026",
        "07",
        Decimal("12000"),
        filing_year=2026,
        authority_grade=RegistryAuthorityGrade.CALCULATION,
    ),
    DemoCase(
        "216",
        "2020-2023",
        "7",
        Decimal("1800"),
        filing_year=2023,
        authority_grade=RegistryAuthorityGrade.CALCULATION,
    ),
    DemoCase("145", "2012-01-31-y-siguientes", None, None, period="comunicacion"),
    DemoCase("232", "2018-y-siguientes", None, None, period="0A"),
    DemoCase("202", "2025-y-siguientes", "34", Decimal("19200"), period="1P"),
    DemoCase("202", "2019-2022", "34", Decimal("3200"), filing_year=2022, period="1P"),
    DemoCase("202", "2023-2024", "34", Decimal("3200"), filing_year=2024, period="1P"),
    DemoCase(
        "222",
        "2025-y-siguientes",
        "34",
        Decimal("19200"),
        authority_grade=RegistryAuthorityGrade.CALCULATION,
        period="1P",
    ),
    *(
        DemoCase(
            "222",
            str(year),
            "34",
            Decimal("3200"),
            filing_year=year,
            authority_grade=RegistryAuthorityGrade.CALCULATION,
            period="1P",
        )
        for year in (2022, 2023, 2024)
    ),
    *(
        DemoCase(
            "194",
            str(year),
            "03",
            Decimal("23.75"),
            filing_year=max(year, 2022),
            period="0A",
            authority_grade=RegistryAuthorityGrade.APPLICABILITY,
        )
        for year in (2019, 2023, 2024)
    ),
    DemoCase("156", "2003-y-siguientes", None, None, period="0A", authority_grade=RegistryAuthorityGrade.APPLICABILITY),
    DemoCase("308", "2019-y-siguientes", "decl.req-iva-devolver-17", Decimal("250.35"), period="AD-HOC"),
    DemoCase("309", "2023-y-siguientes", "decl.resultado-24", Decimal("210"), period="AD-HOC"),
    DemoCase(
        "309",
        "2018-2022",
        "decl.resultado-24",
        Decimal("210"),
        filing_year=2022,
        period="AD-HOC",
        authority_grade=RegistryAuthorityGrade.APPLICABILITY,
    ),
)

DEMO_NOTICE = (
    "EJEMPLO FICTICIO. Generado desde las declaraciones actuales del registro para probar el diseño. "
    "No contiene datos de un contribuyente ni constituye una declaración presentada. "
    "Las entradas de la rama de cálculo demostrada se fijan explícitamente a cero salvo los importes indicados; "
    "las demás entradas permanecen sin dato. Las páginas y secciones conservan su estado de revisión."
)


def demonstration_snapshot(case: DemoCase) -> RegistrySnapshot:
    """Validate mutable development source in memory, without installing it."""
    return compiled_bundled_authority().snapshot(
        case.modelo,
        filing_year=case.filing_year,
        period=case.period,
        revision_id=case.revision,
        grade=case.authority_grade,
    )


def _scenario_leaves(snapshot: RegistrySnapshot, result: str) -> tuple[set[str], set[str]]:
    """Find the selected synthetic result's inputs through the actual formula DAG."""
    casillas = {str(c.id): c for c in snapshot.revision.casillas}
    formulas = {f.id: f for f in snapshot.revision.formulas}
    visited: set[str] = set()
    leaves: set[str] = set()
    bindings: set[str] = set()

    def visit_casilla(identifier: str) -> None:
        if identifier in visited:
            return
        visited.add(identifier)
        casilla = casillas[identifier]
        if casilla.formula is None:
            leaves.add(identifier)
        else:
            visit_expression(formulas[casilla.formula].expression)

    def visit_expression(expression: FormulaExpression) -> None:
        if expression.casilla_id is not None:
            visit_casilla(str(expression.casilla_id))
        if expression.binding is not None:
            bindings.add(str(expression.binding))
        for argument in expression.args:
            visit_expression(argument)

    visit_casilla(result)
    return leaves, bindings


def demonstration_inputs(snapshot: RegistrySnapshot, case: DemoCase) -> tuple[OperatorInputs, dict[str, Decimal]]:
    """Seed fictional figures and declared context; unselected branches remain unknown."""
    if case.modelo == "308":
        return refund_inputs(case.filing_year), {}
    if case.modelo == "309":
        return nonperiodic_vat_inputs(
            case.filing_year,
            additional_rate_row=any(c.id == "decl.rg-base-25" for c in snapshot.revision.casillas),
        ), {}
    if case.modelo == "347":
        with validating_governed_facts(compiled_bundled_authority()):
            totals = third_party_summary(snapshot)
        return OperatorInputs(
            values=(
                OperatorInput(casilla_id="decl.ejercicio", value=Decimal(case.filing_year)),
                OperatorInput(casilla_id="decl.tipo-declaracion", value="Ordinaria"),
                OperatorInput(casilla_id="decl.persona-relacion", value="Contacto ficticio Ejemplo"),
            )
        ), {str(key): value for key, value in totals.items()}
    if case.modelo == "156":
        monthly_values: dict[str, Decimal | str] = {
            "decl.ejercicio": Decimal(case.filing_year),
            "decl.tipo-declaracion": "Ordinaria",
            "declarante-razon-social": "Mutualidad ficticia Ejemplo",
            "numero-total-afiliados": Decimal(len(contribution_members())),
            "domicilio-via": "Calle del Ejemplo",
            "domicilio-numero": "12",
            "domicilio-escalera": "A",
            "domicilio-piso": "2",
            "domicilio-puerta": "1",
            "domicilio-codigo-postal": "08001",
            "domicilio-municipio": "Barcelona",
            "domicilio-provincia": "Barcelona",
        }
        return OperatorInputs(values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in monthly_values.items())), {}
    if case.modelo == "194":
        resolved = resolve_withholding_binding_values(snapshot.revision, financial_asset_observations(case.filing_year))
        inputs = OperatorInputs(
            values=tuple(
                OperatorInput(casilla_id=str(c.id), value=resolved[c.binding])
                for c in snapshot.revision.casillas
                if c.binding is not None and c.binding in resolved
            )
        )
        formula_bindings = set().union(*(_scenario_leaves(snapshot, box)[1] for box in ("02", "03", "05")))
        return inputs, {str(key): value for key, value in resolved.items() if str(key) in formula_bindings}
    if case.modelo == "193":
        _, base_bindings = _scenario_leaves(snapshot, "decl.base-total")
        _, retention_bindings = _scenario_leaves(snapshot, "decl.retenciones-total")
        bindings = {key: Decimal("3000") for key in base_bindings}
        bindings.update({key: Decimal("570") for key in retention_bindings})
        return OperatorInputs(
            values=(
                OperatorInput(casilla_id="decl.total-perceptores", value=Decimal("2")),
                OperatorInput(casilla_id="decl.retenciones-ingresadas", value=Decimal("570")),
                OperatorInput(casilla_id="decl.gastos-total", value=Decimal("25")),
            )
        ), bindings
    if case.modelo == "190":
        _, income_bindings = _scenario_leaves(snapshot, "decl.percepciones-total")
        _, withholding_bindings = _scenario_leaves(snapshot, "decl.retenciones-total")
        bindings = dict.fromkeys(income_bindings | withholding_bindings, Decimal("0"))
        if "modelo-190-111-trabajo-dinerario-importe-anual" in income_bindings:
            bindings["modelo-190-111-trabajo-dinerario-importe-anual"] = Decimal("42000")
            bindings["modelo-190-111-retenciones-anual"] = Decimal("4200")
        else:
            bindings["modelo-190-perceptor-rows-percepcion-dineraria-total"] = Decimal("42000")
            bindings["modelo-190-perceptor-rows-retencion-practicada-total"] = Decimal("4200")
        return OperatorInputs(
            values=(OperatorInput(casilla_id="decl.total-percepciones", value=Decimal("2")),)
        ), bindings
    if case.modelo == "189":
        securities_values: dict[str, Decimal | str] = {
            "ejercicio-declaracion": Decimal(case.filing_year),
            "declarante-nif": "B12345674",
            "declarante-razon-social": "Entidad depositaria ficticia Ejemplo",
            "tipo-soporte": "T",
            "numero-total-declarados": Decimal("1"),
            "valoracion-total": Decimal("1500"),
            "declarado-nif": "12345678Z",
            "declarado-nombre": "Titular ficticia Ejemplo",
            "codigo-provincia": "08",
            "clave-mercado": "A",
            "clave-valor": "A",
            "valoracion": Decimal("1500"),
            "porcentaje-participacion": Decimal("100"),
            "numero-valores": Decimal("10"),
            "nominal-unitario-valores": Decimal("100"),
        }
        return OperatorInputs(
            values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in securities_values.items())
        ), {}
    if case.modelo == "188":
        insurance_values: dict[str, Decimal | str] = {
            "decl.ejercicio": Decimal(case.filing_year),
            "decl.nif": "B12345674",
            "decl.nombre": "Aseguradora ficticia Ejemplo",
            "decl.contacto": "Persona de contacto ficticia",
            "01": Decimal("1"),
            "02": Decimal("1000"),
            "03": Decimal("190"),
            "04": Decimal("0"),
            "05": Decimal("0"),
            "perceptor.nif": "12345678Z",
            "perceptor.nombre": "Perceptora ficticia Ejemplo",
            "perceptor.provincia": "08",
            "perceptor.modalidad": "1",
            "perceptor.rentas": Decimal("1000"),
            "perceptor.reducciones": Decimal("0"),
            "perceptor.base-retenciones": Decimal("1000"),
            "perceptor.porcentaje-retencion": Decimal("19"),
            "perceptor.retenciones": Decimal("190"),
        }
        return OperatorInputs(
            values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in insurance_values.items())
        ), {}
    if case.modelo == "185":
        affiliation_values: dict[str, Decimal | str] = {
            "decl.ejercicio": Decimal(case.filing_year),
            "decl.periodo": case.period,
            "decl.total-registros": Decimal("1"),
            "declarado.nif": "12345678Z",
            "declarado.nombre": "Afiliada ficticia Ejemplo",
            "declarado.numero-afiliacion": "000000000001",
            "declarado.pluriactividad": "N",
        }
        for suffix, days in (("", "31"), ("-1", "28"), ("-2", "15")):
            affiliation_values.update(
                {
                    f"declarado.situacion-mes{suffix}": "A",
                    f"declarado.regimen-cotizacion-mes{suffix}": "G",
                    f"declarado.dias-alta-mes{suffix}": Decimal(days),
                    f"declarado.tipo-jornada-mes{suffix}": "1",
                }
            )
        return OperatorInputs(
            values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in affiliation_values.items())
        ), {}
    if case.modelo == "181":
        loan_values: dict[str, Decimal | str] = {
            "decl.ejercicio": Decimal(case.filing_year),
            "declarante-razon-social": "Entidad financiera ficticia Ejemplo",
            "numero-total-declarados": Decimal("1"),
            "importe-total-capital-amortizado": Decimal("6000"),
            "importe-total-intereses": Decimal("2400"),
            "importe-total-gastos-financiacion": Decimal("120"),
            "importe-total-saldos-pendientes": Decimal("94000"),
            "declarado-nif": "12345678Z",
            "declarado-nombre": "Prestatario ficticio Ejemplo",
            "codigo-provincia": "08",
            "identificacion-operacion": "PRESTAMO-FICTICIO-001",
            "fecha-operacion": "20240115",
            "duracion-operacion": Decimal("240"),
            "importe-operacion": Decimal("100000"),
            "importe-amortizacion-capital": Decimal("6000"),
            "importe-intereses": Decimal("2400"),
            "importe-gastos-financiacion": Decimal("120"),
            "saldo-pendiente": Decimal("94000"),
            "porcentaje-participacion": Decimal("100"),
        }
        return OperatorInputs(values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in loan_values.items())), {}
    if case.modelo == "184":
        reported: dict[str, Decimal | str] = {
            "decl.ejercicio": Decimal(case.filing_year),
            "decl.total-socios": Decimal("2"),
            "decl.entidad-espanola.tipo-entidad": "2",
            "tipo2.clave": "D",
            "tipo2.subclave": "01",
            "tipo2.ingresos-integros": Decimal("10000"),
            "tipo2.gastos": Decimal("4000"),
            "tipo2.renta-atribuible-importe": Decimal("6000"),
        }
        if "decl.total-registros-entidad" in {str(c.id) for c in snapshot.revision.casillas}:
            reported["decl.total-registros-entidad"] = Decimal("1")
        return OperatorInputs(values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in reported.items())), {}
    if case.modelo == "180":
        return OperatorInputs(values=(OperatorInput(casilla_id="decl.total-perceptores", value=Decimal("2")),)), {
            "modelo-180-115-base-anual": Decimal("18000"),
            "modelo-180-115-retenciones-anual": Decimal("3420"),
        }
    if case.modelo == "232":
        reported: dict[str, Decimal | str] = {
            "decl.ejercicio": Decimal(case.filing_year),
            "decl.cnae": "6201",
            "vinculada-1-nif": "B00000000",
            "vinculada-1-fjo": "J",
            "vinculada-1-ingreso-pago": "I",
            "vinculada-1-razon-social": "Entidad vinculada ficticia A",
            "vinculada-1-importe": Decimal("250000"),
            "vinculada-2-nif": "B00000001",
            "vinculada-2-fjo": "J",
            "vinculada-2-ingreso-pago": "P",
            "vinculada-2-razon-social": "Entidad vinculada ficticia B",
            "vinculada-2-importe": Decimal("175000"),
        }
        if not reported.keys() <= {str(c.id) for c in snapshot.revision.casillas}:
            raise ValueError("demonstration assumptions no longer match the registry")
        return OperatorInputs(values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in reported.items())), {}
    if case.modelo == "145":
        # No tax is calculated by this communication. Leave signatures, receipt
        # and unreported family circumstances unknown rather than inventing them.
        family_values: dict[str, Decimal | str] = {
            "perceptor.nif": "12345678Z",
            "perceptor.nombre": "Ana",
            "perceptor.primer-apellido": "Ejemplo",
            "perceptor.segundo-apellido": "Ficticio",
            "perceptor.anio-nacimiento": Decimal("1985"),
            "descendiente-1.anio-nacimiento": Decimal("2015"),
            "descendiente-2.anio-nacimiento": Decimal("2018"),
            "ascendiente-1.anio-nacimiento": Decimal("1950"),
            "pension-compensatoria.importe-anual": Decimal("1200"),
            "anualidades-alimentos.importe-anual": Decimal("2400"),
        }
        if not family_values.keys() <= {str(c.id) for c in snapshot.revision.casillas}:
            raise ValueError("demonstration assumptions no longer match the registry")
        return OperatorInputs(
            values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in sorted(family_values.items()))
        ), {}
    if case.result_casilla is None:
        return OperatorInputs(), {}
    leaves, binding_ids = _scenario_leaves(snapshot, case.result_casilla)
    values: dict[str, Decimal | str | bool | None] = dict.fromkeys(leaves, Decimal("0"))
    bindings = dict.fromkeys(binding_ids, Decimal("0"))
    if case.modelo == "130":
        values.update({"01": Decimal("70200"), "02": Decimal("10835"), "05": Decimal("2950"), "06": Decimal("2550")})
        bindings["irpf.previous_year_economic_activity_net_income"] = Decimal("18000")
    elif case.modelo == "303":
        values.update(
            {
                "iva.repercutido.general.base": Decimal("12000"),
                "iva.repercutido.general": Decimal("2520"),
                "iva.soportado.interiores.base": Decimal("4000"),
                "iva.soportado.interiores": Decimal("840"),
                "65": Decimal("100"),
            }
        )
    elif case.modelo in {"202", "222"}:
        # Explicitly fictional percentages exercise the revision's rate rows;
        # this example does not determine the taxpayer's applicable rates.
        values.update(
            {
                "19": Decimal("30000"),
                "20": Decimal("10000"),
                "21": Decimal("10"),
                "23": Decimal("20000"),
                "24": Decimal("15"),
                "27": Decimal("100"),
                "28": Decimal("200"),
                "29": Decimal("100"),
                "30": Decimal("500"),
            }
        )
        if case.modelo == "222":
            values["decl.ejercicio"] = Decimal(case.filing_year)
            if case.revision != "2025-y-siguientes":
                # Historical 222 derives both the total base and second tier.
                # Supply their upstream accounting result, not computed boxes.
                values.pop("19")
                values.pop("23")
                values["04"] = Decimal("30000")
        if case.revision == "2025-y-siguientes":
            values.update(
                {
                    "19": Decimal("100000"),
                    "61": Decimal("30000"),
                    "62": Decimal("20"),
                    "64": Decimal("40000"),
                    "65": Decimal("25"),
                }
            )
            if case.modelo == "222":
                values.pop("19")
    elif case.modelo == "122":
        # The registry does not calculate this regularization: both entitlement
        # and the final amount are explicitly supplied fictional facts.
        for family in ("descendientes", "ascendientes", "conyuge", "familia-numerosa", "ascendiente-dos-hijos"):
            values[f"{family}.deduccion"] = Decimal("0")
            values[f"{family}.abono-anticipado"] = Decimal("0")
        values.update(
            {
                "decl.ejercicio": Decimal(case.filing_year),
                "familia-numerosa.titulo": "TÍTULO FICTICIO",
                "familia-numerosa.deduccion": Decimal("900"),
                "familia-numerosa.abono-anticipado": Decimal("1200"),
                "resultado.a-ingresar": Decimal("300"),
            }
        )
    elif case.modelo == "136":
        # Whole ticket held by one fictional winner. Exemption is an explicit
        # supplied amount; the registry currently does not calculate proration.
        values.update({"01": Decimal("100000"), "02": Decimal("100000"), "03": Decimal("40000"), "06": Decimal("0")})
        values.update(
            {
                "declarante-nif": "12345678Z",
                "declarante-nombre": "Ana Ejemplo",
                "provincia-residencia-irpf": "28",
                "fecha-cobro-premio": f"{case.filing_year}-12-20",
                "ejercicio-declaracion": Decimal(case.filing_year),
                "periodo-declaracion": case.period,
                "organizador-denominacion": "Organizador ficticio",
                "organizador-pais": "Francia",
                "organizador-codigo-pais": "FR",
                "loteria-apuesta-denominacion": "Sorteo ficticio de diciembre",
                "fecha-celebracion": f"{case.filing_year}-12-15",
                "precio-unitario": Decimal("20"),
            }
        )
    elif case.modelo == "131":
        values.update({"01": Decimal("20000"), "02": Decimal("400"), "03": Decimal("10000"), "08": Decimal("20")})
    elif case.modelo == "123":
        if case.revision == "2019-2023":
            values.update({"01": Decimal("3"), "02": Decimal("10000"), "03": Decimal("1900"), "04": Decimal("0")})
        else:
            values.update(
                {
                    "01": Decimal("2"),
                    "02": Decimal("1"),
                    "04": Decimal("8000"),
                    "05": Decimal("2000"),
                    "07": Decimal("1520"),
                    "08": Decimal("380"),
                    "10": Decimal("0"),
                }
            )
    elif case.modelo == "216" and case.revision == "2020-2023":
        values.update(
            {
                "1": Decimal("3"),
                "2": Decimal("10000"),
                "3": Decimal("1900"),
                "4": Decimal("3"),
                "5": Decimal("2000"),
                "6": Decimal("100"),
            }
        )
    elif case.modelo == "216":
        values.update(
            {
                "05": Decimal("2"),
                "06": Decimal("1"),
                "08": Decimal("8000"),
                "09": Decimal("2000"),
                "11": Decimal("1520"),
                "12": Decimal("380"),
                "14": Decimal("1"),
                "15": Decimal("2"),
                "17": Decimal("500"),
                "18": Decimal("1500"),
                "20": Decimal("100"),
            }
        )
    elif case.modelo == "117":
        values.update(
            {
                "01": Decimal("2"),
                "02": Decimal("10000"),
                "03": Decimal("1900"),
                "04": Decimal("1"),
                "05": Decimal("1000"),
                "06": Decimal("190"),
                "07": Decimal("1000"),
                "08": Decimal("190"),
                "10": Decimal("180"),
            }
        )
    elif case.modelo == "128":
        values.update(
            {"01": Decimal("2"), "02": Decimal("10000"), "03": Decimal("1900"), "04": Decimal("0"), "05": Decimal("0")}
        )
    elif case.modelo == "126":
        values.update({"01": Decimal("10000"), "02": Decimal("1900")})
        values.update(dict.fromkeys(("03", "04", "05", "07", "08", "09"), Decimal("0")))
    elif case.modelo == "115":
        values.update({"01": Decimal("2"), "02": Decimal("10000")})
    elif case.modelo == "111":
        values.update(
            {
                "01": Decimal("2"),
                "02": Decimal("10000"),
                "03": Decimal("1000"),
                "07": Decimal("1"),
                "08": Decimal("1000"),
                "09": Decimal("150"),
            }
        )
    known = {str(c.id) for c in snapshot.revision.casillas}
    if not values.keys() <= known or not bindings.keys() <= binding_ids:
        raise ValueError("demonstration assumptions no longer match the registry")
    calculated = {str(c.id) for c in snapshot.revision.casillas if c.formula is not None}
    if calculated & values.keys():
        raise ValueError("demonstration inputs cannot override calculated casillas")
    return OperatorInputs(
        values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in sorted(values.items()))
    ), bindings


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
    if snapshot.modelo.id != "349":
        return None
    rows = tuple(
        Modelo349OperadorRow.model_validate(
            {
                "codigo_pais": country,
                "nif_comunitario": nif,
                "razon_social": name,
                "clave_operacion": "E",
                "importe": amount,
            }
        )
        for country, nif, name, amount in (
            ("DE", "DE123456789", "Empresa ficticia A", Decimal("12000")),
            ("FR", "FR12345678901", "Empresa ficticia B", Decimal("4500")),
        )
    )
    work_unit_id = sha256_hex(b"registry-workbook-compiler-fictional-349-2025-4T")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=rows,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    timestamp = datetime(2025, 12, 31, tzinfo=UTC)
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        detail_rows=rows,
        created_at=timestamp,
        updated_at=timestamp,
        filing_instance_evidence=None,
        source_provenance=(),
    )


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
        "308",
        "309",
    }:
        return None
    entity_name = {
        "184": "Comunidad ficticia Ejemplo",
        "190": "Empresa ficticia Ejemplo",
        "193": "Empresa ficticia Ejemplo",
        "194": "Entidad financiera ficticia Ejemplo",
        "156": "Mutualidad ficticia Ejemplo",
        "347": "Empresa ficticia Ejemplo",
    }.get(case.modelo)
    return build_filing_producer_snapshot(
        modelo=Modelo(case.modelo),
        taxpayer_tax_id={
            "156": "B12345674",
            "184": "E00000000",
            "190": "B12345674",
            "193": "B12345674",
            "194": "B12345674",
            "347": "B12345674",
        }.get(case.modelo, "12345678Z"),
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=entity_name,
            given_name=None if entity_name else "Ana",
            surnames=None if entity_name else "Ejemplo",
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


def build_demonstration_plan(case: DemoCase) -> tuple[RegistrySnapshot, SheetExportPlan]:
    """Use the same typed form compiler for each modelo and preserve its formulas."""
    snapshot = demonstration_snapshot(case)
    inputs, bindings = demonstration_inputs(snapshot, case)
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
        plan = add_form_workbook(
            plan,
            snapshot,
            revision=demonstration_records(snapshot),
            producer_snapshot=demonstration_producer(case),
        )
    title_regions = {(s.tab, s.start_row, s.start_column) for s in plan.styled_ranges if s.role == StyleRole.TITLE}
    cells = tuple(
        cell.model_copy(update={"value": f"{cell.value} · EJEMPLO FICTICIO"})
        if cell.address.tab == TabName.FORM
        and (cell.address.tab, cell.address.row, cell.address.column) in title_regions
        else cell
        for cell in plan.value_cells
    )
    notice = DEMO_NOTICE + (
        " Los resultados por actividad del modelo 131 son datos introducidos; todavía no se calculan "
        "automáticamente a partir del rendimiento y el porcentaje."
        if case.modelo == "131"
        else ""
    )
    if case.modelo == "136":
        notice += (
            " La cuantía exenta es un dato introducido para este ejemplo de titular único; "
            "no se calcula automáticamente el reparto de la exención. El importe ingresado se declara "
            "por separado y no prueba que se haya efectuado un pago."
        )
    if case.modelo == "309":
        notice += (
            " La base, el tipo y las cuotas por fila son datos introducidos; las cuotas no se recalculan "
            "al cambiar la base o el tipo. Los totales 22 y 24 sí se calculan con las fórmulas del modelo. "
            "El importe mostrado en Ingreso es el resultado a ingresar y no acredita un pago. "
            "Los datos sin completar siguen pendientes; este ejemplo no está listo para presentar."
        )
    if case.modelo == "122":
        notice += (
            " La deducción, el abono anticipado y el resultado de 300 euros son datos introducidos. "
            "El resultado no se recalcula automáticamente al modificar los importes de las deducciones. "
            "Este ejemplo utiliza el diseño de 2018; la presentación histórica de 2017 está pendiente."
        )
    if case.modelo == "145":
        notice = (
            "EJEMPLO FICTICIO. Comunicación al pagador, no declaración presentada a la AEAT. Este borrador conserva "
            "los campos del diseño de 2012; no reproduce íntegramente el formulario vigente. "
            "No calcula retenciones. Las firmas y el acuse de recibo están sin completar. "
            "Los datos no facilitados permanecen sin dato; no se sustituyen por cero."
        )
    if case.modelo == "232":
        notice = (
            "EJEMPLO FICTICIO. Declaración informativa de operaciones vinculadas. "
            "Los importes sin IVA de 250.000 euros de ingreso y 175.000 euros de pago son datos introducidos "
            "de dos entidades jurídicas inventadas. Se muestran por separado, sin compensarlos; "
            "este modelo no calcula una cuota tributaria. Las demás operaciones, códigos y datos de "
            "identificación permanecen sin dato. Las fechas corresponden al período anual seleccionado; "
            "este ejemplo no representa un ejercicio fiscal distinto del año natural. Las explicaciones "
            "de los códigos todavía no están completas. No constituye una declaración presentada."
        )
    if case.modelo == "180":
        notice = (
            "EJEMPLO FICTICIO. Resumen anual de arrendamientos con dos perceptores inventados. "
            "El detalle guardado muestra bases de 12.000 y 6.000 euros y retenciones de 2.280 y 1.140 euros. "
            "Las casillas 02 y 03 copian los totales anuales de origen: 18.000 y 3.420 euros. "
            "El detalle es de consulta; editar los totales de origen no modifica ni vuelve a sumar sus registros. "
            "No constituye una declaración presentada. Los datos no aportados permanecen sin dato."
        )
    if case.modelo == "181":
        notice = (
            "EJEMPLO FICTICIO PARA EL EJERCICIO 2025. Hoja resumen y una operación de préstamo inventada. "
            "Las casillas 01 a 05 siguen la hoja resumen oficial; el detalle adapta el diseño electrónico de 2022. "
            "Los totales y los importes del préstamo son datos declarados independientes: no se recalculan entre sí. "
            "Los datos no aportados permanecen sin dato. "
            "La firma y la repetición de varias operaciones están pendientes. "
            "El nuevo diseño aplicable desde el ejercicio 2026 no está representado en este ejemplo. "
            "No constituye una declaración presentada."
        )
    if case.modelo == "185":
        notice = (
            "EJEMPLO FICTICIO DE MARZO DE 2026. Una afiliada inventada, con datos del mes declarado, "
            "febrero y enero. Ejemplo de información de la Seguridad Social: no corresponde a una mutualidad. "
            "A significa alta; G, régimen general; jornada 1, completa; pluriactividad N, un solo régimen. "
            "Los días 31, 28 y 15 y el total de un registro son datos declarados, no resultados calculados. "
            "La afiliación 000000000001 es ficticia. Los datos no aportados permanecen sin dato. "
            "El documento adapta el diseño electrónico oficial; no es una declaración presentada. "
            "La repetición de varios afiliados y la ocultación de campos no aplicables están pendientes."
        )
    if case.modelo == "188":
        notice = (
            "EJEMPLO FICTICIO. Una perceptora de rendimientos dinerarios de un seguro. "
            "Rendimiento y base de 1.000 euros, tipo declarado del 19 % y retención de 190 euros. "
            "Todos son importes declarados independientes: todavía no se recalculan entre sí. "
            "El resumen también contiene valores declarados, no una suma automática del detalle. "
            "La provincia 08 es Barcelona y la modalidad 1 corresponde a rendimientos dinerarios. "
            "La identidad del declarante es ficticia e introducida manualmente; no procede de un perfil real. "
            "El teléfono, los justificantes y las circunstancias no aportadas quedan sin dato. "
            "La repetición de perceptores y los controles entre campos están pendientes. "
            "No constituye una declaración presentada."
        )
    if case.modelo == "156":
        notice = (
            "EJEMPLO FICTICIO. Dos afiliados y doce meses de cotización por persona. "
            "S indica que cotizó al menos un día; N indica que no cotizó. "
            "Cada situación y cada cuota son datos independientes del ejemplo. "
            "El número de afiliados se obtiene de los dos registros del ejemplo. "
            "No se calcula una deducción ni un resultado fiscal. Los datos no aportados quedan sin dato. "
            "El domicilio es ficticio. La fecha y los datos de quien firma quedan sin dato; el espacio de firma "
            "está reservado para el papel y no acredita una firma electrónica. "
            "El detalle muestra los datos guardados de cada afiliado; sus cuotas no se recalculan.  "
            "No constituye una declaración presentada."
        )
    if case.modelo == "194":
        notice = (
            "EJEMPLO FICTICIO. Cinco operaciones de una misma perceptora. "
            "Dos bases positivas suman 125 euros; tres bases negativas o cero suman 50 euros en valor absoluto. "
            "Las retenciones declaradas suman 23,75 euros. El resumen y el detalle se generan a partir "
            "de las mismas operaciones. Las bases y el tipo del 19 % son supuestos del ejemplo, "
            "no una determinación fiscal. El detalle guardado es de consulta; sus celdas no recalculan el resumen. "
            "Los datos no aportados quedan sin dato. Firma y controles entre campos pendientes. "
            "No constituye una declaración presentada."
        )
    if case.modelo == "193":
        source_notice = (
            "Los totales proceden de los importes anuales del modelo 123. "
            if case.revision == "2024"
            else "Los totales proceden de los importes agregados de los perceptores. "
        )
        notice = (
            "EJEMPLO FICTICIO. Dos perceptores con bases declaradas de 1.000 y 2.000 euros, "
            "retenciones de 190 y 380 euros y un gasto de custodia de 25 euros. "
            + source_notice
            + "El tipo del 19 % y las bases son supuestos del ejemplo, no una determinación fiscal. "
            "El detalle guardado es de consulta: editar los totales de origen "
            "no modifica ni vuelve a sumar sus registros. "
            "Los gastos y las retenciones ingresadas del resumen son importes declarados independientes. "
            "Los datos no aportados quedan sin dato. La empresa y sus perceptores son ficticios. "
            "La firma y los controles entre campos siguen pendientes. No constituye una declaración presentada."
        )
    if case.modelo == "190":
        source_notice = (
            "El resumen usa los totales anuales de origen del modelo 111: 42.000 y 4.200 euros. "
            if case.revision == "2025-y-siguientes"
            else "El resumen suma los importes agregados por concepto del detalle: 42.000 y 4.200 euros. "
        )
        notice = (
            "EJEMPLO FICTICIO. Dos perceptores de rendimientos del trabajo, clave A. "
            "Importes declarados de 24.000 y 18.000 euros, con retenciones de 2.400 y 1.800 euros. "
            + source_notice
            + "Se supone que no hay otras percepciones anuales. El detalle guardado es de consulta: "
            "editar los totales de origen no modifica ni vuelve a sumar sus registros. "
            "Las circunstancias personales no aportadas permanecen sin dato. "
            "La empresa declarante y su NIF son ficticios y distintos de la identidad del presentador. "
            "La firma y los controles entre campos siguen pendientes. "
            "Desde 2025 se adapta el diseño electrónico, sin la numeración de la antigua hoja impresa. "
            "No constituye una declaración presentada."
        )
    if case.modelo == "189":
        notice = (
            "EJEMPLO FICTICIO. Una entidad depositaria y una titular inventadas. "
            "Diez valores, nominal unitario de 100 euros y valoración declarada de 1.500 euros. "
            "El nominal no es el valor de mercado: esta hoja no calcula la valoración multiplicándolo. "
            "Las claves A corresponden al mercado secundario oficial español y a acciones o participaciones. "
            "La participación declarada es del 100 %. El total y el detalle son datos independientes; "
            "todavía no se agregan automáticamente. La identificación del valor, el contacto y los "
            "justificantes no aportados quedan sin dato. La repetición de titulares, la firma y los "
            "controles entre campos están pendientes. No constituye una declaración presentada."
        )
    if case.modelo == "184":
        notice = (
            "EJEMPLO FICTICIO. Entidad en atribución de rentas con dos miembros inventados. "
            "Los ingresos de 10.000 euros, gastos de 4.000 euros y renta atribuible de 6.000 euros "
            "son datos introducidos. "
            "El registro no define fórmulas para recalcularlos. Las participaciones del 60 % y 40 % y los importes "
            "atribuidos de 3.600 y 2.400 euros pertenecen al detalle guardado: "
            "no cambian al editar la renta de la entidad. "
            "La clave D identifica actividades económicas; la subclave 01 de la entidad "
            "indica rentas obtenidas en España "
            "y la subclave 01 de los miembros indica estimación directa normal. "
            "Este ejemplo contiene una sola renta de la entidad. "
            "Los campos de otras clases de renta permanecen sin dato. "
            "No constituye una declaración presentada."
        )
    if case.modelo in {"202", "222"}:
        rate_count = "cuatro" if case.revision == "2025-y-siguientes" else "dos"
        notice += (
            f" Los {rate_count} porcentajes son ficticios para comprobar las filas de la tabla; "
            "no determinan el tipo que corresponde a una empresa. "
        )
        if case.modelo == "222" and case.revision != "2025-y-siguientes":
            notice += (
                "La base total de la casilla 19 y la segunda base de la casilla 23 se calculan desde las entradas. "
            )
        elif case.modelo == "222":
            notice += "La base total de la casilla 19 se calcula desde las entradas. "
        else:
            notice += "La base total de la casilla 19 es un dato introducido. "
        notice += (
            "Este borrador cubre las casillas de la parte 1; "
            "las opciones de régimen y los desgloses de la parte 2 siguen pendientes. "
        )
        if case.modelo == "202":
            notice += (
                "Los datos de identificación permanecen sin dato: la aplicación todavía no admite "
                "un perfil de presentación completo para este modelo."
            )
        else:
            notice += "Este ejemplo no aporta un perfil del grupo fiscal; sus datos de identificación siguen sin dato."
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
    return snapshot, SheetExportPlan.model_validate({**dict(plan), "value_cells": cells, "guide": guide})


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
