"""Per-counterparty comparison of a persona's stated informative-return values against the written fichero BOE.

Modelos 180, 190, 347 and 349 state no casillas for their perceptores and
counterparties: each stated value names a counterparty and the concepts the
law gives for it. The comparison reads the written
fichero through the registry's own export parser, so every position comes from
the hydrated export layout, and matches each stated counterparty with its
type-2 record by the identity the persona's catalogue binds to the role. A
counterparty the persona states as ``declared = "false"`` must have no record.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.export_parse_models import ParsedExportFieldValue
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.tests.personas import ExpectedValue, Identity, IdentityCatalogue

_AMOUNTS = frozenset({"importe_anual", "base"})
_DECLARED = "declared"


@dataclass(frozen=True, slots=True)
class RecordDesign:
    """Which registry bindings carry a counterparty's identity and each stated concept in its type-2 record."""

    nif: str
    country: str | None
    concepts: Mapping[str, str]


DESIGNS: Mapping[str, RecordDesign] = {
    "180": RecordDesign(
        # Positions below are the type-2 field offset and length of the 2023-y-siguientes
        # export layout (modelo-180-fichero-boe, record modelo-180-perceptor); the 2019-2022 layout is identical.
        nif="modelo-180-perceptor-row-nif",  # type-2 positions 18-26: NIF del perceptor
        country=None,
        concepts={
            # positions 79-92: base de retenciones e ingresos a cuenta
            "base_retenciones": "modelo-180-perceptor-row-base",
            # positions 93-96: porcentaje de retencion, 2 integer and 2 fractional digits
            "porcentaje_retencion": "modelo-180-perceptor-row-withholding-percentage",
            # positions 97-109: retenciones e ingresos a cuenta, 2 implied decimals
            "retenciones": "modelo-180-perceptor-row-retenciones",
            # position 78: modalidad
            "modalidad": "modelo-180-perceptor-row-modality",
            # position 114: situacion del inmueble
            "situacion_inmueble": "modelo-180-perceptor-row-property-situation",
            # positions 115-134: referencia catastral
            "referencia_catastral": "modelo-180-perceptor-row-cadastral-reference",
        },
    ),
    "190": RecordDesign(
        # Positions below are the type-2 field offset and length of the 2025-y-siguientes
        # export layout (modelo-190-fichero-boe, record modelo-190-perceptor); 2022-2024 are identical.
        nif="modelo-190-perceptor-row-nif",  # type-2 positions 18-26: NIF del perceptor
        country=None,
        concepts={
            # position 78: clave de percepcion
            "clave": "modelo-190-perceptor-row-clave",
            # positions 81-94: percepcion dineraria integra (sign at 81, magnitude 82-94)
            "importe_integro": "modelo-190-perceptor-row-percibido-dinerario",
            # positions 95-107: retenciones dinerarias practicadas, 2 implied decimals
            "retenciones": "modelo-190-perceptor-row-retencion-practicada",
        },
    ),
    "347": RecordDesign(
        nif="modelo-347-contraparte-row-nif",
        country=None,
        concepts={
            "clave": "modelo-347-contraparte-row-clave",
            "importe_anual": "modelo-347-contraparte-row-importe",
        },
    ),
    "349": RecordDesign(
        nif="iva-349-operador-row-nif",
        country="iva-349-operador-row-codigo-pais",
        concepts={
            "clave": "iva-349-operador-row-clave",
            "base": "iva-349-operador-row-base",
        },
    ),
}
"""The modelos whose per-counterparty values are compared, each with its type-2 record design."""


def is_compared(value: ExpectedValue) -> bool:
    """Whether a stated value is one the counterparty comparator takes: a counterparty value of a designed modelo."""
    return value.counterparty is not None and value.modelo in DESIGNS


def read_records(layout: ExportLayoutDefinition, payload: bytes, design: RecordDesign) -> list[dict[str, object]]:
    """The type-2 records of ``payload`` as binding to parsed value, read through the registry parser."""
    parsed = parse_export_payload(layout, payload)
    return [row for row in _rows(parsed.fields) if design.nif in row]


def _rows(fields: Iterable[ParsedExportFieldValue]) -> list[dict[str, object]]:
    """Split the parsed fields into one binding map per record instance: a repeated field id opens the next."""
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for field in fields:
        if not rows or field.field_id in seen:
            rows.append({})
            seen = set()
        seen.add(field.field_id)
        if field.binding_id is not None and field.value is not None:
            rows[-1].setdefault(field.binding_id, field.value)
    return rows


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _row_key(row: Mapping[str, object], design: RecordDesign) -> str:
    """The identity a record names: the country code and the NIF-IVA where the design carries a country."""
    country = _text(row.get(design.country)) if design.country is not None else ""
    return country + _text(row.get(design.nif))


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _same(concept: str, expected: str, got: object) -> bool:
    if concept in _AMOUNTS:
        return _decimal(got) == _decimal(expected)
    return _text(got) == expected


def _check(role: str, value: ExpectedValue, row: Mapping[str, object] | None, design: RecordDesign) -> list[str]:
    concepts = dict(value.concepts)
    if concepts.get(_DECLARED) == "false":
        return [] if row is None else [f"{role} declared exp none got record"]
    if row is None:
        return [f"{role} no type-2 record"]
    return [
        f"{role} {concept} exp {concepts[concept]} got {_text(row.get(binding))}"
        for concept, binding in design.concepts.items()
        if concept in concepts and not _same(concept, concepts[concept], row.get(binding))
    ]


def _identity_key(identity: Identity) -> str:
    """The key a record of this identity carries: country code and NIF-IVA, or the NIF alone."""
    return identity.value


def counterparty_mismatches(
    values: Sequence[ExpectedValue],
    identities: IdentityCatalogue,
    layout: ExportLayoutDefinition,
    payload: bytes,
) -> list[str]:
    """Each stated counterparty value the written fichero does not give, as ``role field exp .. got ..``.

    ``values`` are the stated values of one return; those without a designed
    counterparty are left to the casilla comparison.
    """
    compared = [value for value in values if is_compared(value)]
    if not compared:
        return []
    design = DESIGNS[compared[0].modelo]
    records = {_row_key(row, design): row for row in reversed(read_records(layout, payload, design))}
    return [
        mismatch
        for value in compared
        for mismatch in _check(
            str(value.counterparty), value, records.get(_identity_key(identities.role(str(value.counterparty)))), design
        )
    ]
