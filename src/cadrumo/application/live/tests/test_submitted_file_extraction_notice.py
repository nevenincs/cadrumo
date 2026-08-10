"""Submitted-file layout refusals survive the live capture accumulator.

The Sede adapter owns the fichero parser and records a genuine parser refusal
on the captured observation. This owning application-suite test drives that
record through the real encrypted observation store and the one shared
accumulator, proving that every report type receives the Notice lane without
depending on entrypoint internals.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    SedeParseError,
    observed_casillas_from_submitted_file,
)
from ....application.filing import (
    ModeloOperatorProfile,
    build_draft,
    build_runtime_schema_provider,
    export_draft,
)
from ....core import Modelo, Period, validated_casilla_id
from ....domain.calculations.registry import bundled_authority
from ....domain.submission import ModeloDraftStatus
from ....tests.secure_sql import isolated_runtime_profile
from .. import FiledDataCaptureReport
from .._filed_data_capture import _CaptureAccumulator

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_FILING_YEAR = 2025
_CAPTURE_BUCKET_ID = "76767676-7676-4767-8767-767676767676"


def _declaration() -> Declaracion:
    return Declaracion(
        modelo="303",
        ejercicio=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, "1T"),
        expediente_id="2025303000000001",
        estado="ALTA",
        presented_at=datetime(_FILING_YEAR, 4, 10, 9, 0, tzinfo=UTC),
    )


@cache
def _exported_payload() -> bytes:
    """Create the same kind of real M303 fichero the Sede parser reads."""
    period = Period.from_year_and_code(_FILING_YEAR, "1T")
    provider = build_runtime_schema_provider(filing_year=_FILING_YEAR, period=period, modelos=("303",))
    draft = build_draft(
        modelo="303",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Live capture notice probe"),
        inputs={
            validated_casilla_id("07", surface="probe"): Decimal("10000.00"),
            validated_casilla_id("iva.repercutido.general", surface="probe"): Decimal("2100.00"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    with TemporaryDirectory() as scratch:
        output = Path(scratch) / "m303-submitted-file.txt"
        export_draft(
            draft,
            output_path=output,
            headers={
                "declaration_type": "C",
                "surnames": "GARCIA LOPEZ",
                "full_name": "GARCIA LOPEZ JUAN",
                "program_version": "A001",
                "presenter_nif": "12345678Z",
                "redeme": "N",
            },
            schema_provider=provider,
        )
        return output.read_bytes()


def _artefact(payload: bytes) -> FiledDeclaracionArtefact:
    return FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl("https://www6.aeat.es/submitted-file-probe"),
        content_type="text/plain",
        byte_count=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _project(payload: bytes):
    return observed_casillas_from_submitted_file(
        snapshot=bundled_authority().snapshot(
            modelo_id=Modelo.M303.value,
            filing_year=_FILING_YEAR,
            period="1T",
        ),
        declaration=_declaration(),
        body=payload,
        artefact=_artefact(payload),
    )


def _captured_report(
    *,
    tmp_path: Path,
    payload: bytes,
    metadata: dict[str, str] | None = None,
    casillas=(),
) -> FiledDataCaptureReport:
    """Persist a captured Sede observation through the shared accumulator."""
    declaration = _declaration()
    output_root = tmp_path / "filed-observations"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_CAPTURE_BUCKET_ID):
        store = FiledDeclaracionObservationStore(output_root)
        artefact = store.persist_artefact(
            (
                declaration.modelo,
                declaration.ejercicio,
                declaration.period,
                declaration.expediente_id,
            ),
            _artefact(payload),
            payload,
        )
        observation = FiledDeclaracionObservation(
            modelo=declaration.modelo,
            ejercicio=declaration.ejercicio,
            period=declaration.period,
            expediente_id=declaration.expediente_id,
            status=declaration.estado,
            presented_at=declaration.presented_at,
            authenticated_identity="12345678Z",
            artefacts=(artefact,),
            casillas=tuple(casillas),
            metadata=metadata or {},
        )
        accumulator = _CaptureAccumulator()
        accumulator.absorb(
            observation,
            store=store,
            bucket_id=_CAPTURE_BUCKET_ID,
            output_root=output_root,
        )
        report_fields = accumulator.capture_report_fields()

    return FiledDataCaptureReport(
        output_root=str(output_root),
        modelo=declaration.modelo,
        year=declaration.ejercicio,
        **report_fields,
        calculation_observation_count=0,
        calculation_observation_keys=(),
    )


def test_a_genuine_layout_refusal_becomes_a_capture_report_notice(tmp_path: Path) -> None:
    """The report names the modelo, filed record and parser-provided reason."""
    payload = _exported_payload()
    truncated = payload[: len(payload) // 2]
    with pytest.raises(SedeParseError) as caught:
        _project(truncated)

    report = _captured_report(
        tmp_path=tmp_path,
        payload=truncated,
        metadata={"submitted_file_extraction_error": str(caught.value)},
    )

    assert len(report.evidence_notices) == 1
    notice = report.evidence_notices[0]
    assert notice.context is not None
    assert notice.context["modelo"] == "303"
    assert notice.context["expediente_id"] == _declaration().expediente_id
    assert notice.context["reason"] == str(caught.value)
    assert "modelo-303-" in notice.context["reason"]
    assert notice.context["expediente_id"] in notice.message


def test_a_successfully_read_submitted_file_emits_no_capture_notice(tmp_path: Path) -> None:
    """The Notice is conditional on recorded refusal metadata, not normal capture."""
    payload = _exported_payload()

    report = _captured_report(tmp_path=tmp_path, payload=payload, casillas=_project(payload))

    assert report.evidence_notices == ()
