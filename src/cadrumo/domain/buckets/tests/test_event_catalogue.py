"""Direct domain tests for ``BucketEventHistoryCatalogue`` invariants.

The catalogue is a frozen, strict pydantic record keyed by event id.
These tests exercise the strict-invariant boundary directly: payload
keys must equal each event's content-addressed id, ``for_bucket`` and
``for_object`` return chronologically-ordered slices, the catalogue is
immutable, and re-construction with a mismatched key raises a typed
error.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from .._event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_BUCKET_A = "5612ee74-f4e5-47c2-9df9-2afa04286b2a"  # was 'operator-a'
_BUCKET_B = "8a08e144-26e5-4275-b75f-42e07d2458e0"  # was 'operator-b'
_T0 = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 4, 1, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)


def _build_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    object_type: BucketEventObjectType,
    object_id: str,
    actor: str = "operator",
    payload: dict[str, str] | None = None,
) -> BucketEvent:
    canonical_payload = payload or {}
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload=canonical_payload,
    )
    return BucketEvent(
        event_id=event_id,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload_version=1,
        payload=canonical_payload,
    )


def test_empty_catalogue_is_constructible_and_iterates_to_nothing() -> None:
    catalogue = BucketEventHistoryCatalogue()
    assert len(catalogue) == 0
    assert tuple(catalogue) == ()
    assert catalogue.for_bucket(_BUCKET_A) == ()
    assert catalogue.for_object(object_type=BucketEventObjectType.WORK_UNIT, object_id="anything") == ()


def test_catalogue_rejects_key_that_does_not_match_event_id() -> None:
    event = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-1",
    )
    bogus_key = "0" * 64
    with pytest.raises(ValidationError) as raised:
        BucketEventHistoryCatalogue(events={bogus_key: event})

    # The refusal names both sides as machine facts rather than a sentence, so
    # the assertion pins the mismatch itself and not a phrase a translation or
    # a reword would break.
    cause = raised.value.errors()[0]["ctx"]["error"]
    assert cause.context == {
        "catalogue_key": bogus_key,
        "event_id": event.event_id,
        "catalogue_key_matches_event_id": False,
    }
    assert str(cause) == cause.translated_message, f"the raise site carries an authored sentence: {str(cause)!r}"


def test_catalogue_for_bucket_returns_chronological_order() -> None:
    later = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_FILED,
        occurred_at=_T2,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id="fr-2",
    )
    earlier = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-1",
    )
    middle = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_VERIFICATION_PASSED,
        occurred_at=_T1,
        object_type=BucketEventObjectType.VERIFICATION_REPORT,
        object_id="vr-1",
    )

    catalogue = BucketEventHistoryCatalogue(
        events={
            later.event_id: later,
            earlier.event_id: earlier,
            middle.event_id: middle,
        },
    )
    rows = catalogue.for_bucket(_BUCKET_A)
    assert tuple(e.occurred_at for e in rows) == (_T0, _T1, _T2)


def test_catalogue_for_bucket_isolates_buckets() -> None:
    a_event = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-a",
    )
    b_event = _build_event(
        bucket_id=_BUCKET_B,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-b",
    )
    catalogue = BucketEventHistoryCatalogue(events={a_event.event_id: a_event, b_event.event_id: b_event})
    assert tuple(e.event_id for e in catalogue.for_bucket(_BUCKET_A)) == (a_event.event_id,)
    assert tuple(e.event_id for e in catalogue.for_bucket(_BUCKET_B)) == (b_event.event_id,)


def test_catalogue_for_bucket_filters_by_event_types() -> None:
    calc = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-1",
    )
    filed = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_FILED,
        occurred_at=_T1,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id="fr-1",
    )
    catalogue = BucketEventHistoryCatalogue(events={calc.event_id: calc, filed.event_id: filed})
    rows = catalogue.for_bucket(_BUCKET_A, event_types=(BucketEventType.MODELO_FILED,))
    assert tuple(e.event_id for e in rows) == (filed.event_id,)


def test_ledger_event_catalogue_uses_approved_transaction_vocabulary() -> None:
    assert BucketEventType.LEDGER_TRANSACTION_CREATED.value == "ledger.transaction.created"
    assert BucketEventType.LEDGER_TRANSACTION_IMPORTED.value == "ledger.transaction.imported"
    assert BucketEventType.LEDGER_IMPORT_DIAGNOSTIC_RECORDED.value == "ledger.import.diagnostic_recorded"
    assert BucketEventType.LEDGER_TRANSACTION_UPDATED.value == "ledger.transaction.updated"
    assert BucketEventType.LEDGER_TRANSACTION_CLASSIFIED.value == "ledger.transaction.classified"
    assert (
        BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED.value == "ledger.transaction.llm_suggestion.rejected"
    )
    assert BucketEventType.LEDGER_TRANSACTION_ALLOCATED.value == "ledger.transaction.allocated"
    assert BucketEventType.LEDGER_TRANSACTION_REMOVED.value == "ledger.transaction.removed"
    assert BucketEventType.LEDGER_TRANSACTION_ARCHIVED.value == "ledger.transaction.archived"
    assert BucketEventType.LEDGER_TRANSACTION_STASHED.value == "ledger.transaction.stashed"
    assert BucketEventType.LEDGER_TRANSACTION_EXPORTED.value == "ledger.transaction.exported"
    assert BucketEventType.LEDGER_TRANSACTION_SPLIT.value == "ledger.transaction.split"
    assert BucketEventType.LEDGER_TRANSACTION_MERGED.value == "ledger.transaction.merged"
    assert BucketEventType.LEDGER_CATALOGUE_RESET.value == "ledger.catalogue.reset"
    assert BucketEventType.LEDGER_SANITIZATION_COMPLETED.value == "ledger.sanitization.completed"
    assert BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED.value == "purchase_invoice_evidence.attached"
    assert BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED.value == "purchase_invoice_evidence.replaced"
    assert BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED.value == "purchase_invoice_evidence.detached"
    assert BucketEventType.ATTACHMENT_LINKED.value == "attachment.linked"
    assert BucketEventType.ATTACHMENT_REMOVED.value == "attachment.removed"


def test_reverse_merge_correction_events_match_taxonomy_contract() -> None:
    """The six correction events match the google-oauth taxonomy contract schema."""

    assert BucketEventType.LEDGER_TRANSACTION_CORRECTION_APPLIED.value == "ledger.transaction.correction.applied"
    assert (
        BucketEventType.LEDGER_PURCHASE_INVOICE_EVIDENCE_CORRECTION_APPLIED.value
        == "ledger.purchase_invoice_evidence.correction.applied"
    )
    assert (
        BucketEventType.LEDGER_PAYABLE_INVOICE_CORRECTION_APPLIED.value == "ledger.payable_invoice.correction.applied"
    )
    assert (
        BucketEventType.LEDGER_COLLECTIBLE_INVOICE_CORRECTION_APPLIED.value
        == "ledger.collectible_invoice.correction.applied"
    )
    assert BucketEventType.LEDGER_RENTAL_INCOME_CORRECTION_APPLIED.value == "ledger.rental_income.correction.applied"
    assert BucketEventType.LEDGER_RENTAL_EXPENSE_CORRECTION_APPLIED.value == "ledger.rental_expense.correction.applied"


def test_ledger_event_catalogue_rejects_legacy_underscore_transaction_events() -> None:
    legacy_values = (
        "ledger_transaction.created",
        "ledger_transaction.imported",
        "ledger_transaction.updated",
        "ledger_transaction.classified",
        "ledger_transaction.allocated",
        "ledger_transaction.removed",
        "ledger_transaction.archived",
        "ledger_transaction.stashed",
        "ledger_transaction.exported",
    )

    for legacy_value in legacy_values:
        with pytest.raises(ValueError, match=legacy_value.replace(".", r"\.")):
            BucketEventType(legacy_value)


def test_ledger_event_object_types_cover_mutation_targets() -> None:
    assert BucketEventObjectType.LEDGER_TRANSACTION.value == "ledger_transaction"
    assert BucketEventObjectType.LEDGER_IMPORT_BATCH.value == "ledger_import_batch"
    assert BucketEventObjectType.LEDGER_CATALOGUE.value == "ledger_catalogue"
    assert BucketEventObjectType.LEDGER_EXPORT.value == "ledger_export"
    assert BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE.value == "purchase_invoice_evidence"
    assert BucketEventObjectType.PAYABLE_INVOICE.value == "payable_invoice"
    assert BucketEventObjectType.COLLECTIBLE_INVOICE.value == "collectible_invoice"
    assert BucketEventObjectType.ATTACHMENT.value == "attachment"


def test_catalogue_filters_ledger_events_by_approved_event_type() -> None:
    created = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.LEDGER_TRANSACTION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.LEDGER_TRANSACTION,
        object_id="tx-1",
    )
    removed = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.LEDGER_TRANSACTION_REMOVED,
        occurred_at=_T1,
        object_type=BucketEventObjectType.LEDGER_TRANSACTION,
        object_id="tx-1",
        payload={"reason": "wrong import"},
    )
    evidence_detached = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
        occurred_at=_T2,
        object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
        object_id="evidence-1",
        payload={"transaction_id": "tx-1"},
    )
    catalogue = BucketEventHistoryCatalogue(
        events={
            created.event_id: created,
            removed.event_id: removed,
            evidence_detached.event_id: evidence_detached,
        },
    )

    rows = catalogue.for_bucket(_BUCKET_A, event_types=(BucketEventType.LEDGER_TRANSACTION_REMOVED,))
    assert tuple(event.event_id for event in rows) == (removed.event_id,)


def test_catalogue_for_object_returns_events_for_one_object() -> None:
    fr_created = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_FILED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id="fr-1",
    )
    other_fr = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_FILED,
        occurred_at=_T1,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id="fr-2",
    )
    fr_amended = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_AMENDED,
        occurred_at=_T2,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id="fr-1",
        payload={"amends": "true"},
    )
    catalogue = BucketEventHistoryCatalogue(
        events={
            fr_created.event_id: fr_created,
            other_fr.event_id: other_fr,
            fr_amended.event_id: fr_amended,
        },
    )
    rows = catalogue.for_object(object_type=BucketEventObjectType.FILING_RECORD, object_id="fr-1")
    assert tuple(e.event_id for e in rows) == (fr_created.event_id, fr_amended.event_id)


def test_catalogue_get_returns_event_by_id_or_none() -> None:
    event = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-1",
    )
    catalogue = BucketEventHistoryCatalogue(events={event.event_id: event})
    assert catalogue.get(event.event_id) is event
    assert catalogue.get("0" * 64) is None


def test_catalogue_is_frozen_and_extra_forbid() -> None:
    catalogue = BucketEventHistoryCatalogue()
    with pytest.raises(ValidationError, match="frozen"):
        catalogue.events = MappingProxyType({})

    event = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-1",
    )
    with pytest.raises(ValidationError, match=r"extra_forbidden|Extra inputs"):
        BucketEventHistoryCatalogue.model_validate({"events": {event.event_id: event}, "extra": "no"})


def test_bucket_event_type_includes_workspace_bootstrap_kinds() -> None:
    """Workspace bootstrap and operator-auth lifecycle have dedicated
    canonical event-type slots so emitters at the application layer
    can route through the bucket-event-history catalogue. Pinning these
    enum members keeps the bootstrap surface from regressing into
    free-string actions."""

    from .._event import BucketEventType

    assert BucketEventType.AUTH_PROVIDER_CONFIGURED.value == "auth.provider.configured"
    assert BucketEventType.CONFIG_ENV_UPDATED.value == "config.env.updated"


def test_bucket_event_type_includes_profile_lifecycle_extensions() -> None:
    """Profile export / import / activation have dedicated canonical
    enum slots distinct from PROFILE_SELECTED so callers can record
    archive-aware lifecycle transitions in the bucket-event-history
    catalogue."""

    from .._event import BucketEventType

    assert BucketEventType.PROFILE_EXPORTED.value == "profile.exported"
    assert BucketEventType.PROFILE_IMPORTED.value == "profile.imported"
    assert BucketEventType.PROFILE_ACTIVATED.value == "profile.activated"


def test_bucket_event_type_includes_bucket_maintenance_kinds() -> None:
    """Bucket maintenance verbs (export / import / rename / delete)
    operate on the container itself rather than its contents and
    have dedicated canonical enum slots so the maintenance audit
    trail does not collide with content-mutation events."""

    from .._event import BucketEventType

    assert BucketEventType.BUCKET_EXPORTED.value == "bucket.exported"
    assert BucketEventType.BUCKET_IMPORTED.value == "bucket.imported"
    assert BucketEventType.BUCKET_RENAMED.value == "bucket.renamed"
    assert BucketEventType.BUCKET_DELETED.value == "bucket.deleted"


def test_bucket_event_type_includes_censo_declaration_kinds() -> None:
    """Modelo 036 declarative-recording verbs (operator declares an
    alta / modificacion / baja was filed at sede) have dedicated
    canonical enum slots distinct from the ``profile.censo.applied``
    cotejo mirror event. Per the 2026-05-16 workflow
    redesign contract for cli-workflow-redesign-modelo-036-037-foundation,
    the local app never files a 036; these events record the
    operator's declaration so downstream profile state and
    stale-cascade logic can react.

    Authority: m036 workflow lifecycle contract and CLI workflow redesign
    contract.
    """

    from .._event import BucketEventType

    assert BucketEventType.CENSO_DECLARATION_ALTA.value == "modelo.036.declaration.alta"
    assert BucketEventType.CENSO_DECLARATION_MODIFICACION.value == "modelo.036.declaration.modificacion"
    assert BucketEventType.CENSO_DECLARATION_BAJA.value == "modelo.036.declaration.baja"


def test_bucket_event_object_type_includes_bucket_container() -> None:
    """``BucketEventObjectType`` carries a ``BUCKET`` value so the four
    bucket-maintenance events (``BUCKET_EXPORTED`` / ``BUCKET_IMPORTED``
    / ``BUCKET_RENAMED`` / ``BUCKET_DELETED``) can reference the
    container itself as their ``object_type``. Reusing the ``PROFILE``
    value would conflate the operator's verb invocation on the bucket
    with the lifecycle change on the encrypted profile record, blurring
    the audit-trail distinction the maintenance events exist to make.

    Authority: cli-workflow redesign composition-pattern preconditions
    and the 2026-05-12 cli-workflow bucket contract.
    """

    from .._event import BucketEventObjectType

    assert BucketEventObjectType.BUCKET.value == "bucket"


def test_bucket_event_type_includes_ledger_ratios_mutation_kinds() -> None:
    """Usage-ratio set / unset mutations have canonical enum slots
    so the ratios CLI handlers can route emissions through the
    bucket-event-history catalogue rather than skipping the audit
    trail entirely."""

    from .._event import BucketEventType

    assert BucketEventType.LEDGER_RATIOS_SET.value == "ledger.ratios.set"
    assert BucketEventType.LEDGER_RATIOS_UNSET.value == "ledger.ratios.unset"
    assert BucketEventType.LEDGER_RATIOS_CENSO_OVERRIDE_WARNING.value == "ledger.ratios.censo_override_warning"
