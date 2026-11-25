"""Credit resolutions through the real encrypted store and the guarded write path.

The acceptance restates the amounts it answers, so it is stored only inside an
encrypted payload. The key is the exact finding, a substituted row is refused on
load, a write needs the revision it was prepared against, and a store that
cannot be read is reported as unreadable and never as an empty one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .....application.modelo.credit_resolution import (
    CreditResolutionLookup,
    credit_resolution_for_finding,
    load_credit_resolutions,
)
from .....application.modelo.credit_resolution_repository import (
    CreditResolutionPersistenceError,
    CreditResolutionRefusedError,
    CreditResolutionRevisionConflictError,
    credit_resolution_key,
    revoke_credit_resolution,
    store_credit_resolution,
)
from .....core.external_constants import UTF_8_ENCODING
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from .....domain.modelos.calculation_revision_sources import CalculationSourceIssue
from .....domain.modelos.credit_resolution import CreditResolutionRecord, CreditResolutionState
from .....domain.modelos.tests.source_disagreement_support import sample_source_disagreement
from ...storage.secure_object_namespaces import MODELO_CREDIT_RESOLUTION_NAMESPACE
from ...storage.sql.secure_objects import SecureObjectRepository
from ..credit_resolution_records import CreditResolutionRepositoryAdapter
from .secure_objects_fixture import secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["secure_objects"]

_BUCKET_ID = "4b8d1c2e-6a3f-4e57-9d10-2c7a5e8f9b34"


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


_AT = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_SESSION = "session-label-one"
_REASON = "Synthetic reason: the payer's own copy of the certificate states this amount."


def _record(*, casilla_id: str = "0596") -> CreditResolutionRecord:
    issue = CalculationSourceIssue(
        reason="credit_source_disagreement",
        binding_source=None,
        message="synthetic",
        casilla_id=casilla_id,
        disagreement=sample_source_disagreement(casilla_id=casilla_id),
    )
    return credit_resolution_for_finding(issue, reason=_REASON, at=_AT, by_session=_SESSION)


def test_a_resolution_survives_the_encrypted_store_and_its_reason_and_amounts_are_never_plaintext(
    tmp_path: Path, secure_objects: SecureObjectRepository
) -> None:
    repository = CreditResolutionRepositoryAdapter(objects=secure_objects)
    record = _record()

    revision_id = store_credit_resolution(
        record, repository=repository, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID
    )

    stored, read_revision = repository.load_revisioned(record.identity)
    assert stored == record
    assert read_revision == revision_id != ABSENT_SECURE_OBJECT_REVISION_ID
    assert repository.load_for_work(modelo="100", filing_year=2025, period="0A") == (record,)
    assert repository.load_for_work(modelo="100", filing_year=2025, period="1T") == ()
    assert repository.load_for_work(modelo="100", filing_year=2024, period="0A") == ()
    assert repository.load_for_work(modelo="303", filing_year=2025, period="0A") == ()
    on_disk = b"".join(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    assert _REASON.encode(UTF_8_ENCODING) not in on_disk
    assert b"499.99" not in on_disk
    assert credit_resolution_key(record.identity).encode(UTF_8_ENCODING) not in on_disk


def test_the_key_names_the_declaration_and_the_exact_finding() -> None:
    record = _record()

    assert credit_resolution_key(record.identity) == f"credit-resolution:100:2025:0A:{record.finding_key}"
    assert MODELO_CREDIT_RESOLUTION_NAMESPACE.object_key_grammar.startswith("credit-resolution:")


def test_one_active_resolution_per_finding_and_a_revoked_one_can_be_replaced_under_its_revision(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = CreditResolutionRepositoryAdapter(objects=secure_objects)
    record = _record()
    first = store_credit_resolution(
        record, repository=repository, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID
    )

    with pytest.raises(CreditResolutionRevisionConflictError):
        store_credit_resolution(record, repository=repository, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID)
    with pytest.raises(CreditResolutionRefusedError) as already:
        store_credit_resolution(record, repository=repository, expected_revision_id=first)
    assert already.value.reason == "already_resolved"

    later = _AT + timedelta(days=1)
    revoked, revoked_revision = revoke_credit_resolution(
        record.identity, at=later, by_session="session-label-two", repository=repository, expected_revision_id=first
    )
    assert revoked.state is CreditResolutionState.REVOKED
    assert revoked_revision not in {first, ABSENT_SECURE_OBJECT_REVISION_ID}
    assert repository.load_revisioned(record.identity) == (revoked, revoked_revision)

    renewed = store_credit_resolution(record, repository=repository, expected_revision_id=revoked_revision)
    stored, stored_revision = repository.load_revisioned(record.identity)
    assert stored == record
    assert stored_revision == renewed


def test_a_revocation_needs_the_current_revision_and_an_active_resolution(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = CreditResolutionRepositoryAdapter(objects=secure_objects)
    record = _record()
    later = _AT + timedelta(days=1)

    with pytest.raises(CreditResolutionRefusedError) as missing:
        revoke_credit_resolution(
            record.identity,
            at=later,
            by_session=_SESSION,
            repository=repository,
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    assert missing.value.reason == "not_resolved"

    first = store_credit_resolution(
        record, repository=repository, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID
    )
    with pytest.raises(CreditResolutionRevisionConflictError):
        revoke_credit_resolution(
            record.identity,
            at=later,
            by_session=_SESSION,
            repository=repository,
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    _revoked, revoked_revision = revoke_credit_resolution(
        record.identity, at=later, by_session=_SESSION, repository=repository, expected_revision_id=first
    )
    with pytest.raises(CreditResolutionRefusedError) as twice:
        revoke_credit_resolution(
            record.identity,
            at=later,
            by_session=_SESSION,
            repository=repository,
            expected_revision_id=revoked_revision,
        )
    assert twice.value.reason == "not_resolved"


def test_a_row_stored_under_another_findings_key_is_refused_on_load(secure_objects: SecureObjectRepository) -> None:
    repository = CreditResolutionRepositoryAdapter(objects=secure_objects)
    original = _record(casilla_id="0596")
    other = _record(casilla_id="0597")
    assert original.finding_key != other.finding_key
    store_credit_resolution(original, repository=repository, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID)
    stored = secure_objects.load(
        MODELO_CREDIT_RESOLUTION_NAMESPACE.namespace,
        credit_resolution_key(original.identity),
        expected_class=MODELO_CREDIT_RESOLUTION_NAMESPACE.sensitivity,
        max_supported_version=MODELO_CREDIT_RESOLUTION_NAMESPACE.schema_version,
    )
    assert stored is not None

    # The original's payload now sits under the other finding's key, as a substituted row would.
    secure_objects.save(
        namespace=MODELO_CREDIT_RESOLUTION_NAMESPACE.namespace,
        object_key=credit_resolution_key(other.identity),
        classification=stored.classification,
        schema_version=stored.schema_version,
        written_at=stored.written_at,
        payload=stored.payload,
    )

    with pytest.raises(CreditResolutionPersistenceError):
        repository.load_revisioned(other.identity)
    with pytest.raises(CreditResolutionPersistenceError):
        repository.load_for_work(modelo="100", filing_year=2025, period="0A")


def test_an_unreadable_store_is_an_unreadable_lookup_and_honours_no_resolution(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = CreditResolutionRepositoryAdapter(objects=secure_objects)
    record = _record()
    store_credit_resolution(record, repository=repository, expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID)
    readable = load_credit_resolutions(repository, modelo="100", filing_year=2025, period="0A")
    assert readable == CreditResolutionLookup(records=(record,))
    assert readable.resolutions.covers(record.finding_key)

    stored = secure_objects.load(
        MODELO_CREDIT_RESOLUTION_NAMESPACE.namespace,
        credit_resolution_key(record.identity),
        expected_class=MODELO_CREDIT_RESOLUTION_NAMESPACE.sensitivity,
        max_supported_version=MODELO_CREDIT_RESOLUTION_NAMESPACE.schema_version,
    )
    assert stored is not None
    broken = json.loads(stored.payload)
    broken["payload"]["state"] = "no-such-state"
    secure_objects.save(
        namespace=MODELO_CREDIT_RESOLUTION_NAMESPACE.namespace,
        object_key=credit_resolution_key(record.identity),
        classification=stored.classification,
        schema_version=stored.schema_version,
        written_at=stored.written_at,
        payload=json.dumps(broken).encode(UTF_8_ENCODING),
    )

    lookup = load_credit_resolutions(repository, modelo="100", filing_year=2025, period="0A")

    assert lookup.unreadable
    assert lookup.records == ()
    assert lookup.active == ()
    assert not lookup.resolutions.covers(record.finding_key)
    assert lookup.resolutions.unreadable
