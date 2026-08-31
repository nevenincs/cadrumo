"""Invocation-scoped delivery of profile-authentication diagnostics."""

from __future__ import annotations

from contextvars import ContextVar

from ...core.json_contract import Notice, NoticeSeverity

_SESSION_NOT_PERSISTED: ContextVar[bool] = ContextVar("cadrumo_profile_session_not_persisted", default=False)


def stage_profile_session_not_persisted_notice() -> None:
    """Remember that this invocation authenticated without durable acceleration."""
    _SESSION_NOT_PERSISTED.set(True)


def drain_profile_authentication_notices() -> tuple[Notice, ...]:
    """Return and clear pending root-authentication notices exactly once."""
    if not _SESSION_NOT_PERSISTED.get():
        return ()
    _SESSION_NOT_PERSISTED.set(False)
    from ...core.i18n._render import tr

    return (
        Notice(
            severity=NoticeSeverity.WARNING,
            code="config.login.session_not_persisted",
            message=tr("cli.config.login.notices.session_not_persisted"),
        ),
    )


__all__ = [
    "drain_profile_authentication_notices",
    "stage_profile_session_not_persisted_notice",
]
