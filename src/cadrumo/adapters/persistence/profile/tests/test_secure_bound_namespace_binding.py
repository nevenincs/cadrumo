"""Registry-definition binding proof for a SecureBoundRepository consumer.

The ``SecureBoundRepository`` subclasses (justificante, submission, filing
drafts) declare their ``namespace`` / ``sensitivity`` / ``schema_version``
ClassVars sourced from their registry
:class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`, not
hardcoded literals. This drives the real ``JustificanteRepository.save`` (an
AUDIT-class consumer) against a genuine encrypted bucket and reads the raw
:class:`SecureObjectRow` back, asserting the persisted classification and
schema_version equal exactly what ``JUSTIFICANTE_METADATA_NAMESPACE`` declares —
so a re-hardcoded divergent metadata literal would surface here (or be refused
outright by the substrate write policy).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl
from sqlalchemy import select

from .....core.period import Period
from .....domain.justificante import Justificante
from .....tests.aeat_literal_fixtures import justificante_wlpl_cotejo_url
from .....tests.secure_sql import isolated_runtime_profile
from ....persistence.storage.sql import SecureObjectRow
from ....persistence.storage.sql.session import session_scope
from ...storage._secure_object_namespaces import JUSTIFICANTE_METADATA_NAMESPACE
from ..justificante import JustificanteRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_justificante_row_carries_registry_declared_metadata(tmp_path: Path) -> None:
    """A justificante saved through its repository persists the def's metadata."""

    record = Justificante(
        csv="ABCD12345678EFGH",
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        ejercicio="2025",
        presentation_id="PRES-2025-001-XYZ",
        presented_at=datetime(2026, 5, 27, 11, 15, 0, tzinfo=UTC),
        tax_id="12345678Z",
        total_a_ingresar=Decimal("12345.67"),
        total_a_devolver=None,
        verification_url=AnyHttpUrl(justificante_wlpl_cotejo_url("ABCD12345678EFGH")),
        source_pdf_path=Path("justificantes/303-2025-1T-ABCD.pdf"),
        source_pdf_sha256="a" * 64,
        parsed_at=datetime(2026, 5, 27, 11, 15, 0, tzinfo=UTC),
    )

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        JustificanteRepository().save(record)

        with session_scope(profile.repository._engine) as session:
            rows = [
                row
                for row in session.execute(select(SecureObjectRow)).scalars().all()
                if row.namespace == JUSTIFICANTE_METADATA_NAMESPACE.namespace
            ]

    assert len(rows) == 1, f"expected one justificante row, saw {len(rows)}"
    assert rows[0].classification == JUSTIFICANTE_METADATA_NAMESPACE.sensitivity.value
    assert rows[0].schema_version == JUSTIFICANTE_METADATA_NAMESPACE.schema_version
