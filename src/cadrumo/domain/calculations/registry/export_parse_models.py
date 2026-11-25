"""Typed field and complete payload records produced by the registry export parsers."""

from __future__ import annotations

from ....core.casilla_id import CasillaId
from .export_value_policy import ParsedExportPolicyValue
from .ids import BindingId, ExportFieldId, ExportLayoutId, RecordId
from .schema_base import RegistryModel


class ParsedExportFieldValue(RegistryModel):
    """One field value read from an AEAT payload using a registry export field."""

    record_id: RecordId
    field_id: ExportFieldId
    casilla_id: CasillaId | None = None
    binding_id: BindingId | None = None
    raw: str
    value: ParsedExportPolicyValue
    source_locator: str


class ParsedExportPayload(RegistryModel):
    """Casilla and field values parsed from a complete registry export layout."""

    layout_id: ExportLayoutId
    fields: tuple[ParsedExportFieldValue, ...]
    casillas: tuple[ParsedExportFieldValue, ...]
