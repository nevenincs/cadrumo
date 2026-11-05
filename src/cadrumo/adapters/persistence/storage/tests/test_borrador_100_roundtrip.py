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

from cadrumo.adapters.persistence.profile.snapshots import SecureSnapshotRepository
from cadrumo.adapters.persistence.storage.errors import SecureObjectUnreadableError, StorageValidationError
from cadrumo.adapters.persistence.storage.secure_object_namespaces import LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_runtime_profile,
    mutate_encrypted_secure_object_json,
    restamp_secure_object_schema_version,
)
from cadrumo.application.live.borrador_100 import (
    Borrador100Snapshot,
    BorradorSnapshotNotFoundError,
    borrador_100_snapshot_object_key,
    derive_borrador_100_snapshot_id,
)
from cadrumo.application.live.errors import LiveApplicationInputError
from cadrumo.application.live.snapshot_base import SnapshotLifecycleState
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.tests.aeat_literal_fixtures import aeat_url, configured_template_path

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_application]
_PERIOD = Period.from_year_and_code(2024, "0A")
_REGISTRY_SNAPSHOT_REF = RegistrySnapshotRef(
    modelo="100",
    revision_id="2024",
    modelo_year=2024,
    period="0A",
)
_BUCKET_ID = "50505050-5050-4050-8050-505050505050"
_CERTIFICATE = "renta-retencion-soportada-trabajo"
_RESIDENCE = "renta-profile-tax-residence-ccaa"
_OTHER_BUCKET_ID = "51515151-5151-4151-8151-515151515151"


def _borrador_repository(
    *,
    bucket_id: str,
    objects: SecureObjectRepository | None = None,
) -> SecureSnapshotRepository[Borrador100Snapshot]:
    """Build the concrete encrypted adapter for the application snapshot port."""
    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=Borrador100Snapshot,
        namespace_definition=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE,
        object_key=borrador_100_snapshot_object_key,
        not_found_factory=lambda snapshot_id: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_not_found",
            context={"snapshot_id": snapshot_id},
        ),
        ambiguous_prefix_factory=lambda snapshot_id, full_ids: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
        ),
        domain_label="borrador",
        input_error_cls=LiveApplicationInputError,
        objects=objects,
    )


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
        _CERTIFICATE: Decimal("8750.50"),
        _RESIDENCE: "madrid",
    }
    source_url = _borrador_detail_url("202410013522456T")
    snapshot_id = derive_borrador_100_snapshot_id(
        filing_year=2024,
        period=_PERIOD,
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
        source_url=source_url,
        binding_values=binding_values,
    )
    return Borrador100Snapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        modelo="100",
        filing_year=2024,
        period=_PERIOD,
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
        captured_at=captured_at,
        source_url=source_url,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=binding_values,
    )


def _save_superseded_original(
    repo: SecureSnapshotRepository[Borrador100Snapshot], bucket_id: str
) -> tuple[Borrador100Snapshot, Borrador100Snapshot]:
    """Save a successor first so the supersession pointer names a real id, then its superseded predecessor."""
    successor = _populated_snapshot(bucket_id=bucket_id)
    repo.save(successor)

    captured_at = datetime(2024, 3, 11, 9, 15, 0, tzinfo=UTC)
    binding_values = {
        _CERTIFICATE: Decimal("8120.00"),
        _RESIDENCE: "madrid",
    }
    source_url = _borrador_detail_url("202410013522401X")
    snapshot_id = derive_borrador_100_snapshot_id(
        filing_year=2024,
        period=_PERIOD,
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
        source_url=source_url,
        binding_values=binding_values,
    )
    original = Borrador100Snapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        modelo="100",
        filing_year=2024,
        period=_PERIOD,
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
        captured_at=captured_at,
        source_url=source_url,
        state=SnapshotLifecycleState.SUPERSEDED,
        binding_values=binding_values,
        superseded_by_snapshot_id=successor.snapshot_id,
    )
    repo.save(original)
    return successor, original


def test_borrador_100_snapshot_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """A populated borrador snapshot round-trips through the encrypted store."""

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repo = _borrador_repository(bucket_id=bucket_id)
        original = _populated_snapshot(bucket_id=bucket_id)
        repo.save(original)
        loaded = repo.load(original.snapshot_id)

        assert profile.paths.database_file.is_file()
        assert loaded == original
        # Witness the Decimal entries survive the union resolution.
        assert loaded.binding_values[_CERTIFICATE] == Decimal("8750.50")
        assert isinstance(loaded.binding_values[_CERTIFICATE], Decimal)
        # And the str entries are still str (not coerced to Decimal).
        assert loaded.binding_values[_RESIDENCE] == "madrid"
        assert isinstance(loaded.binding_values[_RESIDENCE], str)


def test_borrador_100_repository_default_refuses_active_bucket_mismatch(tmp_path: Path) -> None:
    """A repository for bucket-b must not write logical bucket-b rows into bucket-a storage."""

    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID),
        pytest.raises(StorageValidationError, match=r"errors\.storage\.runtime\.not_ready"),
    ):
        _borrador_repository(bucket_id=_OTHER_BUCKET_ID)


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
        repo = _borrador_repository(bucket_id=bucket_id)
        successor, original = _save_superseded_original(repo, bucket_id)
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

    from cadrumo.adapters.persistence.storage.sql.tables import secure_objects_table

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repo = _borrador_repository(bucket_id=bucket_id)

        _, original = _save_superseded_original(repo, bucket_id)

        # Surgically delete ``superseded_by_snapshot_id`` from the
        # persisted JSON envelope payload, then attempt to load. The
        # column accessor handles encrypt/decrypt automatically.
        object_key = borrador_100_snapshot_object_key(bucket_id, original.snapshot_id)
        stmt = select(secure_objects_table).where(
            secure_objects_table.c.namespace == LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.namespace,
            secure_objects_table.c.object_key == object_key,
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


def _snapshot_with_values(
    *, bucket_id: str, source_digit: str, binding_values: dict[str, Decimal | str]
) -> Borrador100Snapshot:
    source_url = "file-import:sha256:" + source_digit * 64
    return Borrador100Snapshot(
        snapshot_id=derive_borrador_100_snapshot_id(
            filing_year=2024,
            period=_PERIOD,
            registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
            source_url=source_url,
            binding_values=binding_values,
        ),
        bucket_id=bucket_id,
        modelo="100",
        filing_year=2024,
        period=_PERIOD,
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
        captured_at=datetime(2024, 4, 12, 11, 30, 0, tzinfo=UTC),
        source_url=source_url,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=binding_values,
    )


def test_borrador_100_text_and_decimal_values_keep_their_exact_type_through_storage(tmp_path: Path) -> None:
    """Text such as ``"09"`` stays text, a decimal keeps its scale, and a mixed mapping is preserved."""

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        repo = _borrador_repository(bucket_id=bucket_id)
        text_only = _snapshot_with_values(bucket_id=bucket_id, source_digit="1", binding_values={_RESIDENCE: "09"})
        decimal_only = _snapshot_with_values(
            bucket_id=bucket_id, source_digit="2", binding_values={_CERTIFICATE: Decimal("9.50")}
        )
        mixed = _snapshot_with_values(
            bucket_id=bucket_id,
            source_digit="3",
            binding_values={_CERTIFICATE: Decimal("9"), _RESIDENCE: "9", "renta-other": "0009.0"},
        )
        for snapshot in (text_only, decimal_only, mixed):
            repo.save(snapshot)

        loaded_text = repo.load(text_only.snapshot_id).binding_values[_RESIDENCE]
        assert loaded_text == "09"
        assert type(loaded_text) is str

        loaded_decimal = repo.load(decimal_only.snapshot_id).binding_values[_CERTIFICATE]
        assert type(loaded_decimal) is Decimal
        assert loaded_decimal.as_tuple() == Decimal("9.50").as_tuple()

        loaded_mixed = repo.load(mixed.snapshot_id).binding_values
        assert {key: (type(value), value) for key, value in loaded_mixed.items()} == {
            _CERTIFICATE: (Decimal, Decimal("9")),
            _RESIDENCE: (str, "9"),
            "renta-other": (str, "0009.0"),
        }


def test_borrador_100_snapshot_id_tells_text_nine_from_decimal_nine() -> None:
    """The content id hashes the tagged value, so the same characters as text and as a decimal differ."""

    def derive(value: str | Decimal) -> str:
        return derive_borrador_100_snapshot_id(
            filing_year=2024,
            period=_PERIOD,
            registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
            source_url="file-import:sha256:" + "4" * 64,
            binding_values={_CERTIFICATE: value},
        )

    assert derive("9") != derive(Decimal("9"))
    assert derive("09") != derive("9")
    assert derive(Decimal("9")) == derive(Decimal("9"))


def _restamp_as_earlier_schema(profile, bucket_id: str, snapshot_id: str) -> None:
    from sqlalchemy import select

    from cadrumo.adapters.persistence.storage.sql.tables import secure_objects_table

    def to_earlier_shape(document):
        document["schema_version"] = 1
        payload = document["payload"]
        payload["binding_values"] = {key: value["value"] for key, value in payload["binding_values"].items()}

    restamp_secure_object_schema_version(
        profile.repository._engine,
        row_statement=select(secure_objects_table).where(
            secure_objects_table.c.namespace == LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.namespace,
            secure_objects_table.c.object_key == borrador_100_snapshot_object_key(bucket_id, snapshot_id),
        ),
        schema_version=1,
        mutate=to_earlier_shape,
    )


def test_borrador_100_row_stored_under_the_earlier_schema_is_counted_not_raised(tmp_path: Path) -> None:
    """An earlier-schema row cannot be read, so listing counts it and still returns the current rows."""

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repo = _borrador_repository(bucket_id=bucket_id)
        current = _snapshot_with_values(bucket_id=bucket_id, source_digit="5", binding_values={_RESIDENCE: "09"})
        earlier = _snapshot_with_values(bucket_id=bucket_id, source_digit="6", binding_values={_RESIDENCE: "09"})
        repo.save(current)
        repo.save(earlier)
        _restamp_as_earlier_schema(profile, bucket_id, earlier.snapshot_id)

        snapshots, outdated = repo.list_snapshots_with_outdated_count()
        assert snapshots == (current,)
        assert outdated == 1
        with pytest.raises(SecureObjectUnreadableError):
            repo.list_snapshots()


def test_borrador_100_row_unreadable_for_another_reason_still_raises(tmp_path: Path) -> None:
    """Only the older-schema refusal is counted; a row from a newer schema is not swallowed."""

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repo = _borrador_repository(bucket_id=bucket_id)
        snapshot = _snapshot_with_values(bucket_id=bucket_id, source_digit="7", binding_values={_RESIDENCE: "09"})
        repo.save(snapshot)

        from sqlalchemy import select

        from cadrumo.adapters.persistence.storage.sql.tables import secure_objects_table

        restamp_secure_object_schema_version(
            profile.repository._engine,
            row_statement=select(secure_objects_table).where(
                secure_objects_table.c.namespace == LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.namespace,
            ),
            schema_version=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.schema_version + 1,
            mutate=lambda document: None,
        )

        with pytest.raises(SecureObjectUnreadableError):
            repo.list_snapshots_with_outdated_count()


def _tamper_row(profile, bucket_id: str, snapshot_id: str, mutate) -> None:
    """Overwrite the columns ``mutate`` derives from the stored snapshot row."""
    from sqlalchemy import select, update

    from cadrumo.adapters.persistence.storage.sql.session import session_scope
    from cadrumo.adapters.persistence.storage.sql.tables import secure_objects_table

    with session_scope(profile.repository._engine) as session:
        row = session.execute(
            select(secure_objects_table).where(
                secure_objects_table.c.namespace == LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE.namespace,
                secure_objects_table.c.object_key == borrador_100_snapshot_object_key(bucket_id, snapshot_id),
            )
        ).one()
        session.execute(
            update(secure_objects_table).where(secure_objects_table.c.id == row.id).values(**mutate(row)),
        )


def test_borrador_100_earlier_schema_row_with_another_classification_is_not_counted(tmp_path: Path) -> None:
    """An older-schema row counts only when that is the sole reason it is unreadable."""

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repo = _borrador_repository(bucket_id=bucket_id)
        earlier = _snapshot_with_values(bucket_id=bucket_id, source_digit="8", binding_values={_RESIDENCE: "09"})
        repo.save(earlier)
        _restamp_as_earlier_schema(profile, bucket_id, earlier.snapshot_id)

        def reclassify(_row) -> dict[str, object]:
            return {"classification": "not-a-classification"}

        _tamper_row(profile, bucket_id, earlier.snapshot_id, reclassify)

        with pytest.raises(SecureObjectUnreadableError):
            repo.list_snapshots_with_outdated_count()


def test_borrador_100_current_schema_row_with_tampered_ciphertext_raises_rather_than_counts(tmp_path: Path) -> None:
    """A row that is unreadable because its bytes were altered is never mistaken for an older-schema row."""

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repo = _borrador_repository(bucket_id=bucket_id)
        snapshot = _snapshot_with_values(bucket_id=bucket_id, source_digit="9", binding_values={_RESIDENCE: "09"})
        repo.save(snapshot)

        def flip_last_byte(row) -> dict[str, object]:
            payload = bytearray(bytes(row.payload))
            payload[-1] ^= 0x01
            return {"payload": bytes(payload)}

        _tamper_row(profile, bucket_id, snapshot.snapshot_id, flip_last_byte)

        with pytest.raises(SecureObjectUnreadableError):
            repo.list_snapshots_with_outdated_count()
