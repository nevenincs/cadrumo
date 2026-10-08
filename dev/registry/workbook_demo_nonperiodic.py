"""Fictional Modelo 309 facts; formulas and form positions remain registry-owned."""

from decimal import Decimal

from cadrumo.application.storage.calc_sheets.records import OperatorInput, OperatorInputs


def nonperiodic_vat_inputs(year: int, *, additional_rate_row: bool) -> OperatorInputs:
    """One fictional new-vehicle acquisition, with unused tax rows explicitly zero."""
    values: dict[str, Decimal | str] = {
        "decl.ejercicio": Decimal(year),
        "decl.periodo": "0A",
        "decl.nombre": "Ana",
        "decl.tipo-declaracion": "I",
        "decl.situacion-tributaria": "5",
        "decl.hecho-imponible": "2",
        "decl.transmitente-apellidos": "Vehículos Ejemplo",
        "decl.transmitente-pais": "FR",
        "decl.vehiculo-marca": "Ejemplo",
        "decl.vehiculo-tipo": "Turismo",
        "decl.vehiculo-modelo": "Demostración",
        "decl.a-deducir-23": Decimal("0"),
        "papel-forma-pago": "Pendiente de elegir",
    }
    for family, triples in (
        ("rg", ((1, 2, 3), (25, 26, 27), (4, 5, 6), (7, 8, 9))),
        ("re", ((10, 11, 12), (13, 14, 15), (16, 17, 18), (19, 20, 21))),
    ):
        for triple in triples:
            if triple == (25, 26, 27) and not additional_rate_row:
                continue
            for part, number in zip(("base", "tipo", "cuota"), triple, strict=True):
                values[f"decl.{family}-{part}-{number:02}"] = Decimal("0")
    values.update(
        {
            "decl.rg-base-07": Decimal("1000"),
            "decl.rg-tipo-08": Decimal("21"),
            "decl.rg-cuota-09": Decimal("210"),
        }
    )
    return OperatorInputs(values=tuple(OperatorInput(casilla_id=key, value=value) for key, value in values.items()))
