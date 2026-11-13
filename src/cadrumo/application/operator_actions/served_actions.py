"""The words and routing served for the recovery actions a precondition verdict offers.

A verdict names its recovery actions by catalogue identity alone. A frontend
that holds no action vocabulary cannot label or route them from that, so the
projection that carries a verdict across a process boundary serves, for the
primary action and each alternative, the action's words in the worker's
language and the registered operations its command submits; and for a verdict
with no way out, the sentence that says so. Producers never author these
fields. An action outside the catalogue, or a sentence the catalogue lacks, is
served as absent rather than as a key or an invented label.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation, tr
from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_surface.action_target_operations import target_operation_ids
from .catalogue import OPERATOR_ACTION_CATALOGUE
from .models import AlternativeRecoveryAction, PreconditionVerdict

ACTION_WORDS_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "operator.auth.configure": "application.operator_actions.served.action.auth_configure",
        "operator.auth.diagnostics.view": "application.operator_actions.served.action.auth_diagnostics_view",
        "operator.auth.login": "application.operator_actions.served.action.auth_login",
        "operator.diagnostics.repair": "application.operator_actions.served.action.diagnostics_repair",
        "operator.diagnostics.secure_objects.quarantine": (
            "application.operator_actions.served.action.diagnostics_secure_objects_quarantine"
        ),
        "operator.diagnostics.workflow.reset_progress": (
            "application.operator_actions.served.action.diagnostics_workflow_reset_progress"
        ),
        "operator.ledger.account.add": "application.operator_actions.served.action.ledger_account_add",
        "operator.ledger.actividad_asset.correct_revision": (
            "application.operator_actions.served.action.ledger_actividad_asset_correct_revision"
        ),
        "operator.ledger.classify": "application.operator_actions.served.action.ledger_classify",
        "operator.ledger.classify.irpf_category": (
            "application.operator_actions.served.action.ledger_classify_irpf_category"
        ),
        "operator.ledger.classify.movement": "application.operator_actions.served.action.ledger_classify_movement",
        "operator.ledger.counterparty.filing_name": (
            "application.operator_actions.served.action.ledger_counterparty_filing_name"
        ),
        "operator.ledger.evidence.review.list": (
            "application.operator_actions.served.action.ledger_evidence_review_list"
        ),
        "operator.ledger.inventory.movement.claim": (
            "application.operator_actions.served.action.ledger_inventory_movement_claim"
        ),
        "operator.ledger.invoice.update.operation_type": (
            "application.operator_actions.served.action.ledger_invoice_update_operation_type"
        ),
        "operator.ledger.link": "application.operator_actions.served.action.ledger_link",
        "operator.ledger.preflight": "application.operator_actions.served.action.ledger_preflight",
        "operator.ledger.prorrata.list": "application.operator_actions.served.action.ledger_prorrata_list",
        "operator.ledger.prorrata.seed": "application.operator_actions.served.action.ledger_prorrata_seed",
        "operator.ledger.review": "application.operator_actions.served.action.ledger_review",
        "operator.live.filed.pull": "application.operator_actions.served.action.live_filed_pull",
        "operator.live.filed.pull_all": "application.operator_actions.served.action.live_filed_pull_all",
        "operator.live.notifications.list": "application.operator_actions.served.action.live_notifications_list",
        "operator.modelo.bindings.list": "application.operator_actions.served.action.modelo_bindings_list",
        "operator.modelo.casillas": "application.operator_actions.served.action.modelo_casillas",
        "operator.modelo.describe": "application.operator_actions.served.action.modelo_describe",
        "operator.modelo.export": "application.operator_actions.served.action.modelo_export",
        "operator.modelo.filing_record.import": (
            "application.operator_actions.served.action.modelo_filing_record_import"
        ),
        "operator.modelo.filing_record.list": "application.operator_actions.served.action.modelo_filing_record_list",
        "operator.modelo.iva_wallet.override": "application.operator_actions.served.action.modelo_iva_wallet_override",
        "operator.modelo.iva_wallet.seed": "application.operator_actions.served.action.modelo_iva_wallet_seed",
        "operator.modelo.verification_report.list": (
            "application.operator_actions.served.action.modelo_verification_report_list"
        ),
        "operator.modelo.work.amend": "application.operator_actions.served.action.modelo_work_amend",
        "operator.modelo.work.amend_wizard": ("application.operator_actions.served.action.modelo_work_amend_wizard"),
        "operator.modelo.work.attest_m303_exonerado_390": (
            "application.operator_actions.served.action.modelo_work_attest_m303_exonerado_390"
        ),
        "operator.modelo.work.attest_prior_carries": (
            "application.operator_actions.served.action.modelo_work_attest_prior_carries"
        ),
        "operator.modelo.work.attest_prior_value": (
            "application.operator_actions.served.action.modelo_work_attest_prior_value"
        ),
        "operator.modelo.work.attest_work_income": (
            "application.operator_actions.served.action.modelo_work_attest_work_income"
        ),
        "operator.modelo.work.calculate": "application.operator_actions.served.action.modelo_work_calculate",
        "operator.modelo.work.calculate_joint_return": (
            "application.operator_actions.served.action.modelo_work_calculate_joint_return"
        ),
        "operator.modelo.work.create": "application.operator_actions.served.action.modelo_work_create",
        "operator.modelo.work.file": "application.operator_actions.served.action.modelo_work_file",
        "operator.modelo.work.list": "application.operator_actions.served.action.modelo_work_list",
        "operator.modelo.work.override": "application.operator_actions.served.action.modelo_work_override",
        "operator.modelo.work.revisions": "application.operator_actions.served.action.modelo_work_revisions",
        "operator.modelo.work.set_value": "application.operator_actions.served.action.modelo_work_set_value",
        "operator.modelo.work.status": "application.operator_actions.served.action.modelo_work_status",
        "operator.modelo.work.verify": "application.operator_actions.served.action.modelo_work_verify",
        "operator.overview.explain": "application.operator_actions.served.action.overview_explain",
        "operator.overview.status": "application.operator_actions.served.action.overview_status",
        "operator.profile.archive.reconcile": "application.operator_actions.served.action.profile_archive_reconcile",
        "operator.profile.arrendamiento": "application.operator_actions.served.action.profile_arrendamiento",
        "operator.profile.ascendiente": "application.operator_actions.served.action.profile_ascendiente",
        "operator.profile.complete_setup": "application.operator_actions.served.action.profile_complete_setup",
        "operator.profile.create": "application.operator_actions.served.action.profile_create",
        "operator.profile.descendiente": "application.operator_actions.served.action.profile_descendiente",
        "operator.profile.edit": "application.operator_actions.served.action.profile_edit",
        "operator.profile.list": "application.operator_actions.served.action.profile_list",
        "operator.profile.login": "application.operator_actions.served.action.profile_login",
        "operator.profile.logout": "application.operator_actions.served.action.profile_logout",
        "operator.profile.repair_active_pointer": (
            "application.operator_actions.served.action.profile_repair_active_pointer"
        ),
        "operator.profile.repair_clear_active": (
            "application.operator_actions.served.action.profile_repair_clear_active"
        ),
        "operator.profile.status": "application.operator_actions.served.action.profile_status",
        "operator.storage.init": "application.operator_actions.served.action.storage_init",
    }
)
"""One catalogue key per operator action, naming the action as an operator reads it on a control."""

NO_RECOVERY_WORDS_LOCALE_KEYS: Final[Mapping[NoRecoveryOutcome, str]] = MappingProxyType(
    {
        NoRecoveryOutcome.TERMINAL: "application.operator_actions.served.no_recovery.terminal",
        NoRecoveryOutcome.SAFETY: "application.operator_actions.served.no_recovery.safety",
        NoRecoveryOutcome.OPERATOR_DECISION: "application.operator_actions.served.no_recovery.operator_decision",
    }
)
"""One catalogue key per closed no-recovery outcome, saying why the refusal offers no way out."""


def _words(key: str | None, language: OutputLanguage) -> str | None:
    """``key``'s words in ``language``, or ``None`` when the catalogue has none."""
    if key is None or lookup_translation(key, locale=language.value) is None:
        return None
    words = tr(key, locale=language.value).strip()
    return words or None


def served_action_fields(action_id: str, language: OutputLanguage) -> dict[str, object]:
    """The served words and target operations of one offered action, absent outside the catalogue."""
    words = _words(ACTION_WORDS_LOCALE_KEYS.get(action_id), language)
    try:
        entry = OPERATOR_ACTION_CATALOGUE.lookup(action_id)
    except KeyError:
        operation_ids: tuple[str, ...] = ()
    else:
        operation_ids = target_operation_ids(entry.target_command_key)
    return {
        "action_words": words,
        "action_words_language": None if words is None else language,
        "target_operation_ids": operation_ids,
    }


def _served_alternative(alternative: AlternativeRecoveryAction, language: OutputLanguage) -> AlternativeRecoveryAction:
    return alternative.model_copy(update=served_action_fields(alternative.action.action_id, language))


def serve_precondition_verdict(verdict: PreconditionVerdict, language: OutputLanguage) -> PreconditionVerdict:
    """``verdict`` with the words and routing of every offered action, or its no-way-out sentence, served.

    Serving replaces whatever an earlier projection served, so a verdict carried
    on is said in the language of the process that carries it.
    """
    if verdict.action is not None:
        return verdict.model_copy(
            update={
                **served_action_fields(verdict.action.action_id, language),
                "alternative_actions": tuple(
                    _served_alternative(item, language) for item in verdict.alternative_actions
                ),
            }
        )
    outcome = verdict.no_recovery_outcome
    words = None if outcome is None else _words(NO_RECOVERY_WORDS_LOCALE_KEYS.get(outcome), language)
    return verdict.model_copy(
        update={"no_recovery_words": words, "no_recovery_words_language": None if words is None else language}
    )


__all__ = [
    "ACTION_WORDS_LOCALE_KEYS",
    "NO_RECOVERY_WORDS_LOCALE_KEYS",
    "serve_precondition_verdict",
    "served_action_fields",
]
