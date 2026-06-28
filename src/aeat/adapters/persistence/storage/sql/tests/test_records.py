"""Unit tests for the public pydantic record models.

Asserts the strict-mode validation, frozen-mutation refusal, enum
coercion, and length invariants on the SQL-layer record types
(:class:`ModeloCatalogueRecord`, :class:`PortalRecord`,
:class:`CorpusArtifactRecord`).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ......tests.aeat_literal_fixtures import PDF_MODELO_130_2024_PATH_FIXTURE, aeat_url, sede_pdf_url
from .. import CorpusArtifactRecord, ModeloCatalogueRecord, PortalAuthMethod, PortalRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _corpus_artifact_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "year": 2024,
        "modelo_id": 1,
        "file_path": "corpus/2024/modelos/130/modelo-130-2024.pdf",
        "sha256": "a" * 64,
        "source_url": sede_pdf_url(PDF_MODELO_130_2024_PATH_FIXTURE),
        "fetched_at": datetime(2026, 4, 12, tzinfo=UTC),
    }
    payload.update(overrides)
    return payload


def test_modelo_record_strict_rejects_coercion() -> None:
    """Strict mode must refuse silent int→str coercion."""
    with pytest.raises(ValidationError):
        ModeloCatalogueRecord.model_validate({"id": 1, "identifier": 130, "name": "Pagos fraccionados"})


def test_records_are_frozen() -> None:
    """Frozen records must reject mutation."""
    record = ModeloCatalogueRecord(identifier="MODELO_130", name="Pagos fraccionados")
    with pytest.raises(ValidationError):
        record.identifier = "MODELO_303"


def test_portal_record_requires_enum_auth_method() -> None:
    """PortalRecord.auth_method is a strict enum, not a bare string."""
    record = PortalRecord(
        identifier="SEDE_ROOT",
        base_url=aeat_url("sede", "/").rstrip("/"),
        auth_method=PortalAuthMethod.CERTIFICATE,
        label="Sede electrónica",
    )
    assert record.auth_method is PortalAuthMethod.CERTIFICATE

    with pytest.raises(ValidationError):
        PortalRecord.model_validate(
            {
                "identifier": "SEDE_ROOT",
                "base_url": aeat_url("sede", "/").rstrip("/"),
                "auth_method": "certificate",
                "label": "Sede electrónica",
            }
        )


@pytest.mark.parametrize("invalid_sha256", ["short", "a" * 63, "a" * 65])
def test_corpus_artifact_record_requires_sha256_length(invalid_sha256: str) -> None:
    """CorpusArtifactRecord.sha256 must be exactly 64 hex characters."""
    ok_digest = "a" * 64
    record = CorpusArtifactRecord.model_validate(_corpus_artifact_payload(sha256=ok_digest))
    assert record.sha256 == ok_digest

    with pytest.raises(ValidationError):
        CorpusArtifactRecord.model_validate(_corpus_artifact_payload(sha256=invalid_sha256))
