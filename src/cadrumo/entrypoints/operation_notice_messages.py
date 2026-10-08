"""Localized operator prompts for the operation notices every frontend renders.

An operation notice crosses the frontend contract as a stable notice code plus
an optional typed display code, never as runtime free text. Each frontend
renders the same localized prompt for it, so the CLI's stderr line and the
TUI's operation modal cannot drift apart.
"""

from __future__ import annotations

from ..core.i18n.render import tr
from ..core.operator_progress import OperatorDisplayCode

# Notices a frontend prompts the operator for, by the executor's stable notice
# code. A code absent here (``operation.started``, or one a newer runtime
# adds) has no prompt.
_OPERATION_NOTICE_LOCALE_KEYS: dict[str, str] = {
    "auth.clave-movil.approval-pending": "operation.notice.clave_movil_approval_pending",
    "auth.clave-movil.qr-scan-pending": "operation.notice.clave_movil_qr_scan_pending",
}
_OPERATION_NOTICE_DISPLAY_CODE_LOCALE_KEYS: dict[str, str] = {
    "auth.clave-movil.approval-pending": "operation.notice.clave_movil_approval_pending_with_code",
    "auth.clave-movil.qr-scan-pending": "operation.notice.clave_movil_qr_scan_pending_with_code",
}


def operation_notice_message(notice_code: str, display_code: OperatorDisplayCode | None) -> str | None:
    """Return the localized prompt for one notice, or ``None`` when no prompt is defined for its code."""
    if display_code is not None:
        code_message_key = _OPERATION_NOTICE_DISPLAY_CODE_LOCALE_KEYS.get(notice_code)
        if code_message_key is not None:
            return tr(code_message_key, code=display_code)
    message_key = _OPERATION_NOTICE_LOCALE_KEYS.get(notice_code)
    return None if message_key is None else tr(message_key)


__all__ = ["operation_notice_message"]
