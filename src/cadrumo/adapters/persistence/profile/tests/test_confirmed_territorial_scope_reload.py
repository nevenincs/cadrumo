"""Reload projection of a confirmed territorial scope at the encrypted boundary.

The encrypted store serialises a registry-projected territorial scope as its
text. A reload must hand the token back as the registry-projected type, and a
stored text the 0083 vocabulary does not declare must be refused rather than
answered as an operator confirmation. Real key provider, real SQLite engine,
real serializer throughout.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from cadrumo.adapters.persistence.profile.counterparty_establishment import CounterpartyEstablishmentRepository
from cadrumo.adapters.persistence.storage.secure_object_namespaces import LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from cadrumo.application.ledger.counterparty_establishment import ConfirmedCounterpartyFacts
from cadrumo.application.ledger.counterparty_establishment_ports import CounterpartyEstablishmentPersistenceError
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.iva.classification import IvaTerritorialScope, require_iva_territorial_scope
from cadrumo.domain.iva.schema import require_eu_member_state

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "37373737-3737-4737-8737-37373737373a"
runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


@pytest.fixture
def secure_objects(runtime_profile: TestRuntimeProfile) -> SecureObjectRepository:
    """Provide the real encrypted-object repository for this adapter suite."""

    return runtime_profile.repository


def _confirmed_fact() -> ConfirmedCounterpartyFacts:
    return ConfirmedCounterpartyFacts.create(
        tax_identifier="B12345674",
        territorial_scope=IvaTerritorialScope.from_registry("es_ceuta_melilla"),
        asserted_by="operator@example.test",
        asserted_at=datetime(2026, 4, 17, 11, 5, tzinfo=UTC),
    )


def _rewrite_scope(secure_objects: SecureObjectRepository, key: str, scope: str) -> None:
    record = secure_objects.load(
        LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.namespace,
        key,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.schema_version,
    )
    assert record is not None
    envelope = json.loads(record.payload.decode("utf-8"))
    envelope["payload"]["territorial_scope"] = scope
    secure_objects.save(
        namespace=LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE.namespace,
        object_key=key,
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )


def test_reloaded_scope_is_the_registry_projected_token(secure_objects: SecureObjectRepository) -> None:
    original = _confirmed_fact()
    CounterpartyEstablishmentRepository(objects=secure_objects).save(original)

    loaded = CounterpartyEstablishmentRepository(objects=secure_objects).load(original.counterparty_key)

    assert loaded is not None
    assert type(loaded.territorial_scope) is IvaTerritorialScope
    assert loaded.territorial_scope == IvaTerritorialScope.from_registry("es_ceuta_melilla")
    assert loaded == original


def test_stored_scope_outside_the_registry_vocabulary_is_refused_at_load(
    secure_objects: SecureObjectRepository,
) -> None:
    original = _confirmed_fact()
    repository = CounterpartyEstablishmentRepository(objects=secure_objects)
    repository.save(original)

    _rewrite_scope(secure_objects, original.counterparty_key, "es_ceuta_melilla")
    assert repository.load(original.counterparty_key) == original

    _rewrite_scope(secure_objects, original.counterparty_key, "atlantis")
    with pytest.raises(CounterpartyEstablishmentPersistenceError):
        repository.load(original.counterparty_key)


def test_reload_under_a_leased_authority_returns_both_projected_axes(
    secure_objects: SecureObjectRepository,
    operation: PinnedAuthorityOperation,
) -> None:
    original = ConfirmedCounterpartyFacts.create(
        tax_identifier="B12345674",
        territorial_scope=require_iva_territorial_scope("es_canarias", operation=operation),
        identification_state=require_eu_member_state("FR", authority=operation),
        asserted_by="operator@example.test",
        asserted_at=datetime(2026, 4, 17, 11, 5, tzinfo=UTC),
    )
    CounterpartyEstablishmentRepository(objects=secure_objects).save(original)

    loaded = CounterpartyEstablishmentRepository(objects=secure_objects).load(original.counterparty_key)

    assert loaded == original
    assert loaded is not None
    assert loaded.territorial_scope == require_iva_territorial_scope("es_canarias", operation=operation)
    assert loaded.identification_state == require_eu_member_state("FR", authority=operation)
