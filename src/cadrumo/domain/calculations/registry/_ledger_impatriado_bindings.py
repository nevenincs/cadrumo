"""Impatriado (Beckham-regime) ledger income aggregation binding family.

One of the per-family modules the registry binding surface is split into: the
selector model, its validators, the observation protocol, and the resolver for
`ledger_impatriado_income_aggregation` bindings.

Separated from the general ledger-binding module so that module holds families
rather than growing into a single file of them, per the per-family module shape
the registry binding surface follows.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from ....core import Modelo
from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ._binding_aggregation import binding_aggregation_op
from ._binding_selector_utils import invariant_diagnostics, selector_against_model
from ._binding_selector_utils import selector_as_dict as _selector_as_dict
from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId
from ._schema import DataBindingDefinition, ModeloRevision

# Ledger-aggregation binding source kinds. Re-exported from
# :data:`cadrumo.core.aggregation.LEDGER_BINDING_SOURCE_KINDS`, which derives the
# set from :class:`~cadrumo.core.BindingSourceKind` (the single source-kind
# taxonomy). Every binding whose ``source`` is a member reads its values from
# the bucket-scoped ledger (transaction-classified IVA / OSS aggregation, Renta
# first-slice income and estimación directa gastos aggregation, the M130
# pago-fraccionado gastos cumulative aggregation,
# the M151 impatriado Spanish-source base aggregation, or the M210 explicit
# IRNR income projection). Cross-domain consumers route through this name so the
# registry stays the single source of truth for ledger readiness.
__all__ = [
    "ImpatriadoIncomeObservationProtocol",
    "resolve_ledger_impatriado_income_aggregation_binding_values",
    "unsupported_ledger_impatriado_income_observations",
    "validate_ledger_impatriado_income_aggregation_binding",
    "validate_ledger_impatriado_income_aggregation_binding_definition",
]


from ._ledger_bindings import _casilla_id_set

# Ledger Modelo 151 impatriado (Ley Beckham, art. 93 LIRPF) Spanish-source
# base aggregation source bindings.
#
# The impatriado income aggregation (source
# ``ledger_impatriado_income_aggregation``) folds ONLY Spanish-source
# (``source_jurisdiction == "ES"``) income into
# ``impatriado.base-liquidable-general``; a foreign-source or
# jurisdiction-unresolved row is segregated by the application-layer classifier
# (:mod:`cadrumo.application.aggregation._impatriado_income_ledger`) as a typed
# BECKHAM_FOREIGN_SOURCE_SEGREGATED issue, never silently admitted. This
# registry family only needs the ES-scoped observation totals; the source-scope
# gate is owned by the classifier, so the resolver here simply sums the matched
# observations per the one-aggregation-path discipline.


class _ImpatriadoLedgerIncomeSelector(BaseModel):
    """Validated form of a ``ledger_impatriado_income_aggregation`` binding selector.

    ``modelo`` is Modelo 151 (the only modelo whose base is legally
    source-scoped to Spanish income by art. 93.2 LIRPF). ``target_casilla_id``
    is the base casilla that receives the annual Spanish-source total.

    ``fact`` controls which aggregation path is applied:

    - ``"ingresos_integros_sum"`` (default) sums the fiscally computable ingreso
      per observation: ``taxable_base_amount`` (the IVA-exclusive base imponible)
      when the transaction carries an explicit IVA tagging, falling back to
      ``gross_amount`` when no base is declared — the canonical base path.
    - ``"gross_income_sum"`` sums ``gross_amount`` across the window, ignoring
      any declared taxable base.
    """

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M151] = Modelo.M151
    target_casilla_id: CasillaId
    fact: Literal["ingresos_integros_sum", "gross_income_sum"] = "ingresos_integros_sum"


# The single Modelo 151 base casilla this aggregation may feed. Validated at
# registry load so a binding targeting any other casilla surfaces before any
# calculation.
_IMPATRIADO_BASE_CASILLAS: frozenset[CasillaId] = _casilla_id_set(
    "_IMPATRIADO_BASE_CASILLAS",
    "impatriado.base-liquidable-general",
)
_IMPATRIADO_SUPPORTED_FACTS: frozenset[str] = frozenset({"ingresos_integros_sum", "gross_income_sum"})


def _impatriado_ledger_income_selector(binding: DataBindingDefinition) -> _ImpatriadoLedgerIncomeSelector:
    try:
        return _ImpatriadoLedgerIncomeSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_impatriado_income_aggregation selector: {exc}",
        ) from exc


def validate_ledger_impatriado_income_aggregation_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate a ``ledger_impatriado_income_aggregation`` binding definition."""
    if binding.source != BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION:
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_impatriado_income_aggregation source")
    selector = _impatriado_ledger_income_selector(binding)
    if selector.target_casilla_id not in _IMPATRIADO_BASE_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            f"is outside the supported Modelo 151 base casillas {sorted(_IMPATRIADO_BASE_CASILLAS)!r}",
        )
    op = binding_aggregation_op(binding)
    if op != BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_impatriado_income_aggregation supports only "
            f"aggregation op 'sum', got {op.value!r}",
        )
    if selector.fact not in _IMPATRIADO_SUPPORTED_FACTS:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_impatriado_income_aggregation supports only "
            f"facts {sorted(_IMPATRIADO_SUPPORTED_FACTS)!r}, got {selector.fact!r}",
        )


def validate_ledger_impatriado_income_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_impatriado_income_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_ImpatriadoLedgerIncomeSelector`;
    runs the casilla / fact / aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_impatriado_income_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _ImpatriadoLedgerIncomeSelector)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_impatriado_income_aggregation",
        validate_ledger_impatriado_income_aggregation_binding_definition,
    )


class ImpatriadoIncomeObservationProtocol(Protocol):
    """Structural protocol for Modelo 151 impatriado Spanish-source income observations.

    The registry only needs these attributes to resolve
    ``ledger_impatriado_income_aggregation`` bindings; the full
    :class:`~cadrumo.application.aggregation._impatriado_income_ledger.ImpatriadoIncomeObservation`
    satisfies this protocol without any explicit declaration.
    """

    @property
    def target_casilla_id(self) -> CasillaId: ...

    @property
    def gross_amount(self) -> Decimal: ...

    @property
    def taxable_base_amount(self) -> Decimal | None: ...


def resolve_ledger_impatriado_income_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[ImpatriadoIncomeObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_impatriado_income_aggregation`` binding on ``revision``.

    The ``fact`` declared in the binding selector controls which field is
    summed: ``"ingresos_integros_sum"`` → ``observation.taxable_base_amount``
    when declared, else ``observation.gross_amount``; ``"gross_income_sum"`` →
    ``observation.gross_amount``. Only ES-scoped observations reach this resolver;
    the source-scope segregation is owned by the application classifier.

    Args:
        revision: The :class:`ModeloRevision` whose bindings are resolved.
        observations: ES-scoped impatriado income ledger lines to aggregate over.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION:
            continue
        selector = _impatriado_ledger_income_selector(binding)
        matched = [
            observation for observation in available if observation.target_casilla_id == selector.target_casilla_id
        ]
        if selector.fact == "ingresos_integros_sum":
            resolved[binding.id] = sum(
                (
                    observation.taxable_base_amount
                    if observation.taxable_base_amount is not None
                    else observation.gross_amount
                    for observation in matched
                ),
                Decimal("0"),
            )
        else:
            resolved[binding.id] = sum((observation.gross_amount for observation in matched), Decimal("0"))
    return resolved


def unsupported_ledger_impatriado_income_observations(
    revision: ModeloRevision,
    observations: Iterable[ImpatriadoIncomeObservationProtocol],
) -> tuple[ImpatriadoIncomeObservationProtocol, ...]:
    """Return ES-scoped impatriado observations no binding on ``revision`` can consume.

    The :class:`ModeloRevision` supplies the
    ``ledger_impatriado_income_aggregation`` binding selectors that define which
    impatriado base casillas are supported.

    Fail-closed counterpart to
    :func:`resolve_ledger_impatriado_income_aggregation_binding_values`. An
    ES-source observation whose ``target_casilla_id`` matches no
    ``ledger_impatriado_income_aggregation`` binding would otherwise have its
    income silently dropped from the impatriado base — a modelling gap, not a
    legitimate zero. A zero-income observation contributes nothing and is
    excluded.

    Returns:
        The unsupported :class:`ImpatriadoIncomeObservationProtocol` rows, in
        input order.
    """
    supported_casillas = frozenset(
        _impatriado_ledger_income_selector(binding).target_casilla_id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION
    )
    unsupported: list[ImpatriadoIncomeObservationProtocol] = []
    for observation in observations:
        declarable = observation.gross_amount
        if observation.taxable_base_amount is not None:
            declarable = max(declarable, observation.taxable_base_amount)
        if declarable == Decimal("0"):
            continue
        if observation.target_casilla_id not in supported_casillas:
            unsupported.append(observation)
    return tuple(unsupported)


# Ledger Renta Modelo 130 pago-fraccionado gastos aggregation source bindings.
#
# The OUTGOING sibling of ``ledger_renta_income_aggregation``: M130 casilla 02
# ("Gastos") accumulates deductible gastos bases over the same cumulative
# year-to-date quarterly window the income path uses (RD 439/2007 art. 110.2).
# Mirrors the income resolver exactly — a minimal observation protocol matched
# only by ``target_casilla_id`` (the revision is M130, so all of its gastos
# bindings are M130). Deliberately distinct from
# ``ledger_renta_gastos_estimacion_directa_aggregation``, whose annual /
# invoice-evidence / category-profile machinery is constraint-shape-divergent
# from this simple cumulative sum.
