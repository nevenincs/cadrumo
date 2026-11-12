"""What the calculation itself noticed, placed on the filer's attention scale and worded from the catalogue.

A calculation raises diagnostics while it resolves its sources: an amount from
the records that reached no box, a box whose source produced nothing, a value
the filer typed that differs from the worked-out one. Each reason has one
place on the scale the findings list uses, one sentence for what happened and
one for what to do, in every language.

The reasons that block filing are exactly those the application refuses
(:data:`BLOCKING_REASONS`), by one of three routes: the calculation-note gate
refuses checking, exporting and recording (:data:`GATE_REFUSED_REASONS`), a
check step refuses on its own evidence (:data:`CHECK_REFUSED_REASONS`), or the
export refuses the file (:data:`EXPORT_REFUSED_REASONS`). The editor withholds
filing on the same set, so the two can never disagree. A reason a check step
decides waits for that check: until the current calculation is checked the
editor offers the check next, and once it is, the check's own finding of the
same cause stands in the note's place.

A value from a binding whose declared grade cap stops it at calculation is
refused by the gate too, unless its resolver proved it zero.

A printed box that could not be worked out, a source with no route and a source
store not ready are refused by the gate: their producers report only sources
that apply to the filer. A box that could not be worked out blocks only when the
form prints it (:data:`PRINTED_BOX_REASONS`, as :mod:`.printed_boxes` reads the
form); a working figure is worth checking. A value arriving by an undeclared
route is worth checking and persists with the calculation: it still fires for a
route kept without a terminal origin by design, so refusing on it would refuse
declarations calculated through that route. An activity-asset note persists too,
with the row, element, interval and amount it names (:func:`fact_locale_key`), so
what was known at calculation stays with the filed record; it withholds nothing.
Every diagnostic that does not persist is held in this process only until
the next calculation of the declaration (:class:`CalculationNoteStore`), and a
declaration opened afresh says to calculate again to see them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from threading import Lock
from types import MappingProxyType
from typing import Final, get_args

from ...core.aggregation import BindingSourceKind, BindingValueOutcome
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language, tr
from ...core.logging import get_logger
from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
)
from ...domain.filing.declared_party_name_filing import DECLARED_PARTY_NAME_DOOR_ACTION_ID
from ...domain.modelos.calculation_revision_sources import (
    DISAGREEMENT_REASONS,
    CalculationNoteFact,
    CalculationNoteSentence,
    CalculationSourceIssue,
    RecordedCalculationNote,
    element_names_of,
    recorded_calculation_notes,
)
from ...domain.user_profile.labels import profile_field_label_key
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..aggregation.source_diagnostic_reason import CalculationSourceDiagnosticReason
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from .disagreement_words import CROSS_CHECK_LABEL_LOCALE_KEYS, sources_facts_words, value_facts_words
from .inventory_purchase_claim_gate import inventory_purchase_claim_verdict
from .value_presentation import format_casilla_value
from .work_form_findings import ModeloFormAttention

_B = ModeloFormAttention.BLOCKS
_M = ModeloFormAttention.MISSING
_C = ModeloFormAttention.CHECK
_I = ModeloFormAttention.INFO

GATE_REFUSED_REASONS: Final[frozenset[str]] = frozenset(
    {
        "unrouted_observation",
        "unrouted_declarable_quantity",
        "invoice_reverse_charge_cuota_not_derivable",
        "m349_operation_unclassified",
        "unresolved_binding",
        "unhandled_binding_source",
        "source_domain_not_ready",
        "advisory_binding_value",
        "credit_source_disagreement",
        "precedence_tier_divergence",
        "household_row_fact_unstated",
        "income_family_not_computed",
    }
)
"""Reasons the calculation-note gate refuses checking, exporting and recording on.

A figure left out or unworked, an intra-community operation whose clave no
record states, or a figure whose binding's declared grade cap
stops it at calculation; a capped figure the resolver proved to be zero is the
one such note the gate passes (:func:`note_attention`).
"""
CHECK_REFUSED_REASONS: Final[frozenset[str]] = frozenset(
    {
        "iva_selected_scope_evidence_failure",
        "iva_compensation_annual_source_evidence_failure",
        "withholding_detail_absent",
    }
)
"""Reasons a check step refuses on its own evidence, which may also admit them (an attested empty detail)."""
EXPORT_REFUSED_REASONS: Final[frozenset[str]] = frozenset({"rate_boxes_underaccount_total"})
"""Reasons the export refuses the file on: an IVA total its rate boxes do not account for."""
BLOCKING_REASONS: Final[frozenset[str]] = GATE_REFUSED_REASONS | CHECK_REFUSED_REASONS | EXPORT_REFUSED_REASONS
"""Every reason the application refuses filing on, and so the editor too."""
CALCULATION_SCREEN_OUTDATED_REASON: Final[str] = "calculation_screen_outdated"
"""The derived reason a stale or unstamped revision is refused with and the editor withholds filing on.

It is never persisted and no resolver raises it, so it is not among the
diagnostic reasons; its remedy is to calculate again.
"""
FILED_BEFORE_GRADE_CAP_REASON: Final[str] = "filed_before_grade_cap"
"""The derived reason a revision recorded as filed before screen stamps existed is refused its export with.

It applies only where the revision carries no stamp, its registry revision caps
a binding, and the box that binding reaches holds a nonzero or absent value. Like
:data:`CALCULATION_SCREEN_OUTDATED_REASON` it is never persisted; its remedy is
to calculate the declaration again and record the new calculation.
"""
DERIVED_GATE_REASONS: Final[frozenset[str]] = frozenset(
    {CALCULATION_SCREEN_OUTDATED_REASON, FILED_BEFORE_GRADE_CAP_REASON}
)
"""The reasons the gate derives from a revision and its pinned registry rather than reading them from a note."""

CALCULATION_NOTE_ATTENTION: Final[Mapping[str, ModeloFormAttention]] = MappingProxyType(
    {
        **dict.fromkeys(BLOCKING_REASONS, _B),
        # Persisted and shown, not refused: the route it reports may lack a terminal origin by design.
        "terminal_origin_mismatch": _C,
        # A credit no second source could confirm: worth checking, never agreement.
        "credit_cross_check_absent": _C,
        # An accepted disagreement that no longer applies: the figure is disputed afresh.
        "credit_resolution_stale": _C,
        # An accepted disagreement, restated for the filer's information.
        "credit_resolution_applied": _I,
        "unresolved_derived_binding": _C,
        # Something only the filer can supply.
        "source_issue": _M,
        "prior_payment_not_deducted": _M,
        "prior_payment_minoracion_not_captured": _M,
        "official_box_unpopulated": _M,
        "settlement_not_computed": _M,
        "prorrata_especial_check_unavailable": _M,
        "prorrata_volume_check_unavailable": _M,
        "prorrata_volume_declaration_missing": _M,
        "prorrata_volume_divergence": _C,
        "missing_transaction_evidence": _M,
        "unclassified_declarant_role_fact": _M,
        "household_rows_incomplete": _M,
        "unconverted_foreign_currency": _M,
        "aggregation_activity_undeclared": _M,
        "m347_declarado_provincia_unrecorded": _M,
        "declared_party_name_unresolved": _M,
        # Worth checking. A value Cadrumo inferred or kept is among them: no box
        # lists it as assumed, so nothing in the editor can confirm it, and the
        # filer checks it against their records instead.
        "operator_override_diverges_from_computed": _C,
        # Amortization left out or left to the filer: never a refusal and never a value the
        # form waits for. Nothing can clear these, so they are shown without counting as missing.
        "activity_asset_claim_gap": _C,
        "activity_asset_accrual_unavailable": _C,
        "activity_asset_activity_undeclared": _C,
        "activity_asset_residence_period_unknown": _C,
        "ledger_amortization_row_unregistered": _C,
        "activity_asset_foral_territory": _C,
        "activity_asset_residence_unresolved": _C,
        "activity_asset_disposal_finding": _C,
        "orphaned_override": _C,
        "devengo_date_proxy_attribution": _C,
        "iva_row_placed_on_movement_date": _C,
        "iva_operation_date_after_movement": _C,
        "m349_clave_inferred_from_category": _C,
        # Owed only where a declarado paid over the threshold in cash, which the filer knows and the records do not.
        "m347_metalico_unrecorded": _C,
        "unsettled_legal_reading": _C,
        "inferred_retencion_rate_unmatched": _C,
        "inferred_retencion_sectoral_rate_unconfirmed": _C,
        "invoice_category_counterparty_mismatch": _C,
        "invoice_recargo_departs_from_published_rate": _C,
        "invoice_recargo_not_attributable_to_a_tier": _C,
        "administrador_retencion_rate_mismatch": _C,
        "prorrata_especial_obligatoria": _C,
        "ungrounded_income_substrate": _C,
        "unusable_sales_invoice_evidence": _C,
        "structurally_unroutable_base_category": _C,
        "storage_degraded": _C,
        "duplicate_binding_owner": _C,
        "duplicate_bound_casilla_owner": _C,
        "duplicate_relation_owner": _C,
        "m193_settled_row_amounts_unresolved_authority": _C,
        "inferred_retencion_excluded_from_credit": _C,
        "unresolved_retencion_substrate": _C,
        "register_acquisition_exceeds_ledger": _C,
        "register_acquisition_partly_accounted": _C,
        "register_acquisition_row_missing": _C,
        "ledger_expense_may_be_durable": _C,
        # Two sources hold different values for a figure that reaches no exported box.
        "precedence_tier_divergence_advisory": _C,
        # For the filer's information.
        "deferred_binding_source": _I,
        "oss_no_live_source": _I,
        "register_owned_capital_acquisition": _I,
        "inventory_book_claimed_purchase": _I,
        "activity_asset_agrarian_excluded": _I,
        "dt12_regime_window_closed": _I,
        "dt12_regime_window_unverified": _I,
        "dt12_parcial_rescate_guidance": _I,
    }
)
"""The one place on the filer's scale of every reason a calculation diagnostic can carry."""

PRINTED_BOX_REASONS: Final[frozenset[str]] = frozenset({"unresolved_binding"})
"""Blocking reasons that withhold filing only on a printed box: a working figure they name is worth checking."""

UNWORKED_BOX_REASONS: Final[frozenset[str]] = frozenset(
    {
        "unresolved_binding",
        "unresolved_derived_binding",
        "activity_asset_claim_gap",
        "activity_asset_accrual_unavailable",
    }
)
"""Reasons that name a box that could not be worked out: it never reads as a zero."""

RECORDS_REASONS: Final[frozenset[str]] = frozenset(
    {
        "unrouted_observation",
        "unrouted_declarable_quantity",
        "structurally_unroutable_base_category",
        "withholding_detail_absent",
        "iva_selected_scope_evidence_failure",
        "iva_compensation_annual_source_evidence_failure",
        "missing_transaction_evidence",
        "devengo_date_proxy_attribution",
        "iva_row_placed_on_movement_date",
        "iva_operation_date_after_movement",
        "m349_clave_inferred_from_category",
        "m349_operation_unclassified",
        "inferred_retencion_rate_unmatched",
        "inferred_retencion_sectoral_rate_unconfirmed",
        "administrador_retencion_rate_mismatch",
        "unconverted_foreign_currency",
        "unclassified_declarant_role_fact",
        "invoice_category_counterparty_mismatch",
        "invoice_reverse_charge_cuota_not_derivable",
        "invoice_recargo_departs_from_published_rate",
        "invoice_recargo_not_attributable_to_a_tier",
        "ungrounded_income_substrate",
        "unusable_sales_invoice_evidence",
        "aggregation_activity_undeclared",
        "ledger_amortization_row_unregistered",
    }
)
"""Reasons whose cause is an entry in the filer's records, where the note sits and is put right."""

PROFILE_REASONS: Final[frozenset[str]] = frozenset({"household_rows_incomplete", "household_row_fact_unstated"})
"""Reasons whose cause is a fact the filer keeps in their profile, where the note is put right."""

_KEY_ROOT: Final[str] = "application.modelo.calc_diagnostic"
_FACT_KEY_ROOT: Final[str] = "application.modelo.calc_diagnostic_fact"
_ELEMENT_NAME_LOCALE_KEY: Final[str] = "application.modelo.calc_diagnostic_words.named_element"
_UNNAMED_ELEMENT_LOCALE_KEY: Final[str] = "application.modelo.calc_diagnostic_words.unnamed_element"
_UNNUMBERED_BOX_LOCALE_KEY: Final[str] = "application.modelo.finding_fact.box_unnumbered"
_INCOME_CLASS_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "trabajo": "application.modelo.calc_diagnostic_words.income_class.trabajo",
        "capital_mobiliario": "application.modelo.calc_diagnostic_words.income_class.capital_mobiliario",
        "arrendamiento_inmueble_urbano": (
            "application.modelo.calc_diagnostic_words.income_class.arrendamiento_inmueble_urbano"
        ),
        "arrendamiento_inmueble_urbano_actividad": (
            "application.modelo.calc_diagnostic_words.income_class.arrendamiento_inmueble_urbano_actividad"
        ),
        "actividad_economica": "application.modelo.calc_diagnostic_words.income_class.actividad_economica",
        "ganancia_patrimonial": "application.modelo.calc_diagnostic_words.income_class.ganancia_patrimonial",
        "atribucion_capital_mobiliario": (
            "application.modelo.calc_diagnostic_words.income_class.atribucion_capital_mobiliario"
        ),
        "atribucion_capital_inmobiliario": (
            "application.modelo.calc_diagnostic_words.income_class.atribucion_capital_inmobiliario"
        ),
        "atribucion_actividad_economica": (
            "application.modelo.calc_diagnostic_words.income_class.atribucion_actividad_economica"
        ),
        "atribucion_ganancia_patrimonial": (
            "application.modelo.calc_diagnostic_words.income_class.atribucion_ganancia_patrimonial"
        ),
        "imputacion_aie_ute": "application.modelo.calc_diagnostic_words.income_class.imputacion_aie_ute",
        "imputacion_derechos_imagen": (
            "application.modelo.calc_diagnostic_words.income_class.imputacion_derechos_imagen"
        ),
    }
)
"""The words of each suffered-withholding income class a note names, by the token the calculation stores."""
_OTHER_INCOME_CLASS_LOCALE_KEY: Final[str] = "application.modelo.calc_diagnostic_words.income_class.other"
_ELEMENT_PLACEHOLDERS: Final[frozenset[str]] = frozenset({"element", "elements"})
_PROFILE_GROUP_VALUE: Final[str] = "group"
_HOUSEHOLD_LEAF_VALUE: Final[str] = "leaf"
_HOUSEHOLD_LEAF_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "nif": "application.modelo.calc_diagnostic_words.household_leaf.nif",
        "apellidos_nombre": "application.modelo.calc_diagnostic_words.household_leaf.apellidos_nombre",
        "birth_date": "application.modelo.calc_diagnostic_words.household_leaf.birth_date",
    }
)
"""The words of each household row fact the design requires, by the leaf token the profile stores."""
_PROFILE_FIELD_VALUE: Final[str] = "field"
_DATE_VALUES: Final[frozenset[str]] = frozenset({"date", "start", "end", "row_date", "period_end"})
_AMOUNT_VALUES: Final[frozenset[str]] = frozenset(
    {
        "amount",
        "cost",
        "paid",
        "price",
        "base",
        "remainder",
        "effect",
        "transmission_value",
        "net_value",
        "row_amount",
        "compared_amount",
    }
)
_INCOME_CLASS_VALUE: Final[str] = "income_class"
_CROSS_CHECK_VALUE: Final[str] = "cross_check"
_ACCEPTED_VALUE: Final[str] = "accepted"
_SOURCES_VALUE: Final[str] = "sources"
_logger = get_logger(__name__)
STALE_LOCALE_KEY: Final[str] = "application.modelo.calc_diagnostic.stale"
REOPEN_HINT_LOCALE_KEY: Final[str] = "application.modelo.calc_diagnostic.reopen_hint"


_RECORD_NOTE_ACTIONS: Final[Mapping[str, tuple[str, str, tuple[str, ...]]]] = MappingProxyType(
    {
        "m349_operation_unclassified": (
            "operator.ledger.invoice.update.operation_type",
            "invoice_id",
            ("operation_type",),
        ),
    }
)
"""The catalogue action that puts right the one record a note names, by reason.

Each names the action, the argument its record fills, and the arguments only
the filer can state: which operation an invoice records is a fact of the
operation, so the note names the invoice and never the clave.
"""


_PARTY_NOTE_ACTIONS: Final[Mapping[str, tuple[str, tuple[str, ...]]]] = MappingProxyType(
    {
        "declared_party_name_unresolved": (
            DECLARED_PARTY_NAME_DOOR_ACTION_ID,
            ("tax_identifier", "country_code", "kind"),
        ),
    }
)
"""The catalogue action that states the fact a note says its party lacks, by reason.

The note names its party only in words, so the door binds none of the action's
arguments, as the export's refusal for the same slot binds none: the filer
states which party and what kind it is.
"""


def _party_note_verdict(reason: str, action_id: str, operator_arguments: tuple[str, ...]) -> PreconditionVerdict:
    condition_id = f"modelo.work.calculate.{reason}.stated"
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=f"modelo.work.calculate.{reason}",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={"reason": reason},
            ),
        ),
        action=ActionReference(action_id=action_id),
        argument_bindings=tuple(
            ActionArgumentBinding(argument_name=name, status=ActionArgumentStatus.MISSING)
            for name in operator_arguments
        ),
        missing_argument_names=operator_arguments,
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def note_record_verdict(diagnostic: CalculationSourceDiagnostic) -> PreconditionVerdict | None:
    """The door a note opens: to the record it names, or to the statement its party lacks, where it has one."""
    inventory_door = inventory_purchase_claim_verdict(diagnostic.fact)
    if inventory_door is not None:
        return inventory_door
    party_door = _PARTY_NOTE_ACTIONS.get(diagnostic.reason)
    if party_door is not None:
        return _party_note_verdict(diagnostic.reason, *party_door)
    declared = _RECORD_NOTE_ACTIONS.get(diagnostic.reason)
    fact = diagnostic.fact
    if declared is None or fact is None or len(fact.row_refs) != 1:
        return None
    action_id, row_argument, operator_arguments = declared
    (row_ref,) = fact.row_refs
    condition_id = f"modelo.work.calculate.{diagnostic.reason}.stated"
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=f"modelo.work.calculate.{diagnostic.reason}",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={row_argument: row_ref},
            ),
        ),
        action=ActionReference(action_id=action_id),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name=row_argument,
                status=ActionArgumentStatus.RESOLVED,
                value=row_ref,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key=row_argument,
            ),
            *(
                ActionArgumentBinding(argument_name=name, status=ActionArgumentStatus.MISSING)
                for name in operator_arguments
            ),
        ),
        missing_argument_names=operator_arguments,
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def capped_value_proven_zero(reason: str, outcome: BindingValueOutcome | None) -> bool:
    """Whether a note reports a capped value its resolver proved to be zero, which withholds nothing.

    The outcome is the resolver's statement, never read off the amount: a
    capped note without one is not a proven zero.
    """
    return reason == "advisory_binding_value" and outcome is BindingValueOutcome.PROVEN_ZERO


def note_attention(
    reason: str, *, box: str | None, outcome: BindingValueOutcome | None = None, accepted: bool = False
) -> ModeloFormAttention:
    """Place one diagnostic reason on the filer's scale; ``box`` is the number the form prints for the box it names.

    ``box`` is ``None`` when the reason names no box or a working figure the
    form does not print (:mod:`.printed_boxes`). ``outcome`` is the resolver's
    stated outcome for a capped value: a proven zero is for the filer's
    information. ``accepted`` says an operator resolution covers the source
    disagreement the note states: it stays listed as worth checking, and no
    longer blocks.
    """
    if reason in DERIVED_GATE_REASONS:
        return _B
    if accepted and reason in DISAGREEMENT_REASONS:
        return _C
    if reason in PRINTED_BOX_REASONS and box is None:
        return _C
    if capped_value_proven_zero(reason, outcome):
        return _I
    return CALCULATION_NOTE_ATTENTION[reason]


def what_locale_key(reason: str) -> str:
    """The catalogue key of the sentence saying what the calculation noticed."""
    return f"{_KEY_ROOT}.{reason}.what"


def what_to_do_locale_key(reason: str) -> str:
    """The catalogue key of the sentence saying what to do about it."""
    return f"{_KEY_ROOT}.{reason}.what_to_do"


def fact_locale_key(sentence: CalculationNoteSentence) -> str:
    """The catalogue key of the sentence that states a note's own row, element, interval and amount."""
    return f"{_FACT_KEY_ROOT}.{sentence.value}"


def note_fact_text(
    fact: CalculationNoteFact,
    *,
    element_names: Iterable[tuple[str, str]] = (),
    locale: str | None = None,
) -> str:
    """State a note's facts in words, in ``locale`` or the active language.

    Dates and amounts read as a box writes them, and an income class by its Renta
    label in the language read in, never its stored token. An element goes by the name it
    has now, or by a plain phrase when it has none or has left the register.
    """
    language = OutputLanguage(locale or output_language())
    names = dict(element_names)
    elements = ", ".join(
        tr(_ELEMENT_NAME_LOCALE_KEY, locale=language.value, name=names[ref])
        if ref in names
        else tr(_UNNAMED_ELEMENT_LOCALE_KEY, locale=language.value)
        for ref in dict.fromkeys(fact.element_refs)
    )
    return tr(
        fact_locale_key(fact.sentence),
        locale=language.value,
        element=elements,
        elements=elements,
        # Older stored facts carry these two names as values; the sentence's own elements take their place.
        **{
            name: _fact_value_text(name, value, language)
            for name, value in fact.values
            if name not in _ELEMENT_PLACEHOLDERS
        },
    )


def _fact_value_text(name: str, value: str, language: OutputLanguage) -> str:
    if name in _DATE_VALUES and value:
        return format_casilla_value(date.fromisoformat(value), data_type="date", language=language)
    if name in _AMOUNT_VALUES:
        return format_casilla_value(Decimal(value), data_type="money", language=language)
    if name == _HOUSEHOLD_LEAF_VALUE:
        return tr(_HOUSEHOLD_LEAF_LOCALE_KEYS[value], locale=language.value)
    if name == _INCOME_CLASS_VALUE:
        return tr(_INCOME_CLASS_LOCALE_KEYS.get(value, _OTHER_INCOME_CLASS_LOCALE_KEY), locale=language.value)
    if name in (_PROFILE_GROUP_VALUE, _PROFILE_FIELD_VALUE):
        section, _, field = value.partition(".")
        return tr(profile_field_label_key(section, field), locale=language.value)
    if name == _CROSS_CHECK_VALUE:
        return tr(CROSS_CHECK_LABEL_LOCALE_KEYS[value], locale=language.value)
    if name == _ACCEPTED_VALUE:
        return value_facts_words(value, language)
    if name == _SOURCES_VALUE:
        return sources_facts_words(value, language)
    return value


def read_element_names(repository: ActivityAssetHistoryRepository | None) -> dict[str, str]:
    """Read the name each element of the register goes by now.

    A note is still worth showing if the register cannot be read, so a failed read
    leaves every element to the plain phrase rather than failing the read it serves.
    """
    if repository is None:
        return {}
    try:
        history = repository.load()
    except (CadrumoError, OSError):
        _logger.warning("activity_asset_names_unavailable")
        return {}
    return {descriptor.asset_id: descriptor.facts.name for descriptor in history.descriptors}


def read_recorded_notes(
    issues: Iterable[CalculationSourceIssue], repository: ActivityAssetHistoryRepository | None
) -> tuple[RecordedCalculationNote, ...]:
    """The notes a calculation kept, in words and under the names their elements go by now.

    A proven zero's fact says all there is to say: its reason's sentence speaks
    of a figure that is held back, which a proven zero is not, so it has no detail.
    """
    return tuple(
        note.model_copy(
            update={
                "message": note_fact_text(note.fact, element_names=note.element_names),
                "detail": ""
                if note.fact.sentence is CalculationNoteSentence.ADVISORY_VALUE_PROVEN_ZERO
                else tr(what_locale_key(note.reason), box=tr(_UNNUMBERED_BOX_LOCALE_KEY)),
            }
        )
        for note in recorded_calculation_notes(issues, names=read_element_names(repository))
    )


def with_element_names(
    diagnostics: tuple[CalculationSourceDiagnostic, ...], repository: ActivityAssetHistoryRepository | None
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Give each diagnostic that speaks of elements the names they go by now, for a command that shows them."""
    if not any(diagnostic.fact is not None and diagnostic.fact.element_refs for diagnostic in diagnostics):
        return diagnostics
    names = read_element_names(repository)
    return tuple(
        diagnostic.model_copy(update={"element_names": element_names_of(diagnostic.fact, names)})
        for diagnostic in diagnostics
    )


def durable_binding_source(diagnostic: CalculationSourceDiagnostic) -> BindingSourceKind | None:
    """The binding source kind a diagnostic names, read from its typed field or its source kind."""
    if diagnostic.binding_source is not None:
        return diagnostic.binding_source
    try:
        return BindingSourceKind(diagnostic.source_kind)
    except ValueError:
        return None


class CalculationNoteStore:
    """The diagnostics of each declaration's latest calculation in this process, by calculation revision.

    A calculation's diagnostics other than the blocking ones are not stored
    with it: they belong to the calculation that raised them, so they are held
    here until the next calculation of the same work unit replaces them, and
    are gone when the application closes.
    """

    def __init__(self) -> None:
        """Start with nothing held."""
        self._lock = Lock()
        self._by_work_unit: dict[str, tuple[str, tuple[CalculationSourceDiagnostic, ...]]] = {}

    def record(
        self, work_unit_id: str, calculation_revision_id: str, diagnostics: tuple[CalculationSourceDiagnostic, ...]
    ) -> None:
        """Hold one calculation's diagnostics, replacing the work unit's earlier ones."""
        with self._lock:
            self._by_work_unit[work_unit_id] = (calculation_revision_id, diagnostics)

    def diagnostics_for(
        self, work_unit_id: str, calculation_revision_id: str | None
    ) -> tuple[CalculationSourceDiagnostic, ...] | None:
        """The diagnostics of that calculation, or ``None`` when this process did not run it."""
        with self._lock:
            held = self._by_work_unit.get(work_unit_id)
        if held is None or calculation_revision_id is None or held[0] != calculation_revision_id:
            return None
        return held[1]


CALCULATION_NOTES: Final[CalculationNoteStore] = CalculationNoteStore()
"""The process's one holder of the latest calculation's diagnostics per declaration."""


def _require_total_levels() -> None:
    """Refuse a diagnostic reason with no place on the scale, or a place for a reason that no longer exists."""
    reasons = set(get_args(CalculationSourceDiagnosticReason))
    if set(CALCULATION_NOTE_ATTENTION) != reasons:
        missing = sorted(reasons - set(CALCULATION_NOTE_ATTENTION))
        extra = sorted(set(CALCULATION_NOTE_ATTENTION) - reasons)
        raise ValueError(f"calculation note levels must cover every reason; missing={missing} extra={extra}")
    blocking_level = frozenset(reason for reason, level in CALCULATION_NOTE_ATTENTION.items() if level is _B)
    if blocking_level.symmetric_difference(BLOCKING_REASONS):
        raise ValueError("the blocking level holds exactly the reasons the application refuses filing on")
    if ModeloFormAttention.CONFIRM in CALCULATION_NOTE_ATTENTION.values():
        raise ValueError("only an assumed box is confirmed; no calculation note waits for a confirmation")
    if not PRINTED_BOX_REASONS <= GATE_REFUSED_REASONS:
        raise ValueError("a reason that blocks only on a printed box must be one the gate refuses")
    if not set(_RECORD_NOTE_ACTIONS) <= RECORDS_REASONS:
        raise ValueError("a note with a door to its record is a note whose cause is in the records")
    if DERIVED_GATE_REASONS & (reasons | set(CALCULATION_NOTE_ATTENTION) | BLOCKING_REASONS):
        raise ValueError("a derived gate reason is never a diagnostic reason, a placed note or a persisted one")


_require_total_levels()


__all__ = [
    "BLOCKING_REASONS",
    "CALCULATION_NOTES",
    "CALCULATION_NOTE_ATTENTION",
    "CALCULATION_SCREEN_OUTDATED_REASON",
    "CHECK_REFUSED_REASONS",
    "DERIVED_GATE_REASONS",
    "EXPORT_REFUSED_REASONS",
    "FILED_BEFORE_GRADE_CAP_REASON",
    "GATE_REFUSED_REASONS",
    "PRINTED_BOX_REASONS",
    "PROFILE_REASONS",
    "RECORDS_REASONS",
    "REOPEN_HINT_LOCALE_KEY",
    "STALE_LOCALE_KEY",
    "UNWORKED_BOX_REASONS",
    "CalculationNoteStore",
    "capped_value_proven_zero",
    "durable_binding_source",
    "fact_locale_key",
    "note_attention",
    "note_fact_text",
    "note_record_verdict",
    "read_element_names",
    "read_recorded_notes",
    "what_locale_key",
    "what_to_do_locale_key",
    "with_element_names",
]
