"""Strict immutable transaction-catalogue boundary models."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Self, override

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_core import core_schema

from ...core import (
    ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS,
    OBJECT_TUPLE_ADAPTER,
    Art104TresExclusion,
    ConceptoIngreso,
    IvaDeductionFactKind,
    TipoActividad,
    fold_diacritics,
)
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import CoreValidationError
from ...core.external_constants import CLASSIFIED_BY_AUTO, DEFAULT_CURRENCY
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId, TransactionId
from ...core.money import round_to_cents
from ...core.parsing import normalise_iso_3166_alpha2_jurisdiction, parse_iso8601_date
from ...core.time import now, parse_iso_datetime
from ..identifiers import canonical_decimal_string
from ..iva.deduction_facts import IvaDeductionClassificationProvenance
from ..iva.prorrata import InputClassification
from ..iva.schema import EUMemberState, IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment, IvaCategory, IvaExemptionArticle
from .enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from .errors import TransactionValidationError
from .irpf_categories import (
    PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING,
    RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING,
    has_activity_irpf_category,
    has_non_work_irpf_category,
    has_rent_irpf_category,
)
from .lineage_models import (
    ClassificationHistoryEntry,
    DecisionProvenance,
    SplitLineage,
    TransactionEditLineageEntry,
    TransactionEvidenceProvenanceEntry,
    TransactionLifecycleLineageEntry,
    _is_object_mapping,
    _string_keyed_mapping,
    derive_split_group_id,
)
from .m210_income_classification import M210IncomeClassification
from .model_validation import (
    coerce_raw_transaction,
    normalize_identifier_tuple,
    require_aware_datetime,
    validate_business_pct_coupling,
    validate_classified_by_shape,
    validate_confidence_range,
    validate_non_negative_decimal,
)
from .raw_transaction import RawTransaction
from .retencion_parameters import maximum_supported_activity_retencion_rate

__all__ = ["DecisionProvenance", "derive_split_group_id"]


def derive_transaction_id(raw: RawTransaction) -> str:
    """Return the stable transaction hash for one raw transaction.

    This content hash is the single authority for storage, audit, and
    machine consumers, and it intentionally **changes when an
    id-affecting fact is edited** (an ``update`` re-derives it and records
    the superseded id as a ``previous_transaction_id`` on the heir's
    :class:`TransactionEditLineageEntry` chain). The operator-facing
    *lineage* convenience that lets an old, written-down handle still
    resolve to the current row through ``ledger history`` / ``view`` /
    ``track`` (see
    :func:`application.ledger.id_resolution.resolve_lineage_transaction_id`) is a
    **read-side lookup layer over this authoritative id**; it never
    freezes or re-mints the id, so the content-addressing invariant import
    dedup relies on is untouched.

    Args:
        raw: The upstream immutable raw transaction emitted by a provider.

    Returns:
        A lowercase SHA-256 digest derived from the provider identity,
        effective value date, amount, and narrative fields.
    """
    effective_value_date = raw.value_date or raw.booked_date
    return content_hash_hex(
        {
            "amount": canonical_decimal_string(raw.amount),
            "narrative": raw.description,
            "provider_id": raw.provider_transaction_id,
            "value_date": effective_value_date.isoformat(),
        }
    )


_REFERENCE_NOISE = re.compile(r"[^0-9a-z]+")

#: Upper bound for an IVA rate held as a decimal fraction. This is the unit
#: boundary of a fraction, not a regulatory rate -- the highest Spanish IVA rate
#: is well below it -- so it stays a local constant rather than a registry lookup
#: and cannot drift with a filing year.
_MAX_IVA_RATE_FRACTION = Decimal("1")


def normalise_movement_reference(value: str) -> str:
    """Return a provider-agnostic normalised form of a transaction narrative.

    OFX and CSV exports of the same bank movement describe it with
    different verbatim narratives (an OFX ``MEMO`` versus a CSV
    reference column), and a later manual edit may further reword the
    description. Cross-format and post-edit deduplication therefore
    cannot key on the raw narrative.

    This collapses a narrative to a stable comparison token: Unicode
    is NFKD-decomposed and combining accents are dropped (``Ó`` -> ``o``),
    the result is lower-cased, and every run of non-alphanumeric
    characters is squeezed out. Two narratives that differ only in
    accents, casing, punctuation, or whitespace map to the same token.
    """
    stripped = fold_diacritics(value)
    return _REFERENCE_NOISE.sub("", stripped.casefold())


def derive_import_fingerprint(raw: RawTransaction, *, direction: TransactionDirection | str | None = None) -> str:
    """Return the stable cross-format import-dedup fingerprint for a raw row.

    Unlike :func:`derive_transaction_id` — which keys on the provider
    identifier and the verbatim narrative and therefore changes when a
    transaction is edited or re-exported in a different file format —
    this fingerprint keys only on the *movement identity* an operator
    would recognise: the effective date, amount magnitude, currency,
    direction, and the normalised narrative (see
    :func:`normalise_movement_reference`).

    The fingerprint is stamped onto :class:`Transaction` at import time
    and carried verbatim through every later edit, so re-importing the
    same statement (or the same movements exported as a different file
    format) recognises the row as already present. Import callers that
    have parsed flow direction must pass it; callers without a parse-boundary
    direction receive an explicit ``UNSPECIFIED`` discriminator.
    """
    effective_value_date = raw.value_date or raw.booked_date
    if isinstance(direction, TransactionDirection):
        direction_value = direction.value
    elif direction is None:
        direction_value = "UNSPECIFIED"
    else:
        direction_value = direction
    return content_hash_hex(
        {
            "amount": canonical_decimal_string(raw.amount),
            "currency": raw.currency,
            "direction": direction_value,
            "reference": normalise_movement_reference(raw.description),
            "value_date": effective_value_date.isoformat(),
        }
    )


def derive_movement_day_key(raw: RawTransaction) -> str:
    """Return the coarse (effective date, amount) key for a raw row.

    Two rows that share this key but not the full
    :func:`derive_import_fingerprint` are *likely* — but not
    confidently — the same movement: same day, same amount, divergent
    narrative. The import path uses this to warn the operator about a
    probable cross-format duplicate rather than silently importing it.
    """
    effective_value_date = raw.value_date or raw.booked_date
    return f"{effective_value_date.isoformat()}:{canonical_decimal_string(raw.amount)}"


def _derive_transaction_id_from_validated_data(data: dict[str, object]) -> str:
    raw = data.get("raw")
    if not isinstance(raw, RawTransaction):
        raise TransactionValidationError("raw is required before transaction_id can be derived")
    return derive_transaction_id(raw)


class Transaction(BaseModel):
    """Immutable transaction wrapper that preserves raw provenance verbatim.

    Attributes:
        transaction_id: Lowercase 64-char SHA-256 derived deterministically
            from the wrapped raw record by :func:`derive_transaction_id`.
            Re-validated on every parse to detect tampering.
        raw: The verbatim
            :class:`domain.transactions.raw_transaction.RawTransaction`.
        direction: Closed :class:`TransactionDirection`.
        business_classification: Current :class:`BusinessClassification`
            decision; defaults to
            :attr:`BusinessClassification.NOT_YET_PROCESSED`.
        business_pct: Required when ``business_classification`` is
            :attr:`BusinessClassification.MIXED`; ``None`` otherwise.
        invoice_id: Optional invoice foreign key.
        category_id: Optional :class:`domain.categories.SpendingCategory`
            foreign key.
        taxable_base: Optional IVA-exclusive base amount.
        iva_rate: Optional IVA rate expressed as a decimal fraction.
        iva_amount: Optional IVA amount on the row.
        irpf_category: Optional IRPF-specific category key.
        usage_ratio_id: Optional proportionality reference.
        prorrata_reference: Optional IVA prorrata substrate reference.
        art_104_tres_exclusion: Operator-declared LIVA art. 104.Tres
            denominator-exclusion tag. Set ONLY for the two judgment
            exclusions the ledger cannot infer -- foreign permanent
            establishment (1.º) and non-habitual inmobiliario/financiero
            operations (4.º); the transaction boundary rejects any
            auto-derived member (art. 7 no-sujeta, art. 9.1.d autoconsumo,
            bienes-inversión disposal, direct cuotas) since those are
            recognised from the category / register / structure. When set,
            the annual prorrata volume rollup excludes this operation from
            both terms of the art. 104.Dos ratio; the operation's own IVA
            cuota treatment is unaffected. ``None`` for every operation that
            is not an art. 104.Tres judgment exclusion.
        input_classification: Operator-declared LIVA art. 106 prorrata-especial
            per-input use classification (:class:`~domain.iva.InputClassification`):
            ``EXCLUSIVELY_DEDUCTIBLE`` (regla 1.ª, deducted in full),
            ``EXCLUSIVELY_NON_DEDUCTIBLE`` (regla 2.ª, no deduction), or
            ``COMMON`` (regla 3.ª, deducted at the general percentage). Meaningful
            only for a purchase row in a bucket whose prorrata register regime is
            especial; the regime-aware aggregation routes the deducible cuota by
            this classification. ``None`` for rows that are not under especial or
            carry no per-input use declaration.
        concepto_ingreso: Operator-declared income concept
            (:class:`~core.ConceptoIngreso`) for base-inclusion purposes. RD
            439/2007 art. 110.1.c) fixes the agrarian pago fraccionado on the
            *volumen de ingresos ... excluidas las subvenciones de capital y las
            indemnizaciones*, and the distinction runs INSIDE subsidies -- a
            subvención corriente counts and a subvención de capital does not --
            so no amount, category or counterparty on the row can settle it.
            ``None`` means ordinary income and is INCLUDED, because an unmarked
            receipt is far more likely to be ordinary than exceptional and
            defaulting the other way would drop real income out of a declared
            volume.
        tipo_actividad: Operator-declared Modelo 036 tipo de actividad
            (:class:`~core.TipoActividad`) the row's activity income belongs to.
            Present so a return that splits casillas by activity can route each
            row to the right one -- Modelo 131 carries the estimación-objetiva
            volume in casilla 01 and the agrarian volume in casilla 08, and
            without this axis the same rows would feed both and double-count. It
            also selects the RIRPF art. 95 retención partition through the
            registry correspondence in
            :mod:`~domain.transactions.tipo_actividad_partitions`. ``None`` for a
            row whose activity is undeclared or that carries no activity income at
            all; an aggregation that needs the split must treat ``None`` as
            unknown rather than as any particular activity.
        prorrata_sector_id: Operator-declared LIVA arts. 9.1.c / 101 differentiated
            sector this input belongs to. References a ``sector_id`` declared in
            the bucket's prorrata register sector definitions; the sector-aware
            aggregation applies THAT sector's provisional percentage to the row's
            deducible cuota. ``None`` means common-use (usable across sectors),
            apportioned by the art. 104.Dos common percentage in a sectorized
            bucket; in a non-sectorized bucket ``None`` is the whole-entity
            default (today's behaviour), so an unsectored taxpayer is unaffected.
        purchase_invoice_evidence_id: Canonical purchase-invoice evidence
            reference attached to the row.
        attachment_ids: Supplementary attachment references.
        created_by: Actor that first created the manual row when known.
        source_command: Backend/CLI command source that created the row.
        created_event_id: Bucket event id for the create event when available.
        evidence_provenance: Actor/source lineage for attached evidence.
        edit_lineage: Durable edit chain for manual corrections.
        lifecycle_state: Current active/archive/stash/split state.
        lifecycle_lineage: Durable lifecycle transition chain.
        split_lineage: Optional :class:`SplitLineage` recording this row's
            role within an N-way split cohort. ``None`` for transactions
            that have never been split.
        notes: Free-text notes.
        import_fingerprint: Stable cross-format dedup fingerprint stamped
            at import time (see :func:`derive_import_fingerprint`) and
            carried verbatim through every later edit so re-imports of
            the same statement — or the same movements in a different
            file format — are recognised as already present. ``None``
            for hand-entered rows that never came from an import.
        classified_at: Timezone-aware timestamp of the active decision
            (``None`` when never classified).
        classified_by: Classifier source string for the active decision.
        classification_reason: Free-text reason for the active decision.
        classification_confidence: Optional confidence in ``[0, 1]`` for
            the active decision.
        classification_history: Tuple of historical
            :class:`ClassificationHistoryEntry` records, oldest first.
        iva_category: Explicit IVA category override.  When set the
            aggregation layer uses this value in place of the
            rate-kind-derived domestic category, enabling non-domestic
            categories (intra-community, export, non-subject) to be
            expressed without a synthetic rate.  ``None`` for
            transactions where the standard domestic rate derivation
            is sufficient.
        exemption_article: Optional Ley 37/1992 Art. 20 sub-article
            discriminator. Valid only when ``iva_category`` is
            :attr:`IvaCategory.DOMESTIC_EXEMPT`; ``None`` preserves
            the broad exempt category with no sub-article distinction.
        counterparty_country: Where the counterparty is ESTABLISHED --
            an address fact, ISO 3166-1 alpha-2. It answers
            establishment-flavoured questions only and is barred from
            identification-keyed gates. ``None`` means establishment
            was not recorded, never that the party is established
            nowhere and above all never that it is outside the Union.

            Stored as the raw code rather than as a Member State enum,
            which is the whole point of the field: an enum closed over
            the Member States can say "established in Germany" and
            cannot say "established in the United States", so absence
            was the only representation a third country had. A gate
            reading that absence as third-country establishment was
            reading "not recorded" as "outside the Union" -- and on the
            issued side outside the Union is export treatment,
            zero-rated, so an unrecorded establishment silently
            exempted a supply. The code is handed to
            :func:`~domain.iva.territorial_scope_for_country`, which
            answers from the closed vocabulary and refuses a code that
            names no country, so ``XX`` establishes nothing rather than
            establishing an export.

            This mirrors :class:`~domain.invoices.Invoice`, which has
            always stored the country and derived the Member State.
            The two models disagreeing about how one fact is held is
            what let the ledger path lose a distinction the invoice
            path kept.
        counterparty_eu_member_state: The Member State the counterparty
            is established in, DERIVED from ``counterparty_country``
            and ``None`` for every country outside the Union. Not a
            stored fact: one establishment cannot be recorded twice
            without the two copies eventually disagreeing.
        counterparty_identification_state: Which Member State
            IVA-IDENTIFIES the counterparty, read from the prefix of
            the IVA number it trades under. A different fact from
            establishment and never derived from it: a Spanish-established
            acquirer can hold a German IVA number, and a German-established
            one can purchase under a Spanish NIF-IVA. This is the operative
            fact for the Ley 37/1992 art. 25 exemption, so the aggregation
            gate requires it non-ES when ``iva_category`` is
            :attr:`IvaCategory.INTRA_COMMUNITY_SUPPLY`.

            ``None`` means the identification was not established, never
            that the party is identified nowhere and above all never that
            it is identified in Spain -- a decision needing it refuses
            with a review item rather than falling back to the country.
        cash_accounting_treatment: Independent criterio-de-caja axis.
            It never replaces ``iva_category``: the operation remains
            domestic/export/intracom/etc. and this field only records
            whether the taxpayer's special regime or a supplier's
            special regime changes IVA timing.
        operation_date: The LIVA art. 75 devengo date -- when the
            operation legally occurred, as distinct from when the bank
            moved. Optional on every regime and REQUIRED whenever
            ``cash_accounting_treatment`` is not ``NONE``, so the
            aggregator never silently reuses a bank movement date as the
            legal devengo projection.

            Available to the general regime, not only to criterio de
            caja. Under art. 75 the cuota is devengada when the
            operation occurs regardless of collection, so for a
            general-regime row the operation date is the legally
            CONTROLLING one and the movement date is the proxy; the
            criterio-de-caja regime is the one where collection timing
            governs and this date is the informational counterpart.
            Restricting the field to cash accounting therefore withheld
            it from the only regime the law binds to it, leaving an
            invoice issued in one quarter and paid in another to declare
            its IVA in the quarter of payment.

            ``None`` means the row makes no distinction, and the
            movement date stands as the operation date -- correct
            whenever an operation is settled on the day it occurs, which
            is the ordinary case.
        cash_accounting_payment_evidence: Total or partial
            collection/payment events that settle affected base/cuota
            under LIVA arts. 163 terdecies / quinquiesdecies.
        fx_rate: ECB reference rate applied at import time to convert
            ``raw.amount`` from ``raw.currency`` to EUR.  The rate is
            expressed as a multiplier: ``raw.amount * fx_rate =
            value_in_eur``.  ``None`` when the native currency is EUR
            or when the rate was unavailable at import time.
        value_in_eur: Pre-converted EUR-equivalent of ``raw.amount``
            computed at import time as ``raw.amount * fx_rate``,
            rounded to two decimal places.  Aggregation layers use
            this field in place of ``raw.amount`` for non-EUR
            transactions, making casilla sums deterministic and
            independent of rate changes after the import date.
            ``None`` when the native currency is EUR or when no rate
            was available.
        source_jurisdiction: ISO 3166-1 alpha-2 uppercase code identifying
            the regulatory source jurisdiction of the income or expense
            (``"ES"`` for Spanish-source, foreign two-letter codes for
            foreign-source). Drives the IRNR scope filter (non-resident
            profiles only emit Spanish-source rows into AEAT bases) and
            the Art. 93 LIRPF Beckham filter (impatriado IRPF base
            excludes foreign-source rows). ``None`` records an explicitly
            unknown jurisdiction.
        created_at: UTC-aware timestamp stamped once at construction and
            carried verbatim through every later edit.
        modified_at: UTC-aware timestamp re-stamped on every mutating edit.
    """

    model_config = _STRICT_FROZEN

    raw: RawTransaction
    transaction_id: TransactionId = Field(default_factory=_derive_transaction_id_from_validated_data)
    direction: TransactionDirection
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED
    business_pct: Decimal | None = None
    invoice_id: str | None = None
    category_id: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    recargo_amount: Decimal | None = None
    irpf_category: str | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    art_104_tres_exclusion: Art104TresExclusion | None = None
    input_classification: InputClassification | None = None
    tipo_actividad: TipoActividad | None = None
    concepto_ingreso: ConceptoIngreso | None = None
    prorrata_sector_id: str | None = Field(default=None, min_length=1, max_length=64)
    purchase_invoice_evidence_id: str | None = None
    attachment_ids: tuple[str, ...] = ()
    created_by: str | None = None
    source_command: str | None = None
    created_event_id: str | None = None
    evidence_provenance: tuple[TransactionEvidenceProvenanceEntry, ...] = ()
    edit_lineage: tuple[TransactionEditLineageEntry, ...] = ()
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE
    lifecycle_lineage: tuple[TransactionLifecycleLineageEntry, ...] = ()
    split_lineage: SplitLineage | None = None
    notes: str = ""
    import_fingerprint: str | None = None
    classified_at: datetime | None = None
    classified_by: str = Field(default=CLASSIFIED_BY_AUTO, min_length=1)
    classification_reason: str = ""
    classification_confidence: Decimal | None = None
    classification_history: tuple[ClassificationHistoryEntry, ...] = ()
    iva_category: IvaCategory | None = None
    deduction_fact_kind: IvaDeductionFactKind | None = None
    deduction_provenance: IvaDeductionClassificationProvenance | None = None
    investment_asset_id: str | None = None
    rectifies_ledger_id: str | None = None
    exemption_article: IvaExemptionArticle | None = None
    counterparty_country: str | None = None
    counterparty_identification_state: EUMemberState | None = None
    cash_accounting_treatment: IvaCashAccountingTreatment = IvaCashAccountingTreatment.NONE
    operation_date: date | None = None
    cash_accounting_payment_evidence: tuple[IvaCashAccountingPaymentEvidence, ...] = ()
    fx_rate: Decimal | None = None
    value_in_eur: Decimal | None = None
    # FX provenance: the rate source label (e.g.
    # "ecb_reference") and the effective rate date as an ISO-8601 string.
    # Optional; populated at import when a normalizer supplied them. Cannot
    # exist without an fx_rate (a rate provenance with no rate is
    # meaningless). Stored as a string (not date) to roundtrip cleanly through the
    # strict-frozen JSON persistence boundary.
    rate_source: str | None = None
    rate_date: str | None = None
    source_jurisdiction: str | None
    m210_income_classification: M210IncomeClassification | None = None
    # Operator-assigned free-text grouping label (e.g. "Proyecto Acme",
    # "Q1 viajes"). Orthogonal to category_id (the regulatory spending
    # category): it is a personal organisational axis for working at scale
    # over thousands of rows. ``None`` means ungrouped. Length-bounded so a
    # grouped display stays legible.
    group_label: str | None = Field(..., max_length=64)
    # Persistence-record lifecycle timestamps (ledger-interface-contract D6).
    # ``created_at`` is stamped once and carried verbatim through every later
    # edit; ``modified_at`` is re-stamped on every mutating edit
    # (update/classify/allocate/attach/doclink/archive/stash/restore/link/
    # split/merge). They make ``--sort-by created_at|modified_at`` honest for
    # hand-added rows, which otherwise carry no creation timestamp (only
    # imported rows have ``raw.provenance.ingested_at``). Both are UTC-aware.
    created_at: datetime = Field(default_factory=now)
    modified_at: datetime = Field(default_factory=now)

    @field_validator("raw", mode="before")
    @classmethod
    def _coerce_raw_field(cls, value: object) -> object:
        """Accept a ``RawTransaction`` or a JSON-shaped/python-native mapping.

        Delegates to :func:`coerce_raw_transaction`, which validates through
        ``RawTransaction``'s own validators -- never ``Transaction``'s -- so
        this carries no re-entrant recursion risk (unlike a model-level
        ``Transaction`` before-validator that called back into
        ``Transaction.model_validate*``, which recurses forever because that
        re-invokes this exact model-level hook on the still string-shaped
        JSON-decoded dict).
        """
        return coerce_raw_transaction(value)

    @field_validator(
        "direction",
        "business_classification",
        "lifecycle_state",
        "iva_category",
        "deduction_fact_kind",
        "exemption_article",
        "counterparty_identification_state",
        "cash_accounting_treatment",
        "art_104_tres_exclusion",
        "input_classification",
        "tipo_actividad",
        "concepto_ingreso",
        mode="before",
    )
    @classmethod
    def _coerce_enum_field(cls, value: object, info: core_schema.ValidationInfo) -> object:
        """Accept a JSON-decoded enum string alongside a real enum instance.

        A field-level ``mode="before"`` coercion inspects only this one
        field's value and never re-triggers model-level validation, so it
        carries no re-entrancy risk. No-op for an already-typed enum member
        or ``None``.
        """
        if not isinstance(value, str):
            return value
        enum_by_field: dict[str, type] = {
            "direction": TransactionDirection,
            "business_classification": BusinessClassification,
            "lifecycle_state": TransactionLifecycleState,
            "iva_category": IvaCategory,
            "deduction_fact_kind": IvaDeductionFactKind,
            "exemption_article": IvaExemptionArticle,
            "counterparty_identification_state": EUMemberState,
            "cash_accounting_treatment": IvaCashAccountingTreatment,
            "art_104_tres_exclusion": Art104TresExclusion,
            "input_classification": InputClassification,
            "tipo_actividad": TipoActividad,
            "concepto_ingreso": ConceptoIngreso,
        }
        return enum_by_field[info.field_name or ""](value)

    @field_validator("operation_date", mode="before")
    @classmethod
    def _parse_operation_date(cls, value: object) -> object:
        if isinstance(value, str):
            return parse_iso8601_date(value)
        return value

    @field_validator(
        "business_pct",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "recargo_amount",
        "classification_confidence",
        "fx_rate",
        "value_in_eur",
        mode="before",
    )
    @classmethod
    def _coerce_decimal_field(cls, value: object) -> object:
        """Accept a JSON-decoded ``Decimal`` string alongside a real ``Decimal``."""
        if isinstance(value, str):
            return Decimal(value)
        return value

    @field_validator("iva_rate")
    @classmethod
    def _iva_rate_is_a_fraction_not_a_percentage(cls, value: Decimal | None) -> Decimal | None:
        """Refuse an IVA rate that was supplied as a percentage.

        This field is a fraction: 21% IVA is ``0.21``. The inventory and asset
        ledgers take the same tax concept as a percentage bounded 0-100 and divide
        by a hundred themselves, so an operator moving between those surfaces and
        this one has two conventions under one option name and no signal telling
        them which applies.

        Left unbounded, ``21`` stored here is a 2100% rate: arithmetically valid,
        silently accepted, and a hundredfold over-statement of the cuota on every
        downstream aggregation that reads the row. No Spanish IVA rate exceeds 21%
        (LIVA arts. 90-91), so no legitimate fraction is above 1 and the refusal
        cannot reject a real filing.

        The message names the convention rather than the bound, because the
        failure it catches is a unit mistake and ``must be <= 1`` does not tell
        the operator that.
        """
        if value is not None and value > _MAX_IVA_RATE_FRACTION:
            raise ValueError(
                f"iva_rate is a decimal fraction, not a percentage: got {value}. Express 21% IVA as 0.21.",
            )
        return value

    @field_validator("classified_at", "created_at", "modified_at", mode="before")
    @classmethod
    def _coerce_datetime_field(cls, value: object) -> object:
        """Accept a JSON-decoded ISO-8601 datetime string alongside a real ``datetime``."""
        if isinstance(value, str):
            return parse_iso_datetime(value)
        return value

    @field_validator(
        "attachment_ids",
        "evidence_provenance",
        "edit_lineage",
        "lifecycle_lineage",
        "classification_history",
        "cash_accounting_payment_evidence",
        mode="before",
    )
    @classmethod
    def _coerce_collection_field(cls, value: object) -> object:
        """Freeze a JSON-decoded list into the declared tuple shape.

        Under strict mode a python-mode ``list`` fails ``tuple_type`` even
        though a JSON-decoded array is legitimately a list; this makes the
        JSON-shaped list acceptable without loosening the frozen-tuple
        contract on the stored value. ``None`` also collapses to the field's
        empty-tuple default rather than failing ``tuple_type``.
        """
        if value is None:
            return ()
        if isinstance(value, list):
            return OBJECT_TUPLE_ADAPTER.validate_python(value)
        return value

    @model_validator(mode="after")
    def _enforce_derived_transaction_id(self) -> Self:
        """Validate ``transaction_id`` against the already-validated raw record."""
        if self.transaction_id != derive_transaction_id(self.raw):
            raise TransactionValidationError("transaction_id must match the stable hash derived from raw")
        return self

    @field_validator(
        "invoice_id",
        "category_id",
        "irpf_category",
        "usage_ratio_id",
        "prorrata_reference",
        "purchase_invoice_evidence_id",
        "created_by",
        "source_command",
        "created_event_id",
    )
    @classmethod
    def _validate_optional_ids(cls, value: str | None) -> str | None:
        """Trim optional foreign keys while rejecting blank strings."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("foreign-key identifiers must not be blank")
        return trimmed

    @field_validator("attachment_ids")
    @classmethod
    def _validate_identifier_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Trim and freeze attachment identifiers."""
        return normalize_identifier_tuple(value)

    @field_validator("taxable_base", "iva_rate", "iva_amount", "recargo_amount")
    @classmethod
    def _validate_tax_amounts(cls, value: Decimal | None, info: core_schema.ValidationInfo) -> Decimal | None:
        """Reject negative tax substrate values."""
        return validate_non_negative_decimal(value, field_name=info.field_name or "")

    @field_validator("notes", "classification_reason")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        """Trim free-text fields while allowing the empty string."""
        return value.strip()

    @field_validator("classified_by")
    @classmethod
    def _validate_classified_by(cls, value: str) -> str:
        """Restrict ``classified_by`` to the approved shapes."""
        return validate_classified_by_shape(value)

    @field_validator("classified_at", "created_at", "modified_at")
    @classmethod
    def _require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        """Reject naive classification/lifecycle timestamps; ``None`` remains valid here."""
        if value is None:
            return None
        return require_aware_datetime(value)

    @field_validator("classification_confidence")
    @classmethod
    def _validate_classification_confidence(cls, value: Decimal | None) -> Decimal | None:
        """Restrict classification_confidence to the inclusive 0..1 range when not None."""
        return validate_confidence_range(value)

    @field_validator("fx_rate", "value_in_eur")
    @classmethod
    def _validate_fx_fields(cls, value: Decimal | None, info: core_schema.ValidationInfo) -> Decimal | None:
        """Reject negative FX rate or converted amounts."""
        return validate_non_negative_decimal(value, field_name=info.field_name or "")

    @field_validator("source_jurisdiction")
    @classmethod
    def _validate_source_jurisdiction(cls, value: str | None) -> str | None:
        """Restrict source_jurisdiction to an ISO 3166-1 alpha-2 uppercase code.

        Carries the regulatory-source axis (Spanish-source vs foreign-source)
        through every ledger boundary. Required for IRNR scope enforcement and
        for the Art. 93 LIRPF impatriado base filter; ``None`` means the
        current record explicitly declares the jurisdiction unknown.

        The shape policy is owned by
        :func:`~core.parsing.normalise_iso_3166_alpha2_jurisdiction`, shared
        with the application-layer ledger command and payload models, so the
        two boundaries cannot drift apart on which tokens they accept. Only
        the domain error type is re-raised here.
        """
        try:
            return normalise_iso_3166_alpha2_jurisdiction(value)
        except CoreValidationError as exc:
            raise TransactionValidationError(str(exc)) from exc

    @field_validator("counterparty_country")
    @classmethod
    def _validate_counterparty_country(cls, value: str | None) -> str | None:
        """Restrict counterparty_country to an ISO 3166-1 alpha-2 uppercase code.

        Shape only, and deliberately not membership. Whether a code names a
        country this codebase can place is a separate question with a separate
        authority -- :func:`~domain.iva.territorial_scope_for_country` and
        :func:`~domain.iva.stated_country_code_status` -- and asking it here
        would refuse a real jurisdiction the bundled vocabulary has simply not
        catalogued yet. Those exist at any given moment -- the vocabulary is a
        bounded subset that grows -- so a membership check at construction would
        make a true establishment unrecordable, while a shape check records it
        and lets the gate report the catalogue gap. Naming whichever country
        happens to be outside today would date this paragraph the moment that
        row is written, which is the same coupling the specimen helpers exist to
        remove.

        The shape policy is the same
        :func:`~core.parsing.normalise_iso_3166_alpha2_jurisdiction` that owns
        ``source_jurisdiction`` above, so one model does not accept two
        different spellings of a country code.
        """
        try:
            return normalise_iso_3166_alpha2_jurisdiction(value)
        except CoreValidationError as exc:
            raise TransactionValidationError(str(exc)) from exc

    @property
    def counterparty_eu_member_state(self) -> EUMemberState | None:
        """Return the Member State the counterparty is established in, or ``None``.

        Derived from :attr:`counterparty_country` rather than stored beside it,
        matching :class:`~domain.invoices.Invoice`. Two stored copies of one
        establishment fact can disagree, and the disagreement is silent.

        ``None`` covers three different situations and deliberately does not
        distinguish them, because a Member State accessor is the wrong place to:
        no country was recorded, the country is outside the Union, or the code
        names no country at all. A caller that must tell those apart asks
        :func:`~domain.iva.territorial_scope_for_country` for the territory and
        :func:`~domain.iva.stated_country_code_status` for why nothing resolved.
        Reading this ``None`` as "outside the Union" is exactly the inference
        that let an unrecorded establishment zero-rate a supply.
        """
        if self.counterparty_country is None:
            return None
        try:
            return EUMemberState(self.counterparty_country.lower())
        except ValueError:
            return None

    @model_validator(mode="after")
    def _enforce_business_pct(self) -> Self:
        """Enforce the classification/business percentage coupling."""
        validate_business_pct_coupling(self.business_classification, self.business_pct)
        return self

    @model_validator(mode="after")
    def _enforce_exemption_article_category(self) -> Self:
        """Keep the Art. 20 discriminator coupled to domestic exempt IVA rows."""
        if self.exemption_article is not None and self.iva_category is not IvaCategory.DOMESTIC_EXEMPT:
            actual = self.iva_category.value if self.iva_category is not None else None
            raise TransactionValidationError(
                f"exemption_article is only valid when iva_category is DOMESTIC_EXEMPT; got iva_category {actual!r}",
            )
        return self

    @model_validator(mode="after")
    def _enforce_art_104_tres_exclusion_is_operator_declared(self) -> Self:
        """Reject an auto-derived art. 104.Tres exclusion as an operator transaction tag.

        Only the two judgment exclusions (foreign PE, non-habitual
        inmobiliario/financiero) are operator-declared. The other four are
        recognised structurally, from the IVA category, or from the
        bienes-inversión register; declaring one on a transaction would
        double-count or misroute a value the ledger already excludes, so the
        boundary refuses it loudly rather than silently mis-scoping the
        prorrata denominator.
        """
        if (
            self.art_104_tres_exclusion is not None
            and self.art_104_tres_exclusion not in ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS
        ):
            accepted = ", ".join(sorted(member.value for member in ART_104_TRES_OPERATOR_DECLARED_EXCLUSIONS))
            raise TransactionValidationError(
                "art_104_tres_exclusion is operator-declared only for the two judgment exclusions "
                f"({accepted}); {self.art_104_tres_exclusion.value!r} is auto-derived and must not be tagged on a "
                "transaction",
            )
        return self

    @model_validator(mode="after")
    def _enforce_cash_accounting_axis(self) -> Self:
        """Keep cash-accounting timing evidence independent and complete.

        ``operation_date`` is deliberately NOT gated on the regime. It is the
        LIVA art. 75 devengo date, which the general regime needs most: there
        the operation date is legally controlling and collection timing is
        irrelevant, so withholding the field from that regime forced its rows
        onto the bank movement date. Only the settlement evidence below is
        criterio-de-caja-specific, because only that regime settles a cuota
        across several collections.
        """
        if self.cash_accounting_treatment is IvaCashAccountingTreatment.NONE:
            if self.cash_accounting_payment_evidence:
                raise TransactionValidationError(
                    "cash_accounting_payment_evidence requires a non-NONE cash_accounting_treatment",
                )
            return self
        if self.operation_date is None:
            raise TransactionValidationError(
                "operation_date is required when cash_accounting_treatment is not NONE",
            )
        if not self.cash_accounting_payment_evidence:
            raise TransactionValidationError(
                "cash_accounting_payment_evidence is required for cash-accounting operations; "
                "wholly unpaid fallback-only operations are not yet represented",
            )
        if self.taxable_base is None or self.iva_amount is None:
            raise TransactionValidationError(
                "cash-accounting operations require taxable_base and iva_amount facts",
            )
        if (
            self.cash_accounting_treatment is IvaCashAccountingTreatment.SUPPLIER_REGIME
            and self.direction is not TransactionDirection.OUTGOING
        ):
            raise TransactionValidationError(
                "supplier-regime cash-accounting treatment is only valid on received/purchase rows",
            )
        fallback_date = date(self.operation_date.year + 1, 12, 31)
        total_base = sum((evidence.taxable_base for evidence in self.cash_accounting_payment_evidence), Decimal("0"))
        total_iva = sum((evidence.iva_amount for evidence in self.cash_accounting_payment_evidence), Decimal("0"))
        total_recargo = sum(
            (evidence.recargo_amount for evidence in self.cash_accounting_payment_evidence),
            Decimal("0"),
        )
        recargo_amount = self.recargo_amount or Decimal("0")
        if total_base > self.taxable_base or total_iva > self.iva_amount or total_recargo > recargo_amount:
            raise TransactionValidationError(
                "cash_accounting_payment_evidence totals must not exceed taxable_base, iva_amount, or recargo_amount",
            )
        if any(evidence.payment_date > fallback_date for evidence in self.cash_accounting_payment_evidence):
            raise TransactionValidationError(
                "cash_accounting_payment_evidence cannot fall after the 31 December statutory fallback date",
            )
        return self

    @model_validator(mode="after")
    def _enforce_fx_coupling(self) -> Self:
        """Enforce that fx_rate and value_in_eur are both set or both absent.

        A non-EUR transaction may carry neither (rate unavailable at import)
        but must never carry only one of the pair, which would signal a
        partially-applied conversion.  EUR-native transactions must have
        both fields absent.
        """
        fx_set = self.fx_rate is not None
        eur_set = self.value_in_eur is not None
        if fx_set != eur_set:
            raise TransactionValidationError("fx_rate and value_in_eur must both be set or both be absent")
        if self.raw.currency == DEFAULT_CURRENCY and (fx_set or eur_set):
            raise TransactionValidationError("fx_rate and value_in_eur must be absent for EUR-native transactions")
        if (self.rate_source is not None or self.rate_date is not None) and not fx_set:
            raise TransactionValidationError("rate_source/rate_date require an fx_rate (rate provenance needs a rate)")
        return self

    @model_validator(mode="after")
    def _enforce_gross_equals_base_plus_iva_plus_recargo(self) -> Self:
        """Enforce ``gross == taxable_base + iva_amount + recargo_amount`` to the cent.

        The IVA-exclusive :attr:`taxable_base`, the :attr:`iva_amount`
        charged on the row, and the :attr:`recargo_amount` surcharged on it
        must reconstitute the IVA-inclusive gross. The gross reference is
        ``raw.amount`` taken as an absolute value: the tax substrate is
        denominated in the row's native currency (the aggregation layer
        carries ``value_in_eur`` as a separate parallel EUR projection and
        does **not** apply ``fx_rate`` to the base or amount), and the
        income/expense direction lives on :attr:`direction`, not on the sign
        of the tax substrate.

        Recargo sits on the opposite side of this identity from retención,
        and that contrast is why it belongs inside the gross. Retención is
        settlement-side: it reduces what the payer *transfers* without
        changing what the operation *cost*, which is why every relaxation
        below is gated on the reconstituted substrate exceeding the cash.
        Recargo de equivalencia is a price component — LIVA art. 161 has the
        supplier repercutir it on the entrega alongside the cuota, and the
        comerciante minorista genuinely owes it — so it is part of the money
        that moved. Omitting it inverted the check's polarity rather than
        merely narrowing it: a recargo row reconstitutes *below* its cash and
        no relaxation covers that direction, so the truthful row (cash
        including the surcharge) was refused while the falsified one
        (surcharge charged, cash understated by it) validated.

        A ``recargo_amount`` of ``None`` contributes zero, which is the
        ordinary case — the overwhelming majority of rows are not supplies to
        a comerciante minorista.

        For self-assessed IVA categories (reverse charge and imports), the
        paid cash gross matches the taxable base; the IVA amount is
        self-assessed but not paid in the transaction itself. Recargo stays
        out of that branch for the same reason it stays out of the IVA
        there: on a self-liquidated acquisition the supplier repercutes
        neither the cuota nor the surcharge, so neither reaches the cash
        movement this row records.

        For professional activity invoices paid or received net of IRPF
        withholding, the bank cash can be lower than the invoice gross while
        the declared base and IVA still need to preserve the invoice substrate.
        That relaxation is accepted only for INCOMING activity rows, or for
        OUTGOING professional-service expense rows, with an explicit
        actividad-economica ``irpf_category`` and only when the reconstituted
        substrate is above the cash movement; under-declared invoice gross
        remains refused.

        For rent expenses paid net of withholding, the same substrate
        preservation is accepted only for OUTGOING rows in the scoped rent
        categories with an explicit non-work ``irpf_category``. The supplier
        invoice base and IVA still reconstitute the invoice gross, while the
        bank movement reflects cash after withholding.

        The check fires **only when both** :attr:`taxable_base` and
        :attr:`iva_amount` are present. A row with either field unset (the
        common case — most transactions never carry the tax substrate)
        validates unconditionally, so the invariant cannot break the
        existing transaction corpus. A recargo declared without either of
        them is therefore unchecked here too, which is the existing
        deliberate shape of this gate rather than a new hole.
        """
        if self.taxable_base is None or self.iva_amount is None:
            return self
        if self.iva_category in {
            IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            IvaCategory.DOMESTIC_REVERSE_CHARGE,
            IvaCategory.IMPORT_THIRD_COUNTRY,
        }:
            expected = round_to_cents(abs(self.raw.amount))
            reconstituted = round_to_cents(self.taxable_base)
            if reconstituted != expected:
                raise TransactionValidationError(
                    "taxable_base must equal the gross to the cent for self-assessed IVA: "
                    f"{self.taxable_base} != {expected}",
                )
            return self
        recargo = self.recargo_amount or Decimal("0")
        expected = round_to_cents(abs(self.raw.amount))
        reconstituted = round_to_cents(self.taxable_base + self.iva_amount + recargo)
        if reconstituted == expected:
            return self
        if (
            self.direction == TransactionDirection.INCOMING
            and has_non_work_irpf_category(self.irpf_category, direction=self.direction)
            and reconstituted > expected
        ):
            inferred_withholding = round_to_cents(reconstituted - expected)
            if has_activity_irpf_category(self.irpf_category, direction=self.direction):
                maximum_supported_withholding = round_to_cents(
                    self.taxable_base * maximum_supported_activity_retencion_rate(),
                )
                if inferred_withholding > maximum_supported_withholding:
                    raise TransactionValidationError(
                        "inferred IRPF withholding exceeds supported activity rate; "
                        "cash amount may be invoice base without IVA",
                    )
            return self
        if (
            self.direction == TransactionDirection.OUTGOING
            and self.category_id in PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING
            and has_activity_irpf_category(self.irpf_category, direction=self.direction)
            and reconstituted > expected
        ):
            inferred_withholding = round_to_cents(reconstituted - expected)
            maximum_supported_withholding = round_to_cents(
                self.taxable_base * maximum_supported_activity_retencion_rate(),
            )
            if inferred_withholding > maximum_supported_withholding:
                raise TransactionValidationError(
                    "inferred IRPF withholding exceeds supported activity rate; "
                    "cash amount may be invoice base without IVA",
                )
            return self
        if (
            self.direction == TransactionDirection.OUTGOING
            and self.category_id in RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING
            and has_rent_irpf_category(self.irpf_category, direction=self.direction)
            and reconstituted > expected
        ):
            return self
        detail = _gross_mismatch_detail(
            direction=self.direction,
            category_id=self.category_id,
            recargo_amount=self.recargo_amount,
            reconstituted=reconstituted,
            expected=expected,
        )
        raise TransactionValidationError(
            "taxable_base + iva_amount + recargo_amount must equal the gross to the cent: "
            f"{self.taxable_base} + {self.iva_amount} + {recargo} = {reconstituted} != {expected}.{detail}",
        )


def _gross_mismatch_detail(
    *,
    direction: TransactionDirection,
    category_id: str | None,
    recargo_amount: Decimal | None,
    reconstituted: Decimal,
    expected: Decimal,
) -> str:
    """Build the operator hint appended to a gross-reconstitution refusal.

    Each branch names the one field that would legitimately explain the gap it
    sees, so the refusal is actionable rather than a bare arithmetic mismatch
    the operator has to decompose. The direction of the gap selects the
    vocabulary: a substrate *above* the cash is the withholding shape, and a
    substrate *below* it is the unrecorded-surcharge shape. Returns the empty
    string when no branch recognises the gap, which leaves the arithmetic to
    speak for itself rather than guessing.
    """
    if reconstituted < expected:
        if recargo_amount is not None:
            return ""
        return (
            " The cash movement is above the declared substrate. If this is a supply to or "
            "from a comerciante minorista under recargo de equivalencia (LIVA art. 161), the "
            "surcharge is part of what was charged: record it with --recargo-amount so the "
            "gross reconstitutes."
        )
    if reconstituted <= expected:
        return ""
    if direction == TransactionDirection.OUTGOING:
        if category_id in RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING:
            return ""
        if category_id in PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING:
            return ""
        return ""
    if direction == TransactionDirection.INCOMING:
        return ""
    return ""


class BucketTransactionRef(BaseModel):
    """A transaction identifier qualified by its owning profile bucket."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    transaction_id: TransactionId

    @field_validator("bucket_id", "transaction_id")
    @classmethod
    def _trim_non_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("bucket transaction reference fields must not be blank")
        return trimmed


def existing_transaction_import_fingerprints(transaction: Transaction) -> frozenset[str]:
    """Return every canonical re-import fingerprint for a stored transaction.

    Imported rows carry their parse-boundary, direction-qualified fingerprint
    verbatim. Older or hand-entered rows may not have that stamp, so their
    current raw payload is projected once with the stored direction as a
    deterministic fallback. Preview diagnostics and the persisting import path
    must use this exact projection: a directionless fallback would incorrectly
    collapse otherwise distinct incoming and outgoing movements.
    """
    fingerprints = {derive_import_fingerprint(transaction.raw, direction=transaction.direction)}
    if transaction.import_fingerprint:
        fingerprints.add(transaction.import_fingerprint)
    return frozenset(fingerprints)


class TransactionCatalogue(BaseModel):
    """Immutable catalogue keyed by ``transaction_id``.

    ``transactions`` is a frozen :class:`types.MappingProxyType` from stable
    transaction id to :class:`Transaction`, built via :meth:`from_transactions`
    or by passing a mapping / iterable to ``model_validate``.
    """

    model_config = _STRICT_FROZEN

    transactions: Mapping[str, Transaction] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_catalogue_input(cls, data: object) -> object:
        """Accept either a bare mapping or an iterable of transactions."""
        if isinstance(data, cls):
            return data
        if _is_object_mapping(data):
            payload = _string_keyed_mapping(data)
            if "transactions" in payload:
                return payload
            return {"transactions": payload}
        if isinstance(data, Iterable) and not isinstance(data, str | bytes):
            transactions: dict[str, Transaction] = {}
            for item in OBJECT_TUPLE_ADAPTER.validate_python(data):
                transaction = item if isinstance(item, Transaction) else Transaction.model_validate(item)
                if transaction.transaction_id in transactions:
                    raise TransactionValidationError(f"duplicate transaction_id: {transaction.transaction_id}")
                transactions[transaction.transaction_id] = transaction
            return {"transactions": transactions}
        return data

    @model_validator(mode="after")
    def _validate_mapping_keys(self) -> Self:
        """Ensure every mapping key matches the embedded transaction ID."""
        for key, transaction in self.transactions.items():
            if key != transaction.transaction_id:
                raise TransactionValidationError(
                    f"catalogue key {key!r} does not match transaction_id {transaction.transaction_id!r}",
                )
        return self

    @field_validator("transactions")
    @classmethod
    def _freeze_transactions(cls, value: Mapping[str, Transaction]) -> Mapping[str, Transaction]:
        """Freeze the catalogue mapping to preserve immutability."""
        return MappingProxyType(dict(value))

    @field_serializer("transactions")
    def _serialize_transactions(self, value: Mapping[str, Transaction]) -> dict[str, Transaction]:
        """Serialize the immutable mapping back to a JSON object."""
        return dict(value)

    @classmethod
    def from_transactions(cls, transactions: Iterable[Transaction | Mapping[str, object]]) -> Self:
        """Build a catalogue from an iterable of transactions.

        Args:
            transactions: Transactions or transaction payloads to load.

        Returns:
            A validated immutable transaction catalogue.
        """
        return cls.model_validate(tuple(transactions))

    @override
    def __iter__(self) -> Iterator[Transaction]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional Pydantic catalogue iteration adapter; the established public API yields Transaction records, not BaseModel field-value tuples
        """Iterate over catalogue transactions."""
        return iter(self.transactions.values())

    def __len__(self) -> int:
        """Return the number of transactions in the catalogue."""
        return len(self.transactions)

    def __contains__(self, transaction_id: object) -> bool:
        """Return whether the catalogue contains ``transaction_id``."""
        if isinstance(transaction_id, Transaction):
            return transaction_id.transaction_id in self.transactions
        if isinstance(transaction_id, str):
            return transaction_id in self.transactions
        return False

    def get(self, transaction_id: str) -> Transaction | None:
        """Fetch one transaction by ID if present.

        Args:
            transaction_id: Stable transaction identifier.

        Returns:
            The matching :class:`Transaction`, or ``None`` when absent.
        """
        return self.transactions.get(transaction_id)

    def values(self) -> Iterator[Transaction]:
        """Iterate over catalogue :class:`Transaction` records."""
        return iter(self.transactions.values())


class OutOfWindowTransactionIndexEntry(BaseModel):
    """A catalogue transaction outside a requested date window, undecrypted.

    Carries ONLY the two plaintext, non-sensitive facts a period-scoped
    aggregator needs to report the transaction as excluded --
    ``transaction_id`` and its ``filing_date`` -- never any decrypted field
    (amount, category, counterparty, direction, business classification).
    This is the period-first partition contract: an out-of-window row is
    diagnosed from the plaintext date-index fact alone, without paying the
    decrypt-and-validate cost, and without leaking anything the index itself
    does not already carry.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    filing_date: date


class OutOfWindowTransactionSummary(BaseModel):
    """Compact diagnostics-only summary for out-of-window catalogue rows.

    Carries only the excluded-row count and the filing-date span covered
    by those rows. It never carries decrypted transaction facts.
    """

    model_config = _STRICT_FROZEN

    count: int = Field(ge=1)
    min_filing_date: date
    max_filing_date: date

    @classmethod
    def from_index_entries(cls, index_entries: Iterable[OutOfWindowTransactionIndexEntry]) -> Self | None:
        """Build a summary from plaintext date-index entries, or ``None`` when empty."""
        materialized = tuple(index_entries)
        if not materialized:
            return None
        filing_dates = tuple(entry.filing_date for entry in materialized)
        return cls(
            count=len(materialized),
            min_filing_date=min(filing_dates),
            max_filing_date=max(filing_dates),
        )

    @model_validator(mode="after")
    def _validate_date_span(self) -> Self:
        if self.max_filing_date < self.min_filing_date:
            raise TransactionValidationError("out-of-window summary date span must be ordered")
        return self


class LedgerDatePartition(BaseModel):
    """A ledger catalogue split into an in-window and an out-of-window half.

    ``in_window`` is a real, fully decrypted :class:`TransactionCatalogue`
    scoped to ``[start, end]`` -- every regulated classifier gate runs over it
    unchanged. ``out_of_window`` is the plaintext-only remainder
    (:class:`OutOfWindowTransactionIndexEntry` rows): transactions the catalogue
    holds outside the window, reported without decryption so a caller can
    still surface a period-exclusion diagnostic for them.

    ``out_of_window_summary`` is the compact diagnostics-channel replacement:
    count plus filing-date span, with no decrypted fields and no row-level
    allocation requirement. During the migration, callers may see either the
    row-level index entries, the summary, or both.

    ``index_complete`` records whether the partition was served from a
    complete plaintext date index (``True``) or from a full-scan fallback
    after a completeness-gate mismatch (``False`` -- see
    ``aeat-ledger-contract``): both cases return
    an identical partition shape, so a caller cannot observe which path
    served it except through this flag and through latency.
    """

    model_config = _STRICT_FROZEN

    in_window: TransactionCatalogue
    out_of_window: tuple[OutOfWindowTransactionIndexEntry, ...] = ()
    out_of_window_summary: OutOfWindowTransactionSummary | None = None
    index_complete: bool
