"""Strict roundtrip across the ``FiledDeclarationObservationStore`` boundary.

Persists :class:`FiledDeclarationObservation` envelopes under the
``aeat.outbound.aeat.sede.filed_declaration.observations`` namespace and
raw artefact bodies under
``aeat.outbound.aeat.sede.filed_declaration.artefacts``. Both sinks
operate at ``SensitivityClass.FINANCIAL``.

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
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from .....core.config import Settings
from ....persistence.storage import EphemeralMasterKeyProvider
from ....persistence.storage.sql import SecureObjectRepository
from ....persistence.storage.sql._orm import Base
from ....persistence.storage.sql.engine import create_engine_from_settings
from ._observation_store import FiledDeclarationObservationStore
from ._schema import (
    FiledDeclarationArtefact,
    FiledDeclarationObservation,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
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
    with provider:
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


def test_filed_declaration_observation_dropped_artefacts_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anti-tautology proof: stripping ``artefacts`` to empty must surface.

    :class:`FiledDeclarationObservation` enforces
    ``artefacts: tuple[..., ...] = Field(min_length=1)`` — every
    persisted observation MUST carry at least one artefact (the source
    PDF or register row that proves AEAT served it). A persisted
    observation whose artefacts tuple is silently emptied would
    invalidate the entire content-addressing chain that proves the
    observation reflects what AEAT actually filed.

    Persists an observation, reaches into ``SecureObjectRow`` via
    ``session_scope``, surgically empties the ``artefacts`` tuple in
    the encrypted JSON envelope, and asserts the load path catches
    the drift via the ``min_length=1`` constraint.

    If this test passes silently with an empty artefacts tuple, the
    observation store's evidence-of-AEAT-serve contract is
    tautological and the boundary cannot be trusted as a filed-
    observation audit trail.
    """

    import json as _json

    from sqlalchemy import select

    from ....persistence.storage.sql._orm import SecureObjectRow
    from ....persistence.storage.sql.session import session_scope
    from ._observation_store import _OBSERVATION_NAMESPACE

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "sede-observation-anti-tautology.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)
            store = FiledDeclarationObservationStore(tmp_path / "sede-cache")

            body = b"%PDF-1.7 sede declaration sample body for anti-tautology"
            artefact = FiledDeclarationArtefact(
                kind="declaration_pdf",
                source_url=AnyHttpUrl(
                    "https://www.agenciatributaria.gob.es/wlpl/KATA-APLI/cotejo/CotejoDocIdSv?CSV=TUD4V9XAUV7QJ8QV"
                ),
                content_type="application/pdf",
                byte_count=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                captured_at=datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC),
            )
            observation_key = ("100", 2023, "0A", "202310013522456T")
            persisted_artefact = store.persist_artefact(observation_key, artefact, body)
            observation = _populated_observation(persisted_artefact)
            logical_path = store.persist_observation(observation)

            with session_scope(engine) as session:
                all_rows = session.execute(select(SecureObjectRow)).scalars().all()
                obs_rows = [r for r in all_rows if r.namespace == _OBSERVATION_NAMESPACE]
                assert len(obs_rows) == 1, (
                    f"expected one observation row, found {len(obs_rows)} "
                    f"(namespaces: {sorted({r.namespace for r in all_rows})})"
                )
                row = obs_rows[0]
                envelope = _json.loads(row.payload.decode("utf-8"))
                payload = envelope["payload"]
                assert payload.get("artefacts"), (
                    "fixture must serialise a non-empty artefacts tuple for "
                    "this proof test to be meaningful"
                )
                payload["artefacts"] = []
                row.payload = _json.dumps(envelope).encode("utf-8")

            regression_caught = False
            try:
                store.load_observation(logical_path)
            except Exception:
                regression_caught = True
            assert regression_caught, (
                "anti-tautology proof failed: stripping artefacts to empty "
                "did NOT surface on load. The observation store's evidence-"
                "of-AEAT-serve contract is tautological and the boundary "
                "cannot be trusted as a filed-observation audit trail."
            )
        finally:
            engine.dispose()


def test_iva_wallet_observation_roundtrips_through_encrypted_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An AEAT IVA wallet observation round-trips as financial evidence."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "iva-wallet-observation-roundtrip.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)
            store = FiledDeclarationObservationStore(tmp_path / "sede-cache")
            captured_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
            observation = IvaCompensationWalletObservation(
                taxpayer_nif="12345678Z",
                authenticated_identity="12345678Z",
                target_year=2026,
                target_period="2T",
                rows=(
                    IvaCompensationWalletRow(
                        generation_year=2026,
                        generation_period="1T",
                        generated_amount=Decimal("1200"),
                        applied_amount=Decimal("0"),
                        pending_amount=Decimal("1200"),
                        raw_label="2026 | 1T | 1200 | 0 | 1200",
                    ),
                ),
                total_pending=Decimal("1200"),
                source_url=AnyHttpUrl("https://www1.agenciatributaria.gob.es/wlpl/DAI3-RUTI/CarteraCuotas"),
                captured_at=captured_at,
                raw_sha256="b" * 64,
            )

            logical_path = store.persist_iva_wallet_observation(observation)
            loaded = store.load_iva_wallet_observation(logical_path)

            assert loaded == observation
            assert loaded.rows[0].generation_period == "1T"
            assert loaded.total_pending == Decimal("1200")
            assert loaded.raw_sha256 == "b" * 64
        finally:
            engine.dispose()
