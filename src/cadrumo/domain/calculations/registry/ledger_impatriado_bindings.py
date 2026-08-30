"""Impatriado (Beckham-regime) ledger income aggregation binding family.

One of the per-family modules the registry binding surface is split into: the
selector model, its validators, the observation protocol, and the resolver for
`ledger_impatriado_income_aggregation` bindings.

Separated from the general ledger-binding module so that module holds families
rather than growing into a single file of them, per the per-family module shape
the registry binding surface follows.

The resolver and its fail-closed screen delegate their filter/aggregate
skeleton to
:func:`~.registry._ledger_binding_resolution.resolve_ledger_family_binding_values`
and :func:`~.registry._ledger_binding_resolution.unsupported_ledger_family_observations`,
the shape shared by every ledger-aggregation family; this module supplies
only the M151 selector, its ``target_casilla_id`` match predicate, the
two-fact aggregation (``ingresos_integros_sum`` with a
``taxable_base_amount``-or-``gross_amount`` per-observation fallback,
``cash_received_sum`` summing ``gross_amount`` unconditionally), and the
declarable-amount false-fire guard.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from ....core import Modelo
from ....core.casilla_id import CasillaId
from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ._ledger_binding_resolution import resolve_ledger_family_binding_values, unsupported_ledger_family_observations
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import invariant_diagnostics, selector_against_model
from .binding_selector_utils import selector_as_dict as _selector_as_dict
from .errors import RegistryValidationError
from .ids import BindingId
from .schema import DataBindingDefinition, ModeloRevision

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


from .ledger_bindings import casilla_id_set

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


def _mapping_lacks_fact(value: object) -> bool:
    """Whether *value* is a mapping with no ``fact`` key.

    Extracted so the ``isinstance`` narrowing stays local. Inline, it widened
    the enclosing validator's inferred return to include an unparameterised
    mapping, which said less than the declared type it replaced.
    """
    return isinstance(value, Mapping) and "fact" not in value


class _ImpatriadoLedgerIncomeSelector(BaseModel):
    """Validated form of a ``ledger_impatriado_income_aggregation`` binding selector.

    ``modelo`` is Modelo 151 (the only modelo whose base is legally
    source-scoped to Spanish income by art. 93.2 LIRPF). ``target_casilla_id``
    is the base casilla that receives the annual Spanish-source total.

    ``fact`` is REQUIRED and carries no default, matching its
    :class:`~._ledger_bindings._RentaLedgerIncomeSelector` sibling. The two
    accepted values name different legal measures of the same rows, so a
    default silently picks a legal claim on the taxpayer's behalf — and a
    default on one sibling but not the other re-creates exactly the divergence
    this requiredness closes (the two families defaulted to *different* facts
    for one concept). An omitting binding fails registry validation naming the
    accepted set.

    ``fact`` controls which aggregation path is applied:

    - ``"ingresos_integros_sum"`` sums the fiscally computable ingreso
      per observation: ``taxable_base_amount`` (the IVA-exclusive base imponible)
      when the transaction carries an explicit IVA tagging, falling back to
      ``gross_amount`` when no base is declared — the canonical base path.
    - ``"cash_received_sum"`` sums ``gross_amount`` across the window, ignoring
      any declared taxable base. Named for what it computes: the cash the bank
      credited, which is neither gross of retención nor IVA-exclusive.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M151] = Modelo.M151
    target_casilla_id: CasillaId
    fact: Literal["ingresos_integros_sum", "cash_received_sum"]

    @model_validator(mode="before")
    @classmethod
    def _require_explicit_fact(cls, value: object) -> object:
        """Refuse an omitted ``fact``, naming the accepted set in the message.

        Pydantic's own "Field required" names the field but not its accepted
        values; a wrong value already enumerates the ``Literal`` members. This
        closes the missing-value half so a binding author reads the choice
        instead of guessing it.
        """
        if _mapping_lacks_fact(value):
            raise ValueError(
                "ledger_impatriado_income_aggregation selector requires an explicit 'fact'; "
                f"accepted facts are {sorted(_IMPATRIADO_SUPPORTED_FACTS)!r}",
            )
        return value


# The single Modelo 151 base casilla this aggregation may feed. Validated at
# registry load so a binding targeting any other casilla surfaces before any
# calculation.
_IMPATRIADO_BASE_CASILLAS: frozenset[CasillaId] = casilla_id_set(
    "_IMPATRIADO_BASE_CASILLAS",
    "impatriado.base-liquidable-general",
)
# The complete accepted ``fact`` set for this family, shared by the
# missing-``fact`` refusal message and the build-time invariant so the two can
# never name different sets.
_IMPATRIADO_SUPPORTED_FACTS: frozenset[str] = frozenset({"ingresos_integros_sum", "cash_received_sum"})


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
    def target_casilla_id(self) -> CasillaId:
        """Return the Modelo 151 base casilla receiving this observation's aggregate."""
        ...

    @property
    def gross_amount(self) -> Decimal:
        """Return the observation's gross or cash-received amount."""
        ...

    @property
    def taxable_base_amount(self) -> Decimal | None:
        """Return the declared IVA-exclusive taxable base, when available."""
        ...


def _impatriado_income_build_matcher(
    selector: _ImpatriadoLedgerIncomeSelector,
) -> Callable[[ImpatriadoIncomeObservationProtocol], bool]:
    target_casilla_id = selector.target_casilla_id

    def matcher(observation: ImpatriadoIncomeObservationProtocol) -> bool:
        return observation.target_casilla_id == target_casilla_id

    return matcher


def _impatriado_income_aggregate(
    matched: Sequence[ImpatriadoIncomeObservationProtocol],
    selector: _ImpatriadoLedgerIncomeSelector,
) -> Decimal:
    if selector.fact == "ingresos_integros_sum":
        return sum(
            (
                observation.taxable_base_amount
                if observation.taxable_base_amount is not None
                else observation.gross_amount
                for observation in matched
            ),
            Decimal("0"),
        )
    # cash_received_sum: the raw bank-credited magnitude, ignoring any declared
    # base. ``fact`` is a required closed Literal, so this is that member alone.
    return sum((observation.gross_amount for observation in matched), Decimal("0"))


def resolve_ledger_impatriado_income_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[ImpatriadoIncomeObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_impatriado_income_aggregation`` binding on ``revision``.

    The ``fact`` declared in the binding selector controls which field is
    summed: ``"ingresos_integros_sum"`` → ``observation.taxable_base_amount``
    when declared, else ``observation.gross_amount``; ``"cash_received_sum"`` →
    ``observation.gross_amount``. Only ES-scoped observations reach this resolver;
    the source-scope segregation is owned by the application classifier.
    Delegates the filter/aggregate skeleton to
    :func:`resolve_ledger_family_binding_values`, shared by every ledger
    family resolver.

    Args:
        revision: The :class:`ModeloRevision` whose bindings are resolved.
        observations: ES-scoped impatriado income ledger lines to aggregate over.
    """
    return resolve_ledger_family_binding_values(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
        parse_selector=_impatriado_ledger_income_selector,
        build_matcher=_impatriado_income_build_matcher,
        aggregate=_impatriado_income_aggregate,
    )


def _impatriado_income_is_declarable(observation: ImpatriadoIncomeObservationProtocol) -> bool:
    declarable = observation.gross_amount
    if observation.taxable_base_amount is not None:
        declarable = max(declarable, observation.taxable_base_amount)
    return declarable != Decimal("0")


def unsupported_ledger_impatriado_income_observations(
    revision: ModeloRevision,
    observations: Iterable[ImpatriadoIncomeObservationProtocol],
) -> tuple[ImpatriadoIncomeObservationProtocol, ...]:
    """Return ES-scoped impatriado observations no binding can consume.

    ``revision`` is the :class:`ModeloRevision` whose declared bindings define
    what is consumable. Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family's
    own contribution is narrow: the ``target_casilla_id`` match predicate
    (reused from the resolver's ``_impatriado_income_build_matcher``) and a
    false-fire guard that excludes an observation whose declarable amount —
    ``max(gross_amount, taxable_base_amount)`` when a base is declared,
    ``gross_amount`` otherwise — is zero. No ``extra_exclusion``.

    Returns:
        The unsupported :class:`ImpatriadoIncomeObservationProtocol` rows, in
        input order.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
        parse_selector=_impatriado_ledger_income_selector,
        build_matcher=_impatriado_income_build_matcher,
        is_declarable=_impatriado_income_is_declarable,
    )


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


ImpatriadoLedgerIncomeSelector = _ImpatriadoLedgerIncomeSelector
