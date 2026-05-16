"""Strict roundtrip across the ``FiledDeclarationObservationStore`` boundary.

Persists :class:`FiledDeclarationObservation` envelopes under the
``aeat.outbound.aeat.sede.filed_declaration.observations`` namespace and
raw artefact bodies under
``aeat.outbound.aeat.sede.filed_declaration.artefacts``. Both sinks
operate at ``SensitivityClass.FINANCIAL``. Flagged as untested in the
persistence-boundary identity audit.

Anti-tautology: the fixture populates non-default values on every
optional field on :class:`FiledDeclarationObservation`
(``casillas``, ``metadata``, ``extraction_coverage``,
``registry_snapshot_id``) plus the optional ``storage_ref`` on the
artefact. A drift that silently dropped any of these on save would
surface as inequality on the loaded observation.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from ....persistence.storage.sql import SecureObjectRepository
from ....persistence.storage.sql._orm import Base
from ....persistence.storage.sql.engine import create_engine_from_settings
from .....core.config import Settings
from ._observation_store import FiledDeclarationObservationStore
from ._schema import (
    FiledDeclarationArtefact,
    FiledDeclarationObservation,
    ObservedCasillaValue,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_observation(artefact: FiledDeclarationArtefact) -> FiledDeclarationObservation:
    return FiledDeclarationObservation(
        modelo="100",
        ejercicio=2023,
        period="0A",
        expediente_id="202310013522456T",
        status="PRESENTADA",
        presented_at=datetime(2024, 6, 30, 12, 34, 56, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(artefact,),
        casillas=(
            ObservedCasillaValue(
                casilla_id="0500",
                value="42500.00",
                source_artefact_kind="declaration_pdf",
                source_locator="page=3,row=Casilla 500",
                confidence=0.87,
            ),
        ),
        metadata={"capture_session": "sede-2024-06-30-A"},
        extraction_coverage={"declaration_pdf": 0.95},
        registry_snapshot_id="registry-2023-snapshot-04",
    )


def test_filed_declaration_observation_roundtrips_through_encrypted_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A populated observation + artefact round-trips through the encrypted store."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "sede-observation-roundtrip.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)
        store = FiledDeclarationObservationStore(tmp_path / "sede-cache")

        body = b"%PDF-1.7 sede declaration sample body for roundtrip witness"
        artefact = FiledDeclarationArtefact(
            kind="declaration_pdf",
            source_url=AnyHttpUrl("https://www.agenciatributaria.gob.es/wlpl/KATA-APLI/cotejo/CotejoDocIdSv?CSV=TUD4V9XAUV7QJ8QV"),
            content_type="application/pdf",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC),
        )
        observation_key = (
            "100",
            2023,
            "0A",
            "202310013522456T",
        )

        persisted_artefact = store.persist_artefact(observation_key, artefact, body)
        assert persisted_artefact.storage_ref is not None
        # The persisted artefact carries the storage-ref the inbound
        # path will rehydrate from. Round-trip the body too.
        loaded_body = store.load_artefact(persisted_artefact.storage_ref)
        assert loaded_body == body

        observation = _populated_observation(persisted_artefact)
        logical_path = store.persist_observation(observation)
        loaded = store.load_observation(logical_path)

        assert loaded == observation
        # Per-field witnesses on the boundary-attacking optional axes.
        assert loaded.casillas[0].confidence == 0.87
        assert loaded.metadata == {"capture_session": "sede-2024-06-30-A"}
        assert loaded.extraction_coverage == {"declaration_pdf": 0.95}
        assert loaded.registry_snapshot_id == "registry-2023-snapshot-04"
        assert loaded.artefacts[0].storage_ref == persisted_artefact.storage_ref
    finally:
        engine.dispose()
        override_master_key_provider(None)
