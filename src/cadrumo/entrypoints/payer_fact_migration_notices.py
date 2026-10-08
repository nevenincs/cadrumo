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
from typing import TYPE_CHECKING

from ..application.operator_actions.catalogue import next_action
from ..application.user_profile.profile_schema_migration import drain_migration_cleared_paths
from ..core.i18n.render import tr
from ..core.json_contract import Notice, NoticeSeverity

if TYPE_CHECKING:
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..domain.user_profile.values import UserProfileRecord

NOTICE_CODE = "config.profile.payer_fact_cleared"
_PROFILE_EDIT_ACTION_ID = "operator.profile.edit"


def _edit_flag_by_path(operation: PinnedAuthorityOperation) -> dict[str, str]:
    """Map each setup-flow profile path to the question id its CLI flag carries."""
    from ..application.wizard.catalogue import build_setup_flow

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
    from ..domain.user_profile.labels import profile_field_label

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
                action=next_action(_PROFILE_EDIT_ACTION_ID),
                context={"path": path, "flag": f"--{flag}"},
            ),
        )
    return tuple(notices)


def drain_payer_fact_migration_notices() -> tuple[Notice, ...]:
    """Return the notices for a migration this invocation ran, exactly once."""
    paths = drain_migration_cleared_paths()
    if not paths:
        return ()
    from ..domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        return payer_fact_cleared_notices(paths, operation=operation)


def _gated_modelos(path: str, *, operation: PinnedAuthorityOperation) -> frozenset[str]:
    """Return the modelos whose payer-fact gate reads the profile field at ``path``."""
    from ..domain.calculations.registry.applicability import iter_modelo_applicability_rules
    from ..domain.calculations.registry.applicability_payer_facts import payer_fact_profile_keys

    schema = operation.profile_decode_context().schema
    return frozenset(
        str(rule.modelo)
        for rule in iter_modelo_applicability_rules()
        if rule.required_payer_fact is not None
        and any(
            schema.path_for_model_selector(key) == path for key in payer_fact_profile_keys(rule.required_payer_fact)
        )
    )


def pending_payer_fact_notices(
    record: UserProfileRecord | None,
    *,
    operation: PinnedAuthorityOperation,
    modelo: str | None = None,
) -> tuple[Notice, ...]:
    """Return notices for cleared payer facts the active record has not answered again.

    With ``modelo`` the notices are limited to facts that gate that modelo.

    Core types:
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """
    if record is None:
        return ()
    from ..application.user_profile.profile_record_repository import ProfileRecordRepository

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
