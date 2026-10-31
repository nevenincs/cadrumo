"""Restore a request's records at the operation boundary, so a broken fact is a worded refusal, not a decode failure."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import ValidationError

from ...domain.renta.actividad_asset.errors import ActividadAssetError, ActividadAssetValidationError

REQUEST_RECORD_INVALID_KEY = "ledger.actividad_asset.errors.request_record_invalid"
"""The reason for a record whose fault no rule words: the field it concerns is its only fact."""


def registered_refusal(error: ValidationError) -> ActividadAssetError:
    """Name the registered refusal a record validation failed with.

    A cross-field rule raises a registered refusal with its reason key and facts, and the validation
    boundary carries it as the cause of the failure it reports. Any other fault is worded by
    ``request_record_invalid`` with the field it concerns.
    """
    for item in error.errors():
        raised = (item.get("ctx") or {}).get("error")
        cause = getattr(raised, "__cause__", None)
        if isinstance(cause, ActividadAssetError):
            return cause
    first = next(iter(error.errors()), None)
    field = "" if first is None else ".".join(str(part) for part in first["loc"])
    return ActividadAssetValidationError(context={"field": field}, translated_message=REQUEST_RECORD_INVALID_KEY)


def restoring[ResultT](build: Callable[[], ResultT]) -> ResultT:
    """Run a record restoration and raise a record's failure as the registered refusal it carries."""
    try:
        return build()
    except ValidationError as error:
        raise registered_refusal(error) from error


__all__ = ["REQUEST_RECORD_INVALID_KEY", "registered_refusal", "restoring"]
