"""Tests for the bucket-scoped expedientes snapshot service.

The suite pins :class:`~application.live.ExpedientesService` as a read-only
capture/list/show/latest surface backed by content-addressed
:class:`~application.live.PersistedExpedientesSnapshot` records in encrypted
bucket-local secure-object storage. It also verifies lookup refusals, object-key
validation, bucket isolation, and absence of AEAT-side write verbs.

See Also:
    :mod:`~application.live.expedientes`
        Service, payload, object-key, and not-found contracts under test.
    :mod:`~application.live.snapshot_base`
        Shared secure snapshot repository and stateless snapshot lifecycle.
    :data:`~adapters.persistence.storage.LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE`
        Registered namespace, sensitivity, schema-version, and object-key
        grammar for persisted expedientes captures.

The ``"live"`` literal in ``cadrumo_live_state_dir / "live" / "expedientes" / ...``
is a ``not (...).exists()`` refusal guard proving a captured tax id never
leaks into a plaintext audit-trail file alongside the encrypted secure-object
write. An accessor aimed at the wrong location would leave that assertion
trivially satisfied -- the exact silent-pass shape a refusal test must not
risk -- so the literal stays.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from ....adapters.outbound.aeat.sede import Declaracion
from ....adapters.persistence.storage import LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE
from ....core import Period
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile, read_db_at_rest_bytes
from .. import LIVE_EXPEDIENTES_READ_OPERATION
from ..errors import LiveApplicationInputError
from ..expedientes import (
    ExpedientesCapture,
    ExpedientesService,
    ExpedientesSnapshotNotFoundError,
    expedientes_snapshot_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"live"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""

_DECLARACION_CONSULT_URL = aeat_url("www6", configured_path("sede_paths", "declaracion_consult"))
_BUCKET_A_ID = "56565656-5656-4656-8656-565656565656"
_BUCKET_B_ID = "57575757-5757-4757-8757-575757575757"


def test_capture_uses_expedientes_auth_operation_label() -> None:
    assert LIVE_EXPEDIENTES_READ_OPERATION == "live-expedientes-read"


def _service(profile: TestRuntimeProfile) -> ExpedientesService:
    return ExpedientesService(settings=profile.settings)


def _declaration(
    *,
    modelo: str = "303",
    ejercicio: int = 2025,
    period: str = "1T",
    expediente_id: str = "12345678901234567890",
    estado: str = "ALTA",
    presented_at: datetime | None = None,
) -> Declaracion:
    return Declaracion(
        modelo=modelo,
        ejercicio=ejercicio,
        period=Period.from_year_and_code(ejercicio, period),
        expediente_id=expediente_id,
        estado=estado,
        presented_at=presented_at or datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
    )


def _capture(
    *,
    declarations: tuple[Declaracion, ...] = (),
    captured_at: datetime | None = None,
    authenticated_identity: str | None = "12345678Z",
) -> ExpedientesCapture:
    return ExpedientesCapture(
        declarations=declarations,
        captured_at=captured_at or datetime(2025, 4, 15, 10, 0, tzinfo=UTC),
        source_url=_DECLARACION_CONSULT_URL,
        authenticated_identity=authenticated_identity,
    )


class TestCapture:
    def test_capture_persists_with_content_addressed_id(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        persisted = svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(declarations=(_declaration(),)),
        )
        assert len(persisted.snapshot_id) == 64
        assert persisted.bucket_id == secure_engine.bucket_id
        assert persisted.authenticated_identity == "12345678Z"
        assert persisted.declarations[0].expediente_id == "12345678901234567890"

    def test_capture_deduplicates_identical_captures(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        cap = _capture(declarations=(_declaration(),))
        a = svc.capture(bucket_id=secure_engine.bucket_id, capture=cap)
        b = svc.capture(bucket_id=secure_engine.bucket_id, capture=cap)
        assert a.snapshot_id == b.snapshot_id
        assert len(svc.list_snapshots(bucket_id=secure_engine.bucket_id)) == 1

    def test_capture_distinct_inputs_yield_distinct_ids(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        a = svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(declarations=(_declaration(modelo="303"),)),
        )
        b = svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(declarations=(_declaration(modelo="130"),)),
        )
        assert a.snapshot_id != b.snapshot_id


class TestShow:
    def test_show_resolves_full_and_prefix(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        persisted = svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(declarations=(_declaration(),)),
        )
        assert svc.show(bucket_id=secure_engine.bucket_id, snapshot_id=persisted.snapshot_id) == persisted
        assert svc.show(bucket_id=secure_engine.bucket_id, snapshot_id=persisted.snapshot_id[:10]) == persisted

    def test_show_refuses_unknown_id(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        with pytest.raises(ExpedientesSnapshotNotFoundError) as exc_info:
            svc.show(bucket_id=secure_engine.bucket_id, snapshot_id="0" * 64)
        assert exc_info.value.translated_message == "application.live.expedientes.errors.snapshot_not_found"
        assert exc_info.value.context == {"snapshot_id": "0" * 64}
        assert secure_engine.bucket_id not in str(exc_info.value)

    def test_show_refuses_ambiguous_prefix_without_full_id_leak(
        self,
        secure_engine: TestRuntimeProfile,
    ) -> None:
        svc = _service(secure_engine)
        by_prefix: dict[str, list[str]] = {}
        for index in range(17):
            persisted = svc.capture(
                bucket_id=secure_engine.bucket_id,
                capture=_capture(
                    declarations=(
                        _declaration(
                            modelo=str(100 + index),
                            expediente_id=f"{index:020d}",
                        ),
                    ),
                ),
            )
            by_prefix.setdefault(persisted.snapshot_id[:1], []).append(persisted.snapshot_id)

        prefix, matches = next((candidate, ids) for candidate, ids in by_prefix.items() if len(ids) > 1)
        with pytest.raises(ExpedientesSnapshotNotFoundError) as exc_info:
            svc.show(bucket_id=secure_engine.bucket_id, snapshot_id=prefix)

        assert exc_info.value.translated_message == "application.live.expedientes.errors.snapshot_prefix_ambiguous"
        assert exc_info.value.context == {"snapshot_id": prefix, "match_count": len(matches)}
        for snapshot_id in matches:
            assert snapshot_id not in str(exc_info.value)


class TestLatest:
    def test_latest_returns_newest_capture(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(
                declarations=(_declaration(),),
                captured_at=datetime(2025, 1, 1, tzinfo=UTC),
            ),
        )
        newer = svc.capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(
                declarations=(_declaration(modelo="130"),),
                captured_at=datetime(2025, 6, 1, tzinfo=UTC),
            ),
        )
        assert svc.latest(bucket_id=secure_engine.bucket_id) == newer

    def test_latest_on_empty_bucket_is_none(self, secure_engine: TestRuntimeProfile) -> None:
        svc = _service(secure_engine)
        assert svc.latest(bucket_id=secure_engine.bucket_id) is None


class TestBucketIsolation:
    def test_snapshots_are_runtime_profile_scoped(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path / "profile-a", bucket_id=_BUCKET_A_ID) as bucket_a:
            svc_a = _service(bucket_a)
            svc_a.capture(
                bucket_id=bucket_a.bucket_id,
                capture=_capture(declarations=(_declaration(modelo="303"),)),
            )
            assert svc_a.list_snapshots(bucket_id=bucket_a.bucket_id)[0].declarations[0].modelo == "303"

        with isolated_runtime_profile(tmp_path=tmp_path / "profile-b", bucket_id=_BUCKET_B_ID) as bucket_b:
            svc_b = _service(bucket_b)
            assert svc_b.list_snapshots(bucket_id=bucket_b.bucket_id) == ()
            svc_b.capture(
                bucket_id=bucket_b.bucket_id,
                capture=_capture(declarations=(_declaration(modelo="130"),)),
            )
            assert svc_b.list_snapshots(bucket_id=bucket_b.bucket_id)[0].declarations[0].modelo == "130"


class TestSecureStorage:
    def test_capture_persists_expedientes_snapshot_as_secure_object(self, secure_engine: TestRuntimeProfile) -> None:
        persisted = _service(secure_engine).capture(
            bucket_id=secure_engine.bucket_id,
            capture=_capture(declarations=(_declaration(),)),
        )

        record = secure_engine.repository.load(
            LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE.namespace,
            expedientes_snapshot_object_key(secure_engine.bucket_id, persisted.snapshot_id),
            expected_class=LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE.sensitivity,
            max_supported_version=LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE.schema_version,
        )

        assert record is not None
        assert b"12345678901234567890" in record.payload
        assert b"12345678901234567890" not in read_db_at_rest_bytes(secure_engine.paths.database_file)
        assert not (
            secure_engine.settings.cadrumo_live_state_dir / "live" / "expedientes" / f"{secure_engine.bucket_id}.jsonl"
        ).exists()

    def test_object_key_refuses_blank_bucket_with_locale_metadata(self) -> None:
        with pytest.raises(LiveApplicationInputError) as exc_info:
            expedientes_snapshot_object_key(" ", "snapshot-1")
        assert exc_info.value.translated_message == "application.live.expedientes.errors.bucket_id_blank"

    def test_object_key_refuses_blank_snapshot_with_locale_metadata(self) -> None:
        with pytest.raises(LiveApplicationInputError) as exc_info:
            expedientes_snapshot_object_key(_BUCKET_A_ID, " ")
        assert exc_info.value.translated_message == "application.live.expedientes.errors.snapshot_id_blank"


class TestNoWriteSurface:
    def test_service_has_no_write_methods(self) -> None:
        assert not hasattr(ExpedientesService, "submit")
        assert not hasattr(ExpedientesService, "send")
        assert not hasattr(ExpedientesService, "modify")
        assert not hasattr(ExpedientesService, "delete_remote")

    def test_capture_mode_is_read_only_marker(self) -> None:
        cap = _capture(declarations=(_declaration(),))
        assert cap.mode == "read"
        # The Declaracion adapter model also carries mode='read'.
        assert cap.declarations[0].mode == "read"
