"""Scratch conversion helper for the production-assert retirement batch."""

from __future__ import annotations

import pathlib

BASE = pathlib.Path("src/cadrumo/domain/calculations/registry")


def sub(name: str, old: str, new: str) -> None:
    path = BASE / name
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{name}: {text.count(old)} matches for {old[:70]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


sub(
    "gasto193_bindings.py",
    """    accum: dict[str, dict[str, Decimal | str]] = {}
    for observation in observations:
        identity: dict[str, Decimal | str] = {
            "contributor_tax_id": observation.contributor_tax_id,
            "contributor_legal_name": observation.contributor_legal_name,
            "importe_gastos": Decimal("0"),
        }
        if observation.representative_tax_id is not None:
            identity["representative_tax_id"] = observation.representative_tax_id
        bucket = accum.setdefault(observation.contributor_tax_id, identity)
        previous = bucket["importe_gastos"]
        assert isinstance(previous, Decimal)
        bucket["importe_gastos"] = previous + observation.importe_gastos
    return tuple(accum[key] for key in sorted(accum.keys()))
""",
    """    accum: dict[str, dict[str, Decimal | str]] = {}
    importe_gastos: dict[str, Decimal] = {}
    for observation in observations:
        identity: dict[str, Decimal | str] = {
            "contributor_tax_id": observation.contributor_tax_id,
            "contributor_legal_name": observation.contributor_legal_name,
        }
        if observation.representative_tax_id is not None:
            identity["representative_tax_id"] = observation.representative_tax_id
        contributor_tax_id = observation.contributor_tax_id
        accum.setdefault(contributor_tax_id, identity)
        importe_gastos[contributor_tax_id] = (
            importe_gastos.get(contributor_tax_id, Decimal("0")) + observation.importe_gastos
        )
    return tuple({**accum[key], "importe_gastos": importe_gastos[key]} for key in sorted(accum.keys()))
""",
)

sub(
    "withholding296_bindings.py",
    """            "clave": observation.clave,
            "subclave": observation.subclave,
            "base_retenciones": Decimal("0"),
            "porcentaje_retencion": Decimal("0"),
            "retencion_practicada": Decimal("0"),
            "compensaciones": Decimal("0"),
            "garantias": Decimal("0"),
            "otros_importes": Decimal("0"),
            "ingreso_a_cuenta_repercutido": Decimal("0"),
""",
    """            "clave": observation.clave,
            "subclave": observation.subclave,
""",
)

sub(
    "withholding296_bindings.py",
    """        bucket = accum.setdefault(key, identity)
        for amount_field in (
            "base_retenciones",
            "porcentaje_retencion",
            "retencion_practicada",
            "compensaciones",
            "garantias",
            "otros_importes",
            "ingreso_a_cuenta_repercutido",
        ):
            previous = bucket[amount_field]
            assert isinstance(previous, Decimal)
            bucket[amount_field] = previous + getattr(observation, amount_field)
    rows: list[dict[str, Decimal | str]] = []
    for index, key in enumerate(sorted(accum.keys()), start=1):
        row = dict(accum[key])
""",
    """        accum.setdefault(key, identity)
        bucket_amounts = amounts.setdefault(key, dict.fromkeys(_WITHHOLDING296_AMOUNT_FIELDS, Decimal("0")))
        for amount_field in _WITHHOLDING296_AMOUNT_FIELDS:
            bucket_amounts[amount_field] += getattr(observation, amount_field)
    rows: list[dict[str, Decimal | str]] = []
    for index, key in enumerate(sorted(accum.keys()), start=1):
        row: dict[str, Decimal | str] = {**accum[key], **amounts[key]}
""",
)

sub(
    "withholding296_bindings.py",
    """    accum: dict[tuple[str, str, str, str], dict[str, Decimal | str]] = {}
    for observation in observations:
        key = (
            observation.codigo_pais or "",
""",
    """    accum: dict[tuple[str, str, str, str], dict[str, Decimal | str]] = {}
    amounts: dict[tuple[str, str, str, str], dict[str, Decimal]] = {}
    for observation in observations:
        key = (
            observation.codigo_pais or "",
""",
)

sub(
    "withholding296_bindings.py",
    """def _build_withholding296_rows(""",
    '''#: Amount fields the modelo 296 perceptor record sums across observations sharing one row identity.
_WITHHOLDING296_AMOUNT_FIELDS: Final[tuple[str, ...]] = (
    "base_retenciones",
    "porcentaje_retencion",
    "retencion_practicada",
    "compensaciones",
    "garantias",
    "otros_importes",
    "ingreso_a_cuenta_repercutido",
)


def _build_withholding296_rows(''',
)

print("ok")
