"""Real encrypted-SQL regression for the profile bare-model persistence kernel."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....adapters.persistence.storage import PROFILE_ASSETS_LEDGER_NAMESPACE
from .....domain.contribuyente.assets import AssetClass, AssetRecord, AssetsLedgerDocument
from .....tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from .._secure_model_document import ProfileBareModelSecurePersistence

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_kernel_roundtrips_a_strict_document_as_encrypted_registry_governed_bytes(tmp_path: Path) -> None:
    """The shared kernel never creates a plaintext model or an ungoverned row."""
    document = AssetsLedgerDocument(
        assets=(
            AssetRecord(
                identifier="kernel-canary",
                description="KERNEL-SECRET-ASSET",
                asset_class=AssetClass.ELECTRONICA_INFORMATICA,
                acquisition_date=date(2025, 1, 1),
                cost_basis=Decimal("100.00"),
            ),
        ),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="a0e10fc6-03c5-4290-832a-fcb4c7654fe4") as profile:
        persistence = ProfileBareModelSecurePersistence(
            objects=profile.repository,
            definition=PROFILE_ASSETS_LEDGER_NAMESPACE,
            model_type=AssetsLedgerDocument,
            empty_document=AssetsLedgerDocument,
        )

        write = persistence.to_secure_object_write(document)
        persistence.save(document)

        at_rest = read_db_at_rest_bytes(profile.paths.database_file)
        assert persistence.load() == document

    assert write.namespace == PROFILE_ASSETS_LEDGER_NAMESPACE.namespace
    assert write.classification is PROFILE_ASSETS_LEDGER_NAMESPACE.sensitivity
    assert write.schema_version == PROFILE_ASSETS_LEDGER_NAMESPACE.schema_version
    assert b"KERNEL-SECRET-ASSET" not in at_rest
    assert b"kernel-canary" not in at_rest
