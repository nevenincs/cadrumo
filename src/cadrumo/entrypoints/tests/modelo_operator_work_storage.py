"""Real encrypted storage for proving that operator work survives edits and recalculation.

Entrypoint tests consume this defining test-support module directly. It seeds
one complete synthetic taxpayer and one work unit through the production doors
(profile capsule, ``create_work_unit``) and hands back the composed calculation
ports, so a test drives the same calculation boundary, edit executor and
persistence writer production uses. Every value is synthetic.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ...adapters.persistence.storage.tests.profile_capsule_runtime import seed_modelo_ready_profile_record
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.modelo.calculation_action_ports import CalculationActionPorts
from ...application.modelo.work_lifecycle import create_work_unit
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit
from ..adapter_composition import build_calculation_action_ports, build_work_lifecycle_ports

SEEDED_AT = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_BUCKET_ID = "13000000-0000-4000-8000-000000000730"


@dataclass(frozen=True, slots=True)
class SeededOperatorWork:
    """One seeded work unit with the ports and pinned authority that calculate it."""

    work_unit: WorkUnit
    ports: CalculationActionPorts
    operation: PinnedAuthorityOperation

    @property
    def work_unit_id(self) -> str:
        return self.work_unit.work_unit_id

    def head(self) -> CalculationRevision | None:
        """Load the work unit's current calculation revision afresh from storage."""
        unit = self.ports.work_unit_repository.load().get(self.work_unit.work_unit_id)
        if unit is None or unit.current_calculation_revision_id is None:
            return None
        return self.ports.calculation_repository.load().get(unit.current_calculation_revision_id)

    def require_head(self) -> CalculationRevision:
        head = self.head()
        if head is None:
            raise AssertionError("the seeded work unit has no current calculation revision")
        return head


@contextmanager
def seeded_operator_work(
    tmp_path: Path,
    *,
    modelo: str = "130",
    filing_year: int = 2026,
    period_code: str = "1T",
) -> Generator[SeededOperatorWork]:
    """Yield one seeded, not yet calculated work unit over isolated encrypted storage."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
        bundled_indexed_authority().operation() as operation,
    ):
        seed_modelo_ready_profile_record(profile.bucket_id, clock=SEEDED_AT)
        period = Period.from_year_and_code(filing_year, period_code)
        revision = operation.revision_for_context(modelo, filing_year=filing_year, period=period.registry_token)
        unit = create_work_unit(
            bucket_id=profile.bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=str(revision.id),
            ports=build_work_lifecycle_ports(bucket_id=profile.bucket_id),
            clock=SEEDED_AT,
            operation=operation,
        )
        yield SeededOperatorWork(
            work_unit=unit,
            ports=build_calculation_action_ports(bucket_id=profile.bucket_id, operation=operation),
            operation=operation,
        )
