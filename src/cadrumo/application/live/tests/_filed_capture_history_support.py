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
)
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import (
    CasillaId,
    CasillaValueKind,
    ObservedHeaderFact,
    Period,
    RegistryAuthorityGrade,
    validated_casilla_id,
)
from ....core.external_constants import load_external_constants
from ....core.resources import bundled_path
from ....domain.calculations.registry.snapshot import build_snapshot
from ....domain.modelos import (
    ExternalEvidence,
    ModeloCode,
    ModeloRecord,
    ModeloRecordStatus,
    WorkUnit,
    derive_filing_record_id,
    derive_work_unit_id,
    upsert_filing_record,
    upsert_work_unit,
)
from ....tests import FIXTURES_DIR
from ....tests.profile_capsule import open_test_profile_session
from ....tests.registry_tree import bundled_registry_tree
from ....tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ....tests.user_profile import register_minimal_profile
from ...workflow.persistence import workflow_state_repository

_CAPTURED_AT = datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC)
#: A checksum-valid synthetic NIF. This value reaches
#: ``IvaCompensationPeriodState.taxpayer_nif`` as the captured
#: ``authenticated_identity``, and that field is a ``SubjectTaxId``, so a
#: placeholder label is refused at the boundary.
_SYNTHETIC_PROFILE_ID = "12345678Z"
_SYNTHETIC_EXPEDIENTE_ID = "200030300000000Z"
_SESSION_BUCKET_ID = "45454545-4545-4454-8454-454545454545"


_M303_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_M303_POSTERIOR_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_GENERADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_M303_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_M303_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("71")
_M303_DECLARATION_TYPE_N = ObservedHeaderFact(
    header_key="declaration_type",
    value="N",
    source_artefact_kind="submitted_file",
    source_locator="submitted-file:declaration-type",
)
_M303_DECLARATION_TYPE_C = ObservedHeaderFact(
    header_key="declaration_type",
    value="C",
    source_artefact_kind="submitted_file",
    source_locator="submitted-file:declaration-type",
)
_M303_DECLARATION_TYPE_I = ObservedHeaderFact(
    header_key="declaration_type",
    value="I",
    source_artefact_kind="submitted_file",
    source_locator="submitted-file:declaration-type",
)


@cache
def _registry_snapshot(modelo: str, filing_year: int, period: str):
    """Build a real snapshot without the tree-wide ``ValidatedRegistryAuthority`` load.

    ``load_registry_tree`` compiles the tree without validating it; ``build_snapshot``
    then validates only the requested modelo's own revisions -- unlike
    ``bundled_authority()``, whose ``.load()`` validates the entire registry
    tree (including every OTHER modelo's export layouts) and currently refuses
    unconditionally as a result. A modelo whose OWN revisions lack an export layout
    still refuses here, honestly, on its own missing capability.
    """
    modelos, catalogues = bundled_registry_tree()
    modelo_definition = next(candidate for candidate in modelos if candidate.id == modelo)
    return build_snapshot(
        modelo_definition,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
        grade=RegistryAuthorityGrade.CALCULATION,
    )


@cache
def _modelo_130_justificante_pdf_bytes() -> bytes:
    return (FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf").read_bytes()


@cache
def _modelo_303_justificante_pdf_bytes() -> bytes:
    return (FIXTURES_DIR / "justificantes" / "modelo_303_2026Q1.pdf").read_bytes()


#: The csv AEAT printed on each receipt fixture, stated independently of the
#: PDF rather than parsed back out of it. A capture stores the cotejo document
#: URL it fetched the bytes under, and production recovers the csv from that
#: URL to check it against the csv in the body. Deriving these from the fixture
#: would make both sides of that comparison one value and every check here
#: would pass for free. ``test_fixture_csv_constants_still_match_the_receipts``
#: keeps them honest.
_MODELO_130_FIXTURE_CSV = "ABCD1234EFGH5678"
_MODELO_303_FIXTURE_CSV = "ZZZZ9999YYYY8888"


def _cotejo_document_source_url(csv: str) -> str:
    """Build the cotejo document URL a capture records as an artefact source.

    Mirrors the production shape: the fetch resolves the csv from the cotejo
    popup AEAT redirected it to, builds the document URL around that csv, and
    persists the URL verbatim.
    """
    external = _aeat_external_constants()
    return f"{external.domains.www6}{external.sede_paths.cotejo_document}?CSV={csv}"


@cache
def _aeat_external_constants():
    return load_external_constants().aeat


@contextmanager
def _secure_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SESSION_BUCKET_ID) as profile:
        yield profile.paths.database_file


@contextmanager
def _profile_backend(tmp_path: Path, *, tax_id: str):
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session("11111111-1111-4111-8111-111111111111"),
    ):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(
            profile_id="11111111-1111-4111-8111-111111111111",
            overrides={"identity.tax_id": tax_id},
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
    casilla_110: Decimal,
    casilla_78: Decimal,
    casilla_87: Decimal,
    casilla_69: Decimal,
    casilla_71: Decimal,
    headers: tuple[ObservedHeaderFact, ...] = (_M303_DECLARATION_TYPE_C,),
) -> FiledDeclaracionObservation:
    """Build a submitted-file observation carrying the five carry-bearing casillas.

    The five values are stated directly rather than encoded into a fichero and
    read back out. What these tests exercise is the carry arithmetic downstream
    of the observation -- lot allocation, applied amounts, availability at
    period end -- and each scenario needs a specific combination of the five,
    which are calculation OUTPUTS no realistic set of inputs can be steered to.
    The round-trip this replaced ran through a page-03 byte-offset reader that
    no longer exists, and it never touched the export layout a real capture
    reads, so nothing about real parsing is lost here. The layout read itself is
    covered where it belongs, against exporter-produced ficheros, by the sede
    adapter's own submitted-file tests.
    """
    observation_period = Period.from_year_and_code(year, period)
    body = f"303-{year}-{period}-submitted-file".encode("ascii")
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
    observed = tuple(
        ObservedCasillaValue(
            casilla_id=casilla_id,
            value=str(value),
            value_kind=CasillaValueKind.NUMERIC,
            source_artefact_kind="submitted_file",
            source_locator=f"submitted-file:{official_number}",
            confidence=1.0,
        )
        for casilla_id, official_number, value in (
            (_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA, "110", casilla_110),
            (_M303_APLICADA_CASILLA, "78", casilla_78),
            (_M303_POSTERIOR_CASILLA, "87", casilla_87),
            (_M303_RESULTADO_CASILLA, "69", casilla_69),
            (_M303_RESULTADO_FINAL_CASILLA, "71", casilla_71),
        )
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
        headers=headers,
        extraction_coverage={"submitted_file": 1.0},
    )


def _stored_130_justificante_observation(
    store: FiledDeclaracionObservationStore,
    *,
    authenticated_identity: str = "00000000T",
    expediente_id: str = "13020260410ABCD1234EFGH5678",
    captured_csv: str = _MODELO_130_FIXTURE_CSV,
) -> FiledDeclaracionObservation:
    return _stored_justificante_observation(
        store,
        modelo="130",
        pdf_bytes=_modelo_130_justificante_pdf_bytes(),
        authenticated_identity=authenticated_identity,
        expediente_id=expediente_id,
        captured_csv=captured_csv,
    )


def _stored_303_justificante_observation(
    store: FiledDeclaracionObservationStore,
    *,
    authenticated_identity: str = "00000000T",
    # Register-shaped, and deliberately NOT the receipt's Número de justificante.
    # The 130 helper's default happens to equal its receipt's identifier, which
    # is what let the old conflated comparison pass in tests while failing on
    # every real capture; this default does not repeat that.
    expediente_id: str = "202630300000411A",
    captured_csv: str = _MODELO_303_FIXTURE_CSV,
) -> FiledDeclaracionObservation:
    return _stored_justificante_observation(
        store,
        modelo="303",
        pdf_bytes=_modelo_303_justificante_pdf_bytes(),
        authenticated_identity=authenticated_identity,
        expediente_id=expediente_id,
        captured_csv=captured_csv,
    )


def _stored_justificante_observation(
    store: FiledDeclaracionObservationStore,
    *,
    modelo: str,
    pdf_bytes: bytes,
    authenticated_identity: str,
    expediente_id: str,
    captured_csv: str,
) -> FiledDeclaracionObservation:
    """Store one receipt PDF under a cotejo-document artefact URL.

    ``captured_csv`` is the csv the capture would have resolved from AEAT's
    cotejo redirect, and it is a separate argument from the PDF bytes on
    purpose: passing a csv other than the one printed in those bytes is how a
    caller reproduces an artefact paired with the wrong filing's receipt.
    """
    period = Period.from_year_and_code(2026, "1T")
    artefact = store.persist_artefact(
        (modelo, 2026, period, expediente_id),
        FiledDeclaracionArtefact(
            kind="justificante_pdf",
            source_url=AnyHttpUrl(_cotejo_document_source_url(captured_csv)),
            content_type="application/pdf",
            byte_count=len(pdf_bytes),
            sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            captured_at=_CAPTURED_AT,
        ),
        pdf_bytes,
    )
    return FiledDeclaracionObservation(
        modelo=modelo,
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
    return _seed_current_filing(
        bucket_id=bucket_id,
        modelo="130",
        aeat_accepted=aeat_accepted,
        external_evidence=external_evidence,
    )


def _seed_current_303_filing(
    *,
    bucket_id: str,
    aeat_accepted: bool = False,
    external_evidence: ExternalEvidence | None = None,
) -> ModeloRecord:
    return _seed_current_filing(
        bucket_id=bucket_id,
        modelo="303",
        aeat_accepted=aeat_accepted,
        external_evidence=external_evidence,
    )


def _seed_current_filing(
    *,
    bucket_id: str,
    modelo: str,
    aeat_accepted: bool = False,
    external_evidence: ExternalEvidence | None = None,
) -> ModeloRecord:
    period = Period.from_year_and_code(2026, "1T")
    revision_id = hashlib.sha256(f"{bucket_id}:{modelo}:2026:1T".encode()).hexdigest()
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=2026,
        period=period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-2026-1T",
        created_at=_CAPTURED_AT,
        updated_at=_CAPTURED_AT,
    )
    work_unit_repo = WorkUnitCatalogueRepository()
    work_unit_repo.save(upsert_work_unit(work_unit_repo.load(), work_unit))
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="operator",
    )
    filing = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
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
    headers: tuple[ObservedHeaderFact, ...] = (_M303_DECLARATION_TYPE_N,),
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
                        value_kind=CasillaValueKind.NUMERIC,
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
                        value_kind=CasillaValueKind.NUMERIC,
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
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:87",
                confidence=1.0,
            ),
            ObservedCasillaValue(
                casilla_id=_M303_RESULTADO_CASILLA,
                value=str(result),
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:69",
                confidence=1.0,
            ),
            *(
                (
                    ObservedCasillaValue(
                        casilla_id=_M303_GENERADA_CASILLA,
                        value=str(generated),
                        value_kind=CasillaValueKind.NUMERIC,
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
                        value_kind=CasillaValueKind.NUMERIC,
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:71",
                        confidence=1.0,
                    ),
                )
                if final_result is not None
                else ()
            ),
        ),
        headers=headers,
        extraction_coverage={"submitted_file": 1.0},
        registry_snapshot_id=f"303:2022:{year}:{period}",
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
