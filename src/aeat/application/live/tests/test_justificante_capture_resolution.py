"""Period-aware expediente resolution and offline orchestrator wiring.

The procedure-tree expediente carries no period, so a quarterly work unit
must resolve through the period-bearing declarations register. These tests
pin the primary risk of the feature: a 1T and a 2T work unit MUST resolve to
distinct expedientes and never silently reconcile against the wrong quarter.

The orchestrator test exercises ``capture_justificante_snapshot`` end to end
with seam-injected live providers (returning real typed sede records, not
mocks) and the real ``JustificanteCaptureSnapshotService`` persisting into an
isolated bucket.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    Declaracion,
    Expediente,
    JustificanteRef,
    SedeCapture,
)
from ....core import Modelo
from ....tests.secure_sql import isolated_runtime_profile
from .._errors import LiveApplicationInputError
from .._justificante import resolve_period_expediente

if TYPE_CHECKING:
    from ....adapters.outbound.aeat.auth import AeatSession
    from ....core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = Modelo.M130.value
_YEAR = 2026
_EXP_1T = "202613000010001A"
_EXP_2T = "202613000020002B"


def _declaration(*, period: str, expediente_id: str, presented_at: datetime) -> Declaracion:
    return Declaracion(
        modelo=_MODELO,
        ejercicio=_YEAR,
        period=period,
        expediente_id=expediente_id,
        estado="Presentada",
        presented_at=presented_at,
    )


def _expediente(*, expediente_id: str) -> Expediente:
    return Expediente(
        expediente_id=expediente_id,
        modelo=_MODELO,
        ejercicio=_YEAR,
        category_path=("AEAT", "Modelo 130. IRPF. Pago fraccionado."),
        detail_url=AnyHttpUrl(f"https://sede.agenciatributaria.gob.es/wlpl/DASR-CORE/Acceso?exp={expediente_id}"),
    )


_DECLARATIONS = (
    _declaration(period="1T", expediente_id=_EXP_1T, presented_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC)),
    _declaration(period="2T", expediente_id=_EXP_2T, presented_at=datetime(2026, 7, 18, 9, 0, tzinfo=UTC)),
)
_EXPEDIENTES = (_expediente(expediente_id=_EXP_1T), _expediente(expediente_id=_EXP_2T))


def test_resolves_first_quarter_to_its_own_expediente() -> None:
    resolved = resolve_period_expediente(
        declarations=_DECLARATIONS,
        expedientes=_EXPEDIENTES,
        modelo=_MODELO,
        period="1T",
    )
    assert resolved.expediente_id == _EXP_1T


def test_resolves_second_quarter_to_a_distinct_expediente() -> None:
    resolved = resolve_period_expediente(
        declarations=_DECLARATIONS,
        expedientes=_EXPEDIENTES,
        modelo=_MODELO,
        period="2T",
    )
    assert resolved.expediente_id == _EXP_2T
    # The primary-risk invariant: the two quarters never collapse to one.
    first = resolve_period_expediente(
        declarations=_DECLARATIONS, expedientes=_EXPEDIENTES, modelo=_MODELO, period="1T"
    )
    assert resolved.expediente_id != first.expediente_id


def test_missing_period_declaration_refuses_rather_than_falls_back() -> None:
    with pytest.raises(LiveApplicationInputError, match="no filed declaration"):
        resolve_period_expediente(
            declarations=_DECLARATIONS,
            expedientes=_EXPEDIENTES,
            modelo=_MODELO,
            period="3T",
        )


def test_declaration_with_expediente_absent_from_tree_refuses() -> None:
    with pytest.raises(LiveApplicationInputError, match="not present in the expedientes tree"):
        resolve_period_expediente(
            declarations=_DECLARATIONS,
            expedientes=(_expediente(expediente_id=_EXP_1T),),  # tree missing the 2T expediente
            modelo=_MODELO,
            period="2T",
        )


def test_refiled_period_resolves_to_the_latest_filing() -> None:
    early = _declaration(period="1T", expediente_id=_EXP_1T, presented_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC))
    refile_exp = "202613000010099Z"
    late = _declaration(period="1T", expediente_id=refile_exp, presented_at=datetime(2026, 5, 2, 11, 0, tzinfo=UTC))
    resolved = resolve_period_expediente(
        declarations=(early, late),
        expedientes=(_expediente(expediente_id=_EXP_1T), _expediente(expediente_id=refile_exp)),
        modelo=_MODELO,
        period="1T",
    )
    assert resolved.expediente_id == refile_exp


def test_orchestrator_persists_period_correct_capture_offline(tmp_path: Path) -> None:
    """capture_justificante_snapshot wires resolution + capture + persistence.

    Seam-injects the live providers with canned typed records (a sentinel
    session, the 1T/2T declarations and expedientes, and a SedeCapture for the
    resolved expediente) and asserts the real service persists the 2T receipt
    against its own expediente.
    """
    from .. import capture_justificante_snapshot

    pdf_bytes = b"%PDF-1.4\n2T justificante\n%%EOF\n"
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    async def _session() -> tuple[AeatSession, Settings]:
        return cast("tuple[AeatSession, Settings]", (object(), object()))

    async def _declarations(session: object, settings: object, *, modelo: str, year: int):
        return _DECLARATIONS

    async def _expedientes(session: object, settings: object, *, modelo: str):
        return _EXPEDIENTES

    async def _capture(session: object, settings: object, *, expediente: Expediente):
        ref = JustificanteRef(
            csv="CSV2T0001ABCD2345",
            expediente_id=expediente.expediente_id,
            cotejo_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/KATA-APLI/cotejo/CotejoIdSv?CSV=CSV2T0001ABCD2345"),
            pdf_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/wlpl/KATA-APLI/cotejo/CotejoDocIdSv?CSV=CSV2T0001ABCD2345"),
        )
        return SedeCapture(
            expediente=expediente,
            ref=ref,
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            captured_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
        )

    bucket_id = "renta-2026-bucket"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        persisted = asyncio.run(
            capture_justificante_snapshot(
                bucket_id=bucket_id,
                modelo=_MODELO,
                year=_YEAR,
                period="2T",
                session_provider=_session,
                declarations_provider=_declarations,
                expedientes_provider=_expedientes,
                justificante_provider=_capture,
            )
        )

    assert persisted.modelo == _MODELO
    assert persisted.period == "2T"
    assert persisted.expediente_id == _EXP_2T
    assert persisted.pdf_sha256 == pdf_sha256
    assert persisted.decoded_pdf_bytes() == pdf_bytes
    assert persisted.source_kind == "aeat_sede_live_capture"
