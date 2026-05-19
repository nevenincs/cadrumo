"""Tests for filed-declaration observation persistence."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Literal

import pytest
from pydantic import AnyHttpUrl

from ....persistence.storage import EphemeralMasterKeyProvider
from ....persistence.storage.sql.engine import dispose_engine
from ._observation_store import FiledDeclaracionObservationStore
from ._schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, ObservedCasillaValue

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


@pytest.fixture(autouse=True)
def _patch_secure_backend(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{tmp_path / 'aeat.db'}")
    try:
        yield
    finally:
        dispose_engine()


def test_store_persists_filed_data_as_ciphertext_and_roundtrips_through_store_api(tmp_path) -> None:
    root = tmp_path / "observations"
    provider = EphemeralMasterKeyProvider()
    store = FiledDeclaracionObservationStore(root, master_key_provider=provider)
    body = b"1302026-1T-submitted-file"
    artefact = _artefact(kind="submitted_file", body=body, content_type="text/plain")

    stored = store.persist_artefact(("130", 2026, "1T", "202610013522222A"), artefact, body)
    observation = FiledDeclaracionObservation(
        modelo="130",
        ejercicio=2026,
        period="1T",
        expediente_id="202610013522222A",
        status="ALTA",
        presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(stored,),
        casillas=(
            ObservedCasillaValue(
                casilla_id="19",
                value="12.34",
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
    persisted_bytes = b"\n".join(path.read_bytes() for path in root.rglob("*") if path.is_file())
    assert body not in persisted_bytes
    assert b"12345678Z" not in persisted_bytes
    assert b"12.34" not in persisted_bytes
    assert b"202610013522222A" not in persisted_bytes
    database_bytes = (tmp_path / "aeat.db").read_bytes()
    assert body not in database_bytes
    assert b"12345678Z" not in database_bytes
    assert b"12.34" not in database_bytes
    assert b"202610013522222A" not in database_bytes
    persisted_paths = "\n".join(str(path.relative_to(root).as_posix()) for path in root.rglob("*"))
    assert "12345678Z" not in persisted_paths
    assert "202610013522222A" not in persisted_paths
    assert "130/2026/1T" not in persisted_paths


def test_store_rejects_artefact_body_that_does_not_match_metadata(tmp_path) -> None:
    store = FiledDeclaracionObservationStore(
        tmp_path / "observations",
        master_key_provider=EphemeralMasterKeyProvider(),
    )
    artefact = _artefact(kind="register_row", body=b"abc", content_type="application/json")

    with pytest.raises(ValueError, match="byte count"):
        store.persist_artefact(("130", 2026, "1T", "202610013522222A"), artefact, b"abcd")


def _artefact(
    *,
    kind: Literal["register_row", "submitted_file", "declaration_pdf", "justificante_pdf"],
    body: bytes,
    content_type: str,
) -> FiledDeclaracionArtefact:
    return FiledDeclaracionArtefact(
        kind=kind,
        source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
        content_type=content_type,
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
    )
