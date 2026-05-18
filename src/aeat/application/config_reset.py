"""Scoped config reset for ``aeat config reset``.

Removes one or more pieces of operator-local state behind an explicit
``--yes`` confirmation gate. Four scopes are supported:

- ``PROFILE``: clears every operator profile pointer and deletes each
  persisted profile bucket.
- ``AUTH``: clears the persisted auth session and provider metadata.
- ``DATA``: quarantines undecryptable secure-object rows only. It
  does not delete readable ledger data; bucket-local ledger reset is
  owned by the ledger backend so finalized modelo protections can run.
- ``ALL``: combines the three scopes above.

Each scope writes one log line through the project's standard
:mod:`aeat.core.logging` channel so post-mortem analysis of an
operator's reset history is possible without an extra audit-only
backend. The function rejects calls without explicit confirmation;
the CLI wrapper requires ``--yes`` before the confirmation gate
flips.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ..core.errors import AeatError
from ..core.logging import get_logger

_log = get_logger(__name__)


class ConfigResetScope(StrEnum):
    """Closed catalogue of operator-driven reset scopes."""

    PROFILE = "PROFILE"
    AUTH = "AUTH"
    DATA = "DATA"
    ALL = "ALL"


CONFIG_RESET_SCOPE_CLI_VALUES: tuple[str, ...] = tuple(scope.value.lower() for scope in ConfigResetScope)
"""Lowercase scope tokens accepted by ``aeat config reset --scope``."""


def parse_config_reset_scope(raw: str) -> ConfigResetScope:
    """Parse a CLI reset-scope token into the backend enum."""

    return ConfigResetScope(raw.strip().upper())


class ConfigResetUnconfirmedError(AeatError):
    """Raised when :func:`reset_config` is called without ``confirmed=True``."""


class ConfigResetReport(BaseModel):
    """Outcome of a scoped reset.

    Attributes:
        scope: The :class:`ConfigResetScope` that was applied.
        removed_profile_names: Sorted tuple of profile names cleared
            from the workflow state and profile bucket repository.
            Empty when the scope did not touch profiles.
        removed_auth_session: True when the auth session was reset.
        quarantined_namespace_count: Number of secure-object namespaces
            whose unreadable rows were archived to the quarantine table
            during the reset.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    scope: ConfigResetScope
    removed_profile_names: tuple[str, ...] = Field(default=())
    removed_auth_session: bool = False
    quarantined_namespace_count: int = Field(default=0, ge=0)


def reset_config(scope: ConfigResetScope, *, confirmed: bool) -> ConfigResetReport:
    """Apply the scoped reset; raise unless ``confirmed=True``.

    Args:
        scope: The :class:`ConfigResetScope` to apply.
        confirmed: Explicit ``--yes`` flag from the CLI surface. The
            function refuses without it.

    Returns:
        A :class:`ConfigResetReport` summarising what was cleared.
    """

    if not confirmed:
        raise ConfigResetUnconfirmedError("config reset refused: confirmed must be True (run with --yes from the CLI)")

    from .diagnostics import quarantine_unreadable_secure_objects
    from .workflow._models import AuthState
    from .workflow._persistence import workflow_state_repository
    from .workflow._utils import utc_now

    repository = workflow_state_repository()
    current = repository.load()
    new_state = current
    removed_profile_names: tuple[str, ...] = ()
    removed_auth_session = False
    quarantined_namespace_count = 0

    if scope in {ConfigResetScope.PROFILE, ConfigResetScope.ALL}:
        from .user_profile import UserProfileLifecycleRepository

        profile_targets = tuple(
            sorted((profile_id, pointer.bucket_id) for profile_id, pointer in current.profiles.items())
        )
        removed_profile_names = tuple(profile_id for profile_id, _bucket_id in profile_targets)
        for profile_id, bucket_id in profile_targets:
            UserProfileLifecycleRepository(bucket_id=bucket_id).delete(profile_id)
        new_state = new_state.model_copy(
            update={
                "profiles": {},
                "declarations": {},
                "invoice_reviews": {},
                "ledger_reviews": {},
                "updated_at": utc_now(),
            }
        )
        _log.info("config reset PROFILE scope cleared %d profile(s)", len(removed_profile_names))

    if scope in {ConfigResetScope.AUTH, ConfigResetScope.ALL}:
        new_state = new_state.model_copy(update={"auth": AuthState(), "updated_at": utc_now()})
        removed_auth_session = True
        _log.info("config reset AUTH scope cleared session state")

    repository.update(lambda _state: new_state)

    if scope in {ConfigResetScope.DATA, ConfigResetScope.ALL}:
        report = quarantine_unreadable_secure_objects()
        quarantined_namespace_count = sum(1 for ns in report.namespaces if ns.unreadable > 0)
        _log.info(
            "config reset DATA scope quarantined %d unreadable rows across %d namespace(s)",
            report.unreadable_total,
            quarantined_namespace_count,
        )

    return ConfigResetReport(
        scope=scope,
        removed_profile_names=removed_profile_names,
        removed_auth_session=removed_auth_session,
        quarantined_namespace_count=quarantined_namespace_count,
    )


__all__ = [
    "CONFIG_RESET_SCOPE_CLI_VALUES",
    "ConfigResetReport",
    "ConfigResetScope",
    "ConfigResetUnconfirmedError",
    "parse_config_reset_scope",
    "reset_config",
]
