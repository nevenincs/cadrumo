"""Canonical ledger aggregation binding family."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING, Annotated, Final, Literal, Self

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

from ....core.aggregation import BindingSourceKind
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period
from ...iva.classification import TransactionKind, require_transaction_kind
from ...iva.errors import IvaValidationError
from ...iva.oss import OssIossRegime, require_oss_ioss_regime, resolve_oss_ioss_regime_catalogue
from ...iva.schema import EUMemberState, InvoiceKind, IvaRateKind
from .binding_selector_utils import provider_member
from .errors import RegistryValidationError
from .eu_member_state_catalogue import require_eu_member_state
from .governed_fact_scope import require_governed_fact_authority
from .ids import BindingId
from .iva_rate_kind_catalogue import require_iva_rate_kind
from .ledger_binding_resolution import resolve_ledger_family_binding_values
from .ledger_binding_selector_support import OSS_IOSS_LEDGER_FACTS, LedgerIvaFact, OssIossLedgerFact
from .ledger_binding_validation import (
    ledger_binding_build_diagnostics,
    ledger_binding_selector,
    ledger_selector_vocabulary_date,
    require_ledger_aggregation_op,
    require_ledger_fact,
)
from .schema_base import coerce_enum_member, coerce_enum_tuple

if TYPE_CHECKING:
    from .governed_fact_scope import GovernedFactSource
    from .schema import BindingDefinition, ModeloRevision


_SELECTOR_TOKEN: Final = re.compile(r"[a-z][a-z0-9_]*")
"""The closed form of an authored OSS/IOSS selector token."""

_MEMBER_STATE_TOKEN: Final = re.compile(r"[A-Z]{2}")
"""The closed form of an authored destination Member State token, once upper-cased."""


def _member_state_token_form(value: object) -> object:
    """Refuse a destination token outside the two-letter form before the member-state type projects it.

    A selector carries no governing date of its own, so its membership in the
    dated member-state vocabulary is checked by
    :func:`ledger_oss_revision_vocabulary_failures` on the date of the revision
    that declares it.
    """
    if isinstance(value, EUMemberState):
        return value
    if not isinstance(value, str) or _MEMBER_STATE_TOKEN.fullmatch(value.strip().upper()) is None:
        raise RegistryValidationError("destination member state must be a two-letter registry token")
    return value.strip().upper()


class OssLineEffect(StrEnum):
    """What a line's magnitudes do to its destination and rate."""

    SUPPLY = "supply"
    CORRECTION = "correction"


class OssIossLedgerObservation(BaseModel):
    """One factual ledger line tagged with substrate-grounded classification.

    Modelo 369 binding selectors filter these observations by the four
    classification axes (regime, destination Member State, rate tier,
    invoice direction) plus the optional transaction kind set; the
    runtime aggregates the matched lines through the binding's
    aggregation operator.

    Attributes:
        ledger_id: Stable id of the source ledger line.
        transaction_date: When the supply takes place.
        regime: OSS / IOSS Esquema the line is filed under.
        destination_member_state: Member State of consumption (the
            destination MS for the supply, which determines the
            applicable IVA rate per the OSS / IOSS rules).
        rate_kind: Substrate rate tier (general / reduced / etc.).
        invoice_direction: Whether the autónomo issued or received
            the invoice.
        transaction_kind: Substrate :class:`cadrumo.domain.iva.classification.TransactionKind`
            the line resolves to.
        base_amount: Taxable base in EUR.
        iva_amount: IVA amount in EUR (already applied at the
            destination MS rate per OSS / IOSS rules).
        effect: Whether the amounts add a supply or take a correction off one.
        corrected_period: The earlier period the amounts adjust, or ``None`` when they belong
            to the period being filed. Such a line reaches the return only as a correction row.
    """

    model_config = STRICT_FROZEN_CONFIG

    ledger_id: str = Field(min_length=1, max_length=128)
    transaction_date: date
    regime: OssIossRegime
    destination_member_state: EUMemberState
    rate_kind: IvaRateKind
    invoice_direction: InvoiceKind
    transaction_kind: TransactionKind
    base_amount: Decimal
    iva_amount: Decimal
    effect: OssLineEffect = OssLineEffect.SUPPLY
    corrected_period: Period | None = None

    @property
    def signed_base_amount(self) -> Decimal:
        """Return the base as it counts towards a sum: a correction takes off what a supply adds."""
        return -self.base_amount if self.effect is OssLineEffect.CORRECTION else self.base_amount

    @property
    def signed_iva_amount(self) -> Decimal:
        """Return the cuota as it counts towards a sum: a correction takes off what a supply adds."""
        return -self.iva_amount if self.effect is OssLineEffect.CORRECTION else self.iva_amount

    @model_validator(mode="after")
    def _validate_registry_regime(self) -> Self:
        """Refuse an observation whose regime is absent from facts authority."""
        authority = require_governed_fact_authority(None, subject="ledger OSS observation validation")
        regime = require_oss_ioss_regime(
            self.regime,
            effective_date=self.transaction_date,
            authority=authority,
        )
        require_iva_rate_kind(self.rate_kind, effective_date=self.transaction_date, authority=authority)
        transaction_kind = require_transaction_kind(
            self.transaction_kind,
            effective_date=self.transaction_date,
            operation=authority,
        )
        catalogue = resolve_oss_ioss_regime_catalogue(
            effective_date=self.transaction_date,
            authority=authority,
        )
        if transaction_kind.value not in catalogue.transaction_kinds_for(regime):
            raise RegistryValidationError(
                "transaction kind is not admitted by the supplied OSS/IOSS regime",
            )
        return self


class LedgerOssProvider(BaseModel):
    """Validated form of a ledger_oss_aggregation binding selector.

    The selector is expressed in TOML as a mapping of string-valued
    keys (the registry binding selector contract); this record coerces
    those strings into substrate enum members at validation time so
    downstream consumers see typed values.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.LEDGER_OSS_AGGREGATION] = BindingSourceKind.LEDGER_OSS_AGGREGATION

    regime: OssIossRegime
    destination_member_state: Annotated[EUMemberState, BeforeValidator(_member_state_token_form)]
    rate_kind: Annotated[IvaRateKind, BeforeValidator(coerce_enum_member(IvaRateKind))]
    invoice_direction: Annotated[InvoiceKind, BeforeValidator(coerce_enum_member(InvoiceKind))]
    transaction_kinds: Annotated[
        tuple[TransactionKind, ...],
        BeforeValidator(coerce_enum_tuple(TransactionKind)),
    ] = Field(min_length=1)
    fact: OssIossLedgerFact = LedgerIvaFact.IVA_AMOUNT_SUM

    @field_validator("regime", "rate_kind", mode="after")
    @classmethod
    def _token_form(cls, value: str) -> str:
        """Refuse a token outside the closed authored form; its dated membership is the revision's check."""
        if _SELECTOR_TOKEN.fullmatch(value) is None:
            raise RegistryValidationError(f"OSS/IOSS selector token {value!r} is not a lowercase registry token")
        return value

    @field_validator("transaction_kinds", mode="after")
    @classmethod
    def _transaction_kinds_form(cls, value: tuple[TransactionKind, ...]) -> tuple[TransactionKind, ...]:
        for kind in value:
            if _SELECTOR_TOKEN.fullmatch(kind) is None:
                raise RegistryValidationError(f"transaction kind {kind!r} is not a lowercase registry token")
        return value

    @field_validator("transaction_kinds", mode="after")
    @classmethod
    def _kinds_unique(cls, value: tuple[TransactionKind, ...]) -> tuple[TransactionKind, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("transaction_kinds entries must be unique")
        return value


def _refusal(check: Callable[[], object]) -> str | None:
    """Return the refusal ``check`` raises, or ``None`` when it admits its value.

    The transaction-kind vocabulary refuses with the IVA domain's validation
    error, the others with the registry's.
    """
    try:
        check()
    except (RegistryValidationError, IvaValidationError) as exc:
        return str(exc)
    return None


def ledger_oss_selector_vocabulary_failures(
    selector: LedgerOssProvider,
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> tuple[str, ...]:
    """Return the refusals one OSS/IOSS selector earns against the vocabulary in force on ``effective_date``.

    The selector model checks only the form of its tokens, because a selector
    carries no date of its own; membership in the dated regime, member-state,
    rate-tier and transaction-kind vocabularies is judged here, on the date and
    against the facts the caller names.
    """
    checks: list[Callable[[], object]] = [
        partial(require_oss_ioss_regime, selector.regime, effective_date=effective_date, authority=authority),
        partial(
            require_eu_member_state,
            selector.destination_member_state,
            effective_date=effective_date,
            authority=authority,
        ),
        partial(require_iva_rate_kind, selector.rate_kind, effective_date=effective_date, authority=authority),
    ]
    checks.extend(
        partial(require_transaction_kind, kind, effective_date=effective_date, operation=authority)
        for kind in selector.transaction_kinds
    )
    return tuple(refusal for refusal in map(_refusal, checks) if refusal is not None)


def ledger_oss_revision_vocabulary_failures(
    revision: ModeloRevision,
    *,
    authority: GovernedFactSource,
) -> list[str]:
    """Return every OSS/IOSS selector's dated-vocabulary refusal, read on the revision's start.

    The date is :func:`ledger_selector_vocabulary_date`: the revision's own
    ``valid_from``, raised to the support floor when the revision starts below it.
    """
    on_date = ledger_selector_vocabulary_date(revision, authority.supported_filing_years())
    if on_date is None:
        return []
    return [
        f"binding {binding.id!r} has malformed OSS/IOSS selector: {failure}"
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_OSS_AGGREGATION
        for failure in ledger_oss_selector_vocabulary_failures(
            provider_member(binding, LedgerOssProvider),
            effective_date=on_date,
            authority=authority,
        )
    ]


def validate_ledger_oss_aggregation_binding_definition(
    binding: BindingDefinition,
) -> None:
    """Validate a ``ledger_oss_aggregation`` binding's selector and aggregation.

    Args:
        binding: The :class:`BindingDefinition` to validate. Must
            have ``source == "ledger_oss_aggregation"``.

    Raises:
        RegistryValidationError: If the selector is malformed (unknown
            regime / member state / rate kind / invoice direction /
            transaction kind), or if the aggregation operator is
            inconsistent with the declared fact.
    """
    selector = ledger_binding_selector(binding, BindingSourceKind.LEDGER_OSS_AGGREGATION, LedgerOssProvider)
    require_ledger_aggregation_op(binding)
    require_ledger_fact(binding, selector.fact, OSS_IOSS_LEDGER_FACTS)


def _oss_build_matcher(
    selector: LedgerOssProvider,
) -> Callable[[OssIossLedgerObservation], bool]:
    regime, destination, rate_kind, direction = (
        selector.regime,
        selector.destination_member_state,
        selector.rate_kind,
        selector.invoice_direction,
    )
    kinds = set(selector.transaction_kinds)

    def matcher(observation: OssIossLedgerObservation) -> bool:
        return (
            observation.corrected_period is None
            and observation.regime == regime
            and observation.destination_member_state == destination
            and observation.rate_kind == rate_kind
            and observation.invoice_direction is direction
            and observation.transaction_kind in kinds
        )

    return matcher


def _oss_aggregate(
    matched: Sequence[OssIossLedgerObservation],
    selector: LedgerOssProvider,
) -> Decimal:
    if selector.fact == LedgerIvaFact.IVA_AMOUNT_SUM:
        return sum((observation.signed_iva_amount for observation in matched), Decimal("0"))
    return sum((observation.signed_base_amount for observation in matched), Decimal("0"))


def resolve_ledger_oss_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[OssIossLedgerObservation],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_oss_aggregation`` binding on ``revision``.

    For each binding, observations are filtered by the four
    classification axes plus the transaction-kind set; matched
    observations are aggregated through the binding's declared fact
    (``iva_amount_sum`` defaults; ``base_amount_sum`` selects the base).
    The resolver is deterministic and side-effect-free. Delegates the
    filter/aggregate skeleton to :func:`resolve_ledger_family_binding_values`,
    shared by every ledger family resolver; the per-selector
    ``transaction_kinds`` set is built once when the matcher closure is
    constructed for a binding, not once per observation.

    Args:
        revision: The :class:`ModeloRevision` whose bindings to resolve.
        observations: Iterable of substrate-classified ledger lines.

    Returns:
        Mapping of binding id to the aggregated Decimal value. Empty
        match sets resolve to ``Decimal("0")``.
    """
    return resolve_ledger_family_binding_values(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_OSS_AGGREGATION,
        provider_model=LedgerOssProvider,
        build_matcher=_oss_build_matcher,
        aggregate=_oss_aggregate,
    )


# Ledger IVA aggregation source bindings (cross-modelo IVA roll-out).
#
# Generic counterpart to :func:`resolve_ledger_oss_aggregation_binding_values`
# for the standard IVA modelos (303 autoliquidación trimestral, 322 grupos
# individual, 353 grupos agregado, 309 no periódica, 390 resumen anual).
# Aggregates ledger lines by the canonical IVA classification triple
# (IvaCategory + IvaRateKind + IvaFlowDirection).
#
# OSS / IOSS bindings keep their dedicated source kind because they
# additionally carry the regime + destination Member State axes; this
# generic source covers domestic IVA, intra-community supplies /
# acquisitions, exports, imports, recargo de equivalencia, and
# domestic-reverse-charge operations.


def validate_ledger_oss_aggregation_binding(binding: BindingDefinition) -> list[str]:
    """Validate a ``ledger_oss_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector shape against
    :class:`LedgerOssProvider` (preserving the underlying pydantic field
    error) then runs the fact/aggregation-op invariant through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_oss_aggregation_binding_definition`. This validator is
    that body's only caller, so the invariant is enforced at registry-build time
    only; :func:`resolve_ledger_oss_aggregation_binding_values` narrows the
    selector independently through its own provider model.
    """
    return ledger_binding_build_diagnostics(
        binding, LedgerOssProvider, validate_ledger_oss_aggregation_binding_definition
    )


LedgerOssProvider = LedgerOssProvider
