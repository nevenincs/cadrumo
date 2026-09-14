"""Encrypted-boundary coverage for the remembered IVA identification axis.

The application ledger tests keep the counterparty policy on an inward fake.
This test owns the concrete profile repository and proves that a persisted
identification cannot disappear or silently default on reload.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.counterparty_establishment import CounterpartyEstablishmentRepository
from cadrumo.adapters.persistence.storage.secure_object_namespaces import LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.counterparty_establishment import (
    ConfirmedCounterpartyFacts,
    record_confirmed_counterparty_facts,
)
from cadrumo.application.ledger.counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.domain.iva.classification import IvaTerritorialScope
from cadrumo.domain.iva.schema import EUMemberState

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "36363636-3636-4636-8636-363636363636"
_ASSERTED_AT = datetime(2026, 4, 17, 11, 5, tzinfo=UTC)
_CIF = "B12345674"


def _confirm(repository: CounterpartyEstablishmentRepositoryProtocol) -> ConfirmedCounterpartyFacts:
    return record_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_CIF,
        territorial_scope=IvaTerritorialScope.ES_MAINLAND,
        asserted_by="operator@example.test",
        identification_state=EUMemberState.DE,
        note="",
        asserted_at=_ASSERTED_AT,
        repository=repository,
    )


def test_a_dropped_identification_on_disk_does_not_reload_as_an_answer(tmp_path: Path) -> None:
    """A payload stripped of identification must not reload as the stored answer.

    The field is legitimately nullable, so a record without it is a valid
    shape and the model cannot raise. Inequality is therefore the honest tooth:
    a payload stripped of identification must not come back equal to what was
    saved. A control re-saves the unmodified envelope through the same surgery
    first, so the inequality cannot be an artefact of that surgery.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        objects = runtime.repository
        repository = CounterpartyEstablishmentRepository(objects=objects)
        stored = _confirm(repository)

        record = objects.load(
            LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.namespace,
            stored.counterparty_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.schema_version,
        )
        assert record is not None
        envelope = json.loads(record.payload.decode("utf-8"))
        assert envelope["payload"]["identification_state"] == EUMemberState.DE.value, (
            "fixture must actually persist the identification for this proof to mean anything"
        )

        def _rewrite(payload: dict[str, object]) -> None:
            objects.save(
                namespace=LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.namespace,
                object_key=stored.counterparty_key,
                classification=record.classification,
                schema_version=record.schema_version,
                written_at=record.written_at,
                payload=json.dumps(payload).encode("utf-8"),
            )

        _rewrite(envelope)
        control = CounterpartyEstablishmentRepository(objects=objects).load(stored.counterparty_key)
        assert control == stored, "the surgery itself must be lossless, or the proof below is meaningless"

        del envelope["payload"]["identification_state"]
        _rewrite(envelope)

        reloaded = CounterpartyEstablishmentRepository(objects=objects).load(stored.counterparty_key)

    assert reloaded != stored, "a dropped identification re-defaulted silently: the boundary is tautological"
    assert reloaded is not None
    assert reloaded.identification_state is None
