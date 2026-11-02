"""Locate the export-layout positions that state a declaration's filing kind.

The record designs of Modelo 130 and 131 carry a one-byte "Declaración
complementaria" position whose value domain is blank or ``X``. The registry
reaches that byte two ways: a header owned by the
``amendment_evidence.is_complementaria`` producer key, and, for the Modelo 131
designs from 2024, an operator binding that names the same record-design field.
:func:`filing_kind_marker_role` resolves both to one typed role, so the
submitted-file reader never depends on which way a revision declares it.

A second role covers a page-level "Indicador de página complementaria" on
records other than the one holding the declaration marker. Its meaning is not
settled by the design, so a reader records it without admitting it.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ....core.filing_producer_key import FilingProducerKey
from ..export_field_kind import CasillaFieldKind
from .export_semantics import ExportComputedKey
from .manual_input_selector import ManualInputProvider

if TYPE_CHECKING:
    from .ids import BindingId
    from .schema import BindingDefinition
    from .schema_exports import ExportFieldDefinition


class FilingKindMarkerRole(StrEnum):
    """What an export position says about the declaration's filing kind.

    Attributes:
        DECLARATION_MARKER: The declaration-level complementaria byte.
        PAGE_INDICATOR: A page-level complementaria indicator, recorded only.
    """

    DECLARATION_MARKER = "declaration_marker"
    PAGE_INDICATOR = "page_indicator"


#: The record-design field an operator binding names for the declaration-level
#: complementaria byte. It is the design's own field identity on the binding's
#: record-field selector, not a display label.
_DECLARATION_MARKER_DESIGN_FIELD: Final = "declaracion-complementaria"


def _is_declaration_marker_binding(binding: BindingDefinition | None) -> bool:
    if binding is None:
        return False
    provider = binding.provider
    return isinstance(provider, ManualInputProvider) and provider.field == _DECLARATION_MARKER_DESIGN_FIELD


def filing_kind_marker_role(
    field: ExportFieldDefinition,
    *,
    bindings_by_id: Mapping[BindingId, BindingDefinition],
) -> FilingKindMarkerRole | None:
    """Return the filing-kind role of one export field, or ``None`` when it has none.

    Only one-byte positions qualify. A page indicator is any
    ``continuation_page_marker`` position; the caller keeps only those on records
    other than the declaration marker's, because the principal page's own
    indicator is always blank by design.
    """
    if field.length != 1:
        return None
    if field.kind is CasillaFieldKind.HEADER and field.producer_key is FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA:
        return FilingKindMarkerRole.DECLARATION_MARKER
    if (
        field.kind is CasillaFieldKind.BINDING
        and field.binding is not None
        and _is_declaration_marker_binding(bindings_by_id.get(field.binding))
    ):
        return FilingKindMarkerRole.DECLARATION_MARKER
    if field.kind is CasillaFieldKind.COMPUTED and field.computed_key is ExportComputedKey.CONTINUATION_PAGE_MARKER:
        return FilingKindMarkerRole.PAGE_INDICATOR
    return None


__all__ = ["FilingKindMarkerRole", "filing_kind_marker_role"]
