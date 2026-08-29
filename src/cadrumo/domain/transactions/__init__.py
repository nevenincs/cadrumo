"""Public facade for immutable ledger transactions.

This package re-exports the transaction domain boundary used by
:mod:`~application.ledger`: :class:`~domain.transactions.Transaction` wraps an upstream
:class:`~domain.transactions.RawTransaction` and its :class:`~domain.transactions.RawProvenance`, while
:class:`~domain.transactions.TransactionCatalogue` keeps the immutable mapping keyed by the
content-derived transaction id. Import helpers such as
:func:`~domain.transactions.derive_transaction_id`,
:func:`~domain.transactions.derive_import_fingerprint`, and
:func:`~domain.transactions.normalise_movement_reference` are the public identity helpers.

The row model separates amount magnitude from
:class:`~domain.transactions.TransactionDirection`; downstream tax calculations route by direction
rather than by signed amounts. It carries classification, tax substrate,
evidence, split, edit, lifecycle, FX, jurisdiction, and timestamp provenance
through typed records such as :class:`~domain.transactions.ClassificationHistoryEntry`,
:class:`~domain.transactions.TransactionEvidenceProvenanceEntry`,
:class:`~domain.transactions.TransactionEditLineageEntry`, and
:class:`~domain.transactions.TransactionLifecycleLineageEntry`. Classification helpers
:func:`~domain.transactions.set_classification`,
:func:`~domain.transactions.snapshot_classification_state`, and
:func:`~domain.transactions.link_invoice` return fresh catalogues instead of mutating callers'
instances.

Persistence is served by the read-side
:class:`~domain.transactions.TransactionCatalogueRepositoryProtocol` port; the concrete encrypted
implementation lives in the persistence adapter
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
It stores each transaction under the bucket-scoped transaction namespace as
``FINANCIAL`` :class:`~core.classification.SensitivityClass` rows wrapped in
:class:`~adapters.persistence.storage.Envelope` through
:class:`~adapters.persistence.storage.SecureObjectRepository`; callers should
not write plaintext catalogues or reach into private modules. The pure port
surface (:class:`~domain.transactions.ImportSummary`, the key-derivation helpers, and the namespace
constant) remains exposed lazily here.

LLM-facing :class:`~domain.transactions.LLMClassifier`,
:class:`~domain.transactions.LLMSplitProposer`,
:class:`~domain.transactions.PromptSpec`,
:class:`~domain.transactions.LedgerClassificationRule`, and
:func:`~domain.transactions.ledger_irpf_category_catalogue` also live behind
this facade. They constrain model choices to typed
:class:`~domain.transactions.BusinessClassification`,
:class:`~domain.transactions.CategoryChoice`, and
:class:`~domain.transactions.IvaCategoryChoice` allow-lists; regulated tax
numbers are derived by application services, not originated by this package.

Downstream modelo calculation records keep only forward transaction ids on
:class:`~domain.modelos.CalculationRevision`. Aggregation services consume
this catalogue to produce registry binding values and ledger filing snapshots,
while :class:`~domain.modelos.TransactionRevisionParticipationIndex`
provides the rebuildable inverse audit lookup from one ledger transaction to
finalized revisions and filing records.

See Also:
    :mod:`~application.ledger`
        Operator-facing lifecycle that creates, edits, classifies, splits,
        attaches evidence, and preflights bucket-scoped transactions.
    :mod:`~application.aggregation`
        Source resolvers that turn transaction catalogues into
        :class:`~application.aggregation.CalculationSourceResolution`
        payloads for modelo calculation.
    :func:`~application.aggregation._ledger_filing_snapshot.compute_ledger_filing_snapshot`
        Captures tax-relevant transaction fields for finalized calculation
        revisions.
    :mod:`~domain.invoices`
        Invoice catalogue and reconciliation records referenced by
        ``invoice_id`` and ``purchase_invoice_evidence_id``.
    :mod:`~domain.usage_ratios`
        Proportionality profiles referenced by ledger rows before aggregation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .classification_rule import LedgerClassificationRule
from ._dates import transaction_eligible_date_span, transaction_filing_date
from ._enums import (
    BUSINESS_BEARING_STATES,
    CLASSIFIED_STATES,
    BusinessClassification,
    SplitRole,
    TransactionDirection,
    TransactionLifecycleState,
    is_classified,
)
from ._irpf_categories import (
    IRPF_CATEGORY_ACTIVIDAD_ECONOMICA,
    IRPF_CATEGORY_TRABAJO,
    PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING,
    RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING,
    RENT_IRPF_CATEGORIES_PAID_NET_OF_WITHHOLDING,
    LedgerIrpfCategoryDescriptor,
    has_activity_irpf_category,
    has_employment_irpf_category,
    ledger_irpf_category_catalogue,
    normalize_irpf_category,
)
from ._llm import (
    MINIMUM_CLASSIFICATION_TIER,
    PIPELINE_ONLY_CLASSIFICATIONS,
    CategoryChoice,
    ClassificationChoice,
    IvaCategoryChoice,
    LLMClassificationResponse,
    LLMClassifier,
    LLMClassifierError,
    LLMSplitChild,
    LLMSplitProposer,
    LLMSplitResponse,
    ModelProfile,
    ModelTier,
    PromptSpec,
    build_split_prompt,
    default_classification_choices,
    default_iva_category_choices,
    default_prompt_spec,
    parse_response,
    parse_split_response,
    prompt_spec_with_every_spending_category,
    prompt_spec_with_saturation_fields,
)
from ._m210_income_classification import M210IncomeClassification
from ._model_tier import ModelCapability, catalogue, profiles_for_provider, resolve_profile
from ._models import (
    BucketTransactionRef,
    ClassificationHistoryEntry,
    DecisionProvenance,
    IvaCashAccountingPaymentEvidence,
    IvaCashAccountingTreatment,
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    SplitLineage,
    Transaction,
    TransactionCatalogue,
    TransactionEditLineageEntry,
    TransactionEvidenceProvenanceEntry,
    TransactionLifecycleLineageEntry,
    derive_import_fingerprint,
    derive_movement_day_key,
    derive_split_group_id,
    derive_transaction_id,
    existing_transaction_import_fingerprints,
    normalise_movement_reference,
)
from ._protocols import (
    TransactionCatalogueRepositoryProtocol,
)
from ._raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ._retencion_parameters import (
    AdministradorRetencionRates,
    RirpfArt95RetencionRates,
    administrador_retencion_legal_refs,
    load_administrador_retencion_rates,
    load_retencion_actividades_rates,
    maximum_supported_activity_retencion_rate,
    professional_activity_retencion_rates,
    rirpf_art95_retencion_legal_refs,
    sectoral_activity_retencion_rates,
    statutory_activity_retencion_rates,
)
from ._service import (
    find_transaction,
    link_invoice,
    set_classification,
    snapshot_classification_state,
)
from ._tipo_actividad_partitions import (
    irpf_activity_kind_for,
    load_tipo_actividad_selectors,
    tipo_actividad_code_set,
)
from ._volumen_ingresos import (
    counts_toward_art_109_activity_income,
    counts_toward_volumen_de_ingresos,
)
from .errors import (
    LedgerNoActiveBucketError,
    LedgerStorageError,
    StoredTransactionDriftError,
    TransactionCatalogueError,
    TransactionError,
    TransactionIdPrefixError,
    TransactionNotFoundError,
    TransactionPersistenceError,
    TransactionValidationError,
)

if TYPE_CHECKING:
    from ._repository import (
        ImportSummary,
        transaction_index_object_key,
        transaction_object_key,
    )


_LAZY_REPOSITORY_NAMES = frozenset(
    {
        "ImportSummary",
        "transaction_index_object_key",
        "transaction_object_key",
    },
)


def __getattr__(name: str):
    """Lazy-import the pure persistence surface to defer the ``_repository`` module load.

    The concrete :class:`TransactionCatalogueRepository` now lives in the
    persistence adapter
    :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`;
    only the pure port surface (``ImportSummary`` and the key-derivation
    helpers) is resolved here.
    """
    if name in _LAZY_REPOSITORY_NAMES:
        from . import _repository

        return getattr(_repository, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BUSINESS_BEARING_STATES",
    "CLASSIFIED_STATES",
    "IRPF_CATEGORY_ACTIVIDAD_ECONOMICA",
    "IRPF_CATEGORY_TRABAJO",
    "MINIMUM_CLASSIFICATION_TIER",
    "PIPELINE_ONLY_CLASSIFICATIONS",
    "PROFESSIONAL_SERVICE_CATEGORIES_PAID_NET_OF_WITHHOLDING",
    "RENT_CATEGORIES_PAID_NET_OF_WITHHOLDING",
    "RENT_IRPF_CATEGORIES_PAID_NET_OF_WITHHOLDING",
    "AdministradorRetencionRates",
    "BucketTransactionRef",
    "BusinessClassification",
    "CategoryChoice",
    "ClassificationChoice",
    "ClassificationHistoryEntry",
    "DecisionProvenance",
    "ImportSummary",
    "IvaCashAccountingPaymentEvidence",
    "IvaCashAccountingTreatment",
    "IvaCategoryChoice",
    "LLMClassificationResponse",
    "LLMClassifier",
    "LLMClassifierError",
    "LLMSplitChild",
    "LLMSplitProposer",
    "LLMSplitResponse",
    "LedgerClassificationRule",
    "LedgerDatePartition",
    "LedgerIrpfCategoryDescriptor",
    "LedgerNoActiveBucketError",
    "LedgerStorageError",
    "M210IncomeClassification",
    "ModelCapability",
    "ModelProfile",
    "ModelTier",
    "OutOfWindowTransactionIndexEntry",
    "OutOfWindowTransactionSummary",
    "PromptSpec",
    "RawProvenance",
    "RawTransaction",
    "RirpfArt95RetencionRates",
    "SourceFormat",
    "SplitLineage",
    "SplitRole",
    "StoredTransactionDriftError",
    "Transaction",
    "TransactionCatalogue",
    "TransactionCatalogueError",
    "TransactionCatalogueRepositoryProtocol",
    "TransactionDirection",
    "TransactionEditLineageEntry",
    "TransactionError",
    "TransactionEvidenceProvenanceEntry",
    "TransactionIdPrefixError",
    "TransactionLifecycleLineageEntry",
    "TransactionLifecycleState",
    "TransactionNotFoundError",
    "TransactionPersistenceError",
    "TransactionValidationError",
    "administrador_retencion_legal_refs",
    "build_split_prompt",
    "catalogue",
    "counts_toward_art_109_activity_income",
    "counts_toward_volumen_de_ingresos",
    "default_classification_choices",
    "default_iva_category_choices",
    "default_prompt_spec",
    "derive_import_fingerprint",
    "derive_movement_day_key",
    "derive_split_group_id",
    "derive_transaction_id",
    "existing_transaction_import_fingerprints",
    "find_transaction",
    "has_activity_irpf_category",
    "has_employment_irpf_category",
    "irpf_activity_kind_for",
    "is_classified",
    "ledger_irpf_category_catalogue",
    "link_invoice",
    "load_administrador_retencion_rates",
    "load_retencion_actividades_rates",
    "load_tipo_actividad_selectors",
    "maximum_supported_activity_retencion_rate",
    "normalise_movement_reference",
    "normalize_irpf_category",
    "parse_response",
    "parse_split_response",
    "professional_activity_retencion_rates",
    "profiles_for_provider",
    "prompt_spec_with_every_spending_category",
    "prompt_spec_with_saturation_fields",
    "resolve_profile",
    "rirpf_art95_retencion_legal_refs",
    "sectoral_activity_retencion_rates",
    "set_classification",
    "snapshot_classification_state",
    "statutory_activity_retencion_rates",
    "tipo_actividad_code_set",
    "transaction_eligible_date_span",
    "transaction_filing_date",
    "transaction_index_object_key",
    "transaction_object_key",
]
