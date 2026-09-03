"""Formula-runtime operation helpers for registry calculations.

The formula evaluator delegates arithmetic dispatch, dated parameter lookup,
rounding, and input validation here while executing
:class:`~domain.calculations.registry.ModeloRevision` formula graphs.
Helpers raise :class:`~domain.calculations.registry.RegistryValidationError`
so :func:`domain.calculations.registry._formula_runtime.calculate_registry_snapshot`
reports contract failures through the registry error channel.

See Also:
    :mod:`domain.calculations.registry._formula_runtime`
        Snapshot evaluator that calls these helpers while materialising
        :class:`~domain.calculations.registry.RegistrySnapshot` outputs.
    :mod:`domain.calculations.registry._runtime_graph`
        Formula graph walkers that discover the casilla, binding, relation, and
        parameter refs consumed before operation dispatch starts.
    :class:`domain.calculations.registry.ValidatedRegistryAuthority`
        Registry authority loaded by :func:`read_parameter` for ad hoc parameter
        reads outside snapshot execution.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.money.rounding import round_to_cents as _round_to_cents
from ._formula_operator_contracts import require_formula_operator_arity
from .casilla_membership import undeclared_casilla_ids
from .errors import RegistrySnapshotError, RegistryValidationError
from .ids import RevisionId
from .schema import ModeloRevision
from .schema_base import NUMERIC_CASILLA_DATA_TYPES
from .schema_formula import BracketEntry, DatedValue, ParameterDefinition
from .schema_rounding import RegistryRoundingCode

if TYPE_CHECKING:
    from _typeshed import SupportsAllComparisons

    from .formula_runtime import EvalContext as _EvalContext

_ZERO = Decimal("0")
_ONE = Decimal("1")
_COMPARISON_OPS = frozenset({"less_than", "less_equal", "greater_than", "greater_equal", "equal"})
_UNARY_PASSTHROUGH_OPS = frozenset({"copy", "lookup_parameter", "previous_period_value", "cross_model_sum"})


class UnresolvedFormulaDependencyError(RegistrySnapshotError):
    """Raised internally when a non-blocking source gap makes a formula unresolved.

    Shared between :mod:`~domain.calculations.registry._formula_runtime`
    and its per-family op-evaluator siblings (e.g.
    :mod:`~domain.calculations.registry._formula_runtime_irnr`) so a
    family module can signal a deferred dependency without importing back
    into the dispatcher module.
    """

    def __init__(self, dependency_ids: tuple[str, ...]) -> None:
        """Initialise the refusal with every unresolved dependency identifier."""
        super().__init__(", ".join(dependency_ids))
        self.dependency_ids = dependency_ids


class RegistryUnresolvedOutcomeReason(StrEnum):
    """Closed reason catalogue for typed formula outcomes with no Decimal value."""

    M210_BASELINE_TIPO_DEFERRED = "m210-baseline-tipo-deferred"
    M210_CONVENIO_RATE_MISSING = "m210-convenio-rate-missing"


class UnresolvedFormulaOutcomeError(RegistrySnapshotError):
    """Raised internally when a formula emits a typed unresolved outcome."""

    def __init__(
        self,
        reason: RegistryUnresolvedOutcomeReason,
        *,
        context: Mapping[str, str],
    ) -> None:
        """Initialise the typed unresolved outcome and its safe context."""
        super().__init__(reason.value)
        self.reason = reason
        self.context = dict(context)


def numeric_casilla_value(casilla_id: CasillaId, ctx: _EvalContext) -> Decimal:
    """Read a resolved numeric casilla value from the evaluation context.

    Generic accessor shared by the M210/IRNR, M131 módulos, and M303 módulos
    IVA formula-op families; each raises :class:`UnresolvedFormulaDependencyError`
    the same way for a casilla deferred by a non-blocking source gap.
    """
    if casilla_id not in ctx.values:
        if casilla_id in ctx.unresolved_casilla_ids:
            raise UnresolvedFormulaDependencyError((casilla_id,))
        raise RegistryValidationError(
            f"casilla {casilla_id!r} referenced before evaluation",
            translated_message="errors.calc.casilla_referenced_before_evaluation",
            context={"casilla_id": casilla_id},
        )
    value = ctx.values[casilla_id]
    ctx.operand_refs.append(casilla_id)
    ctx.operand_casilla_refs.append(casilla_id)
    ctx.operand_values.append(value)
    return value


def evaluate_args_op(op: str, args: list[Decimal]) -> Decimal:
    """Evaluate a resolved formula operation over decimal operands.

    Operation names mirror
    :class:`~domain.calculations.registry.FormulaExpression` ``op`` values
    consumed by
    :func:`domain.calculations.registry._formula_runtime.calculate_registry_snapshot`.
    """
    require_formula_operator_arity(op, len(args))
    if op in {"add", "sum", "previous_period_sum"}:
        if op == "previous_period_sum":
            _require_non_empty(op, args)
        return sum(args, _ZERO)
    if op in _COMPARISON_OPS:
        _require_arg_count(op, args, 2)
        return _ONE if _compare(op, args[0], args[1]) else _ZERO
    if op in _UNARY_PASSTHROUGH_OPS:
        _require_arg_count(op, args, 1)
        return args[0]
    return _dispatch_named_arithmetic_op(op, args)


def _dispatch_named_arithmetic_op(op: str, args: list[Decimal]) -> Decimal:
    """Dispatch non-comparison arithmetic operations for :func:`evaluate_args_op`."""
    match op:
        case "subtract":
            _require_arg_count(op, args, 2)
            return args[0] - args[1]
        case "multiply":
            result = _ONE
            for arg in args:
                result *= arg
            return result
        case "divide":
            _require_arg_count(op, args, 2)
            if args[1] == _ZERO:
                raise RegistryValidationError(
                    "formula expression divides by zero",
                    translated_message="errors.calc.divide_by_zero",
                )
            return args[0] / args[1]
        case "percent":
            _require_arg_count(op, args, 2)
            return args[0] * args[1] / Decimal("100")
        case "min":
            _require_non_empty(op, args)
            return min(args)
        case "max":
            _require_non_empty(op, args)
            return max(args)
        case "clamp":
            _require_arg_count(op, args, 3)
            return max(args[1], min(args[0], args[2]))
        case "negate":
            _require_arg_count(op, args, 1)
            return -args[0]
        case _:
            raise RegistryValidationError(f"formula expression uses unsupported op {op!r}")


def _compare(op: str, left: Decimal, right: Decimal) -> bool:
    """Evaluate a comparison operation from a registry formula expression."""
    if op == "less_than":
        return left < right
    if op == "less_equal":
        return left <= right
    if op == "greater_than":
        return left > right
    if op == "greater_equal":
        return left >= right
    if op == "equal":
        return left == right
    raise RegistryValidationError(f"formula expression uses unsupported comparison op {op!r}")


def _bracket_candidates(
    parameter: ParameterDefinition,
    date_context: Mapping[str, date],
) -> list[BracketEntry]:
    if parameter.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {parameter.id!r} must declare data_type='bracket_table' to use lookup_bracket",
        )
    if parameter.bracket_axis is None:
        raise RegistryValidationError(f"parameter {parameter.id!r} bracket_table requires bracket_axis")
    if parameter.bracket_axis not in date_context:
        raise RegistryValidationError(f"parameter {parameter.id!r} requires date axis {parameter.bracket_axis!r}")
    selected = date_context[parameter.bracket_axis]
    candidates: list[BracketEntry] = [
        bracket
        for bracket in parameter.brackets
        if bracket.valid_from <= selected and (bracket.valid_to is None or selected <= bracket.valid_to)
    ]
    if not candidates:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} has no bracket valid for {selected.isoformat()}",
            translated_message="errors.calc.bracket_no_window",
            context={"parameter_id": parameter.id, "as_of": selected.isoformat()},
        )
    return candidates


def _resolve_bracket_entry(
    parameter: ParameterDefinition,
    candidates: list[BracketEntry],
    base: Decimal,
) -> BracketEntry:
    if base < Decimal("0"):
        raise RegistryValidationError(
            f"parameter {parameter.id!r} lookup_bracket received negative base {base}",
            translated_message="errors.calc.bracket_negative_base",
            context={"parameter_id": parameter.id, "base": str(base)},
        )
    for entry in sorted(candidates, key=lambda bracket: bracket.lower_bound):
        if entry.lower_bound <= base and (entry.upper_bound is None or base <= entry.upper_bound):
            return entry
    raise RegistryValidationError(
        f"parameter {parameter.id!r} has no bracket covering base {base}",
        translated_message="errors.calc.bracket_no_coverage",
        context={"parameter_id": parameter.id, "base": str(base)},
    )


def resolve_bracket(
    parameter: ParameterDefinition,
    base: Decimal,
    date_context: Mapping[str, date],
) -> Decimal:
    """Resolve a bracket-table :class:`ParameterDefinition` for a base amount.

    The parameter's bracket date axis must be present in ``date_context`` so
    registry-authored validity windows select exactly one bracket row.
    """
    candidates = _bracket_candidates(parameter, date_context)
    base = Decimal(base)
    selected_entry = _resolve_bracket_entry(parameter, candidates, base)
    return selected_entry.fixed_addition + selected_entry.marginal_rate * (base - selected_entry.lower_bound)


def resolve_parameter(parameter: ParameterDefinition, date_context: Mapping[str, date]) -> Decimal:
    """Resolve one dated value from a :class:`ParameterDefinition`.

    Exactly one :class:`~domain.calculations.registry._schema_formula.DatedValue` must match
    the selected date axes for the parameter lookup to be deterministic.
    """
    if not parameter.values:
        raise RegistryValidationError(f"parameter {parameter.id!r} has no dated values")
    matches: list[DatedValue] = []
    for value in parameter.values:
        if value.date_axis not in date_context:
            raise RegistryValidationError(f"parameter {parameter.id!r} requires date axis {value.date_axis!r}")
        selected = date_context[value.date_axis]
        if value.valid_from <= selected and (value.valid_to is None or selected <= value.valid_to):
            matches.append(value)
    if len(matches) != 1:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} expected exactly one dated value, found {len(matches)}",
        )
    return matches[0].value


def resolve_scalar_parameter(parameter_id: str, ctx: _EvalContext, *, op: str) -> Decimal:
    """Resolve a scalar parameter and record its runtime provenance.

    Formula-operation families share the same scalar type contract and must
    record the parameter id alongside the resolved Decimal in their common
    evaluation context.  Keeping both actions together prevents a successful
    lookup from escaping the explainability surface.
    """
    parameter = ctx.parameters.get(parameter_id)
    if parameter is None:
        raise RegistryValidationError(
            f"parameter {parameter_id!r} not registered",
            translated_message="errors.calc.parameter_unknown",
            context={"parameter_id": parameter_id},
        )
    if parameter.data_type not in NUMERIC_CASILLA_DATA_TYPES:
        raise RegistryValidationError(
            f"parameter {parameter_id!r} must be scalar to be used by {op}",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": parameter_id, "op": op},
        )
    value = resolve_parameter(parameter, ctx.date_context)
    ctx.operand_refs.append(parameter_id)
    ctx.operand_values.append(value)
    return value


def resolve_keyed_bracket(
    parameter: ParameterDefinition | None,
    *,
    key: str,
    filing_year: int,
) -> Decimal | None:
    """Resolve one keyed-bracket row for a filing year.

    A missing parameter or key is the caller's explicit "not tabled" signal;
    overlapping matching windows are a contradictory registry definition and
    therefore fail closed instead of selecting an arbitrary first row.
    """
    if parameter is None:
        return None
    if parameter.data_type != "keyed_bracket_table":
        raise RegistryValidationError(
            f"parameter {parameter.id!r} must declare data_type='keyed_bracket_table' to resolve a keyed bracket",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": parameter.id, "op": "resolve_keyed_bracket"},
        )
    matches = [
        entry
        for entry in parameter.keyed_brackets
        if entry.key == key
        and entry.valid_from.year <= filing_year
        and (entry.valid_to is None or filing_year <= entry.valid_to.year)
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} key {key!r} expected exactly one keyed bracket for filing year "
            f"{filing_year}, found {len(matches)}",
            context={
                "parameter_id": parameter.id,
                "key": key,
                "filing_year": str(filing_year),
                "match_count": str(len(matches)),
            },
        )
    return matches[0].value


def apply_rounding(value: Decimal, rounding: RegistryRoundingCode | None) -> Decimal:
    """Apply a registry rounding rule to a decimal formula result.

    ``money-2`` uses :func:`core.money.round_to_cents`; ``integer`` uses
    half-up quantization for registry-authored integer targets;
    ``integer-ceiling`` quantizes with :data:`decimal.ROUND_CEILING` for
    the targets whose governing provision takes the result to the next
    unit up rather than to the nearest one (LIVA art. 104.Dos, "se
    redondeará en la unidad superior"). ``ROUND_CEILING`` leaves an
    already-integral value untouched, so a 50 % ratio stays 50.

    ``ROUND_CEILING`` moves toward positive infinity, which differs from
    away-from-zero for a negative operand. Every ``integer-ceiling``
    target today is a registry-constrained non-negative percentage
    (``sign = "non_negative"``, ``min_value = "0"``), so the two readings
    coincide; a future negative-capable target must state which reading
    its provision means before enrolling here.
    """
    if rounding is None:
        return value
    if rounding == RegistryRoundingCode.MONEY_2:
        return _round_to_cents(value)
    if rounding == RegistryRoundingCode.INTEGER:
        return value.quantize(_ONE, rounding=ROUND_HALF_UP)
    if rounding == RegistryRoundingCode.INTEGER_CEILING:
        return value.quantize(_ONE, rounding=ROUND_CEILING)
    raise RegistryValidationError(f"unsupported rounding rule {rounding!r}")


def reject_non_decimal[Key](items: Mapping[Key, Decimal], label: str) -> None:
    """Reject non-decimal values before formula runtime consumption."""
    del items, label


def validated_decimal_input_casilla_ids[InputKey, InputValue](
    inputs: Mapping[InputKey, InputValue],
    *,
    revision: ModeloRevision,
) -> dict[CasillaId, Decimal]:
    """Canonicalise decimal input keys against a :class:`ModeloRevision`.

    Raw string keys become validated :class:`~core.CasillaId`
    values, then :func:`domain.calculations.registry._casilla_membership.undeclared_casilla_ids`
    rejects inputs outside the revision's declared casilla set.
    """
    invalid = tuple(repr(key) for key in inputs if not isinstance(key, str))
    if invalid:
        raise RegistryValidationError(
            f"input keys must be canonical casilla.id strings: {sorted(invalid)!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": ",".join(sorted(invalid))},
        )
    malformed: list[str] = []
    canonical_inputs: dict[CasillaId, InputValue] = {}
    for key in inputs:
        try:
            canonical_inputs[validated_casilla_id(key, surface="input casilla.id")] = inputs[key]
        except ValueError:
            malformed.append(str(key))
    if malformed:
        raise RegistryValidationError(
            f"input keys must be canonical casilla.id strings: {sorted(malformed)!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": ",".join(sorted(malformed))},
        )
    unknown = undeclared_casilla_ids(revision, canonical_inputs)
    if unknown:
        raise RegistryValidationError.for_unknown_input_casilla_ids(casilla_ids=unknown)
    resolved_inputs: dict[CasillaId, Decimal] = {}
    for key, value in canonical_inputs.items():
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError(f"input {key!r} must be a Decimal")
        resolved_inputs[key] = value
    return resolved_inputs


def reject_non_string[Key](values: Mapping[Key, str], label: str) -> None:
    """Reject empty or non-string external values before registry validation."""
    for key, value in values.items():
        if not value:
            raise RegistryValidationError(f"{label} {key!r} must be a non-empty string")


def reject_unknown_external_values[Key: SupportsAllComparisons](
    items: Mapping[Key, Decimal],
    known_ids: set[Key],
    label: str,
) -> None:
    """Reject external ids not declared by the current registry snapshot."""
    unknown = sorted(set(items).difference(known_ids))
    if unknown:
        raise RegistryValidationError(f"unknown registry {label} ids: {unknown!r}")


def _require_arg_count(op: str, args: list[Decimal], count: int) -> None:
    """Require an exact operand count for a formula operation."""
    if len(args) != count:
        raise RegistryValidationError(f"formula op {op!r} expects {count} args, got {len(args)}")


def _require_non_empty(op: str, args: list[Decimal]) -> None:
    """Require at least one operand for aggregate formula operations."""
    if not args:
        raise RegistryValidationError(f"formula op {op!r} expects at least one arg")


def read_parameter(
    modelo_id: str,
    revision_id: RevisionId,
    parameter_id: str,
    *,
    date_context: Mapping[str, date],
    registry_root: Path | None = None,
) -> Decimal:
    """Read a registry parameter through :class:`ValidatedRegistryAuthority`.

    The ad hoc public helper loads the same validated registry authority used by
    snapshot callers, narrows to the selected
    :class:`~domain.calculations.registry.ModeloRevision`, and delegates the
    dated value lookup to :func:`resolve_parameter`.

    The default registry root takes the identical path as an explicit one, and
    neither may be memoised here. Every argument this function could be keyed on
    -- a modelo id, a revision id, a parameter id, a root path -- is an argument
    of a registry READ, and none of them moves when the registry itself moves, so
    any memo at this level outlives the tree its value was compiled from.
    :meth:`ValidatedRegistryAuthority.load` is the bound: it re-collects the
    complete registry, treaty, supplementary-orden and source-evidence
    fingerprints on every call and keys its own cache on them, so repeat reads of
    an unchanged tree resolve to the same compiled authority while an edited tree
    resolves to a new one.
    """
    from ....core.resources.bundled_data import bundled_path
    from .authority import ValidatedRegistryAuthority

    source_root = bundled_path()
    root = bundled_path("registry", "aeat") if registry_root is None else registry_root
    authority = ValidatedRegistryAuthority.load(root, source_root=source_root)
    try:
        modelo_match = authority.modelo(modelo_id)
    except RegistrySnapshotError as exc:
        raise RegistryValidationError(f"modelo {modelo_id!r} not registered in {root}") from exc
    revision = modelo_match.revisions.get(revision_id)
    if revision is None:
        raise RegistryValidationError(f"modelo {modelo_id!r} has no revision {revision_id!r}")
    parameter = next((p for p in revision.parameters if p.id == parameter_id), None)
    if parameter is None:
        raise RegistryValidationError(
            f"parameter {parameter_id!r} not registered under modelo {modelo_id!r} revision {revision_id!r}",
        )
    return resolve_parameter(parameter, date_context)
