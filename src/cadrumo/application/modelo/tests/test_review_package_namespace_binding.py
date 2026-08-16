"""Registry-definition binding proof for the review-package signing key store.

The review-package secure-object consumers (signing key, recipient encryption
key, recipient fingerprint registry, replay-guard nonce ledger) single-source
their ``classification`` from the owning
:class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition` rather
than restating a ``SensitivityClass`` literal, and already source
``schema_version`` from the same def.

This drives the real ``ensure_review_package_signing_keypair`` save path against
a genuine encrypted bucket and reads the raw :class:`SecureObjectRow` back,
asserting the persisted classification and schema_version equal exactly what
``MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE`` declares. The sibling recipient
encryption / registry / replay-guard stores follow the identical single-sourcing
pattern and are exercised by their own per-store roundtrip suites.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from ....adapters.persistence.storage import MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....adapters.persistence.storage.sql.session import session_scope
from ....tests.secure_sql import isolated_runtime_profile
from .._review_package_signing import ensure_review_package_signing_keypair

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_signing_key_row_carries_registry_declared_metadata(tmp_path: Path) -> None:
    """The signing keypair save persists the metadata its registry def declares."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="a19b3b57-1e77-4a31-9dc1-54d04fbd5d9d") as profile:
        ensure_review_package_signing_keypair(bucket_id=profile.bucket_id, repository=profile.repository)

        with session_scope(profile.repository._engine) as session:
            rows = [
                row
                for row in session.execute(select(SecureObjectRow)).scalars().all()
                if row.namespace == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.namespace
            ]

    assert len(rows) == 1, f"expected one signing-key row, saw {len(rows)}"
    assert rows[0].classification == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.sensitivity.value
    assert rows[0].schema_version == MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE.schema_version
