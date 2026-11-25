"""The sentence the capital-goods declaration operation serves for each of its refusals.

A frontend shows these sentences as served, so they sit under keys of their own.
The sentence for a duplicate names the identifier the operator chose; the others
are worded from their key alone.
"""

from __future__ import annotations

from typing import Final, Literal

from ...core.external_constants import OutputLanguage
from ..operations.error_detail import operation_catalogue_refusal_words
from .registered_contracts import BienesInversionRefusalReason

_VALIDATION_KEY: Final = "application.bienes_inversion.served.validation"
_DUPLICATE_KEY: Final = "application.bienes_inversion.served.duplicate_identifier"
_DISPOSAL_KEYS: Final[dict[str, str]] = {
    "year": "application.bienes_inversion.served.disposal_year_missing",
    "regime": "application.bienes_inversion.served.disposal_regime_missing",
}


def served_refusal_words(
    reason: BienesInversionRefusalReason,
    *,
    error_code: str,
    missing: Literal["year", "regime"] | None = None,
    identifier: str | None = None,
) -> tuple[str, OutputLanguage]:
    """The finished sentence for ``reason`` and the language the worker's catalogue rendered it in."""
    if reason == "disposal_incomplete" and missing is not None:
        return operation_catalogue_refusal_words(error_code, _DISPOSAL_KEYS[missing])
    if reason == "duplicate_identifier" and identifier is not None:
        return operation_catalogue_refusal_words(error_code, _DUPLICATE_KEY, {"identifier": identifier})
    return operation_catalogue_refusal_words(error_code, _VALIDATION_KEY)


__all__ = ["served_refusal_words"]
