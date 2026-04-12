"""Unit tests for the public pydantic record models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from pydantic import ValidationError

from aeat.storage import CorpusArtifactRecord, ModeloRecord, PortalAuthMethod, PortalRecord


@pytest.mark.unit
def test_modelo_record_strict_rejects_coercion() -> None:
    """Strict mode must refuse silent int→str coercion."""
    with pytest.raises(ValidationError):
        ModeloRecord(id=1, identifier=cast(str, 130), name="Pagos fraccionados")


@pytest.mark.unit
def test_records_are_frozen() -> None:
    """Frozen records must reject mutation."""
    record = ModeloRecord(identifier="MODELO_130", name="Pagos fraccionados")
    mutable: Any = record
    with pytest.raises(ValidationError):
        mutable.identifier = "MODELO_303"


@pytest.mark.unit
def test_portal_record_requires_enum_auth_method() -> None:
    """PortalRecord.auth_method is a strict enum, not a bare string."""
    record = PortalRecord(
        identifier="SEDE_ROOT",
        base_url="https://sede.agenciatributaria.gob.es",
        auth_method=PortalAuthMethod.CERTIFICATE,
        label="Sede electrónica",
    )
    assert record.auth_method is PortalAuthMethod.CERTIFICATE


@pytest.mark.unit
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
