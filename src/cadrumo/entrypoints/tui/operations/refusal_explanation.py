"""Operator-facing explanation of a settled operation refusal."""

from __future__ import annotations

from ....application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from ....core.errors.error_codes import declared_error_codes_by_qualname, resolve_error_message
from ....core.errors.hierarchy import RecordedRegisteredError
from ....core.i18n.render import tr


def public_refusal_explanation(code: str | None) -> str | None:
    """Return the registry's complete public explanation for a refusal code, when it declares one.

    A settled refusal persists only its registry code, never the exception's
    context, so only a code whose registered message is itself the public text
    can be explained; any other code stays a bare code.
    """
    if code is None:
        return None
    for error_code in declared_error_codes_by_qualname().values():
        if error_code.code == code and error_code.public_message_from_registry:
            return tr(error_code.message_key)
    return None


def operation_error_explanation(detail: OperationErrorDetailV1 | None) -> str | None:
    """Return the stopped executor's own localized message from its recorded public detail.

    Only a registered error has a message of its own; a record fault is an
    internal defect whose words are the generic failure the modal already shows.
    """
    if detail is None or detail.kind is not OperationErrorDetailKind.REGISTERED_ERROR or detail.error_code is None:
        return None
    error = RecordedRegisteredError(
        detail.error_code, context=detail.context_mapping(), translated_message=detail.message_key
    )
    return resolve_error_message(error)


__all__ = ["operation_error_explanation", "public_refusal_explanation"]
