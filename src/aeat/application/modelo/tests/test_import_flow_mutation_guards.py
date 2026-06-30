"""Work-unit and local-filing guard checks for external Modelo filing imports."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.modelos._calculation_revision import CalculationRevisionAmendmentKind
from ....domain.modelos._filing_record import ExternalEvidenceKind
from .. import (
    AmendmentEvidenceMissingError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    calculate_modelo_revision,
    create_work_unit,
    discard_work_unit,
    import_external_filing_evidence,
    mark_revision_verificado_completo,
)
from ._import_flow_support import (
    _IMPORT_INCOME_CASILLA,
    _M111_ACTIVITY_AMOUNT_CASILLA,
    _M111_ACTIVITY_COUNT_CASILLA,
    _M111_ACTIVITY_WITHHELD_CASILLA,
    _M111_AMENDMENT_CASILLA,
    _M111_EMPLOYMENT_WITHHELD_CASILLA,
    _M111_FORESTRY_WITHHELD_CASILLA,
    _M111_IMAGE_RIGHTS_WITHHELD_CASILLA,
    _M111_IMPUTED_INCOME_WITHHELD_CASILLA,
    _M111_PRIZE_WITHHELD_CASILLA,
    _M111_PROFESSIONAL_WITHHELD_CASILLA,
    _M111_TOTAL_WITHHELD_CASILLA,
    _PROFILE_ID,
    _T0,
    _T1,
    _T2,
    _T3,
    _T4,
    _import_external_filing,
    _Repos,
    _repos,
    _seed_local_filing_record,
    _seed_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    yield from _repos(tmp_path)


def test_import_refuses_discarded_work_unit(repos: _Repos) -> None:
    """A discarded work unit cannot accept new imports."""

    wu_repo, _, _, _, bv_repo = repos
    work_unit = _seed_work_unit(wu_repo)
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator-A",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    with pytest.raises(WorkUnitMutationRefusedError):
        _import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUST-LATE",
            clock=_T2,
        )


def test_import_refuses_unknown_work_unit(repos: _Repos) -> None:
    """A work_unit_id absent from the catalogue is rejected."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    with pytest.raises(WorkUnitNotFoundError):
        import_external_filing_evidence(
            work_unit_id="0" * 64,
            casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500")},
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="JUST-WHATEVER",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )


def test_amend_locally_filed_still_refused_after_import_path_exists(repos: _Repos) -> None:
    """The import path does not loosen the local-filing amendment evidence gate."""

    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="111",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={
            _M111_EMPLOYMENT_WITHHELD_CASILLA: Decimal("180.25"),
            _M111_PROFESSIONAL_WITHHELD_CASILLA: Decimal("12.10"),
            _M111_PRIZE_WITHHELD_CASILLA: Decimal("300.00"),
            _M111_IMAGE_RIGHTS_WITHHELD_CASILLA: Decimal("14.40"),
            _M111_FORESTRY_WITHHELD_CASILLA: Decimal("25.00"),
            _M111_IMPUTED_INCOME_WITHHELD_CASILLA: Decimal("0.50"),
            _M111_ACTIVITY_COUNT_CASILLA: Decimal("7.00"),
            _M111_ACTIVITY_AMOUNT_CASILLA: Decimal("8.00"),
            _M111_ACTIVITY_WITHHELD_CASILLA: Decimal("9.00"),
            _M111_TOTAL_WITHHELD_CASILLA: Decimal("40.00"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    verified_revision = mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator-A",
        calculation_repository=cr_repo,
        clock=_T2,
    )
    locally_filed = _seed_local_filing_record(
        work_unit=work_unit,
        revision_id=verified_revision.calculation_revision_id,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        filed_at=_T3,
        filed_by="operator-A",
    )
    assert locally_filed.external_evidence is None

    with pytest.raises(AmendmentEvidenceMissingError, match=r"external_evidence|imported|baseline"):
        amend_modelo_revision(
            from_filing_record_id=locally_filed.filing_record_id,
            overrides={_M111_AMENDMENT_CASILLA: Decimal("1700")},
            amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            reason="needed to amend",
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T4,
        )
