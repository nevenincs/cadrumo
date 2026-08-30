"""Strict roundtrip across the encrypted TransactionParticipationIndexRepository.

Persists :class:`TransactionRevisionParticipationIndex` under
``cadrumo.domain.modelos.participation_index`` at :class:`SensitivityClass`
FINANCIAL, one secure object per ledger transaction id.

The participation index is the FINANCIAL-class encrypted boundary that links a
ledger transaction to the finalized modelo revisions and filings that consumed
it. ``filing_record_id`` and ``justificante_reference`` default to ``None``; a
save-drops-field regression on either is invisible unless the roundtrip fixture
populates them with non-default values on a filed participation.

The fixture below populates EVERY defaultable field with a non-default value: a
filed participation carrying ``filing_record_id`` and ``justificante_reference``,
alongside a second verified-but-unfiled participation for the same transaction.
The anti-tautology proof mutates the on-disk encrypted JSON to drop the
``filing_record_id`` from a persisted participation and asserts the boundary
surfaces the regression as strict inequality on reload.
"""

from __future__ import annotations

import json as _json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ....adapters.persistence.storage import TRANSACTION_PARTICIPATION_INDEX_NAMESPACE, SensitivityClass
from ....core.period import Period
from ....tests.secure_sql import isolated_runtime_profile
from ..codes import ModeloCode
from ..participation_index import (
    TransactionParticipationIndexPersistenceError,
    TransactionRevisionParticipation,
    TransactionRevisionParticipationIndex,
    derive_participation_index_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The registry definition is the sole authority for this namespace's identifier
# and envelope schema version; the probe reads it rather than restating the
# values the repository under test writes at.
PARTICIPATION_INDEX_NAMESPACE = TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.namespace
PARTICIPATION_INDEX_SCHEMA_VERSION = TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.schema_version
_BUCKET_ID = "1f8dbeda-8e90-4f36-9576-7e09554cf7ba"  # was 'modelo-participation-runtime'
_P_2024_2T = Period.from_year_and_code(2024, "2T")
_CORRUPT_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 28, 10, 20, 0, tzinfo=UTC)


def _hex(seed: str) -> str:
    """Return a stable 64-char hex blob for typed-id fixture values."""
    return (seed * 64)[:64]


_TRANSACTION_ID = _hex("a")


def _populated_index() -> TransactionRevisionParticipationIndex:
    """Build an index whose every defaultable field is non-default.

    Two participations for one transaction: a filed one carrying both
    ``filing_record_id`` and ``justificante_reference``, and a verified-only one
    leaving both ``None`` (so the roundtrip exercises both the populated and the
    absent shape).
    """
    filed = TransactionRevisionParticipation(
        calculation_revision_id=_hex("b"),
        work_unit_id=_hex("c"),
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        revision_state="presentado",
        filing_record_id=_hex("d"),
        justificante_reference="2024-303-2T-JUST-0001",
    )
    verified = TransactionRevisionParticipation(
        calculation_revision_id=_hex("e"),
        work_unit_id=_hex("f"),
        modelo=ModeloCode("130"),
        filing_year=2024,
        period=_P_2024_2T,
        revision_state="verificado_completo",
    )
    return TransactionRevisionParticipationIndex(
        transaction_id=_TRANSACTION_ID,
        participations=(filed, verified),
    )


def test_participation_index_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """A fully-populated participation index round-trips through encrypted SQL."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)
        original = _populated_index()
        repo.save(original)
        loaded = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID).load(_TRANSACTION_ID)

    assert loaded == original
    assert len(loaded.participations) == 2
    filed = next(p for p in loaded.participations if p.filing_record_id is not None)
    assert filed.modelo == "303"
    assert filed.revision_state == "presentado"
    assert filed.filing_record_id == _hex("d")
    assert filed.justificante_reference == "2024-303-2T-JUST-0001"
    verified = next(p for p in loaded.participations if p.filing_record_id is None)
    assert verified.revision_state == "verificado_completo"
    assert verified.justificante_reference is None
    assert profile.paths.database_file.is_file()


def test_participation_index_empty_for_unknown_transaction(tmp_path: Path) -> None:
    """An unpersisted transaction loads an empty (not raising) participation index."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        loaded = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID).load(_hex("9"))

    assert loaded.transaction_id == _hex("9")
    assert loaded.participations == ()


def test_participation_index_dropped_filing_record_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: dropping ``filing_record_id`` on disk must surface.

    Persists a filed participation, then surgically deletes the
    ``filing_record_id`` key from the encrypted JSON envelope.
    ``filing_record_id`` defaults to ``None`` on the model, so a naive load would
    silently re-default and return an index that compares unequal to the
    original. The proof asserts the regression surfaces as strict inequality.

    If this test passes silently with the field dropped, the participation-index
    boundary is tautological and every roundtrip in the suite is suspect.
    """
    object_key = derive_participation_index_id(_TRANSACTION_ID)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)
        original = _populated_index()
        repo.save(original)

        record = profile.repository.load(
            PARTICIPATION_INDEX_NAMESPACE,
            object_key,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=PARTICIPATION_INDEX_SCHEMA_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        participations = envelope["payload"]["participations"]
        filed = next(p for p in participations if p.get("filing_record_id") is not None)
        assert "filing_record_id" in filed, "fixture must persist filing_record_id for the proof to be meaningful"
        del filed["filing_record_id"]
        profile.repository.save(
            namespace=PARTICIPATION_INDEX_NAMESPACE,
            object_key=object_key,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        mutated = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID).load(_TRANSACTION_ID)

    assert mutated != original, (
        "anti-tautology proof failed: dropping the filing_record_id did NOT "
        "surface on load. The participation-index boundary is tautological and "
        "every roundtrip in the suite is suspect."
    )


def test_participation_index_wrong_inner_classification_is_localized(tmp_path: Path) -> None:
    """A corrupted envelope classification raises a translated persistence error."""
    from ....adapters.persistence.storage import Envelope

    object_key = derive_participation_index_id(_TRANSACTION_ID)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[TransactionRevisionParticipationIndex](
            schema_version=PARTICIPATION_INDEX_SCHEMA_VERSION,
            written_at=_CORRUPT_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.AUDIT,
            payload=TransactionRevisionParticipationIndex(transaction_id=_TRANSACTION_ID),
        )
        profile.repository.save(
            namespace=PARTICIPATION_INDEX_NAMESPACE,
            object_key=object_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=PARTICIPATION_INDEX_SCHEMA_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(TransactionParticipationIndexPersistenceError) as raised:
            TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID).load(_TRANSACTION_ID)

    assert raised.value.context == {
        "reason": "classification_mismatch",
        "expected_classification": "financial",
        "actual_classification": "audit",
    }
