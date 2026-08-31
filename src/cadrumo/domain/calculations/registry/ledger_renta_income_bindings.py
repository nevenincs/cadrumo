"""Canonical Renta income ledger aggregation binding family."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Literal, NamedTuple, Protocol

from pydantic import BaseModel, model_validator

from ....core.aggregation import (
    BindingAggregationOp,
    BindingSourceKind,
    LedgerIncomeGrounding,
)
from ....core.casilla_id import CasillaId
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG
from ._ledger_binding_resolution import (
    UnroutedLedgerQuantity,
    resolve_ledger_family_binding_values,
    unrouted_ledger_family_quantities,
    unsupported_ledger_family_observations,
)
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import invariant_diagnostics, selector_against_model
from .binding_selector_utils import selector_as_dict as _selector_as_dict
from .errors import RegistryValidationError
from .ids import BindingId
from .ledger_binding_selector_support import _mapping_lacks_fact, casilla_id_set
from .quantity_screen_enrolment import assert_quantity_readers_cover_independent_facts, independent_quantity_facts
from .schema import DataBindingDefinition, ModeloRevision


class _RentaLedgerIncomeSelector(BaseModel):
    """Validated form of a ledger_renta_income_aggregation binding selector.

    ``modelo`` names the declaration series the aggregation feeds: M130's
    cumulative quarter, M100's annual ejercicio, or M131's agrarian quarterly
    volumen de ingresos. ``target_casilla_id`` is the casilla that receives the
    total. The M131 leg is NOT cumulative -- art. 110.1.c) fixes its payment on
    *el volumen de ingresos del trimestre* -- and its projection applies two
    filters the others do not: the art. 110.1.c) activity set, and the exclusion
    of subvenciones de capital and indemnizaciones. Both live in the projection
    rather than in this selector because they decide which rows EXIST as
    observations, not which observations a binding claims.

    ``fact`` is REQUIRED and carries no default. Each accepted value names a
    different legal measure of the same rows, so a default would silently pick
    a legal claim on the taxpayer's behalf: ``cash_received_sum`` is the raw
    bank-credited amount — net of any retención practicada and possibly
    IVA-inclusive — while ``ingresos_integros_sum`` is the ingresos íntegros
    the M130 instructions actually ask for. An omitting binding fails registry
    validation naming the accepted set rather than inheriting the weakest
    measure.

    ``fact`` controls which aggregation path is applied:

    - ``"ingresos_integros_sum"`` sums the fiscally computable ingreso per
      observation: ``taxable_base_amount`` (the IVA-exclusive base
      imponible) when the transaction carries an explicit IVA tagging,
      falling back to ``gross_amount`` when no base is declared — the
      canonical ingresos-íntegros path feeding casilla ``"01"``. The AEAT
      M130 instructions define casilla 01 as the "ingresos íntegros
      fiscalmente computables"; IVA repercutido is collected on behalf of
      Hacienda and is not computable income, so a tagged invoice
      contributes its base, never its IVA-inclusive gross.
    - ``"cash_received_sum"`` sums ``RentaIncomeObservation.gross_amount``
      (``raw.amount`` or its business fraction) across the window,
      ignoring any declared taxable base. Named for what it computes: the
      cash the bank credited, which is neither gross of retención nor
      IVA-exclusive and is therefore NOT the ingresos-íntegros measure.
    - ``"taxable_base_sum"`` sums ``RentaIncomeObservation.taxable_base_amount``
      (the IVA-exclusive base imponible).  Observations whose
      ``taxable_base_amount`` is ``None`` declare no base and contribute
      nothing to this sum;
      :func:`ungrounded_ledger_renta_income_observations` surfaces every such
      row so the omission is visible rather than silent.
    - ``"withheld_amount_sum"`` sums the IRPF amount withheld at source from
      net-paid professional receipts.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: Literal[Modelo.M130, Modelo.M100, Modelo.M131] = Modelo.M130
    target_casilla_id: CasillaId
    fact: Literal["ingresos_integros_sum", "cash_received_sum", "taxable_base_sum", "withheld_amount_sum"]

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
                "ledger_renta_income_aggregation selector requires an explicit 'fact'; "
                f"accepted facts are {sorted(_RENTA_INCOME_SUPPORTED_FACTS)!r}",
            )
        return value


# Per-modelo income casillas this aggregation may feed. M130 (pago fraccionado)
# feeds the cumulative-quarter ingresos casillas; M100 (annual IRPF) feeds the
# estimación-directa "Ingresos de explotación" leaf (0171). Validated at registry
# load so a binding targeting any other casilla surfaces before any calculation.
_RENTA_130_INCOME_CASILLAS: frozenset[CasillaId] = casilla_id_set("_RENTA_130_INCOME_CASILLAS", "01", "03")
_RENTA_100_INCOME_CASILLAS: frozenset[CasillaId] = casilla_id_set("_RENTA_100_INCOME_CASILLAS", "0171")
# One casilla, and the narrowness is the point. Modelo 131 casilla 01 is the sum
# of modulos-computed rendimientos -- derived from signos and indices correctores,
# not from receipts -- so no ledger sum may target it. Only casilla 05, the
# agrarian volumen de ingresos del trimestre, is a real ledger aggregation.
_RENTA_131_INCOME_CASILLAS: frozenset[CasillaId] = casilla_id_set("_RENTA_131_INCOME_CASILLAS", "05")
_RENTA_INCOME_CASILLAS_BY_MODELO: dict[Modelo, frozenset[CasillaId]] = {
    Modelo.M130: _RENTA_130_INCOME_CASILLAS,
    Modelo.M100: _RENTA_100_INCOME_CASILLAS,
    Modelo.M131: _RENTA_131_INCOME_CASILLAS,
}


def _renta_ledger_income_selector(binding: DataBindingDefinition) -> _RentaLedgerIncomeSelector:
    try:
        return _RentaLedgerIncomeSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_income_aggregation selector: {exc}",
        ) from exc


# The complete accepted ``fact`` set for this family, shared by the
# missing-``fact`` refusal message and the build-time invariant so the two can
# never name different sets. Covers both M130 and M100, which is why the name
# carries no modelo segment.
_RENTA_INCOME_SUPPORTED_FACTS: frozenset[str] = frozenset(
    {"ingresos_integros_sum", "cash_received_sum", "taxable_base_sum", "withheld_amount_sum"},
)


def validate_ledger_renta_income_aggregation_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate a ``ledger_renta_income_aggregation`` binding definition."""
    if binding.source != BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION:
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_renta_income_aggregation source")
    selector = _renta_ledger_income_selector(binding)
    allowed = _RENTA_INCOME_CASILLAS_BY_MODELO.get(selector.modelo, frozenset())
    if selector.target_casilla_id not in allowed:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            f"is outside the supported {selector.modelo.value} income casillas {sorted(allowed)!r}",
        )
    op = binding_aggregation_op(binding)
    if op != BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_income_aggregation supports only "
            f"aggregation op 'sum', got {op.value!r}",
        )
    if selector.fact not in _RENTA_INCOME_SUPPORTED_FACTS:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_income_aggregation supports only "
            f"facts {sorted(_RENTA_INCOME_SUPPORTED_FACTS)!r}, got {selector.fact!r}",
        )


class RentaIncomeObservationProtocol(Protocol):
    """Structural protocol for actividad-económica income observations.

    The registry only needs these attributes to resolve
    ``ledger_renta_income_aggregation`` bindings; the full
    :class:`~cadrumo.application.aggregation._renta_income_ledger.RentaIncomeObservation`
    satisfies this protocol without any explicit declaration.
    """

    @property
    def transaction_id(self) -> str:
        """Return the ledger row this observation was projected from.

        Declared because a consumer samples these ids to name the offending
        rows in an ungrounded-income diagnostic. Leaving it off the protocol
        let a conforming implementation omit it and fail there at runtime.
        """
        ...

    @property
    def target_casilla_id(self) -> CasillaId:
        """Return the declaration casilla receiving the income aggregate."""
        ...

    @property
    def gross_amount(self) -> Decimal:
        """Return the observation's gross or cash-received amount."""
        ...

    @property
    def taxable_base_amount(self) -> Decimal | None:
        """Return the declared IVA-exclusive taxable base, when available."""
        ...

    @property
    def withheld_amount(self) -> Decimal:
        """Return the IRPF amount withheld at source for the observation."""
        ...

    @property
    def grounding(self) -> LedgerIncomeGrounding:
        """Return the substrate-grounding marker for the income observation."""
        ...


def _renta_income_build_matcher(
    selector: _RentaLedgerIncomeSelector,
) -> Callable[[RentaIncomeObservationProtocol], bool]:
    target_casilla_id = selector.target_casilla_id

    def matcher(observation: RentaIncomeObservationProtocol) -> bool:
        return observation.target_casilla_id == target_casilla_id

    return matcher


def _renta_income_aggregate(
    matched: Sequence[RentaIncomeObservationProtocol],
    selector: _RentaLedgerIncomeSelector,
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
    if selector.fact == "taxable_base_sum":
        # A row that declares no base contributes nothing: this fact sums
        # DECLARED bases, and inventing one from cash would fabricate a legal
        # figure. Written as an explicit ``is not None`` filter rather than
        # ``or Decimal("0")`` so a genuinely-zero declared base and an absent
        # one stop sharing a branch.
        return sum(
            (observation.taxable_base_amount for observation in matched if observation.taxable_base_amount is not None),
            Decimal("0"),
        )
    if selector.fact == "withheld_amount_sum":
        return sum((observation.withheld_amount for observation in matched), Decimal("0"))
    # cash_received_sum: the raw bank-credited magnitude, ignoring any declared
    # base. ``fact`` is a required closed Literal, so this is that member alone.
    return sum((observation.gross_amount for observation in matched), Decimal("0"))


def resolve_ledger_renta_income_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_renta_income_aggregation`` binding on ``revision``.

    The ``fact`` declared in the binding selector controls which field is
    summed: ``"ingresos_integros_sum"`` → ``observation.taxable_base_amount``
    when declared, else ``observation.gross_amount`` (per-observation
    fallback); ``"cash_received_sum"`` → ``observation.gross_amount``;
    ``"taxable_base_sum"`` → ``observation.taxable_base_amount`` (a base-less
    row contributes nothing); ``"withheld_amount_sum"`` →
    ``observation.withheld_amount``. Delegates the filter/aggregate skeleton to
    :func:`resolve_ledger_family_binding_values`, shared by every ledger
    family resolver.

    Args:
        revision: The :class:`ModeloRevision` whose bindings are resolved.
        observations: Renta income ledger lines to aggregate over.
    """
    return resolve_ledger_family_binding_values(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        parse_selector=_renta_ledger_income_selector,
        build_matcher=_renta_income_build_matcher,
        aggregate=_renta_income_aggregate,
    )


def _renta_income_is_declarable(observation: RentaIncomeObservationProtocol) -> bool:
    declarable = observation.gross_amount
    if observation.taxable_base_amount is not None:
        declarable = max(declarable, observation.taxable_base_amount)
    return declarable != Decimal("0")


def unsupported_ledger_renta_income_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> tuple[RentaIncomeObservationProtocol, ...]:
    """Return the :class:`RentaIncomeObservationProtocol` rows no binding on ``revision`` can consume.

    Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family's
    own contribution is narrow: the ``target_casilla_id`` match predicate
    (reused from the resolver's ``_renta_income_build_matcher``) and a
    false-fire guard that excludes an observation whose declarable amount —
    ``max(gross_amount, taxable_base_amount)`` when a base is declared,
    ``gross_amount`` otherwise — is zero. No ``extra_exclusion``.

    Args:
        revision: The :class:`ModeloRevision` whose renta-income bindings define
            the supported ``target_casilla_id`` set.
        observations: Actividad-económica income observations to screen.

    Returns:
        Tuple of observations whose non-zero income is selected by no
        ``ledger_renta_income_aggregation`` binding.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        parse_selector=_renta_ledger_income_selector,
        build_matcher=_renta_income_build_matcher,
        is_declarable=_renta_income_is_declarable,
    )


# The facts that read a row's DECLARED taxable_base. Both mis-handle a row that
# declares none, in opposite directions, which is why one screen serves both:
# ``ingresos_integros_sum`` substitutes the raw bank cash (net of retención,
# possibly IVA-inclusive — wrong in a direction that depends on the invoice),
# and ``taxable_base_sum`` contributes nothing at all (always under-declares).
# ``cash_received_sum`` and ``withheld_amount_sum`` never read the base, so a
# base-less row is not an ungrounded contribution for them.
_RENTA_INCOME_BASE_READING_FACTS: frozenset[str] = frozenset({"ingresos_integros_sum", "taxable_base_sum"})


class UngroundedRentaIncome(NamedTuple):
    """Base-less income rows that a base-reading binding still consumes.

    ``facts`` is the set of base-reading facts the revision actually declares,
    so a caller can describe the consequence precisely rather than guessing:
    ``ingresos_integros_sum`` means the listed rows contributed bank cash in
    place of a base, ``taxable_base_sum`` means they contributed nothing.
    ``observations`` are the contributing rows, in input order.

    Empty ``observations`` means every consumed row declared its substrate;
    empty ``facts`` means the revision declares no base-reading income binding,
    in which case ``observations`` is empty too.
    """

    facts: frozenset[str]
    observations: tuple[RentaIncomeObservationProtocol, ...]


def ungrounded_ledger_renta_income_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> UngroundedRentaIncome:
    """Return the base-less rows a base-reading income binding on ``revision`` consumes.

    The companion to :func:`unsupported_ledger_renta_income_observations`, for
    the opposite failure: that screen catches a row NO binding consumes, this
    one catches a row a binding DOES consume but without the substrate the
    binding's fact assumes. Both are ``no-silent-under-declaration`` screens;
    neither changes a value.

    A row reaches an income casilla through declared substrate or through the
    cash fallback, and only the row's :class:`LedgerIncomeGrounding` marker
    distinguishes them — this screen keys on that marker, never on
    ``taxable_base_amount is None``, so the grounding fact has exactly one
    definition. Rows are screened against the ``target_casilla_id`` of the
    base-reading bindings only, so a revision whose income bindings all read
    cash or withholdings reports nothing.

    The caller surfaces the result as a NON-BLOCKING advisory: the fallback is
    deliberately kept (dropping an untagged income row would under-declare by
    the whole row, strictly worse than mis-measuring it), so what this screen
    buys is visibility, not exclusion.

    Args:
        revision: The :class:`ModeloRevision` whose renta-income bindings
            decide which casillas and facts are in play.
        observations: Actividad-económica income observations to screen.

    Returns:
        An :class:`UngroundedRentaIncome` pairing the declared base-reading
        facts with the base-less rows those bindings consume.
    """
    matchers: list[Callable[[RentaIncomeObservationProtocol], bool]] = []
    facts: set[str] = set()
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION:
            continue
        selector = _renta_ledger_income_selector(binding)
        if selector.fact not in _RENTA_INCOME_BASE_READING_FACTS:
            continue
        facts.add(selector.fact)
        matchers.append(_renta_income_build_matcher(selector))
    if not matchers:
        return UngroundedRentaIncome(facts=frozenset(), observations=())
    ungrounded = tuple(
        observation
        for observation in observations
        if observation.grounding is LedgerIncomeGrounding.CASH_FALLBACK
        and any(matcher(observation) for matcher in matchers)
    )
    return UngroundedRentaIncome(facts=frozenset(facts), observations=ungrounded)


# The renta-income facts excluded from the quantity screen, each with the reason
# it re-measures a quantity another fact already carries. These are DECLARATIONS
# a reviewer can check against the form, not proofs: excluding a fact narrows the
# screen, so the claim is written at the site rather than inferred from an
# absence.
#
# ``withheld_amount_sum`` is deliberately absent from this mapping, and that is
# the whole point: the retención a taxpayer suffered is an INDEPENDENT quantity
# carried on the same observation, not an alternative measure of its income.
# Nothing else can stand in for it.
_RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS: Mapping[str, str] = {
    "ingresos_integros_sum": (
        "measures the row's income as its declared taxable base, falling back to bank cash; "
        "one of three income measures a revision picks between"
    ),
    "taxable_base_sum": (
        "measures the same income as the declared taxable base only, contributing nothing for a "
        "base-less row; the stricter sibling of ingresos_integros_sum"
    ),
    "cash_received_sum": (
        "measures the same income as the raw bank credit, net of retención and possibly "
        "IVA-inclusive; the loosest of the three measures"
    ),
}

#: The independent quantities, DERIVED as the complement so the two sets cannot
#: drift apart. A new fact added to the closed set is screened by default and
#: must be classified deliberately as an alternative measure to be excluded --
#: the safe direction, since forgetting to classify one surfaces an advisory
#: rather than silently dropping a quantity.
_RENTA_INCOME_INDEPENDENT_QUANTITY_FACTS: frozenset[str] = independent_quantity_facts(
    _RENTA_INCOME_SUPPORTED_FACTS,
    _RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS,
)


#: Per-fact readers for the independent quantities. Keyed on the same
#: selector-fact vocabulary the resolver dispatches on
#: (:func:`_renta_income_aggregate`), so a fact cannot be screened under one
#: reading and resolved under another.
_RENTA_INDEPENDENT_QUANTITY_READERS: dict[str, Callable[[RentaIncomeObservationProtocol], Decimal]] = {
    "withheld_amount_sum": lambda observation: observation.withheld_amount,
}

assert_quantity_readers_cover_independent_facts(
    "renta-income",
    _RENTA_INCOME_INDEPENDENT_QUANTITY_FACTS,
    _RENTA_INDEPENDENT_QUANTITY_READERS,
)


def unrouted_ledger_renta_income_quantities(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> tuple[UnroutedLedgerQuantity[RentaIncomeObservationProtocol], ...]:
    """Return independent quantities the rows carry that no binding on ``revision`` draws.

    The third renta-income screen, and it watches an axis the other two cannot
    see. :func:`unsupported_ledger_renta_income_observations` asks whether a ROW
    is selected by some binding; :func:`ungrounded_ledger_renta_income_observations`
    asks whether a consumed row carried the substrate its binding's fact assumes.
    Both key on the row. This one keys on the QUANTITY.

    The distinction is load-bearing because every ``RentaIncomeObservation`` is
    built with ``target_casilla_id = "01"`` regardless of which fact a binding
    reads off it (see the note in the M130 ``0003-m130-income-cumulative.toml``
    bindings fragment). A row therefore matches the income bindings on that key
    and counts as consumed — while a SECOND, independent quantity it carries,
    the retención suffered, reaches nothing at all. Drop the
    ``withheld_amount_sum`` binding from a revision and the row-level screen
    stays silent: every row is still consumed, for its income. The taxpayer's
    whole retención credit disappears with a clean screen on both sides, which
    is precisely the silent under-declaration the screens exist to prevent.

    Alternative MEASURES of one quantity are excluded
    (:data:`_RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS`): a revision picks one
    income measure and omitting the other two is correct, so demanding all three
    would fire on every revision and train the operator to ignore the advisory.
    Only a genuinely independent quantity is screened.

    Reports nothing when the rows carry nothing: a taxpayer who suffered no
    retención has a zero total, which is a legitimate zero rather than a
    modelling gap, and this screen must not manufacture a finding from it.

    Args:
        revision: The :class:`ModeloRevision` whose renta-income bindings
            decide which facts are drawn.
        observations: Actividad-económica income observations to screen.

    Returns:
        One :class:`UnroutedLedgerQuantity` per uncovered non-zero quantity,
        ordered by fact name. Empty when every quantity the rows carry is drawn.
    """
    return unrouted_ledger_family_quantities(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        parse_selector=_renta_ledger_income_selector,
        build_matcher=_renta_income_build_matcher,
        read_fact=lambda selector: selector.fact,
        independent_facts=_RENTA_INCOME_INDEPENDENT_QUANTITY_FACTS,
        readers=_RENTA_INDEPENDENT_QUANTITY_READERS,
    )


# Casilla IDs that the M130 gastos cumulative aggregation may feed. Validated at
# registry load time so a binding targeting any other casilla surfaces before
# any calculation runs.


def validate_ledger_renta_income_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_renta_income_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_RentaLedgerIncomeSelector`;
    runs the fact/aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_renta_income_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _RentaLedgerIncomeSelector)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_renta_income_aggregation",
        validate_ledger_renta_income_aggregation_binding_definition,
    )


RentaLedgerIncomeSelector = _RentaLedgerIncomeSelector
