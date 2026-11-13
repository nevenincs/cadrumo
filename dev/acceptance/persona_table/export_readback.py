"""Hold a written fichero to the stated casilla values, read back through the registry export parser.

The calculate stage compares the stated values with the calculation. This
comparison reads the exported file itself, so a return whose file omits or
misstates a stated value fails at export. A stated casilla (or a role resolved
to one in the return's edition) is compared only when the export design
carries it in at least one field; a casilla the design does not carry was
compared at calculate and is not reported here. A blank parsed value equals a
stated zero and nothing else.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from cadrumo.application.filing.runtime import build_runtime_schema_provider
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.export_parse_models import ParsedExportFieldValue
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.filing.errors import ModeloBuilderError
from cadrumo.tests.personas import ExpectedValue

from .roles import CasillaIdentity, StatedCasilla, compared, mismatch_text

_LISTED = 3
"""How many mismatches the reason names; the rest are counted."""


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).strip())
    except InvalidOperation:
        return None


def _agrees(item: StatedCasilla, fields: Iterable[ParsedExportFieldValue]) -> bool:
    expected = _decimal(item.amount)
    for field in fields:
        got = _decimal(field.value)
        if got == expected or (got is None and expected == 0):
            return True
    return False


def _shown(fields: list[ParsedExportFieldValue]) -> str:
    values = dict.fromkeys(str(field.value) for field in fields if _decimal(field.value) is not None)
    return ",".join(values) or "none"


def read_fields(
    layout: ExportLayoutDefinition,
    payload: bytes,
    *,
    modelo: str,
    year: int,
    period: str,
    operation: PinnedAuthorityOperation,
) -> tuple[ParsedExportFieldValue, ...]:
    """The fields of ``payload`` read through the registry parser, with the published sources an XML layout needs."""
    provider = build_runtime_schema_provider(
        modelos=(modelo,),
        filing_year=year,
        period=Period.from_year_and_code(year, period),
        operation=operation,
    )
    return parse_export_payload(
        layout,
        payload,
        sources=provider.sources,
        source_payloads=provider.source_payloads,
        casillas=provider.get_snapshot(modelo).revision.casillas,
    ).fields


def readback_mismatches(
    values: Iterable[ExpectedValue],
    casillas: tuple[CasillaIdentity, ...],
    unchecked: Iterable[str],
    parsed: Iterable[ParsedExportFieldValue],
) -> list[str]:
    """Each stated casilla or role the written file carries with another value, as ``<label> exp .. got ..``."""
    stated = [item for item in compared(values, casillas, unchecked) if item.casilla is not None]
    held = list(parsed)
    mismatches: list[str] = []
    for item in stated:
        carried = [field for field in held if field.casilla_id is not None and str(field.casilla_id) == item.casilla]
        if carried and not _agrees(item, carried):
            mismatches.append(mismatch_text(item, _shown(carried)))
    return mismatches


def unreadable_reason(error: RegistryError | ModeloBuilderError) -> str:
    """The export stage's refusal text for a file the registry parser cannot read."""
    return f"export readback: could not parse: {error}"[:400]


def readback_reason(mismatches: list[str]) -> str:
    """The export stage's refusal text for the mismatches, or empty when there are none."""
    if not mismatches:
        return ""
    more = len(mismatches) - _LISTED
    tail = f"; and {more} more" if more > 0 else ""
    return f"export readback: {'; '.join(mismatches[:_LISTED])}{tail}"
