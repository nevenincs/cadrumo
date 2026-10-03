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

from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, field_validator, model_validator

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG
from ._ledger_binding_resolution import (
    cash_received_total,
    casilla_target_matcher,
    ingresos_integros_total,
    resolve_ledger_family_binding_values,
    unsupported_ledger_family_observations,
)
from .ids import BindingId
from .ledger_binding_selector_support import (
    IMPATRIADO_LEDGER_INCOME_FACTS,
    ImpatriadoLedgerIncomeFact,
    LedgerIncomeFact,
    mapping_lacks_fact,
)
from .ledger_binding_validation import (
    ledger_binding_build_diagnostics,
    ledger_binding_selector,
    require_ledger_aggregation_op,
    require_ledger_fact,
    require_ledger_target_casilla,
)

# Ledger-aggregation binding source kinds, imported from the canonical
# :data:`cadrumo.core.aggregation.LEDGER_BINDING_SOURCE_KINDS` definition. Every
# binding whose ``source`` is a member reads its values from
# the bucket-scoped ledger (transaction-classified IVA / OSS aggregation, Renta
# first-slice income and estimación directa gastos aggregation, the M130
# pago-fraccionado gastos cumulative aggregation,
# the M151 impatriado Spanish-source base aggregation, or the M210 explicit
# IRNR income projection). Cross-domain consumers import the taxonomy from its
# defining core module.
__all__ = [
    "ImpatriadoIncomeObservationProtocol",
    "resolve_ledger_impatriado_income_aggregation_binding_values",
    "unsupported_ledger_impatriado_income_observations",
    "validate_ledger_impatriado_income_aggregation_binding",
    "validate_ledger_impatriado_income_aggregation_binding_definition",
]


from ....core.errors.hierarchy import pydantic_validation_boundary
from .ledger_binding_selector_support import casilla_id_set

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision

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


class LedgerImpatriadoIncomeProvider(BaseModel):
    """Validated form of a ``ledger_impatriado_income_aggregation`` binding selector.

    ``modelo`` is Modelo 151 (the only modelo whose base is legally
    source-scoped to Spanish income by art. 93.2 LIRPF). ``target_casilla_id``
    is the base casilla that receives the annual Spanish-source total.

    ``fact`` is REQUIRED and carries no default, matching its
    :class:`~.ledger_renta_income_bindings.LedgerRentaIncomeProvider` sibling. The two
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

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION] = (
        BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION
    )

    modelo: Modelo = Modelo("151")
    target_casilla_id: CasillaId
    fact: ImpatriadoLedgerIncomeFact

    @field_validator("modelo")
    @classmethod
    @pydantic_validation_boundary
    def _require_modelo_151(cls, value: Modelo) -> Modelo:
        if value != Modelo("151"):
            raise ValueError("ledger_impatriado_income_aggregation modelo must be '151'")
        return value

    @model_validator(mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _require_explicit_fact(cls, value: object) -> object:
        """Refuse an omitted ``fact``, naming the accepted set in the message.

        Pydantic's own "Field required" names the field but not its accepted
        values; a wrong value already enumerates the ``Literal`` members. This
        closes the missing-value half so a binding author reads the choice
        instead of guessing it.
        """
        if mapping_lacks_fact(value):
            raise ValueError(
                "ledger_impatriado_income_aggregation selector requires an explicit 'fact'; "
                f"accepted facts are {sorted(IMPATRIADO_LEDGER_INCOME_FACTS)!r}",
            )
        return value


# The single Modelo 151 base casilla this aggregation may feed. Validated at
# registry load so a binding targeting any other casilla surfaces before any
# calculation.
_IMPATRIADO_BASE_CASILLAS: frozenset[CasillaId] = casilla_id_set(
    "_IMPATRIADO_BASE_CASILLAS",
    "impatriado.base-liquidable-general",
)


def validate_ledger_impatriado_income_aggregation_binding_definition(binding: BindingDefinition) -> None:
    """Validate a ``ledger_impatriado_income_aggregation`` binding definition."""
    selector = ledger_binding_selector(
        binding,
        BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
        LedgerImpatriadoIncomeProvider,
    )
    require_ledger_target_casilla(
        binding,
        selector.target_casilla_id,
        _IMPATRIADO_BASE_CASILLAS,
        scope="supported Modelo 151 base casillas",
    )
    require_ledger_aggregation_op(binding)
    require_ledger_fact(binding, selector.fact, IMPATRIADO_LEDGER_INCOME_FACTS)


def validate_ledger_impatriado_income_aggregation_binding(binding: BindingDefinition) -> list[str]:
    """Validate a ``ledger_impatriado_income_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`LedgerImpatriadoIncomeProvider`;
    runs the casilla / fact / aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_impatriado_income_aggregation_binding_definition`.
    """
    return ledger_binding_build_diagnostics(
        binding,
        LedgerImpatriadoIncomeProvider,
        validate_ledger_impatriado_income_aggregation_binding_definition,
    )


class ImpatriadoIncomeObservationProtocol(Protocol):
    """Structural protocol for Modelo 151 impatriado Spanish-source income observations.

    The registry only needs these attributes to resolve
    ``ledger_impatriado_income_aggregation`` bindings; the full
    :class:`~cadrumo.application.aggregation.impatriado_income_ledger.ImpatriadoIncomeObservation`
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


def _impatriado_income_aggregate(
    matched: Sequence[ImpatriadoIncomeObservationProtocol],
    selector: LedgerImpatriadoIncomeProvider,
) -> Decimal:
    if selector.fact == LedgerIncomeFact.INGRESOS_INTEGROS_SUM:
        return ingresos_integros_total(matched)
    # ``fact`` is a required closed Literal, so this is cash_received_sum alone.
    return cash_received_total(matched)


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
        provider_model=LedgerImpatriadoIncomeProvider,
        build_matcher=casilla_target_matcher,
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
    (the shared casilla-keyed matcher the resolver also uses) and a
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
        provider_model=LedgerImpatriadoIncomeProvider,
        build_matcher=casilla_target_matcher,
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


LedgerImpatriadoIncomeProvider = LedgerImpatriadoIncomeProvider
