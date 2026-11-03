"""Registry-build refusals for a revision's credit reconciliation, and the reads its consumers share.

Each entry is checked against the rest of its revision, never against a list of
casilla numbers or modelos:

* the casilla must belong to the derived credit set, the operands of the
  payments-on-account total;
* the value source must be the casilla's own bound binding, or the formula that
  computes it;
* a binding value source must be admitted to the borrador only as
  ``cross_check_only``, so an informative prefill never becomes the credit;
* a payer-record cross-check must name an income class whose credit roles
  include the casilla's role;
* a borrador cross-check must name a binding a borrador snapshot may hold;
* a ledger cross-check must name a ledger binding that is not a withholding
  agent's own payer-side figure;
* a filed-observation cross-check must name a casilla that records withholding
  suffered (:func:`filed_observation_source_failures`, run over the whole tree);
* an operand must be an operand of the value source's formula.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from ....core.aggregation import LEDGER_BINDING_SOURCE_KINDS
from ....core.casilla_id import CasillaId
from ....core.hashing import content_hash_hex
from .binding_borrador_participation import BorradorParticipation
from .binding_provider_registration import BINDING_PROVIDER_REGISTRATIONS
from .binding_targets import revision_bindings_by_id
from .binding_terminal_origin import TerminalOriginClass
from .credit_reconciliation import (
    BorradorCrossCheck,
    CreditReconciliationEntry,
    CreditReconciliationOperand,
    FiledObservationCrossCheck,
    LedgerCrossCheck,
    RetencionSoportadaCrossCheck,
    WithholdingSide,
)
from .retencion_soportada_bindings import RETENCION_SOPORTADA_CREDIT_ROLES, credit_casilla_ids
from .runtime_graph import expression_binding_refs, expression_casilla_refs
from .schema_input_kind import InputKind

if TYPE_CHECKING:
    from .schema import BindingDefinition, FormulaDefinition, ModeloRevision
    from .schema_surfaces import CasillaDefinition

__all__ = [
    "credit_reconciliation_digest",
    "credit_reconciliation_revision_failures",
    "filed_observation_source_failures",
]

_LEDGER_CROSS_CHECK_REFUSED_ORIGINS: frozenset[TerminalOriginClass] = frozenset(
    {TerminalOriginClass.PERCEPTOR_OBSERVATION}
)
"""Terminal origins of the payer-side stores, whose figures are withholding practised on others."""


def credit_reconciliation_digest(revision: ModeloRevision) -> str:
    """Return the content digest of the revision's credit reconciliation declarations, in declaration order."""
    return content_hash_hex([entry.model_dump(mode="json") for entry in revision.credit_reconciliation])


def _formulas_by_id(revision: ModeloRevision) -> dict[str, FormulaDefinition]:
    return {str(formula.id): formula for formula in revision.formulas}


def _value_source_failures(
    entry: CreditReconciliationEntry,
    casilla: CasillaDefinition,
    bindings: Mapping[str, BindingDefinition],
    owner: str,
) -> list[str]:
    source = entry.value_source
    if source.binding is not None:
        if casilla.input_kind is not InputKind.BOUND or casilla.binding != source.binding:
            return [f"{owner}: value source binding {source.binding!r} is not the binding bound to the casilla"]
        binding = bindings.get(str(source.binding))
        if binding is None:
            return [f"{owner}: value source binding {source.binding!r} is not declared"]
        if not binding.aeat_prefilled or binding.borrador_participation is not BorradorParticipation.CROSS_CHECK_ONLY:
            return [
                f"{owner}: value source binding {source.binding!r} must be aeat_prefilled with "
                "borrador_participation = 'cross_check_only', so the borrador only cross-checks the credit",
            ]
        return []
    if casilla.input_kind is not InputKind.COMPUTED or casilla.formula != source.formula:
        return [f"{owner}: value source formula {source.formula!r} is not the formula computing the casilla"]
    return []


def _operand_failures(
    operand: CreditReconciliationOperand | None,
    entry: CreditReconciliationEntry,
    formulas: Mapping[str, FormulaDefinition],
    owner: str,
) -> list[str]:
    if operand is None:
        return []
    formula = None if entry.value_source.formula is None else formulas.get(str(entry.value_source.formula))
    if formula is None:
        return [f"{owner}: an operand is named, but the value source is not a formula"]
    if operand.casilla_id is not None and operand.casilla_id not in expression_casilla_refs(formula.expression):
        return [f"{owner}: operand casilla {operand.casilla_id!r} is not an operand of formula {formula.id!r}"]
    if operand.binding is not None and operand.binding not in expression_binding_refs(formula.expression):
        return [f"{owner}: operand binding {operand.binding!r} is not an operand of formula {formula.id!r}"]
    return []


def _cross_check_failures(
    entry: CreditReconciliationEntry,
    casilla: CasillaDefinition,
    bindings: Mapping[str, BindingDefinition],
    owner: str,
) -> list[str]:
    failures: list[str] = []
    for cross_check in entry.cross_checks:
        if isinstance(cross_check, RetencionSoportadaCrossCheck):
            if casilla.semantic_role not in RETENCION_SOPORTADA_CREDIT_ROLES[cross_check.income_class]:
                failures.append(
                    f"{owner}: income class {cross_check.income_class.value!r} does not credit a casilla "
                    f"with role {casilla.semantic_role!r}",
                )
            continue
        if isinstance(cross_check, FiledObservationCrossCheck):
            continue
        binding = bindings.get(str(cross_check.binding))
        if binding is None:
            failures.append(f"{owner}: cross-check binding {cross_check.binding!r} is not declared")
            continue
        if isinstance(cross_check, BorradorCrossCheck) and not binding.aeat_prefilled:
            failures.append(
                f"{owner}: borrador cross-check binding {cross_check.binding!r} is not aeat_prefilled, "
                "so no borrador snapshot can hold a value for it",
            )
        if isinstance(cross_check, LedgerCrossCheck):
            failures.extend(_ledger_cross_check_failures(binding, owner))
    return failures


def _ledger_cross_check_failures(binding: BindingDefinition, owner: str) -> list[str]:
    registration = BINDING_PROVIDER_REGISTRATIONS.get(binding.source)
    if registration is None or binding.source not in LEDGER_BINDING_SOURCE_KINDS:
        return [f"{owner}: ledger cross-check binding {binding.id!r} is not a ledger binding"]
    if registration.permitted_terminal_origins & _LEDGER_CROSS_CHECK_REFUSED_ORIGINS:
        return [
            f"{owner}: ledger cross-check binding {binding.id!r} reads a payer-side store, whose figures are "
            "withholding practised on others and never a credit",
        ]
    return []


def _entry_failures(
    entry: CreditReconciliationEntry,
    *,
    casillas: Mapping[CasillaId, CasillaDefinition],
    credit_set: frozenset[CasillaId],
    bindings: Mapping[str, BindingDefinition],
    formulas: Mapping[str, FormulaDefinition],
) -> list[str]:
    owner = f"credit reconciliation of casilla {entry.casilla_id!r}"
    casilla = casillas.get(entry.casilla_id)
    if casilla is None:
        return [f"{owner}: the casilla is not declared"]
    if entry.casilla_id not in credit_set:
        return [f"{owner}: the casilla is not an operand of the payments-on-account total"]
    failures = _value_source_failures(entry, casilla, bindings, owner)
    failures.extend(_cross_check_failures(entry, casilla, bindings, owner))
    for cross_check in entry.cross_checks:
        failures.extend(_operand_failures(cross_check.operand, entry, formulas, owner))
    return failures


def _duplicate_entry_failures(entries: Iterable[CreditReconciliationEntry]) -> list[str]:
    seen: set[CasillaId] = set()
    failures: list[str] = []
    for entry in entries:
        if entry.casilla_id in seen:
            failures.append(f"credit reconciliation declares casilla {entry.casilla_id!r} twice")
        seen.add(entry.casilla_id)
    return failures


def filed_observation_source_failures(
    cross_check: FiledObservationCrossCheck,
    source_revisions: Iterable[ModeloRevision],
    *,
    owner: str,
) -> tuple[str, ...]:
    """Refuse a filed-observation cross-check whose casilla does not record withholding suffered.

    ``source_revisions`` are the revisions of the source modelo that declare the
    cross-check's period. The casilla must be declared by at least one of them,
    and every one that declares it must mark it ``suffered``: an undeclared or
    practised side is a withholding agent's figure and never a credit.
    """
    declaring = [
        casilla for revision in source_revisions for casilla in revision.casillas if casilla.id == cross_check.casilla
    ]
    if not declaring:
        return (
            f"{owner}: filed-observation casilla {cross_check.casilla!r} of modelo {cross_check.modelo} "
            f"period {cross_check.period!r} is not declared by any revision of that modelo",
        )
    if any(casilla.withholding_side is not WithholdingSide.SUFFERED for casilla in declaring):
        return (
            f"{owner}: filed-observation casilla {cross_check.casilla!r} of modelo {cross_check.modelo} is not "
            "declared withholding_side = suffered, so it cannot corroborate a credit",
        )
    return ()


def credit_reconciliation_revision_failures(revision: ModeloRevision) -> tuple[str, ...]:
    """Return every refusal the revision's credit reconciliation earns; empty when it declares none."""
    entries = revision.credit_reconciliation
    if not entries:
        return ()
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    credit_set = credit_casilla_ids(revision)
    bindings = {str(binding_id): binding for binding_id, binding in revision_bindings_by_id(revision).items()}
    formulas = _formulas_by_id(revision)
    failures = _duplicate_entry_failures(entries)
    for entry in entries:
        failures.extend(
            _entry_failures(entry, casillas=casillas, credit_set=credit_set, bindings=bindings, formulas=formulas)
        )
    return tuple(failures)
