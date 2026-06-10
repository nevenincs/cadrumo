"""M036 declaration, reconciliation-history, and IVA-wallet-correction payloads.

Split from :mod:`_modelo_payloads` to keep each module within the line budget.
Each class is a strict :class:`OutputSchema` and is re-exported through
``_modelo_payloads`` so the public ``--json`` payload import surface is unchanged.
"""

from __future__ import annotations

from ...core.identity import BucketId
from ...domain.modelos._ids import WorkUnitId
from ._schemas import OutputSchema, register_schema


@register_schema("modelo.m036.alta")
@register_schema("modelo.m036.modificacion")
@register_schema("modelo.m036.baja")
class M036DeclarationRecordResult(OutputSchema):
    """Envelope payload for the ``aeat app modelo m036 {alta,modificacion,baja}`` verbs.

    All three verbs share a single typed contract: the result is the
    persisted declaration record's content-address + scope + canonical
    fields, as strings (the CLI envelope is JSON-serialisable). The
    domain-side typed record is ``aeat.application.modelo.M036DeclarationResult``.
    """

    declaration_id: str
    bucket_id: BucketId
    profile_id: str
    event_kind: str
    declared_on: str
    sede_justificante: str | None = None
    note: str | None = None
    recorded_at: str


class M036DeclarationRowPayload(OutputSchema):
    """One recorded M036 declaration row surfaced by ``m036 list`` / ``m036 view``.

    Projects the persisted ``aeat.application.modelo.M036DeclarationResult``
    into a JSON-serialisable row, preserving every field (the content-address
    ``declaration_id``, the canonical ``event_kind``, the ``declared_on`` and
    ``recorded_at`` dates, and the optional ``sede_justificante`` / ``note``).
    """

    declaration_id: str
    bucket_id: BucketId
    profile_id: str
    event_kind: str
    declared_on: str
    sede_justificante: str | None = None
    note: str | None = None
    recorded_at: str


@register_schema("modelo.m036.list")
class M036DeclarationListResult(OutputSchema):
    """Listing returned by ``aeat app modelo m036 list``.

    Enumerates the active bucket's recorded M036 declarations. An empty
    ``declarations`` list is the clean "no declarations recorded yet" signal,
    not an error.
    """

    operation: str = "modelo.m036.list"
    bucket_id: BucketId
    declaration_count: int
    declarations: list[M036DeclarationRowPayload]


@register_schema("modelo.m036.view")
class M036DeclarationShowResult(OutputSchema):
    """Detail returned by ``aeat app modelo m036 view``."""

    operation: str = "modelo.m036.view"
    declaration_id: str
    bucket_id: BucketId
    profile_id: str
    event_kind: str
    declared_on: str
    sede_justificante: str | None = None
    note: str | None = None
    recorded_at: str


class ModeloReconciliationHistoryRowPayload(OutputSchema):
    """One past reconciliation row surfaced by ``modelo reconciliation-history``.

    Projects the typed ``aeat.application.modelo.ModeloReconciliationHistoryEntry``
    read back from the ``MODELO_RECONCILED`` bucket event: the event id, the
    reconciled work unit, the evidence source kind and path, the verdict, the
    per-casilla diff count, the actor, and the reconciliation instant.
    """

    event_id: str
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    source_kind: str
    source_path: str
    verdict: str
    diff_count: int
    actor: str
    reconciled_at: str


@register_schema("modelo.reconciliation_history")
class ModeloReconciliationHistoryResult(OutputSchema):
    """Listing returned by ``aeat app modelo reconciliation-history``.

    Enumerates the active bucket's recorded reconciliations (optionally narrowed
    to one work unit). An empty ``reconciliations`` list is the clean "no
    reconciliations recorded yet" signal, not an error.
    """

    operation: str = "modelo.reconciliation_history"
    bucket_id: BucketId
    work_unit_id: WorkUnitId | None = None
    reconciliation_count: int
    reconciliations: list[ModeloReconciliationHistoryRowPayload]


@register_schema("modelo.iva_wallet.correct")
class IvaWalletCorrectResult(OutputSchema):
    """Confirmation returned by ``aeat app modelo iva-wallet correct``.

    Surfaces the corrected period, the taxpayer, the new opening
    carry-forward amount, the prior amount it replaced, the seeded ``status``,
    and the operator reason recorded into the audit event.
    """

    operation: str = "modelo.iva_wallet.correct"
    filing_year: int
    period: str
    taxpayer_nif: str
    previous_amount: str
    amount: str
    status: str
    reason: str
