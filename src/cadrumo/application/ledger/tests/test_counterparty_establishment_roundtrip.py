"""Encrypted-boundary roundtrip for the counterparty establishment store.

A :class:`~application.ledger.ConfirmedCounterpartyFacts` is the answer to a
question the operator was asked once and will never be asked again for that
counterparty, so the record has to come back exactly as it went in. A dropped
``territorial_scope`` would not read as corruption downstream -- it would read as
"nothing is confirmed about this party", which sends the pipeline back to asking
and is indistinguishable from the honest empty case.

The two gates ``aeat-quality-gates`` requires of a persistence boundary: a real
save -> load -> strict-equality cycle with every defaultable field carrying a
NON-default value, and an anti-tautology proof that rewrites the stored payload
and asserts the real load path refuses it. Real key provider, real SQLite
engine, real serializer throughout.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ._ledger_value_fixtures import secure_objects

__all__ = ["secure_objects"]
from pydantic import ValidationError

from ....adapters.persistence.storage import (
    LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE,
    SensitivityClass,
)
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import ClassifierInputSource
from ....domain.iva import EUMemberState, IvaTerritorialScope
from .._counterparty_establishment import (
    ConfirmedCounterpartyFacts,
    ConfirmedCounterpartyFactsRepository,
)

_BUCKET_ID = "37373737-3737-4737-8737-373737373739"
runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSERTED_AT = datetime(2026, 4, 17, 11, 5, tzinfo=UTC)


def _fully_populated_fact() -> ConfirmedCounterpartyFacts:
    """Build a fact whose defaultable fields all carry non-default values.

    ``note`` defaults to the empty string, and it is the field a
    save-drops / load-re-defaults regression would hide behind: an operator's
    stated reason for the confirmation would vanish while the territory still
    round-tripped, so the record would keep answering without keeping why.

    ``identification_state`` defaults to ``None`` and is the same hazard with
    money behind it: dropped on the way to disk it reloads as "unanswered",
    which withholds an art. 25 exemption the operator already confirmed. It is
    set to a Member State that DIFFERS from the territory, so a load that
    re-derived it from the establishment beside it would not reproduce this
    value and the strict comparison would fail -- which is the only reason the
    field is worth round-tripping.

    ``source`` is deliberately not defaultable on the model, so there is no
    default here to leave in place -- the fixture states it, and the persisted
    payload carries it.
    """
    return ConfirmedCounterpartyFacts.create(
        tax_identifier="B12345674",
        territorial_scope=IvaTerritorialScope.ES_CANARIAS,
        asserted_by="operator@example.test",
        identification_state=EUMemberState.FR,
        note="supplier confirmed established in Las Palmas by telephone on 2026-04-17",
        asserted_at=_ASSERTED_AT,
    )


def test_establishment_fact_roundtrips_through_encrypted_storage(
    secure_objects: SecureObjectRepository,
) -> None:
    """Save, load through a FRESH handle, assert strict model equality."""
    original = _fully_populated_fact()
    ConfirmedCounterpartyFactsRepository(objects=secure_objects).save(original)

    # A fresh repository handle: the record is genuinely re-read from storage
    # rather than returned from state the writing handle still held.
    loaded = ConfirmedCounterpartyFactsRepository(objects=secure_objects).load(original.counterparty_key)

    assert loaded == original
    assert loaded is not None
    assert loaded.territorial_scope is IvaTerritorialScope.ES_CANARIAS
    assert loaded.source is ClassifierInputSource.OPERATOR_ASSERTION
    assert loaded.identification_state is EUMemberState.FR
    # The two axes survived as the DIFFERENT facts they are: nothing collapsed
    # the registration onto the territory beside it.
    assert loaded.territorial_scope is not IvaTerritorialScope.EU_MEMBER
    assert loaded.note == "supplier confirmed established in Las Palmas by telephone on 2026-04-17"
    assert loaded.asserted_at == _ASSERTED_AT
    assert loaded.canonical_tax_identifier == "B12345674"


def test_persisted_fact_answering_neither_question_is_refused_at_load(
    secure_objects: SecureObjectRepository,
) -> None:
    """Anti-tautology proof: strip the record of every answer and reload.

    The territory alone is no longer the whole content: the two confirmed facts
    are independent, either may stand alone, and a record answering only the
    identification is legitimate. So deleting the territory is a NARROWER record
    rather than a corrupt one and must still load.

    What must not load is a record answering NEITHER question. That is the
    invariant this proof now stands on, and it is the sharper one: an empty
    record addresses a counterparty, occupies the key, and answers every later
    question with a silence that reads as a confirmed absence. If this ever
    passed with both fields gone, the model guard would be unenforced at the
    encrypted boundary and the roundtrip above would prove nothing.
    """
    original = _fully_populated_fact()
    repository = ConfirmedCounterpartyFactsRepository(objects=secure_objects)
    repository.save(original)

    record = secure_objects.load(
        LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.namespace,
        original.counterparty_key,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.schema_version,
    )
    assert record is not None
    envelope = json.loads(record.payload.decode("utf-8"))
    stored = envelope["payload"]
    assert stored["territorial_scope"] == IvaTerritorialScope.ES_CANARIAS.value, (
        "fixture must serialise territorial_scope for this proof to mean anything"
    )

    def _rewrite(payload: dict[str, object]) -> None:
        secure_objects.save(
            namespace=LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.namespace,
            object_key=original.counterparty_key,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=json.dumps(payload).encode("utf-8"),
        )

    # Control: re-saving the UNMODIFIED envelope through the same decode/encode
    # surgery must still load, or a refusal below could come from the surgery
    # rather than from the missing field.
    _rewrite(envelope)
    assert ConfirmedCounterpartyFactsRepository(objects=secure_objects).load(original.counterparty_key) is not None

    # A record narrowed to its identification is legitimate and must survive.
    del stored["territorial_scope"]
    _rewrite(envelope)
    narrowed = ConfirmedCounterpartyFactsRepository(objects=secure_objects).load(original.counterparty_key)
    assert narrowed is not None, "a record answering only the identification is legitimate"
    assert narrowed.territorial_scope is None
    assert narrowed.identification_state is not None

    # A record answering nothing is not.
    del stored["identification_state"]
    _rewrite(envelope)

    with pytest.raises(ValidationError):
        ConfirmedCounterpartyFactsRepository(objects=secure_objects).load(original.counterparty_key)


def test_persisted_fact_relabelled_as_document_evidence_is_refused_at_load(
    secure_objects: SecureObjectRepository,
) -> None:
    """A stored fact claiming a document said so must not load.

    The store's whole warrant is that it holds what an OPERATOR confirmed. A
    record carrying ``document_evidence`` would be a cached page reading
    answering later documents as an assertion -- the shape that silently
    disables the contradiction channel -- so the refusal is enforced at the
    boundary rather than only at the constructor a caller may bypass.
    """
    original = _fully_populated_fact()
    ConfirmedCounterpartyFactsRepository(objects=secure_objects).save(original)

    record = secure_objects.load(
        LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.namespace,
        original.counterparty_key,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.schema_version,
    )
    assert record is not None
    envelope = json.loads(record.payload.decode("utf-8"))
    envelope["payload"]["source"] = ClassifierInputSource.DOCUMENT_EVIDENCE.value

    secure_objects.save(
        namespace=LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.namespace,
        object_key=original.counterparty_key,
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )

    with pytest.raises(ValidationError):
        ConfirmedCounterpartyFactsRepository(objects=secure_objects).load(original.counterparty_key)


def test_object_key_carries_no_tax_identifier(secure_objects: SecureObjectRepository) -> None:
    """The addressing key is a digest, and the identifier lives inside the envelope.

    An object key is metadata outside the encrypted payload. Addressing the
    record by the counterparty's NIF would place a real tax identifier of one of
    the taxpayer's trading partners in the clear, which the secure-storage rule
    forbids regardless of how convenient the lookup would be.
    """
    original = _fully_populated_fact()
    ConfirmedCounterpartyFactsRepository(objects=secure_objects).save(original)

    assert original.counterparty_key != original.canonical_tax_identifier
    assert original.canonical_tax_identifier not in original.counterparty_key
    assert len(original.counterparty_key) == 64
    assert set(original.counterparty_key) <= set("0123456789abcdef")
