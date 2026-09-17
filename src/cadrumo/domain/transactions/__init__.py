"""Inert namespace for immutable ledger transactions.

The transaction domain boundary used by :mod:`~application.ledger` is defined
across the owning modules listed below. :class:`~domain.transactions.models.Transaction` wraps an upstream
:class:`~domain.transactions.raw_transaction.RawTransaction` and its
:class:`~domain.transactions.raw_transaction.RawProvenance`, while
:class:`~domain.transactions.models.TransactionCatalogue` keeps the immutable mapping keyed by the
content-derived transaction id. Import helpers such as
:func:`~domain.transactions.models.derive_transaction_id`,
:func:`~domain.transactions.models.derive_import_fingerprint`, and
:func:`~domain.transactions.models.normalise_movement_reference` are the public identity helpers.

The row model separates amount magnitude from
:class:`~domain.transactions.enums.TransactionDirection`; downstream tax calculations route by direction
rather than by signed amounts. It carries classification, tax substrate,
evidence, split, edit, lifecycle, FX, jurisdiction, and timestamp provenance
through typed records such as :class:`~domain.transactions.lineage_models.ClassificationHistoryEntry`,
:class:`~domain.transactions.lineage_models.TransactionEvidenceProvenanceEntry`,
:class:`~domain.transactions.lineage_models.TransactionEditLineageEntry`, and
:class:`~domain.transactions.lineage_models.TransactionLifecycleLineageEntry`. Classification helpers
:func:`~domain.transactions.service.set_classification`,
:func:`~domain.transactions.service.snapshot_classification_state`, and
:func:`~domain.transactions.service.link_invoice` return fresh catalogues instead of mutating callers'
instances.

Persistence is served by the read-side
:class:`~domain.transactions.protocols.TransactionCatalogueRepositoryProtocol` port; the concrete encrypted
implementation lives in the persistence adapter
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
It stores each transaction under the bucket-scoped transaction namespace as
``FINANCIAL`` :class:`~core.classification.policies.SensitivityClass` rows wrapped in
:class:`~adapters.persistence.storage.envelope.contract.Envelope` through
:class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`; callers should
not write plaintext catalogues or reach into private modules. The pure port
surface, key-derivation helpers, and namespace constant are imported from their
defining modules.

LLM-facing :class:`~domain.transactions.llm.LLMClassifier`,
:class:`~domain.transactions.llm.LLMSplitProposer`,
:class:`~domain.transactions.llm.PromptSpec`,
:class:`~domain.transactions.classification_rule.LedgerClassificationRule`, and
:func:`~domain.transactions.irpf_categories.ledger_irpf_category_catalogue` are likewise
imported from their defining modules. They constrain model choices to typed
:class:`~domain.transactions.enums.BusinessClassification`,
:class:`~domain.transactions.llm.CategoryChoice`, and
:class:`~domain.transactions.llm.IvaCategoryChoice` allow-lists; regulated tax
numbers are derived by application services, not originated by this package.

Downstream modelo calculation records keep only forward transaction ids on
:class:`~CalculationRevision`. Aggregation services consume
this catalogue to produce registry binding values and ledger filing snapshots,
while :class:`~TransactionRevisionParticipationIndex`
provides the rebuildable inverse audit lookup from one ledger transaction to
finalized revisions and filing records.

See Also:
    :mod:`~application.ledger`
        Operator-facing lifecycle that creates, edits, classifies, splits,
        attaches evidence, and preflights bucket-scoped transactions.
    :mod:`~application.aggregation`
        Source resolvers that turn transaction catalogues into
        :class:`~application.aggregation.source_mesh.CalculationSourceResolution`
        payloads for modelo calculation.
    :func:`~application.aggregation.ledger_filing_snapshot.compute_ledger_filing_snapshot`
        Captures tax-relevant transaction fields for finalized calculation
        revisions.
    :mod:`~domain.invoices`
        Invoice catalogue and reconciliation records referenced by
        ``invoice_id`` and ``purchase_invoice_evidence_id``.
    :mod:`~domain.usage_ratios`
        Proportionality profiles referenced by ledger rows before aggregation.

Consumers import from the owning module -- :mod:`models`, :mod:`llm`,
:mod:`enums`, :mod:`irpf_categories`, :mod:`retencion_facts`,
:mod:`raw_transaction`, :mod:`repository`, :mod:`service`, :mod:`model_tier`,
:mod:`classification_rule`, :mod:`model_validation`, :mod:`errors` -- rather
than from this package root, which is inert.

The root carried a lazy guard for the persistence port so an importer did not
pay for the repository module. That deferral is now structural: a caller
naming :mod:`repository` asks for it, and one naming :mod:`models` does not.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
