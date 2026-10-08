"""Fictional Modelo 322 facts; the registry owns every formula and form position."""

from decimal import Decimal

from cadrumo.application.storage.calc_sheets.records import OperatorInput, OperatorInputs


def group_vat_inputs(year: int, period: str) -> OperatorInputs:
    """An explicit example with output VAT, deductible VAT and an advance payment."""
    values: dict[str, Decimal | str] = {}
    # Explicitly unused rows in this example, including discontinued rate slots.
    for start in (159, 171, 1, 162, 4, 7, 150, 165, 12, 153, 15, 18, 156, 168, 27, 30, 33):
        for number in range(start, start + 3):
            values[f"{number:02}"] = Decimal("0")
    for number in (10, 11, 21, 22, 23, 24, 25, 26, 36, 37, *range(39, 62)):
        values[f"{number:02}"] = Decimal("0")
    for number in (
        66,
        67,
        69,
        71,
        72,
        74,
        75,
        76,
        77,
        79,
        80,
        81,
        83,
        84,
        86,
        *range(89, 100),
        107,
        112,
        120,
        *range(122, 129),
    ):
        values[str(number)] = Decimal("0")
    values.update(
        {
            "decl.ejercicio": Decimal(year),
            "decl.periodo": period,
            "decl.sin-actividad": "",
            "decl.grupo-numero": "0001",
            "decl.grupo-rol": "D",
            "decl.regimen-163-sexies-cinco": "2",
            "decl.redeme-inscrito": "2",
            "decl.destinatario-criterio-caja": "2",
            "decl.prorrata-especial": "3" if period == "12" else "0",
            "decl.exonerado-modelo-390": "1" if period == "12" else "0",
            "decl.volumen-anual-no-cero": "1" if period == "12" else "0",
            "decl.deduccion-pago-cuenta-gasolinas": "1",
            "18": Decimal("10000"),
            "19": Decimal("21"),
            "20": Decimal("2100"),
            "45": Decimal("2000"),
            "46": Decimal("420"),
            "64": Decimal("100"),
            "66": Decimal("100"),
            "76": Decimal("20"),
            "77": Decimal("50"),
            "112": Decimal("150"),
            "actividad.principal.descripcion": "Distribución de carburantes · ejemplo ficticio",
            "80": Decimal("10000"),
            "107": Decimal("100"),
        }
    )
    # No codes, bank details or additional activities are invented to fill blanks.
    return OperatorInputs(values=tuple(OperatorInput(casilla_id=key, value=value) for key, value in values.items()))
