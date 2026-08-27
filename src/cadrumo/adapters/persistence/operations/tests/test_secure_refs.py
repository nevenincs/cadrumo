"""Real encrypted-storage proofs for operation secure references."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from .....core.classification import SensitivityClass
from .....core.hashing import sha256_hex
from .....tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from ...storage import (
    STORAGE_NAMESPACE_REGISTRY,
    StorageCustodyDisposition,
    StorageNamespaceScope,
)
from ...storage.errors import RepositoryError
from ..secure_references import (
    OPERATION_SECURE_REFERENCE_NAMESPACE,
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_WRITTEN_AT = datetime(2026, 8, 14, 14, tzinfo=UTC)


class _Operand(BaseModel):
    subject: str = Field(min_length=1)
    amount: int = Field(ge=0)


class _OtherOperand(BaseModel):
    label: str = Field(min_length=1)


def test_secure_reference_round_trip_is_content_addressed_and_encrypted(tmp_path: Path) -> None:
    """Typed operands deduplicate by exact JSON bytes and never reach disk plaintext."""
    operand = _Operand(subject="taxpayer-private", amount=73)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        store = operation_secure_reference_repository(objects=profile.repository)
        reference = asyncio.run(store.put(operand, written_at=_WRITTEN_AT))
        repeated = asyncio.run(store.put(operand, written_at=_WRITTEN_AT))

        assert reference == repeated == sha256_hex(operand.model_dump_json().encode("utf-8"))
        assert asyncio.run(store.resolve(reference, _Operand)) == operand
        encrypted_database = read_db_at_rest_bytes(profile.paths.database_file)
        assert operand.subject.encode("utf-8") not in encrypted_database
        assert b'"amount":73' not in encrypted_database


def test_secure_reference_refuses_absent_wrong_type_and_digest_corruption(tmp_path: Path) -> None:
    """An addressed object must exist, match its bytes, and hydrate the requested type."""
    operand = _Operand(subject="integrity-subject", amount=12)
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        objects = profile.repository
        store = operation_secure_reference_repository(objects=objects)
        with pytest.raises(RepositoryError, match="absent"):
            asyncio.run(store.resolve("a" * 64, _Operand))

        reference = asyncio.run(store.put(operand, written_at=_WRITTEN_AT))
        with pytest.raises(RepositoryError, match="requested operand type"):
            asyncio.run(store.resolve(reference, _OtherOperand))

        objects.save(
            namespace=OPERATION_SECURE_REFERENCE_NAMESPACE.namespace,
            object_key=reference,
            classification=OPERATION_SECURE_REFERENCE_NAMESPACE.sensitivity,
            schema_version=OPERATION_SECURE_REFERENCE_NAMESPACE.schema_version,
            written_at=_WRITTEN_AT,
            payload=_Operand(subject="substituted", amount=99).model_dump_json().encode("utf-8"),
        )
        with pytest.raises(RepositoryError, match="digest mismatch"):
            asyncio.run(store.resolve(reference, _Operand))


def test_secure_reference_constructor_refuses_plaintext_or_non_digest_namespace(tmp_path: Path) -> None:
    """The adapter accepts only a ciphertext-required content-addressed namespace."""
    plaintext_namespace = OPERATION_SECURE_REFERENCE_NAMESPACE.model_copy(
        update={"sensitivity": SensitivityClass.OPERATIONAL}
    )
    wrong_key_namespace = OPERATION_SECURE_REFERENCE_NAMESPACE.model_copy(
        update={"object_key_grammar": "operand:{content_digest}"}
    )
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        with pytest.raises(ValueError, match="unsuitable sensitivity"):
            OperationSecureReferenceRepository(objects=profile.repository, namespace=plaintext_namespace)
        with pytest.raises(ValueError, match="keyed by"):
            OperationSecureReferenceRepository(objects=profile.repository, namespace=wrong_key_namespace)


def test_canonical_namespace_is_registered_once_in_its_defining_module() -> None:
    """The global operation-reference home is unique and definition-owned."""
    namespace = OPERATION_SECURE_REFERENCE_NAMESPACE

    assert STORAGE_NAMESPACE_REGISTRY.namespace_by_key(namespace.key) is namespace
    assert STORAGE_NAMESPACE_REGISTRY.namespace_by_value(namespace.namespace) is namespace
    assert namespace.owner == "cadrumo.adapters.persistence.operations"
    assert namespace.object_key_grammar == "{content_digest}"
    assert namespace.scope is StorageNamespaceScope.BUCKET_LOCAL
    assert namespace.custody_disposition is StorageCustodyDisposition.PROCESS_LOCAL
