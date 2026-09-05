"""Repository-backed IVA observation projection from ledger catalogues.

This module classifies bucket-local
:class:`~domain.transactions.TransactionCatalogue` rows into typed
:class:`~domain.calculations.registry.IvaLedgerObservation` records and
binding-ready totals. The source-mesh resolver in :mod:`~._modelo_bindings`
then applies the target
:class:`~domain.calculations.registry.ModeloRevision`, resolves
``ledger_iva_aggregation`` bindings, and surfaces source diagnostics for ledger
rows that no declared binding consumes.

When the bucket's cross-period prorrata register resolves an active
``general`` provisional percentage for the filing year, the aggregation result
carries :class:`IvaLedgerProrrataApportionment`. The binding resolver applies
that percentage only to deducible IVA cuota bindings; bases and output IVA
cuotas stay unapportioned.

The repository-backed entry point constructs a
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository` for the active
bucket when none is supplied. Pre-classified callers can use
:class:`IvaLedgerCandidate` and :func:`aggregate_iva_ledger_candidate_bindings`
to run the same validation and registry binding path.

See Also:
    :mod:`~domain.prorrata_register`
        Per-ejercicio carry home for the provisional percentage consumed by
        the IVA ledger apportionment.
    :class:`~application.aggregation._modelo_bindings.LedgerIvaAggregationSourceResolver`
        Source-mesh adapter that calls this projection and records prorrata
        apportionment provenance.
    :mod:`~application.aggregation.tests.test_iva_ledger_prorrata_apportionment`
        Regression coverage proving the active provisional percentage reduces
        deducible cuotas without reducing bases.
    :mod:`~._renta_ledger`, :mod:`~._renta_income_ledger`, :mod:`~._renta_gasto_ledger`
        Sibling Renta ledger projections.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, Field, StringConstraints, field_serializer, field_validator, model_validator

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.aggregation import BindingSourceKind
from ...core.decimal.constants import HUNDRED
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
from ...core.identity import TransactionId
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...core.prorrata_register import (
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    regime_apportions_deduction,
)
from ...core.prose_elision import ElidedProse
from ...domain.bienes_inversion.register import BienesInversionIvaRegister, validate_investment_asset_reciprocity
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
    unsupported_ledger_iva_observations,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.iva.classification import IvaTerritorialScope
from ...domain.iva.deduction_facts import IvaDeductionClassificationProvenance, validate_iva_deduction_fact
from ...domain.iva.errors import ProrrataInputError
from ...domain.iva.establishment import (
    StatedCountryCodeStatus,
    stated_country_code_status,
    territorial_scope_for_country,
)
from ...domain.iva.flow import IvaFlowDirection, is_deducible_flow
from ...domain.iva.lookup import rate_kinds_for_declared_rate
from ...domain.iva.prorrata import (
    InputClassification,
    ProrrataReference,
    deductible_percentage_for,
    validate_prorrata_reference,
)
from ...domain.iva.schema import (
    EUMemberState,
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.prorrata_register.register import ProrrataRegister
from ...domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ...domain.transactions.models import OutOfWindowTransactionSummary, Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from . import _shared_issue_reasons
from ._business_proportion import business_proportion
from .errors import AggregationValidationError, t

_LedgerId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class IvaLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce IVA observations.

    The first five values are shared with
    :class:`~application.aggregation._renta_ledger.RentaLedgerAggregationIssueReason`
    through :mod:`~application.aggregation._shared_issue_reasons` so cross-ledger telemetry can
    group upstream filter rejections under one key. The remaining values
    are IVA-specific.
    """

    UNSUPPORTED_DIRECTION = _shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    PERSONAL_TRANSACTION = _shared_issue_reasons.PERSONAL_TRANSACTION
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    MISSING_TAXABLE_BASE = "missing_taxable_base"
    MISSING_IVA_AMOUNT = "missing_iva_amount"
    MISSING_IVA_RATE = "missing_iva_rate"
    UNSUPPORTED_IVA_RATE = "unsupported_iva_rate"
    # The transaction's DATE is reached by no tier bearing a positive rate, so
    # no tier could match whatever positive rate the row carries. Scoped to the
    # positive tiers rather than to every record because a declared zero
    # classifies through the zero-tier exemption and never arrives here, so the
    # zero tier's own reach says nothing about whether this row was priceable.
    # Distinct from
    # UNSUPPORTED_IVA_RATE, which means the date is covered and the rate still
    # matched no tier: there the operator's rate is what needs looking at, here
    # it is the year. Collapsing the two tells a taxpayer filing an
    # out-of-coverage year that their rate is wrong, sending them to correct a
    # figure that was right.
    IVA_RATE_DATE_OUTSIDE_TABLE_COVERAGE = "iva_rate_date_outside_table_coverage"
    # The row declares a 0 % rate and a non-zero cuota, which its own declared
    # rate makes arithmetically impossible: cuota is base x tipo, so a zero
    # tipo admits only a zero cuota. This is corrupt data rather than an
    # unrouted value, so it is refused here rather than routed onward. Routing
    # it instead would put money AEAT can disprove from the filed record into a
    # 0 % box -- the return publishes both the rate and the cuota, so the
    # contradiction is checkable arithmetically without any other source.
    CUOTA_ON_ZERO_RATED_ROW = "cuota_on_zero_rated_row"
    # The mirror of the above, one field over. The operator declared a category
    # whose cuota is zero BY LAW for the side of the operation this row is on --
    # an issued inversión del sujeto pasivo supply, an exempt or not-subject
    # operation, an exportación, an entrega intracomunitaria -- and then declared
    # a non-zero tipo on it. A tipo is what produces a cuota, so the two facts
    # contradict each other exactly as a zero tipo contradicts a non-zero cuota.
    # The zero-by-law expectation is READ from the Axis-A component table rather
    # than re-listed here: that table is already the invoices path's authority
    # for this same legal fact, and a second list beside it is how the two paths
    # came to disagree in the first place.
    NON_ZERO_RATE_ON_ZERO_CUOTA_CATEGORY = "non_zero_rate_on_zero_cuota_category"
    # The declared category is directional by law and the row is on the side it
    # cannot occur on -- an entrega intracomunitaria the taxpayer RECEIVED, an
    # exportación they received, an adquisición they issued. The Axis-A table
    # declares this per pair, and reading it is the whole check.
    #
    # A SIBLING of the screen above, not an extension of it. "This operation has
    # no cuota" and "this operation does not exist" are different questions: a
    # non-arising pair declares every component UNKNOWN rather than ZERO_BY_LAW,
    # so the zero-cuota predicate correctly answers False here. Merging the two
    # would have made the cuota screen fire on operations that legitimately bear
    # no cuota.
    #
    # The error direction is OVER-deduction: an intra-community supply mis-sided
    # to received routes its cuota to soportado and claims input IVA on an
    # operation LIVA art. 25 does not permit a received side of. Nothing else in
    # this apparatus watches that direction.
    NON_ARISING_CATEGORY_FOR_INVOICE_SIDE = "non_arising_category_for_invoice_side"
    MISSING_EUR_TAX_SUBSTRATE = "missing_eur_tax_substrate"
    INVALID_PRORRATA_REFERENCE = "invalid_prorrata_reference"
    UNSUPPORTED_IVA_CATEGORY = "unsupported_iva_category"
    # Ley 37/1992 art. 25 exempts on the acquirer's IVA IDENTIFICATION in
    # another Member State, not on where it is established, so these two read
    # `counterparty_identification_state`. Keyed on establishment they landed in
    # money in BOTH directions: a Spanish-established acquirer holding a German
    # IVA number was refused an exemption art. 25 grants, and a
    # German-established acquirer purchasing under a Spanish NIF-IVA had a
    # domestic supply zero-rated. Absent identification refuses here rather than
    # falling back to the country -- that fallback IS the defect.
    MISSING_COUNTERPARTY_IDENTIFICATION_STATE = "missing_counterparty_identification_state"
    DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION = "domestic_identification_on_intra_community_transaction"
    EU_MEMBER_STATE_ON_EXPORT_TRANSACTION = "eu_member_state_on_export_transaction"
    # The export families are the one place absence of an EU member state used
    # to be read as PRESENCE of third-country establishment. It is not: the
    # establishment field could not represent a third country at all, so every
    # unrecorded establishment resolved to the same blank a genuine export did.
    # This fires when nothing positively places the counterparty OUTSIDE the
    # Union. A country our own vocabulary has not catalogued is spared -- that
    # is our data gap, not the operator's -- so this names only an absent,
    # malformed or ISO-unassigned code.
    MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT = "missing_counterparty_establishment_on_export"
    CASH_ACCOUNTING_EXCLUDED_CATEGORY = "cash_accounting_excluded_category"
    MISSING_DEDUCTION_CLASSIFICATION = "missing_deduction_classification"


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.
_IssueDetail = Annotated[str, ElidedProse(512)]


class IvaLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while projecting IVA ledger observations."""

    model_config = _STRICT_FROZEN

    # NOT core.identity.TransactionId, deliberately: most call sites feed a real
    # Transaction's id, but aggregate_iva_ledger_candidates feeds candidate.ledger_id
    # (IvaLedgerCandidate.ledger_id: _LedgerId, 1-128 chars, no hex-64 pattern) --
    # a pre-classified ledger line that need not be a catalogued Transaction. The
    # 128-char bound below matches _LedgerId's own bound, not TransactionId's.
    transaction_id: str = Field(min_length=1, max_length=128)
    reason: IvaLedgerAggregationIssueReason
    detail: _IssueDetail


class ProrrataLedgerReference(BaseModel):
    """Bucket-local ledger row pointer to a legal IVA prorrata reference."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    transaction_date: date
    reference: ProrrataReference
    base_amount: Decimal = Field(..., ge=Decimal("0"))
    input_iva_amount: Decimal = Field(..., ge=Decimal("0"))


class IvaLedgerSectorApportionment(BaseModel):
    """Per-sector prorrata apportionment for a sectores-diferenciados bucket.

    Under LIVA arts. 9.1.c / 101 a taxpayer with differentiated sectors applies
    the deduction regime separately per sector. Each declared sector carries its
    own provisional ``percentage`` and its own ``regime`` (a sector may run
    general while another runs especial); the sector-aware binding resolver
    applies THIS sector's apportionment to every deducible cuota whose
    observation carries the matching ``sector_id``.

    See Also:
        :class:`~domain.prorrata_register.SectorDefinition`
            Operator-declared sector this apportionment resolves for.
    """

    model_config = _STRICT_FROZEN

    sector_id: str = Field(min_length=1, max_length=64)
    percentage: Decimal = Field(..., ge=Decimal("0"), le=HUNDRED)
    regime: ProrrataRegisterRegime = ProrrataRegisterRegime.GENERAL


class IvaLedgerProrrataApportionment(BaseModel):
    """Prorrata percentage applied to deducible ledger IVA cuotas.

    Under ``regime == GENERAL`` (LIVA art. 104) the single ``percentage`` is
    applied to every deducible cuota binding. Under ``regime == ESPECIAL``
    (LIVA art. 106) ``percentage`` is the general percentage that applies only
    to the COMMON-use inputs; exclusively-deductible inputs deduct in full and
    exclusively-non-deductible inputs deduct nothing, routed per the
    observation's ``input_classification``.

    When ``sector_apportionments`` is non-empty (LIVA arts. 9.1.c / 101), every
    sector-owned input carries one exact declared sector. Cross-sector common
    use is represented only by explicit :attr:`InputClassification.COMMON`;
    a bare missing sector never defaults to common. Empty
    ``sector_apportionments`` is the whole-entity register.

    See Also:
        :class:`~core.ProrrataProvisionalProvenance`
            Regulated source of the provisional percentage carried on this
            apportionment.
        :func:`resolve_iva_ledger_binding_values`
            Applies the percentage after registry selector resolution.
    """

    model_config = _STRICT_FROZEN

    percentage: Decimal = Field(..., ge=Decimal("0"), le=HUNDRED)
    provenance: ProrrataProvisionalProvenance
    regime: ProrrataRegisterRegime = ProrrataRegisterRegime.GENERAL
    source_observation_ref: str | None = Field(default=None, min_length=1)
    authorisation_reference: str | None = Field(default=None, min_length=1)
    sector_apportionments: tuple[IvaLedgerSectorApportionment, ...] = ()


class IvaDifferentiatedDeductionContribution(BaseModel):
    """Immutable canonical apportioned contribution for one sector/source family."""

    model_config = _STRICT_FROZEN

    sector_id: str = Field(min_length=1, max_length=64)
    deduction_fact_kind: IvaDeductionFactKind
    source_ledger_ids: tuple[str, ...]
    base_amount: Decimal
    deducible_iva_amount: Decimal

    @field_validator("source_ledger_ids")
    @classmethod
    def _source_ledger_ids_are_unique_and_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not ledger_id.strip() for ledger_id in value):
            raise ValueError("differentiated deduction source ledger ids must be nonblank")
        if len(value) != len(set(value)):
            raise ValueError("differentiated deduction source ledger ids must be unique")
        return value


class AnnualDeducibleTotalsByRegime(BaseModel):
    """The ejercicio's whole-year deducible IVA cuota under both prorrata regimes.

    The settlement input to the LIVA art. 103.Dos.2.º mandatory-especial
    check (``build_prorrata_especial_mandatory_advisory``): art. 103.Dos.2.º makes
    prorrata especial obligatory when the deducción under the general regime
    exceeds the deducción under the especial regime by ten percent or more.
    ``deduction_under_general`` is mechanically derivable for any bucket (art. 104
    applies one whole-entity percentage), so it is always honest; the especial
    total (art. 106 per-input classification) is honest only when the register
    regime is ESPECIAL, or when every deducible soportado row of the ejercicio
    carries a declared ``input_classification`` — ``unclassified_deducible_count``
    records how many deducible soportado observations are still unclassified, so
    the caller can decide whether the especial total is honestly computable or the
    filer must first classify.

    See Also:
        :func:`compute_annual_deducible_totals_by_regime`
            Builds this record from one annual observation aggregation and two
            apportionment passes.
    """

    model_config = _STRICT_FROZEN

    deduction_under_general: Decimal = Field(..., ge=Decimal("0"))
    deduction_under_especial: Decimal = Field(..., ge=Decimal("0"))
    unclassified_deducible_count: int = Field(..., ge=0)
    regime: ProrrataRegisterRegime


class IvaLedgerCandidate(BaseModel):
    """One pre-classified ledger line for generic IVA aggregation.

    This is the application hand-off shape for IVA facts that cannot be
    inferred safely from a bank transaction direction plus a rate:
    exenciones, no-sujetas, recargo de equivalencia, intra-community
    reverse-charge operations, imports/exports, and explicit
    adjustments. Upstream classifiers must supply the authoritative IVA
    category, rate kind, and flow direction before this layer creates a
    registry-ready :class:`IvaLedgerObservation`.
    """

    model_config = _STRICT_FROZEN

    ledger_id: _LedgerId
    transaction_date: date
    category: IvaCategory
    exemption_article: IvaExemptionArticle | None = None
    rate_kind: IvaRateKind
    flow_direction: IvaFlowDirection
    base_amount: Decimal
    iva_amount: Decimal
    deduction_fact_kind: IvaDeductionFactKind | None = None
    deduction_provenance: IvaDeductionClassificationProvenance | None = None
    investment_asset_id: str | None = Field(default=None, min_length=1, max_length=128)
    rectifies_ledger_id: str | None = Field(default=None, min_length=1, max_length=128)
    prorrata_reference_id: _LedgerId | None = None
    cash_accounting_treatment: IvaCashAccountingTreatment = IvaCashAccountingTreatment.NONE
    observation_role: IvaLedgerObservationRole
    input_classification: InputClassification | None = None
    prorrata_sector_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def _enforce_exemption_article_category(self) -> IvaLedgerCandidate:
        if self.exemption_article is not None and self.category is not IvaCategory.DOMESTIC_EXEMPT:
            raise AggregationValidationError(
                t("aggregation.iva_ledger.errors.unsupported_iva_category"),
                context={
                    "ledger_id": self.ledger_id,
                    "category": self.category.value,
                    "exemption_article": self.exemption_article.value,
                },
            )
        if not is_deducible_flow(self.flow_direction) or self.category is IvaCategory.RECARGO_EQUIVALENCIA:
            if self.deduction_fact_kind is not None or self.deduction_provenance is not None:
                raise AggregationValidationError(
                    t("aggregation.iva_ledger.errors.output_facts_carry_deduction_authority"),
                    context={
                        "ledger_id": self.ledger_id,
                        "flow_direction": self.flow_direction.value,
                        "category": self.category.value,
                    },
                )
            return self
        if self.deduction_fact_kind is None or self.deduction_provenance is None:
            raise AggregationValidationError(
                t("aggregation.iva_ledger.errors.input_facts_missing_deduction_authority"),
                context={
                    "ledger_id": self.ledger_id,
                    "flow_direction": self.flow_direction.value,
                    "category": self.category.value,
                },
            )
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
        )
        return self


class IvaLedgerAggregation(BaseModel):
    """IVA observations produced from one bucket-local transaction catalogue.

    ``out_of_window_summary`` is only populated by repository-backed date
    partitions. Full-catalogue aggregation continues to emit row-level issues
    because every transaction is already loaded for classification.
    """

    model_config = _STRICT_FROZEN

    period: Period
    observations: Sequence[IvaLedgerObservation] = Field(default_factory=tuple)
    prorrata_references: Sequence[ProrrataLedgerReference] = Field(default_factory=tuple)
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None
    issues: Sequence[IvaLedgerAggregationIssue] = Field(default_factory=tuple)
    out_of_window_summary: OutOfWindowTransactionSummary | None = None
    # Ledger ids of operator-tagged LIVA art. 104.Tres judgment exclusions
    # (foreign PE, non-habitual inmobiliario/financiero). The prorrata annual
    # volume rollup skips these on the ledger side so the reconciliation does
    # not count operations the law removes from both terms of the ratio. The
    # operations' own IVA cuota observations are unaffected and still aggregate.
    art_104_tres_excluded_ledger_ids: tuple[str, ...] = ()

    @field_validator("observations")
    @classmethod
    def _freeze_observations(cls, value: Sequence[IvaLedgerObservation]) -> tuple[IvaLedgerObservation, ...]:
        return tuple(value)

    @field_validator("art_104_tres_excluded_ledger_ids")
    @classmethod
    def _freeze_excluded_ledger_ids(cls, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(value)

    @field_validator("prorrata_references")
    @classmethod
    def _freeze_prorrata_references(
        cls,
        value: Sequence[ProrrataLedgerReference],
    ) -> tuple[ProrrataLedgerReference, ...]:
        return tuple(value)

    @field_validator("issues")
    @classmethod
    def _freeze_issues(cls, value: Sequence[IvaLedgerAggregationIssue]) -> tuple[IvaLedgerAggregationIssue, ...]:
        return tuple(value)

    @model_validator(mode="after")
    def _rectifications_are_consumed_once(self) -> IvaLedgerAggregation:
        rectified_ids = [
            observation.rectifies_ledger_id
            for observation in self.observations
            if observation.deduction_fact_kind is IvaDeductionFactKind.RECTIFICATION
        ]
        if len(rectified_ids) != len(set(rectified_ids)):
            raise AggregationValidationError(
                t("aggregation.iva_ledger.errors.rectification_consumed_more_than_once"),
                context={"rectified_ledger_id_count": len(rectified_ids)},
            )
        return self

    @field_serializer("observations")
    def _serialize_observations(
        self,
        value: Sequence[IvaLedgerObservation],
    ) -> tuple[IvaLedgerObservation, ...]:
        return tuple(value)

    @field_serializer("prorrata_references")
    def _serialize_prorrata_references(
        self,
        value: Sequence[ProrrataLedgerReference],
    ) -> tuple[ProrrataLedgerReference, ...]:
        return tuple(value)

    @field_serializer("issues")
    def _serialize_issues(
        self,
        value: Sequence[IvaLedgerAggregationIssue],
    ) -> tuple[IvaLedgerAggregationIssue, ...]:
        return tuple(value)


def aggregate_iva_ledger_observations_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    investment_asset_register: BienesInversionIvaRegister | None = None,
    investment_asset_profile_id: str | None = None,
) -> IvaLedgerAggregation:
    """Load the bucket-local transaction catalogue and project IVA observations.

    Returns an :class:`IvaLedgerAggregation`.

    Args:
        bucket_id: The profile bucket every supplied repository must be scoped
            to; a divergent repository bucket is refused, not silently used.
        period: The filing period whose transactions are projected.
        prorrata_register_repository: The canonical register repository read for
            the active general-prorrata provisional percentage. Required, so no
            caller can fall back to an implicitly constructed register whose
            bucket nobody checked.
        transaction_repository: Catalogue repository; defaults to the bucket's
            own, which also supplies the bienes-inversion authority.
        investment_asset_register: Bienes-inversion authority, mandatory
            whenever ``transaction_repository`` is injected.
        investment_asset_profile_id: Profile owning that register.
    """
    if prorrata_register_repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.bucket_mismatch"),
            context={
                "bucket_id": bucket_id,
                "repository_bucket_id": prorrata_register_repository.bucket_id,
            },
        )
    if transaction_repository is None:
        concrete_repository = TransactionCatalogueRepository(bucket_id=bucket_id)
        investment_asset_register = concrete_repository.migrate_iva_deduction_authority(asset_profile_id=bucket_id)
        repository: TransactionCatalogueRepositoryProtocol = concrete_repository
        investment_asset_profile_id = bucket_id
    else:
        repository = transaction_repository
        if repository.bucket_id != bucket_id:
            raise AggregationValidationError(
                t("aggregation.iva_ledger.errors.bucket_mismatch"),
                context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
            )
        if investment_asset_register is None or investment_asset_profile_id is None:
            raise AggregationValidationError(
                t("aggregation.iva_ledger.errors.injected_repositories_missing_bienes_inversion_authority"),
                context={"bucket_id": bucket_id},
            )
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    prorrata_apportionment = _active_prorrata_apportionment(
        bucket_id=bucket_id,
        ejercicio=period.filing_year,
        prorrata_register_repository=prorrata_register_repository,
    )
    # Only the in-window subset is decrypted and classified. Out-of-window
    # catalogue rows come from the plaintext date index and are reported
    # uniformly as ``OUTSIDE_PERIOD`` because decrypted-field gates cannot run
    # for those rows. A period with no calendar span falls back to the
    # unfiltered load.
    if not period.has_date_span():
        result = aggregate_iva_ledger_observations(
            repository.load(),
            period=period,
            prorrata_apportionment=prorrata_apportionment,
            ledger_profile_id=bucket_id,
            investment_asset_register=investment_asset_register,
            investment_asset_profile_id=investment_asset_profile_id,
        )
    else:
        partition = repository.partition_by_date_range(period.start_date, period.end_date)
        result = aggregate_iva_ledger_observations(
            partition.in_window,
            period=period,
            prorrata_apportionment=prorrata_apportionment,
            ledger_profile_id=bucket_id,
            investment_asset_register=investment_asset_register,
            investment_asset_profile_id=investment_asset_profile_id,
        )
        out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
            partition.out_of_window,
        )
        result = result.model_copy(
            update={"out_of_window_summary": out_of_window_summary},
        )
    _validate_investment_asset_authority(
        result.observations,
        period=period,
        ledger_profile_id=bucket_id,
        investment_asset_register=investment_asset_register,
        investment_asset_profile_id=investment_asset_profile_id,
    )
    return result


def _validate_investment_asset_authority(
    observations: Sequence[IvaLedgerObservation],
    *,
    period: Period,
    ledger_profile_id: str | None,
    investment_asset_register: BienesInversionIvaRegister | None,
    investment_asset_profile_id: str | None,
) -> None:
    """Require explicit owner inputs before an investment fact can aggregate."""
    has_investment_observation = any(
        observation.deduction_fact_kind is not None and observation.deduction_fact_kind.is_investment_acquisition
        for observation in observations
    )
    if not has_investment_observation and investment_asset_register is None:
        return
    if ledger_profile_id is None or investment_asset_register is None or investment_asset_profile_id is None:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.investment_observations_missing_bienes_inversion_authority"),
            context={
                "filing_year": period.filing_year,
                "has_ledger_profile_id": ledger_profile_id is not None,
                "has_investment_asset_register": investment_asset_register is not None,
                "has_investment_asset_profile_id": investment_asset_profile_id is not None,
            },
        )
    validate_investment_asset_reciprocity(
        observations=observations,
        register=investment_asset_register,
        ledger_profile_id=ledger_profile_id,
        asset_profile_id=investment_asset_profile_id,
        filing_year=period.filing_year,
    )


def validate_iva_ledger_observation(candidate: IvaLedgerCandidate) -> IvaLedgerObservation:
    """Validate a pre-classified IVA candidate and return an :class:`IvaLedgerObservation`.

    The validator does not re-classify the operation and does not derive
    IVA from the base. It only blocks sentinel categories that are not
    declarable ledger facts; the category, rate, and flow axes must have
    been resolved upstream from invoice/operation evidence.
    """
    if candidate.category in {IvaCategory.UNKNOWN, IvaCategory.ERRONEOUS_INVOICE}:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.unsupported_iva_category"),
            context={
                "ledger_id": candidate.ledger_id,
                "category": candidate.category.value,
            },
        )
    return IvaLedgerObservation(
        ledger_id=candidate.ledger_id,
        transaction_date=candidate.transaction_date,
        category=candidate.category,
        exemption_article=candidate.exemption_article,
        rate_kind=candidate.rate_kind,
        flow_direction=candidate.flow_direction,
        base_amount=candidate.base_amount,
        iva_amount=candidate.iva_amount,
        prorrata_reference_id=candidate.prorrata_reference_id,
        cash_accounting_treatment=candidate.cash_accounting_treatment,
        observation_role=candidate.observation_role,
        input_classification=candidate.input_classification,
        prorrata_sector_id=candidate.prorrata_sector_id,
        deduction_fact_kind=candidate.deduction_fact_kind,
        deduction_provenance=candidate.deduction_provenance,
        investment_asset_id=candidate.investment_asset_id,
        rectifies_ledger_id=candidate.rectifies_ledger_id,
    )


def validate_iva_ledger_observations(candidates: Iterable[IvaLedgerCandidate]) -> tuple[IvaLedgerObservation, ...]:
    """Validate every pre-classified IVA candidate in input order.

    Returns a tuple of :class:`IvaLedgerObservation` instances.
    """
    return tuple(validate_iva_ledger_observation(candidate) for candidate in candidates)


def aggregate_iva_ledger_candidates(
    candidates: Iterable[IvaLedgerCandidate],
    *,
    period: Period,
    ledger_profile_id: str,
    investment_asset_register: BienesInversionIvaRegister,
    investment_asset_profile_id: str,
) -> IvaLedgerAggregation:
    """Project pre-classified IVA candidates into period-scoped observations.

    This path complements :func:`aggregate_iva_ledger_observations`,
    which remains the domestic-rate projection from bank
    transactions. Pre-classified candidates are required for non-domestic
    IVA and adjustments because those axes cannot be recovered from a
    transaction amount or direction without guessing.

    Returns an :class:`IvaLedgerAggregation` carrying the accepted
    observations and any period-exclusion issues.
    """
    resolved_period = period
    observations: list[IvaLedgerObservation] = []
    issues: list[IvaLedgerAggregationIssue] = []
    for candidate in candidates:
        if not resolved_period.contains(candidate.transaction_date):
            issues.append(
                IvaLedgerAggregationIssue(
                    transaction_id=candidate.ledger_id,
                    reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                    detail=(f"transaction date {candidate.transaction_date.isoformat()} is outside {resolved_period}"),
                ),
            )
            continue
        observations.append(validate_iva_ledger_observation(candidate))
    result = IvaLedgerAggregation(
        period=resolved_period,
        observations=tuple(observations),
        issues=tuple(issues),
    )
    _validate_investment_asset_authority(
        result.observations,
        period=period,
        ledger_profile_id=ledger_profile_id,
        investment_asset_register=investment_asset_register,
        investment_asset_profile_id=investment_asset_profile_id,
    )
    return result


def aggregate_iva_ledger_candidate_bindings(
    revision: ModeloRevision,
    candidates: Iterable[IvaLedgerCandidate],
    *,
    period: Period,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None,
    ledger_profile_id: str,
    investment_asset_register: BienesInversionIvaRegister,
    investment_asset_profile_id: str,
) -> dict[BindingId, Decimal]:
    """Validate pre-classified candidates and resolve registry bindings.

    Args:
        revision: The :class:`ModeloRevision` used to resolve binding values.
        candidates: Pre-classified :class:`IvaLedgerCandidate` rows to project
            into engine binding channels.
        period: The aggregation :class:`Period` whose date range bounds the
            candidate set.
        prorrata_apportionment: Optional active general-prorrata percentage to
            apply to deducible IVA cuota bindings after selector resolution.
        ledger_profile_id: Secure profile that owns the candidate ledger facts.
        investment_asset_register: Explicit typed Bienes register authority for
            investment acquisition facts.
        investment_asset_profile_id: Secure profile that owns that register.
    """
    aggregation = aggregate_iva_ledger_candidates(
        candidates,
        period=period,
        ledger_profile_id=ledger_profile_id,
        investment_asset_register=investment_asset_register,
        investment_asset_profile_id=investment_asset_profile_id,
    )
    if aggregation.issues:
        first = aggregation.issues[0]
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.candidate_outside_period"),
            context={
                "ledger_id": first.transaction_id,
                "reason": first.reason.value,
                "detail": first.detail,
            },
        )
    unsupported = unsupported_ledger_iva_observations(revision, aggregation.observations)
    if unsupported:
        first = unsupported[0]
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.unsupported_iva_category"),
            context={
                "ledger_id": first.ledger_id,
                "category": first.category.value,
                "rate_kind": first.rate_kind.value,
                "flow_direction": first.flow_direction.value,
                "revision_id": revision.id,
            },
        )
    return resolve_iva_ledger_binding_values(
        revision,
        aggregation.observations,
        prorrata_apportionment=prorrata_apportionment,
    )


def aggregate_iva_ledger_observations(
    transactions: TransactionCatalogue,
    *,
    period: Period,
    ledger_profile_id: str,
    investment_asset_register: BienesInversionIvaRegister,
    investment_asset_profile_id: str,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None,
) -> IvaLedgerAggregation:
    """Project classified ledger transaction tax facts into an :class:`IvaLedgerAggregation`.

    Args:
        transactions: The :class:`TransactionCatalogue` supplying active ledger entries.
        period: Filing period as a typed :class:`Period` instance.
        ledger_profile_id: Profile that owns the ledger facts.
        investment_asset_register: Explicit Bienes register authority.
        investment_asset_profile_id: Profile that owns the Bienes register.
        prorrata_apportionment: Optional active general-prorrata percentage to
            apply later to deducible IVA cuota binding values.
    """
    resolved_period = period
    observations: list[IvaLedgerObservation] = []
    prorrata_references: list[ProrrataLedgerReference] = []
    issues: list[IvaLedgerAggregationIssue] = []
    art_104_tres_excluded_ledger_ids: list[str] = []
    from ._iva_transaction import classify_iva_transaction

    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
            # Operator reviewed and deliberately excluded this row from filing
            # (a final disposition): omit it silently — no observation, no gate
            # issue. The exclusion is an explicit, recorded operator decision,
            # not an unclassified row that should nag with a "classify me" advisory.
            continue
        outcome = classify_iva_transaction(transaction, resolved_period=resolved_period)
        if outcome.gate_issue is not None:
            issues.append(outcome.gate_issue)
            continue
        if outcome.prorrata_issue is not None:
            issues.append(outcome.prorrata_issue)
        if outcome.prorrata_reference is not None:
            prorrata_references.append(outcome.prorrata_reference)
        observations.extend(outcome.observations)
        # LIVA art. 104.Tres: an operator-declared judgment exclusion removes the
        # operation from BOTH terms of the prorrata ratio. The IVA cuota
        # observations above still aggregate (the operation is a real taxable
        # supply); only the prorrata annual volume rollup skips it, keyed by the
        # ledger id recorded here.
        if transaction.art_104_tres_exclusion is not None:
            art_104_tres_excluded_ledger_ids.append(transaction.transaction_id)
    result = IvaLedgerAggregation(
        period=resolved_period,
        observations=tuple(observations),
        prorrata_references=tuple(prorrata_references),
        prorrata_apportionment=prorrata_apportionment,
        issues=tuple(issues),
        art_104_tres_excluded_ledger_ids=tuple(art_104_tres_excluded_ledger_ids),
    )
    _validate_investment_asset_authority(
        result.observations,
        period=period,
        ledger_profile_id=ledger_profile_id,
        investment_asset_register=investment_asset_register,
        investment_asset_profile_id=investment_asset_profile_id,
    )
    return result


def resolve_iva_ledger_binding_values(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
    *,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None,
) -> dict[BindingId, Decimal]:
    """Resolve IVA ledger bindings, applying general-prorrata to deducible cuotas only.

    Args:
        revision: The :class:`ModeloRevision` whose IVA ledger bindings are
            resolved.
        observations: Typed :class:`IvaLedgerObservation` rows to aggregate.
        prorrata_apportionment: Optional
            :class:`IvaLedgerProrrataApportionment` applied only to deducible
            cuota bindings.

    Under ``regime == GENERAL`` the single provisional percentage multiplies
    every deducible cuota binding (LIVA art. 104). Under ``regime == ESPECIAL``
    the deducible cuota is routed per the observation's ``input_classification``
    (LIVA art. 106.Uno: exclusively-deductible 100%, exclusively-non-deductible
    0%, common at the general percentage) by
    :func:`_apply_especial_apportionment`; the general-regime code path is
    unchanged.

    See Also:
        :func:`~domain.calculations.registry.resolve_ledger_iva_aggregation_binding_values`
            Registry selector resolver that produces the unapportioned binding
            values before this wrapper applies prorrata.
        :class:`~domain.prorrata_register.ProrrataRegisterEntry`
            Source record for the active provisional percentage represented by
            :class:`IvaLedgerProrrataApportionment`.
    """
    observations = tuple(observations)
    binding_values = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    if prorrata_apportionment is None:
        return binding_values
    if prorrata_apportionment.sector_apportionments:
        # Sectores diferenciados (LIVA arts. 9.1.c / 101): route each input to
        # its sector's percentage; common-use (no sector) at art. 104.Dos.
        return _apply_sector_apportionment(
            revision,
            observations,
            binding_values,
            prorrata_apportionment,
        )
    if prorrata_apportionment.regime is ProrrataRegisterRegime.ESPECIAL:
        return _apply_especial_apportionment(
            revision,
            observations,
            binding_values,
            prorrata_apportionment,
        )
    # GENERAL regime — byte-identical to the pre-especial behaviour.
    if prorrata_apportionment.percentage == HUNDRED:
        return binding_values
    multiplier = prorrata_apportionment.percentage / HUNDRED
    deducible_binding_ids = _deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return binding_values
    return {
        binding_id: value * multiplier if binding_id in deducible_binding_ids else value
        for binding_id, value in binding_values.items()
    }


def _apply_especial_apportionment(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    binding_values: dict[BindingId, Decimal],
    apportionment: IvaLedgerProrrataApportionment,
) -> dict[BindingId, Decimal]:
    """Route deducible cuota bindings per LIVA art. 106 prorrata especial.

    Each deducible cuota binding value is recomputed as the sum, over the
    per-classification partitions of ``observations``, of the partition's
    canonically-resolved binding value weighted by that classification's
    art. 106 deductible percentage (:func:`~domain.iva.deductible_percentage_for`):
    exclusively-deductible at 100%, exclusively-non-deductible at 0%, and
    common-use (and unclassified inputs, the mixed-use default) at the
    ``apportionment.percentage`` general percentage. Non-deducible bindings
    (output cuotas, bases, recargo) keep their unapportioned aggregate.

    The partitions are resolved through the SAME canonical registry resolver
    the general path uses (:func:`~domain.calculations.registry.resolve_ledger_iva_aggregation_binding_values`),
    so especial reuses one aggregation path rather than forking selector logic.
    An all-common (or wholly-unclassified) especial bucket therefore reduces to
    the general-percentage result exactly.
    """
    deducible_binding_ids = _deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return binding_values
    general_percentage = apportionment.percentage
    partitions = _partition_by_input_classification(observations)
    apportioned: dict[BindingId, Decimal] = dict.fromkeys(deducible_binding_ids, Decimal("0"))
    for classification, partition_observations in partitions.items():
        if not partition_observations:
            continue
        multiplier = deductible_percentage_for(classification, general_percentage) / HUNDRED
        if multiplier == 0:
            # exclusively-non-deductible: contributes nothing to any deducible cuota.
            continue
        partition_values = resolve_ledger_iva_aggregation_binding_values(revision, partition_observations)
        for binding_id in deducible_binding_ids:
            apportioned[binding_id] += partition_values.get(binding_id, Decimal("0")) * multiplier
    return {
        binding_id: apportioned[binding_id] if binding_id in deducible_binding_ids else value
        for binding_id, value in binding_values.items()
    }


def _partition_by_input_classification(
    observations: Sequence[IvaLedgerObservation],
) -> dict[InputClassification, list[IvaLedgerObservation]]:
    """Bucket ``observations`` by their art. 106 input classification.

    An unclassified observation defaults to :attr:`InputClassification.COMMON`
    (the mixed-use default). Shared by the general especial-regime
    apportionment and the per-partition primitive so both partition
    identically.
    """
    partitions: dict[InputClassification, list[IvaLedgerObservation]] = {
        classification: [] for classification in InputClassification
    }
    for observation in observations:
        classification = observation.input_classification or InputClassification.COMMON
        partitions[classification].append(observation)
    return partitions


def _apportioned_deducible_cuota(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    *,
    percentage: Decimal,
    regime: ProrrataRegisterRegime,
    deducible_binding_ids: frozenset[BindingId],
) -> dict[BindingId, Decimal]:
    """Return only the deducible-cuota binding contributions for one observation set.

    Applies the observation set's regime at ``percentage``: ``GENERAL`` multiplies
    every deducible cuota by ``percentage`` (LIVA art. 104); ``ESPECIAL`` routes
    each deducible cuota per the observation's ``input_classification`` (LIVA
    art. 106.Uno reglas 100%/0%/general), with ``percentage`` as the common
    (regla 3.ª) percentage. Both branches resolve through the SAME canonical
    registry resolver, so one aggregation path drives every regime. This is the
    per-partition primitive the sectores-diferenciados routing composes over each
    sector.
    """
    result: dict[BindingId, Decimal] = dict.fromkeys(deducible_binding_ids, Decimal("0"))
    if regime is ProrrataRegisterRegime.ESPECIAL:
        partitions = _partition_by_input_classification(observations)
        for classification, partition_observations in partitions.items():
            if not partition_observations:
                continue
            multiplier = deductible_percentage_for(classification, percentage) / HUNDRED
            if multiplier == 0:
                continue
            partition_values = resolve_ledger_iva_aggregation_binding_values(revision, partition_observations)
            for binding_id in deducible_binding_ids:
                result[binding_id] += partition_values.get(binding_id, Decimal("0")) * multiplier
        return result
    # GENERAL regime: a single multiplier over the whole observation set.
    multiplier = percentage / HUNDRED
    partition_values = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    for binding_id in deducible_binding_ids:
        result[binding_id] = partition_values.get(binding_id, Decimal("0")) * multiplier
    return result


def _apply_sector_apportionment(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    binding_values: dict[BindingId, Decimal],
    apportionment: IvaLedgerProrrataApportionment,
) -> dict[BindingId, Decimal]:
    """Route deducible cuota bindings per sector (LIVA arts. 9.1.c / 101).

    Partitions input ``observations`` by their exact ``prorrata_sector_id`` and recomputes each
    deducible cuota binding as the sum, over the partitions, of that sector's
    :func:`_apportioned_deducible_cuota` contribution (each sector applies its
    own percentage and regime). Missing or unknown sector identity refuses;
    the sole no-sector case is an explicitly classified cross-sector COMMON
    input, routed through the declared whole-entity common percentage.
    Non-deducible bindings keep their
    unapportioned aggregate. Resolution runs through the SAME canonical registry
    resolver, so the sectored path is one more consumer of the single
    aggregation path.
    """
    deducible_binding_ids = _deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return binding_values
    by_sector, partitions = _sectorized_deduction_partitions(apportionment, observations)
    apportioned: dict[BindingId, Decimal] = dict.fromkeys(deducible_binding_ids, Decimal("0"))
    for sector_key, partition_observations in partitions.items():
        percentage, regime = _partition_apportionment(apportionment, by_sector, sector_key)
        partition_deducible = _apportioned_deducible_cuota(
            revision,
            partition_observations,
            percentage=percentage,
            regime=regime,
            deducible_binding_ids=deducible_binding_ids,
        )
        for binding_id in deducible_binding_ids:
            apportioned[binding_id] += partition_deducible[binding_id]
    return {
        binding_id: apportioned[binding_id] if binding_id in deducible_binding_ids else value
        for binding_id, value in binding_values.items()
    }


def _sectorized_deduction_partitions(
    apportionment: IvaLedgerProrrataApportionment,
    observations: Sequence[IvaLedgerObservation],
) -> tuple[
    dict[str, IvaLedgerSectorApportionment],
    dict[str | None, list[IvaLedgerObservation]],
]:
    by_sector = _sector_apportionments_by_id(apportionment)
    partitions: dict[str | None, list[IvaLedgerObservation]] = {}
    for observation in observations:
        if observation.deduction_fact_kind is None:
            continue
        _append_sectorized_deduction_observation(partitions, by_sector, observation)
    return by_sector, partitions


def _sector_apportionments_by_id(
    apportionment: IvaLedgerProrrataApportionment,
) -> dict[str, IvaLedgerSectorApportionment]:
    by_sector = {sector.sector_id: sector for sector in apportionment.sector_apportionments}
    if len(by_sector) != len(apportionment.sector_apportionments):
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.sectorized_apportionment_duplicate_sectors"),
            context={"declared_sector_count": len(apportionment.sector_apportionments)},
        )
    return by_sector


def _append_sectorized_deduction_observation(
    partitions: dict[str | None, list[IvaLedgerObservation]],
    sectors: dict[str, IvaLedgerSectorApportionment],
    observation: IvaLedgerObservation,
) -> None:
    sector_key = observation.prorrata_sector_id
    if sector_key is None:
        _append_common_sector_observation(partitions, observation)
        return
    sector = _active_sector_apportionment(sectors, sector_key)
    _require_sector_input_classification(sector, observation)
    partitions.setdefault(sector_key, []).append(observation)


def _append_common_sector_observation(
    partitions: dict[str | None, list[IvaLedgerObservation]],
    observation: IvaLedgerObservation,
) -> None:
    if observation.input_classification is not InputClassification.COMMON:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.sectorized_input_missing_sector_identity"),
            context={"ledger_id": observation.ledger_id},
        )
    partitions.setdefault(None, []).append(observation)


def _active_sector_apportionment(
    sectors: dict[str, IvaLedgerSectorApportionment],
    sector_key: str,
) -> IvaLedgerSectorApportionment:
    sector = sectors.get(sector_key)
    if sector is None:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.sectorized_input_unknown_sector"), context={"sector_id": sector_key}
        )
    if sector.regime is ProrrataRegisterRegime.NINGUNA:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.sectorized_input_inactive_sector"), context={"sector_id": sector_key}
        )
    return sector


def _require_sector_input_classification(
    sector: IvaLedgerSectorApportionment,
    observation: IvaLedgerObservation,
) -> None:
    if sector.regime is ProrrataRegisterRegime.ESPECIAL and observation.input_classification is None:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.sectorized_especial_missing_input_classification"),
            context={"sector_id": sector.sector_id, "ledger_id": observation.ledger_id},
        )


def _partition_apportionment(
    apportionment: IvaLedgerProrrataApportionment,
    sectors: dict[str, IvaLedgerSectorApportionment],
    sector_key: str | None,
) -> tuple[Decimal, ProrrataRegisterRegime]:
    if sector_key is None:
        return apportionment.percentage, apportionment.regime
    sector = sectors[sector_key]
    return sector.percentage, sector.regime


def resolve_iva_differentiated_deduction_contributions(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
    *,
    apportionment: IvaLedgerProrrataApportionment,
) -> tuple[IvaDifferentiatedDeductionContribution, ...]:
    """Expose the canonical sector apportionment as immutable per-kind outputs."""
    if not apportionment.sector_apportionments:
        return ()
    rows = tuple(observations)
    _validate_differentiated_observation_identities(rows)
    by_sector = _validated_differentiated_sectors(apportionment, rows)
    deducible_binding_ids = _deducible_cuota_binding_ids(revision)
    return tuple(
        _differentiated_sector_contribution(revision, rows, sector_id, sector, kind, deducible_binding_ids)
        for sector_id, sector in by_sector.items()
        for kind in IvaDeductionFactKind
        if kind is not IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION
    )


def _validate_differentiated_observation_identities(rows: tuple[IvaLedgerObservation, ...]) -> None:
    ledger_ids = tuple(row.ledger_id for row in rows)
    if len(ledger_ids) != len(set(ledger_ids)):
        raise ValueError("differentiated deduction observations contain duplicate ledger identity")
    if any(row.deduction_fact_kind is IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION for row in rows):
        raise ValueError("investment-goods regularisation is owned only by the bienes-inversion register")


def _validated_differentiated_sectors(
    apportionment: IvaLedgerProrrataApportionment, rows: tuple[IvaLedgerObservation, ...]
) -> dict[str, IvaLedgerSectorApportionment]:
    by_sector = {item.sector_id: item for item in apportionment.sector_apportionments}
    if len(by_sector) != len(apportionment.sector_apportionments):
        raise ValueError("differentiated deduction apportionment carries duplicate sectors")
    unknown = sorted({row.prorrata_sector_id for row in rows if row.prorrata_sector_id not in by_sector}, key=str)
    if unknown:
        raise ValueError(f"differentiated deduction observations have missing or unknown sectors: {unknown!r}")
    for row in rows:
        _validate_differentiated_sector_row(by_sector, row)
    return by_sector


def _validate_differentiated_sector_row(
    by_sector: dict[str, IvaLedgerSectorApportionment],
    row: IvaLedgerObservation,
) -> None:
    sector_id = row.prorrata_sector_id
    if sector_id is None:
        raise ValueError("differentiated deduction observation is missing explicit sector identity")
    sector = by_sector[sector_id]
    if sector.regime is ProrrataRegisterRegime.NINGUNA:
        raise ValueError(f"differentiated deduction sector {sector.sector_id!r} is inactive")
    if sector.regime is ProrrataRegisterRegime.ESPECIAL and row.input_classification is None:
        raise ValueError("common-use classification must be explicit under differentiated prorrata especial")


def _differentiated_sector_contribution(
    revision: ModeloRevision,
    rows: tuple[IvaLedgerObservation, ...],
    sector_id: str,
    sector: IvaLedgerSectorApportionment,
    kind: IvaDeductionFactKind,
    deducible_binding_ids: frozenset[str],
) -> IvaDifferentiatedDeductionContribution:
    selected = tuple(row for row in rows if row.prorrata_sector_id == sector_id and row.deduction_fact_kind is kind)
    apportioned = _apportioned_deducible_cuota(
        revision,
        selected,
        percentage=sector.percentage,
        regime=sector.regime,
        deducible_binding_ids=deducible_binding_ids,
    )
    return IvaDifferentiatedDeductionContribution(
        sector_id=sector_id,
        deduction_fact_kind=kind,
        source_ledger_ids=tuple(row.ledger_id for row in selected),
        base_amount=sum((row.base_amount for row in selected), Decimal("0")),
        deducible_iva_amount=sum(apportioned.values(), Decimal("0")),
    )


def _active_prorrata_apportionment(
    *,
    bucket_id: str,
    ejercicio: int,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
) -> IvaLedgerProrrataApportionment | None:
    """Resolve the regime-aware prorrata apportionment for the ejercicio.

    Returns ``None`` when no register entry applies, the entry's regime carries
    no apportionment (``NINGUNA``), or no provisional percentage is resolvable.
    A ``GENERAL`` entry carries the single provisional percentage; an
    ``ESPECIAL`` entry carries the same provisional percentage as the general
    percentage applied to common-use inputs (LIVA art. 106.Uno regla 3.ª),
    with the regime stamped so the binding resolver routes per-input.

    When the register declares a differentiated-sector partition
    (LIVA arts. 9.1.c / 101), the whole-entity (``sector_id = None``) entry is
    the COMMON-use apportionment (art. 104.Dos common percentage) and each
    declared sector's ``(ejercicio, sector_id)`` entry contributes a
    :class:`IvaLedgerSectorApportionment`; a sectorized register therefore also
    requires its common ``sector_id = None`` entry to apportion common-use
    inputs (absent it, no apportionment applies, exactly as for any register
    with no whole-entity entry).
    """
    register = prorrata_register_repository.load()
    base = _sector_scoped_apportionment(register, ejercicio, sector_id=None)
    if base is None:
        return None
    if not register.is_sectorized:
        return base
    sector_apportionments_list: list[IvaLedgerSectorApportionment] = []
    for sector_id in register.sector_ids():
        sector = _sector_scoped_apportionment(register, ejercicio, sector_id=sector_id)
        if sector is None:
            entry = register.entry_for(ejercicio, sector_id=sector_id)
            facts = {"sector_id": sector_id, "ejercicio": ejercicio}
            if entry is None:
                raise AggregationValidationError(
                    t("aggregation.iva_ledger.errors.differentiated_sector_without_filing_year_entry"),
                    context=facts,
                )
            if entry.interrupted or not regime_apportions_deduction(entry.regime):
                raise AggregationValidationError(
                    t("aggregation.iva_ledger.errors.differentiated_sector_inactive_for_filing_year"),
                    context=facts,
                )
            raise AggregationValidationError(
                t("aggregation.iva_ledger.errors.differentiated_sector_without_provisional_percentage"),
                context=facts,
            )
        sector_apportionments_list.append(
            IvaLedgerSectorApportionment(
                sector_id=sector_id,
                percentage=sector.percentage,
                regime=sector.regime,
            )
        )
    sector_apportionments = tuple(sector_apportionments_list)
    return base.model_copy(update={"sector_apportionments": sector_apportionments})


def _sector_scoped_apportionment(
    register: ProrrataRegister,
    ejercicio: int,
    *,
    sector_id: str | None,
) -> IvaLedgerProrrataApportionment | None:
    """Resolve the apportionment for one ``(ejercicio, sector_id)`` register key.

    Returns ``None`` when the key has no apportioning entry (``NINGUNA`` /
    interrupted / absent) or no provisional percentage is resolvable.
    """
    entry = register.entry_for(ejercicio, sector_id=sector_id)
    if entry is None or not regime_apportions_deduction(entry.regime):
        return None
    resolution = register.resolve_provisional(ejercicio, sector_id=sector_id)
    if resolution.percentage is None or resolution.provenance is None:
        return None
    return IvaLedgerProrrataApportionment(
        percentage=resolution.percentage,
        provenance=resolution.provenance,
        regime=entry.regime,
        source_observation_ref=entry.source_observation_ref,
        authorisation_reference=entry.authorisation_reference,
    )


def _deducible_cuota_binding_ids(revision: ModeloRevision) -> frozenset[BindingId]:
    ledger_iva_amount_bindings = {
        binding.id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_IVA_AGGREGATION
        and getattr(binding.selector, "fact", "iva_amount_sum") == "iva_amount_sum"
    }
    binding_ids: set[BindingId] = set()
    for casilla in revision.casillas:
        if "deducible" not in casilla.section:
            continue
        for binding_id in (casilla.binding, *casilla.alternate_bindings):
            if binding_id is not None and binding_id in ledger_iva_amount_bindings:
                binding_ids.add(binding_id)
    return frozenset(binding_ids)


def _unclassified_deducible_soportado_count(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    deducible_binding_ids: frozenset[BindingId],
) -> int:
    """Count deducible-cuota observations that carry no ``input_classification``.

    A deducible soportado observation is one whose own canonically-resolved
    contribution lands on at least one deducible cuota binding (the registry
    selector decides membership; no category is hard-coded here). An observation
    with no declared ``input_classification`` is one the art. 106 especial total
    cannot honestly route, so the general filer must classify it before the art. 103.Dos.2.º
    check can run. The signal drives the CHECK-vs-PROMPT branch in the settlement
    collector.
    """
    count = 0
    for observation in observations:
        if observation.input_classification is not None:
            continue
        single = resolve_ledger_iva_aggregation_binding_values(revision, (observation,))
        if any(single.get(binding_id, Decimal("0")) != Decimal("0") for binding_id in deducible_binding_ids):
            count += 1
    return count


def compute_annual_deducible_totals_by_regime(
    *,
    bucket_id: str,
    ejercicio: int,
    revision: ModeloRevision,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> AnnualDeducibleTotalsByRegime | None:
    """Compute the ejercicio's deducible IVA cuota under both prorrata regimes.

    The plumbing for the LIVA art. 103.Dos.2.º mandatory-especial settlement
    check. Aggregates the ejercicio's annual IVA observations ONCE
    (:func:`aggregate_iva_ledger_observations_from_repositories` over the
    canonical ``0A`` annual :class:`~core.Period`), then resolves
    :func:`resolve_iva_ledger_binding_values` TWICE over the same observations —
    once with a GENERAL-stamped and once with an ESPECIAL-stamped
    :class:`IvaLedgerProrrataApportionment` at the register's resolved percentage
    — and sums the deducible-cuota binding ids under each. One aggregation, two
    apportionment passes through the one canonical resolver
    (``aeat-calculation-aggregation``); no second aggregation
    implementation is introduced.

    Returns ``None`` when no register apportionment resolves for the ejercicio
    (prorrata inapplicable), when the register is sectorized (LIVA arts. 9.1.c /
    101 — the art-103.Dos.2.º comparison composes per sector, a named v1 deferral),
    or when the revision declares no deducible cuota bindings. A negative
    deducible total (an adjustment-heavy degenerate case the art-103.Dos.2
    comparison is undefined over) also returns ``None`` so the check stays silent
    rather than crashing on a non-comparable input.

    Args:
        bucket_id: Active bucket whose annual ledger and prorrata register are
            read.
        ejercicio: The filing year whose annual deducible totals are computed.
        revision: The target :class:`ModeloRevision` whose deducible cuota
            bindings are summed.
        transaction_repository: Optional catalogue repository (defaults to the
            active bucket's).
        prorrata_register_repository: Canonical register repository for the
            same bucket as the transaction catalogue.

    See Also:
        :class:`AnnualDeducibleTotalsByRegime`
            The frozen record returned.
        :func:`~application.calculations.build_prorrata_especial_mandatory_advisory`
            Consumes the two totals to build the mandatory-especial advisory.
    """
    period = Period.from_year_and_code(ejercicio, "0A")
    aggregation = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=bucket_id,
        period=period,
        transaction_repository=transaction_repository,
        prorrata_register_repository=prorrata_register_repository,
    )
    apportionment = aggregation.prorrata_apportionment
    if apportionment is None:
        return None
    if apportionment.sector_apportionments:
        # Sectorized register: the art-103.Dos.2.º comparison composes per sector,
        # a named v1 deferral (LIVA arts. 9.1.c / 101). No branch in v1.
        return None
    deducible_binding_ids = _deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return None
    observations = tuple(aggregation.observations)
    general_apportionment = apportionment.model_copy(update={"regime": ProrrataRegisterRegime.GENERAL})
    especial_apportionment = apportionment.model_copy(update={"regime": ProrrataRegisterRegime.ESPECIAL})
    general_values = resolve_iva_ledger_binding_values(
        revision,
        observations,
        prorrata_apportionment=general_apportionment,
    )
    especial_values = resolve_iva_ledger_binding_values(
        revision,
        observations,
        prorrata_apportionment=especial_apportionment,
    )
    deduction_under_general = sum(
        (general_values.get(binding_id, Decimal("0")) for binding_id in deducible_binding_ids),
        Decimal("0"),
    )
    deduction_under_especial = sum(
        (especial_values.get(binding_id, Decimal("0")) for binding_id in deducible_binding_ids),
        Decimal("0"),
    )
    if deduction_under_general < Decimal("0") or deduction_under_especial < Decimal("0"):
        return None
    return AnnualDeducibleTotalsByRegime(
        deduction_under_general=deduction_under_general,
        deduction_under_especial=deduction_under_especial,
        unclassified_deducible_count=_unclassified_deducible_soportado_count(
            revision,
            observations,
            deducible_binding_ids,
        ),
        regime=apportionment.regime,
    )


#: The categories whose exemption rests on the operation LEAVING the Union.
#:
#: Named rather than spelled at each branch because the export rule now has two
#: refusals reading one membership question, and a second inline literal is how
#: the pair would drift apart.
_EXPORT_CATEGORIES: Final[frozenset[IvaCategory]] = frozenset(
    {
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
    },
)


def _export_establishment_is_answerable(counterparty_country: str | None) -> bool:
    """Return whether this country evidence may carry an export exemption.

    Two different situations are allowed through, and collapsing them would be
    wrong in opposite directions.

    A code the vocabulary places in a third country answers the question
    outright -- that is the exemption's actual premise.

    A code the vocabulary does NOT carry is also allowed through, and that
    carve-out is what separates a guard from a trap. The scope resolver answers
    from a closed table, so a well-formed code naming a real jurisdiction it
    does not list resolves to nothing, and such jurisdictions exist at any
    moment because the table is a bounded subset that grows. The establishment
    is then a gap in OUR data rather than in the operator's, and refusing there
    would reject a legitimate export over a row nobody has written. A refusal an
    operator cannot act on is how they learn to skip refusals, which costs more
    than the case it catches. The ingestion path's
    declared-relief guard spares the same status on the same authority, so the
    two surfaces cannot disagree about what evidence an export needs.

    Everything else is refused: an absent code, a malformed one, and an
    ISO-unassigned pair, each of which genuinely establishes nothing about
    where the party is.
    """
    if territorial_scope_for_country(counterparty_country) is IvaTerritorialScope.THIRD_COUNTRY:
        return True
    return stated_country_code_status(counterparty_country) is StatedCountryCodeStatus.UNCATALOGUED


def validate_intracom_export_counterparty(
    *,
    transaction_id: str,
    category: IvaCategory,
    counterparty_country: str | None,
    eu_member_state: EUMemberState | None,
    identification_state: EUMemberState | None,
) -> IvaLedgerAggregationIssue | None:
    """Return a gate issue when the counterparty/category coupling is violated.

    Rules:

    - ``INTRA_COMMUNITY_SUPPLY`` requires a non-ES ``identification_state``.
    - Export and export-assimilated categories require the counterparty to be
      POSITIVELY established in a third country, and must carry no
      ``EUMemberState``.

    The two rules read DIFFERENT facts, deliberately. Ley 37/1992 art. 25
    exempts on the acquirer holding an IVA identification assigned by another
    Member State and says nothing about where it has its sede, so the
    intra-community rule reads identification and establishment does not enter
    it at all. The export rule is the one genuinely about place -- an export
    leaves the Union -- so it keeps reading establishment.

    Absent identification refuses rather than falling back to
    ``eu_member_state``. That fallback is precisely the defect this shape
    replaced: it read an address fact as a registration fact, over-declaring a
    Spanish-established acquirer holding a German IVA number and silently
    under-declaring a German-established acquirer purchasing under a Spanish
    NIF-IVA.
    """
    if category is IvaCategory.INTRA_COMMUNITY_SUPPLY:
        if identification_state is None:
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE,
                detail=tr(
                    "aggregation.iva_ledger.errors.missing_counterparty_identification_state",
                    default=(
                        "An intra-community supply is exempt on the acquirer's IVA identification in "
                        "another Member State. Record which Member State IVA-identifies this "
                        "counterparty; its country of establishment cannot answer this."
                    ),
                ),
            )
        if identification_state is EUMemberState.ES:
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION,
                detail=tr(
                    "aggregation.iva_ledger.errors.domestic_identification_on_intra_community_transaction",
                    default=(
                        "A counterparty purchasing under a Spanish IVA identification is not an "
                        "intra-community acquirer, whatever its country of establishment."
                    ),
                ),
            )
    if category in _EXPORT_CATEGORIES:
        if eu_member_state is not None:
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION,
                detail=tr(
                    "aggregation.iva_ledger.errors.eu_member_state_on_export_transaction",
                    member_state=eu_member_state.value,
                    default=(
                        "Export or export-assimilated operations must not carry an EU member state; "
                        "got %{member_state}."
                    ),
                ),
            )
        # Only NOW is absence reached, and it is refused rather than read as
        # third-country establishment. That inference is the defect this branch
        # closes: an export leaves the Union, so the exemption turns on where
        # the counterparty IS, and "no country recorded" is not a place. Read
        # as one it zero-rated a supply from a fact nobody had stated, which is
        # the under-declaration direction on the issued side.
        if not _export_establishment_is_answerable(counterparty_country):
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT,
                detail=tr(
                    "aggregation.iva_ledger.errors.missing_counterparty_establishment_on_export",
                    default=(
                        "An export is exempt because the operation leaves the Union, so it turns on where "
                        "the counterparty is ESTABLISHED. Record the counterparty's country; an absent or "
                        "unassigned code establishes nothing, and its IVA identification cannot answer this."
                    ),
                ),
            )
    return None


def validate_iva_ledger_counterparty_category(transaction: Transaction) -> IvaLedgerAggregationIssue | None:
    """Return the D5 counterparty/category gate :class:`IvaLedgerAggregationIssue` for a ledger transaction."""
    category = transaction.iva_category
    if category is None:
        return None
    return validate_intracom_export_counterparty(
        transaction_id=transaction.transaction_id,
        category=category,
        counterparty_country=transaction.counterparty_country,
        eu_member_state=transaction.counterparty_eu_member_state,
        identification_state=transaction.counterparty_identification_state,
    )


def business_proportionality_for(transaction: Transaction) -> Decimal | None:
    return business_proportion(transaction.business_classification, transaction.business_pct)


def has_converted_non_eur_amount(transaction: Transaction) -> bool:
    return transaction.raw.currency != DEFAULT_CURRENCY and transaction.value_in_eur is not None


def missing_tax_fact_reason(transaction: Transaction) -> IvaLedgerAggregationIssueReason | None:
    reasons = iva_ledger_missing_fact_reasons(transaction)
    return reasons[0] if reasons else None


#: The required IVA tax fact behind each missing-fact reason, in report order.
#:
#: Read as the single source of both the probe and the emission set, so
#: :data:`IVA_LEDGER_MISSING_FACT_REASONS` cannot fall out of step with what
#: :func:`iva_ledger_missing_fact_reasons` actually emits. A hand-listed
#: companion set would drift the moment a fourth required fact is added, and
#: the readiness layer downstream keys its operator-facing mapping on that set.
_MISSING_FACT_REASON_BY_FIELD: Final[Mapping[str, IvaLedgerAggregationIssueReason]] = {
    "taxable_base": IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE,
    "iva_amount": IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT,
    "iva_rate": IvaLedgerAggregationIssueReason.MISSING_IVA_RATE,
}

#: Every reason :func:`iva_ledger_missing_fact_reasons` can emit, derived.
IVA_LEDGER_MISSING_FACT_REASONS: Final[frozenset[IvaLedgerAggregationIssueReason]] = frozenset(
    _MISSING_FACT_REASON_BY_FIELD.values(),
)

#: Every reason :func:`validate_iva_ledger_counterparty_category` can emit.
#:
#: Declared rather than derived because the three branches read three different
#: counterparty facts and collapsing them into one table would erase the legal
#: distinction between identification and establishment the gate turns on. A
#: behavioural gate exercises the real screen across the category matrix and
#: asserts the observed emissions equal this set, so the declaration is pinned
#: to behaviour rather than trusted.
IVA_LEDGER_COUNTERPARTY_GATE_REASONS: Final[frozenset[IvaLedgerAggregationIssueReason]] = frozenset(
    {
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE,
        IvaLedgerAggregationIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION,
        IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION,
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT,
    },
)


def iva_ledger_missing_fact_reasons(transaction: Transaction) -> tuple[IvaLedgerAggregationIssueReason, ...]:
    """Return missing IVA fact reasons for a transaction without projecting it.

    Each element is an :class:`IvaLedgerAggregationIssueReason` describing
    one absent required tax fact.
    """
    return tuple(
        reason for field, reason in _MISSING_FACT_REASON_BY_FIELD.items() if getattr(transaction, field) is None
    )


def missing_tax_fact_detail(reason: IvaLedgerAggregationIssueReason) -> str:
    return {
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: "transaction has no taxable_base fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: "transaction has no iva_amount fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: "transaction has no iva_rate fact",
    }[reason]


def prorrata_reference_for(
    reference_id: str | None,
    *,
    transaction_id: str,
) -> ProrrataReference | IvaLedgerAggregationIssue | None:
    if reference_id is None:
        return None
    try:
        return validate_prorrata_reference(reference_id)
    except ProrrataInputError as exc:
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE,
            detail=str(exc),
        )


def iva_rate_kind_for(rate: Decimal, *, on_date: date) -> IvaRateKind | None:
    """Return the tier a declared rate belongs to, or ``None`` if it is not one.

    Delegates to :func:`rate_kinds_for_declared_rate`, the registry's own
    value-to-tier direction. This previously iterated the tiers and called the
    tier-to-value lookup once each, comparing percentages -- a simulation of the
    inverse that holds only while the mapping is one-to-one per date. Spain's
    2024 temporary food rates broke that: 2 % and 4 % were both correct
    super-reducido rates, and the simulation found neither for a 2 % row.

    When a rate matches more than one tier the FIRST registered match wins, and
    the ambiguity is real rather than a defect -- the tiers genuinely share that
    rate on that date, and no bundled AEAT surface carries the goods axis that
    would separate them. Callers that must report the rate itself carry it
    separately on the observation.
    """
    matched = rate_kinds_for_declared_rate(EUMemberState.ES, rate, on_date)
    return matched[0] if matched else None


# One local test-facing name. Seven siblings carried the same comment while no
# test referenced any of them, so the claim was true only of this one.
_iva_rate_kind_for = iva_rate_kind_for


__all__ = [
    "AnnualDeducibleTotalsByRegime",
    "IvaLedgerAggregation",
    "IvaLedgerAggregationIssue",
    "IvaLedgerAggregationIssueReason",
    "IvaLedgerCandidate",
    "IvaLedgerProrrataApportionment",
    "IvaLedgerSectorApportionment",
    "ProrrataLedgerReference",
    "aggregate_iva_ledger_candidate_bindings",
    "aggregate_iva_ledger_candidates",
    "aggregate_iva_ledger_observations",
    "aggregate_iva_ledger_observations_from_repositories",
    "compute_annual_deducible_totals_by_regime",
    "iva_ledger_missing_fact_reasons",
    "resolve_iva_ledger_binding_values",
    "validate_iva_ledger_counterparty_category",
    "validate_iva_ledger_observation",
    "validate_iva_ledger_observations",
]
