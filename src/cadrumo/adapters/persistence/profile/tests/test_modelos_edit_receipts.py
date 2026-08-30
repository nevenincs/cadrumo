"""Encrypted-boundary proofs for Modelo edit mutation result receipt persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from .....application.modelo.edit_contract import ModeloEditMutationFamily, ModeloEditMutationResultReceiptV1
from .....tests.secure_sql import (
    isolated_runtime_profile,
    mutate_encrypted_secure_object_json,
    read_db_at_rest_bytes,
)
from ...storage.sql import SecureObjectRow
from ..modelos_edit_receipts import ModeloEditReceiptRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_RECEIPT_ID = "1" * 64
_OPERATION_ID = "2" * 64
_BASELINE_ID = "3" * 64
_WORK_UNIT_ID = "4" * 64
_CALCULATION_REVISION_ID = "5" * 64
_BUCKET_EVENT_ID = "6" * 64


def _receipt(*, receipt_id: str = _RECEIPT_ID) -> ModeloEditMutationResultReceiptV1:
    return ModeloEditMutationResultReceiptV1(
        receipt_id=receipt_id,
        operation_id=_OPERATION_ID,
        mutation_family=ModeloEditMutationFamily.RECALCULATE,
        baseline_id=_BASELINE_ID,
        work_unit_id=_WORK_UNIT_ID,
        calculation_revision_id=_CALCULATION_REVISION_ID,
        bucket_event_id=_BUCKET_EVENT_ID,
        committed_at=datetime(2026, 8, 26, 9, 30, 0, tzinfo=UTC),
        result_destination="modelo/130/2025/1T/edit-result",
    )


def test_receipt_roundtrips_strictly_and_stays_encrypted_at_rest(tmp_path: Path) -> None:
    """Every non-default receipt field survives, and its content stays off disk."""
    receipt = _receipt()

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ModeloEditReceiptRepository(objects=profile.repository)
        repository.save(receipt)

        loaded = ModeloEditReceiptRepository(objects=profile.repository).load(receipt.receipt_id)
        at_rest = read_db_at_rest_bytes(profile.paths.database_file)

    assert loaded == receipt
    assert loaded is not None
    assert loaded.mutation_family is ModeloEditMutationFamily.RECALCULATE
    assert loaded.effect.value == "updated"
    assert _WORK_UNIT_ID.encode() not in at_rest
    assert _CALCULATION_REVISION_ID.encode() not in at_rest
    assert b"modelo/130/2025/1T/edit-result" not in at_rest


def test_receipt_load_is_absent_for_an_unknown_id(tmp_path: Path) -> None:
    """A never-written receipt id loads as absent, never as a fabricated default."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ModeloEditReceiptRepository(objects=profile.repository)
        repository.save(_receipt())

        missing = repository.load("f" * 64)

    assert missing is None


def test_receipt_load_refuses_a_tampered_calculation_revision_id(tmp_path: Path) -> None:
    """A corrupted stored payload refuses to load rather than laundering silently.

    This is the anti-tautology proof: without the real strict validation on
    the load path, a directly-mutated on-disk field would come back
    unremarked, and every other roundtrip assertion in this module would be
    proving nothing.
    """
    original = _receipt()

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ModeloEditReceiptRepository(objects=profile.repository)
        repository.save(original)
        statement = select(SecureObjectRow).where(
            SecureObjectRow.namespace == repository.namespace,
            SecureObjectRow.object_key == original.receipt_id,
        )

        def corrupt_calculation_revision_id(envelope: dict[str, object]) -> None:
            payload = envelope["payload"]
            assert isinstance(payload, dict)
            assert payload["calculation_revision_id"] == original.calculation_revision_id
            payload["calculation_revision_id"] = "not-a-hex64-identity"

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=statement,
            mutate=corrupt_calculation_revision_id,
        )

        with pytest.raises(ValidationError):
            repository.load(original.receipt_id)


def test_two_receipts_for_the_same_work_unit_are_independently_addressable(tmp_path: Path) -> None:
    """Each receipt is its own row: an unrelated key never shadows another."""
    first = _receipt(receipt_id="1" * 64)
    second = _receipt(receipt_id="a" * 64).model_copy(update={"bucket_event_id": "b" * 64})

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = ModeloEditReceiptRepository(objects=profile.repository)
        repository.save(first)
        repository.save(second)

        loaded_first = repository.load(first.receipt_id)
        loaded_second = repository.load(second.receipt_id)

    assert loaded_first == first
    assert loaded_second == second
    assert loaded_first != loaded_second
