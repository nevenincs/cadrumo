"""Registry error types for AEAT legal calculation definitions.

This module provides classmethod factories on :class:`RegistryValidationError`
and :class:`RegistrySnapshotError` for each canonical raise scenario. The
factory pattern pins the context-dict keys downstream consumers
(``cadrumo.core.errors._registry`` template renderer, CLI JSON emit via
``SchemaEnvelope``, i18n locales referencing keys by name) rely on.

The existing ``raise RegistryValidationError(message, context=...)`` shape
stays valid for one-off scenarios that haven't been promoted to canonical
factories yet; migration is additive and non-breaking.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from ....core import CasillaId, Modelo
from ....core.errors.hierarchy import CadrumoError, CoreValidationError, TerminalPreconditionErrorMixin
from .ids import BindingId, RelationId, RevisionId


class RegistryFailureCondition(StrEnum):
    """Domain-owned failed-condition identities for registry refusals.

    These names identify facts the registry can observe.  They deliberately do
    not encode a command or an outcome: application policy decides whether a
    live surface has a canonical action, and the CLI resolves that action.
    """

    TAXPAYER_MODEL_DECLARED = "registry.applicability.taxpayer_model.declared"
    MODELO_202_INCN_DECLARED = "registry.applicability.modelo_202.incn.declared"
    QUERY_FILING_YEAR_SCOPED = "registry.query.filing_year.scoped"
    QUERY_CASILLA_DECLARED = "registry.query.casilla.declared"
    SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT = "registry.snapshot.authority_grade.sufficient"
    SNAPSHOT_EXPORT_LAYOUT_DECLARED = "registry.snapshot.export_layout.declared"
    TREE_QUIESCENT = "registry.tree.concurrent_write.quiescent"


@dataclass(frozen=True)
class RegistryFailureClassification:
    """One registry-observed failed condition and its locale-neutral facts."""

    condition: RegistryFailureCondition
    facts: Mapping[str, str | int | bool]


class RegistryError(TerminalPreconditionErrorMixin[object], CadrumoError, ValueError):
    """Base error retaining domain facts for a higher-layer action projection."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        registry_failure: RegistryFailureClassification | None = None,
        precondition_verdict: object | None = None,
    ) -> None:
        """Keep a domain classification without importing application policy."""
        super().__init__(
            message=message,
            context=context,
            translated_message=translated_message,
            precondition_verdict=precondition_verdict,
        )
        self._registry_failure = registry_failure

    @property
    def registry_failure(self) -> RegistryFailureClassification | None:
        """Return the domain fact classification for an application to resolve."""
        return self._registry_failure


class RegistryLoadError(RegistryError):
    """Raised when registry files cannot be parsed into strict schema objects."""


def _csv(items: Iterable[str]) -> str:
    """Stable comma-join used by every context-key serialisation.

    Callers pass already-sorted tuples where order matters; this
    helper just centralises the ``", ".join`` style so a future
    formatting change lands in one place.
    """
    return ",".join(items)


class RegistryValidationError(RegistryError, CoreValidationError):
    """Raised when registry definitions are incomplete or contradictory.

    Inherits from CoreValidationError to participate in the shared
    CoreValidationError catch surface across all layers. RegistryError
    already provides ValueError co-inheritance.

    Canonical raise scenarios route through one of the ``for_*``
    classmethod factories so the context-dict keys consumed by
    locale templates and CLI JSON emit are pinned to a named
    contract per scenario.
    """

    @classmethod
    def for_unsupported_op(cls, op: str) -> Self:
        """Formula expression uses an op the runtime does not implement.

        Canonical key: ``op``. Twelve raise sites today.
        """
        return cls(
            f"formula expression uses unsupported op {op!r}",
            translated_message="errors.calc.unsupported_op",
            context={"op": op},
        )

    @classmethod
    def for_unsupported_comparison_op(cls, op: str) -> Self:
        """``compare(...)`` received an op name outside the closed comparison set."""
        return cls(
            f"formula expression uses unsupported comparison op {op!r}",
            translated_message="errors.calc.unsupported_comparison_op",
            context={"op": op},
        )

    @classmethod
    def for_unknown_parameter(cls, *, parameter_id: str) -> Self:
        """A formula referenced a parameter id absent from the revision.

        Canonical key: ``parameter_id``. Seven raise sites today.
        """
        return cls(
            f"parameter {parameter_id!r} not registered",
            translated_message="errors.calc.parameter_unknown",
            context={"parameter_id": parameter_id},
        )

    @classmethod
    def for_dispatch_key_unknown(
        cls,
        *,
        op: str,
        binding_id: BindingId,
        dispatch_key: str,
        available_keys: Sequence[str],
    ) -> Self:
        """A formula's dispatch_table is missing the resolved enum key.

        Canonical keys: ``op``, ``binding_id``, ``dispatch_key``,
        ``available_keys``. Three raise sites today (lookup_bracket_by_ccaa
        / lookup_parameter_by_entity_type / lookup_bracket_by_entity_type).
        """
        return cls(
            f"{op} dispatch_table is missing key {dispatch_key!r} (declared keys: {sorted(available_keys)})",
            translated_message="errors.calc.dispatch_key_unknown",
            context={
                "op": op,
                "binding_id": binding_id,
                "dispatch_key": dispatch_key,
                "available_keys": _csv(sorted(available_keys)),
            },
        )

    @classmethod
    def for_lookup_dispatch_arg_kind(
        cls,
        *,
        op: str,
        position: str,
        expected_kind: str,
    ) -> Self:
        """A lookup-dispatch op's positional arg has the wrong leaf kind.

        Canonical keys: ``op``, ``position``, ``expected_kind``. Four
        raise sites today.
        """
        return cls(
            f"formula op {op!r} requires {position} to be a {expected_kind} leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": position, "expected_kind": expected_kind},
        )

    @classmethod
    def for_lookup_dispatch_arg_count(cls, *, op: str, expected: str) -> Self:
        """A lookup-dispatch op was passed the wrong number of args.

        Canonical keys: ``op``, ``expected``.
        """
        return cls(
            f"formula op {op!r} expects {expected} args",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": expected},
        )

    @classmethod
    def for_dispatch_parameter_kind(
        cls,
        *,
        parameter_id: str,
        op: str,
    ) -> Self:
        """A dispatched parameter has the wrong ``data_type`` for its op."""
        return cls(
            f"parameter {parameter_id!r} has wrong data_type for {op!r}",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": parameter_id, "op": op},
        )

    @classmethod
    def for_enum_binding_value_missing(cls, *, binding_id: BindingId, op: str) -> Self:
        """A required enum binding has no supplied value at evaluation time.

        Canonical keys: ``binding_id``, ``op``.
        """
        return cls(
            f"enum binding {binding_id!r} has no supplied value; required by {op}",
            translated_message="errors.calc.enum_binding_value_missing",
            context={"binding_id": binding_id, "op": op},
        )

    @classmethod
    def for_binding_value_missing(cls, *, binding_id: BindingId) -> Self:
        """A required binding has no supplied value at evaluation time."""
        return cls(
            f"binding {binding_id!r} has no supplied value",
            translated_message="errors.calc.binding_value_missing",
            context={"binding_id": binding_id},
        )

    @classmethod
    def for_relation_value_missing(cls, *, relation_id: RelationId) -> Self:
        """A required relation has no supplied value at evaluation time."""
        return cls(
            f"relation {relation_id!r} has no supplied value",
            translated_message="errors.calc.relation_value_missing",
            context={"relation_id": relation_id},
        )

    @classmethod
    def for_casilla_referenced_before_evaluation(cls, *, casilla_id: CasillaId) -> Self:
        """A formula referenced a casilla that hasn't been evaluated yet."""
        return cls(
            f"casilla {casilla_id!r} referenced before evaluation",
            translated_message="errors.calc.casilla_referenced_before_evaluation",
            context={"casilla_id": casilla_id},
        )

    @classmethod
    def for_unknown_input_casilla_ids(cls, *, casilla_ids: Sequence[CasillaId]) -> Self:
        """Inputs to the runtime referenced casilla ids absent from the revision."""
        ids = sorted(casilla_ids)
        return cls(
            f"unknown registry input casilla ids: {ids!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": _csv(ids)},
        )

    @classmethod
    def for_computed_supplied_as_input(cls, *, casilla_ids: Sequence[CasillaId]) -> Self:
        """Inputs to the runtime supplied values for computed casillas."""
        ids = sorted(casilla_ids)
        return cls(
            f"computed registry casillas cannot be supplied as inputs: {ids!r}",
            translated_message="errors.calc.computed_supplied_as_input",
            context={"casilla_ids": _csv(ids)},
        )

    @classmethod
    def for_bracket_no_window(cls, *, parameter_id: str, as_of: str) -> Self:
        """A bracket-table parameter has no bracket valid for the requested date."""
        return cls(
            f"parameter {parameter_id!r} has no bracket valid for {as_of}",
            translated_message="errors.calc.bracket_no_window",
            context={"parameter_id": parameter_id, "as_of": as_of},
        )

    @classmethod
    def for_bracket_no_coverage(cls, *, parameter_id: str, base: str) -> Self:
        """A bracket-table parameter has no bracket covering the requested base."""
        return cls(
            f"parameter {parameter_id!r} has no bracket covering base {base}",
            translated_message="errors.calc.bracket_no_coverage",
            context={"parameter_id": parameter_id, "base": base},
        )

    @classmethod
    def for_bracket_negative_base(cls, *, parameter_id: str, base: str) -> Self:
        """A bracket-table lookup received a negative base value."""
        return cls(
            f"parameter {parameter_id!r} lookup_bracket received negative base {base}",
            translated_message="errors.calc.bracket_negative_base",
            context={"parameter_id": parameter_id, "base": base},
        )

    @classmethod
    def for_divide_by_zero(cls) -> Self:
        """A formula expression divides by zero at runtime."""
        return cls(
            "formula expression divides by zero",
            translated_message="errors.calc.divide_by_zero",
        )

    @classmethod
    def for_empty_expression(cls) -> Self:
        """A formula expression contains no leaf or op (empty)."""
        return cls(
            "empty formula expression",
            translated_message="errors.calc.empty_expression",
        )

    @classmethod
    def for_prorrata_activity_rows_incomplete(cls, *, ejercicio: int) -> Self:
        """An applicable Modelo 303 ejercicio is missing a DP30305 activity row.

        An absent row collection is honest only when the register's regime
        says prorrata does not apply for ``ejercicio``; once it applies, a
        partial collection must fail before a target export file can mask the
        under-declaration. Canonical key: shares the filing package's
        pre-existing ``application.filing.m303_prorrata_activity_rows.errors.
        activity_rows_incomplete`` catalogue entry, which already carries the
        operator-facing sentence in all four locales.
        """
        return cls(
            f"modelo 303 per-activity prorrata rows are incomplete for ejercicio {ejercicio}",
            translated_message="application.filing.m303_prorrata_activity_rows.errors.activity_rows_incomplete",
            context={
                "modelo": Modelo.M303.value,
                "filing_year": ejercicio,
                "required_slot_first": 1,
                "required_slot_last": 5,
            },
        )


class RegistrySnapshotError(RegistryError):
    """Raised when a filing-grade snapshot cannot be selected.

    The single canonical raise scenario is `for_modelo_not_registered`
    at the `_authority.modelo` boundary; the bare constructor stays
    valid for one-off scenarios not yet promoted to a factory.

    Two temporal-selection scenarios carry structured context as
    dedicated subclasses (:class:`NoRevisionForPeriodError`,
    :class:`AmbiguousRevisionSelectionError`) so a consumer dispatches
    by ``except`` type rather than parsing the human-readable message.
    Both subclass this type, so every existing ``except
    RegistrySnapshotError`` site catches them unchanged.
    """

    @classmethod
    def for_modelo_not_registered(cls, *, modelo_id: str) -> Self:
        """The requested modelo id has no registered revision."""
        return cls(
            f"modelo {modelo_id!r} is not present in the calculation registry",
            translated_message="errors.snapshot.modelo_not_registered",
            context={"modelo_id": modelo_id},
        )


class NoRevisionForPeriodError(RegistrySnapshotError):
    """No registry revision matches the requested temporal natural key.

    Raised by :func:`select_revision` when the (modelo, filing year,
    period, optional date window, optional revision id) constraints
    select zero candidate revisions. Carries the natural-key components
    as structured context so a consumer (e.g. the ``config profile
    preflight`` resolver) can build an instructive refusal without
    parsing the message. Catchable as :class:`RegistrySnapshotError`.

    Structured attributes: ``modelo_id``, ``filing_year``,
    ``period``, ``revision_id``.
    """

    def __init__(
        self,
        *,
        modelo_id: str,
        filing_year: int,
        period: str,
        revision_id: RevisionId | None,
        available_revision_ids: Iterable[str],
    ) -> None:
        """Construct the no-revision-for-period error.

        Args:
            modelo_id: The modelo whose revisions were searched.
            filing_year: The AEAT filing year used to narrow revisions.
            period: The period token that found no covering revision.
            revision_id: The optional explicit revision-id filter, if any.
            available_revision_ids: Every revision the modelo declares, stored
                sorted on ``available_revision_ids``. REQUIRED rather than
                defaulted: a refusal that cannot say what IS available reads as
                a malfunction, and the operator's real question here is which
                filing years exist at all. Both raisers hold the modelo's
                revision collection already, so there is no case where it is
                genuinely unknown -- and a default would let a future raiser
                silently ship the uninformative form.
        """
        available = tuple(sorted(available_revision_ids))
        self.modelo_id: str = modelo_id
        self.filing_year: int = filing_year
        self.period: str = period
        self.revision_id: RevisionId | None = revision_id
        self.available_revision_ids: tuple[str, ...] = available
        detail = f"modelo {modelo_id}: no revision for year={filing_year!r} period={period!r} revision={revision_id!r}"
        if available:
            detail = f"{detail}; modelo {modelo_id} declares: {', '.join(available)}"
        super().__init__(
            detail,
            translated_message="errors.snapshot.no_revision_for_period",
            context={
                "modelo_id": modelo_id,
                "filing_year": filing_year,
                "period": period,
                "revision_id": revision_id if revision_id is not None else "",
                "available_revision_ids": _csv(available),
            },
        )


class AmbiguousRevisionSelectionError(RegistrySnapshotError):
    """More than one registry revision matches the temporal natural key.

    Raised by :func:`select_revision` when the constraints select two or
    more candidate revisions. Carries the candidate revision ids as a
    structured, already-sorted tuple so a consumer can list them in an
    operator refusal without re-parsing the message. Catchable as
    :class:`RegistrySnapshotError`.

    THE REMEDY IS RAISER-SELECTED, through the locale key rather than through a
    second channel beside it. Two selectors raise this: the year-only one, where
    the fix is to supply a period or an as-of date, and the period-scoped one,
    where the caller has already supplied a period and that advice would send an
    operator to redo what they just did. No single string is correct for both,
    so the year-only raiser names its own ``translated_message`` and the
    period-scoped raiser keeps the shared default, which states the collision
    without prescribing an action the operator cannot take.

    Structured attributes: ``modelo_id``, ``candidate_ids``, ``filing_year``.
    """

    def __init__(
        self,
        *,
        modelo_id: str,
        candidate_ids: Iterable[str],
        filing_year: int | None = None,
        reason: str | None = None,
        translated_message: str = "errors.snapshot.ambiguous_revision_selection",
    ) -> None:
        """Construct the ambiguous-revision-selection error.

        Args:
            modelo_id: The modelo whose revisions were searched.
            candidate_ids: The matching revision ids; stored sorted as a
                tuple on ``candidate_ids``.
            filing_year: Optional filing year the ambiguity arose for. Named in
                the fallback text and carried structurally, because "two
                revisions match" is far more actionable once the reader knows
                WHICH year is doubly covered.
            reason: Optional raiser-supplied explanation of WHY the year is
                ambiguous, appended to the fallback text.
            translated_message: Locale key for the operator-facing refusal. The
                default states the collision alone; the year-only selector names
                a key whose text also carries the remedy, because the two
                selectors have opposite remedies and one shared string is
                correct for neither.
        """
        ids = tuple(sorted(candidate_ids))
        self.modelo_id: str = modelo_id
        self.candidate_ids: tuple[str, ...] = ids
        self.filing_year: int | None = filing_year
        scope = f"modelo {modelo_id}" if filing_year is None else f"modelo {modelo_id} filing year {filing_year}"
        detail = f"{scope}: ambiguous revision selection: {', '.join(ids)}"
        if reason:
            detail = f"{detail} -- {reason}"
        context: dict[str, object] = {"modelo_id": modelo_id, "candidate_ids": _csv(ids)}
        if filing_year is not None:
            context["filing_year"] = filing_year
        super().__init__(
            detail,
            translated_message=translated_message,
            context=context,
        )


class CasillaConstraintViolationError(RegistryError):
    """Raised when a computed casilla value falls outside its declared constraints.

    The constraint set is ``casilla.constraints`` (sign, min_value, max_value).
    The error envelope carries ``casilla_id``, the offending ``value``, the
    offended constraint clause, and the casilla's ``legal_refs`` so the
    operator sees the BOE permalink that justifies the rule.
    """
