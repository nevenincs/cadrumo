"""Canonical IVA ledger aggregation binding family."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Annotated, Final, Literal, NamedTuple, Protocol

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

from ....core.aggregation import BindingSourceKind
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.iva_deduction_fact import IvaDeductionFactKind
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.prorrata_exclusions import Art104TresExclusion
from ....core.type_guards import is_object_list_or_tuple
from ....core.unit_proportion import UnitProportion
from ...iva.components import registry_category_projection
from ...iva.deduction_facts import (
    IvaDeductionClassificationProvenance,
    admits_iva_deduction_classification,
    validate_iva_deduction_fact,
)
from ...iva.flow import (
    IvaFlowDirection,
    is_deducible_flow,
    received_flow_direction,
)
from ...iva.prorrata import InputClassification
from ...iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
    default_iva_cash_accounting_treatment,
)
from .binding_selector_utils import provider_member, selector_against_model
from .errors import RegistryValidationError
from .ids import BindingId
from .iva_cash_accounting_vocabulary import require_iva_cash_accounting_treatment
from .iva_category_catalogue import IvaCategoryCatalogue, resolve_iva_category_catalogue
from .iva_deduction_catalogue import require_iva_deduction_fact_kind
from .iva_flow_catalogue import (
    IvaFlowDirectionCatalogue,
    require_iva_flow_direction,
    resolve_iva_flow_direction_catalogue,
)
from .iva_legal_vocabulary import require_iva_exemption_article
from .iva_rate_kind_catalogue import require_iva_rate_kind
from .ledger_binding_resolution import (
    UnroutedLedgerQuantity,
    resolve_ledger_family_binding_values,
    unrouted_ledger_family_quantities,
    unsupported_ledger_family_observations,
)
from .ledger_binding_selector_support import LEDGER_IVA_FACTS, LedgerIvaFact, LedgerIvaFactValue
from .ledger_binding_validation import (
    ledger_binding_build_diagnostics,
    ledger_binding_selector,
    ledger_selector_vocabulary_date,
    require_ledger_aggregation_op,
    require_ledger_fact,
)
from .prorrata_exclusions import resolve_art104_tres_exclusion_catalogue
from .prorrata_vocabulary import require_input_classification
from .quantity_screen_enrolment import assert_quantity_readers_cover_independent_facts, independent_quantity_facts
from .schema_base import coerce_decimal_tuple, coerce_enum_tuple

if TYPE_CHECKING:
    from .governed_fact_scope import GovernedFactSource
    from .schema import BindingDefinition, ModeloRevision


IvaCashAccountingTreatmentCode = Annotated[
    str,
    StringConstraints(min_length=1, pattern=r"^[a-z][a-z0-9_]*$"),
]
"""Authored cash-accounting vocabulary token, validated against the IVA fact catalogue.

The runtime observation still uses :class:`IvaCashAccountingTreatment` because
that enum describes the application's operational routes.  A registry binding
is different: its treatment vocabulary is an authored tax classification and
must be checked against the canonical IVA schema fact rather than duplicated
in this module.
"""


def _coerce_cash_accounting_treatment_codes(value: object) -> object:
    """Hydrate TOML arrays before strict tuple validation."""
    if is_object_list_or_tuple(value):
        return tuple(value)
    return value


_SELECTOR_TOKEN: Final = re.compile(r"[a-z][a-z0-9_]*")
"""The closed form every authored IVA selector token takes."""


def _project_selector_flow_direction(value: object) -> IvaFlowDirection:
    """Project a selector's flow token by its form alone.

    A selector carries no governing date of its own, so its membership in the
    dated flow vocabulary is checked by :func:`ledger_iva_revision_vocabulary_failures`
    on the date of the revision that declares it.
    """
    if isinstance(value, IvaFlowDirection):
        return value
    if not isinstance(value, str) or _SELECTOR_TOKEN.fullmatch(value) is None:
        raise RegistryValidationError("IVA flow direction must be a lowercase registry token")
    return IvaFlowDirection.from_registry(value)


def _observation_date(data: Mapping[str, object], subject: str) -> date:
    """Return the validated ``transaction_date`` an observation's dated vocabulary is read on.

    Raises:
        RegistryValidationError: When the observation has no valid transaction date.
    """
    transaction_date = data.get("transaction_date")
    if not isinstance(transaction_date, date):
        raise RegistryValidationError(f"{subject} requires the observation's transaction_date")
    return transaction_date


def _default_observation_cash_accounting_treatment(data: Mapping[str, object]) -> IvaCashAccountingTreatment:
    """Return the ordinary cash-accounting token in force on the observation's date."""
    return default_iva_cash_accounting_treatment(
        _observation_date(data, "the default cash-accounting treatment"),
    )


def _project_deduction_fact_kinds(value: object) -> object:
    """Project authored deduction-kind tokens through fact 0085, element-wise."""
    if not is_object_list_or_tuple(value):
        return value
    return tuple(require_iva_deduction_fact_kind(item) for item in value)


class IvaLedgerObservation(BaseModel):
    """One factual ledger line tagged with the IVA classification triple.

    Modelo 303 / 322 / 353 / 309 / 390 binding selectors filter these
    observations by category, rate kind, and flow direction; the
    runtime aggregates the matched lines through the binding's
    aggregation operator.

    Attributes:
        ledger_id: Stable id of the source ledger line.
        transaction_date: When the supply takes place.
        category: Substrate :class:`IvaCategory` resolved by the
            classifier.
        rate_kind: Substrate :class:`IvaRateKind` rate tier.
        flow_direction: Substrate :class:`IvaFlowDirection` (output /
            input / self-assessed reverse charge).
        base_amount: Taxable base in EUR.
        iva_amount: IVA amount in EUR (cuota repercutida or soportada,
            depending on flow direction).
    """

    model_config = STRICT_FROZEN_CONFIG

    ledger_id: str = Field(min_length=1, max_length=128)
    transaction_date: date
    category: IvaCategory
    exemption_article: IvaExemptionArticle | None = None
    rate_kind: IvaRateKind
    flow_direction: IvaFlowDirection
    base_amount: Decimal
    iva_amount: Decimal
    applied_rate: UnitProportion | None = None
    """The numeric IVA rate this line was charged at, as a fraction, when known.

    Carried ALONGSIDE :attr:`rate_kind` rather than instead of it, because the
    two answer different questions and the annual return asks both. ``rate_kind``
    is the semantic tier (general / reducido / super-reducido / zero); this is the
    rate that tier resolved to on this line's date. One tier can produce several
    rates within a single filing year: the anti-inflation food measures stepped
    the super-reducido tier 4 % to 2 % to 0 % and the reducido tier 10 % to 5 %
    to 7.5 % across successive extensions, which is why Modelo 390 carries one box
    per rate per window where Modelo 303 carries one per tier. Resolving to the
    tier and discarding the value made those boxes unpopulatable, because two
    lines at 4 % and 2 % arrived downstream indistinguishable.

    ``None`` where the rate is genuinely unknown rather than zero — a
    pre-classified candidate supplied without one, or an exempt line that carries
    no rate at all. A caller MUST NOT read ``None`` as 0 %: zero-rated and
    rate-less are different declarations, and :class:`IvaRateKind` already
    distinguishes ``ZERO`` from ``EXEMPT`` for exactly that reason.
    """
    recargo_amount: Decimal = Decimal("0")
    """Recargo de equivalencia cuota the supplier charged on a repercutido sale to
    a recargo-regime retailer, in EUR. ``Decimal("0")`` on every line that carries
    no recargo. Modelo 303 recargo cuota casillas select these via the
    ``recargo_amount_sum`` fact, routed by the line's IVA rate tier."""
    prorrata_reference_id: str | None = Field(default=None, min_length=1, max_length=128)
    """Stable id of the linked :class:`ProrrataLedgerReference` row, when set.

    Populated by the aggregator only on ``SOPORTADO`` (input IVA) flows
    that carry a validated prorrata reference. Downstream Modelo 303 /
    390 binding selectors filter prorrata-linked observations without
    a manual join against the parallel ``prorrata_references`` tuple.
    """
    cash_accounting_treatment: IvaCashAccountingTreatment = Field(
        default_factory=_default_observation_cash_accounting_treatment
    )
    """Independent criterio-de-caja affiliation for this projection."""
    observation_role: IvaLedgerObservationRole
    """Whether this is a monetary settlement or an art. 75 information projection.

    Cash-accounting operation and payment observations retain the same typed
    treatment affiliation.  Registry bindings select this orthogonal role so
    informational boxes cannot consume monetary settlements, and ordinary IVA
    boxes cannot consume the operation-date information projection.
    """
    input_classification: InputClassification | None = None
    """Operator-declared LIVA art. 106 prorrata-especial per-input use class.

    Carried from the source ledger transaction's
    ``input_classification``. Meaningful only for ``SOPORTADO`` (input IVA)
    rows in a bucket under prorrata especial: the regime-aware ledger IVA
    apportionment routes the deducible cuota by this classification (the
    art. 106.Uno reglas 100%/0%/general). ``None`` for every row not under
    especial or carrying no per-input use declaration; the general-regime
    apportionment ignores it.
    """
    prorrata_sector_id: str | None = Field(default=None, min_length=1, max_length=64)
    """Operator-declared LIVA arts. 9.1.c / 101 differentiated sector.

    Carried from the source ledger transaction's ``prorrata_sector_id``.
    Meaningful only for ``SOPORTADO`` (input IVA) rows in a sectorized bucket:
    the sector-aware ledger IVA apportionment applies THAT sector's provisional
    percentage to the deducible cuota. ``None`` is a common-use input in a
    sectorized bucket (apportioned by the art. 104.Dos common percentage) and
    the whole-entity default otherwise; the non-sectorized apportionment ignores
    it.
    """
    deduction_fact_kind: IvaDeductionFactKind | None = None
    """Exact, evidence-grounded differentiated-sector deduction family."""
    deduction_provenance: IvaDeductionClassificationProvenance | None = None
    investment_asset_id: str | None = Field(default=None, min_length=1, max_length=128)
    rectifies_ledger_id: str | None = Field(default=None, min_length=1, max_length=128)
    art_104_tres_exclusion: Art104TresExclusion | None = None
    """The operator's LIVA art. 104.Tres exclusion declared on the source ledger row, when any.

    Carried so a binding whose box the law measures without such operations can
    leave the row out by its declared token; every other binding still reads it.
    ``None`` is a row with no declaration, never a row proven not to be excluded.
    """

    @field_validator("input_classification", mode="before")
    @classmethod
    def _input_classification_registry_declared(cls, value: object) -> object:
        """Project raw input-use tokens through the dated prorrata catalogue."""
        if value is None or isinstance(value, InputClassification):
            return value
        return require_input_classification(value)

    @field_validator("flow_direction", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _flow_direction_registry_declared(cls, value: object, info: ValidationInfo) -> object:
        """Project raw flow tokens, such as a JSON round trip, through fact 0083 on the row's date."""
        if isinstance(value, IvaFlowDirection):
            return value
        return require_iva_flow_direction(value, effective_date=_observation_date(info.data, "IVA flow direction"))

    @field_validator("deduction_fact_kind", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _deduction_fact_kind_registry_declared(cls, value: object) -> object:
        """Project raw deduction-kind tokens through fact 0085."""
        if value is None or isinstance(value, IvaDeductionFactKind):
            return value
        return require_iva_deduction_fact_kind(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _enforce_exemption_article_category(self) -> IvaLedgerObservation:
        require_iva_rate_kind(self.rate_kind, effective_date=self.transaction_date)
        require_iva_cash_accounting_treatment(self.cash_accounting_treatment, effective_date=self.transaction_date)
        if self.exemption_article is not None:
            require_iva_exemption_article(self.exemption_article, effective_date=self.transaction_date)
        category_catalogue = resolve_iva_category_catalogue(effective_date=self.transaction_date)
        if self.exemption_article is not None and self.category != category_catalogue.require("domestic_exempt"):
            raise RegistryValidationError(
                "exemption_article is only valid when category is DOMESTIC_EXEMPT; "
                f"got category {self.category.value!r}",
            )
        # Fact 0085, not the flow direction, decides whether a deduction arises on
        # this row. Every RECEIVED operation settles as ``soportado``, and LIVA
        # art. 92.Uno grants a deduction only of a cuota devengada and borne by
        # repercusión, so an exempt (art. 20) or not-subject (art. 7) purchase and
        # a recargo de equivalencia acquisition raise none to classify. Keyed on
        # the flow alone, this required authority that the same fact then refused,
        # leaving those rows representable in no form at all.
        if not is_deducible_flow(
            self.flow_direction, effective_date=self.transaction_date
        ) or not admits_iva_deduction_classification(
            category=self.category,
            flow_direction=self.flow_direction,
            effective_date=self.transaction_date,
        ):
            if self.deduction_fact_kind is not None or self.deduction_provenance is not None:
                raise RegistryValidationError("an IVA row bearing no deducible cuota cannot carry deduction authority")
            return self
        if self.deduction_fact_kind is None or self.deduction_provenance is None:
            raise RegistryValidationError("input IVA facts require exact deduction authority")
        validate_iva_deduction_fact(
            kind=self.deduction_fact_kind,
            provenance=self.deduction_provenance,
            category=self.category,
            rate_kind=self.rate_kind,
            flow_direction=self.flow_direction,
            base_amount=self.base_amount,
            iva_amount=self.iva_amount,
            investment_asset_id=self.investment_asset_id,
            rectifies_ledger_id=self.rectifies_ledger_id,
            effective_date=self.transaction_date,
        )
        return self


class LedgerIvaProvider(BaseModel):
    """Validated form of a ledger_iva_aggregation binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.LEDGER_IVA_AGGREGATION] = BindingSourceKind.LEDGER_IVA_AGGREGATION

    categories: Annotated[tuple[IvaCategory, ...], BeforeValidator(coerce_enum_tuple(IvaCategory))] = Field(
        min_length=1,
    )
    exemption_articles: (
        Annotated[tuple[IvaExemptionArticle, ...], BeforeValidator(coerce_enum_tuple(IvaExemptionArticle))] | None
    ) = Field(default=None, min_length=1)
    rate_kinds: Annotated[tuple[IvaRateKind, ...], BeforeValidator(coerce_enum_tuple(IvaRateKind))] = Field(
        min_length=1,
    )
    flow_direction: Annotated[
        IvaFlowDirection,
        BeforeValidator(pydantic_validation_boundary(_project_selector_flow_direction)),
    ]
    observation_roles: Annotated[
        tuple[IvaLedgerObservationRole, ...],
        BeforeValidator(coerce_enum_tuple(IvaLedgerObservationRole)),
    ] = Field(min_length=1)
    cash_accounting_treatments: Annotated[
        tuple[IvaCashAccountingTreatmentCode, ...],
        BeforeValidator(_coerce_cash_accounting_treatment_codes),
    ] = Field(min_length=1)
    applied_rates: Annotated[tuple[Decimal, ...], BeforeValidator(coerce_decimal_tuple)] | None = Field(
        default=None,
        min_length=1,
    )
    """Numeric rates this binding accepts, when the box is rate-specific.

    ``None`` -- the default and the shape every quarterly binding uses -- means
    the binding does not discriminate on the value and matches whatever rates
    its ``rate_kinds`` tiers admit. Set it only where the FORM asks per rate
    rather than per tier: Modelo 390 carries one box per rate per window because
    a tier's rate can change inside a filing year, so its 2 % box must reject a
    4 % line that shares the super-reducido tier with it.

    An observation whose ``applied_rate`` is ``None`` (rate genuinely unknown --
    an invoice-sourced line carries a rate slot, not a number) matches NO
    rate-specific binding. That is deliberate: admitting it would put an
    unmeasured line in a box that asserts a specific rate, and the annual return
    is where that assertion is read.
    """
    deduction_fact_kinds: (
        Annotated[
            tuple[IvaDeductionFactKind, ...],
            BeforeValidator(pydantic_validation_boundary(_project_deduction_fact_kinds)),
        ]
        | None
    ) = Field(default=None, min_length=1)
    """Fact-0085 deduction kinds this binding accepts, when the box is kind-specific.

    ``None`` means the binding does not discriminate on the deduction and matches
    every row its other axes admit. Set it where the FORM splits one deducible
    quantity by what was acquired: Modelo 303 asks for the cuota soportada on
    bienes corrientes and on bienes de inversión in different boxes ([28]/[29]
    against [30]/[31], [32]/[33] against [34]/[35], [36]/[37] against [38]/[39]),
    and the category, rate and flow of the two rows are identical. The ledger
    row's reciprocal deduction kind is the only axis that tells them apart.

    A row whose ``deduction_fact_kind`` is ``None`` matches no kind-specific
    binding. Only a deducible flow carries a deduction kind, so the axis is
    refused on any other flow rather than left to match nothing.
    """
    excluded_art_104_tres_exclusions: tuple[Art104TresExclusion, ...] | None = Field(default=None, min_length=1)
    """Art. 104.Tres exclusion tokens whose rows this binding leaves out, when the box asks for that.

    ``None`` -- the default -- reads every row the other axes admit, declared
    exclusion or not. Set it where the governing text measures the box without
    the operations art. 104.Tres names, so a row the operator declared under one
    of these tokens does not enter the box. A row with no declaration is read.
    """
    fact: LedgerIvaFactValue = LedgerIvaFact.IVA_AMOUNT_SUM

    @field_validator("categories", mode="after")
    @classmethod
    @pydantic_validation_boundary
    def _categories_unique(cls, value: tuple[IvaCategory, ...]) -> tuple[IvaCategory, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("categories entries must be unique")
        return value

    @field_validator("rate_kinds", mode="after")
    @classmethod
    @pydantic_validation_boundary
    def _rate_kinds_unique(cls, value: tuple[IvaRateKind, ...]) -> tuple[IvaRateKind, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("rate_kinds entries must be unique")
        return value

    @field_validator("cash_accounting_treatments", mode="after")
    @classmethod
    @pydantic_validation_boundary
    def _cash_accounting_treatments_unique(
        cls,
        value: tuple[IvaCashAccountingTreatmentCode, ...],
    ) -> tuple[IvaCashAccountingTreatmentCode, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("cash_accounting_treatments entries must be unique")
        return value

    @field_validator("observation_roles", mode="after")
    @classmethod
    @pydantic_validation_boundary
    def _observation_roles_unique(
        cls,
        value: tuple[IvaLedgerObservationRole, ...],
    ) -> tuple[IvaLedgerObservationRole, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("observation_roles entries must be unique")
        return value

    @field_validator("exemption_articles", mode="after")
    @classmethod
    @pydantic_validation_boundary
    def _exemption_articles_unique(
        cls,
        value: tuple[IvaExemptionArticle, ...] | None,
    ) -> tuple[IvaExemptionArticle, ...] | None:
        if value is not None and len(set(value)) != len(value):
            raise RegistryValidationError("exemption_articles entries must be unique")
        return value

    @field_validator("excluded_art_104_tres_exclusions", mode="after")
    @classmethod
    @pydantic_validation_boundary
    def _excluded_art_104_tres_exclusions_unique(
        cls,
        value: tuple[Art104TresExclusion, ...] | None,
    ) -> tuple[Art104TresExclusion, ...] | None:
        if value is not None and len(set(value)) != len(value):
            raise RegistryValidationError("excluded_art_104_tres_exclusions entries must be unique")
        return value

    @field_validator("deduction_fact_kinds", mode="after")
    @classmethod
    @pydantic_validation_boundary
    def _deduction_fact_kinds_unique(
        cls,
        value: tuple[IvaDeductionFactKind, ...] | None,
    ) -> tuple[IvaDeductionFactKind, ...] | None:
        if value is not None and len(set(value)) != len(value):
            raise RegistryValidationError("deduction_fact_kinds entries must be unique")
        return value


def _refusal(check: Callable[[], object]) -> str | None:
    """Return the refusal ``check`` raises, or ``None`` when it admits its value."""
    try:
        check()
    except RegistryValidationError as exc:
        return str(exc)
    return None


def ledger_iva_selector_vocabulary_failures(
    selector: LedgerIvaProvider,
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> tuple[str, ...]:
    """Return the refusals one IVA selector earns against the vocabulary in force on ``effective_date``.

    The selector model checks only the form of its tokens, because a selector
    carries no date of its own. Membership in the dated IVA vocabularies, and the
    two rules those vocabularies decide -- a deduction-kind axis needs a
    deducible flow, an exemption-article axis needs the domestic exempt
    category -- are judged here, on the date and against the facts the caller
    names.
    """
    categories = resolve_iva_category_catalogue(effective_date=effective_date, authority=authority)
    flows = resolve_iva_flow_direction_catalogue(effective_date=effective_date, authority=authority)
    checks = _selector_membership_checks(
        selector, categories=categories, flows=flows, effective_date=effective_date, authority=authority
    )
    failures = tuple(refusal for refusal in map(_refusal, checks) if refusal is not None)
    return failures or _selector_axis_rule_failures(selector, categories=categories, flows=flows)


def _selector_membership_checks(
    selector: LedgerIvaProvider,
    *,
    categories: IvaCategoryCatalogue,
    flows: IvaFlowDirectionCatalogue,
    effective_date: date,
    authority: GovernedFactSource,
) -> list[Callable[[], object]]:
    """Return one deferred vocabulary lookup per token the selector names."""
    checks: list[Callable[[], object]] = [
        partial(categories.require, str(category)) for category in selector.categories
    ]
    checks.extend(
        partial(require_iva_rate_kind, kind, effective_date=effective_date, authority=authority)
        for kind in selector.rate_kinds
    )
    checks.append(partial(flows.require, selector.flow_direction))
    checks.extend(
        partial(require_iva_cash_accounting_treatment, token, effective_date=effective_date, authority=authority)
        for token in selector.cash_accounting_treatments
    )
    checks.extend(
        partial(require_iva_exemption_article, token, effective_date=effective_date, authority=authority)
        for token in selector.exemption_articles or ()
    )
    if selector.excluded_art_104_tres_exclusions is not None:
        exclusions = resolve_art104_tres_exclusion_catalogue(effective_date=effective_date, authority=authority)
        checks.extend(partial(exclusions.require, token) for token in selector.excluded_art_104_tres_exclusions)
    return checks


def _selector_axis_rule_failures(
    selector: LedgerIvaProvider,
    *,
    categories: IvaCategoryCatalogue,
    flows: IvaFlowDirectionCatalogue,
) -> tuple[str, ...]:
    """Return the refusals of the two axis rules the dated vocabularies decide."""
    failures: list[str] = []
    if selector.deduction_fact_kinds is not None and not flows.is_deducible(selector.flow_direction):
        failures.append(
            f"deduction_fact_kinds selector requires a deducible flow_direction; got {selector.flow_direction.value!r}",
        )
    if selector.exemption_articles is not None and categories.require("domestic_exempt") not in selector.categories:
        failures.append("exemption_articles selector requires DOMESTIC_EXEMPT in categories")
    return tuple(failures)


def ledger_iva_revision_vocabulary_failures(
    revision: ModeloRevision,
    *,
    authority: GovernedFactSource,
) -> list[str]:
    """Return every IVA selector's dated-vocabulary refusal, read on the revision's start.

    The date is :func:`ledger_selector_vocabulary_date`: the revision's own
    ``valid_from``, raised to the support floor when the revision starts below it.
    """
    on_date = ledger_selector_vocabulary_date(revision, authority.supported_filing_years())
    if on_date is None:
        return []
    return [
        f"binding {binding.id!r} has malformed IVA selector: {failure}"
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_IVA_AGGREGATION
        for failure in ledger_iva_selector_vocabulary_failures(
            provider_member(binding, LedgerIvaProvider),
            effective_date=on_date,
            authority=authority,
        )
    ]


def validate_ledger_iva_aggregation_binding_definition(
    binding: BindingDefinition,
) -> None:
    """Validate a ``ledger_iva_aggregation`` binding's selector and aggregation.

    Args:
        binding: The :class:`BindingDefinition` to validate. Must
            have ``source == "ledger_iva_aggregation"``.

    Raises:
        RegistryValidationError: If the selector is malformed (unknown
            category / rate kind / flow direction / fact, empty
            tuple), if the aggregation operator is not "sum", or if
            the binding source is not "ledger_iva_aggregation".
    """
    selector = ledger_binding_selector(binding, BindingSourceKind.LEDGER_IVA_AGGREGATION, LedgerIvaProvider)
    diagnostics = selector_against_model(binding, LedgerIvaProvider)
    if diagnostics:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed IVA selector: {'; '.join(diagnostics)}")
    require_ledger_aggregation_op(binding)
    require_ledger_fact(binding, selector.fact, LEDGER_IVA_FACTS)

    try:
        iva_reachability_probe(selector)
    except RegistryValidationError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} {exc}") from exc


class IvaSelectorAxesProtocol(Protocol):
    """The axes the IVA selector matcher reads off an observation.

    Declared so the matcher can state the shape it actually needs instead of
    naming the full :class:`IvaLedgerObservation` record. Both that record and
    the reachability probe below satisfy it structurally, which is what makes
    the probe a legitimate stand-in rather than an unchecked substitution --
    previously the probe was passed where the concrete record was declared and
    only the absence of a checked seam kept that quiet.

    Same shape as :class:`RentaIncomeObservationProtocol` serves for the renta
    side of this module.
    """

    @property
    def category(self) -> IvaCategory:
        """Return the IVA category assigned to the observation."""
        ...

    @property
    def rate_kind(self) -> IvaRateKind:
        """Return the IVA rate tier assigned to the observation."""
        ...

    @property
    def flow_direction(self) -> IvaFlowDirection:
        """Return the observation's IVA flow direction."""
        ...

    @property
    def cash_accounting_treatment(self) -> str:
        """Return the observation's cash-accounting treatment."""
        ...

    @property
    def observation_role(self) -> IvaLedgerObservationRole:
        """Return the ledger observation role used by the selector."""
        ...

    @property
    def exemption_article(self) -> IvaExemptionArticle | None:
        """Return the exemption article when the observation is exempt."""
        ...

    @property
    def applied_rate(self) -> Decimal | None:
        """Return the applied IVA rate as a fraction, when known."""
        ...

    @property
    def deduction_fact_kind(self) -> IvaDeductionFactKind | None:
        """Return the fact-0085 deduction kind, when the row bears a deduction."""
        ...

    @property
    def art_104_tres_exclusion(self) -> Art104TresExclusion | None:
        """Return the art. 104.Tres exclusion declared on the source row, when any."""
        ...


class _IvaReachabilityProbeObservation(NamedTuple):
    """Minimal shape carrying only the axes the IVA matcher reads.

    Stands in for :class:`IvaLedgerObservation` so the probe never needs the
    full record's unrelated required fields (ledger id, dates, amounts). The
    matcher reads exactly these attributes, which is the seam that makes
    the substitution legitimate.
    """

    category: IvaCategory
    rate_kind: IvaRateKind
    flow_direction: IvaFlowDirection
    cash_accounting_treatment: str
    observation_role: IvaLedgerObservationRole
    exemption_article: IvaExemptionArticle | None
    # The probe asks whether a binding is REACHABLE by some observation, so it
    # supplies the rate the binding under test names rather than a fixed value:
    # a rate-specific binding is reachable, just not by a differently-rated line.
    applied_rate: Decimal | None = None
    # Same reasoning for the deduction kind: a kind-specific binding is asked
    # whether a row of a kind it names can reach it.
    deduction_fact_kind: IvaDeductionFactKind | None = None
    # A row with no declared exclusion reaches every binding, so the probe asks
    # with none: a binding excluding declared rows is still reachable.
    art_104_tres_exclusion: Art104TresExclusion | None = None


def iva_reachability_probe(selector: LedgerIvaProvider) -> None:
    """Assert the selector matches at least one constructible observation shape.

    Builds a synthetic observation from the selector's OWN declared values and
    runs it through the real matcher this family's resolver builds
    (:func:`iva_build_matcher`), not a reimplementation of the match rule.
    A selector whose matcher accepts no shape assembled from its own
    declarations can never resolve a value: the binding aggregates to zero
    forever, indistinguishable from a taxpayer with no IVA of that kind.

    This family is where a selector-derived probe genuinely bites, and the
    reason is worth stating because it is not true of every family. Every
    multi-value axis is non-empty -- ``categories``, ``rate_kinds``,
    ``observation_roles`` and ``cash_accounting_treatments`` carry
    ``MinLen(1)``, while ``exemption_articles`` is either absent or non-empty
    and ``flow_direction`` is a single enum. The probe therefore confirms the
    declared combination itself can reach the matcher without inventing an
    implicit observation role or cash-accounting policy.

    What this cannot catch, stated so no reader over-trusts it:

    * It never touches real ledger data, so it proves the selector CAN match a
      shape, never that any real row DOES.
    * It cannot catch a matcher that accepts the WRONG rows, only one that
      accepts none.
    * It cannot catch a resolver that aggregates correctly-matched rows
      incorrectly. That residual blind spot needs a data-carrying check, and
      no build-time data-free check can observe it.
    """
    matcher = iva_build_matcher(selector)
    probe = _IvaReachabilityProbeObservation(
        category=selector.categories[0],
        rate_kind=selector.rate_kinds[0],
        flow_direction=selector.flow_direction,
        # Both role and treatment policies are deliberately explicit and
        # non-empty; reachability may therefore exercise their first declared
        # members without introducing an implicit default.
        cash_accounting_treatment=selector.cash_accounting_treatments[0],
        observation_role=selector.observation_roles[0],
        exemption_article=(
            selector.exemption_articles[0]
            if (selector.exemption_articles is not None and selector.exemption_articles)
            else None
        ),
        # Offer the first rate the selector names, so a rate-specific binding is
        # asked whether ANY line can reach it rather than whether a rate-less one
        # can. A None here would fail every rate-specific binding at build time
        # and read as "unreachable" when the binding is simply particular.
        applied_rate=(
            selector.applied_rates[0] if (selector.applied_rates is not None and selector.applied_rates) else None
        ),
        deduction_fact_kind=(
            selector.deduction_fact_kinds[0]
            if (selector.deduction_fact_kinds is not None and selector.deduction_fact_kinds)
            else None
        ),
    )
    if not matcher(probe):
        raise RegistryValidationError(
            "ledger_iva_aggregation selector matches no constructible observation shape -- "
            "the binding can never resolve a value from any ledger data",
        )


def _iva_ledger_observation_matches_selector(
    observation: IvaSelectorAxesProtocol,
    selector: LedgerIvaProvider,
    *,
    categories: set[IvaCategory],
    rate_kinds: set[IvaRateKind],
) -> bool:
    if observation.category not in categories:
        return False
    if observation.rate_kind not in rate_kinds:
        return False
    if observation.flow_direction != selector.flow_direction:
        return False
    if observation.cash_accounting_treatment not in set(selector.cash_accounting_treatments):
        return False
    if observation.observation_role not in set(selector.observation_roles):
        return False
    return _iva_optional_selector_axes_match(observation, selector)


def _iva_optional_selector_axes_match(
    observation: IvaSelectorAxesProtocol,
    selector: LedgerIvaProvider,
) -> bool:
    if selector.applied_rates is not None and observation.applied_rate not in set(selector.applied_rates):
        return False
    if selector.deduction_fact_kinds is not None and observation.deduction_fact_kind not in set(
        selector.deduction_fact_kinds,
    ):
        return False
    if selector.excluded_art_104_tres_exclusions is not None and observation.art_104_tres_exclusion in set(
        selector.excluded_art_104_tres_exclusions
    ):
        return False
    return selector.exemption_articles is None or observation.exemption_article in set(selector.exemption_articles)


def iva_build_matcher(selector: LedgerIvaProvider) -> Callable[[IvaSelectorAxesProtocol], bool]:
    """Build a predicate matching IVA ledger observations to a selector's categories and rates."""
    categories = set(selector.categories)
    rate_kinds = set(selector.rate_kinds)

    def matcher(observation: IvaSelectorAxesProtocol) -> bool:
        return _iva_ledger_observation_matches_selector(
            observation,
            selector,
            categories=categories,
            rate_kinds=rate_kinds,
        )

    return matcher


def _iva_aggregate(matched: Sequence[IvaLedgerObservation], selector: LedgerIvaProvider) -> Decimal:
    if selector.fact == "iva_amount_sum":
        return sum((observation.iva_amount for observation in matched), Decimal("0"))
    if selector.fact == "recargo_amount_sum":
        return sum((observation.recargo_amount for observation in matched), Decimal("0"))
    return sum((observation.base_amount for observation in matched), Decimal("0"))


def resolve_ledger_iva_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_iva_aggregation`` binding on ``revision``.

    Filters observations by the three classification axes (category in
    selector.categories, rate_kind in selector.rate_kinds, flow_direction
    matches selector.flow_direction) and aggregates the matched lines'
    iva_amount, recargo_amount, or base_amount per the declared fact.
    Delegates the filter/aggregate skeleton to
    :func:`resolve_ledger_family_binding_values`, shared by every ledger
    family resolver; the per-selector ``categories`` / ``rate_kinds`` sets
    are built once when the matcher closure is constructed for a binding,
    not once per observation.

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
        source_kind=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        provider_model=LedgerIvaProvider,
        build_matcher=iva_build_matcher,
        aggregate=_iva_aggregate,
    )


def unsupported_ledger_iva_observations(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
) -> tuple[IvaLedgerObservation, ...]:
    """Return IVA observations no binding on ``revision`` can consume.

    Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family
    carries the campaign's two documented, deliberate asymmetries against
    its six siblings — both load-bearing, neither a gap to "fix":

    1. **``extra_exclusion`` (no sibling has one).** Categories that bear no
       Modelo 303 cuota *by law*
       (the published 0084 cuota-less projection — exempt,
       zero-rated, not-subject, exempt intra-community supplies/exports,
       triangulation, régimen simplificado) are excluded before the binding
       check: they correctly match no cuota binding, so flagging them would
       be a false positive. After the M303 routing tail (domestic /
       intra-community reverse-charge bindings, the import deducible
       binding) landed, every cuota-bearing declarable category has a
       consuming binding, so the residual unsupported set is empty for the
       known declarable categories; the function still fail-closes on any
       *new* declarable triple that no binding selects.
    2. **``is_declarable`` is ``lambda observation: True`` — this family has
       NO zero-amount false-fire guard, unlike every other ledger family.**
       This is intentional, not an oversight: adding one would SUPPRESS
       real findings the current code fires on
       (``no-silent-under-declaration``). Do not add a zero-amount /
       zero-cuota guard here to "match" the other six families.

    Args:
        revision: The :class:`ModeloRevision` whose bindings define the
            supported IVA classification triples.
        observations: Ledger lines to screen.

    Returns:
        Tuple of :class:`IvaLedgerObservation` instances not matched by any binding.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        provider_model=LedgerIvaProvider,
        build_matcher=iva_build_matcher,
        is_declarable=lambda observation: True,
        extra_exclusion=lambda observation: (
            observation.category
            in registry_category_projection("cuota_less_m303", effective_date=observation.transaction_date)
        ),
    )


# The IVA facts excluded from the quantity screen. There are NONE:
# ``base_amount_sum``, ``iva_amount_sum`` and ``recargo_amount_sum`` are three
# INDEPENDENT quantities carried on one line -- the taxable base, the cuota
# charged on it, and the recargo de equivalencia surcharged alongside. No one of
# them stands in for another, so every undrawn one is a real gap.
#
# Contrast the renta side, where three income measures ARE alternatives
# (:data:`_RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS`) and screening all three
# would fire on every revision. The emptiness here is a measured property of
# this family, not an unfilled placeholder, and
# ``test_ledger_quantity_screen_partition`` asserts it so the claim is checked
# rather than left as an absence a later author could fill in unnoticed.
IVA_ALTERNATIVE_MEASURE_FACTS: Mapping[str, str] = dict[str, str]()

#: DERIVED as the complement, exactly as the renta side derives its own, so the
#: two sets cannot drift apart.
IVA_INDEPENDENT_QUANTITY_FACTS: frozenset[str] = independent_quantity_facts(
    LEDGER_IVA_FACTS,
    IVA_ALTERNATIVE_MEASURE_FACTS,
)

#: Per-fact readers for the independent quantities. Keyed on the same
#: selector-fact vocabulary :func:`_iva_aggregate` dispatches on, so a fact
#: cannot be screened under one reading and resolved under another.
_IVA_INDEPENDENT_QUANTITY_READERS: dict[str, Callable[[IvaLedgerObservation], Decimal]] = {
    "base_amount_sum": lambda observation: observation.base_amount,
    "iva_amount_sum": lambda observation: observation.iva_amount,
    "recargo_amount_sum": lambda observation: observation.recargo_amount,
}

assert_quantity_readers_cover_independent_facts(
    "ledger-IVA",
    IVA_INDEPENDENT_QUANTITY_FACTS,
    _IVA_INDEPENDENT_QUANTITY_READERS,
)


def ledger_iva_quantity(fact: str, observation: IvaLedgerObservation) -> Decimal:
    """Return the amount of the independent quantity ``fact`` that ``observation`` carries.

    Read through the same per-fact readers the quantity screen uses, so a row is
    named by exactly the amount the screen found undrawn.

    Raises:
        KeyError: If ``fact`` is not one of :data:`IVA_INDEPENDENT_QUANTITY_FACTS`.
    """
    return _IVA_INDEPENDENT_QUANTITY_READERS[fact](observation)


def declarable_ledger_iva_observations(
    observations: Iterable[IvaLedgerObservation],
) -> tuple[IvaLedgerObservation, ...]:
    """Return the observations whose base an IVA self-assessment return can declare.

    A received operation outside the IVA taxable event bears no IVA soportado,
    and the returns' non-subject boxes declare only operations the taxpayer
    performs, so its base has no box to reach. The registry's
    ``received_outside_iva_scope`` projection names those categories, read on
    each row's own date. Only the received side is dropped: a non-subject supply
    the taxpayer makes keeps its devengado routing and its screens.
    """
    rows = tuple(observations)
    outside_by_date: dict[date, frozenset[IvaCategory] | None] = {}
    for observation in rows:
        on_date = observation.transaction_date
        if on_date not in outside_by_date:
            outside_by_date[on_date] = (
                registry_category_projection("received_outside_iva_scope", effective_date=on_date)
                if observation.flow_direction == received_flow_direction(effective_date=on_date)
                else None
            )
    return tuple(
        observation
        for observation in rows
        if observation.flow_direction != received_flow_direction(effective_date=observation.transaction_date)
        or observation.category not in (outside_by_date[observation.transaction_date] or frozenset())
    )


def unrouted_ledger_iva_quantities(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
) -> tuple[UnroutedLedgerQuantity[IvaLedgerObservation], ...]:
    """Return IVA quantities the rows carry that no binding on ``revision`` draws.

    The quantity-keyed sibling of :func:`unsupported_ledger_iva_observations`,
    and it watches the axis that screen cannot. That one asks whether a ROW is
    selected by some binding; every IVA row carries three independent
    quantities, so a row selected for its cuota reads as consumed while its
    base imponible reaches nothing at all.

    The gap survives a revision declaring the fact. A revision whose
    ``base_amount_sum`` bindings cover the domestic tiers answers yes to "is
    base imponible drawn", yet a category whose CUOTA some binding draws and
    whose base no binding reaches -- as the import and intra-community
    reverse-charge rows were on Modelo 303 and Modelo 390 before their base
    boxes were bound -- is consumed for that cuota, so the row screen is silent
    by construction, and a coverage test keyed on the fact alone would be
    silent too.

    That is why coverage is asked per row and per fact. A screen's value is the
    mechanism, never the instance: this one keeps reporting whatever the
    declared bindings fail to reach, and correctly falls silent on every
    category the committed modelos now cover.

    This function reports; it does not close. Routing a base imponible is
    registry work with its own casillas and grounding.

    Args:
        revision: The :class:`ModeloRevision` whose IVA bindings decide which
            facts are drawn, and which rows each drawing binding reaches.
        observations: Ledger IVA observations to screen.

    Returns:
        One :class:`UnroutedLedgerQuantity` per fact with uncovered non-zero
        rows, ordered by fact name, each carrying only the rows that fact's
        bindings fail to reach.
    """
    return unrouted_ledger_family_quantities(
        revision,
        declarable_ledger_iva_observations(observations),
        source_kind=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        provider_model=LedgerIvaProvider,
        build_matcher=iva_build_matcher,
        read_fact=lambda selector: selector.fact,
        independent_facts=IVA_INDEPENDENT_QUANTITY_FACTS,
        readers=_IVA_INDEPENDENT_QUANTITY_READERS,
    )


def _base_iva_selectors(revision: ModeloRevision) -> tuple[LedgerIvaProvider, ...]:
    """Return the revision's ``base_amount_sum`` IVA selectors in source order."""
    selectors = [
        provider_member(binding, LedgerIvaProvider)
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_IVA_AGGREGATION
    ]
    return tuple(selector for selector in selectors if selector.fact == "base_amount_sum")


def _iva_reachability_probe_for_category(
    category: IvaCategory,
    selector: LedgerIvaProvider,
) -> _IvaReachabilityProbeObservation | None:
    """Build a probe from a selector when it declares ``category``."""
    if category not in selector.categories:
        return None
    return _IvaReachabilityProbeObservation(
        category=category,
        rate_kind=selector.rate_kinds[0],
        flow_direction=selector.flow_direction,
        cash_accounting_treatment=selector.cash_accounting_treatments[0],
        observation_role=selector.observation_roles[0],
        exemption_article=selector.exemption_articles[0]
        if (selector.exemption_articles is not None and selector.exemption_articles)
        else None,
        applied_rate=selector.applied_rates[0]
        if (selector.applied_rates is not None and selector.applied_rates)
        else None,
        deduction_fact_kind=selector.deduction_fact_kinds[0]
        if (selector.deduction_fact_kinds is not None and selector.deduction_fact_kinds)
        else None,
    )


def _iva_category_is_reachable(
    category: IvaCategory,
    matchers: Sequence[tuple[LedgerIvaProvider, Callable[[IvaSelectorAxesProtocol], bool]]],
) -> bool:
    """Return whether a real IVA matcher can accept a declared category probe."""
    for selector, matcher in matchers:
        probe = _iva_reachability_probe_for_category(category, selector)
        if probe is not None and matcher(probe):
            return True
    return False


def structurally_unroutable_iva_base_categories(
    revision: ModeloRevision,
    *,
    out_of_scope: frozenset[IvaCategory] | None = None,
) -> tuple[IvaCategory, ...]:
    """Return :class:`IvaCategory` members no ``base_amount_sum`` binding on ``revision`` could ever reach.

    A fourth axis beside :func:`unsupported_ledger_iva_observations` (is this
    ROW selected) and :func:`unrouted_ledger_iva_quantities` (is this row's
    FACT drawn). Both siblings are OBSERVATION-DEPENDENT: they cannot fire
    until a taxpayer's ledger actually holds a row of the affected category,
    and :func:`unrouted_ledger_iva_quantities` in particular reports only
    *"uncovered non-zero rows"* -- its own docstring states it "must not
    manufacture a finding from" a zero total, which is exactly why it needs no
    category exclusion set: a cuota-less category's cuota is 0.00 BY LAW, so
    it is filtered by the non-zero guard before any exclusion set could matter.

    This screen has no rows to filter on, so it needs the opposite of that
    guard -- an explicit declaration of what is out of scope, because
    "unmentioned" would otherwise mean "unrouted." It answers a question
    neither sibling can: *"could this revision's bindings EVER route this
    category's base, independent of whether any taxpayer has fallen into the
    hole yet?"* True or false from the registry alone, before a single ledger
    row exists. For a filing-grade tool that distinction matters: the first
    taxpayer with an unrouted reverse-charge base should not be the detector.

    Three states result from combining this screen with its siblings, and a
    caller must not collapse two of them into one "no finding":

    - **unroutable**: this screen fires -- no binding on the revision could
      ever draw this category's base, for any observation.
    - **unrouted**: this screen is silent (some binding COULD draw it) but
      :func:`unrouted_ledger_iva_quantities` fires for a real row -- the
      binding exists but a particular row still reached nothing (e.g. a
      binding scoped to one flow direction leaves a row of the same category
      under a different flow direction uncovered).
    - **routed**: both are silent.

    ``out_of_scope`` is deliberately NOT the published 0084 cuota-less
    projection.
    That set answers "does this category produce a cuota?"; this screen asks
    "does this category's BASE reach some casilla?", and several by-law
    cuota-less categories DO carry a real base by law --
    the registry-declared zero-rated category is the proof: zero
    cuota by definition, base-bearing by law. Reusing CUOTA_LESS here would
    suppress exactly the population this screen exists to catch. The default
    is M303's own published 0084 out-of-scope declaration; no
    generic per-modelo scope mechanism exists in the registry today (a
    registry-expressiveness gap in its own right), so a caller working a
    different modelo must supply its own set rather than default into M303's.

    Uses the real production selector narrowing (:func:`provider_member`)
    and matcher (:func:`iva_build_matcher`) -- never a re-implementation of
    the match rule. For each ``base_amount_sum`` binding whose declared
    categories include the candidate, a probe observation is assembled from
    values the selector's OWN declared axes already admit (one representative
    rate kind, the declared flow direction, one representative cash-accounting
    treatment, and one representative applied rate / exemption article where
    the selector restricts them) and run through the real matcher. This never
    guesses a value the selector did not itself declare, so it cannot invent a
    false match.

    Args:
        revision: The :class:`ModeloRevision` whose ``ledger_iva_aggregation``
        bindings decide which categories' base is drawn.
        out_of_scope: Categories this screen must not evaluate at all, because
            "unroutable base" is not a meaningful question for them on this
            modelo. When omitted, the published 0084 M303 projection is
            resolved fail-closed.

    Returns:
        Every :class:`IvaCategory` member not in ``out_of_scope`` for which no
        ``base_amount_sum`` binding on ``revision`` could ever match an
        observation of that category, in enum declaration order.
    """
    if out_of_scope is None:
        out_of_scope = registry_category_projection("m303_base_out_of_scope", effective_date=revision.valid_from)
    base_selectors = _base_iva_selectors(revision)
    matchers = tuple((selector, iva_build_matcher(selector)) for selector in base_selectors)
    return tuple(
        category
        for category in resolve_iva_category_catalogue(effective_date=revision.valid_from).all_categories
        if category not in out_of_scope and not _iva_category_is_reachable(category, matchers)
    )


# Ledger Renta estimación directa gastos aggregation source bindings.
#
# These bindings consume first-slice Modelo 100 gastos observations produced
# by the ledger/Renta aggregation layer. They deliberately aggregate already
# evaluated deductible amounts, so proportionality, legal category eligibility,
# invoice reconciliation, and period/date filtering stay outside the registry
# formula runtime.
#
# The registry accesses only four attributes on each observation. A Protocol
# avoids a cross-domain import (domain.calculations -> domain.renta) that
# would violate the hexagonal direction.

# Casilla IDs covered by the first Renta gastos slice (Modelo 100, period 0A).
# These must stay in sync with the binding selectors in the TOML and with
# domain-owned SpendingCategory -> casilla routing projection (which this
# registry-layer module cannot import directly without reversing the hexagonal
# dependency direction); they are validated at registry load time so
# mismatches surface before any calculation. Coverage is currently a subset of
# the full


def validate_ledger_iva_aggregation_binding(binding: BindingDefinition) -> list[str]:
    """Validate a ``ledger_iva_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`LedgerIvaProvider`; runs
    the fact/aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_iva_aggregation_binding_definition`.
    """
    return ledger_binding_build_diagnostics(
        binding, LedgerIvaProvider, validate_ledger_iva_aggregation_binding_definition
    )
