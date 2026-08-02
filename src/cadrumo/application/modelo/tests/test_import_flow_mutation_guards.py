"""Work-unit and local-filing guard checks for external Modelo filing imports."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Period
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
    ExternalEvidenceKind,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    AmendmentEvidenceMissingError,
    CalculationRevisionNotFoundError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    calculate_modelo_revision,
    create_work_unit,
    discard_work_unit,
    get_calculation_revision,
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


def test_import_refuses_a_work_unit_outside_the_repository_bucket(tmp_path: Path) -> None:
    """A bucket-B work unit cannot be imported through A-bound repositories.

    ``import_external_filing_evidence`` loaded the WorkUnit by id from a
    caller-supplied repository and never checked that repository's bucket against
    ``work_unit.bucket_id``, then used separately supplied calculation, filing,
    work-unit, and event repositories for the whole mutation. A caller could
    persist a B-bucket filing through A-bound stores, advance B pointers, and
    emit a B event with no cross-bucket refusal.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_GUARD_BUCKET_A) as profile:
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_GUARD_BUCKET_A, objects=profile.repository)
        cr_repo = CalculationRevisionCatalogueRepository(objects=profile.repository)
        fr_repo = ModeloRecordCatalogueRepository(objects=profile.repository)
        bv_repo = BucketEventHistoryRepository(objects=profile.repository)
        foreign = _guard_work_unit(_GUARD_BUCKET_B)
        wu_repo.save(upsert_work_unit(wu_repo.load(), foreign))

        with pytest.raises(WorkUnitNotFoundError):
            import_external_filing_evidence(
                work_unit_id=foreign.work_unit_id,
                casilla_values={_GUARD_INCOME_CASILLA: Decimal("1500")},
                evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                evidence_reference_id="JUST-GUARD-FOREIGN",
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
                filing_repository=fr_repo,
                bucket_event_repository=bv_repo,
                expected_tax_id="X1234567L",
                clock=_GUARD_CLOCK,
            )

        # Nothing advanced, nothing filed, nothing recorded for bucket B.
        assert wu_repo.load().get(foreign.work_unit_id) == foreign
        assert len(cr_repo.load()) == 0
        assert bv_repo.load().events == {}


def test_the_foreign_import_target_is_genuinely_present(tmp_path: Path) -> None:
    """Anti-tautology: the refusal above is bucket scope, not an absent unit."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_GUARD_BUCKET_A) as profile:
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_GUARD_BUCKET_A, objects=profile.repository)
        foreign = _guard_work_unit(_GUARD_BUCKET_B)
        wu_repo.save(upsert_work_unit(wu_repo.load(), foreign))

        stored = wu_repo.load().get(foreign.work_unit_id)

    assert stored is not None
    assert stored.bucket_id == _GUARD_BUCKET_B


def test_calculation_revision_actions_refuse_a_foreign_work_unit(tmp_path: Path) -> None:
    """A foreign revision already present in A's stores is not addressable by A."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_GUARD_BUCKET_A) as profile:
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_GUARD_BUCKET_A, objects=profile.repository)
        cr_repo = CalculationRevisionCatalogueRepository(bucket_id=_GUARD_BUCKET_A, objects=profile.repository)
        foreign = _guard_work_unit(_GUARD_BUCKET_B)
        wu_repo.save(upsert_work_unit(wu_repo.load(), foreign))
        revision = CalculationRevision(
            calculation_revision_id=derive_calculation_revision_id(
                work_unit_id=foreign.work_unit_id,
                input_values_by_casilla_id={},
                binding_overrides={},
                casilla_values={},
            ),
            work_unit_id=foreign.work_unit_id,
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id={},
            casilla_values={},
            created_at=_GUARD_CLOCK,
            updated_at=_GUARD_CLOCK,
        )
        cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))

        with pytest.raises(CalculationRevisionNotFoundError):
            get_calculation_revision(
                revision.calculation_revision_id,
                calculation_repository=cr_repo,
                work_unit_repository=wu_repo,
            )
        with pytest.raises(CalculationRevisionNotFoundError):
            mark_revision_verificado_completo(
                revision.calculation_revision_id,
                actor="operator-A",
                calculation_repository=cr_repo,
                work_unit_repository=wu_repo,
                clock=_GUARD_CLOCK,
            )

        assert cr_repo.load().get(revision.calculation_revision_id) == revision


_GUARD_BUCKET_A = "6aa00000-0000-4000-8000-0000000000aa"
_GUARD_BUCKET_B = "6bb00000-0000-4000-8000-0000000000bb"
_GUARD_CLOCK = _T1
_GUARD_INCOME_CASILLA = _IMPORT_INCOME_CASILLA


def _guard_work_unit(bucket_id: str) -> WorkUnit:
    """Build a valid M130 work unit owned by ``bucket_id``."""
    period = Period.from_year_and_code(2026, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id="2019-y-siguientes",
        ),
        bucket_id=bucket_id,
        name="130-2026-1T",
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id="2019-y-siguientes",
        created_at=_T0,
        updated_at=_T0,
    )
