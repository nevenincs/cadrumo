"""Strict roundtrip across the Modelo 100 borrador snapshot repository.

Persists :class:`Borrador100Snapshot` records under
``cadrumo.application.live.borrador_100_snapshot`` at
``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture populates ``binding_values`` with one
``Decimal`` and one ``str`` value to stress the
``_BorradorValue = Decimal | str`` union — the same drift pattern that
silently coerced ``UserProfileFact.value`` Decimals to ``str`` on JSON
re-parse. Also exercises the ``SUPERSEDED`` lifecycle (a state the
model_validator enforces with ``superseded_by_snapshot_id``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.errors import StorageValidationError
from ....core import Period
from ....tests.aeat_literal_fixtures import aeat_url, configured_template_path
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    SnapshotLifecycleState,
    derive_borrador_100_snapshot_id,
)
from ..errors import LiveApplicationInputError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PERIOD = Period.from_year_and_code(2024, "0A")
_BUCKET_ID = "50505050-5050-4050-8050-505050505050"
_OTHER_BUCKET_ID = "51515151-5151-4151-8151-515151515151"


def _borrador_detail_url(expediente_id: str) -> str:
    return aeat_url(
        "www2",
        configured_template_path(
            "sede_paths",
            "borrador_100_detail_template",
            year=2024,
            expediente_id=expediente_id,
        ),
    )


def _populated_snapshot(*, bucket_id: str) -> Borrador100Snapshot:
    captured_at = datetime(2024, 4, 12, 11, 30, 0, tzinfo=UTC)
    binding_values = {
        "casilla.0500": Decimal("42500.00"),
        "casilla.0501": Decimal("8750.50"),
        "casilla.identity.declarant_label": "Persona Prueba",
    }
    source_url = _borrador_detail_url("202410013522456T")
    snapshot_id = derive_borrador_100_snapshot_id(
        filing_year=2024,
        period=_PERIOD,
        captured_at=captured_at,
        source_url=source_url,
        binding_values=binding_values,
    )
    return Borrador100Snapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        modelo="100",
        filing_year=2024,
        period=_PERIOD,
        captured_at=captured_at,
        source_url=source_url,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=binding_values,
    )


def test_borrador_100_snapshot_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A populated borrador snapshot round-trips through the encrypted store."""

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repo = Borrador100SnapshotRepository(bucket_id=bucket_id)
        original = _populated_snapshot(bucket_id=bucket_id)
        repo.save(original)
        loaded = repo.load(original.snapshot_id)

        assert profile.paths.database_file.is_file()
        assert loaded == original
        # Witness the Decimal entries survive the union resolution.
        assert loaded.binding_values["casilla.0500"] == Decimal("42500.00")
        assert isinstance(loaded.binding_values["casilla.0500"], Decimal)
        assert loaded.binding_values["casilla.0501"] == Decimal("8750.50")
        assert isinstance(loaded.binding_values["casilla.0501"], Decimal)
        # And the str entries are still str (not coerced to Decimal).
        assert loaded.binding_values["casilla.identity.declarant_label"] == "Persona Prueba"
        assert isinstance(loaded.binding_values["casilla.identity.declarant_label"], str)


def test_borrador_100_repository_default_refuses_active_bucket_mismatch(tmp_path: Path) -> None:
    """A repository for bucket-b must not write logical bucket-b rows into bucket-a storage."""

    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID),
        pytest.raises(StorageValidationError, match=r"errors\.storage\.runtime\.not_ready"),
    ):
        Borrador100SnapshotRepository(bucket_id=_OTHER_BUCKET_ID)


def test_borrador_100_superseded_state_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A SUPERSEDED borrador snapshot round-trips with its successor pointer.

    The model_validator on :class:`Borrador100Snapshot` enforces that a
    SUPERSEDED state requires a non-None ``superseded_by_snapshot_id``.
    Exercising the full state union via a SUPERSEDED fixture witnesses
    that the supersession pointer survives the encrypted envelope
    boundary — a save-drops-pointer drift would surface at load time
    as the model_validator rejecting the rehydrated record.
    """

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        repo = Borrador100SnapshotRepository(bucket_id=bucket_id)
        # First save the successor so the supersession pointer references
        # a real id; then build and save the superseded predecessor.
        successor = _populated_snapshot(bucket_id=bucket_id)
        repo.save(successor)

        captured_at = datetime(2024, 3, 11, 9, 15, 0, tzinfo=UTC)
        binding_values = {
            "casilla.0500": Decimal("39800.00"),
            "casilla.identity.declarant_label": "Persona Prueba",
        }
        source_url = _borrador_detail_url("202410013522401X")
        snapshot_id = derive_borrador_100_snapshot_id(
            filing_year=2024,
            period=_PERIOD,
            captured_at=captured_at,
            source_url=source_url,
            binding_values=binding_values,
        )
        original = Borrador100Snapshot(
            snapshot_id=snapshot_id,
            bucket_id=bucket_id,
            modelo="100",
            filing_year=2024,
            period=_PERIOD,
            captured_at=captured_at,
            source_url=source_url,
            state=SnapshotLifecycleState.SUPERSEDED,
            binding_values=binding_values,
            superseded_by_snapshot_id=successor.snapshot_id,
        )
        repo.save(original)
        loaded = repo.load(original.snapshot_id)

        assert loaded == original
        assert loaded.state is SnapshotLifecycleState.SUPERSEDED
        # Per-field witness: the supersession pointer is the load-bearing
        # field for this state; a silent drop would either trip the
        # model_validator on reload or surface as inequality on this
        # specific assertion.
        assert loaded.superseded_by_snapshot_id == successor.snapshot_id


def test_borrador_100_dropped_superseded_pointer_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: deleting the supersession pointer must surface.

    Builds a SUPERSEDED snapshot, persists it, then surgically mutates
    the on-disk JSON envelope payload to delete the
    ``superseded_by_snapshot_id`` field, and asserts that the load
    path rejects the record (the model_validator requires the field
    on SUPERSEDED state). If this test ever passes silently with a
    dropped field, every borrador roundtrip in the suite is
    tautological.
    """

    from sqlalchemy import select

    from ....adapters.persistence.storage.sql import SecureObjectRow

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repo = Borrador100SnapshotRepository(bucket_id=bucket_id)

        successor = _populated_snapshot(bucket_id=bucket_id)
        repo.save(successor)

        captured_at = datetime(2024, 3, 11, 9, 15, 0, tzinfo=UTC)
        binding_values = {
            "casilla.0500": Decimal("39800.00"),
            "casilla.identity.declarant_label": "Persona Prueba",
        }
        source_url = _borrador_detail_url("202410013522401X")
        snapshot_id = derive_borrador_100_snapshot_id(
            filing_year=2024,
            period=_PERIOD,
            captured_at=captured_at,
            source_url=source_url,
            binding_values=binding_values,
        )
        original = Borrador100Snapshot(
            snapshot_id=snapshot_id,
            bucket_id=bucket_id,
            modelo="100",
            filing_year=2024,
            period=_PERIOD,
            captured_at=captured_at,
            source_url=source_url,
            state=SnapshotLifecycleState.SUPERSEDED,
            binding_values=binding_values,
            superseded_by_snapshot_id=successor.snapshot_id,
        )
        repo.save(original)

        # Surgically delete ``superseded_by_snapshot_id`` from the
        # persisted JSON envelope payload, then attempt to load. The
        # column accessor handles encrypt/decrypt automatically.
        from ..borrador_100 import (
            BORRADOR_100_SNAPSHOT_NAMESPACE,
            borrador_100_snapshot_object_key,
        )

        object_key = borrador_100_snapshot_object_key(bucket_id, original.snapshot_id)
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == BORRADOR_100_SNAPSHOT_NAMESPACE,
            SecureObjectRow.object_key == object_key,
        )

        def mutate(decoded):
            assert "superseded_by_snapshot_id" in decoded["payload"], (
                "fixture must serialise superseded_by_snapshot_id into the "
                "envelope payload for this test to be meaningful"
            )
            del decoded["payload"]["superseded_by_snapshot_id"]

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        # With the field absent, the model_validator on
        # Borrador100Snapshot must reject the rehydrated record (the
        # SUPERSEDED state requires the pointer).
        from pydantic import ValidationError

        with pytest.raises(
            (ValidationError, LiveApplicationInputError),
            match=r"state_supersession_pointer_required|superseded",
        ):
            repo.load(original.snapshot_id)
