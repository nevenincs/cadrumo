"""Verification findings presented in the modelo work form."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.hex_ids import InvoiceId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .verification_finding_contracts import INVOICE_SOURCE_DOCUMENT_MISSING_KEY


class ModeloFormAttention(StrEnum):
    """How much a finding asks of the filer."""

    #: It must be resolved before the declaration can be recorded as filed.
    BLOCKS = "blocks"
    #: A value the declaration requires is missing; giving it resolves the finding.
    MISSING = "missing"
    #: A value Cadrumo assumed or kept, waiting for the filer to confirm it.
    CONFIRM = "confirm"
    #: A warning worth checking; it does not stop the filing.
    CHECK = "check"
    #: A figure the calculation leaves out and says so; nothing to resolve, but the filer must know it.
    LIMITATION = "limitation"
    #: An explanation of what the calculation did; nothing to act on.
    INFO = "info"


EXPLANATORY_FINDING_MESSAGE_KEYS: Final[frozenset[str]] = frozenset(
    {
        # A dependency on an earlier period scoped out because the filer
        # declared a later activity start: it says why a filing is not needed.
        "application.modelo.findings.cross_period_operator_declared_suppression",
        # A first-year Modelo 202 instalment scoped out by the activity start.
        "application.modelo.findings.cross_period_first_year_fractional_suppression",
        # An earlier filing admitted because it carries zero into this one.
        "application.modelo.findings.cross_period_zero_value_previous_filing",
        # An earlier Modelo 111 admitted because it declares no withholdings.
        "application.modelo.findings.cross_period_m111_no_retenciones",
        # Source modelos this taxpayer does not file.
        "application.modelo.findings.cross_period_modelo_not_applicable.message",
        # An empty annual withholdings summary the filer attested that no
        # withholding was paid in any period: it says why nothing is declared.
        "application.modelo.findings.withholding_detail_absent_attested",
    }
)
"""The advisory findings that explain a decision the verification already made.

Each is produced when the verification admits or scopes out a dependency on
explicit evidence, such as the filer's own declaration of when their activity
started or that they paid no income subject to withholding: the finding tells
the filer why, and asks nothing of them. Advisories outside this set, such as
a possibly missed reduction or a total resting on a non-official local chain,
remain worth checking. The set is closed and keyed on the producers' catalogue
keys; a key it names that no catalogue carries fails its guard test.
"""


def finding_attention(finding: ModeloVerificationFinding) -> ModeloFormAttention:
    """Classify one verification finding on the filer's attention scale.

    A required value that is missing sits with the other missing values, since
    giving it is all it asks. Any other blocking finding blocks. A warning is
    worth checking, unless it discloses a limitation of the calculation, which
    has its own level, or is an advisory the verification emits to explain an
    admitted or scoped-out dependency, which is for information only. The
    finding's own marker decides the limitation level; the finding model
    already refuses a blocking limitation.
    """
    if finding.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA:
        return ModeloFormAttention.MISSING
    if finding.severity is ModeloVerificationFindingSeverity.BLOCKING:
        return ModeloFormAttention.BLOCKS
    if finding.disclosed_limitation:
        return ModeloFormAttention.LIMITATION
    if (
        finding.kind is ModeloVerificationFindingKind.ADVISORY
        and finding.message_locale_key in EXPLANATORY_FINDING_MESSAGE_KEYS
    ):
        return ModeloFormAttention.INFO
    return ModeloFormAttention.CHECK


def _issue_attention(data: dict[str, object]) -> ModeloFormAttention:
    finding = data.get("finding")
    if not isinstance(finding, ModeloVerificationFinding):
        raise ValueError("an issue's attention is derived from its finding")
    return finding_attention(finding)


FINDING_KIND_ACTION_LOCALE_KEYS: Final[Mapping[ModeloVerificationFindingKind, str]] = MappingProxyType(
    {
        ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA: (
            "application.modelo.work_form.finding_action.enter_box_value"
        ),
        ModeloVerificationFindingKind.RECONCILIATION_MISMATCH: (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN: (
            "application.modelo.work_form.finding_action.settle_earlier_declaration"
        ),
        ModeloVerificationFindingKind.BLOCKING_RULE: (
            "application.modelo.work_form.finding_action.correct_and_recalculate"
        ),
        ModeloVerificationFindingKind.ADVISORY: "application.modelo.work_form.finding_action.read_and_decide",
        ModeloVerificationFindingKind.STALE_CALCULATION: "application.modelo.work_form.finding_action.calculate_again",
    }
)
"""What to do about a finding whose message has no action of its own, by the finding's kind."""

FINDING_MESSAGE_ACTION_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        # Explanations: the verification already decided, on the filer's own evidence.
        "application.modelo.findings.cross_period_operator_declared_suppression": (
            "application.modelo.work_form.finding_action.nothing_to_do"
        ),
        "application.modelo.findings.cross_period_first_year_fractional_suppression": (
            "application.modelo.work_form.finding_action.nothing_to_do"
        ),
        "application.modelo.findings.cross_period_m111_no_retenciones": (
            "application.modelo.work_form.finding_action.nothing_to_do"
        ),
        "application.modelo.findings.cross_period_modelo_not_applicable.message": (
            "application.modelo.work_form.finding_action.nothing_to_do"
        ),
        "application.modelo.findings.cross_period_zero_value_previous_filing": (
            "application.modelo.work_form.finding_action.check_carried_zero"
        ),
        "application.modelo.findings.cross_period_dependency_operator_attested": (
            "application.modelo.work_form.finding_action.check_stated_figure"
        ),
        "application.modelo.findings.withholding_detail_absent_attested": (
            "application.modelo.work_form.finding_action.review_attested_year"
        ),
        # A document the records lack.
        "application.modelo.findings.transaction_evidence_missing_output": (
            "application.modelo.work_form.finding_action.attach_document"
        ),
        "application.modelo.findings.transaction_evidence_missing_deductible": (
            "application.modelo.work_form.finding_action.attach_document"
        ),
        "application.modelo.findings.invoice_source_document_missing": (
            "application.modelo.work_form.finding_action.attach_document"
        ),
        "application.modelo.findings.iva_import_document_unrecordable": (
            "application.modelo.work_form.finding_action.file_another_way"
        ),
        "application.modelo.findings.iva_cuota_disagrees_with_rate": (
            "application.modelo.work_form.finding_action.correct_and_recalculate"
        ),
        "application.modelo.findings.iva_reagp_document_unrecordable": (
            "application.modelo.work_form.finding_action.file_another_way"
        ),
        "application.modelo.findings.iva_rectification_document_unrecordable": (
            "application.modelo.work_form.finding_action.file_another_way"
        ),
        "application.modelo.findings.oss_evidence_missing": (
            "application.modelo.work_form.finding_action.attach_document"
        ),
        "application.modelo.findings.cuota_less_ledger_row_base_missing": (
            "application.modelo.work_form.finding_action.add_base_to_entry"
        ),
        "application.modelo.findings.shared_casilla_cells_unadjudicated": (
            "application.modelo.work_form.finding_action.shared_box_awaits_review"
        ),
        "application.modelo.findings.xml_required_content_missing": (
            "application.modelo.work_form.finding_action.enter_required_statement"
        ),
        # Figures that disagree.
        "application.modelo.findings.m303_m349_intracom_reconciliation_mismatch": (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        "application.modelo.findings.m200_incn_periodo_anterior_disagrees": (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        "application.modelo.findings.pulled_filing_casilla_mismatch": (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        "application.modelo.findings.cross_casilla_invariant_violated": (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        "application.modelo.findings.attribution_received_unfolded": (
            "application.modelo.work_form.finding_action.compare_figures"
        ),
        # Earlier declarations and records.
        "application.modelo.findings.cross_period_non_official_local_chain.message": (
            "application.modelo.work_form.finding_action.check_earlier_figures"
        ),
        "application.modelo.findings.iva_compensation_annual_source_evidence_failure": (
            "application.modelo.work_form.finding_action.resolve_303_returns"
        ),
        # Facts the filer supplies.
        "application.modelo.findings.cross_period_activity_start_missing": (
            "application.modelo.work_form.finding_action.add_activity_start"
        ),
        "application.modelo.findings.attribution_received_uncaptured": (
            "application.modelo.work_form.finding_action.add_attribution_to_profile"
        ),
        "application.modelo.findings.objective_estimation_exclusion_threshold_exceeded": (
            "application.modelo.work_form.finding_action.check_profile_value"
        ),
        "application.modelo.findings.suffered_retencion_trabajo_uncredited": (
            "application.modelo.work_form.finding_action.enter_withholding_certificate"
        ),
        "application.modelo.findings.suffered_retencion_capital_mobiliario_uncredited": (
            "application.modelo.work_form.finding_action.enter_withholding_certificate"
        ),
        "application.modelo.findings.withholding_count_exceeds_summary_perceptors": (
            "application.modelo.work_form.finding_action.enter_payee_payments"
        ),
        "application.modelo.findings.withholding_count_not_cross_checked": (
            "application.modelo.work_form.finding_action.settle_earlier_declaration"
        ),
        "application.modelo.findings.withholding_total_differs_from_periodic_returns": (
            "application.modelo.work_form.finding_action.compare_withholding_with_periodic_returns"
        ),
        "application.modelo.findings.withholding_detail_absent_against_ledger_evidence": (
            "application.modelo.work_form.finding_action.enter_payee_payments"
        ),
        "application.modelo.findings.withholding_detail_absent_unproven": (
            "application.modelo.work_form.finding_action.enter_or_confirm_payments"
        ),
        "application.modelo.findings.foreign_asset_redeclaration": (
            "application.modelo.work_form.finding_action.declare_asset_again"
        ),
        "application.modelo.findings.m210_agrupacion_renta_invalid": (
            "application.modelo.work_form.finding_action.regroup_income_lines"
        ),
        # Reductions and deductions the figures suggest.
        "application.modelo.findings.dt12a_reduccion_possible": (
            "application.modelo.work_form.finding_action.check_possible_reduction"
        ),
        "application.modelo.findings.madrid_nacimiento_adopcion_eligibility_advisory": (
            "application.modelo.work_form.finding_action.check_possible_reduction"
        ),
        "application.modelo.findings.art52_reduccion_individual_sublimit_possible": (
            "application.modelo.work_form.finding_action.check_condition"
        ),
        "application.modelo.findings.dt12a_reduccion_antiquity_possible": (
            "application.modelo.work_form.finding_action.check_condition"
        ),
        # What this application cannot settle yet.
        "application.modelo.findings.application_order_unsettled": (
            "application.modelo.work_form.finding_action.await_update"
        ),
        "application.modelo.findings.m193_settled_row_amount_authority_unresolved": (
            "application.modelo.work_form.finding_action.await_update"
        ),
        "application.modelo.findings.registry_authority_grade_insufficient": (
            "application.modelo.work_form.finding_action.await_update"
        ),
        "application.modelo.findings.registry_filing_year_projected": (
            "application.modelo.work_form.finding_action.await_update"
        ),
        "application.modelo.findings.registry_snapshot_unresolved": (
            "application.modelo.work_form.finding_action.retry_or_update"
        ),
        # A filed declaration whose profile facts were edited since.
        "application.modelo.findings.profile_read_superseded_filed": (
            "application.modelo.work_form.finding_action.amend_filed_declaration"
        ),
    }
)
"""What to do about a finding, by its message, where the message says more than its kind.

Each action restates the step the finding's own message names or implies, and
nothing more. A message not listed takes its kind's action from
:data:`FINDING_KIND_ACTION_LOCALE_KEYS`; the mapping is closed, and a key on
either side that no catalogue carries fails its guard test.
"""


def finding_action_locale_key(finding: ModeloVerificationFinding) -> str:
    """Return the catalogue key of the one sentence that says what to do about ``finding``.

    The finding's message decides first, then its kind. An explanation's
    "nothing to do" holds only while the finding is an explanation: the same
    message raised as a blocker or a warning of another kind takes its kind's
    action, so a finding that must be resolved never tells the filer to leave it.
    """
    action = FINDING_MESSAGE_ACTION_LOCALE_KEYS.get(finding.message_locale_key)
    explains = finding.message_locale_key in EXPLANATORY_FINDING_MESSAGE_KEYS
    if action is None or (explains and finding_attention(finding) is not ModeloFormAttention.INFO):
        return FINDING_KIND_ACTION_LOCALE_KEYS[finding.kind]
    return action


def _issue_action(data: dict[str, object]) -> str:
    finding = data.get("finding")
    if not isinstance(finding, ModeloVerificationFinding):
        raise ValueError("an issue's action is derived from its finding")
    return finding_action_locale_key(finding)


def finding_invoice_to_open(finding: ModeloVerificationFinding) -> InvoiceId | None:
    """The invoice the filer opens to resolve ``finding``, when the finding names one."""
    if finding.message_locale_key != INVOICE_SOURCE_DOCUMENT_MISSING_KEY:
        return None
    invoice_id = finding.message_facts.get("invoice_id")
    return invoice_id if isinstance(invoice_id, str) else None


def _issue_invoice(data: dict[str, object]) -> InvoiceId | None:
    finding = data.get("finding")
    if not isinstance(finding, ModeloVerificationFinding):
        raise ValueError("an issue's invoice is derived from its finding")
    return finding_invoice_to_open(finding)


FINDING_MESSAGE_DOORS: Final[Mapping[str, str]] = MappingProxyType(
    {
        # Correcting a declaration recorded as filed starts an amendment.
        "application.modelo.findings.profile_read_superseded_filed": "operator.modelo.work.amend",
    }
)
"""The served operator action that resolves a finding, by its message, where one does."""


def finding_door_action_id(finding: ModeloVerificationFinding) -> str | None:
    """The served operator action the filer takes to resolve ``finding``, when one resolves it."""
    return FINDING_MESSAGE_DOORS.get(finding.message_locale_key)


def _issue_door(data: dict[str, object]) -> str | None:
    finding = data.get("finding")
    if not isinstance(finding, ModeloVerificationFinding):
        raise ValueError("an issue's door is derived from its finding")
    return finding_door_action_id(finding)


class ModeloFormIssue(BaseModel):
    """One finding of the current calculation's latest verification, with the box it concerns.

    The finding keeps its catalogue key and typed facts, so the frontend renders
    it in the filer's language; ``box`` is the official box number when the
    finding names a casilla the form shows. ``attention`` places the finding on
    the filer's scale, and ``action_locale_key`` is the catalogue key of the one
    sentence that says what to do about it; both are derived from the finding
    when not given, and must match what it derives to when given.
    """

    model_config = STRICT_FROZEN_CONFIG

    finding: ModeloVerificationFinding
    box: str | None = None
    attention: ModeloFormAttention = Field(default_factory=_issue_attention)
    action_locale_key: str = Field(default_factory=_issue_action)
    #: The invoice whose document the action attaches, served as the door to it.
    open_invoice_id: InvoiceId | None = Field(default_factory=_issue_invoice)
    #: The served operator action that resolves the finding, such as the amendment of a filed declaration.
    door_action_id: str | None = Field(default_factory=_issue_door)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _attention_matches_the_finding(self) -> ModeloFormIssue:
        if self.attention is not finding_attention(self.finding):
            raise ValueError("an issue's attention must be the one its finding classifies to")
        if self.action_locale_key != finding_action_locale_key(self.finding):
            raise ValueError("an issue's action must be the one its finding maps to")
        if self.open_invoice_id != finding_invoice_to_open(self.finding):
            raise ValueError("an issue's invoice must be the one its finding names")
        if self.door_action_id != finding_door_action_id(self.finding):
            raise ValueError("an issue's door must be the one its finding maps to")
        return self
