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

Consumers import from the owning module -- :mod:`models`, :mod:`llm`,
:mod:`enums`, :mod:`irpf_categories`, :mod:`retencion_parameters`,
:mod:`raw_transaction`, :mod:`repository`, :mod:`service`, :mod:`model_tier`,
:mod:`classification_rule`, :mod:`model_validation`, :mod:`errors` -- rather
than from this package root, which is inert.

The root carried a lazy guard for the persistence port so an importer did not
pay for the repository module. That deferral is now structural: a caller
naming :mod:`repository` asks for it, and one naming :mod:`models` does not.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
"""Inert namespace: every contract is reached at the module that defines it."""
