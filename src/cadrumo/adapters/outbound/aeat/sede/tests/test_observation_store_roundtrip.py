"""Strict roundtrip across the ``FiledDeclaracionObservationStore`` boundary.

Persists :class:`FiledDeclaracionObservation` envelopes under the
``cadrumo.outbound.aeat.sede.filed_declaration.observations`` namespace and
raw artefact bodies under
``cadrumo.outbound.aeat.sede.filed_declaration.artefacts``. Both sinks
operate at ``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture populates non-default values on every
optional field on :class:`FiledDeclaracionObservation`
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

from ......core import CasillaId, CasillaValueKind, Period, validated_casilla_id
from ......core.config import Settings
from ......tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from .._iva_compensation_wallet import IVA_COMPENSATION_WALLET_URL
from .._observation_store import FiledDeclaracionObservationStore
from .._schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
    ObservedCasillaValue,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_BUCKET_ID = "83a88c7e-9334-477e-83a8-40856124b522"  # was 'sede-observation'
_AEAT = Settings.external_constants().aeat
_COTEJO_DOCUMENT_URL = f"{_AEAT.domains.www6}{_AEAT.sede_paths.cotejo_document}"
_M100_BASE_LIQUIDABLE_CASILLA: CasillaId = validated_casilla_id("0500", surface="_M100_BASE_LIQUIDABLE_CASILLA")


def _populated_observation(artefact: FiledDeclaracionArtefact) -> FiledDeclaracionObservation:
    return FiledDeclaracionObservation(
        modelo="100",
        ejercicio=2023,
        period=Period.from_year_and_code(2023, "0A"),
        expediente_id="202310013522456T",
        status="PRESENTADA",
        presented_at=datetime(2024, 6, 30, 12, 34, 56, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(artefact,),
        casillas=(
            ObservedCasillaValue(
                casilla_id=_M100_BASE_LIQUIDABLE_CASILLA,
                value="42500.00",
                value_kind=CasillaValueKind.NUMERIC,
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
) -> None:
    """A populated observation + artefact round-trips through the encrypted store."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")

        body = b"%PDF-1.7 sede declaration sample body for roundtrip witness"
        artefact = FiledDeclaracionArtefact(
            kind="declaration_pdf",
            source_url=AnyHttpUrl(f"{_COTEJO_DOCUMENT_URL}?CSV=TUD4V9XAUV7QJ8QV"),
            content_type="application/pdf",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC),
        )
        observation_key = (
            "100",
            2023,
            Period.from_year_and_code(2023, "0A"),
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


def test_filed_declaration_observation_dropped_artefacts_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: stripping ``artefacts`` to empty must surface.

    :class:`FiledDeclaracionObservation` enforces
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

    from sqlalchemy import select

    from .....persistence.storage.sql import SecureObjectRow
    from .....persistence.storage.sql.session import session_scope
    from .._observation_store import _OBSERVATION_NAMESPACE

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")

        body = b"%PDF-1.7 sede declaration sample body for anti-tautology"
        artefact = FiledDeclaracionArtefact(
            kind="declaration_pdf",
            source_url=AnyHttpUrl(f"{_COTEJO_DOCUMENT_URL}?CSV=TUD4V9XAUV7QJ8QV"),
            content_type="application/pdf",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC),
        )
        observation_key = ("100", 2023, Period.from_year_and_code(2023, "0A"), "202310013522456T")
        persisted_artefact = store.persist_artefact(observation_key, artefact, body)
        observation = _populated_observation(persisted_artefact)
        logical_path = store.persist_observation(observation)

        with session_scope(profile.repository._engine) as session:
            all_rows = session.execute(select(SecureObjectRow)).scalars().all()
            obs_rows = [r for r in all_rows if r.namespace == _OBSERVATION_NAMESPACE]
            assert len(obs_rows) == 1, (
                f"expected one observation row, found {len(obs_rows)} "
                f"(namespaces: {sorted({r.namespace for r in all_rows})})"
            )
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == _OBSERVATION_NAMESPACE,
        )

        def mutate(envelope):
            payload = envelope["payload"]
            assert payload.get("artefacts"), (
                "fixture must serialise a non-empty artefacts tuple for this proof test to be meaningful"
            )
            payload["artefacts"] = []

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            store.load_observation(logical_path)


def test_iva_wallet_observation_roundtrips_through_encrypted_store(
    tmp_path: Path,
) -> None:
    """An AEAT IVA wallet observation round-trips as financial evidence."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        captured_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
        observation = IvaCompensationWalletObservation(
            taxpayer_nif="12345678Z",
            authenticated_identity="12345678Z",
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            rows=(
                IvaCompensationWalletRow(
                    generation_year=2026,
                    generation_period=Period.from_year_and_code(2026, "1T"),
                    generated_amount=Decimal("1200"),
                    applied_amount=Decimal("0"),
                    pending_amount=Decimal("1200"),
                    raw_label="2026 | 1T | 1200 | 0 | 1200",
                ),
            ),
            total_pending=Decimal("1200"),
            source_url=AnyHttpUrl(IVA_COMPENSATION_WALLET_URL),
            captured_at=captured_at,
            raw_sha256="b" * 64,
        )

        logical_path = store.persist_iva_wallet_observation(observation)
        loaded = store.load_iva_wallet_observation(logical_path)

        assert loaded == observation
        assert loaded.rows[0].generation_period == Period.from_year_and_code(2026, "1T")
        assert loaded.total_pending == Decimal("1200")
        assert loaded.raw_sha256 == "b" * 64
