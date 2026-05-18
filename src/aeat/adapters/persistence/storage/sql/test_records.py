"""Unit tests for the public pydantic record models.

Asserts the strict-mode validation, frozen-mutation refusal, enum
coercion, and length invariants on the SQL-layer record types
(:class:`ModeloRecord`, :class:`PortalRecord`,
:class:`CorpusArtifactRecord`).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from . import CorpusArtifactRecord, ModeloRecord, PortalAuthMethod, PortalRecord

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_modelo_record_strict_rejects_coercion() -> None:
    """Strict mode must refuse silent int→str coercion."""
    with pytest.raises(ValidationError):
        ModeloRecord.model_validate({"id": 1, "identifier": 130, "name": "Pagos fraccionados"})


def test_records_are_frozen() -> None:
    """Frozen records must reject mutation."""
    record = ModeloRecord(identifier="MODELO_130", name="Pagos fraccionados")
    with pytest.raises(ValidationError):
        setattr(record, "identifier", "MODELO_303")  # noqa: B010 — exercise frozen-model __setattr__


def test_portal_record_requires_enum_auth_method() -> None:
    """PortalRecord.auth_method is a strict enum, not a bare string."""
    record = PortalRecord(
        identifier="SEDE_ROOT",
        base_url="https://sede.agenciatributaria.gob.es",
        auth_method=PortalAuthMethod.CERTIFICATE,
        label="Sede electrónica",
    )
    assert record.auth_method is PortalAuthMethod.CERTIFICATE


def test_corpus_artifact_record_requires_sha256_length() -> None:
    """CorpusArtifactRecord.sha256 must be exactly 64 hex characters."""
    ok_digest = "a" * 64
    record = CorpusArtifactRecord(
        year=2024,
        modelo_id=1,
        file_path="corpus/2024/modelos/130/modelo-130-2024.pdf",
        sha256=ok_digest,
        source_url="https://sede.agenciatributaria.gob.es/modelo-130-2024.pdf",
        fetched_at=datetime(2026, 4, 12, tzinfo=UTC),
    )
    assert record.sha256 == ok_digest

    with pytest.raises(ValidationError):
        CorpusArtifactRecord(
            year=2024,
            modelo_id=1,
            file_path="corpus/2024/modelos/130/modelo-130-2024.pdf",
            sha256="short",
            source_url="https://sede.agenciatributaria.gob.es/modelo-130-2024.pdf",
            fetched_at=datetime(2026, 4, 12, tzinfo=UTC),
        )
