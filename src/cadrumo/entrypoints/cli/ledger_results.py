"""Typed ``--json`` payload schemas for ledger CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass and is referenced as a deferred public schema
target by production-authored CommandSpec so the
JSON-contract test suite can enumerate every ledger-command surface this module
covers.  Emission wraps the validated result in
:class:`SchemaEnvelope` through
:func:`emit_envelope`.

Field sets match the production payload dicts constructed in ``_ledger.py``
at their emit sites. Optional fields cover multi-branch payload shapes
(e.g. ledger.classify has a bulk path and a single-transaction path;
ledger.import carries import facts while advisories use the shared notices channel).

All sequence fields use ``list`` rather than ``tuple`` because
``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays, and
the strict ``OutputSchema`` base does not coerce lists to tuples on
re-validation.

The application layer remains authoritative for
:class:`LedgerSourceImportResult`,
:class:`LedgerTransactionPayload`,
:class:`LedgerTransactionResultPayload`,
:class:`LedgerPreflightReport`.  Adjacent
surfaces that split out of this module keep their own transport schemas in
:mod:`ledger_interchange_results` (import / export),
:mod:`ledger_participation_results` (participation / tracking),
:mod:`ledger_rule_results`,
:mod:`ledger_llm_payloads`,
:mod:`ledger_catalogue_invoice_results`, and
:mod:`ledger_business_payloads` (the invoice / inventory / evidence
sub-app payload families).
"""

from __future__ import annotations

from pydantic import NonNegativeInt, field_validator, model_validator

from ...application.ledger.models import IsoDateText
from ...core.decimal.grammar import is_non_negative_canonical_decimal, try_parse_canonical_decimal
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, InvoiceId, WorkUnitId
from ...core.identity.transaction_ids import TransactionId
from ...core.json_contract import OutputRootSchema, OutputSchema
from ...core.parsing.codes import IsoCurrencyCode
from ...core.period import Period
from ...core.text_bounds import NonEmptyStr
from ...core.unit_proportion import is_unit_proportion
from .ledger_period_results import LedgerPeriodsPayload

# ---------------------------------------------------------------------------
# Shared nested models (not direct CommandSpec schema targets)
# ---------------------------------------------------------------------------


class LedgerEntryOptionPayload(OutputSchema):
    """One offered value, the key of its word where the backend words it, and the group it is filed under."""

    value: str
    label_key: str | None = None
    group: str | None = None


class LedgerEntryOptionFamilyPayload(OutputSchema):
    """One vocabulary."""

    family: str
    options: list[LedgerEntryOptionPayload]


class LedgerEntryClassificationPayload(OutputSchema):
    """What one classification takes: a business share, a category on a new rule, a category on a split part."""

    classification: str
    takes_business_share: bool
    takes_usage_ratio: bool
    carries_business_figures: bool
    keeps_category: bool
    rule_may_name_category: bool
    split_part_requires_category: bool


class LedgerEntryDecimalRulePayload(OutputSchema):
    """How many decimals one kind of figure takes, and whether zero is a value."""

    rule: str
    decimals: int
    zero: bool


class LedgerEntryPercentFieldPayload(OutputSchema):
    """The scale one field's rate is typed on."""

    field: str
    unit: str


class LedgerEntryTextLimitPayload(OutputSchema):
    """The most characters (or items) one kind of entry takes."""

    name: str
    max: int


class LedgerEntryLimitsPayload(OutputSchema):
    """Every limit a ledger entry form holds typed text to."""

    decimal_text_max: int
    two_way_decimal: str
    decimal_rules: list[LedgerEntryDecimalRulePayload]
    percent_decimals: int
    percent_points_max: str
    percent_fraction_max: str
    percent_bare_fraction_ceiling: str
    document_percent_fields: list[LedgerEntryPercentFieldPayload]
    rule_pattern_max: int
    payment_id_pattern: str
    text_limits: list[LedgerEntryTextLimitPayload]


class LedgerEntryOptionsResult(OutputSchema):
    """JSON envelope for ``aeat app ledger entry-options``.

    ``default_currency`` is the ledger's functional currency, one of the served ``currency`` codes.
    """

    default_currency: str
    families: list[LedgerEntryOptionFamilyPayload]
    classifications: list[LedgerEntryClassificationPayload]
    limits: LedgerEntryLimitsPayload
    periods: LedgerPeriodsPayload


class LedgerStagedRoutePayload(OutputSchema):
    """Where one staged cell goes, or why it can go nowhere."""

    field: str
    route: str | None
    refused: str | None


class LedgerStagedBlockerPayload(OutputSchema):
    """Why a movement's staged work cannot be sent as it stands, and what puts it right, in words."""

    kind: str
    fields: list[str]
    words: str
    fix_words: str
    words_language: str


class LedgerStagedNotePayload(OutputSchema):
    """What sending the work carries along without holding it back."""

    kind: str
    value: str | None
    fields: list[str]


class LedgerStagedRowPayload(OutputSchema):
    """The backend's answer for one movement as staged."""

    transaction_id: str
    found: bool
    classified: bool
    takes_expense_category: bool
    takes_share: bool
    category_askable: bool
    category_settable: bool
    category_on_income: bool
    takes_changes: bool
    takes_invoice: bool
    evidence_advised: bool
    lifecycle_actions: list[str]
    tax_set_skip: str | None
    transfer_locked_fields: list[str]
    classifying_fields: list[str]
    identity_fields: list[str]
    routes: list[LedgerStagedRoutePayload]
    blockers: list[LedgerStagedBlockerPayload]
    notes: list[LedgerStagedNotePayload]


class LedgerStagedDraftPayload(OutputSchema):
    """The backend's answer for one new movement."""

    key: str
    blockers: list[LedgerStagedBlockerPayload]


class LedgerStagedCategoryFitPayload(OutputSchema):
    """Which classifications may name a category."""

    category: str
    business: bool
    mixed: bool


class LedgerRuleTrialEnvelope(OutputSchema):
    """JSON envelope for ``aeat app ledger rule trial``."""

    outcome: str
    hits: list[str]
    pending: list[str]


class LedgerInvoiceDuplicateEnvelope(OutputSchema):
    """JSON envelope for ``aeat app ledger invoice duplicate``."""

    invoice_id: str | None
    basis: str | None


class LedgerInvoiceMatchPairPayload(OutputSchema):
    """One movement and one invoice that settle each other, and the evidence the pair stands on."""

    transaction_id: str
    invoice_id: str
    number: bool
    gap: int
    counterparty: bool


class LedgerInvoiceMatchSuggestionPayload(LedgerInvoiceMatchPairPayload):
    """A movement's best invoice, with what competes with it."""

    ambiguous: bool
    ties: list[LedgerInvoiceMatchPairPayload]
    others: list[LedgerInvoiceMatchPairPayload]


class LedgerInvoiceMatchInvoiceChoicePayload(OutputSchema):
    """An invoice a movement may be linked to by hand."""

    invoice_id: str
    settles: bool
    staged_for: str | None
    linked: int


class LedgerInvoiceMatchMovementChoicePayload(OutputSchema):
    """A movement an invoice may be linked to by hand."""

    transaction_id: str
    settles: bool


class LedgerInvoiceMatchMismatchPayload(OutputSchema):
    """One way a judged movement and invoice do not agree; the fields besides ``kind`` are the kind's own."""

    kind: str
    difference: str | None
    movement: str | None
    invoice: str | None
    count: int | None


class LedgerInvoiceMatchJudgementPayload(OutputSchema):
    """What stands against one named link."""

    transaction_id: str
    invoice_id: str
    found: bool
    mismatches: list[LedgerInvoiceMatchMismatchPayload]


class LedgerInvoiceMatchEnvelope(OutputSchema):
    """JSON envelope for ``aeat app ledger invoice match``."""

    suggestions: list[LedgerInvoiceMatchSuggestionPayload]
    window_days: int
    invoice_choices: list[LedgerInvoiceMatchInvoiceChoicePayload] | None
    movement_choices: list[LedgerInvoiceMatchMovementChoicePayload] | None
    judgements: list[LedgerInvoiceMatchJudgementPayload]


class LedgerSplitCheckProblemPayload(OutputSchema):
    """The first thing the split writer would refuse in the parts asked about."""

    kind: str
    index: int | None
    max: int | None
    difference: str | None
    over: bool | None


class LedgerSplitCheckChildPayload(OutputSchema):
    """One part as the split writer takes it."""

    amount: str
    description: str


class LedgerSplitCheckEnvelope(OutputSchema):
    """JSON envelope for ``aeat app ledger split-check``."""

    remainder: str | None
    problem: LedgerSplitCheckProblemPayload | None
    children: list[LedgerSplitCheckChildPayload]


class LedgerStagedCheckEnvelope(OutputSchema):
    """JSON envelope for ``aeat app ledger staged-check``."""

    input_digest: str
    rows: list[LedgerStagedRowPayload]
    drafts: list[LedgerStagedDraftPayload]
    categories: list[LedgerStagedCategoryFitPayload]
    share_refusal_words: str
    share_refusal_words_language: str


class LedgerInvoicePreviewRateSlotPayload(OutputSchema):
    """One IVA rate slot's standing on the draft's date; no fraction means no rate applies."""

    slot: str
    fraction: str | None
    in_force: bool
    coverage_gap: bool
    label_key: str


class LedgerInvoicePreviewFigurePayload(OutputSchema):
    """The backend's figure, the stated one with its verdict, and what add would store."""

    computed: str | None
    stated: str | None
    verdict: str | None
    submitted: str | None


class LedgerInvoicePreviewLinePayload(OutputSchema):
    """One draft line's figures, correlated to the request by its key."""

    key: str
    subtotal: LedgerInvoicePreviewFigurePayload
    iva_amount: LedgerInvoicePreviewFigurePayload


class LedgerInvoicePreviewTotalsPayload(OutputSchema):
    """The totals known so far; an unknown one is null, never zero."""

    base: str | None
    iva: str | None
    recargo: str | None
    total: str | None
    net_of_retention: str | None


class LedgerInvoicePreviewRetentionPayload(OutputSchema):
    """The stated retención and the amount its rate implies on the known base."""

    rate: str | None
    amount: str | None
    implied: str | None


class LedgerInvoicePreviewFactPayload(OutputSchema):
    """One value a finding compared."""

    key: str
    value: str | int | bool


class LedgerInvoicePreviewFindingPayload(OutputSchema):
    """One closed finding, located by field and, on a line, by the line's key."""

    code: str
    severity: str
    fields: list[str]
    line_key: str | None
    values: list[LedgerInvoicePreviewFactPayload]
    label_key: str


class LedgerInvoicePreviewResult(OutputSchema):
    """JSON envelope for ``aeat app ledger invoice preview``."""

    input_digest: str
    on_date: str
    on_date_source: str
    rate_slots: list[LedgerInvoicePreviewRateSlotPayload]
    lines: list[LedgerInvoicePreviewLinePayload]
    totals: LedgerInvoicePreviewTotalsPayload
    retention: LedgerInvoicePreviewRetentionPayload
    findings: list[LedgerInvoicePreviewFindingPayload]
    missing_fields: list[str]
    verdict: str
    refusal_code: str | None
    invoice_id: str | None
    rule_findings: list[LedgerInvoicePreviewFindingPayload]
    verdict_scope: str


class M210IncomeClassificationPayload(OutputSchema):
    """Operator-visible persisted M210 classification facts for one ledger row."""

    official_tipo_renta_code: str
    gross_income_amount: str
    applicable_rate: str
    payer_mode: str
    payer_id: str | None = None
    asset_or_right_id: str | None = None

    @field_validator("gross_income_amount")
    @classmethod
    @pydantic_validation_boundary
    def _is_a_non_negative_canonical_amount(cls, value: str) -> str:
        """Gross income is a magnitude, bounded ``ge=0`` on the record.

        The bound does not survive the projection to a string, so the wire
        re-asserts it rather than publishing a schema looser than the fact.
        """
        if not is_non_negative_canonical_decimal(value):
            raise ValueError(f"gross_income_amount must be a non-negative canonical decimal, got {value!r}")
        return value

    @field_validator("applicable_rate")
    @classmethod
    @pydantic_validation_boundary
    def _is_a_share_of_one(cls, value: str) -> str:
        """The M210 rate is a share of one, not merely a non-negative number.

        The record bounds it at ``ge=0, le=1``, which is
        :obj:`~core.unit_proportion.UnitProportion`. Asserting only
        non-negativity here would let a rate of ``5`` onto the wire -- five
        hundred per cent, which reads as a plausible percentage typed into a
        share field, so the upper bound is the half that catches the real
        mistake.
        """
        parsed = try_parse_canonical_decimal(value, signed=False)
        if parsed is None or not is_unit_proportion(parsed):
            raise ValueError(f"applicable_rate must be a decimal share between 0 and 1, got {value!r}")
        return value


class TransactionPayload(OutputSchema):
    """Nested CLI copy of :class:`LedgerTransactionPayload`.

    Field constraints mirror the canonical projection so a malformed
    identity, date, currency, or blank description that
    ``LedgerTransactionPayload`` refuses is refused at the CLI boundary too.
    """

    transaction_id: TransactionId
    date: IsoDateText
    booked_date: IsoDateText
    value_date: str | None = None
    operation_date: str | None = None
    accrual_date: str | None = None
    amount: NonEmptyStr
    currency: IsoCurrencyCode
    direction: NonEmptyStr
    counterparty: str = ""
    description: NonEmptyStr
    statement_reference: str | None = None
    business_classification: NonEmptyStr
    business_pct: str | None = None
    category_id: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    recargo_amount: str | None = None
    iva_category: str | None = None
    deduction_fact_kind: str | None = None
    investment_asset_id: str | None = None
    counterparty_country: str | None = None
    counterparty_identification_state: str | None = None
    irpf_category: str | None = None
    m210_income_classification: M210IncomeClassificationPayload | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    arrendamiento_ref: str | None = None
    inmueble_ref: str | None = None
    gasto_capital_inmobiliario: str | None = None
    purchase_invoice_evidence_id: str | None = None
    invoice_id: str | None = None
    attachment_ids: list[str] = []
    notes: str = ""
    lifecycle_state: NonEmptyStr
    classified_by: NonEmptyStr
    # Decision-provenance fields: the "why" behind the active
    # classification decision. Declared here so the strict single-transaction
    # read surface (ledger view/classify/update/archive/stash) accepts the
    # persisted provenance fields rather than rejecting them as
    # extra_forbidden.
    classified_at: str | None = None
    classification_reason: str = ""
    classification_confidence: str | None = None
    source_jurisdiction: str | None = None
    # FX provenance for foreign-currency rows: the
    # EUR-equivalent and applied CCY->EUR rate the application payload emits.
    # Declared here so the strict single-transaction read surface (ledger
    # view/classify/update/archive/stash) accepts the persisted FX fields
    # rather than rejecting them as extra_forbidden. None for EUR-native rows.
    value_in_eur: str | None = None
    fx_rate: str | None = None
    # Persistence-record lifecycle timestamps, rendered as ISO-8601 strings.
    created_at: str
    modified_at: str


class BulkClassifyFailurePayload(OutputSchema):
    """One failed row from a bulk classify operation."""

    row_index: int
    transaction_id: str
    reason: str


class LedgerReviewRowPayload(OutputSchema):
    """One :class:`LedgerReviewRow` transport row.

    Mirrors the canonical row's constraints rather than restating its fields as
    free strings: the id is the content-addressed transaction identity, the
    date is the 10-character ISO day, and the amount, description and review
    status are the values the row was projected from. Declared as bare ``str``
    this transport accepted ``id='bad'``, ``date='bad'`` and blank
    amount/description that :class:`LedgerReviewRow` itself refuses.
    """

    id: TransactionId
    date: IsoDateText
    amount: NonEmptyStr
    description: NonEmptyStr
    status: NonEmptyStr
    transaction: TransactionPayload | None = None


class LedgerRemovalBlockerPayload(OutputSchema):
    """One modelo revision reference surfaced by ledger removal.

    Mirrors :class:`LedgerRemovalBlocker`.  In
    ``blocking_modelo_references`` the row names a finalized revision that
    prevents removal because it still cites the transaction through
    ``source_transaction_ids``.  In ``stale_draft_revision_references`` the same
    shape is a non-blocking draft advisory that tells the operator which
    borradores should be recalculated after removal.
    """

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    revision_state: str
    modelo: str
    filing_year: int
    period: str


class LedgerSplitChildIdPayload(OutputSchema):
    """One persisted split-child id, carrying both the full and short forms.

    Emitted on the manual / applied split surface so an operator can copy the
    ids straight into ``aeat app ledger merge --child-id ...`` to undo the split.
    ``full_id`` is the 64-char canonical id ``merge`` resolves; ``display_id`` is
    the shortest unique prefix within the child cohort (the same display-width
    convention :class:`LedgerListRowPayload` uses), suitable for human reading.
    """

    full_id: str
    display_id: str


class LedgerSplitChildProposalPayload(OutputSchema):
    """One proposed child of an evidence-driven LLM split (preview surface).

    The model proposed the ``proportion`` and selected the ``category`` /
    ``iva_category``; the system DERIVED the euro ``amount`` and the regulated
    ``iva_rate`` / ``taxable_base`` / ``iva_amount`` from the registry. Numbers
    are JSON strings to preserve ``~decimal.Decimal`` precision.
    """

    proportion: str
    amount: str
    description: str
    category: str | None = None
    iva_category: str | None = None
    iva_rate: str | None = None
    taxable_base: str | None = None
    iva_amount: str | None = None
    rate_derivable: bool = False


# ---------------------------------------------------------------------------
# Mutation verb result schemas
# ---------------------------------------------------------------------------


class LedgerMutationResult(OutputSchema):
    """Shared shape for single-transaction mutation verbs.

    The uniform mutation quintet: every verb that mutates exactly one ledger
    transaction returns ``{bucket_id, transaction_id, bucket_event_ids,
    review_status, transaction}``. Subclassed per verb so each CommandSpec can
    reference its own schema target.
    """

    bucket_id: BucketId
    transaction_id: TransactionId
    bucket_event_ids: list[str]
    review_status: str
    transaction: TransactionPayload


class LedgerAddResult(LedgerMutationResult):
    """JSON envelope for ``aeat app ledger add``.

    ``add`` joins the uniform mutation quintet by subclassing
    :class:`LedgerMutationResult`, gaining the ``review_status`` field every
    other single-transaction mutation already carries.
    """


class LedgerUpdateResult(LedgerMutationResult):
    """JSON envelope for ``aeat app ledger update``."""


class LedgerClassifySingleResult(LedgerMutationResult):
    """JSON envelope for the single-transaction ``aeat app ledger classify`` path.

    The primary, non-optional mutation quintet: classifying one transaction
    returns the same ``{bucket_id, transaction_id, bucket_event_ids,
    review_status, transaction}`` shape every other single-transaction
    mutation carries, rather than the former all-optional union.
    """


class LedgerClassifyBulkResult(OutputSchema):
    """JSON result for the bulk ``aeat app ledger classify --file`` path.

    Structurally distinct from :class:`LedgerClassifySingleResult`: a bulk run
    reports row counts across many transactions, not one mutation quintet.
    """

    total: int
    applied: int
    skipped: int
    failures: list[BulkClassifyFailurePayload] = []


class LedgerClassifyResult(OutputRootSchema[LedgerClassifySingleResult | LedgerClassifyBulkResult]):
    """JSON envelope for ``aeat app ledger classify``, either branch.

    The one CLI leaf emits two structurally distinct shapes depending on
    ``--file``: the single-transaction mutation quintet
    (:class:`LedgerClassifySingleResult`) or the bulk row-count summary
    (:class:`LedgerClassifyBulkResult`). The JSON-schema conformance gate maps
    exactly one graph-declared schema per CLI leaf, so this discriminated root
    validates either branch under the one ``ledger.classify`` command key;
    ``model_dump`` serialises the flat branch shape, not a wrapped root.
    """


class LedgerAllocateResult(LedgerMutationResult):
    """JSON envelope for ``aeat app ledger allocate``."""


class LedgerAttachResult(LedgerMutationResult):
    """JSON envelope for ``aeat app ledger attach``."""


class LedgerDetachResult(LedgerMutationResult):
    """JSON envelope for ``aeat app ledger detach``.

    The same uniform single-transaction mutation shape the attach side returns:
    detaching is a mutation of one addressable transaction, so it reports the
    quintet rather than a bespoke payload.
    """


class LedgerArchiveResult(LedgerMutationResult):
    """JSON envelope for ``aeat app ledger archive``."""


class LedgerStashResult(LedgerMutationResult):
    """JSON envelope for ``aeat app ledger stash``."""


class LedgerRestoreResult(LedgerMutationResult):
    """JSON envelope for ``aeat app ledger restore``."""


class LedgerExcludeResult(LedgerMutationResult):
    """JSON envelope for ``aeat app ledger exclude``.

    Marks a reviewed transaction as deliberately excluded from filing; the
    ``review_status`` field carries ``excluded`` and the row stays in the
    uniform mutation quintet.
    """


class LedgerRemoveResult(OutputSchema):
    """JSON envelope for ``aeat app ledger remove``.

    Mirrors :class:`LedgerTransactionRemovalReport`.
    ``blocking_modelo_references`` is the hard finalized-revision guard;
    ``stale_draft_revision_references`` is advisory evidence for borradores that
    still cite the removed transaction and should be recalculated.
    """

    bucket_id: BucketId
    transaction_id: TransactionId
    removed: bool = False
    dry_run: bool = False
    actor: str
    reason: str = ""
    cascaded_purchase_invoice_evidence_ids: list[str] = []
    cascaded_attachment_ids: list[str] = []
    blocking_modelo_references: list[LedgerRemovalBlockerPayload] = []
    stale_draft_revision_references: list[LedgerRemovalBlockerPayload] = []
    bucket_event_ids: list[str] = []


class LedgerResetResult(OutputSchema):
    """JSON envelope for ``aeat app ledger reset``.

    Mirrors ``LedgerCatalogueResetReport.model_dump(mode='json')``.
    """

    bucket_id: BucketId
    removed_transaction_ids: list[str] = []
    reset: bool = False
    dry_run: bool = False
    actor: str
    reason: str = ""
    cascaded_purchase_invoice_evidence_ids: list[str] = []
    cascaded_attachment_ids: list[str] = []
    blocking_modelo_references: list[LedgerRemovalBlockerPayload] = []
    stale_draft_revision_references: list[LedgerRemovalBlockerPayload] = []
    bucket_event_ids: list[str] = []


class LedgerSplitResult(OutputSchema):
    """JSON envelope for ``aeat app ledger split``.

    Covers the manual split (explicit ``--child-amount`` / ``--child-description``)
    and the evidence-driven LLM split (``--llm``). On the LLM preview path
    (``--llm`` without ``--apply``) ``persisted`` is False, nothing is written, and
    ``proposed_children`` carries the derived child amounts for review; the
    structural ``split_group_id`` / ``bucket_event_id`` appear only once a split is
    actually persisted.
    """

    bucket_id: BucketId
    parent_transaction_id: TransactionId
    split_group_id: str | None = None
    child_transaction_ids: list[str] = []
    # Persisted child ids in full + short form so the operator can copy them
    # into ``ledger merge --child-id`` to undo the split (audit M11). Empty on
    # the LLM preview path, where nothing is persisted yet.
    child_transactions: list[LedgerSplitChildIdPayload] = []
    bucket_event_id: str | None = None
    # LLM evidence-driven path (--llm)
    llm: bool | None = None
    persisted: bool | None = None
    provider: str | None = None
    provenance: str | None = None
    reason: str | None = None
    parent_amount: str | None = None
    proposed_children: list[LedgerSplitChildProposalPayload] | None = None
    classified_child_count: int | None = None


class LedgerMergeResult(OutputSchema):
    """JSON envelope for ``aeat app ledger merge``."""

    bucket_id: BucketId
    split_group_id: str
    parent_transaction_id: TransactionId
    merged_transaction_id: TransactionId
    source_child_ids: list[str]
    bucket_event_id: str


# ---------------------------------------------------------------------------
# Query verb result schemas
# ---------------------------------------------------------------------------


class LedgerListRowPayload(OutputSchema):
    """One typed ``aeat app ledger list`` row.

    Projected from
    :class:`LedgerTransactionReviewPayload` plus the
    three id/group keys the list builder appends (``full_id``,
    ``display_id``, ``group_label``). Carries the non-negative ``amount`` magnitude
    plus ``direction`` and the ``created_at`` /
    ``modified_at`` lifecycle timestamps.
    """

    # Identity / display
    full_id: str
    display_id: str
    transaction_id: TransactionId
    # Core read projection (mirrors LedgerTransactionReviewPayload)
    date: str
    booked_date: str
    value_date: str | None = None
    operation_date: str | None = None
    accrual_date: str | None = None
    amount: str
    currency: IsoCurrencyCode
    direction: str
    counterparty: str = ""
    description: str
    statement_reference: str | None = None
    business_classification: str
    business_pct: str | None = None
    category_id: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    recargo_amount: str | None = None
    iva_category: str | None = None
    deduction_fact_kind: str | None = None
    investment_asset_id: str | None = None
    counterparty_country: str | None = None
    counterparty_identification_state: str | None = None
    irpf_category: str | None = None
    m210_income_classification: M210IncomeClassificationPayload | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    arrendamiento_ref: str | None = None
    inmueble_ref: str | None = None
    gasto_capital_inmobiliario: str | None = None
    purchase_invoice_evidence_id: str | None = None
    invoice_id: str | None = None
    attachment_ids: list[str] = []
    notes: str = ""
    lifecycle_state: str
    review_status: str
    classified_by: str
    # Decision-provenance fields: present so the row validates from
    # the shared `LedgerTransactionReviewPayload` dump without rejecting
    # extra keys; not rendered in the tab-delimited list line (view/history
    # are the dedicated provenance surfaces).
    classified_at: str | None = None
    classification_reason: str = ""
    classification_confidence: str | None = None
    source_jurisdiction: str | None = None
    value_in_eur: str | None = None
    fx_rate: str | None = None
    created_at: str
    modified_at: str
    # List-builder extras
    group_label: str | None = None


class LedgerKnownCounterpartyPayload(OutputSchema):
    """One party as ``aeat app ledger known-values`` names it."""

    name: str
    tax_id: str | None = None
    country: str | None = None
    identification_state: str | None = None
    uses: int
    last_used: str


class LedgerKnownTextPayload(OutputSchema):
    """One free text as ``aeat app ledger known-values`` names it."""

    text: str
    uses: int
    last_used: str
    counterparty: str | None = None


class LedgerKnownValuesResult(OutputSchema):
    """JSON envelope for ``aeat app ledger known-values``.

    Each list is most recent first and capped; ``truncated`` names the kinds that
    hold more than they show.
    """

    bucket_id: BucketId
    counterparties: list[LedgerKnownCounterpartyPayload]
    descriptions: list[LedgerKnownTextPayload]
    group_labels: list[LedgerKnownTextPayload]
    m210_payers: list[LedgerKnownTextPayload]
    m210_assets: list[LedgerKnownTextPayload]
    asset_references: list[LedgerKnownTextPayload]
    truncated: list[str]


class LedgerListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger list``.

    ``rows`` is the page actually rendered; ``total`` is the full bucket row
    count. When ``--limit`` clips the page, ``truncated`` is ``True`` and
    ``offset`` / ``limit`` describe the window so a large ledger is never
    silently capped — the consumer can always see that more rows exist.
    """

    bucket_id: BucketId
    rows: list[LedgerListRowPayload]
    total: int = 0
    shown: int = 0
    offset: int = 0
    limit: int | None = None
    truncated: bool = False


class LedgerViewResult(OutputSchema):
    """JSON envelope for ``aeat app ledger view``.

    Mirrors ``LedgerTransactionResultPayload``.
    """

    bucket_id: BucketId
    transaction_id: TransactionId
    review_status: str
    transaction: TransactionPayload


class LedgerReadinessIssuePayload(OutputSchema):
    """One readiness issue nested in ``aeat app ledger status``.

    Mirrors :class:`~cadrumo.application.ledger.readiness_query.LedgerReadinessIssueV1`.
    Every explaining fact is optional because it is optional on the row: a
    deductible transaction missing its category is the finding itself, not a
    gap in the read, so ``null`` here means "absent on the row" rather than
    "not looked up".
    """

    transaction_id: str
    reason: str
    detail: str
    transaction_present: bool
    business_classification: str | None = None
    category_id: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None


class LedgerStaleFilingPayload(OutputSchema):
    """One drifted filing nested in ``aeat app ledger status``.

    Mirrors :class:`~cadrumo.application.ledger.stale_filing_query.LedgerStaleFilingV1`,
    including ``covers_current_fact_set``: ``false`` means the comparison behind
    the counts was sound but narrower than today's fact set, not that anything
    additional drifted.
    """

    modelo: str
    filing_year: int
    period: str
    calculation_revision_id: str
    work_unit_id: str
    changed_count: NonNegativeInt
    removed_count: NonNegativeInt
    covers_current_fact_set: bool = True
    register_state: str = "current"
    register_change_count: NonNegativeInt = 0


class LedgerStatusResult(OutputSchema):
    """JSON envelope for ``aeat app ledger status``.

    Mirrors :class:`LedgerStatusReport`.  With no
    period it is an at-a-glance bucket summary; with ``--period`` it adds the
    ledger preflight counts and readiness verdict for the selected
    :class:`Period`.  The money totals are gross EUR roll-ups over
    active business/mixed rows, not modelo registry calculations.
    """

    bucket_id: BucketId
    business_income_total: str = "0.00"
    business_expense_total: str = "0.00"
    business_net_total: str = "0.00"
    total_count: NonNegativeInt
    active_count: NonNegativeInt
    archived_count: NonNegativeInt
    stashed_count: NonNegativeInt
    split_count: NonNegativeInt = 0
    pending_review_count: NonNegativeInt
    reviewed_count: NonNegativeInt
    skipped_count: NonNegativeInt
    period: Period | None = None
    checked_transaction_count: NonNegativeInt = 0
    readiness_issue_count: NonNegativeInt = 0
    # Active business rows left OUT of the money totals above because they are
    # foreign-currency with no conversion applied. A non-zero value says the
    # totals are partial; without it a JSON consumer cannot tell a complete
    # roll-up from one missing every unconverted row.
    unconverted_currency_count: NonNegativeInt = 0
    ready: bool | None = None
    # The findings behind ``readiness_issue_count``, and the drifted filings the
    # text output already lists. Both were computed by this command and emitted
    # only as text lines, so a JSON consumer could see that N issues existed but
    # never which -- and could not see a stale filing at all. A second frontend
    # cannot act on a count.
    readiness_issues: list[LedgerReadinessIssuePayload] = []
    stale_filings: list[LedgerStaleFilingPayload] = []


class LedgerHistoryEventPayload(OutputSchema):
    """One bucket event nested in ``aeat app ledger history``.

    Mirrors :class:`BucketEvent`'s
    ``model_dump(mode="json")`` — replaces the former bare ``dict[str, object]`` event shape. The
    ``payload`` mapping stays a typed ``dict[str, str]`` (the append-only event's
    free-form short-string detail, per the bucket-event contract), not a bare
    ``object`` map.
    """

    event_id: str
    bucket_id: BucketId
    event_type: str
    occurred_at: str
    actor: str
    object_type: str
    object_id: str
    payload_version: int
    payload: dict[str, str] = {}


class LedgerHistoryResult(OutputSchema):
    """JSON envelope for ``aeat app ledger history``."""

    bucket_id: BucketId
    transaction_id: TransactionId
    event_count: int
    events: list[LedgerHistoryEventPayload]


# ---------------------------------------------------------------------------
# Review verb result schemas
# ---------------------------------------------------------------------------


class LedgerReviewResult(OutputSchema):
    """JSON envelope for ``aeat app ledger review``.

    Covers three payload branches:
    - Multi-row list: ``rows`` + ``filters``
    - Empty-result (positional id with no match): empty ``rows`` + ``filters``
    - Single-row detail: scalar fields for the matched row

    Every field is optional because the branches are disjoint, so the branch
    invariant below -- not the field types -- is what makes the envelope
    honest: without it ``model_validate({})``, ``{"filters": []}`` and a
    half-populated detail all validated, and an operator could not tell an
    empty result from a malformed one.

    The detail fields carry the same constraints as
    :class:`LedgerReviewRowPayload`, so a detail branch cannot claim a row
    shape the canonical projection would refuse.
    """

    # Multi-row and empty-result paths
    rows: list[LedgerReviewRowPayload] | None = None
    filters: list[str] | None = None
    # Single-transaction detail path
    id: TransactionId | None = None
    date: IsoDateText | None = None
    amount: NonEmptyStr | None = None
    description: NonEmptyStr | None = None
    review_status: NonEmptyStr | None = None
    transaction: TransactionPayload | None = None
    verbose: bool | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _exactly_one_complete_branch(self) -> LedgerReviewResult:
        """Require the envelope to be exactly one of the three documented branches.

        ``rows``/``filters`` together are the list branch (an empty ``rows`` is
        the legitimate no-match result); the five detail fields together are the
        detail branch. Mixing them, or populating neither, describes no
        outcome the command can produce.

        Raises:
            ValueError: The envelope is neither a complete list branch nor a
                complete detail branch, or is both.
        """
        detail_fields = (self.id, self.date, self.amount, self.description, self.review_status)
        is_list_branch = self.rows is not None and self.filters is not None
        detail_present = sum(field is not None for field in detail_fields)
        is_detail_branch = detail_present == len(detail_fields)
        if is_list_branch and detail_present:
            raise ValueError("ledger review result must not mix the list and detail branches")
        if not is_list_branch and not is_detail_branch:
            raise ValueError(
                "ledger review result must populate either rows and filters, "
                "or every one of id, date, amount, description and review_status",
            )
        return self


# ---------------------------------------------------------------------------
# Diagnostic verb result schemas (check / preflight / link)
# ---------------------------------------------------------------------------


class LedgerLinkResult(OutputSchema):
    """JSON envelope for ``aeat app ledger link``.

    ``link`` establishes an invoice-only bidirectional relationship and carries
    only the link metadata. Evidence assignment is a separate operation
    (``aeat app ledger attach``) and never rides on this result.
    """

    operation: str
    bucket_id: BucketId
    transaction_id: TransactionId
    invoice_id: InvoiceId
    actor: str


# ---------------------------------------------------------------------------
# Usage-ratios sub-app result schemas
# ---------------------------------------------------------------------------

__all__ = [
    "BulkClassifyFailurePayload",
    "LedgerAddResult",
    "LedgerAllocateResult",
    "LedgerArchiveResult",
    "LedgerAttachResult",
    "LedgerClassifyBulkResult",
    "LedgerClassifyResult",
    "LedgerClassifySingleResult",
    "LedgerDetachResult",
    "LedgerEntryClassificationPayload",
    "LedgerEntryDecimalRulePayload",
    "LedgerEntryLimitsPayload",
    "LedgerEntryOptionFamilyPayload",
    "LedgerEntryOptionPayload",
    "LedgerEntryOptionsResult",
    "LedgerEntryPercentFieldPayload",
    "LedgerEntryTextLimitPayload",
    "LedgerExcludeResult",
    "LedgerHistoryEventPayload",
    "LedgerHistoryResult",
    "LedgerInvoiceDuplicateEnvelope",
    "LedgerInvoiceMatchEnvelope",
    "LedgerInvoiceMatchInvoiceChoicePayload",
    "LedgerInvoiceMatchJudgementPayload",
    "LedgerInvoiceMatchMismatchPayload",
    "LedgerInvoiceMatchMovementChoicePayload",
    "LedgerInvoiceMatchPairPayload",
    "LedgerInvoiceMatchSuggestionPayload",
    "LedgerInvoicePreviewFactPayload",
    "LedgerInvoicePreviewFigurePayload",
    "LedgerInvoicePreviewFindingPayload",
    "LedgerInvoicePreviewLinePayload",
    "LedgerInvoicePreviewRateSlotPayload",
    "LedgerInvoicePreviewResult",
    "LedgerInvoicePreviewRetentionPayload",
    "LedgerInvoicePreviewTotalsPayload",
    "LedgerLinkResult",
    "LedgerListResult",
    "LedgerListRowPayload",
    "LedgerMergeResult",
    "LedgerMutationResult",
    "LedgerReadinessIssuePayload",
    "LedgerRemovalBlockerPayload",
    "LedgerRemoveResult",
    "LedgerResetResult",
    "LedgerRestoreResult",
    "LedgerReviewResult",
    "LedgerReviewRowPayload",
    "LedgerRuleTrialEnvelope",
    "LedgerSplitCheckChildPayload",
    "LedgerSplitCheckEnvelope",
    "LedgerSplitCheckProblemPayload",
    "LedgerSplitChildIdPayload",
    "LedgerSplitChildProposalPayload",
    "LedgerSplitResult",
    "LedgerStagedBlockerPayload",
    "LedgerStagedCategoryFitPayload",
    "LedgerStagedCheckEnvelope",
    "LedgerStagedDraftPayload",
    "LedgerStagedNotePayload",
    "LedgerStagedRoutePayload",
    "LedgerStagedRowPayload",
    "LedgerStaleFilingPayload",
    "LedgerStashResult",
    "LedgerStatusResult",
    "LedgerUpdateResult",
    "LedgerViewResult",
    "M210IncomeClassificationPayload",
    "TransactionPayload",
]
