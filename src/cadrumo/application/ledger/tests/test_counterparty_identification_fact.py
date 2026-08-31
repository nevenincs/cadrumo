"""The counterparty row remembers an IVA identification, once, for every document.

Ley 37/1992 art. 25 exempts an intra-community supply on the acquirer's IVA
IDENTIFICATION in another Member State. That is a stable fact about an entity,
not about a page, so asking it per document would put the same question to the
operator on every invoice and every manual row for the same counterparty.

It joins the row that already remembers where the counterparty is ESTABLISHED,
which is a different fact: arts. 69-70 govern the place, art. 25 the
registration, and the two diverge in real trade. Both live on one record so one
operator interaction settles both, and neither is ever read for the other.

The write rules are asymmetric between the axes in exactly one respect, and it
is not a softening: an identification arriving where none is stored ANSWERS a
second question rather than replacing an answer, so it is written through. A
DIFFERENT one refuses like any other contradiction, and a call supplying none
leaves a stored answer standing -- ``None`` is an unasked question, and reading
it as an answer would let a note correction silently withdraw the registration.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....domain.iva.classification import IvaTerritorialScope
from ....domain.iva.schema import EUMemberState
from ....tests.secure_sql import TestRuntimeProfile
from ..counterparty_establishment import (
    ConfirmedCounterpartyFactsRepository,
    CounterpartyEstablishmentConflictError,
    forget_confirmed_counterparty_facts,
    record_confirmed_counterparty_facts,
    resolve_confirmed_counterparty_facts,
)
from ._counterparty_fact_fixtures import runtime_profile
from ._ledger_value_fixtures import repository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["repository", "runtime_profile"]

_BUCKET_ID = "36363636-3636-4636-8636-363636363636"
_ASSERTED_AT = datetime(2026, 4, 17, 11, 5, tzinfo=UTC)
_CIF = "B12345674"


def _confirm(
    repository: ConfirmedCounterpartyFactsRepository,
    *,
    scope: IvaTerritorialScope = IvaTerritorialScope.ES_MAINLAND,
    identification_state: EUMemberState | None = None,
    note: str = "",
):
    return record_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_CIF,
        territorial_scope=scope,
        asserted_by="operator@example.test",
        identification_state=identification_state,
        note=note,
        asserted_at=_ASSERTED_AT,
        repository=repository,
    )


def _resolve(repository: ConfirmedCounterpartyFactsRepository):
    return resolve_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_CIF,
        repository=repository,
    )


def test_one_answer_serves_every_later_read(repository: ConfirmedCounterpartyFactsRepository) -> None:
    """The row's whole justification: asked once, answered for every document after.

    The establishment is Spanish and the identification German -- the divergent
    pair art. 25 turns on, and the case a single-axis row could not hold at all.
    """
    _confirm(repository, scope=IvaTerritorialScope.ES_MAINLAND, identification_state=EUMemberState.DE)

    for _ in range(3):
        resolution = _resolve(repository)
        assert resolution.identification is not None
        assert resolution.identification.value is EUMemberState.DE
        assert resolution.fact is not None
        assert resolution.fact.value is IvaTerritorialScope.ES_MAINLAND


def test_an_unanswered_identification_resolves_to_nothing(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """Absence is absence: a confirmed TERRITORY never supplies a registration.

    The territory here is a perfectly good non-Spanish one. A row that read it
    across would hand back an identification the operator never gave, which is
    the substitution the whole axis exists to prevent.
    """
    _confirm(repository, scope=IvaTerritorialScope.EU_MEMBER)

    resolution = _resolve(repository)
    assert resolution.fact is not None
    assert resolution.identification is None


@pytest.mark.parametrize("scope", list(IvaTerritorialScope))
def test_no_territory_ever_produces_an_identification(
    repository: ConfirmedCounterpartyFactsRepository,
    scope: IvaTerritorialScope,
) -> None:
    """Swept across every member of the territory enum, not just a convenient one.

    A cross-reading would most plausibly be written for one territory -- the EU
    member case -- so checking that case alone could pass while another leaked.
    """
    _confirm(repository, scope=scope)

    assert _resolve(repository).identification is None


def test_answering_the_identification_later_is_an_addition_not_a_conflict(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """A second question answered later must not read as overwriting the first.

    The operator confirms the territory from the document in front of them and
    learns the registration afterwards. Refusing that would force a withdraw
    plus a re-confirm to record a fact that contradicts nothing.
    """
    first = _confirm(repository, scope=IvaTerritorialScope.ES_MAINLAND)
    assert first.identification_state is None

    second = _confirm(
        repository,
        scope=IvaTerritorialScope.ES_MAINLAND,
        identification_state=EUMemberState.DE,
    )

    assert second.identification_state is EUMemberState.DE
    # The original attribution survives: answering a further question is not a
    # fresh confirmation of the first one.
    assert second.asserted_at == first.asserted_at
    assert _resolve(repository).identification is not None


def test_a_different_identification_refuses_and_names_both_values(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """Replacing a confirmed registration takes the withdraw path, like a territory."""
    _confirm(repository, identification_state=EUMemberState.DE)

    with pytest.raises(CounterpartyEstablishmentConflictError) as raised:
        _confirm(repository, identification_state=EUMemberState.FR)

    message = str(raised.value)
    assert "de" in message and "fr" in message, message
    # The stored answer is untouched by the refused call.
    resolved = _resolve(repository).identification
    assert resolved is not None
    assert resolved.value is EUMemberState.DE


def test_a_retry_omitting_the_identification_does_not_withdraw_it(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """The silent-erasure case, which is the one that would move money.

    A caller correcting only the note supplies no identification. Treating that
    ``None`` as "identified nowhere" would drop the registration and turn every
    later intra-community supply for this counterparty into a refusal -- an
    over-declaration nobody asked for and nothing would report.
    """
    _confirm(repository, identification_state=EUMemberState.DE)

    _confirm(repository, note="corrected the reference on the confirmation call")

    resolved = _resolve(repository).identification
    assert resolved is not None
    assert resolved.value is EUMemberState.DE


def test_withdrawing_removes_both_axes_together(
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """Withdrawal is about the entity, so it cannot leave half a record standing."""
    _confirm(repository, identification_state=EUMemberState.DE)

    assert forget_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_CIF,
        repository=repository,
    )

    resolution = _resolve(repository)
    assert resolution.fact is None
    assert resolution.identification is None


def test_a_dropped_identification_on_disk_does_not_reload_as_an_answer(
    runtime_profile: TestRuntimeProfile,
    repository: ConfirmedCounterpartyFactsRepository,
) -> None:
    """Anti-tautology proof for the new axis, keyed on inequality rather than refusal.

    The field is legitimately nullable, so a record without it is a valid shape
    and the model cannot raise. Inequality is therefore the honest tooth: a
    payload stripped of the identification must not come back equal to what was
    saved. If it ever does, the roundtrip beside it proves nothing about this
    field and a save-drops regression would withhold an art. 25 exemption in
    silence.

    A control re-saves the UNMODIFIED envelope through the same decode/encode
    surgery first, so the inequality below cannot be an artefact of the surgery.
    """
    import json

    from ....adapters.persistence.storage._secure_object_namespaces import LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE
    from ....core.classification.policies import SensitivityClass

    stored = _confirm(repository, identification_state=EUMemberState.DE)
    objects = runtime_profile.repository

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
    control = ConfirmedCounterpartyFactsRepository(objects=objects).load(stored.counterparty_key)
    assert control == stored, "the surgery itself must be lossless, or the proof below is meaningless"

    del envelope["payload"]["identification_state"]
    _rewrite(envelope)

    reloaded = ConfirmedCounterpartyFactsRepository(objects=objects).load(stored.counterparty_key)
    assert reloaded != stored, "a dropped identification re-defaulted silently: the boundary is tautological"
    assert reloaded is not None
    assert reloaded.identification_state is None
