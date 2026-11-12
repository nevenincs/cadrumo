"""Declared doors of the export refusals that no catalogued action repairs.

An export refuses a value it cannot write instead of padding, cutting or
guessing it. Two causes divide those refusals. A value the filer stated, or the
ledger and profile behind it, is missing, too wide, written with a character the
design cannot take, or contradicts another value: the filer decides how to put
it right, and no catalogued action does it for them. A fault in the published
layout, the registry, or the arguments the caller handed the export is beyond
the filer: nothing they change repairs it.
"""

from __future__ import annotations

from enum import StrEnum

from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions.models import PreconditionVerdict
from .errors import FilingPreconditionCondition, filing_no_recovery_verdict


class ExportRefusalReason(StrEnum):
    """The fixed description of the guard that refused; never a value of the filer."""

    ENVELOPE_OPTION_UNADMITTED = "envelope_option_unadmitted"
    PRODUCT_IDENTITY_UNSUPPLIED = "product_identity_unsupplied"
    PRIOR_DOMICILIATION_ELECTION_UNSTATED = "prior_domiciliation_election_unstated"
    PRIOR_DOMICILIATION_ELECTION_DIFFERS = "prior_domiciliation_election_differs"
    LAYOUT_NOT_RENDERABLE = "layout_not_renderable"
    RECEIPT_ARTEFACT_UNREADABLE = "receipt_artefact_unreadable"
    RECEIPT_ARTEFACT_DIFFERS = "receipt_artefact_differs"
    VERIFY_SNAPSHOT_STALE = "verify_snapshot_stale"
    WRITTEN_FILE_REFUSED = "written_file_refused"
    PAYLOAD_NOT_READABLE = "payload_not_readable"
    VALUE_NOT_CONVERTIBLE = "value_not_convertible"
    BOX_HAS_NO_SINGLE_OCCURRENCE = "box_has_no_single_occurrence"
    ROW_VALUE_INVALID = "row_value_invalid"
    ROWS_EXCEED_SCHEMA = "rows_exceed_schema"
    VALUE_NOT_STATED_BY_ROWS = "value_not_stated_by_rows"
    COMUNIDAD_AMBIGUOUS = "comunidad_ambiguous"
    VALUE_FORM_REFUSED = "value_form_refused"
    RECORD_INCOMPLETE = "record_incomplete"
    CONTEXT_UNSUPPLIED = "context_unsupplied"
    RECORD_CONTEXT_CONTRADICTED = "record_context_contradicted"
    MARK_UNREPRESENTABLE = "mark_unrepresentable"
    COUNTERPARTY_ROWS_UNATTRIBUTABLE = "counterparty_rows_unattributable"
    PROJECTION_FACTS_UNSUPPLIED = "projection_facts_unsupplied"
    PRODUCER_FACT_UNSUPPLIED = "producer_fact_unsupplied"
    REQUIRED_BINDING_OMITTED = "required_binding_omitted"
    POSITIVE_CASILLA_REQUIRED = "positive_casilla_required"
    SLOT_VALUE_TOO_WIDE = "slot_value_too_wide"
    REQUIRED_RECORD_ABSENT = "required_record_absent"
    SHARED_CELLS_UNADJUDICATED = "shared_cells_unadjudicated"


def _verdict(reason: ExportRefusalReason, outcome: NoRecoveryOutcome) -> PreconditionVerdict:
    return filing_no_recovery_verdict(
        FilingPreconditionCondition.OPERATION_ADMISSIBLE,
        facts={"reason": reason.value},
        outcome=outcome,
    )


def export_input_decision(reason: ExportRefusalReason) -> PreconditionVerdict:
    """The door of a refusal caused by a value the filer, or the ledger and profile behind it, supplied.

    No catalogued action states the value, so the outcome is the filer's
    decision, not a command.
    """
    return _verdict(reason, NoRecoveryOutcome.OPERATOR_DECISION)


def export_design_terminal(reason: ExportRefusalReason) -> PreconditionVerdict:
    """The door of a refusal caused by the published layout, the registry or the caller's arguments.

    Nothing the filer changes repairs it, so the outcome is terminal.
    """
    return _verdict(reason, NoRecoveryOutcome.TERMINAL)


__all__ = ["ExportRefusalReason", "export_design_terminal", "export_input_decision"]
