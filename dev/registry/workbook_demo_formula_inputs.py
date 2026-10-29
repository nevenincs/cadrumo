"""Fictional inputs for registered formula branches."""

from __future__ import annotations

from decimal import Decimal

from cadrumo.application.storage.calc_sheets.records import (
    OperatorInput,
    OperatorInputs,
)
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

from .workbook_demo_cases import DemoCase
from .workbook_demo_formula_graph import scenario_leaves

InputValues = dict[str, Decimal | str | bool | None]


def _seed_130(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
    values.update({"01": Decimal("70200"), "02": Decimal("10835"), "05": Decimal("2950"), "06": Decimal("2550")})
    bindings["irpf.previous_year_economic_activity_net_income"] = Decimal("18000")


def _seed_303(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
    if case.period == "4T" and any(formula.target_casilla_id == "88" for formula in snapshot.revision.formulas):
        annual_leaves, annual_bindings = scenario_leaves(snapshot, "88")
        values.update(dict.fromkeys(annual_leaves, Decimal("0")))
        bindings.update(dict.fromkeys(annual_bindings, Decimal("0")))
        values["80"] = Decimal("48000")
    values.update(
        {
            "iva.repercutido.general.base": Decimal("12000"),
            "iva.repercutido.general": Decimal("2520"),
            "iva.soportado.interiores.base": Decimal("4000"),
            "iva.soportado.interiores": Decimal("840"),
            "65": Decimal("100"),
        }
    )


def _seed_390(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
    if case.revision in {"2024", "2025"}:
        for group in range(1, 4):
            target = f"iva.anual.sector-diferenciado-{group}.suma-deducciones"
            group_leaves, group_bindings = scenario_leaves(snapshot, target)
            values.update(dict.fromkeys(group_leaves, Decimal(group * 100)))
            bindings.update(dict.fromkeys(group_bindings, Decimal(group * 100)))
            binding_ids.update(group_bindings)
    else:
        for target in (
            "iva.anual.total-bases-iva",
            "iva.anual.soportado.interiores.base",
            "iva.anual.volumen.total",
        ):
            extra_leaves, extra_bindings = scenario_leaves(snapshot, target)
            values.update(dict.fromkeys(extra_leaves, Decimal("0")))
            bindings.update(dict.fromkeys(extra_bindings, Decimal("0")))
            binding_ids.update(extra_bindings)
        values.update(
            {
                "iva.anual.repercutido.tipo-21.base": Decimal("48000"),
                "iva.anual.repercutido.tipo-21.cuota": Decimal("10080"),
                "iva.anual.deducible.interiores-corrientes.soportado.base": Decimal("16000"),
                "iva.anual.deducible.interiores-corrientes.soportado.cuota": Decimal("3360"),
                "iva.anual.volumen.regimen-general": Decimal("48000"),
            }
        )


def _seed_222(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
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


def _seed_122(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
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


def _seed_136(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
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


def _seed_131(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
    values.update({"01": Decimal("20000"), "02": Decimal("400"), "03": Decimal("10000"), "08": Decimal("20")})


def _seed_123(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
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


def _seed_216(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
    if case.revision == "2020-2023":
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
    else:
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


def _seed_117(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
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


def _seed_128(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
    values.update(
        {"01": Decimal("2"), "02": Decimal("10000"), "03": Decimal("1900"), "04": Decimal("0"), "05": Decimal("0")}
    )


def _seed_126(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
    values.update({"01": Decimal("10000"), "02": Decimal("1900")})
    values.update(dict.fromkeys(("03", "04", "05", "07", "08", "09"), Decimal("0")))


def _seed_115(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
    values.update({"01": Decimal("2"), "02": Decimal("10000")})


def _seed_111(
    snapshot: RegistrySnapshot, case: DemoCase, values: InputValues, bindings: dict[str, Decimal], binding_ids: set[str]
) -> None:
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


_SEEDERS = {
    "130": _seed_130,
    "303": _seed_303,
    "390": _seed_390,
    "222": _seed_222,
    "202": _seed_222,
    "122": _seed_122,
    "136": _seed_136,
    "131": _seed_131,
    "123": _seed_123,
    "216": _seed_216,
    "117": _seed_117,
    "128": _seed_128,
    "126": _seed_126,
    "115": _seed_115,
    "111": _seed_111,
}


def formula_inputs(snapshot: RegistrySnapshot, case: DemoCase) -> tuple[OperatorInputs, dict[str, Decimal]]:
    """Seed one registered result branch, retaining unknown unrelated inputs."""
    if case.result_casilla is None:
        return OperatorInputs(), {}
    leaves, binding_ids = scenario_leaves(snapshot, case.result_casilla)
    values: InputValues = dict.fromkeys(leaves, Decimal("0"))
    bindings = dict.fromkeys(binding_ids, Decimal("0"))
    seed = _SEEDERS.get(case.modelo)
    if seed is not None:
        seed(snapshot, case, values, bindings, binding_ids)
    known = {str(c.id) for c in snapshot.revision.casillas}
    if not values.keys() <= known or not bindings.keys() <= binding_ids:
        raise ValueError("demonstration assumptions no longer match the registry")
    calculated = {str(c.id) for c in snapshot.revision.casillas if c.formula is not None}
    if calculated & values.keys():
        raise ValueError("demonstration inputs cannot override calculated casillas")
    return OperatorInputs(
        values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in sorted(values.items()))
    ), bindings
