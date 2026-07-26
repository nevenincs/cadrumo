"""M036 declaration, reconcile-history, and IVA-wallet-correction payloads.

Split from :mod:`_modelo_payloads` to keep each module
within the line budget. Each class is a strict
:class:`OutputSchema` subclass registered through
:func:`register_schema` and re-exported through
:mod:`_modelo_payloads` so the public ``--json``
payload import surface is
unchanged. Validated results enter
:class:`SchemaEnvelope` through
:func:`_emit_envelope`.

The application modelo facade remains authoritative for
:class:`M036DeclarationResult`,
:class:`ModeloReconciliationHistoryEntry`, and
:func:`correct_iva_compensation_period_for_bucket`;
this module only documents their CLI transport projections.
"""

from __future__ import annotations

from ...core import Period
from ...core.identity import BucketId
from ...domain.modelos import WorkUnitId
from ._schemas import OutputSchema, register_schema


@register_schema("modelo.m036.alta")
@register_schema("modelo.m036.modificacion")
@register_schema("modelo.m036.baja")
class M036DeclarationRecordResult(OutputSchema):
    """Envelope payload for the ``aeat app modelo m036 {alta,modificacion,baja}`` verbs.

    All three verbs share a single typed contract: the result is the
    persisted declaration record's content-address + scope + canonical
    fields, as strings (the CLI envelope is JSON-serialisable). The
    application-side typed record is
    :class:`M036DeclarationResult`, scoped by the emitted :obj:`BucketId`.
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

    Projects the persisted
    :class:`M036DeclarationResult`
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

    Enumerates the active :obj:`BucketId` bucket's recorded M036 declarations.
    An empty ``declarations`` list is the clean "no declarations recorded yet"
    signal, not an error.
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
    """One past reconciliation row surfaced by ``modelo reconcile history``.

    Projects the typed
    :class:`ModeloReconciliationHistoryEntry`
    read back from the encrypted reconciliation-record store: the id of the
    ``MODELO_RECONCILED`` bucket event co-written with that record, the
    reconciled :obj:`WorkUnitId`, the evidence source kind and path, the
    verdict, the per-casilla diff count, the actor, and the reconciliation
    instant.
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


@register_schema("modelo.reconcile.history")
class ModeloReconciliationHistoryResult(OutputSchema):
    """Listing returned by ``aeat app modelo reconcile history``.

    Enumerates the active bucket's recorded reconciliations (optionally narrowed
    to one :obj:`WorkUnitId`). An empty ``reconciliations`` list is the clean "no
    reconciliations recorded yet" signal, not an error.
    """

    operation: str = "modelo.reconcile.history"
    bucket_id: BucketId
    work_unit_id: WorkUnitId | None = None
    reconciliation_count: int
    reconciliations: list[ModeloReconciliationHistoryRowPayload]


@register_schema("modelo.iva_wallet.correct")
class IvaWalletCorrectResult(OutputSchema):
    """Confirmation returned by ``aeat app modelo iva-wallet correct``.

    Surfaces the corrected :class:`Period`, the taxpayer, the new opening
    carry-forward amount, the prior amount it replaced, the seeded ``status``,
    and the operator reason recorded into the audit event.

    The mutation itself is owned by
    :func:`correct_iva_compensation_period_for_bucket`,
    which returns the corrected
    :class:`IvaCompensationPeriodState` and emits
    the ``MODELO_IVA_WALLET_CORRECTED`` audit event.
    """

    operation: str = "modelo.iva_wallet.correct"
    filing_year: int
    period: Period
    taxpayer_nif: str
    previous_amount: str
    amount: str
    status: str
    reason: str
