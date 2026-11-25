"""A counterparty's filing name is stated once and kept in the encrypted counterparty record.

The name sits beside the establishment answers on the same record, keyed by the
counterparty's tax identifier, with its own attribution. Stating it keeps every
other answer; restating it replaces only the name; the same name again writes
nothing. A record written before the name existed loads with no name. Real key
provider, real SQLite engine, real serializer throughout.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from cadrumo.adapters.persistence.profile.counterparty_establishment import CounterpartyEstablishmentRepository
from cadrumo.adapters.persistence.storage.secure_object_namespaces import LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from cadrumo.application.ledger.counterparty_establishment import (
    ConfirmedCounterpartyFactsInputError,
    CounterpartyFilingNameInputError,
    confirmed_counterparty_facts_key,
    declared_filing_name_from_parts,
    record_confirmed_counterparty_facts,
    record_counterparty_filing_name,
    record_counterparty_provincia,
)
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.domain.filing.declared_party_name import DeclaredPartyFilingName, DeclaredPartyKind

from .....domain.iva.schema import IvaTerritorialScope

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "37373737-3737-4737-8737-37373737373b"
_SUPPLIER_CIF = "B00015016"
# Whole seconds so the stored timestamp round-trips exactly; restating happens later than stating.
_FIRST_STATED = datetime.now(UTC).replace(microsecond=0)
_RESTATED = _FIRST_STATED + timedelta(days=15, hours=22)
runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


@pytest.fixture
def repository(runtime_profile: TestRuntimeProfile) -> CounterpartyEstablishmentRepository:
    """Bind the real encrypted counterparty store to this suite's profile."""
    return CounterpartyEstablishmentRepository(objects=runtime_profile.repository)


def _entity(razon_social: str) -> DeclaredPartyFilingName:
    return DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social=razon_social)


def _key() -> str:
    key = confirmed_counterparty_facts_key(_SUPPLIER_CIF)
    assert key is not None
    return key


def test_a_stated_name_is_stored_with_its_own_attribution(repository: CounterpartyEstablishmentRepository) -> None:
    stated = record_counterparty_filing_name(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        filing_name=_entity("Suministros Ficticios del Norte, S.L."),
        asserted_by="operator",
        asserted_at=_FIRST_STATED,
        repository=repository,
    )

    loaded = repository.load(_key())
    assert loaded == stated
    assert loaded is not None
    assert loaded.declared_filing_name == _entity("Suministros Ficticios del Norte, S.L.")
    assert (loaded.filing_name_asserted_by, loaded.filing_name_asserted_at) == ("operator", _FIRST_STATED)
    # Stating a name answers no establishment question.
    assert loaded.territorial_scope is None
    assert loaded.declared_fact is None


def test_a_name_keeps_the_establishment_answers_and_their_attribution(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    canarias = IvaTerritorialScope.from_registry("es_canarias")
    record_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        asserted_by="first operator",
        territorial_scope=canarias,
        asserted_at=_FIRST_STATED,
        repository=repository,
    )
    record_counterparty_provincia(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        provincia_code="35",
        asserted_by="first operator",
        repository=repository,
    )

    named = record_counterparty_filing_name(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        filing_name=_entity("Suministros Ficticios del Norte, S.L."),
        asserted_by="second operator",
        asserted_at=_RESTATED,
        repository=repository,
    )

    assert repository.load(_key()) == named
    assert named.territorial_scope == canarias
    assert named.provincia_code == "35"
    assert (named.asserted_by, named.asserted_at) == ("first operator", _FIRST_STATED)
    assert (named.filing_name_asserted_by, named.filing_name_asserted_at) == ("second operator", _RESTATED)

    # An establishment confirmation afterwards keeps the stated name.
    reconfirmed = record_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        asserted_by="first operator",
        territorial_scope=canarias,
        note="checked again",
        repository=repository,
    )
    assert reconfirmed.declared_filing_name == named.declared_filing_name


def test_restating_replaces_the_name_and_the_same_name_writes_nothing(
    repository: CounterpartyEstablishmentRepository,
) -> None:
    record_counterparty_filing_name(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        filing_name=_entity("Suministros Ficticios del Norte, S.L."),
        asserted_by="operator",
        asserted_at=_FIRST_STATED,
        repository=repository,
    )
    retried = record_counterparty_filing_name(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        filing_name=_entity("Suministros Ficticios del Norte, S.L."),
        asserted_by="someone else",
        asserted_at=_RESTATED,
        repository=repository,
    )
    assert (retried.filing_name_asserted_by, retried.filing_name_asserted_at) == ("operator", _FIRST_STATED)

    renamed = DeclaredPartyFilingName(
        kind=DeclaredPartyKind.NATURAL_PERSON, primer_apellido="Ejemplo", segundo_apellido="Prueba", nombre="Ana"
    )
    restated = record_counterparty_filing_name(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        filing_name=renamed,
        asserted_by="someone else",
        asserted_at=_RESTATED,
        repository=repository,
    )
    assert repository.load(_key()) == restated
    assert restated.declared_filing_name == renamed
    assert (restated.filing_name_asserted_by, restated.filing_name_asserted_at) == ("someone else", _RESTATED)


def test_a_record_written_before_the_name_existed_loads_with_no_name(
    repository: CounterpartyEstablishmentRepository,
    runtime_profile: TestRuntimeProfile,
) -> None:
    confirmed = record_confirmed_counterparty_facts(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        asserted_by="operator",
        territorial_scope=IvaTerritorialScope.from_registry("es_mainland"),
        asserted_at=_FIRST_STATED,
        repository=repository,
    )
    objects: SecureObjectRepository = runtime_profile.repository
    namespace = LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE
    record = objects.load(
        namespace.namespace,
        _key(),
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=namespace.schema_version,
    )
    assert record is not None
    envelope = json.loads(record.payload.decode("utf-8"))
    # The payload exactly as the store held it before the filing name was added.
    for member in ("declared_filing_name", "filing_name_asserted_by", "filing_name_asserted_at"):
        del envelope["payload"][member]
    objects.save(
        namespace=namespace.namespace,
        object_key=_key(),
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )

    loaded = repository.load(_key())
    assert loaded == confirmed
    assert loaded is not None
    assert loaded.declared_filing_name is None

    named = record_counterparty_filing_name(
        bucket_id=_BUCKET_ID,
        tax_identifier=_SUPPLIER_CIF,
        filing_name=_entity("Suministros Ficticios del Norte, S.L."),
        asserted_by="operator",
        repository=repository,
    )
    assert repository.load(_key()) == named
    assert named.territorial_scope == confirmed.territorial_scope


def test_an_unverifiable_identifier_holds_no_name(repository: CounterpartyEstablishmentRepository) -> None:
    with pytest.raises(ConfirmedCounterpartyFactsInputError):
        record_counterparty_filing_name(
            bucket_id=_BUCKET_ID,
            tax_identifier="NOT-A-TAX-ID",
            filing_name=_entity("Suministros Ficticios del Norte, S.L."),
            asserted_by="operator",
            repository=repository,
        )


_REFUSED_PARTS = pytest.mark.parametrize(
    ("kind", "primer_apellido", "razon_social", "renderings"),
    [
        ("sole_trader", None, "Ficticia, S.L.", ()),
        ("natural_person", "Ejemplo", None, ()),
        ("entity", None, "Ficticia  S.L.", ()),
        ("entity", None, "Ficticia, S.L.", ((4, "Ficticia"),)),
    ],
    ids=["unknown_kind", "person_without_second_surname_statement", "doubled_space", "rendering_over_its_width"],
)


@_REFUSED_PARTS
def test_parts_that_form_no_filing_name_are_refused_with_the_registered_code(
    kind: str, primer_apellido: str | None, razon_social: str | None, renderings: tuple[tuple[int, str], ...]
) -> None:
    with pytest.raises(CounterpartyFilingNameInputError) as refused:
        declared_filing_name_from_parts(
            kind=kind,
            primer_apellido=primer_apellido,
            nombre="Ana" if primer_apellido is not None else None,
            razon_social=razon_social,
            renderings=renderings,
        )

    assert get_registered_error_code(refused.value).code == "REFUSED_LEDGER_COUNTERPARTY_FILING_NAME_INPUT"
    assert refused.value.translated_message == "errors.refused.refused_ledger_counterparty_filing_name_input"
    # The refusal names the broken rule, never the third party's name.
    assert "Ficticia" not in str(refused.value.context)
    assert "Ejemplo" not in str(refused.value.context)
