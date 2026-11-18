"""A sign-in refusal that is logged with its cause and served with the reference of its log line."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from cadrumo.core.logging import get_logger

from ..providers.application.contracts import ProviderSettingsRefusalCode, ServiceCause, ServiceRefusalCode

if TYPE_CHECKING:
    from .auth_attempt import AuthAttempt

_LOGGER = get_logger(__name__)


def new_log_ref() -> str:
    """One reference that appears in the log line of a failure and in what is served for it.

    A whole UUID, because the log scrubber leaves UUIDs intact but pseudonymises some shorter hex words, which
    would make the served reference absent from its own log line.
    """
    return str(uuid4())


def refuse(
    code: ServiceRefusalCode | ProviderSettingsRefusalCode,
    *,
    cause: ServiceCause,
    provider: str | None = None,
    error: BaseException | None = None,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Log a refusal at warning and serve it with its closed cause and log reference.

    ``base`` is an answer that already names the refusal and keeps its shape. Only
    the exception's class name is logged: its message can carry provider output.
    """
    log_ref = new_log_ref()
    _LOGGER.warning(
        "provider sign-in refused provider=%s code=%s cause=%s error_class=%s log_ref=%s",
        provider or "none",
        code,
        cause,
        "none" if error is None else type(error).__name__,
        log_ref,
    )
    served = {"kind": "refused", "code": str(code)} if base is None else base
    return {**served, "cause": cause, "log_ref": log_ref}


def log_settlement(
    logger: logging.Logger,
    lane: str,
    outcome: str,
    reason: str | None,
    cause: str | None,
    status_cause: object,
    *,
    cleanup_confirmed: bool,
    exit_status: int | None,
    stderr_bytes: int,
    errors: Sequence[str],
    log_ref: str,
    reached: str,
    reached_after: float,
    lasted: float,
) -> None:
    """One line per settled attempt on the attempt's own logger, at warning when it failed; no helper output.

    ``reached`` is the last step the attempt stood at before it settled, ``reached_after`` the seconds from
    its start to that step and ``lasted`` its whole life, so an attempt that ended unfinished says whether
    it ever offered the browser.
    """
    logger.log(
        logging.WARNING if outcome == "failed" else logging.INFO,
        "provider sign-in settled provider=%s event=%s reason=%s cause=%s status_cause=%s "
        "cleanup_confirmed=%s helper_exit_status=%s helper_stderr_bytes=%d errors=%s "
        "reached=%s reached_after_s=%.1f lasted_s=%.1f log_ref=%s",
        lane,
        outcome,
        reason or "none",
        cause or "none",
        status_cause or "none",
        cleanup_confirmed,
        "none" if exit_status is None else exit_status,
        stderr_bytes,
        ",".join(errors) or "none",
        reached,
        reached_after,
        lasted,
        log_ref,
    )


def sign_in_in_flight(attempt: AuthAttempt | None, abandoned: list[AuthAttempt]) -> tuple[bool, AuthAttempt | None]:
    """Whether a live sign-in blocks a new one, and the attempt still held.

    An ended attempt whose cleanup is unconfirmed has its cleanup tried once
    more. If that still fails it is abandoned, logged, and kept only so that
    closing the service retries it, so a person can always start again.
    """
    if attempt is None or not attempt.active:
        return False, attempt
    if not attempt.finished:
        return True, attempt
    try:
        attempt.close()
    except RuntimeError:
        refuse(ServiceRefusalCode.BUSY, cause="previous_cleanup_unconfirmed", provider=attempt.lane)
        abandoned.append(attempt)
        return False, None
    return False, attempt
