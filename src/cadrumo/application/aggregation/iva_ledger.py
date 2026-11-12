"""Repository-backed IVA observation projection from ledger catalogues.

This module classifies bucket-local
:class:`~domain.transactions.models.TransactionCatalogue` rows into typed
:class:`~domain.calculations.registry.ledger_iva_bindings.IvaLedgerObservation` records and
binding-ready totals. The source-mesh resolver in :mod:`~.modelo_bindings`
then applies the target
:class:`~domain.calculations.registry.schema.ModeloRevision`, resolves
``ledger_iva_aggregation`` bindings, and surfaces source diagnostics for ledger
rows that no declared binding consumes.

When the bucket's cross-period prorrata register resolves an active
``general`` provisional percentage for the filing year, the aggregation result
carries :class:`IvaLedgerProrrataApportionment`. The binding resolver applies
that percentage only to deducible IVA cuota bindings; bases and output IVA
cuotas stay unapportioned.

The repository-backed entry point requires the application-owned transaction
catalogue capability for the active bucket.

See Also:
    :mod:`~domain.prorrata_register`
        Per-ejercicio carry home for the provisional percentage consumed by
        the IVA ledger apportionment.
    :class:`~application.aggregation.modelo_bindings_iva.LedgerIvaAggregationSourceResolver`
        Source-mesh adapter that calls this projection and records prorrata
        apportionment provenance.
    :mod:`~adapters.persistence.profile.tests.test_iva_ledger_prorrata_apportionment`
        Regression coverage proving the active provisional percentage reduces
        deducible cuotas without reducing bases.
    :mod:`~.renta_ledger`, :mod:`~.renta_income_ledger`, :mod:`~.renta_gasto_ledger`
        Sibling Renta ledger projections.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_serializer, field_validator

from ...core.decimal.constants import HUNDRED
from ...core.i18n.translatable import Translatable as tr
from ...core.identity.transaction_ids import TransactionId
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.prorrata_register import (
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
)
from ...core.prose_elision import IssueDetail
from ...domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    InvestmentAssetAcquisitionLink,
    validate_investment_asset_reciprocity,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.iva_deduction_catalogue import (
    is_iva_deduction_kind,
)
from ...domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
)
from ...domain.calculations.registry.prorrata_register_catalogue import (
    general_prorrata_register_regime,
    regime_apportions_deduction,
)
from ...domain.iva.prorrata import (
    ProrrataReference,
)
from ...domain.iva.schema import (
    InvoiceKind,
    is_iva_cash_accounting_none,
)
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.prorrata_register.register import ProrrataRegister
from ...domain.transactions.date_partition import OutOfWindowTransactionSummary
from ...domain.transactions.dates import transaction_filing_date, transaction_operation_date
from ...domain.transactions.enums import (
    BUSINESS_BEARING_STATES,
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..invoices.catalogue_reads_ports import BucketBoundCatalogueReader, InvoiceCatalogueReader
from ..prorrata_register.service import require_prorrata_register_coordinates_current
from . import shared_issue_reasons
from .errors import AggregationValidationError
from .invoice_iva_source import (
    InvoiceIvaFinding,
    period_invoice_iva_side,
    refuse_contradicting_linked_movements,
)
from .invoice_kind import invoice_kind_for_direction


class IvaLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce IVA observations.

    The first five values are shared with
    :class:`~application.aggregation.renta_ledger_models.RentaLedgerAggregationIssueReason`
    through :mod:`~application.aggregation.shared_issue_reasons` so cross-ledger reporting can
    group upstream filter rejections under one key. The remaining values
    are IVA-specific.
    """

    UNSUPPORTED_DIRECTION = shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    PERSONAL_TRANSACTION = shared_issue_reasons.PERSONAL_TRANSACTION
    OUTSIDE_PERIOD = shared_issue_reasons.OUTSIDE_PERIOD
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
    # The declared cuota is not base x the declared tipo within one cent, the
    # same tolerance the invoice path applies to a line. The rate was already
    # proven in force on the operation date, so the amount is what disagrees;
    # routing the row would file a cuota its own base and tipo contradict.
    CUOTA_DISAGREES_WITH_RATE = "cuota_disagrees_with_rate"
    # The recargo de equivalencia a charged row records is more than a cent
    # from its base at the recargo rate LIVA art. 161 pairs with the row's IVA
    # rate on its date. The law fixes that figure, so the remedy is correcting
    # the row or a factura rectificativa; the recorded figure never reaches the
    # recargo casilla.
    RECARGO_DEPARTS_FROM_PUBLISHED_RATE = "recargo_departs_from_published_rate"
    # A charged row records a recargo on an IVA rate and date the registry
    # publishes no recargo rate for. Unresolved rather than refused: the gap is
    # the registry's, and a rate is never guessed for it.
    RECARGO_RATE_UNMODELLED = "recargo_rate_unmodelled"
    # A charged row's recargo is the labores del tabaco rate (art. 161 4.o),
    # declared on its own 303 rung that no casilla is bound for here. Never
    # refused as a mismatch and never folded into the general recargo casilla.
    RECARGO_TOBACCO_RUNG_UNSUPPORTED = "recargo_tobacco_rung_unsupported"
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
    # The sibling of the reason above, one step further along. There the
    # deduction taxonomy is ABSENT; here it is PRESENT and the combination it
    # names has no legal authority -- an exempt purchase classified as an
    # ordinary domestic deduction, an investment kind with no reciprocal asset
    # identity, a kind whose required evidence authority is not the one
    # attached, or deduction authority carried on an output row.
    #
    # Both are operator data errors, and the distinction matters because the
    # remedies differ: an absent classification is supplied, an inadmissible one
    # is CORRECTED. Collapsing them would tell a taxpayer to classify a row they
    # already classified.
    #
    # Separate from the screens above it because admissibility is not derivable
    # from any single declared field: it is the closed pairing table in fact
    # 0085, resolved by the domain validator. Until this reason existed that
    # validator ran only inside the observation's own model validator, AFTER
    # every typed gate, so the operator's data error surfaced as an internal
    # payload-boundary defect with no row, no field and no remedy named.
    INADMISSIBLE_DEDUCTION_CLASSIFICATION = "inadmissible_deduction_classification"
    # The row carries a registry value -- a cash-accounting treatment, an
    # exemption article, an art. 106 input classification, an Art. 104.tres
    # exclusion, a counterparty identification state -- that the operation's
    # pinned authority does not declare, or does not admit on this row. Write
    # admission accepted it under the authority then current; this calculation
    # pins its own. Each value used to be read as its nearest ordinary meaning
    # (criterio de caja, an exempt acquirer, a mixed-use input, a volume
    # exclusion), so a value no authority supports reached the return.
    #
    # Distinct from every absence reason: nothing is missing, and the remedy is
    # to CORRECT a stored value rather than to supply one.
    UNACCEPTED_REGISTRY_VALUE = "unaccepted_registry_value"
    # The row's criterio-de-caja facts contradict each other: a non-ordinary
    # treatment with no operation date, settlement evidence on an ordinary row,
    # evidence exceeding the operation's base or cuota, or a payment after the
    # statutory fallback date. The settlement split reads exactly these facts,
    # so a contradiction would split the cuota across the wrong periods.
    CASH_ACCOUNTING_EVIDENCE_INCOHERENT = "cash_accounting_evidence_incoherent"
    # A MIXED received row whose spending category grants no IVA deduction for
    # simultaneous business and private use (LIVA art. 95.Uno and Dos.2.º), or
    # whose good is below the bien de inversión value (art. 108.Dos.5.º).
    # Excluded like a personal row rather than observed with a zero cuota: a
    # cuota the law never lets be deducted has no base in the deductible boxes.
    NON_DEDUCTIBLE_MIXED_USE = "non_deductible_mixed_use"
    # A MIXED received row whose category states no IVA treatment for the pinned
    # authority, usually because the row has no category at all. Simultaneous use
    # deducts nothing (LIVA art. 95.Uno and Dos.2.º) unless the good is a bien de
    # inversión (art. 95.Tres) or follows one (art. 95.Cuatro), and only the
    # category answers that. Neither the row's share nor nothing is therefore
    # known: unlike NON_DEDUCTIBLE_MIXED_USE, the remedy is to supply a fact, and
    # the calculation stays unresolved until it is supplied.
    UNDETERMINED_MIXED_USE_TREATMENT = "undetermined_mixed_use_treatment"


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.


class IvaLedgerRowDateSource(StrEnum):
    """Which of a ledger row's dates stood as its LIVA art. 75 devengo date.

    A row with no recorded ``operation_date`` is dated by its bank movement:
    the value date, else the booked date. A refusal keyed on that date reads
    as a fault in the rate or the year when the fact actually missing may be
    the operation date, so the issue names which date was used.
    """

    OPERATION_DATE = "operation_date"
    VALUE_DATE = "value_date"
    BOOKED_DATE = "booked_date"


class IvaLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while projecting IVA ledger observations.

    ``operation_date_source`` is stated only by the refusals that judge the row
    on its devengo date, and ``None`` elsewhere.
    """

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: str = Field(min_length=1, max_length=128)
    reason: IvaLedgerAggregationIssueReason
    detail: IssueDetail
    operation_date_source: IvaLedgerRowDateSource | None = None


class ProrrataLedgerReference(BaseModel):
    """Bucket-local ledger row pointer to a legal IVA prorrata reference."""

    model_config = STRICT_FROZEN_CONFIG

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
        :class:`~domain.prorrata_register.register.SectorDefinition`
            Operator-declared sector this apportionment resolves for.
    """

    model_config = STRICT_FROZEN_CONFIG

    sector_id: str = Field(min_length=1, max_length=64)
    percentage: Decimal = Field(..., ge=Decimal("0"), le=HUNDRED)
    regime: ProrrataRegisterRegime = Field(default_factory=general_prorrata_register_regime)


class IvaLedgerSettlementSectorPercentage(BaseModel):
    """One differentiated sector's settled definitive percentage (LIVA arts. 101.Uno, 105.Cuatro)."""

    model_config = STRICT_FROZEN_CONFIG

    sector_id: str = Field(min_length=1, max_length=64)
    percentage: Decimal = Field(..., ge=Decimal("0"), le=HUNDRED)


class IvaLedgerSettlementApportionment(BaseModel):
    """Definitive prorrata percentage for the year's annual settlement liquidation.

    LIVA art. 105.Cuatro has the last liquidation of the year -- the fourth
    quarter, or month 12 for a monthly filer -- deduct its own cuotas at the
    year's definitive percentage, while the regularisation box corrects only
    the earlier liquidations. Observations dated inside ``period`` are
    apportioned at ``percentage``; every other observation keeps the
    provisional percentage of the enclosing apportionment, so a Modelo 390
    spanning the whole year reproduces each periodic liquidation.

    Under differentiated sectors (LIVA art. 101.Uno) each declared sector
    settles its own definitive percentage, carried in
    ``sector_percentages``; ``percentage`` is then the definitive percentage
    of the cross-sector common-use inputs. Under prorrata especial
    ``percentage`` reaches only the common-use slice (art. 106.Uno regla 3.ª).
    """

    model_config = STRICT_FROZEN_CONFIG

    period: Period
    percentage: Decimal = Field(..., ge=Decimal("0"), le=HUNDRED)
    sector_percentages: tuple[IvaLedgerSettlementSectorPercentage, ...] = ()

    @field_validator("sector_percentages")
    @classmethod
    def _sector_percentages_are_unique(
        cls, value: tuple[IvaLedgerSettlementSectorPercentage, ...]
    ) -> tuple[IvaLedgerSettlementSectorPercentage, ...]:
        if len({item.sector_id for item in value}) != len(value):
            raise ValueError("settlement sector percentages must name each sector once")
        return value


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
    use is represented only by the registry-declared mixed-use token;
    a bare missing sector never defaults to common. Empty
    ``sector_apportionments`` is the whole-entity register.

    See Also:
        :class:`~core.prorrata_register.ProrrataProvisionalProvenance`
            Regulated source of the provisional percentage carried on this
            apportionment.
        :func:`resolve_iva_ledger_binding_values`
            Applies the percentage after registry selector resolution.
    """

    model_config = STRICT_FROZEN_CONFIG

    percentage: Decimal = Field(..., ge=Decimal("0"), le=HUNDRED)
    provenance: ProrrataProvisionalProvenance
    regime: ProrrataRegisterRegime = Field(default_factory=general_prorrata_register_regime)
    source_observation_ref: str | None = Field(default=None, min_length=1)
    authorisation_reference: str | None = Field(default=None, min_length=1)
    sector_apportionments: tuple[IvaLedgerSectorApportionment, ...] = ()
    settlement: IvaLedgerSettlementApportionment | None = None
    """Definitive percentages for the settlement liquidation, once they are known.

    A differentiated-sector apportionment carries one only when every declared
    sector has settled its definitive percentage; otherwise the settlement
    liquidation keeps the provisional percentages while the regularisation box
    stays unresolved.
    """


class IvaDifferentiatedDeductionContribution(BaseModel):
    """Immutable canonical apportioned contribution for one sector/source family."""

    model_config = STRICT_FROZEN_CONFIG

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
    total (art. 106 per-input classification) exists only when every deducible
    soportado row of the ejercicio carries a declared ``input_classification``,
    whatever the register regime, and is ``None`` otherwise.
    ``unclassified_deducible_count`` records how many deducible soportado
    observations are still unclassified, so the caller can tell the filer to
    classify first.

    See Also:
        :func:`compute_annual_deducible_totals_by_regime`
            Builds this record from one annual observation aggregation and two
            apportionment passes.
    """

    model_config = STRICT_FROZEN_CONFIG

    deduction_under_general: Decimal = Field(..., ge=Decimal("0"))
    deduction_under_especial: Decimal | None = Field(..., ge=Decimal("0"))
    unclassified_deducible_count: int = Field(..., ge=0)
    regime: ProrrataRegisterRegime


class IvaLedgerAggregation(BaseModel):
    """IVA observations produced from one bucket-local transaction catalogue.

    ``out_of_window_summary`` is only populated by repository-backed date
    partitions. Full-catalogue aggregation continues to emit row-level issues
    because every transaction is already loaded for classification.
    """

    model_config = STRICT_FROZEN_CONFIG

    period: Period
    observations: Sequence[IvaLedgerObservation] = Field(default_factory=tuple)
    prorrata_references: Sequence[ProrrataLedgerReference] = Field(default_factory=tuple)
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None
    issues: Sequence[IvaLedgerAggregationIssue] = Field(default_factory=tuple)
    unclassified_output_ledger_ids: tuple[str, ...] = ()
    out_of_window_summary: OutOfWindowTransactionSummary | None = None
    # Ledger ids of operator-tagged LIVA art. 104.Tres judgment exclusions
    # (foreign PE, non-habitual inmobiliario/financiero). The prorrata annual
    # volume rollup skips these on the ledger side so the reconciliation does
    # not count operations the law removes from both terms of the ratio. The
    # operations' own IVA cuota observations are unaffected and still aggregate.
    art_104_tres_excluded_ledger_ids: tuple[str, ...] = ()
    # Contributing rows no operation date was recorded on, so their bank movement
    # date placed them.
    movement_dated_ledger_ids: tuple[str, ...] = ()
    # Contributing rows whose recorded operation date is later than the money:
    # the shape of a pago anticipado, which art. 75.Dos dates at the collection.
    operation_after_movement_ledger_ids: tuple[str, ...] = ()
    # Invoices whose lines are among ``observations``: the invoice is the IVA
    # source (LIVA art. 75, art. 97), and the movements paying it contribute none.
    invoice_ids: tuple[str, ...] = ()
    # What blocks filing grade on the invoice side of the period.
    invoice_findings: tuple[InvoiceIvaFinding, ...] = ()
    # The invoice screen's advisories, for the resolver's diagnostics. Read it
    # through ``invoice_screen_of``; it is process-local and never serialized.
    invoice_screen: object | None = Field(default=None, exclude=True, repr=False)

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
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    invoice_reader: InvoiceCatalogueReader,
    investment_asset_register: BienesInversionIvaRegister | None = None,
    investment_asset_profile_id: str | None = None,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregation:
    """Load the bucket's invoices and transactions and project IVA observations.

    The invoice is the IVA source: every invoice accruing in ``period``
    contributes its lines, and a movement an invoice names is its payment
    evidence, contributing no observation of its own. Movements no invoice
    names keep their own IVA facts.

    Returns an :class:`IvaLedgerAggregation`.

    Args:
        bucket_id: The profile bucket every supplied repository must be scoped
            to; a divergent repository bucket is refused, not silently used.
        period: The filing period whose transactions are projected.
        prorrata_register_repository: The canonical register repository read for
            the active general-prorrata provisional percentage. Required, so no
            caller can fall back to an implicitly constructed register whose
            bucket nobody checked.
        transaction_repository: Required bucket-bound catalogue capability.
        invoice_reader: The same bucket's invoice catalogue. Required, so no
            caller can calculate IVA from movements alone while the person's
            Libro de facturas holds the operations.
        investment_asset_register: Bienes-inversion authority, mandatory
            whenever ``transaction_repository`` is injected.
        investment_asset_profile_id: Profile owning that register.
        operation: Existing generation-pinned authority operation owned by the
            enclosing workflow.
    """
    if prorrata_register_repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.bucket_mismatch"),
            context={
                "bucket_id": bucket_id,
                "repository_bucket_id": prorrata_register_repository.bucket_id,
            },
        )
    repository = transaction_repository
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    if isinstance(invoice_reader, BucketBoundCatalogueReader) and invoice_reader.bucket_id not in (None, bucket_id):
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": invoice_reader.bucket_id},
        )
    prorrata_apportionment = _active_prorrata_apportionment(
        bucket_id=bucket_id,
        ejercicio=period.filing_year,
        prorrata_register_repository=prorrata_register_repository,
        operation=operation,
    )
    # Only the in-window subset is decrypted and classified. Out-of-window
    # catalogue rows come from the plaintext date index and are reported
    # uniformly as ``OUTSIDE_PERIOD`` because decrypted-field gates cannot run
    # for those rows. A period with no calendar span falls back to the
    # unfiltered load.
    if not period.has_date_span():
        window = repository.load()
        out_of_window_summary = None
    else:
        date_partition = repository.partition_by_date_range(period.start_date, period.end_date)
        window = date_partition.in_window
        out_of_window_summary = (
            date_partition.out_of_window_summary
            or OutOfWindowTransactionSummary.from_index_entries(date_partition.out_of_window)
        )
    invoice_side = period_invoice_iva_side(
        tuple(invoice_reader.load()),
        bucket_id=bucket_id,
        period=period,
        window=window,
        repository=repository,
        operation=operation,
    )
    refuse_contradicting_linked_movements(invoice_side.contradicted)
    result = aggregate_iva_ledger_observations(
        invoice_side.unpaid_window,
        period=period,
        prorrata_apportionment=prorrata_apportionment,
        ledger_profile_id=bucket_id,
        investment_asset_register=investment_asset_register,
        investment_asset_profile_id=investment_asset_profile_id,
        investment_acquisition_rows=(
            _register_acquisition_rows_outside_window(
                window,
                filing_year=period.filing_year,
                investment_asset_register=investment_asset_register,
                repository=repository,
            )
            if period.has_date_span()
            else None
        ),
        operation=operation,
    )
    result = result.model_copy(
        update={
            "observations": (*result.observations, *invoice_side.source.observations),
            "out_of_window_summary": out_of_window_summary,
            "invoice_ids": invoice_side.source.screen.invoice_ids,
            "invoice_findings": invoice_side.source.findings,
            "invoice_screen": invoice_side.source.screen,
        },
    )
    _validate_rectifications_consumed_once(result.observations, operation=operation)
    return result


def _register_acquisition_rows_outside_window(
    catalogue: TransactionCatalogue,
    *,
    filing_year: int,
    investment_asset_register: BienesInversionIvaRegister | None,
    repository: TransactionCatalogueRepositoryProtocol,
) -> TransactionCatalogue:
    """Read the filing year's register-named acquisition rows a period window left out.

    Only the rows a register record acquired in ``filing_year`` names are read,
    by id, so a quarter decrypts its own window plus at most one row per capital
    good the year acquired elsewhere. A named id the ledger does not hold is
    simply absent from the result, and the reciprocity contract refuses it.
    """
    if investment_asset_register is None:
        return TransactionCatalogue.from_transactions(())
    outside_ids = {
        record.acquisition_ledger_id
        for record in investment_asset_register.records
        if record.acquisition_year == filing_year and catalogue.get(record.acquisition_ledger_id) is None
    }
    if not outside_ids:
        return TransactionCatalogue.from_transactions(())
    return repository.load_by_ids(outside_ids)


def _validate_investment_asset_authority(
    observations: Sequence[IvaLedgerObservation],
    *,
    period: Period,
    ledger_profile_id: str | None,
    investment_asset_register: BienesInversionIvaRegister | None,
    investment_asset_profile_id: str | None,
    acquisition_rows: Sequence[TransactionCatalogue],
    operation: PinnedAuthorityOperation,
) -> None:
    """Require explicit owner inputs before an investment fact can aggregate.

    The reciprocity contract is one of the filing YEAR: every record acquired in
    it pairs with exactly one acquisition row of that year. A period observes
    only its own rows, so the acquisitions the register places in the year's
    other periods join the evidence from ``acquisition_rows``; without them a
    declared bien de inversión would refuse every period but the one holding it.
    """
    has_investment_observation = any(
        observation.deduction_fact_kind is not None
        and is_iva_deduction_kind(
            observation.deduction_fact_kind,
            "kind.investment_acquisition",
            authority=operation,
        )
        for observation in observations
    )
    if not has_investment_observation and investment_asset_register is None:
        return
    if ledger_profile_id is None or investment_asset_register is None or investment_asset_profile_id is None:
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.investment_observations_missing_bienes_inversion_authority"),
            context={
                "filing_year": period.filing_year,
                "has_ledger_profile_id": ledger_profile_id is not None,
                "has_investment_asset_register": investment_asset_register is not None,
                "has_investment_asset_profile_id": investment_asset_profile_id is not None,
            },
        )
    validate_investment_asset_reciprocity(
        observations=(
            *observations,
            *_acquisitions_outside_period(
                observations,
                period=period,
                investment_asset_register=investment_asset_register,
                acquisition_rows=acquisition_rows,
            ),
        ),
        register=investment_asset_register,
        ledger_profile_id=ledger_profile_id,
        asset_profile_id=investment_asset_profile_id,
        filing_year=period.filing_year,
    )


def _acquisitions_outside_period(
    observations: Sequence[IvaLedgerObservation],
    *,
    period: Period,
    investment_asset_register: BienesInversionIvaRegister,
    acquisition_rows: Sequence[TransactionCatalogue],
) -> tuple[InvestmentAssetAcquisitionLink, ...]:
    """Return the acquisition links of the filing year's records whose row lies in another period.

    Only a record this period did not observe is looked up, and only a row whose
    devengo date falls outside ``period`` is linked: a row dated inside it that
    produced no observation here stays unproven, because this period's own
    classification of that row is the authority for it. A record naming a row
    no catalogue holds, or one the ledger has retired, contributes no link and
    so remains a refusal in every period of its acquisition year.
    """
    observed_ledger_ids = {observation.ledger_id for observation in observations}
    links: list[InvestmentAssetAcquisitionLink] = []
    for record in investment_asset_register.records:
        if record.acquisition_year != period.filing_year or record.acquisition_ledger_id in observed_ledger_ids:
            continue
        transaction = next(
            (row for catalogue in acquisition_rows if (row := catalogue.get(record.acquisition_ledger_id)) is not None),
            None,
        )
        if transaction is None:
            continue
        link = _investment_acquisition_link(transaction)
        if link is not None and not period.contains(link.transaction_date):
            links.append(link)
    return tuple(links)


def _investment_acquisition_link(transaction: Transaction) -> InvestmentAssetAcquisitionLink | None:
    """Project one live ledger row onto the reciprocal edge it claims, if it claims one."""
    if (
        transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE
        or transaction.direction is TransactionDirection.INTERNAL_TRANSFER
        or transaction.business_classification not in BUSINESS_BEARING_STATES
        or transaction.deduction_fact_kind is None
        or transaction.investment_asset_id is None
    ):
        return None
    return InvestmentAssetAcquisitionLink(
        ledger_id=transaction.transaction_id,
        transaction_date=transaction.operation_date or transaction_filing_date(transaction),
        deduction_fact_kind=transaction.deduction_fact_kind,
        investment_asset_id=transaction.investment_asset_id,
        prorrata_sector_id=transaction.prorrata_sector_id,
    )


def _validate_rectifications_consumed_once(
    observations: Sequence[IvaLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Ensure each rectified ledger identity is consumed at most once."""
    rectified_ids = [
        observation.rectifies_ledger_id
        for observation in observations
        if observation.deduction_fact_kind is not None
        and is_iva_deduction_kind(
            observation.deduction_fact_kind,
            "kind.rectification",
            authority=operation,
        )
    ]
    if len(rectified_ids) != len(set(rectified_ids)):
        raise AggregationValidationError(
            tr("aggregation.iva_ledger.errors.rectification_consumed_more_than_once"),
            context={"rectified_ledger_id_count": len(rectified_ids)},
        )


def _is_included_transaction(transaction: Transaction) -> bool:
    """Include only active rows not deliberately excluded by review."""
    return (
        transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
        and transaction.business_classification is not BusinessClassification.REVIEWED_EXCLUDED
    )


@dataclass(slots=True)
class _IvaLedgerCollection:
    """What the per-row pass accumulates before the aggregation is assembled."""

    observations: list[IvaLedgerObservation] = field(default_factory=list[IvaLedgerObservation])
    prorrata_references: list[ProrrataLedgerReference] = field(default_factory=list[ProrrataLedgerReference])
    issues: list[IvaLedgerAggregationIssue] = field(default_factory=list[IvaLedgerAggregationIssue])
    art_104_tres_excluded_ledger_ids: list[str] = field(default_factory=list[str])
    unclassified_output_ledger_ids: list[str] = field(default_factory=list[str])
    movement_dated_ledger_ids: list[str] = field(default_factory=list[str])
    operation_after_movement_ledger_ids: list[str] = field(default_factory=list[str])


def _gate_leaves_output_unclassified(transaction: Transaction, gate_issue: IvaLedgerAggregationIssue) -> bool:
    """Whether a gate refusal drops an issued row whose output IVA is then unclassified."""
    return invoice_kind_for_direction(transaction.direction) is InvoiceKind.ISSUED and gate_issue.reason not in {
        IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION,
        IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
    }


def _operation_after_movement(transaction: Transaction, *, operation: PinnedAuthorityOperation) -> bool:
    """Whether a dated operation follows the movement of a row not under IVA cash accounting."""
    operation_date = transaction.operation_date
    return (
        operation_date is not None
        and operation_date > transaction_filing_date(transaction)
        and is_iva_cash_accounting_none(
            transaction.cash_accounting_treatment, transaction_operation_date(transaction), authority=operation
        )
    )


def _collect_iva_transaction(
    transaction: Transaction,
    collected: _IvaLedgerCollection,
    *,
    resolved_period: Period,
    operation: PinnedAuthorityOperation,
) -> None:
    """Classify one included ledger row and add what it yields to ``collected``."""
    from .iva_transaction import classify_iva_transaction

    outcome = classify_iva_transaction(transaction, resolved_period=resolved_period, operation=operation)
    if outcome.gate_issue is not None:
        collected.issues.append(outcome.gate_issue)
        if _gate_leaves_output_unclassified(transaction, outcome.gate_issue):
            collected.unclassified_output_ledger_ids.append(transaction.transaction_id)
        return
    if outcome.prorrata_issue is not None:
        collected.issues.append(outcome.prorrata_issue)
    if outcome.prorrata_reference is not None:
        collected.prorrata_references.append(outcome.prorrata_reference)
    collected.observations.extend(outcome.observations)
    if outcome.observations:
        if transaction.operation_date is None:
            collected.movement_dated_ledger_ids.append(transaction.transaction_id)
        elif _operation_after_movement(transaction, operation=operation):
            collected.operation_after_movement_ledger_ids.append(transaction.transaction_id)
    # LIVA art. 104.Tres: an operator-declared judgment exclusion removes the
    # operation from BOTH terms of the prorrata ratio. The IVA cuota
    # observations above still aggregate (the operation is a real taxable
    # supply); only the prorrata annual volume rollup skips it, keyed by the
    # ledger id recorded here.
    if transaction.art_104_tres_exclusion is not None:
        collected.art_104_tres_excluded_ledger_ids.append(transaction.transaction_id)


def aggregate_iva_ledger_observations(
    transactions: TransactionCatalogue,
    *,
    period: Period,
    ledger_profile_id: str,
    investment_asset_register: BienesInversionIvaRegister | None = None,
    investment_asset_profile_id: str | None = None,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None,
    investment_acquisition_rows: TransactionCatalogue | None = None,
    operation: PinnedAuthorityOperation,
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
        investment_acquisition_rows: Acquisition rows the register names that
            ``transactions`` does not hold, as a period-scoped catalogue leaves
            out the rows of the year's other periods. They are never
            aggregated; they only prove, against the register, an acquisition
            dated outside ``period``. Omitted, ``transactions`` is taken to hold
            every row the register names.
        operation: Existing generation-pinned authority operation owned by the
            enclosing workflow.
    """
    resolved_period = period
    collected = _IvaLedgerCollection()
    for transaction in transactions.values():
        if not _is_included_transaction(transaction):
            continue
        _collect_iva_transaction(transaction, collected, resolved_period=resolved_period, operation=operation)
    result = IvaLedgerAggregation(
        period=resolved_period,
        observations=tuple(collected.observations),
        prorrata_references=tuple(collected.prorrata_references),
        prorrata_apportionment=prorrata_apportionment,
        issues=tuple(collected.issues),
        art_104_tres_excluded_ledger_ids=tuple(collected.art_104_tres_excluded_ledger_ids),
        unclassified_output_ledger_ids=tuple(collected.unclassified_output_ledger_ids),
        movement_dated_ledger_ids=tuple(collected.movement_dated_ledger_ids),
        operation_after_movement_ledger_ids=tuple(collected.operation_after_movement_ledger_ids),
    )
    _validate_investment_asset_authority(
        result.observations,
        period=period,
        ledger_profile_id=ledger_profile_id,
        investment_asset_register=investment_asset_register,
        investment_asset_profile_id=investment_asset_profile_id,
        acquisition_rows=(transactions,)
        if investment_acquisition_rows is None
        else (transactions, investment_acquisition_rows),
        operation=operation,
    )
    _validate_rectifications_consumed_once(result.observations, operation=operation)
    return result


def _active_prorrata_apportionment(
    *,
    bucket_id: str,
    ejercicio: int,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    operation: PinnedAuthorityOperation,
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
    register = require_prorrata_register_coordinates_current(
        prorrata_register_repository.load(),
        operation=operation,
    )
    base = sector_scoped_apportionment(register, ejercicio, sector_id=None, operation=operation)
    if base is None:
        return None
    if not register.is_sectorized:
        return base
    sector_apportionments_list: list[IvaLedgerSectorApportionment] = []
    for sector_id in register.sector_ids():
        sector = sector_scoped_apportionment(register, ejercicio, sector_id=sector_id, operation=operation)
        if sector is None:
            entry = register.entry_for(ejercicio, sector_id=sector_id)
            facts = {"sector_id": sector_id, "ejercicio": ejercicio}
            if entry is None:
                raise AggregationValidationError(
                    tr("aggregation.iva_ledger.errors.differentiated_sector_without_filing_year_entry"),
                    context=facts,
                )
            if entry.interrupted or not regime_apportions_deduction(entry.regime, authority=operation):
                raise AggregationValidationError(
                    tr("aggregation.iva_ledger.errors.differentiated_sector_inactive_for_filing_year"),
                    context=facts,
                )
            raise AggregationValidationError(
                tr("aggregation.iva_ledger.errors.differentiated_sector_without_provisional_percentage"),
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


def sector_scoped_apportionment(
    register: ProrrataRegister,
    ejercicio: int,
    *,
    sector_id: str | None,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerProrrataApportionment | None:
    """Resolve the apportionment for one ``(ejercicio, sector_id)`` register key.

    Returns ``None`` when the key has no apportioning entry (``NINGUNA`` /
    interrupted / absent) or no provisional percentage is resolvable.
    """
    entry = register.entry_for(ejercicio, sector_id=sector_id)
    if entry is None or not regime_apportions_deduction(entry.regime, authority=operation):
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


def settled_sector_definitive_percentages(
    register: ProrrataRegister,
    ejercicio: int,
) -> tuple[IvaLedgerSettlementSectorPercentage, ...] | None:
    """Return every declared sector's settled definitive percentage for the ejercicio.

    LIVA art. 101.Uno has each differentiated sector apply its own deduction
    regime, so its settlement liquidation deducts at the sector's own
    definitive percentage (art. 105.Cuatro), written on its
    ``(ejercicio, sector_id)`` register entry when the sector is settled. A
    whole-entity register returns an empty tuple; a sectorized register with
    any sector not yet settled returns ``None`` so no sector is settled while
    another keeps its provisional percentage.
    """
    percentages: list[IvaLedgerSettlementSectorPercentage] = []
    for sector_id in register.sector_ids():
        entry = register.entry_for(ejercicio, sector_id=sector_id)
        if entry is None or entry.definitive_percentage is None:
            return None
        percentages.append(
            IvaLedgerSettlementSectorPercentage(sector_id=sector_id, percentage=entry.definitive_percentage)
        )
    return tuple(percentages)


__all__ = [
    "AnnualDeducibleTotalsByRegime",
    "IvaLedgerAggregation",
    "IvaLedgerAggregationIssue",
    "IvaLedgerAggregationIssueReason",
    "IvaLedgerProrrataApportionment",
    "IvaLedgerRowDateSource",
    "IvaLedgerSectorApportionment",
    "IvaLedgerSettlementApportionment",
    "IvaLedgerSettlementSectorPercentage",
    "ProrrataLedgerReference",
    "aggregate_iva_ledger_observations",
    "aggregate_iva_ledger_observations_from_repositories",
    "settled_sector_definitive_percentages",
]
