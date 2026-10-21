"""Root-cause chains for failures that cross a process or operator boundary.

A boundary that turns an exception into a registered public refusal keeps its
code and translated message stable, and records here what the public shape
cannot carry: each exception in the chain, the first-party frame that raised
it, its registered code and its registered reason. Every record and the
operator envelope share one correlation id stored on the error itself, so a
console document and its log record can be joined.

Only identifiers leave this module: qualified type names, ``module:function:line``
frames, registered codes, translation keys, refusal codes and check names. An
exception's free text is never rendered, with one exception: an
:class:`~cadrumo.core.errors.hierarchy.InternalInvariantError`'s developer-authored
invariant, which is logged after redaction and never reaches the console.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Final
from uuid import uuid4

from .hierarchy import CadrumoError, InternalInvariantError

FIRST_PARTY_MODULE_ROOTS: Final[tuple[str, ...]] = (
    "cadrumo",
    "cadrumo_client",
    "cadrumo_runtime",
    "cadrumo_agent_service",
    "cadrumo_harness",
)
_MAX_LINKS: Final = 16
_MAX_INVARIANT_TEXT: Final = 240
_TRACE_ATTRIBUTE: Final = "_cadrumo_failure_trace_id"
_REASON_PATTERN: Final = re.compile(r"[A-Za-z0-9_.:-]{1,160}")
_CHAIN_SEPARATOR: Final = " <- "


@dataclass(frozen=True, slots=True)
class FailureLink:
    """One exception of a failure chain, described only by identifiers."""

    exception_type: str
    raised_at: str | None
    code: str | None
    reason: str | None

    def render(self) -> str:
        """Render this link as one compact, identifier-only token."""
        qualifiers = [part for part in (self.code, self.reason) if part is not None]
        rendered = self.exception_type
        if qualifiers:
            rendered += f"[{' '.join(qualifiers)}]"
        if self.raised_at is not None:
            rendered += f"@{self.raised_at}"
        return rendered


def _is_first_party(module: object) -> bool:
    return isinstance(module, str) and any(
        module == root or module.startswith(f"{root}.") for root in FIRST_PARTY_MODULE_ROOTS
    )


def raising_product_frame(error: BaseException) -> str | None:
    """Return the deepest first-party ``module:function:line`` in ``error``'s own traceback."""
    located: str | None = None
    trace = error.__traceback__
    while trace is not None:
        module = trace.tb_frame.f_globals.get("__name__", "")
        if _is_first_party(module):
            located = f"{module}:{trace.tb_frame.f_code.co_name}:{trace.tb_lineno}"
        trace = trace.tb_next
    return located


def _qualified_type(error: BaseException) -> str:
    error_type = type(error)
    module = error_type.__module__
    return error_type.__qualname__ if module == "builtins" else f"{module}.{error_type.__qualname__}"


def _identifier(value: object) -> str | None:
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, str) and _REASON_PATTERN.fullmatch(value):
        return value
    return None


def failure_reason(error: BaseException) -> str | None:
    """Return the registered, identifier-shaped reason ``error`` carries, if any.

    A named check wins over a refusal code, which wins over a translation key;
    free text never qualifies.
    """
    for candidate in (getattr(error, "check", None), getattr(error, "reason", None)):
        reason = _identifier(candidate)
        if reason is not None:
            return reason
    if isinstance(error, CadrumoError):
        reason = _identifier(error.translated_message)
        if reason is not None:
            return reason
        context = error.context
        if isinstance(context, Mapping):
            return _identifier(context.get("reason"))
    return None


def _registered_code(error: BaseException) -> str | None:
    if not isinstance(error, CadrumoError):
        return None
    try:
        from .error_codes import get_registered_error_code

        return get_registered_error_code(error).code
    except Exception:
        return None


def _next_in_chain(error: BaseException) -> BaseException | None:
    wrapped = getattr(error, "original_exception", None)
    if isinstance(wrapped, BaseException):
        return wrapped
    if error.__cause__ is not None:
        return error.__cause__
    if error.__suppress_context__:
        return None
    return error.__context__


def _chain(error: BaseException) -> tuple[BaseException, ...]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen and len(chain) < _MAX_LINKS:
        seen.add(id(current))
        chain.append(current)
        current = _next_in_chain(current)
    return tuple(chain)


def failure_chain(error: BaseException) -> tuple[FailureLink, ...]:
    """Describe ``error`` and every cause it wraps, outermost first and root last."""
    return tuple(
        FailureLink(
            exception_type=_qualified_type(link),
            raised_at=raising_product_frame(link),
            code=_registered_code(link),
            reason=failure_reason(link),
        )
        for link in _chain(error)
    )


def failure_trace_id(error: BaseException) -> str:
    """Return the correlation id of ``error``'s failure, minting it on first use.

    Any link that already carries an id lends it to the whole chain, so a
    wrapper rendered at the operator boundary reports the id its cause was
    logged under deeper in the process.
    """
    chain = _chain(error)
    identifier = next(
        (value for link in chain if isinstance(value := getattr(link, _TRACE_ATTRIBUTE, None), str)),
        None,
    )
    identifier = identifier or uuid4().hex
    for link in chain:
        try:
            setattr(link, _TRACE_ATTRIBUTE, identifier)
        except (AttributeError, TypeError):
            continue
    return identifier


def _invariant_text(chain: tuple[BaseException, ...]) -> str | None:
    for link in chain:
        if isinstance(link, InternalInvariantError) and link.args and isinstance(link.args[0], str):
            from ..redaction.rules import redact_for_log

            return redact_for_log(link.args[0])[:_MAX_INVARIANT_TEXT]
    return None


def root_cause_context(error: BaseException) -> dict[str, str]:
    """Return the console-safe root-cause summary for an envelope's ``context``.

    The keys match the ones the unexpected-boundary error already publishes,
    so native helper parents read one shape whatever the failure was.
    """
    links = failure_chain(error)
    root = links[-1]
    context = {"exception_type": root.exception_type, "trace_id": failure_trace_id(error)}
    if root.raised_at is not None:
        context["raised_at"] = root.raised_at
    if root.reason is not None and root.reason != links[0].reason:
        context["root_reason"] = root.reason
    if len(links) > 1:
        context["cause_chain"] = _CHAIN_SEPARATOR.join(link.exception_type.rpartition(".")[2] for link in links)
    return context


def log_boundary_failure(
    logger: logging.Logger,
    boundary: str,
    error: BaseException,
    *,
    level: int = logging.ERROR,
    operator_document: bool = False,
    durable: bool = False,
) -> str:
    """Log ``error``'s whole chain at ``boundary`` and return its correlation id.

    Never raises: a boundary is reporting a failure already, and a diagnostic
    problem must not replace it. ``operator_document`` keeps the record off
    stderr when the boundary writes its own document there. ``durable``
    configures the diagnostic sink first, for long-lived bridges whose
    records would otherwise wait for a configuration that never comes.
    """
    try:
        trace_id = failure_trace_id(error)
    except Exception:
        trace_id = uuid4().hex
    try:
        from ..logging import OPERATOR_DOCUMENT_LOG_EXTRA, configure_logging, logging_configuration_deferred

        if logging_configuration_deferred():
            # A deferred CLI must stay state-free; the placeholder holds the
            # record until configuration resumes instead of echoing it.
            level = logging.DEBUG
        elif durable:
            configure_logging()
        links = failure_chain(error)
        failure = links[0]
        extra: dict[str, object] = {
            "failure_boundary": boundary,
            "trace_id": trace_id,
            "error_type": failure.exception_type,
            "error_chain": _CHAIN_SEPARATOR.join(link.render() for link in links),
        }
        if failure.raised_at is not None:
            extra["error_origin"] = failure.raised_at
        if len(links) > 1:
            extra["root_cause"] = links[-1].render()
        code = next((link.code for link in links if link.code is not None), None)
        if code is not None:
            extra["error_code"] = code
        reason = next((link.reason for link in links if link.reason is not None), None)
        if reason is not None:
            extra["reason"] = reason
        invariant = _invariant_text(_chain(error))
        if invariant is not None:
            extra["invariant"] = invariant
        if operator_document:
            extra[OPERATOR_DOCUMENT_LOG_EXTRA] = True
        logger.log(
            level,
            "boundary failure at %s trace_id=%s chain: %s",
            boundary,
            trace_id,
            extra["error_chain"],
            extra=extra,
        )
    except Exception:
        return trace_id
    return trace_id


__all__ = [
    "FIRST_PARTY_MODULE_ROOTS",
    "FailureLink",
    "failure_chain",
    "failure_reason",
    "failure_trace_id",
    "log_boundary_failure",
    "raising_product_frame",
    "root_cause_context",
]
