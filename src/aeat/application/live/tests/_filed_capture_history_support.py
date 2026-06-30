"""Shared support for filed calculation-history capture tests."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    ObservedCasillaValue,
    observed_casillas_from_submitted_file,
)
from ....core import Period
from ....core.external_constants import load_external_constants
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.modelos import (
    ExternalEvidence,
    ModeloRecord,
    ModeloRecordCatalogueRepository,
    ModeloRecordStatus,
    derive_filing_record_id,
    upsert_filing_record,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests import FIXTURES_DIR
from ....tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository

_CAPTURED_AT = datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC)
_SYNTHETIC_PROFILE_ID = "SYNTHETIC_PROFILE"
_SYNTHETIC_EXPEDIENTE_ID = "200030300000000Z"
_SESSION_BUCKET_ID = "45454545-4545-4454-8454-454545454545"


def _casilla_id(value: object) -> CasillaId:
    return validated_casilla_id(value, surface="test casilla id")


_M303_DISPONIBLE_CASILLA: CasillaId = _casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = _casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
)
_M303_POSTERIOR_CASILLA: CasillaId = _casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: CasillaId = _casilla_id("iva.resultado")
_M303_GENERADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-generada-periodo")
_M303_APLICADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-aplicada-periodo")
_M303_RESULTADO_FINAL_CASILLA: CasillaId = _casilla_id("71")


@cache
def _registry_snapshot(modelo: str, filing_year: int, period: str):
    return resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)


@cache
def _modelo_130_justificante_pdf_bytes() -> bytes:
    return (FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf").read_bytes()


@cache
def _aeat_external_constants():
    return load_external_constants().aeat


@contextmanager
def _secure_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SESSION_BUCKET_ID) as profile:
        yield profile.paths.db_dir / "aeat.db"


@contextmanager
def _profile_backend(tmp_path: Path, *, tax_id: str):
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("11111111-1111-4111-8111-111111111111"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="11111111-1111-4111-8111-111111111111",
                overrides={"identity.tax_id": tax_id},
            ),
        )
        bucket_id = workflow_state_repository().load().active_profile_bucket_id()
        assert bucket_id is not None
        yield bucket_id


def _parsed_303_submitted_file_observation(
    *,
    year: int,
    period: str,
    expediente_id: str,
    presented_at: datetime,
    casilla_110: str,
    casilla_78: str,
    casilla_87: str,
    casilla_69: str,
    casilla_71: str,
) -> FiledDeclaracionObservation:
    observation_period = Period.from_year_and_code(year, period)
    body = _modelo_303_page_03_payload(
        casilla_110=casilla_110,
        casilla_78=casilla_78,
        casilla_87=casilla_87,
        casilla_69=casilla_69,
        casilla_71=casilla_71,
    )
    external = _aeat_external_constants()
    declarations_url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl(declarations_url),
        content_type="application/octet-stream",
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=presented_at,
    )
    declaration = Declaracion(
        modelo="303",
        ejercicio=year,
        period=observation_period,
        expediente_id=expediente_id,
        estado="ALTA",
        tipo_solicitud=None,
        observaciones=None,
        presented_at=presented_at,
        justificante_link_text="Ver",
        archive_link_text="Ver",
        declaration_copy_link_text=None,
    )
    observed = observed_casillas_from_submitted_file(
        snapshot=_registry_snapshot("303", year, period),
        declaration=declaration,
        body=body,
        artefact=artefact,
    )
    return FiledDeclaracionObservation(
        modelo="303",
        ejercicio=year,
        period=observation_period,
        expediente_id=expediente_id,
        status="ALTA",
        presented_at=presented_at,
        authenticated_identity=_SYNTHETIC_PROFILE_ID,
        artefacts=(artefact,),
        casillas=observed,
        extraction_coverage={"submitted_file": 1.0},
    )


def _stored_130_justificante_observation(
    store: FiledDeclaracionObservationStore,
    *,
    authenticated_identity: str = "00000000T",
    expediente_id: str = "13020260410ABCD1234EFGH5678",
) -> FiledDeclaracionObservation:
    pdf_bytes = _modelo_130_justificante_pdf_bytes()
    period = Period.from_year_and_code(2026, "1T")
    external = _aeat_external_constants()
    declarations_url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    artefact = store.persist_artefact(
        ("130", 2026, period, expediente_id),
        FiledDeclaracionArtefact(
            kind="justificante_pdf",
            source_url=AnyHttpUrl(declarations_url),
            content_type="application/pdf",
            byte_count=len(pdf_bytes),
            sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            captured_at=_CAPTURED_AT,
        ),
        pdf_bytes,
    )
    return FiledDeclaracionObservation(
        modelo="130",
        ejercicio=2026,
        period=period,
        expediente_id=expediente_id,
        status="ALTA",
        presented_at=_CAPTURED_AT,
        authenticated_identity=authenticated_identity,
        artefacts=(artefact,),
    )


def _seed_current_130_filing(
    *,
    bucket_id: str,
    aeat_accepted: bool = False,
    external_evidence: ExternalEvidence | None = None,
) -> ModeloRecord:
    period = Period.from_year_and_code(2026, "1T")
    revision_id = hashlib.sha256(f"{bucket_id}:130:2026:1T".encode()).hexdigest()
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name="130-2026-1T",
        created_at=_CAPTURED_AT,
        updated_at=_CAPTURED_AT,
    )
    work_unit_repo = WorkUnitCatalogueRepository()
    work_unit_repo.save(upsert_work_unit(work_unit_repo.load(), work_unit))
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=_CAPTURED_AT,
        filed_by="operator",
    )
    filing = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        filed_at=_CAPTURED_AT,
        filed_by="operator",
        aeat_accepted=aeat_accepted,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=external_evidence,
    )
    filing_repo = ModeloRecordCatalogueRepository()
    filing_repo.save(upsert_filing_record(filing_repo.load(), filing))
    return filing


def _modelo_303_page_03_payload(
    *,
    casilla_110: str,
    casilla_78: str,
    casilla_87: str,
    casilla_69: str,
    casilla_71: str,
) -> bytes:
    page = list("<T30303000>" + (" " * (1017 - len("<T30303000>"))))
    for position, raw in (
        (255, casilla_110),
        (272, casilla_78),
        (289, casilla_87),
        (323, casilla_69),
        (374, casilla_71),
    ):
        page[position - 1 : position - 1 + len(raw)] = raw
    page[1005:1017] = list("</T30303000>")
    return "".join(page).encode("latin-1")


def _prior_303_observation(
    *,
    pending_compensation: Decimal,
    prior_pending: Decimal | None = None,
    applied: Decimal | None = None,
    result: Decimal = Decimal("0.00"),
    final_result: Decimal | None = None,
    generated: Decimal | None = None,
    year: int = 2026,
    period: str = "1T",
    expediente_id: str = _SYNTHETIC_EXPEDIENTE_ID,
    presented_at: datetime = _CAPTURED_AT,
    status: str = "ALTA",
) -> FiledDeclaracionObservation:
    observation_period = Period.from_year_and_code(year, period)
    body = f"303-{year}-{period}-submitted-file".encode("ascii")
    external = _aeat_external_constants()
    declarations_url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    return FiledDeclaracionObservation(
        modelo="303",
        ejercicio=year,
        period=observation_period,
        expediente_id=expediente_id,
        status=status,
        presented_at=presented_at,
        authenticated_identity=_SYNTHETIC_PROFILE_ID,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl(declarations_url),
                content_type="application/octet-stream",
                byte_count=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                captured_at=_CAPTURED_AT,
            ),
        ),
        casillas=(
            *(
                (
                    ObservedCasillaValue(
                        casilla_id=_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
                        value=str(prior_pending),
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:110",
                        confidence=1.0,
                    ),
                )
                if prior_pending is not None
                else ()
            ),
            *(
                (
                    ObservedCasillaValue(
                        casilla_id=_M303_APLICADA_CASILLA,
                        value=str(applied),
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:78",
                        confidence=1.0,
                    ),
                )
                if applied is not None
                else ()
            ),
            ObservedCasillaValue(
                casilla_id=_M303_POSTERIOR_CASILLA,
                value=str(pending_compensation),
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:87",
                confidence=1.0,
            ),
            ObservedCasillaValue(
                casilla_id=_M303_RESULTADO_CASILLA,
                value=str(result),
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:69",
                confidence=1.0,
            ),
            *(
                (
                    ObservedCasillaValue(
                        casilla_id=_M303_GENERADA_CASILLA,
                        value=str(generated),
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:derived-generated",
                        confidence=1.0,
                    ),
                )
                if generated is not None
                else ()
            ),
            *(
                (
                    ObservedCasillaValue(
                        casilla_id=_M303_RESULTADO_FINAL_CASILLA,
                        value=str(final_result),
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:71",
                        confidence=1.0,
                    ),
                )
                if final_result is not None
                else ()
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
        registry_snapshot_id=f"303:2009-y-siguientes:{year}:{period}",
    )


def _declaration(
    *,
    period: str,
    expediente_id: str,
    estado: str,
    presented_at: datetime,
) -> Declaracion:
    return Declaracion(
        modelo="303",
        ejercicio=2026,
        period=Period.from_year_and_code(2026, period),
        expediente_id=expediente_id,
        estado=estado,
        tipo_solicitud=None,
        observaciones=None,
        presented_at=presented_at,
        justificante_link_text="Ver",
        archive_link_text="Ver",
        declaration_copy_link_text=None,
    )
