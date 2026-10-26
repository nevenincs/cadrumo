"""Registry-definition binding proof for the review-package signing adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from cadrumo.adapters.persistence.profile.review_package_signing import ReviewPackageSigningKeypairAdapter
from cadrumo.adapters.persistence.storage.secure_object_namespaces import MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE
from cadrumo.adapters.persistence.storage.sql.orm import SecureObjectRow
from cadrumo.adapters.persistence.storage.sql.session import session_scope
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_signing_key_row_carries_registry_declared_metadata(tmp_path: Path) -> None:
    """The signing adapter persists exactly its registry-declared metadata."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="a19b3b57-1e77-4a31-9dc1-54d04fbd5d9d") as profile:
        ReviewPackageSigningKeypairAdapter(
            repository=profile.repository,
            bucket_id=profile.bucket_id,
        ).ensure_keypair(bucket_id=profile.bucket_id)

        with session_scope(profile.repository._engine) as session:
            rows = [
                row
                for row in session.execute(select(SecureObjectRow)).scalars().all()
                if row.namespace == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace
            ]

    assert len(rows) == 1, f"expected one signing-key row, saw {len(rows)}"
    assert rows[0].classification == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity.value
    assert rows[0].schema_version == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version
