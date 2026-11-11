"""Notices naming payer facts a profile schema migration cleared.

A migration that drops a stored default must never read as a new obligation
appearing from nothing, so each cleared fact is named together with the exact
flags that answer it, and the typed action on the notice resolves to the
profile edit verb that carries them. The notice is delivered once by the
invocation that ran the migration, and again by explain and the calendar for
as long as the fact stays unanswered.

A yes/no fact is answered by one of two flags and a select by one flag and a
value, so the two carry different wording: naming ``--no-fiscal-residency``
would send the operator to a flag the command does not have.

A migration also retires the year-keyed art. 23.2 reduction tier. That is no payer
fact and has no flag: the notice asks the operator to record the leases, whose
facts decide the tier, and stays until one is recorded.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from ..application.operator_actions.catalogue import next_action
from ..application.user_profile.profile_schema_migration import drain_migration_cleared_paths
from ..core.i18n.render import tr
from ..core.json_contract import Notice, NoticeSeverity
from ..domain.user_profile.schema_migration import RETIRED_RENTAL_TIER_PATH

if TYPE_CHECKING:
    from ..application.wizard.models import WizardQuestion
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..domain.user_profile.values import UserProfileRecord

NOTICE_CODE = "config.profile.payer_fact_cleared"
_PROFILE_EDIT_ACTION_ID = "operator.profile.edit"
_CLEARED_BOOL_LOCALE_KEY = "cli.config.profile.notices.payer_fact_cleared"
_CLEARED_SELECT_LOCALE_KEY = "cli.config.profile.notices.payer_fact_cleared_select"
RENTAL_TIER_NOTICE_CODE = "config.profile.rental_tier_cleared"
_RENTAL_TIER_ACTION_ID = "operator.profile.arrendamiento"
_RENTAL_TIER_LOCALE_KEY = "cli.config.profile.notices.rental_tier_cleared"
_RENTAL_TIER_MODELO = "100"


def rental_tier_cleared_notice() -> Notice:
    """Return the finding that asks the operator to record the leases a cleared tier stood for."""
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=RENTAL_TIER_NOTICE_CODE,
        message=tr(_RENTAL_TIER_LOCALE_KEY),
        action=next_action(_RENTAL_TIER_ACTION_ID),
        context={"path": RETIRED_RENTAL_TIER_PATH},
    )


def _edit_question_by_path(operation: PinnedAuthorityOperation) -> dict[str, WizardQuestion]:
    """Map each setup-flow profile path to the question whose CLI flag answers it."""
    from ..application.wizard.catalogue import build_setup_flow

    flow = build_setup_flow(operation)
    return {
        question.profile_key: question
        for section in flow.sections
        for question in section.questions
        if question.profile_key is not None
    }


def _cleared_fact_message(question: WizardQuestion, *, fact: str) -> str:
    """Render the notice naming the flags that answer one cleared fact."""
    from ..application.wizard.models import WizardWidget

    flag = f"--{question.id}"
    if question.widget is WizardWidget.CONFIRM:
        return tr(_CLEARED_BOOL_LOCALE_KEY, fact=fact, yes_flag=flag, no_flag=f"--no-{question.id}")
    return tr(_CLEARED_SELECT_LOCALE_KEY, fact=fact, flag=flag)


def payer_fact_cleared_notices(
    paths: Iterable[str],
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[Notice, ...]:
    """Return one localized notice per cleared payer-fact path."""
    from ..domain.user_profile.labels import profile_field_label

    questions = _edit_question_by_path(operation)
    schema = operation.profile_decode_context().schema
    notices: list[Notice] = []
    for path in sorted(set(paths)):
        if path == RETIRED_RENTAL_TIER_PATH:
            notices.append(rental_tier_cleared_notice())
            continue
        question = questions[path]
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=NOTICE_CODE,
                message=_cleared_fact_message(
                    question,
                    fact=profile_field_label(path.split(".", 1)[0], schema.field(path)),
                ),
                action=next_action(_PROFILE_EDIT_ACTION_ID),
                context={"path": path, "flag": f"--{question.id}"},
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


def payer_fact_gated_modelos(path: str, *, operation: PinnedAuthorityOperation) -> frozenset[str]:
    """Return the modelos whose payer-fact gate reads the profile field at ``path``.

    A rule gates its modelo through the fact it requires and equally through
    the fact an exclusion reads: the Art. 109 RIRPF coverage fact excludes
    Modelo 130 rather than requiring it, and a cleared answer has to be asked
    again on that modelo too. ``gating_payer_facts`` is the rule's own
    enumeration of both, so this notice and the explain payload name the same
    facts.
    """
    from ..domain.calculations.registry.applicability import iter_modelo_applicability_rules
    from ..domain.calculations.registry.applicability_payer_facts import payer_fact_profile_keys

    schema = operation.profile_decode_context().schema
    return frozenset(
        str(rule.modelo)
        for rule in iter_modelo_applicability_rules()
        for fact in rule.gating_payer_facts
        if any(schema.path_for_model_selector(key) == path for key in payer_fact_profile_keys(fact))
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
        paths = tuple(path for path in paths if modelo in payer_fact_gated_modelos(path, operation=operation))
    notices = payer_fact_cleared_notices(paths, operation=operation)
    if modelo in (None, _RENTAL_TIER_MODELO) and repository.rental_tier_finding_pending(record.profile_id):
        notices = (*notices, rental_tier_cleared_notice())
    return notices


__all__ = [
    "NOTICE_CODE",
    "RENTAL_TIER_NOTICE_CODE",
    "drain_payer_fact_migration_notices",
    "payer_fact_cleared_notices",
    "payer_fact_gated_modelos",
    "pending_payer_fact_notices",
    "rental_tier_cleared_notice",
]
