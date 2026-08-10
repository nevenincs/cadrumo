"""Canonical semantic producer vocabulary for registry export fields."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final

from pydantic import BeforeValidator

from .._export_field_kind import CasillaFieldKind
from ._errors import RegistryValidationError

__all__ = [
    "ExportComputedKey",
    "ExportComputedKeyValue",
    "ExportDraftAttribute",
    "ExportDraftAttributeValue",
    "ExportHeaderKey",
    "ExportHeaderKeyValue",
    "ExportSemanticPayloadAxis",
    "export_semantic_payload_axis",
]


class ExportHeaderKey(StrEnum):
    """Closed keys currently supplied by the one production header composer."""

    AMENDMENT_RECTIFICATIVE = "autoliq_rectificativa"
    BANK_ADDRESS = "bank_address"
    BANK_CITY = "bank_city"
    BANK_COUNTRY_CODE = "bank_country_code"
    BANK_NAME = "bank_name"
    COMPLEMENTARIA = "complementaria"
    COMPLEMENTARIA_PAGE = "complementaria_page"
    DECLARATION_TYPE = "declaration_type"
    DEVENGO_START_DATE = "devengo_start_date"
    ENTITY_TYPE = "entity_type"
    FECHA_FIN_PERIODO = "fecha_fin_periodo"
    FECHA_INICIO_PERIODO = "fecha_inicio_periodo"
    FULL_NAME = "full_name"
    IBAN = "iban"
    JUSTIFICANTE_ANTERIOR = "justificante_anterior"
    NAME = "name"
    PREVIOUS_JUSTIFICANTE = "previous_justificante"
    PRIOR_DOMICILIATION_ACTION = "prior_domiciliation_action"
    PROGRAM_VERSION = "program_version"
    REDEME = "redeme"
    SEPA_MARCA = "sepa_marca"
    SURNAMES = "surnames"
    SWIFT_BIC = "swift_bic"
    TAX_ID = "tax_id"


class ExportDraftAttribute(StrEnum):
    """Closed draft values the filing renderer may project directly."""

    PROFILE_TAX_ID = "profile_tax_id"
    FILING_YEAR = "filing_year"
    PERIOD_CODE = "period_code"


class ExportComputedKey(StrEnum):
    """Closed export values computed by the filing renderer."""

    ENVELOPE_CLOSING_TAG = "envelope_closing_tag"


class ExportSemanticPayloadAxis(StrEnum):
    """The one payload field permitted for each semantic export kind."""

    CASILLA_ID = "casilla_id"
    BINDING = "binding"
    LITERAL = "literal"
    HEADER_KEY = "header_key"
    DRAFT_ATTRIBUTE = "draft_attribute"
    COMPUTED_KEY = "computed_key"


_PAYLOAD_AXIS_BY_KIND: Final[dict[CasillaFieldKind, ExportSemanticPayloadAxis | None]] = {
    CasillaFieldKind.CASILLA: ExportSemanticPayloadAxis.CASILLA_ID,
    CasillaFieldKind.BINDING: ExportSemanticPayloadAxis.BINDING,
    CasillaFieldKind.LITERAL: ExportSemanticPayloadAxis.LITERAL,
    CasillaFieldKind.HEADER: ExportSemanticPayloadAxis.HEADER_KEY,
    CasillaFieldKind.DRAFT: ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE,
    CasillaFieldKind.COMPUTED: ExportSemanticPayloadAxis.COMPUTED_KEY,
    CasillaFieldKind.FILLER: None,
    CasillaFieldKind.CHECKSUM: None,
}


def export_semantic_payload_axis(kind: CasillaFieldKind) -> ExportSemanticPayloadAxis | None:
    """Return the sole semantic payload axis admitted for ``kind``."""
    return _PAYLOAD_AXIS_BY_KIND[kind]


def _coerce_export_token[ExportToken: StrEnum](
    value: object,
    *,
    enum_type: type[ExportToken],
    subject: str,
) -> object:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError:
            raise RegistryValidationError(
                f"{subject} {value!r} is not recognised; expected one of {[member.value for member in enum_type]}",
            ) from None
    raise RegistryValidationError(f"{subject} must be a string, got {type(value).__name__!r}")


def _coerce_export_header_key(value: object) -> object:
    return _coerce_export_token(value, enum_type=ExportHeaderKey, subject="export header_key")


def _coerce_export_draft_attribute(value: object) -> object:
    return _coerce_export_token(value, enum_type=ExportDraftAttribute, subject="export draft_attribute")


def _coerce_export_computed_key(value: object) -> object:
    return _coerce_export_token(value, enum_type=ExportComputedKey, subject="export computed_key")


ExportHeaderKeyValue = Annotated[ExportHeaderKey, BeforeValidator(_coerce_export_header_key)]
"""TOML-boundary form of :class:`ExportHeaderKey`."""

ExportDraftAttributeValue = Annotated[ExportDraftAttribute, BeforeValidator(_coerce_export_draft_attribute)]
"""TOML-boundary form of :class:`ExportDraftAttribute`."""

ExportComputedKeyValue = Annotated[ExportComputedKey, BeforeValidator(_coerce_export_computed_key)]
"""TOML-boundary form of :class:`ExportComputedKey`."""
