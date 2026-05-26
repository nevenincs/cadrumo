"""Declaration-period casilla resolution from work-unit metadata.

``decl.ejercicio`` / ``decl.periodo`` are ``informational`` casillas:
AEAT requires them on the filed declaration, but they are neither
operator-entered figures nor formula outputs. Their values come
entirely from the work unit's ``(filing_year, period)`` axes.

These tests prove the calculate path projects the work unit's
metadata onto the matching semantic-role casillas, so a Modelo 303
calculation no longer leaves ``ejercicio``/``periodo`` at ``0``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.application.modelo import calculate_modelo_revision, create_work_unit
from aeat.core.resources import resources
from aeat.domain.buckets import BucketEventHistoryRepository
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_CLOCK = datetime(2026, 5, 21, 9, 0, 0, tzinfo=UTC)


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="operator"):
        yield


def _repositories():
    return (
        WorkUnitCatalogueRepository(),
        CalculationRevisionCatalogueRepository(),
        BucketEventHistoryRepository(),
    )


def _modelo_303_engine_inputs() -> dict[str, Decimal]:
    return {
        "modelo-303-iva-repercutido-general-cuota": Decimal("1000.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
    }


def _calculate_303(*, filing_year: int, period: str, period_date: date, tmp_path: Path):
    with _secure_backend(tmp_path):
        snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period)
        work_repo, calc_repo, event_repo = _repositories()
        work_unit = create_work_unit(
            bucket_id="operator",
            modelo="303",
            filing_year=filing_year,
            period=period,
            revision_id=snapshot.revision.id,
            repository=work_repo,
            clock=_CLOCK,
        )
        return calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values=_modelo_303_engine_inputs(),
            filing_period_date=period_date,
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_CLOCK,
        )


def test_modelo_303_declaration_year_resolves_from_work_unit_filing_year(tmp_path: Path) -> None:
    """``decl.ejercicio`` carries the work unit's filing year, not ``0``."""
    revision = _calculate_303(
        filing_year=2025,
        period="1T",
        period_date=date(2025, 3, 31),
        tmp_path=tmp_path,
    )
    assert revision.casilla_values["decl.ejercicio"] == Decimal("2025")


@pytest.mark.parametrize(
    ("period", "period_date", "expected_ordinal"),
    [
        ("1T", date(2026, 3, 31), Decimal("1")),
        ("2T", date(2026, 6, 30), Decimal("2")),
        ("3T", date(2026, 9, 30), Decimal("3")),
        ("4T", date(2026, 12, 31), Decimal("4")),
    ],
)
def test_modelo_303_declaration_period_resolves_from_work_unit_period(
    period: str,
    period_date: date,
    expected_ordinal: Decimal,
    tmp_path: Path,
) -> None:
    """``decl.periodo`` carries the work unit's quarter ordinal, not ``0``."""
    revision = _calculate_303(
        filing_year=2026,
        period=period,
        period_date=period_date,
        tmp_path=tmp_path,
    )
    assert revision.casilla_values["decl.periodo"] == expected_ordinal


def test_modelo_303_declaration_casillas_carry_registry_provenance(tmp_path: Path) -> None:
    """The informational casillas land as typed observations with legal grounding.

    A populated value with empty ``legal_refs`` / ``source_refs``
    would be a provenance-loss regression: the audit surface
    depends on every casilla carrying its registry grounding.
    """
    revision = _calculate_303(
        filing_year=2025,
        period="2T",
        period_date=date(2025, 6, 30),
        tmp_path=tmp_path,
    )
    observations = {obs.casilla_id: obs for obs in revision.observations}
    for casilla_id in ("decl.ejercicio", "decl.periodo"):
        observation = observations[casilla_id]
        assert observation.formula_id is None
        assert observation.legal_refs
        assert observation.source_refs
    assert observations["decl.ejercicio"].value == Decimal("2025")
    assert observations["decl.periodo"].value == Decimal("2")


def test_modelo_303_declaration_year_distinguishes_two_filing_years(tmp_path: Path) -> None:
    """Two work units differing only by filing year resolve distinct ejercicio values.

    Anti-tautology: the value is read off the work unit, so a
    different work unit must yield a different ``decl.ejercicio``.
    """
    revision_2024 = _calculate_303(
        filing_year=2024,
        period="1T",
        period_date=date(2024, 3, 31),
        tmp_path=tmp_path / "y2024",
    )
    revision_2026 = _calculate_303(
        filing_year=2026,
        period="1T",
        period_date=date(2026, 3, 31),
        tmp_path=tmp_path / "y2026",
    )
    assert revision_2024.casilla_values["decl.ejercicio"] == Decimal("2024")
    assert revision_2026.casilla_values["decl.ejercicio"] == Decimal("2026")
    assert (
        revision_2024.casilla_values["decl.ejercicio"]
        != revision_2026.casilla_values["decl.ejercicio"]
    )
