"""Real encrypted v1-to-v2 migration proofs for IVA deduction authority."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from .....application.aggregation import aggregate_iva_ledger_observations_from_repositories
from .....core import IvaDeductionEvidenceAuthority, IvaDeductionFactKind, Period
from .....core.hashing import sha256_hex
from .....core.time import now
from .....domain.bienes_inversion import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    BienInversionKind,
    BienInversionRecordError,
)
from .....domain.iva import IvaCategory, IvaDeductionClassificationProvenance
from .....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
    transaction_index_object_key,
    transaction_object_key,
)
from .....tests.secure_sql import isolated_runtime_profile
from ...storage import (
    PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE,
    TRANSACTION_CATALOGUE_NAMESPACE,
    Envelope,
    SecureObjectMigrationTarget,
    SecureObjectRepository,
    SensitivityClass,
)
from ...storage.crypto import (
    encrypt_secure_object_payload,
    secure_object_key_digest,
    secure_object_payload_aad,
)
from ...storage.errors import SecureObjectRevisionConflictError, StorageValidationError
from ...storage.sql import SecureObjectRow
from ...storage.sql._secure_object_crypto import derive_revision_id
from ...storage.sql.engine import get_engine
from ...storage.sql.session import session_scope
from ..bienes_inversion import BienesInversionIvaRegisterRepository
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import LedgerStorageError, TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _authoritative_transaction() -> Transaction:
    return Transaction(
        raw=RawTransaction(
            provider_transaction_id="v1-authoritative-transaction",
            booked_date=date(2026, 4, 10),
            value_date=date(2026, 4, 10),
            amount=Decimal("121.00"),
            currency="EUR",
            counterparty="Proveedor IVA SL",
            description="Factura con IVA deducible",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="c" * 64,
                source_row_index=1,
                source_format=SourceFormat.CSV,
                ingested_at=datetime(2026, 4, 10, 10, 0, tzinfo=UTC),
                provider_name="migration proof",
            ),
            raw_fields={"invoice": "V1-001"},
        ),
        direction=TransactionDirection.OUTGOING,
        business_classification=BusinessClassification.BUSINESS,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        iva_category=IvaCategory.DOMESTIC_GENERAL,
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            source_locator="invoice:V1-001",
            evidence_digest="d" * 64,
        ),
        source_jurisdiction="ES",
        group_label=None,
    )


def _register() -> BienesInversionIvaRegister:
    return BienesInversionIvaRegister(
        records=(
            BienInversionIvaRecord(
                identifier="asset-v1-001",
                description="Vehicle with authoritative original ledger reference",
                acquisition_year=2026,
                cuota_soportada=Decimal("2100.00"),
                prorrata_inicial_pct=Decimal("80"),
                kind=BienInversionKind.MUEBLE,
                acquisition_ledger_id="ledger-v1-001",
                prorrata_sector_id="sector-a",
            ),
        )
    )


def _transaction_payload(transaction: Transaction, *, schema_version: int) -> bytes:
    return (
        Envelope[Transaction](
            schema_version=schema_version,
            written_at=transaction.modified_at,
            classification=SensitivityClass.FINANCIAL,
            payload=transaction,
        )
        .model_dump_json()
        .encode("utf-8")
    )


def _index_payload(transaction_id: str, *, schema_version: int) -> bytes:
    return json.dumps(
        {
            "schema_version": schema_version,
            "written_at": now().isoformat(),
            "classification": SensitivityClass.FINANCIAL.value,
            "payload": {"transaction_ids": [transaction_id]},
            "encryption": None,
        }
    ).encode("utf-8")


def _seed_historical_v1_row(
    *,
    objects: SecureObjectRepository,
    engine: Engine,
    namespace: str,
    object_key: str,
    written_at: datetime,
    current_payload: bytes,
    legacy_payload: bytes,
) -> None:
    """Create a real current row, then reproduce a self-consistent v1 row.

    The registered namespace rejects new v1 writes. Historical data must
    therefore be represented by changing the real encrypted database row and
    restamping all metadata that the repository validates before decrypting.
    """
    objects.save(
        namespace=namespace,
        object_key=object_key,
        classification=SensitivityClass.FINANCIAL,
        schema_version=2,
        written_at=written_at,
        payload=current_payload,
    )
    with session_scope(engine) as session:
        row = session.execute(
            select(SecureObjectRow).where(
                SecureObjectRow.namespace == namespace,
                SecureObjectRow.object_key == object_key,
            )
        ).scalar_one()
        legacy_schema_version = 1
        legacy_payload_wire = encrypt_secure_object_payload(
            legacy_payload,
            associated_data=secure_object_payload_aad(
                namespace,
                bytes(row.object_key),
                legacy_schema_version,
            ),
        )
        legacy_payload_hash = sha256_hex(legacy_payload)
        legacy_ciphertext_hash = sha256_hex(legacy_payload_wire)
        row.schema_version = legacy_schema_version
        row.payload = legacy_payload_wire
        row.payload_hash = legacy_payload_hash
        row.ciphertext_hash = legacy_ciphertext_hash
        row.revision_id = derive_revision_id(
            namespace=namespace,
            object_key=bytes(row.object_key),
            schema_version=legacy_schema_version,
            written_at=row.written_at,
            payload_hash=legacy_payload_hash,
            ciphertext_hash=legacy_ciphertext_hash,
            previous_revision_id=row.previous_revision_id,
            previous_payload_hash=row.previous_payload_hash,
        )


def _seed_v1_catalogue(
    repository: TransactionCatalogueRepository,
    *,
    engine: Engine,
    bucket_id: str,
    transaction: Transaction,
) -> None:
    _seed_historical_v1_row(
        objects=repository._objects,
        engine=engine,
        namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key=transaction_object_key(bucket_id, transaction.transaction_id),
        written_at=transaction.modified_at,
        current_payload=_transaction_payload(transaction, schema_version=2),
        legacy_payload=_transaction_payload(transaction, schema_version=1),
    )
    _seed_historical_v1_row(
        objects=repository._objects,
        engine=engine,
        namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key=transaction_index_object_key(bucket_id),
        written_at=now(),
        current_payload=_index_payload(transaction.transaction_id, schema_version=2),
        legacy_payload=_index_payload(transaction.transaction_id, schema_version=1),
    )


def _stored_row_state(engine: Engine, namespace: str) -> tuple[tuple[bytes, int, str, str], ...]:
    with session_scope(engine) as session:
        rows = session.execute(select(SecureObjectRow).where(SecureObjectRow.namespace == namespace)).scalars().all()
        states: list[tuple[bytes, int, str, str]] = []
        for row in rows:
            assert row.payload_hash is not None
            states.append(
                (
                    bytes(row.object_key),
                    row.schema_version,
                    row.revision_id or "",
                    row.payload_hash or "",
                )
            )
        return tuple(sorted(states))


def test_atomic_v1_migration_cas_conflict_writes_no_replacements(tmp_path: Path) -> None:
    """A concurrent revision between validation and commit rolls back every replacement."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="7918a6f2-c538-4517-a103-21c162fce270") as profile:
        engine = get_engine(profile.settings)
        repository = TransactionCatalogueRepository(bucket_id="7918a6f2-c538-4517-a103-21c162fce270")
        transaction = _authoritative_transaction().model_copy(
            update={
                "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_INVESTMENT,
                "investment_asset_id": "asset-v1-001",
                "prorrata_sector_id": "sector-a",
            }
        )
        _seed_v1_catalogue(
            repository,
            engine=engine,
            bucket_id="7918a6f2-c538-4517-a103-21c162fce270",
            transaction=transaction,
        )
        bienes_repository = BienesInversionIvaRegisterRepository()
        register = BienesInversionIvaRegister(
            records=(_register().records[0].model_copy(update={"acquisition_ledger_id": transaction.transaction_id}),)
        )
        legacy_register = register.model_dump(mode="json")
        legacy_register["schema_version"] = "1"
        legacy_register["records"][0]["schema_version"] = "1"
        _seed_historical_v1_row(
            objects=bienes_repository._storage._objects,
            engine=engine,
            namespace=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
            object_key=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.require_default_object_key(),
            written_at=now(),
            current_payload=register.model_dump_json().encode("utf-8"),
            legacy_payload=json.dumps(legacy_register).encode("utf-8"),
        )
        state_at_conflict: tuple[tuple[bytes, int, str, str], ...] = ()
        bienes_state_at_conflict: tuple[tuple[bytes, int, str, str], ...] = ()

        def create_concurrent_revision(_payloads: object) -> None:
            nonlocal bienes_state_at_conflict, state_at_conflict
            with session_scope(engine) as session:
                row = session.execute(
                    select(SecureObjectRow).where(
                        SecureObjectRow.namespace == TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                        SecureObjectRow.object_key == transaction_repository_key,
                    )
                ).scalar_one()
                row.revision_id = "f" * 64
            state_at_conflict = _stored_row_state(engine, TRANSACTION_CATALOGUE_NAMESPACE.namespace)
            bienes_state_at_conflict = _stored_row_state(
                engine, PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace
            )

        transaction_repository_key = secure_object_key_digest(
            transaction_object_key("7918a6f2-c538-4517-a103-21c162fce270", transaction.transaction_id)
        )
        with pytest.raises(SecureObjectRevisionConflictError):
            repository._objects.migrate_targets_atomically(
                (
                    SecureObjectMigrationTarget(
                        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                        transaction_index_object_key("7918a6f2-c538-4517-a103-21c162fce270"),
                        SensitivityClass.FINANCIAL,
                        2,
                    ),
                    SecureObjectMigrationTarget(
                        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                        transaction_object_key("7918a6f2-c538-4517-a103-21c162fce270", transaction.transaction_id),
                        SensitivityClass.FINANCIAL,
                        2,
                    ),
                    SecureObjectMigrationTarget(
                        PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
                        PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.require_default_object_key(),
                        SensitivityClass.FINANCIAL,
                        2,
                    ),
                ),
                validate_upgraded_payloads=create_concurrent_revision,
                write_provenance="s54-cas-conflict-proof",
            )

        assert _stored_row_state(engine, TRANSACTION_CATALOGUE_NAMESPACE.namespace) == state_at_conflict
        assert (
            _stored_row_state(engine, PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace)
            == bienes_state_at_conflict
        )
        assert {schema_version for _, schema_version, _, _ in state_at_conflict} == {1}
        assert {schema_version for _, schema_version, _, _ in bienes_state_at_conflict} == {1}


def test_authoritative_v1_rows_upgrade_and_roundtrip_through_real_secure_repositories(tmp_path: Path) -> None:
    """Both deduction-schema owners validate and atomically replace authoritative v1 rows."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="949862e4-398e-4c4c-8209-f3dbd4b2636d") as profile:
        engine = get_engine(profile.settings)
        transaction_repository = TransactionCatalogueRepository(bucket_id="949862e4-398e-4c4c-8209-f3dbd4b2636d")
        transaction = _authoritative_transaction().model_copy(
            update={
                "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_INVESTMENT,
                "investment_asset_id": "asset-v1-001",
                "prorrata_sector_id": "sector-a",
            }
        )
        _seed_historical_v1_row(
            objects=transaction_repository._objects,
            engine=engine,
            namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            object_key=transaction_object_key("949862e4-398e-4c4c-8209-f3dbd4b2636d", transaction.transaction_id),
            written_at=transaction.modified_at,
            current_payload=_transaction_payload(transaction, schema_version=2),
            legacy_payload=_transaction_payload(transaction, schema_version=1),
        )
        _seed_historical_v1_row(
            objects=transaction_repository._objects,
            engine=engine,
            namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            object_key=transaction_index_object_key("949862e4-398e-4c4c-8209-f3dbd4b2636d"),
            written_at=now(),
            current_payload=_index_payload(transaction.transaction_id, schema_version=2),
            legacy_payload=_index_payload(transaction.transaction_id, schema_version=1),
        )
        bienes_repository = BienesInversionIvaRegisterRepository()
        original_register = BienesInversionIvaRegister(
            records=(_register().records[0].model_copy(update={"acquisition_ledger_id": transaction.transaction_id}),)
        )
        legacy_register = original_register.model_dump(mode="json")
        legacy_register["schema_version"] = "1"
        legacy_register["records"][0]["schema_version"] = "1"
        _seed_historical_v1_row(
            objects=bienes_repository._storage._objects,
            engine=engine,
            namespace=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
            object_key=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.require_default_object_key(),
            written_at=now(),
            current_payload=original_register.model_dump_json().encode("utf-8"),
            legacy_payload=json.dumps(legacy_register).encode("utf-8"),
        )
        aggregation = aggregate_iva_ledger_observations_from_repositories(
            bucket_id="949862e4-398e-4c4c-8209-f3dbd4b2636d",
            period=Period.from_year_and_code(2026, "2T"),
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id="949862e4-398e-4c4c-8209-f3dbd4b2636d"),
        )
        loaded_transactions = transaction_repository.load()
        loaded_register = bienes_repository.load()

        stored_s54_rows = [
            row
            for row in transaction_repository._objects.iter_all_records_raw()
            if row.namespace
            in {
                TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
            }
        ]
        assert len(stored_s54_rows) == 3
        assert {row.schema_version for row in stored_s54_rows} == {2}

    loaded = loaded_transactions.transactions[transaction.transaction_id]
    assert loaded == transaction
    assert aggregation.observations[0].investment_asset_id == "asset-v1-001"
    assert loaded.deduction_provenance is not None
    assert loaded.deduction_provenance.source_locator == "invoice:V1-001"
    assert loaded_register == original_register
    assert loaded_register.records[0].acquisition_ledger_id == transaction.transaction_id
    assert loaded_register.records[0].prorrata_sector_id == "sector-a"


def test_exact_id_read_refuses_v1_until_authoritative_atomic_migration(tmp_path: Path) -> None:
    """Full and exact-ID reads enforce the same explicit v1 cutover."""
    bucket_id = "db42333e-64c8-4686-a2b0-67d24225ab61"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        engine = get_engine(profile.settings)
        repository = TransactionCatalogueRepository(bucket_id=bucket_id)
        transaction = _authoritative_transaction()
        _seed_v1_catalogue(repository, engine=engine, bucket_id=bucket_id, transaction=transaction)
        BienesInversionIvaRegisterRepository(bucket_id=bucket_id).save(BienesInversionIvaRegister())

        with pytest.raises(LedgerStorageError, match="requires explicit IVA authority migration"):
            repository.load()
        with pytest.raises(LedgerStorageError, match="requires explicit IVA authority migration"):
            repository.load_by_ids((transaction.transaction_id,))
        assert {
            row.schema_version
            for row in repository._objects.iter_all_records_raw()
            if row.namespace == TRANSACTION_CATALOGUE_NAMESPACE.namespace
        } == {1}

        repository.migrate_iva_deduction_authority(asset_profile_id=bucket_id)

        assert repository.load().get(transaction.transaction_id) == transaction
        assert repository.load_by_ids((transaction.transaction_id,)).get(transaction.transaction_id) == transaction
        transaction_versions = {
            row.schema_version
            for row in repository._objects.iter_all_records_raw()
            if row.namespace == TRANSACTION_CATALOGUE_NAMESPACE.namespace
        }
        assert transaction_versions == {2}


def test_v1_rows_without_authoritative_backfill_evidence_refuse_through_real_secure_repository(tmp_path: Path) -> None:
    """The read-side cutover names the exact legacy item that needs remediation."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="688dd717-f78e-48ae-86a6-8d689a9c0843") as profile:
        engine = get_engine(profile.settings)
        transaction_repository = TransactionCatalogueRepository(bucket_id="688dd717-f78e-48ae-86a6-8d689a9c0843")
        transaction = _authoritative_transaction()
        legacy_transaction = json.loads(_transaction_payload(transaction, schema_version=1).decode("utf-8"))
        del legacy_transaction["payload"]["deduction_fact_kind"]
        del legacy_transaction["payload"]["deduction_provenance"]
        _seed_historical_v1_row(
            objects=transaction_repository._objects,
            engine=engine,
            namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            object_key=transaction_object_key("688dd717-f78e-48ae-86a6-8d689a9c0843", transaction.transaction_id),
            written_at=transaction.modified_at,
            current_payload=_transaction_payload(transaction, schema_version=2),
            legacy_payload=json.dumps(legacy_transaction).encode("utf-8"),
        )
        _seed_historical_v1_row(
            objects=transaction_repository._objects,
            engine=engine,
            namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            object_key=transaction_index_object_key("688dd717-f78e-48ae-86a6-8d689a9c0843"),
            written_at=now(),
            current_payload=_index_payload(transaction.transaction_id, schema_version=2),
            legacy_payload=_index_payload(transaction.transaction_id, schema_version=1),
        )
        with pytest.raises(StorageValidationError, match="deduction_fact_kind and deduction_provenance"):
            transaction_repository.migrate_iva_deduction_authority(
                asset_profile_id="688dd717-f78e-48ae-86a6-8d689a9c0843"
            )
        transaction_versions = {
            row.schema_version
            for row in transaction_repository._objects.iter_all_records_raw()
            if row.namespace == TRANSACTION_CATALOGUE_NAMESPACE.namespace
        }
        assert transaction_versions == {1}

        bienes_repository = BienesInversionIvaRegisterRepository()
        legacy_register = _register().model_dump(mode="json")
        legacy_register["schema_version"] = "1"
        legacy_register["records"][0]["schema_version"] = "1"
        del legacy_register["records"][0]["acquisition_ledger_id"]
        _seed_historical_v1_row(
            objects=bienes_repository._storage._objects,
            engine=engine,
            namespace=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
            object_key=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.require_default_object_key(),
            written_at=now(),
            current_payload=_register().model_dump_json().encode("utf-8"),
            legacy_payload=json.dumps(legacy_register).encode("utf-8"),
        )
        with pytest.raises(BienInversionRecordError) as raised:
            bienes_repository.load()
        assert isinstance(raised.value.__cause__, StorageValidationError)
        assert "requires explicit schema migration before read" in str(raised.value.__cause__)
        bienes_versions = {
            row.schema_version
            for row in bienes_repository._storage._objects.iter_all_records_raw()
            if row.namespace == PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace
        }
        assert bienes_versions == {1}


def test_semantically_malformed_v1_provenance_refuses_before_every_replacement(tmp_path: Path) -> None:
    """A present but legally incompatible authority is not accepted as backfill evidence."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="22edd7b2-41ac-4280-8bd3-d0a901d1f986") as profile:
        engine = get_engine(profile.settings)
        repository = TransactionCatalogueRepository(bucket_id="22edd7b2-41ac-4280-8bd3-d0a901d1f986")
        transaction = _authoritative_transaction().model_copy(
            update={
                "deduction_provenance": IvaDeductionClassificationProvenance(
                    authority=IvaDeductionEvidenceAuthority.CUSTOMS_DECLARATION,
                    source_locator="customs:wrong-for-domestic",
                    evidence_digest="e" * 64,
                )
            }
        )
        _seed_v1_catalogue(
            repository,
            engine=engine,
            bucket_id="22edd7b2-41ac-4280-8bd3-d0a901d1f986",
            transaction=transaction,
        )

        with pytest.raises(ValueError, match="requires 'invoice_evidence' evidence"):
            repository.migrate_iva_deduction_authority(asset_profile_id="22edd7b2-41ac-4280-8bd3-d0a901d1f986")

        assert {
            row.schema_version
            for row in repository._objects.iter_all_records_raw()
            if row.namespace == TRANSACTION_CATALOGUE_NAMESPACE.namespace
        } == {1}


def test_reciprocal_investment_v1_migration_refuses_unlinked_then_persists_only_v2(tmp_path: Path) -> None:
    """The same real migration path proves zero-write refusal and linked success."""
    transaction = _authoritative_transaction().model_copy(
        update={
            "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_INVESTMENT,
            "investment_asset_id": "asset-machine",
            "prorrata_sector_id": "sector-a",
        }
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bbacb43d-ef9c-4322-832f-a3c04a1ed7e5") as profile:
        engine = get_engine(profile.settings)
        repository = TransactionCatalogueRepository(bucket_id="bbacb43d-ef9c-4322-832f-a3c04a1ed7e5")
        _seed_v1_catalogue(
            repository,
            engine=engine,
            bucket_id="bbacb43d-ef9c-4322-832f-a3c04a1ed7e5",
            transaction=transaction,
        )
        unlinked_register = BienesInversionIvaRegister(
            records=(
                BienInversionIvaRecord(
                    identifier="asset-machine",
                    description="Machine",
                    acquisition_year=2026,
                    cuota_soportada=Decimal("21.00"),
                    prorrata_inicial_pct=Decimal("100"),
                    kind=BienInversionKind.MUEBLE,
                    acquisition_ledger_id="wrong-ledger",
                    prorrata_sector_id="sector-a",
                ),
            )
        )
        bienes_repository = BienesInversionIvaRegisterRepository()
        unlinked_legacy = unlinked_register.model_dump(mode="json")
        unlinked_legacy["schema_version"] = "1"
        unlinked_legacy["records"][0]["schema_version"] = "1"
        _seed_historical_v1_row(
            objects=bienes_repository._storage._objects,
            engine=engine,
            namespace=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
            object_key=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.require_default_object_key(),
            written_at=now(),
            current_payload=unlinked_register.model_dump_json().encode("utf-8"),
            legacy_payload=json.dumps(unlinked_legacy).encode("utf-8"),
        )
        with pytest.raises(ValueError, match="not reciprocal"):
            repository.migrate_iva_deduction_authority(asset_profile_id="bbacb43d-ef9c-4322-832f-a3c04a1ed7e5")
        assert {
            row.schema_version
            for row in repository._objects.iter_all_records_raw()
            if row.namespace == TRANSACTION_CATALOGUE_NAMESPACE.namespace
        } == {1}

        linked_register = BienesInversionIvaRegister(
            records=(
                unlinked_register.records[0].model_copy(update={"acquisition_ledger_id": transaction.transaction_id}),
            )
        )
        linked_legacy = linked_register.model_dump(mode="json")
        linked_legacy["schema_version"] = "1"
        linked_legacy["records"][0]["schema_version"] = "1"
        _seed_historical_v1_row(
            objects=bienes_repository._storage._objects,
            engine=engine,
            namespace=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
            object_key=PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.require_default_object_key(),
            written_at=now(),
            current_payload=linked_register.model_dump_json().encode("utf-8"),
            legacy_payload=json.dumps(linked_legacy).encode("utf-8"),
        )
        repository.migrate_iva_deduction_authority(asset_profile_id="bbacb43d-ef9c-4322-832f-a3c04a1ed7e5")
        assert {
            row.schema_version
            for row in repository._objects.iter_all_records_raw()
            if row.namespace
            in {
                TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE.namespace,
            }
        } == {2}
