"""Strict roundtrip across the deudas snapshot service and its encrypted store.

Persists :class:`PersistedDeudasSnapshot` records under
``cadrumo.application.live.deudas_snapshot`` at
``SensitivityClass.FINANCIAL``, through the real key provider, the real
``SecureObjectRepository`` and a real SQLite engine.

Every defaultable field is populated with a NON-default value, because a
save-drops-field / load-re-defaults-field regression is invisible when a
fixture leaves the default in place. ``mode`` is the one exception and
deliberately so: it is a single-value ``Literal``, so it has no non-default
value to carry, which is exactly the structural read-only marker it exists to
be.

The anti-tautology proof deletes ``direccion`` from a nested deuda row on disk
and asserts the load refuses. That field is chosen over an easier one because
it carries the owed-versus-refundable axis: were it to silently re-default, a
debt would read back as a refund, which is the precise failure the
amount-is-magnitude convention exists to make unrepresentable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ....adapters.outbound.aeat.sede.deudas import Deuda
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....core.deuda_direccion import DeudaDireccion
from ....core.objeto_tributario import ObjetoTributario
from ....core.period import Period
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..deudas import (
    DeudasCapture,
    DeudasService,
    DeudasSnapshotNotFoundError,
    deudas_snapshot_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "60606060-6060-4060-8060-606060606060"
_NAMESPACE = "cadrumo.application.live.deudas_snapshot"
_CAPTURED_AT = datetime(2026, 3, 14, 10, 45, 0, tzinfo=UTC)


def _populated_capture(*, captured_at: datetime = _CAPTURED_AT) -> DeudasCapture:
    """Build a capture whose every defaultable field carries a non-default value."""
    return DeudasCapture(
        deudas=(
            # A debt owed, attributed to a period, every optional field set.
            Deuda(
                clave_liquidacion="A2860024500012345",
                objeto_tributario=ObjetoTributario.SANCION,
                importe_pendiente=Decimal("1250.75"),
                direccion=DeudaDireccion.DEUDOR,
                periodo=Period.from_year_and_code(2025, "1T"),
                situacion="Pendiente de pago",
            ),
            # A refundable amount: the direction differs while the importe
            # stays a positive magnitude, so a sign-based reading would be
            # indistinguishable from the row above.
            Deuda(
                clave_liquidacion="A2860024500067890",
                objeto_tributario=ObjetoTributario.INTERES_DEMORA,
                importe_pendiente=Decimal("83.19"),
                direccion=DeudaDireccion.ACREEDOR,
                periodo=Period.from_year_and_code(2024, "4T"),
                situacion="Devolución acordada",
            ),
            # A row AEAT attributes to no single period, exercising the
            # optional period and the honest OTRO remainder.
            Deuda(
                clave_liquidacion="K1610125300099999",
                objeto_tributario=ObjetoTributario.OTRO,
                importe_pendiente=Decimal("0.00"),
                direccion=DeudaDireccion.DEUDOR,
                periodo=None,
                situacion="En período ejecutivo",
            ),
            Deuda(
                clave_liquidacion="A2860024500011111",
                objeto_tributario=ObjetoTributario.RECARGO_APREMIO,
                importe_pendiente=Decimal("250.15"),
                direccion=DeudaDireccion.DEUDOR,
                periodo=Period.from_year_and_code(2025, "2T"),
                situacion="Apremio notificado",
            ),
        ),
        captured_at=captured_at,
        source_url="deudas:consulta",
        # Non-default: the field defaults to None.
        authenticated_identity="99999999R",
    )


def test_a_populated_snapshot_survives_the_encrypted_roundtrip(tmp_path: Path) -> None:
    """Strict equality across the real encrypted store, field for field."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = DeudasService()
        capture = _populated_capture()

        persisted = service.capture(bucket_id=_BUCKET_ID, capture=capture)
        loaded = service.show(bucket_id=_BUCKET_ID, snapshot_id=persisted.snapshot_id)

        assert profile.paths.database_file.is_file()
        assert loaded == persisted

        # Witness the fields a re-default would silently change.
        assert loaded.authenticated_identity == "99999999R"
        assert loaded.deudas == capture.deudas
        assert [d.direccion for d in loaded.deudas] == [
            DeudaDireccion.DEUDOR,
            DeudaDireccion.ACREEDOR,
            DeudaDireccion.DEUDOR,
            DeudaDireccion.DEUDOR,
        ]
        assert loaded.deudas[2].periodo is None
        assert loaded.deudas[1].periodo == Period.from_year_and_code(2024, "4T")
        # Decimals must survive as Decimals, not as floats or strings.
        assert isinstance(loaded.deudas[0].importe_pendiente, Decimal)
        assert loaded.deudas[0].importe_pendiente == Decimal("1250.75")
        assert loaded.deudas[2].importe_pendiente == Decimal("0.00")
        assert all(d.importe_pendiente >= Decimal("0") for d in loaded.deudas)
        assert all(d.mode == "read" for d in loaded.deudas)


def test_recapturing_the_same_reading_is_deduplicated(tmp_path: Path) -> None:
    """Content-addressed ids mean an identical re-read is one snapshot."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        service = DeudasService()

        first = service.capture(bucket_id=_BUCKET_ID, capture=_populated_capture())
        second = service.capture(bucket_id=_BUCKET_ID, capture=_populated_capture())

        assert first.snapshot_id == second.snapshot_id
        assert len(service.list_snapshots(bucket_id=_BUCKET_ID)) == 1


def test_a_different_reading_is_a_distinct_snapshot_and_latest_wins(tmp_path: Path) -> None:
    """A later capture is its own row, and latest resolves by capture time."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        service = DeudasService()

        earlier = service.capture(bucket_id=_BUCKET_ID, capture=_populated_capture())
        later_at = datetime(2026, 6, 1, 8, 0, 0, tzinfo=UTC)
        later = service.capture(bucket_id=_BUCKET_ID, capture=_populated_capture(captured_at=later_at))

        assert earlier.snapshot_id != later.snapshot_id
        assert len(service.list_snapshots(bucket_id=_BUCKET_ID)) == 2

        latest = service.latest(bucket_id=_BUCKET_ID)
        assert latest is not None
        assert latest.snapshot_id == later.snapshot_id
        assert latest.captured_at == later_at


def test_latest_reports_none_rather_than_reaching_for_aeat(tmp_path: Path) -> None:
    """An empty register is an empty answer, never a live fetch."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        assert DeudasService().latest(bucket_id=_BUCKET_ID) is None
        assert DeudasService().list_snapshots(bucket_id=_BUCKET_ID) == ()


def test_an_unknown_snapshot_id_is_refused(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID),
        pytest.raises(DeudasSnapshotNotFoundError),
    ):
        DeudasService().show(bucket_id=_BUCKET_ID, snapshot_id="0" * 64)


def test_the_service_exposes_no_method_that_could_mutate_aeat_state(tmp_path: Path) -> None:
    """Structural read-only check on the public surface.

    The service is the persistence side of a payment-adjacent AEAT surface, so
    the absence of a paying, filing or acknowledging verb is a property worth
    asserting rather than assuming from the current file's contents.
    """
    forbidden = ("pay", "pagar", "submit", "file", "presentar", "acknowledge", "aplazamiento", "delete")
    public = {name for name in dir(DeudasService) if not name.startswith("_")}
    assert not [name for name in public if any(verb in name.lower() for verb in forbidden)]


def test_deleting_the_direction_on_disk_makes_the_load_refuse(tmp_path: Path) -> None:
    """Anti-tautology proof: a dropped required field must surface at load.

    Deletes ``direccion`` from the first persisted deuda row inside the
    encrypted envelope payload and asserts the load refuses. If this ever
    passed with the field absent, every roundtrip assertion above would be
    tautological, and worse, a debt could read back as a refund.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = DeudasService()
        persisted = service.capture(bucket_id=_BUCKET_ID, capture=_populated_capture())

        object_key = deudas_snapshot_object_key(_BUCKET_ID, persisted.snapshot_id)
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == _NAMESPACE,
            SecureObjectRow.object_key == object_key,
        )

        def mutate(decoded):
            assert "direccion" in decoded["payload"]["deudas"][0], (
                "fixture must serialise direccion into the envelope payload for this proof to mean anything"
            )
            del decoded["payload"]["deudas"][0]["direccion"]

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        with pytest.raises(ValidationError, match="direccion"):
            service.show(bucket_id=_BUCKET_ID, snapshot_id=persisted.snapshot_id)


def test_a_negative_importe_on_disk_makes_the_load_refuse(tmp_path: Path) -> None:
    """The magnitude constraint is enforced on the way IN, not just at build.

    A stored negative importe would mean flow was encoded twice and the two
    encodings disagree. The load must refuse rather than hand back a row whose
    sign contradicts its direction field.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = DeudasService()
        persisted = service.capture(bucket_id=_BUCKET_ID, capture=_populated_capture())

        object_key = deudas_snapshot_object_key(_BUCKET_ID, persisted.snapshot_id)
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == _NAMESPACE,
            SecureObjectRow.object_key == object_key,
        )

        def mutate(decoded):
            decoded["payload"]["deudas"][0]["importe_pendiente"] = "-1250.75"

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        with pytest.raises(ValidationError, match="importe_pendiente"):
            service.show(bucket_id=_BUCKET_ID, snapshot_id=persisted.snapshot_id)
