"""Direct fictional input values for individual model demonstrations."""

from __future__ import annotations

from decimal import Decimal

from cadrumo.application.storage.calc_sheets.records import (
    OperatorInput,
    OperatorInputs,
)
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.withholding_bindings import resolve_withholding_binding_values

from .compiler.authority import compiled_bundled_authority
from .workbook_demo_cases import DemoCase
from .workbook_demo_formula_graph import scenario_leaves
from .workbook_demo_group_vat import group_vat_inputs
from .workbook_demo_intracommunity import intracommunity_summary
from .workbook_demo_members import contribution_members
from .workbook_demo_nonperiodic import nonperiodic_vat_inputs
from .workbook_demo_records import (
    financial_asset_observations,
)
from .workbook_demo_refunds import refund_inputs
from .workbook_demo_third_parties import third_party_summary

InputResult = tuple[OperatorInputs, dict[str, Decimal]]


def _inputs_322(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
    return group_vat_inputs(case.filing_year, case.period), {}


def _inputs_308(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
    return refund_inputs(case.filing_year), {}


def _inputs_309(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
    return nonperiodic_vat_inputs(
        case.filing_year,
        additional_rate_row=any(c.id == "decl.rg-base-25" for c in snapshot.revision.casillas),
    ), {}


def _inputs_349(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
    totals = intracommunity_summary(snapshot)
    return OperatorInputs(
        values=tuple(
            OperatorInput(casilla_id=str(c.id), value=totals[c.binding])
            for c in snapshot.revision.casillas
            if c.binding is not None and c.binding in totals
        )
    ), {}


def _inputs_347(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
    with validating_governed_facts(compiled_bundled_authority()):
        totals = third_party_summary(snapshot)
    return OperatorInputs(
        values=(
            OperatorInput(casilla_id="decl.ejercicio", value=Decimal(case.filing_year)),
            OperatorInput(casilla_id="decl.tipo-declaracion", value="Ordinaria"),
            OperatorInput(casilla_id="decl.persona-relacion", value="Contacto ficticio Ejemplo"),
        )
    ), {str(key): value for key, value in totals.items()}


def _inputs_156(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
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


def _inputs_194(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
    resolved = resolve_withholding_binding_values(snapshot.revision, financial_asset_observations(case.filing_year))
    inputs = OperatorInputs(
        values=tuple(
            OperatorInput(casilla_id=str(c.id), value=resolved[c.binding])
            for c in snapshot.revision.casillas
            if c.binding is not None and c.binding in resolved
        )
    )
    formula_bindings = set[str]().union(*(scenario_leaves(snapshot, box)[1] for box in ("02", "03", "05")))
    return inputs, {str(key): value for key, value in resolved.items() if str(key) in formula_bindings}


def _inputs_193(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
    _, base_bindings = scenario_leaves(snapshot, "decl.base-total")
    _, retention_bindings = scenario_leaves(snapshot, "decl.retenciones-total")
    bindings = {key: Decimal("3000") for key in base_bindings}
    bindings.update({key: Decimal("570") for key in retention_bindings})
    return OperatorInputs(
        values=(
            OperatorInput(casilla_id="decl.total-perceptores", value=Decimal("2")),
            OperatorInput(casilla_id="decl.retenciones-ingresadas", value=Decimal("570")),
            OperatorInput(casilla_id="decl.gastos-total", value=Decimal("25")),
        )
    ), bindings


def _inputs_190(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
    _, income_bindings = scenario_leaves(snapshot, "decl.percepciones-total")
    _, withholding_bindings = scenario_leaves(snapshot, "decl.retenciones-total")
    bindings = dict.fromkeys(income_bindings | withholding_bindings, Decimal("0"))
    if "modelo-190-111-trabajo-dinerario-importe-anual" in income_bindings:
        bindings["modelo-190-111-trabajo-dinerario-importe-anual"] = Decimal("42000")
        bindings["modelo-190-111-retenciones-anual"] = Decimal("4200")
    else:
        bindings["modelo-190-perceptor-rows-percepcion-dineraria-total"] = Decimal("42000")
        bindings["modelo-190-perceptor-rows-retencion-practicada-total"] = Decimal("4200")
    return OperatorInputs(values=(OperatorInput(casilla_id="decl.total-percepciones", value=Decimal("2")),)), bindings


def _inputs_189(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
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
    return OperatorInputs(values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in securities_values.items())), {}


def _inputs_188(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
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
    return OperatorInputs(values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in insurance_values.items())), {}


def _inputs_185(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
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
    return OperatorInputs(values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in affiliation_values.items())), {}


def _inputs_181(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
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


def _inputs_184(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
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


def _inputs_180(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
    return OperatorInputs(values=(OperatorInput(casilla_id="decl.total-perceptores", value=Decimal("2")),)), {
        "modelo-180-115-base-anual": Decimal("18000"),
        "modelo-180-115-retenciones-anual": Decimal("3420"),
    }


def _inputs_232(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
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


def _inputs_145(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult:
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


_DIRECT_INPUTS = {
    "322": _inputs_322,
    "308": _inputs_308,
    "309": _inputs_309,
    "349": _inputs_349,
    "347": _inputs_347,
    "156": _inputs_156,
    "194": _inputs_194,
    "193": _inputs_193,
    "190": _inputs_190,
    "189": _inputs_189,
    "188": _inputs_188,
    "185": _inputs_185,
    "181": _inputs_181,
    "184": _inputs_184,
    "180": _inputs_180,
    "232": _inputs_232,
    "145": _inputs_145,
}


def direct_inputs(snapshot: RegistrySnapshot, case: DemoCase) -> InputResult | None:
    """Resolve direct fictional inputs for a scenario when provided."""
    resolver = _DIRECT_INPUTS.get(case.modelo)
    return resolver(snapshot, case) if resolver is not None else None
