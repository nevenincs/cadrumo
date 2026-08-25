"""The one sanctioned entry point for an operator-facing JSON success envelope.

:func:`emit_operator_json_success` is the SOLE function outside
:mod:`core.json_contract` itself that may call
:func:`~cadrumo.core.json_contract.emit_json_success` directly for an
operator-facing command result. Every JSON-emitting command surface —
the CLI transport's :func:`~cadrumo.entrypoints.cli._common.emit_envelope`
and the setup wizard's success/save-exit emitters — routes through this
function so the sandbox-active indicator cannot be dropped by a caller that
forgets to ask for it: there is no other way to reach
:class:`~cadrumo.core.json_contract.SchemaEnvelope` for a routine command
result. The CLI transport's metadata-only fast path (``--help`` /
``--version``) is the one documented exception, justified and enforced by
the widened ``test_json_schema_conformance.py::test_no_bare_emit_json_success_call``
gate.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...core.json_contract import Notice, validate_registered_result
from ._sandbox_notice import sandbox_notice_for_active_bucket

__all__ = ["emit_operator_json_success"]


def emit_operator_json_success(
    command: str,
    result: object,
    *,
    notices: Sequence[Notice] = (),
    active_profile: str | None = None,
) -> None:
    """Emit ``result`` through :class:`SchemaEnvelope`, prepending the sandbox notice.

    Resolves :func:`sandbox_notice_for_active_bucket` and, when the active
    profile bucket is a sandbox, prepends the persistent info
    :class:`Notice` ahead of ``notices`` before delegating to
    :func:`~cadrumo.core.json_contract.emit_json_success`. Callers must never
    pre-add the sandbox notice themselves — this function is the single
    place that decides whether it belongs on the envelope.

    Args:
        command: Stable command-spec result identity for ``result``'s type.
        result: The strict-validated, registered
            :class:`~cadrumo.core.json_contract.OutputSchema` payload.
        notices: Caller-supplied notices, excluding the sandbox indicator.
        active_profile: Optional active-profile display label for the
            envelope spine.
    """
    from ...core.json_contract import emit_json_success

    validated_result = validate_registered_result(command, result)
    sandbox_notice = sandbox_notice_for_active_bucket()
    resolved_notices: tuple[Notice, ...] = (sandbox_notice, *notices) if sandbox_notice is not None else tuple(notices)
    emit_json_success(command, validated_result, notices=resolved_notices, active_profile=active_profile)
