"""Tests for filed-declaration observation persistence."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest
from pydantic import AnyHttpUrl

from ......adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ......core import CasillaValueKind, Period
from ......core.casilla_id import CasillaId, validated_casilla_id
from ......core.config import Settings
from ......core.directory_scan import DirectoryEntryKind, scan_directory
from ......tests.secure_sql import TestRuntimeProfile
from ..errors import SedeValidationError
from ..observation_store import FiledDeclaracionObservationStore
from ..schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, ObservedCasillaValue

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_BUCKET_ID = "83a88c7e-9334-477e-83a8-40856124b522"  # was 'sede-observation'
_AEAT = Settings.external_constants().aeat
_DECLARATIONS_LISTING_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.declarations_listing}"
_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_CASILLA")
_M303_PRINTED_COMPENSATION_REFERENCE_CASILLA: CasillaId = validated_casilla_id(
    "110",
    surface="_M303_PRINTED_COMPENSATION_REFERENCE_CASILLA",
)


active_storage = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="active_storage")


def test_store_persists_filed_data_as_ciphertext_and_roundtrips_through_store_api(
    tmp_path: Path,
    active_storage: TestRuntimeProfile,
) -> None:
    root = tmp_path / "observations"
    store = FiledDeclaracionObservationStore(root)
    body = b"1302026-1T-submitted-file"
    artefact = _artefact(kind="submitted_file", body=body, content_type="text/plain")

    stored = store.persist_artefact(
        ("130", 2026, Period.from_year_and_code(2026, "1T"), "202610013522222A"), artefact, body
    )
    observation = FiledDeclaracionObservation(
        modelo="130",
        ejercicio=2026,
        period=Period.from_year_and_code(2026, "1T"),
        expediente_id="202610013522222A",
        status="ALTA",
        presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(stored,),
        casillas=(
            ObservedCasillaValue(
                casilla_id=_M130_RESULTADO_CASILLA,
                value="12.34",
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="layout:field:19",
                confidence=1.0,
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
        registry_snapshot_id="130:2019-y-siguientes:2026:1T",
    )

    manifest_path = store.persist_observation(observation)

    assert stored.storage_ref is not None
    assert stored.storage_ref.startswith("secure-object:financial:")
    assert store.load_artefact(stored.storage_ref) == body
    assert store.load_observation(manifest_path) == observation
    persisted_bytes = b"\n".join(
        path.read_bytes() for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES)
    )
    assert body not in persisted_bytes
    assert b"12345678Z" not in persisted_bytes
    assert b"12.34" not in persisted_bytes
    assert b"202610013522222A" not in persisted_bytes
    from ......tests.secure_sql import read_db_at_rest_bytes

    database_bytes = read_db_at_rest_bytes(active_storage.paths.database_file)
    assert body not in database_bytes
    assert b"12345678Z" not in database_bytes
    assert b"12.34" not in database_bytes
    assert b"202610013522222A" not in database_bytes
    persisted_paths = "\n".join(
        str(path.relative_to(root).as_posix()) for path in scan_directory(root, pattern="*", recursive=True)
    )
    assert "12345678Z" not in persisted_paths
    assert "202610013522222A" not in persisted_paths
    assert "130/2026/1T" not in persisted_paths


def test_store_rejects_artefact_body_that_does_not_match_metadata(
    tmp_path: Path,
    active_storage: TestRuntimeProfile,
) -> None:
    del active_storage
    store = FiledDeclaracionObservationStore(tmp_path / "observations")
    artefact = _artefact(kind="register_row", body=b"abc", content_type="application/json")

    with pytest.raises(ValueError, match="byte count"):
        store.persist_artefact(
            ("130", 2026, Period.from_year_and_code(2026, "1T"), "202610013522222A"), artefact, b"abcd"
        )


def test_store_rejects_observation_with_printed_number_casilla_reference(
    tmp_path: Path,
    active_storage: TestRuntimeProfile,
) -> None:
    del active_storage
    store = FiledDeclaracionObservationStore(tmp_path / "observations")
    body = b"3032024-4T-submitted-file"
    artefact = _artefact(kind="submitted_file", body=body, content_type="text/plain")
    observation = FiledDeclaracionObservation(
        modelo="303",
        ejercicio=2024,
        period=Period.from_year_and_code(2024, "4T"),
        expediente_id="202410013522222A",
        status="ALTA",
        presented_at=datetime(2025, 1, 20, 10, 0, 0, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(artefact,),
        casillas=(
            ObservedCasillaValue(
                casilla_id=_M303_PRINTED_COMPENSATION_REFERENCE_CASILLA,
                value="0.00",
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:casilla:110",
                confidence=1.0,
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
    )

    with pytest.raises(SedeValidationError, match=r"canonical casilla\.id"):
        store.persist_observation(observation)


def _artefact(
    *,
    kind: Literal["register_row", "submitted_file", "declaration_pdf", "justificante_pdf"],
    body: bytes,
    content_type: str,
) -> FiledDeclaracionArtefact:
    return FiledDeclaracionArtefact(
        kind=kind,
        source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
        content_type=content_type,
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
    )
