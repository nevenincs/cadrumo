"""Registry error types for AEAT legal calculation definitions.

This module provides classmethod factories on :class:`RegistryValidationError`
and :class:`RegistrySnapshotError` for each canonical raise scenario. The
factory pattern pins the context-dict keys downstream consumers
(``aeat.core.errors._registry`` template renderer, CLI JSON emit via
``SchemaEnvelope``, i18n locales referencing keys by name) rely on.

The existing ``raise RegistryValidationError(message, context=...)`` shape
stays valid for one-off scenarios that haven't been promoted to canonical
factories yet; migration is additive and non-breaking.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Self

from ....core.errors import AeatError, CoreValidationError


class RegistryError(AeatError, ValueError):
    """Base error for registry loading, resolution, and validation."""


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
        binding_id: str,
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
    def for_enum_binding_value_missing(cls, *, binding_id: str, op: str) -> Self:
        """A required enum binding has no supplied value at evaluation time.

        Canonical keys: ``binding_id``, ``op``.
        """
        return cls(
            f"enum binding {binding_id!r} has no supplied value; required by {op}",
            translated_message="errors.calc.enum_binding_value_missing",
            context={"binding_id": binding_id, "op": op},
        )

    @classmethod
    def for_binding_value_missing(cls, *, binding_id: str) -> Self:
        """A required binding has no supplied value at evaluation time."""
        return cls(
            f"binding {binding_id!r} has no supplied value",
            translated_message="errors.calc.binding_value_missing",
            context={"binding_id": binding_id},
        )

    @classmethod
    def for_relation_value_missing(cls, *, relation_id: str) -> Self:
        """A required relation has no supplied value at evaluation time."""
        return cls(
            f"relation {relation_id!r} has no supplied value",
            translated_message="errors.calc.relation_value_missing",
            context={"relation_id": relation_id},
        )

    @classmethod
    def for_casilla_referenced_before_evaluation(cls, *, casilla_id: str) -> Self:
        """A formula referenced a casilla that hasn't been evaluated yet."""
        return cls(
            f"casilla {casilla_id!r} referenced before evaluation",
            translated_message="errors.calc.casilla_referenced_before_evaluation",
            context={"casilla_id": casilla_id},
        )

    @classmethod
    def for_unknown_input_casillas(cls, *, casilla_ids: Sequence[str]) -> Self:
        """Inputs to the runtime referenced casilla ids absent from the revision."""
        ids = sorted(casilla_ids)
        return cls(
            f"unknown registry input casilla ids: {ids!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": _csv(ids)},
        )

    @classmethod
    def for_computed_supplied_as_input(cls, *, casilla_ids: Sequence[str]) -> Self:
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
        revision_id: str | None,
    ) -> None:
        """Construct the no-revision-for-period error.

        Args:
            modelo_id: The modelo whose revisions were searched.
            filing_year: The AEAT filing year used to narrow revisions.
            period: The period token that found no covering revision.
            revision_id: The optional explicit revision-id filter, if any.
        """
        self.modelo_id: str = modelo_id
        self.filing_year: int = filing_year
        self.period: str = period
        self.revision_id: str | None = revision_id
        super().__init__(
            f"modelo {modelo_id}: no revision for year={filing_year!r} period={period!r} revision={revision_id!r}",
            translated_message="errors.snapshot.no_revision_for_period",
            context={
                "modelo_id": modelo_id,
                "filing_year": filing_year,
                "period": period,
                "revision_id": revision_id if revision_id is not None else "",
            },
        )


class AmbiguousRevisionSelectionError(RegistrySnapshotError):
    """More than one registry revision matches the temporal natural key.

    Raised by :func:`select_revision` when the constraints select two or
    more candidate revisions. Carries the candidate revision ids as a
    structured, already-sorted tuple so a consumer can list them in an
    operator refusal without re-parsing the message. Catchable as
    :class:`RegistrySnapshotError`.

    Structured attributes: ``modelo_id``, ``candidate_ids``.
    """

    def __init__(self, *, modelo_id: str, candidate_ids: Iterable[str]) -> None:
        """Construct the ambiguous-revision-selection error.

        Args:
            modelo_id: The modelo whose revisions were searched.
            candidate_ids: The matching revision ids; stored sorted as a
                tuple on ``candidate_ids``.
        """
        ids = tuple(sorted(candidate_ids))
        self.modelo_id: str = modelo_id
        self.candidate_ids: tuple[str, ...] = ids
        super().__init__(
            f"modelo {modelo_id}: ambiguous revision selection: {', '.join(ids)}",
            translated_message="errors.snapshot.ambiguous_revision_selection",
            context={"modelo_id": modelo_id, "candidate_ids": _csv(ids)},
        )


class CasillaConstraintViolationError(RegistryError):
    """Raised when a computed casilla value falls outside its declared constraints.

    The constraint set is ``casilla.constraints`` (sign, min_value, max_value).
    The error envelope carries ``casilla_id``, the offending ``value``, the
    offended constraint clause, and the casilla's ``legal_refs`` so the
    operator sees the BOE permalink that justifies the rule.
    """
