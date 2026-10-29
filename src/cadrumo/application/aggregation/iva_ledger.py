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
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_serializer, field_validator

from ...core.decimal.constants import HUNDRED
from ...core.i18n.translatable import Translatable as tr
from ...core.identity.transaction_ids import TransactionId
from ...core.iva_deduction_fact import IvaDeductionFactKind
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
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
)
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.prorrata_register.register import ProrrataRegister
from ...domain.transactions.date_partition import OutOfWindowTransactionSummary
from ...domain.transactions.dates import transaction_filing_date
from ...domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..prorrata_register.service import require_prorrata_register_coordinates_current
from . import _shared_issue_reasons
from .errors import AggregationValidationError
from .invoice_kind import invoice_kind_for_direction


class IvaLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce IVA observations.

    The first five values are shared with
    :class:`~application.aggregation.renta_ledger_models.RentaLedgerAggregationIssueReason`
    through :mod:`~application.aggregation._shared_issue_reasons` so cross-ledger reporting can
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


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.


class IvaLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while projecting IVA ledger observations."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    reason: IvaLedgerAggregationIssueReason
    detail: IssueDetail


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
        :class:`~domain.prorrata_register.register.SectorDefinition`
            Operator-declared sector this apportionment resolves for.
    """

    model_config = _STRICT_FROZEN

    sector_id: str = Field(min_length=1, max_length=64)
    percentage: Decimal = Field(..., ge=Decimal("0"), le=HUNDRED)
    regime: ProrrataRegisterRegime = Field(default_factory=general_prorrata_register_regime)


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

    model_config = _STRICT_FROZEN

    percentage: Decimal = Field(..., ge=Decimal("0"), le=HUNDRED)
    provenance: ProrrataProvisionalProvenance
    regime: ProrrataRegisterRegime = Field(default_factory=general_prorrata_register_regime)
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
    unclassified_output_ledger_ids: tuple[str, ...] = ()
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
    investment_asset_register: BienesInversionIvaRegister | None = None,
    investment_asset_profile_id: str | None = None,
    operation: PinnedAuthorityOperation,
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
        transaction_repository: Required bucket-bound catalogue capability.
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
        result = aggregate_iva_ledger_observations(
            repository.load(),
            period=period,
            prorrata_apportionment=prorrata_apportionment,
            ledger_profile_id=bucket_id,
            investment_asset_register=investment_asset_register,
            investment_asset_profile_id=investment_asset_profile_id,
            operation=operation,
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
            investment_acquisition_rows=_register_acquisition_rows_outside_window(
                partition.in_window,
                filing_year=period.filing_year,
                investment_asset_register=investment_asset_register,
                repository=repository,
            ),
            operation=operation,
        )
        out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
            partition.out_of_window,
        )
        result = result.model_copy(
            update={"out_of_window_summary": out_of_window_summary},
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
        or transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED
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
    observations: list[IvaLedgerObservation] = []
    prorrata_references: list[ProrrataLedgerReference] = []
    issues: list[IvaLedgerAggregationIssue] = []
    art_104_tres_excluded_ledger_ids: list[str] = []
    unclassified_output_ledger_ids: list[str] = []
    from ._iva_transaction import classify_iva_transaction

    for transaction in transactions.values():
        if not _is_included_transaction(transaction):
            continue
        outcome = classify_iva_transaction(transaction, resolved_period=resolved_period, operation=operation)
        if outcome.gate_issue is not None:
            issues.append(outcome.gate_issue)
            if invoice_kind_for_direction(
                transaction.direction
            ) is InvoiceKind.ISSUED and outcome.gate_issue.reason not in {
                IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION,
                IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            }:
                unclassified_output_ledger_ids.append(transaction.transaction_id)
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
        unclassified_output_ledger_ids=tuple(unclassified_output_ledger_ids),
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


__all__ = [
    "AnnualDeducibleTotalsByRegime",
    "IvaLedgerAggregation",
    "IvaLedgerAggregationIssue",
    "IvaLedgerAggregationIssueReason",
    "IvaLedgerProrrataApportionment",
    "IvaLedgerSectorApportionment",
    "ProrrataLedgerReference",
    "aggregate_iva_ledger_observations",
    "aggregate_iva_ledger_observations_from_repositories",
]
