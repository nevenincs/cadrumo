"""Scoped reset service for ``aeat config reset``.

Removes one or more pieces of operator-local state behind an explicit
``--yes`` confirmation gate and the CLI requires an explicit ``--scope``.
Four :class:`ConfigResetScope` values are supported and returned through the
typed :class:`ConfigResetReport`:

- ``PROFILE``: clears every operator profile pointer and deletes each
  persisted profile bucket.
- ``AUTH``: resolves the active target bucket and delegates all-provider
  cleanup to :func:`application.auth.reset_operator_auth`, which owns provider
  configuration, persisted sessions, acquisition locks, certificate-source
  registrations, canonical secure-storage secrets, and auth events.
- ``DATA``: quarantines undecryptable secure-object rows only. It
  does not delete readable ledger data; bucket-local ledger reset is
  owned by the ledger backend so finalized modelo protections can run.
- ``ALL``: enumerates live and tombstoned profiles in sorted order, invokes
  canonical all-provider auth reset for each target bucket before profile
  deletion, and then applies the DATA quarantine.

The service runs through public application authorities.
:func:`application.auth.reset_operator_auth` owns target-bucket auth cleanup,
profile removal goes through
:class:`~application.user_profile.UserProfileLifecycleRepository` plus
:func:`~application.user_profile.remove_profile_bucket_directory`, and DATA
reset delegates to
:func:`~application.diagnostics.quarantine_unreadable_secure_objects`
for a :class:`~application.diagnostics.SecureObjectIntegrityReport`.
:func:`~application.workflow.workflow_state_repository` enforces active-route
readiness without owning auth mutation. The service does not directly erase
readable ledger data.

Each scope writes one log line through the project's standard
:mod:`core.logging` channel so post-mortem analysis of an
operator's reset history is possible without an extra audit-only
backend. The function rejects calls without explicit confirmation and
raises :class:`ConfigResetUnconfirmedError` with a registered translated
message key.

See Also:
    :func:`~application.workflow._persistence.reset_workflow_state`
        Narrow ``aeat config repair reset-progress`` route that deletes the
        saved workflow-state envelope after producing a
        :class:`~application.workflow.WorkflowStateResetFingerprint`.
    :class:`~application.diagnostics.SecureObjectIntegrityReport`
        DATA-scope quarantine summary returned by the diagnostics pipeline.
    :mod:`application.repair_integrity`
        Policy registry for repair surfaces, including the metadata-only
        workflow-state reset plan.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG, resolve_active_bucket_id
from ..core.errors import AeatError
from ..core.logging import get_logger
from .auth import reset_operator_auth

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
    :class:`~core.errors.ErrorEnvelope` refusal catalogue.
    """


class ConfigResetReport(BaseModel):
    """Outcome of a scoped reset.

    Attributes:
        scope: The :class:`ConfigResetScope` that was applied.
        removed_profile_ids: Sorted tuple of profile UUIDs cleared from the
            profile lifecycle repository and then removed from their bucket
            directories. Empty when the scope did not touch profiles.
        removed_auth_session: Coarse success flag for auth-session cleanup. It
            does not establish that a persisted session existed.
        quarantined_namespace_count: Number of secure-object namespaces
            whose unreadable rows were archived to the quarantine table
            during the DATA reset via
            :class:`~application.diagnostics.SecureObjectIntegrityReport`.
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
    manifests via :func:`~application.workflow.list_profile_buckets`,
    delete each profile through
    :class:`~application.user_profile.UserProfileLifecycleRepository`, and
    then remove bucket directories after disposing cached SQL engines. AUTH
    resolves the active target bucket and delegates its all-provider cleanup to
    :func:`application.auth.reset_operator_auth`. ALL performs that canonical
    target-bucket auth reset before deleting each enumerated profile. DATA
    resets call
    :func:`~application.diagnostics.quarantine_unreadable_secure_objects`
    for unreadable secure-object rows only.
    This broad reset surface is separate from
    :func:`~application.workflow._persistence.reset_workflow_state`, which
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
    from .workflow import workflow_state_repository

    auth_target_bucket_id: str | None = None
    if scope is ConfigResetScope.AUTH:
        auth_target_bucket_id = resolve_active_bucket_id()
        if auth_target_bucket_id is None:
            reset_operator_auth(all_providers=True, target_bucket_id=None)

    workflow_state_repository().load()
    removed_profile_ids: tuple[str, ...] = ()
    removed_auth_session = False
    quarantined_namespace_count = 0
    profile_bucket_ids_to_remove: tuple[str, ...] = ()

    if scope in {ConfigResetScope.PROFILE, ConfigResetScope.ALL}:
        from .user_profile import UserProfileLifecycleRepository, profile_storage_session
        from .workflow import list_profile_buckets

        # Registered profiles are a filesystem-manifest scan, not a
        # persisted WorkflowState field. Each profile is identified by
        # its immutable UUID, which is also its bucket id and bucket
        # directory name.
        # A reset physically removes every bucket directory, tombstoned
        # ones included, so the scan must enumerate the full set.
        removed_profile_ids = tuple(sorted(list_profile_buckets(include_tombstoned=True)))
        profile_bucket_ids_to_remove = removed_profile_ids
        for profile_id in removed_profile_ids:
            with profile_storage_session(profile_id):
                if scope is ConfigResetScope.ALL:
                    reset_operator_auth(all_providers=True, target_bucket_id=profile_id)
                UserProfileLifecycleRepository(bucket_id=profile_id).delete(profile_id)
        _log.info("config reset PROFILE scope cleared %d profile(s)", len(removed_profile_ids))

    if scope is ConfigResetScope.AUTH:
        assert auth_target_bucket_id is not None
        reset_operator_auth(
            all_providers=True,
            target_bucket_id=auth_target_bucket_id,
        )
        removed_auth_session = True
        _log.info("config reset AUTH scope cleared session state")
    elif scope is ConfigResetScope.ALL:
        removed_auth_session = True
        _log.info(
            "config reset ALL scope cleared auth custody for %d profile(s)",
            len(removed_profile_ids),
        )

    if scope in {ConfigResetScope.DATA, ConfigResetScope.ALL}:
        report = quarantine_unreadable_secure_objects()
        quarantined_namespace_count = sum(1 for ns in report.namespaces if ns.unreadable > 0)
        _log.info(
            "config reset DATA scope quarantined %d unreadable rows across %d namespace(s)",
            report.unreadable_total,
            quarantined_namespace_count,
        )

    if profile_bucket_ids_to_remove:
        from .user_profile import remove_profile_bucket_directory

        for profile_id in profile_bucket_ids_to_remove:
            # The bucket manifest is the existence claim; removing the
            # directory clears the profile from the manifest scan.
            # ``remove_profile_bucket_directory`` disposes that bucket's
            # engine first, releasing the SQLite file handle that would
            # otherwise block the rename on Windows.
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
