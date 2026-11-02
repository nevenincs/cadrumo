"""Typed ``--json`` payload schemas for ledger participation and tracking commands.

Split from :mod:`ledger_results` along the audit-trail seam: the finalized
revision participation rows, the participation index rebuild summary, and the
``ledger track`` envelope with its evidence, edit and lifecycle lineage
entries. Each class is a strict :class:`OutputSchema` subclass referenced as a
deferred public schema target by the ledger command specs.
"""

from __future__ import annotations

from pydantic import PositiveInt

from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.identity.transaction_ids import TransactionId
from ...core.json_contract import OutputSchema
from ...core.period import Period
from ...core.text_bounds import NonEmptyStr
from .ledger_results import TransactionPayload


class LedgerTransactionParticipationEntryPayload(OutputSchema):
    """One finalized-revision participation recorded against a ledger transaction.

    Surfaces the inverse of the forward ``source_transaction_ids`` link:
    a finalized modelo revision (and, where filed, its filing record and
    justificante reference) that consumed the transaction.  The row mirrors
    :class:`TransactionRevisionParticipation`, which lives
    in the derived, rebuildable participation index rather than on the
    content-addressed transaction itself.
    """

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    modelo: str
    filing_year: int
    period: Period
    revision_state: str
    filing_record_id: FilingRecordId | None = None
    justificante_reference: str | None = None


class LedgerTransactionParticipationPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger participation <transaction-id>``.

    Carries the full
    :class:`TransactionRevisionParticipationIndex` read for
    one ledger transaction: every finalized modelo revision and filing that
    consumed it.  An empty ``participations`` list is the auditable "not used in
    any finalized declaration" answer, not a lookup failure.
    """

    transaction_id: TransactionId
    participations: list[LedgerTransactionParticipationEntryPayload]


class LedgerParticipationRebuildResult(OutputSchema):
    """JSON envelope for ``aeat app ledger participation rebuild``.

    Reports the outcome of
    :func:`rebuild_participation_index`, which
    regenerates the derived participation index from the authoritative finalized
    calculation-revision catalogue.  The result is a repair summary for the
    read-side cache, not a mutation of ledger transactions.

    ``stale_removed_count`` reports the participation objects pruned because the
    regenerated catalogue no longer records them; a non-zero value means the
    cache had been surfacing revisions the authoritative catalogue had dropped.
    """

    transaction_count: int
    participation_count: int
    revision_count: int
    stale_removed_count: int


class LedgerTrackingProvenancePayload(OutputSchema):
    """One evidence-link lineage entry nested in ``ledger track``.

    Mirrors
    :class:`TransactionEvidenceProvenanceEntry`'s JSON
    dump; ``linked_at`` is the ISO-8601 timestamp.
    """

    evidence_id: str
    evidence_kind: str
    actor: str
    source_command: str
    linked_at: str
    bucket_event_id: str | None = None


class LedgerTrackingEditPayload(OutputSchema):
    """One manual-correction lineage entry nested in ``ledger track``.

    Mirrors :class:`TransactionEditLineageEntry`'s
    JSON dump; ``edited_at`` is the ISO-8601 timestamp.
    """

    previous_transaction_id: TransactionId
    actor: str
    source_command: str
    edited_at: str
    bucket_event_id: str | None = None


class LedgerTrackingLifecyclePayload(OutputSchema):
    """One lifecycle-transition lineage entry nested in ``ledger track``.

    Mirrors
    :class:`TransactionLifecycleLineageEntry`'s JSON
    dump; ``changed_at`` is the ISO-8601 timestamp.
    """

    previous_state: str
    state: str
    actor: str
    source_command: str
    changed_at: str
    reason: str = ""
    bucket_event_id: str | None = None


class LedgerTrackingPayload(OutputSchema):
    """Durable event-lineage projection for one transaction.

    Mirrors
    :class:`LedgerTransactionTrackingPayload`'s JSON
    dump — replaces the former bare ``dict[str, object]`` ``tracking`` field on
    :class:`LedgerTrackResult`.
    """

    transaction_id: TransactionId
    created_event_id: str | None = None
    evidence_provenance: list[LedgerTrackingProvenancePayload] = []
    edit_lineage: list[LedgerTrackingEditPayload] = []
    lifecycle_state: str
    lifecycle_lineage: list[LedgerTrackingLifecyclePayload] = []


class LedgerTrackResult(OutputSchema):
    """JSON envelope for ``aeat app ledger track``.

    ``participated_in`` carries the finalized-revision participations that
    consumed this transaction (the inverse audit trail), or ``None`` when the
    transaction appears in no finalized revision.  The field is read from
    :class:`TransactionRevisionParticipationIndex` and
    complements the transaction's own evidence/edit/lifecycle lineage.
    """

    bucket_id: BucketId
    transaction: TransactionPayload
    tracking: LedgerTrackingPayload
    source_filename: NonEmptyStr | None = None
    source_row_index: PositiveInt | None = None
    participated_in: list[LedgerTransactionParticipationEntryPayload] | None = None
