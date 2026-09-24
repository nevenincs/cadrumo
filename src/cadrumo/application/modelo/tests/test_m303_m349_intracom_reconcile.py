"""Real-behavior tests for the Modelo 303 <-> Modelo 349 intra-community reconcile.

The cross-validator reads the persisted totals of both declarations for the same
bucket and period and surfaces a non-blocking WARNING advisory when the Modelo
303 intra-community total (box 10 acquisitions + box 59 supplies) diverges from
 the Modelo 349 resumen total (``decl.importe-operaciones``) beyond a de-minimis
euro tolerance. These tests build both sides through local implementations of
the application-facing catalogue ports and the registry-grounded observation
fixtures, then assert the advisory fires on a genuine divergence and stays
silent when the totals reconcile. Encrypted catalogue round-trips belong to
the persistence adapter tests. The expected fire/silent outcomes derive from
the reconcile contract (which boxes, which tolerance), not from re-running any
registry formula, so they are not tautological calculation assertions.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...calculations.tests.filing_evidence import general_m303_filing_evidence
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.classification.policies import SensitivityClass
from ....core.period import Period
from ....core.secure_object_write import SecureObjectWrite
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.verification_report import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from .._m303_m349_reconcile import m303_m349_intracom_reconcile_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000349"
_CLOCK = datetime(2025, 4, 15, tzinfo=UTC)
_REPOSITORY_REVISION_ID = "0" * 64
_M303_ADQUISICIONES: CasillaId = validated_casilla_id("10", surface="test")
_M303_ENTREGAS: CasillaId = validated_casilla_id("59", surface="test")
_M349_IMPORTE_OPERACIONES: CasillaId = validated_casilla_id("decl.importe-operaciones", surface="test")


def _secure_write(
    *,
    namespace: str,
    object_key: str,
    payload: bytes,
    expected_revision_id: str | None = None,
) -> SecureObjectWrite:
    return SecureObjectWrite(
        namespace=namespace,
        object_key=object_key,
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=_CLOCK,
        payload=payload,
        expected_revision_id=expected_revision_id,
    )


class _InMemoryWorkUnitRepository:
    """Application-test fake for the work-unit catalogue port."""

    def __init__(self) -> None:
        self._catalogue = WorkUnitCatalogue()

    @property
    def bucket_id(self) -> str | None:
        return _BUCKET_ID

    def load(self) -> WorkUnitCatalogue:
        return self._catalogue

    def exists(self) -> bool:
        return bool(self._catalogue.work_units)

    def load_revisioned(self) -> tuple[WorkUnitCatalogue, str]:
        return self._catalogue, _REPOSITORY_REVISION_ID

    def save(self, catalogue: WorkUnitCatalogue) -> None:
        self._catalogue = catalogue

    def mutate(self, mutation: Callable[[WorkUnitCatalogue], WorkUnitCatalogue]) -> WorkUnitCatalogue:
        self._catalogue = mutation(self._catalogue)
        return self._catalogue

    def to_secure_object_write(
        self,
        catalogue: WorkUnitCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return _secure_write(
            namespace="application-test-work-units",
            object_key="m303-m349-reconcile",
            payload=catalogue.model_dump_json().encode("utf-8"),
            expected_revision_id=expected_revision_id,
        )

    def save_with_secure_object_writes(
        self,
        catalogue: WorkUnitCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        del extra_writes, expected_revision_id
        self._catalogue = catalogue


class _InMemoryCalculationRevisionRepository:
    """Application-test fake for the calculation-revision catalogue port."""

    def __init__(self) -> None:
        self._catalogue = CalculationRevisionCatalogue()

    @property
    def bucket_id(self) -> str | None:
        return _BUCKET_ID

    def load(self) -> CalculationRevisionCatalogue:
        return self._catalogue

    def exists(self) -> bool:
        return bool(self._catalogue.revisions)

    def load_revisioned(self) -> tuple[CalculationRevisionCatalogue, str]:
        return self._catalogue, _REPOSITORY_REVISION_ID

    def save(self, catalogue: CalculationRevisionCatalogue) -> None:
        self._catalogue = catalogue

    def to_secure_object_write(
        self,
        catalogue: CalculationRevisionCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return _secure_write(
            namespace="application-test-calculation-revisions",
            object_key="m303-m349-reconcile",
            payload=catalogue.model_dump_json().encode("utf-8"),
            expected_revision_id=expected_revision_id,
        )

    def save_with_secure_object_writes(
        self,
        catalogue: CalculationRevisionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        del extra_writes, expected_revision_id
        self._catalogue = catalogue


@pytest.fixture
def repositories() -> tuple[_InMemoryWorkUnitRepository, _InMemoryCalculationRevisionRepository]:
    return _InMemoryWorkUnitRepository(), _InMemoryCalculationRevisionRepository()


def _seed_work_unit(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    repository: _InMemoryWorkUnitRepository,
) -> WorkUnit:
    bucket_id = repository.bucket_id
    assert bucket_id is not None
    typed_period = Period.from_year_and_code(filing_year, period)
    revision_id = published_snapshot(modelo, filing_year=filing_year, period=typed_period.registry_token).revision.id
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{typed_period.registry_token}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    repository.save(upsert_work_unit(repository.load(), work_unit))
    return work_unit


def _build_revision(
    work_unit: WorkUnit, casilla_values: dict[CasillaId, Decimal], *, operation: PinnedAuthorityOperation
) -> CalculationRevision:
    filing_instance_evidence = (
        general_m303_filing_evidence(work_unit.period, reference="test:m303-m349-reconcile", operation=operation)
        if str(work_unit.modelo) == "303"
        else None
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=casilla_values,
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )


def _persist_revision(
    work_unit: WorkUnit,
    casilla_values: dict[CasillaId, Decimal],
    repository: _InMemoryCalculationRevisionRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> CalculationRevision:
    revision = _build_revision(work_unit, casilla_values, operation=operation)
    repository.save(upsert_calculation_revision(repository.load(), revision))
    return revision


def _m303_values(*, adquisiciones: Decimal, entregas: Decimal) -> dict[CasillaId, Decimal]:
    return {_M303_ADQUISICIONES: adquisiciones, _M303_ENTREGAS: entregas}


def _m349_values(*, importe: Decimal) -> dict[CasillaId, Decimal]:
    return {_M349_IMPORTE_OPERACIONES: importe}


def _reconcile(
    work_unit: WorkUnit,
    target: CalculationRevision,
    *,
    work_unit_repository: _InMemoryWorkUnitRepository,
    calculation_repository: _InMemoryCalculationRevisionRepository,
    operation: PinnedAuthorityOperation,
):
    return m303_m349_intracom_reconcile_findings(
        work_unit=work_unit,
        target=target,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        operation=operation,
    )


def test_advisory_fires_when_m303_intracom_exceeds_m349_resumen(
    repositories: tuple[_InMemoryWorkUnitRepository, _InMemoryCalculationRevisionRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_repository, calculation_repository = repositories
    m303 = _seed_work_unit(modelo="303", filing_year=2025, period="1T", repository=work_unit_repository)
    m349 = _seed_work_unit(modelo="349", filing_year=2025, period="1T", repository=work_unit_repository)
    target = _build_revision(
        m303, _m303_values(adquisiciones=Decimal("6000"), entregas=Decimal("4000")), operation=operation
    )
    _persist_revision(m349, _m349_values(importe=Decimal("8000")), calculation_repository, operation=operation)

    findings = _reconcile(
        m303,
        target,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        operation=operation,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ModeloVerificationFindingKind.RECONCILIATION_MISMATCH
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    # 303 total 6000 + 4000 = 10000 vs 349 resumen 8000 -> gap 2000.
    assert finding.message_locale_key == "application.modelo.findings.m303_m349_intracom_reconciliation_mismatch"
    assert finding.message_facts["m303_total"] == Decimal("10000")
    assert finding.message_facts["m349_total"] == Decimal("8000")
    assert finding.message_facts["gap"] == Decimal("2000")
    assert finding.legal_refs  # grounded, non-empty


def test_advisory_silent_when_totals_reconcile(
    repositories: tuple[_InMemoryWorkUnitRepository, _InMemoryCalculationRevisionRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_repository, calculation_repository = repositories
    m303 = _seed_work_unit(modelo="303", filing_year=2025, period="1T", repository=work_unit_repository)
    m349 = _seed_work_unit(modelo="349", filing_year=2025, period="1T", repository=work_unit_repository)
    target = _build_revision(
        m303, _m303_values(adquisiciones=Decimal("6000"), entregas=Decimal("4000")), operation=operation
    )
    _persist_revision(m349, _m349_values(importe=Decimal("10000")), calculation_repository, operation=operation)

    assert (
        _reconcile(
            m303,
            target,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            operation=operation,
        )
        == []
    )


def test_advisory_fires_when_verifying_the_m349_side(
    repositories: tuple[_InMemoryWorkUnitRepository, _InMemoryCalculationRevisionRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_repository, calculation_repository = repositories
    m303 = _seed_work_unit(modelo="303", filing_year=2025, period="1T", repository=work_unit_repository)
    m349 = _seed_work_unit(modelo="349", filing_year=2025, period="1T", repository=work_unit_repository)
    _persist_revision(
        m303,
        _m303_values(adquisiciones=Decimal("6000"), entregas=Decimal("4000")),
        calculation_repository,
        operation=operation,
    )
    target = _build_revision(m349, _m349_values(importe=Decimal("8000")), operation=operation)

    findings = _reconcile(
        m349,
        target,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        operation=operation,
    )

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.RECONCILIATION_MISMATCH
    assert findings[0].message_facts["m303_total"] == Decimal("10000")
    assert findings[0].message_facts["m349_total"] == Decimal("8000")


def test_no_finding_when_sibling_declaration_absent(
    repositories: tuple[_InMemoryWorkUnitRepository, _InMemoryCalculationRevisionRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_repository, calculation_repository = repositories
    m303 = _seed_work_unit(modelo="303", filing_year=2025, period="1T", repository=work_unit_repository)
    target = _build_revision(
        m303, _m303_values(adquisiciones=Decimal("6000"), entregas=Decimal("4000")), operation=operation
    )

    assert (
        _reconcile(
            m303,
            target,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            operation=operation,
        )
        == []
    )


def test_within_de_minimis_gap_is_silent(
    repositories: tuple[_InMemoryWorkUnitRepository, _InMemoryCalculationRevisionRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_repository, calculation_repository = repositories
    m303 = _seed_work_unit(modelo="303", filing_year=2025, period="1T", repository=work_unit_repository)
    m349 = _seed_work_unit(modelo="349", filing_year=2025, period="1T", repository=work_unit_repository)
    target = _build_revision(
        m303, _m303_values(adquisiciones=Decimal("6000"), entregas=Decimal("4000")), operation=operation
    )
    # gap of 0.50 EUR <= 1.00 de-minimis tolerance -> no advisory.
    _persist_revision(m349, _m349_values(importe=Decimal("9999.50")), calculation_repository, operation=operation)

    assert (
        _reconcile(
            m303,
            target,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            operation=operation,
        )
        == []
    )


def test_no_finding_when_nothing_intracommunity_declared(
    repositories: tuple[_InMemoryWorkUnitRepository, _InMemoryCalculationRevisionRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_repository, calculation_repository = repositories
    m303 = _seed_work_unit(modelo="303", filing_year=2025, period="1T", repository=work_unit_repository)
    m349 = _seed_work_unit(modelo="349", filing_year=2025, period="1T", repository=work_unit_repository)
    target = _build_revision(m303, _m303_values(adquisiciones=Decimal("0"), entregas=Decimal("0")), operation=operation)
    _persist_revision(m349, _m349_values(importe=Decimal("0")), calculation_repository, operation=operation)

    assert (
        _reconcile(
            m303,
            target,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            operation=operation,
        )
        == []
    )


def test_reconcile_skipped_for_unrelated_modelo(
    repositories: tuple[_InMemoryWorkUnitRepository, _InMemoryCalculationRevisionRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_repository, calculation_repository = repositories
    m130 = _seed_work_unit(modelo="130", filing_year=2024, period="1T", repository=work_unit_repository)
    # The reconcile short-circuits before reading any casilla for a non-303/349
    # modelo, so an empty-values draft (no grounded observations required) suffices.
    target = _build_revision(m130, {}, operation=operation)

    assert (
        _reconcile(
            m130,
            target,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            operation=operation,
        )
        == []
    )
