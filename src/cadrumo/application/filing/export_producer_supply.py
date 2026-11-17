"""Refuse an export whose layout needs a producer value nothing in the application supplies.

A record design says where a value sits and its producer key says where it
comes from. The header producers resolve exactly the keys the shared snapshot
owns, so a key the layout cites outside that set has no producer at all: the
renderer would write a non-required field blank, and a return whose identifying
header is empty is worse than one that refuses. Every such key is named at once,
before anything renders, so the refusal lists what the export is missing rather
than the first field it reached.

The same refusal covers an unsupported producer field: a slot whose wire
content its edition's official design does not state. A value for it cannot be
written without choosing a representation the design never gave, so a stated
value refuses, and so does a slot the layout requires; only an optional slot
with no value keeps its declared blank fill.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from ...core.filing_producer_key import FilingProducerKey
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.filing.errors import FilingExportValidationError
from .export_refusal_doors import ExportRefusalReason, export_design_terminal
from .producer_profile_facts import missing_producer_fact_names

#: Producer fields whose wire content the official design of their edition does
#: not state.
#:
#: Sheet DP200DID of every Modelo 200 design prints "Período Impositivo inicio -
#: Año" and "fin - Año" as Num fields of length 2 with an empty Contenido cell,
#: and the Orden's documento de ingreso o devolución draws undivided boxes: no
#: official text says which two digits of the year are written.
#:
#: Page 1 field 26 of the Modelo 200 designs that carry it, "Autoliquidación
#: rectificativa - Como consecuencia de la presentación de la autoliquidación
#: rectificativa solicito dar de baja la domiciliación efectuada", has empty
#: Validación and Contenido cells, and the Orden's page 1 prints no box for it.
UNSUPPORTED_PRODUCER_KEYS: Final[frozenset[FilingProducerKey]] = frozenset(
    {
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_INICIO_ANO,
        FilingProducerKey.M200_PERIODO_IMPOSITIVO_FIN_ANO,
        FilingProducerKey.M200_COMO_CONSECUENCIA_DE_LA_PRESENTACION_DE_LA_A,
    }
)


def unsupplied_producer_keys(
    layout: ExportLayoutDefinition, headers: Mapping[FilingProducerKey, object]
) -> tuple[FilingProducerKey, ...]:
    """Return every producer key a record of ``layout`` cites that ``headers`` holds no producer for, sorted."""
    cited = {
        field.producer_key for record in layout.records for field in record.fields if field.producer_key is not None
    }
    return tuple(sorted((key for key in cited if key not in headers), key=lambda key: key.value))


def unsupported_producer_keys(
    layout: ExportLayoutDefinition, headers: Mapping[FilingProducerKey, object]
) -> tuple[FilingProducerKey, ...]:
    """Return every unsupported producer key ``layout`` would have to write, sorted.

    A key is written when ``headers`` states a value for it, or when a field
    citing it is required and so has no blank to fall back on.
    """
    refused = {
        field.producer_key
        for record in layout.records
        for field in record.fields
        if field.producer_key in UNSUPPORTED_PRODUCER_KEYS
        and (field.required or not _is_blank(headers.get(field.producer_key)))
    }
    return tuple(sorted(refused, key=lambda key: key.value))


def require_supplied_producers(
    layout: ExportLayoutDefinition, headers: Mapping[FilingProducerKey, object], *, modelo: str
) -> None:
    """Refuse the export of ``modelo`` when its layout cites a producer nothing supplies, naming each one.

    An unsupported producer field the export would have to write refuses the
    same way: nothing in the application can supply a value its design does not
    define.
    """
    missing = unsupplied_producer_keys(layout, headers)
    unsupported = unsupported_producer_keys(layout, headers)
    if not missing and not unsupported:
        return
    refused = tuple(sorted({*missing, *unsupported}, key=lambda key: key.value))
    facts = ", ".join(missing_producer_fact_names(key) for key in refused)
    raise FilingExportValidationError(
        f"export layout of modelo {modelo} cites {len(refused)} producer key(s) nothing supplies",
        translated_message="application.filing.export.errors.producer_facts_unsupplied",
        context={
            "modelo": modelo,
            "facts": facts,
            "missing_producer_keys": ",".join(key.value for key in missing),
            "unsupported_producer_keys": ",".join(key.value for key in unsupported),
        },
        precondition_verdict=export_design_terminal(ExportRefusalReason.PRODUCER_FACT_UNSUPPLIED),
    )


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


__all__ = [
    "UNSUPPORTED_PRODUCER_KEYS",
    "require_supplied_producers",
    "unsupplied_producer_keys",
    "unsupported_producer_keys",
]
