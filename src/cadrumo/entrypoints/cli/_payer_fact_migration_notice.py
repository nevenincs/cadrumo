"""Notices naming payer facts a profile schema migration cleared.

A migration that drops a stored ``false`` must never read as a new obligation
appearing from nothing, so each cleared fact is named together with the exact
flags that answer it, and the notice's typed action resolves to the profile
edit verb that carries them. The notice is delivered once by the invocation
that ran the migration, and again by explain and the calendar for as long as
the fact stays unanswered.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...application.operator_actions.models import ActionReference
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.profile_schema_migration import drain_migration_cleared_paths
from ...application.wizard.catalogue import build_setup_flow
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.calculations.registry.applicability import iter_modelo_applicability_rules
from ...domain.calculations.registry.applicability_payer_facts import payer_fact_profile_keys
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.user_profile.labels import profile_field_label
from ...domain.user_profile.values import UserProfileRecord
from .common import resolve_notice_action

NOTICE_CODE = "config.profile.payer_fact_cleared"
_PROFILE_EDIT_ACTION_ID = "operator.profile.edit"


def _edit_flag_by_path(operation: PinnedAuthorityOperation) -> dict[str, str]:
    """Map each setup-flow profile path to the question id its CLI flag carries."""
    flow = build_setup_flow(operation)
    return {
        question.profile_key: question.id
        for section in flow.sections
        for question in section.questions
        if question.profile_key is not None
    }


def payer_fact_cleared_notices(
    paths: Iterable[str],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[Notice, ...]:
    """Return one localized notice per cleared payer-fact path."""
    flags = _edit_flag_by_path(operation)
    schema = operation.profile_decode_context().schema
    notices: list[Notice] = []
    for path in sorted(set(paths)):
        flag = flags[path]
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=NOTICE_CODE,
                message=tr(
                    "cli.config.profile.notices.payer_fact_cleared",
                    fact=profile_field_label(path.split(".", 1)[0], schema.field(path)),
                    yes_flag=f"--{flag}",
                    no_flag=f"--no-{flag}",
                ),
                action=resolve_notice_action(action=ActionReference(action_id=_PROFILE_EDIT_ACTION_ID)),
                context={"path": path, "flag": f"--{flag}"},
            ),
        )
    return tuple(notices)


def drain_payer_fact_migration_notices() -> tuple[Notice, ...]:
    """Return the notices for a migration this invocation ran, exactly once."""
    paths = drain_migration_cleared_paths()
    if not paths:
        return ()
    with bundled_indexed_authority().operation() as operation:
        return payer_fact_cleared_notices(paths, operation=operation)


def _gated_modelos(path: str, *, operation: PinnedAuthorityOperation) -> frozenset[str]:
    """Return the modelos whose payer-fact gate reads the profile field at ``path``."""
    schema = operation.profile_decode_context().schema
    return frozenset(
        str(rule.modelo)
        for rule in iter_modelo_applicability_rules()
        if rule.required_payer_fact is not None
        and any(
            schema.path_for_model_selector(key) == path for key in payer_fact_profile_keys(rule.required_payer_fact)
        )
    )


def pending_payer_fact_notices(record: UserProfileRecord | None, *, modelo: str | None = None) -> tuple[Notice, ...]:
    """Return notices for cleared payer facts the active record has not answered again.

    With ``modelo`` the notices are limited to facts that gate that modelo.
    """
    if record is None:
        return ()
    with bundled_indexed_authority().operation() as operation:
        repository = ProfileRecordRepository.for_current_session(
            record.profile_id,
            profile_decode_context=operation.profile_decode_context(),
        )
        paths = repository.pending_cleared_payer_fact_paths(record.profile_id)
        if modelo is not None:
            paths = tuple(path for path in paths if modelo in _gated_modelos(path, operation=operation))
        return payer_fact_cleared_notices(paths, operation=operation)


__all__ = [
    "NOTICE_CODE",
    "drain_payer_fact_migration_notices",
    "payer_fact_cleared_notices",
    "pending_payer_fact_notices",
]
