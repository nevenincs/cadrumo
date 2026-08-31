"""Registry-definition binding proof for the Cl@ve Móvil diagnostic write path.

The Cl@ve Móvil authenticator persists a failure-triage diagnostic as an
encrypted secure object. Its ``namespace``, ``classification``, and envelope
``schema_version`` MUST be single-sourced from the
:class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`
``CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE`` rather than restated as literals in the
auth adapter modules. The page-flow reads ``.sensitivity`` / ``.schema_version``
off that def and takes its namespace from the module-local
``_clave_movil_support.DIAGNOSTIC_NAMESPACE`` alias, which is itself derived from
``def.namespace``.

This is a write-path proof, not a bare constant-equality assertion: it persists
one diagnostic row through the exact symbols the page-flow save uses, then reads
the raw :class:`SecureObjectRow` back from the encrypted SQL backend and asserts
the persisted namespace, classification, and schema_version equal exactly what
the registry def declares. If any auth consumer ever re-hardcoded a divergent
namespace, sensitivity, or version, the persisted row would disagree with the
registry authority and this gate would fail.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from ......core import external_constants
from ......tests.secure_sql import isolated_runtime_profile
from .....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from .....persistence.storage.secure_object_namespaces import CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE
from .....persistence.storage.sql import SecureObjectRow
from .....persistence.storage.sql.session import session_scope
from ..clave_movil_support import DIAGNOSTIC_NAMESPACE, mint_diagnostic_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_BUCKET_ID = "1f6b0000-0000-4000-8000-00000000c0c0"


def test_clave_movil_support_namespace_alias_resolves_to_registry_def() -> None:
    """The module-local namespace alias the page-flow saves under is the def's namespace."""

    assert CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace == DIAGNOSTIC_NAMESPACE


def test_core_clave_movil_diagnostic_namespace_symbol_is_deleted() -> None:
    """The retired core string is gone; the storage registry def is the sole authority."""

    assert not hasattr(external_constants, "CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE")


def test_persisted_diagnostic_row_carries_registry_declared_metadata(tmp_path: Path) -> None:
    """A diagnostic saved through the page-flow's symbols persists the def's metadata."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        payload = {
            "diagnostic_id": "diag-binding-proof",
            "reason": "namespace-binding-proof",
            "captured_at": datetime(2026, 5, 26, 9, 0, tzinfo=UTC).isoformat(),
        }
        secure_object_repository_for_active_bucket().save(
            namespace=DIAGNOSTIC_NAMESPACE,
            object_key=payload["diagnostic_id"],
            classification=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.sensitivity,
            schema_version=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.schema_version,
            written_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
            payload=json.dumps(payload, sort_keys=True).encode(),
        )

        with session_scope(profile.repository._engine) as session:
            rows = [
                row
                for row in session.execute(select(SecureObjectRow)).scalars().all()
                if row.namespace == CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace
            ]

        assert len(rows) == 1, (
            f"expected one diagnostic row under {CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace!r}, saw {len(rows)}"
        )
        row = rows[0]
        assert row.classification == CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.sensitivity.value, (
            f"persisted classification {row.classification!r} diverges from registry def "
            f"{CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.sensitivity.value!r}"
        )
        assert row.schema_version == CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.schema_version, (
            f"persisted schema_version {row.schema_version} diverges from registry def "
            f"{CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.schema_version}"
        )


def test_rapid_diagnostic_captures_keep_distinct_encrypted_rows(tmp_path: Path) -> None:
    """One UTC capture instant cannot collapse distinct encrypted diagnostics."""

    captured_at = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)
    diagnostic_ids = tuple(mint_diagnostic_id(captured_at) for _ in range(8))

    assert len(set(diagnostic_ids)) == len(diagnostic_ids)
    assert all(diagnostic_id.startswith("20260802T090000.000000Z-") for diagnostic_id in diagnostic_ids)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        for sequence, diagnostic_id in enumerate(diagnostic_ids):
            payload = {
                "diagnostic_id": diagnostic_id,
                "reason": f"rapid-capture-{sequence}",
                "captured_at": captured_at.isoformat(),
            }
            secure_object_repository_for_active_bucket().save(
                namespace=DIAGNOSTIC_NAMESPACE,
                object_key=diagnostic_id,
                classification=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.sensitivity,
                schema_version=CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.schema_version,
                written_at=captured_at,
                payload=json.dumps(payload, sort_keys=True).encode(),
            )

        with session_scope(profile.repository._engine) as session:
            rows = [
                row
                for row in session.execute(select(SecureObjectRow)).scalars().all()
                if row.namespace == CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE.namespace
            ]

    assert len(rows) == len(diagnostic_ids)
