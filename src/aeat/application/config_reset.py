"""Scoped reset service for ``aeat config reset``.

Removes one or more pieces of operator-local state behind an explicit
``--yes`` confirmation gate and the CLI requires an explicit ``--scope``.
Four :class:`ConfigResetScope` values are supported and returned through the
typed :class:`ConfigResetReport`:

- ``PROFILE``: clears every operator profile pointer and deletes each
  persisted profile bucket.
- ``AUTH``: clears the persisted auth session and provider metadata.
- ``DATA``: quarantines undecryptable secure-object rows only. It
  does not delete readable ledger data; bucket-local ledger reset is
  owned by the ledger backend so finalized modelo protections can run.
- ``ALL``: combines the three scopes above.

The service runs through the normal runtime storage routes.
:class:`~aeat.application.workflow.WorkflowStateRepository` loads the typed
:class:`~aeat.application.workflow.WorkflowState`, profile removal goes
through :class:`~aeat.application.user_profile.UserProfileLifecycleRepository`
plus :func:`~aeat.application.user_profile.remove_profile_bucket_directory`,
and DATA reset delegates to
:func:`~aeat.application.diagnostics.quarantine_unreadable_secure_objects`
for a :class:`~aeat.application.diagnostics.SecureObjectIntegrityReport`.
It does not bypass runtime readiness or directly erase readable ledger data.

Each scope writes one log line through the project's standard
:mod:`aeat.core.logging` channel so post-mortem analysis of an
operator's reset history is possible without an extra audit-only
backend. The function rejects calls without explicit confirmation and
raises :class:`ConfigResetUnconfirmedError` with a registered translated
message key.

See Also:
    :func:`~aeat.application.workflow._persistence.reset_workflow_state`
        Narrow ``aeat config repair reset-progress`` route that deletes the
        saved workflow-state envelope after producing a
        :class:`~aeat.application.workflow.WorkflowStateResetFingerprint`.
    :class:`~aeat.application.diagnostics.SecureObjectIntegrityReport`
        DATA-scope quarantine summary returned by the diagnostics pipeline.
    :mod:`aeat.application.repair_integrity`
        Policy registry for repair surfaces, including the metadata-only
        workflow-state reset plan.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG
from ..core.errors import AeatError
from ..core.logging import get_logger

_log = get_logger(__name__)


class ConfigResetScope(StrEnum):
    """Closed catalogue of operator-driven reset scopes.

    The enum is the shared application/CLI contract: CLI tokens are parsed
    by :func:`parse_config_reset_scope` from
    :data:`CONFIG_RESET_SCOPE_CLI_VALUES` before :func:`reset_config` runs, and
    :class:`ConfigResetReport` echoes the applied scope.
    """

    PROFILE = "PROFILE"
    AUTH = "AUTH"
    DATA = "DATA"
    ALL = "ALL"


CONFIG_RESET_SCOPE_CLI_VALUES: tuple[str, ...] = tuple(scope.value.lower() for scope in ConfigResetScope)
"""Lowercase :class:`ConfigResetScope` tokens accepted by ``aeat config reset --scope``."""


def parse_config_reset_scope(raw: str) -> ConfigResetScope:
    """Parse a CLI reset-scope token into the :class:`ConfigResetScope` member.

    The CLI renders :data:`CONFIG_RESET_SCOPE_CLI_VALUES` as the accepted token
    set, then delegates normalization here before calling :func:`reset_config`.
    """
    return ConfigResetScope(raw.strip().upper())


class ConfigResetUnconfirmedError(AeatError):
    """Raised when :func:`reset_config` is called without ``confirmed=True``.

    The error carries ``errors.refused.refused_config_reset_unconfirmed`` and
    the refused :class:`ConfigResetScope` value in structured context so the
    CLI/error envelope renders through the registered
    :class:`~aeat.core.errors.ErrorEnvelope` refusal catalogue.
    """


class ConfigResetReport(BaseModel):
    """Outcome of a scoped reset.

    Attributes:
        scope: The :class:`ConfigResetScope` that was applied.
        removed_profile_ids: Sorted tuple of profile UUIDs cleared from the
            profile lifecycle repository and then removed from their bucket
            directories. Empty when the scope did not touch profiles.
        removed_auth_session: True when the auth session was reset.
        quarantined_namespace_count: Number of secure-object namespaces
            whose unreadable rows were archived to the quarantine table
            during the DATA reset via
            :class:`~aeat.application.diagnostics.SecureObjectIntegrityReport`.
    """

    model_config = STRICT_FROZEN_CONFIG

    scope: ConfigResetScope
    removed_profile_ids: tuple[str, ...] = Field(default=())
    removed_auth_session: bool = False
    quarantined_namespace_count: int = Field(default=0, ge=0)


def reset_config(scope: ConfigResetScope, *, confirmed: bool) -> ConfigResetReport:
    """Apply the scoped reset and return a :class:`ConfigResetReport`.

    The operation is destructive and therefore refuses unless
    ``confirmed=True``. Confirmed PROFILE / ALL resets enumerate profile
    manifests via :func:`~aeat.application.workflow.list_profile_buckets`,
    delete each profile through
    :class:`~aeat.application.user_profile.UserProfileLifecycleRepository`, and
    then remove bucket directories after disposing cached SQL engines. AUTH
    resets replace auth state inside
    :class:`~aeat.application.workflow.WorkflowState`. DATA resets call
    :func:`~aeat.application.diagnostics.quarantine_unreadable_secure_objects`
    for unreadable secure-object rows only.
    This broad reset surface is separate from
    :func:`~aeat.application.workflow._persistence.reset_workflow_state`, which
    only clears the workflow-state envelope for
    ``aeat config repair reset-progress``.

    Args:
        scope: The :class:`ConfigResetScope` to apply.
        confirmed: Explicit ``--yes`` flag from the CLI surface. The
            function refuses without it.

    Returns:
        A :class:`ConfigResetReport` summarising what was cleared.

    Raises:
        :class:`ConfigResetUnconfirmedError`: When ``confirmed`` is ``False``.
    """
    if not confirmed:
        raise ConfigResetUnconfirmedError(
            translated_message="errors.refused.refused_config_reset_unconfirmed",
            context={"scope": scope.value},
        )

    from .diagnostics import quarantine_unreadable_secure_objects
    from .workflow._models import AuthState
    from .workflow._persistence import workflow_state_repository
    from .workflow._utils import utc_now

    repository = workflow_state_repository()
    current = repository.load()
    new_state = current
    removed_profile_ids: tuple[str, ...] = ()
    removed_auth_session = False
    quarantined_namespace_count = 0
    profile_bucket_ids_to_remove: tuple[str, ...] = ()

    if scope in {ConfigResetScope.PROFILE, ConfigResetScope.ALL}:
        from .user_profile import UserProfileLifecycleRepository
        from .workflow._profile_bucket_scan import list_profile_buckets

        # Registered profiles are a filesystem-manifest scan, not a
        # persisted WorkflowState field. Each profile is identified by
        # its immutable UUID, which is also its bucket id and bucket
        # directory name.
        # A reset physically removes every bucket directory, tombstoned
        # ones included, so the scan must enumerate the full set.
        removed_profile_ids = tuple(sorted(list_profile_buckets(include_tombstoned=True)))
        profile_bucket_ids_to_remove = removed_profile_ids
        for profile_id in removed_profile_ids:
            UserProfileLifecycleRepository(bucket_id=profile_id).delete(profile_id)
        new_state = new_state.model_copy(
            update={
                "declarations": {},
                "invoice_reviews": {},
                "ledger_reviews": {},
                "updated_at": utc_now(),
            },
        )
        _log.info("config reset PROFILE scope cleared %d profile(s)", len(removed_profile_ids))

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

    if profile_bucket_ids_to_remove:
        from ..adapters.persistence.storage.sql import dispose_engine
        from .user_profile._orchestration import remove_profile_bucket_directory

        for profile_id in profile_bucket_ids_to_remove:
            # Dispose the cached per-bucket engine so its SQLite file
            # handle is released before the directory is removed; an
            # open handle blocks the rename on Windows.
            dispose_engine()
            # The bucket manifest is the existence claim; removing the
            # directory clears the profile from the manifest scan.
            remove_profile_bucket_directory(profile_id)

    return ConfigResetReport(
        scope=scope,
        removed_profile_ids=removed_profile_ids,
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
