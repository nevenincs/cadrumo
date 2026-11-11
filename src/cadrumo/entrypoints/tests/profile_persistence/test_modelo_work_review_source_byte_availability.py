"""Work review assembly reads only embedded source bytes and keeps every citation."""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.work_review import ModeloWorkReview, build_modelo_work_review
from cadrumo.core.estado_casilla_oficial import EstadoCasillaOficial
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import T0, Repos

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"


def _review(
    repos: Repos,
    operation: PinnedAuthorityOperation,
    *,
    modelo: ModeloCode,
    filing_year: int,
    period_code: str,
) -> tuple[ModeloWorkReview, RegistrySnapshot]:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    period = Period.from_year_and_code(filing_year, period_code)
    revision = operation.revision_for_context(modelo, filing_year=filing_year, period=period.registry_token)
    snapshot = operation.snapshot(
        modelo,
        filing_year=filing_year,
        period=period.registry_token,
        revision_id=revision.id,
        grade=revision.effective_authority_grade,
    )
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision.id,
        name=f"{modelo}-{filing_year}-{period_code}",
        created_at=T0,
        updated_at=T0,
    )
    work_repo.save(upsert_work_unit(work_repo.load(), unit))
    review = build_modelo_work_review(
        _BUCKET_ID,
        modelo,
        filing_year,
        period,
        operation=operation,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
    )
    return review, snapshot


def _assert_rows_cite_registry_provenance(review: ModeloWorkReview, snapshot: RegistrySnapshot) -> None:
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    assert review.casillas
    for row in review.casillas:
        assert row.source_refs == tuple(casillas[row.casilla_id].source_refs)
        assert row.legal_refs == tuple(casillas[row.casilla_id].legal_refs)


def test_fixed_width_review_assembles_without_record_design_bytes(
    repos: Repos, operation: PinnedAuthorityOperation
) -> None:
    review, snapshot = _review(repos, operation, modelo=ModeloCode("130"), filing_year=2026, period_code="1T")
    record_designs = {
        str(source_id)
        for source_id, source in snapshot.sources.items()
        if source.kind is RegistrySourceKind.RECORD_DESIGN
    }
    assert record_designs
    for source_id in record_designs:
        with pytest.raises(LookupError):
            operation.source_evidence(source_id)

    _assert_rows_cite_registry_provenance(review, snapshot)
    cited = {str(ref) for row in review.casillas for ref in row.source_refs}
    assert record_designs & cited
    addressed = [row for row in review.casillas if row.estado_casilla_oficial is EstadoCasillaOficial.ADDRESSED]
    assert addressed
    assert all(row.official_reference == row.number for row in addressed)


def test_xml_dictionary_review_resolves_official_paths_from_embedded_dictionary(
    repos: Repos, operation: PinnedAuthorityOperation
) -> None:
    review, snapshot = _review(repos, operation, modelo=ModeloCode("100"), filing_year=2023, period_code="0A")

    _assert_rows_cite_registry_provenance(review, snapshot)
    addressed = [row for row in review.casillas if row.estado_casilla_oficial is EstadoCasillaOficial.ADDRESSED]
    assert addressed
    assert any(row.official_reference is not None and "/" in row.official_reference for row in addressed)
