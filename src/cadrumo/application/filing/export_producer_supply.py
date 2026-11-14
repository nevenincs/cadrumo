"""Refuse an export whose layout needs a producer value nothing in the application supplies.

A record design says where a value sits and its producer key says where it
comes from. The header producers resolve exactly the keys the shared snapshot
owns, so a key the layout cites outside that set has no producer at all: the
renderer would write a non-required field blank, and a return whose identifying
header is empty is worse than one that refuses. Every such key is named at once,
before anything renders, so the refusal lists what the export is missing rather
than the first field it reached.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.filing_producer_key import FilingProducerKey
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.filing.errors import FilingExportValidationError
from .export_refusal_doors import ExportRefusalReason, export_design_terminal
from .producer_profile_facts import missing_producer_fact_names


def unsupplied_producer_keys(
    layout: ExportLayoutDefinition, headers: Mapping[FilingProducerKey, object]
) -> tuple[FilingProducerKey, ...]:
    """Return every producer key a record of ``layout`` cites that ``headers`` holds no producer for, sorted."""
    cited = {
        field.producer_key for record in layout.records for field in record.fields if field.producer_key is not None
    }
    return tuple(sorted((key for key in cited if key not in headers), key=lambda key: key.value))


def require_supplied_producers(
    layout: ExportLayoutDefinition, headers: Mapping[FilingProducerKey, object], *, modelo: str
) -> None:
    """Refuse the export of ``modelo`` when its layout cites a producer nothing supplies, naming each one."""
    missing = unsupplied_producer_keys(layout, headers)
    if not missing:
        return
    facts = ", ".join(missing_producer_fact_names(key) for key in missing)
    raise FilingExportValidationError(
        f"export layout of modelo {modelo} cites {len(missing)} producer key(s) nothing supplies",
        translated_message="application.filing.export.errors.producer_facts_unsupplied",
        context={"modelo": modelo, "facts": facts, "missing_producer_keys": ",".join(key.value for key in missing)},
        precondition_verdict=export_design_terminal(ExportRefusalReason.PRODUCER_FACT_UNSUPPLIED),
    )


__all__ = ["require_supplied_producers", "unsupplied_producer_keys"]
