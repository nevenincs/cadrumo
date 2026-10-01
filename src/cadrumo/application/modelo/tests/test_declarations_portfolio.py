"""One stale historical coordinate cannot erase healthy persisted declarations."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Never

import pytest

from ....core.period import Period
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.filing_record import ModeloRecordCatalogue
from ....domain.modelos.work_unit import WorkUnitCatalogue, WorkUnitState
from ....entrypoints.adapter_composition import build_work_lifecycle_ports
from ....entrypoints.tests.modelo_operator_work_storage import SEEDED_AT, SeededOperatorWork, seeded_operator_work
from ..action_errors import WorkUnitMutationRefusedError
from ..calculation_actions import calculate_modelo_revision
from ..declaration_summary import DeclarationSummaryState
from ..declarations_portfolio import project_declarations_portfolio
from ..declarations_workspace import (
    DeclarationsLifecycleKind,
    DeclarationsSanitizedLifecycleFactV1,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneObservationV1,
)
from ..work_lifecycle import create_work_unit, discard_work_unit

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]
_FIRST = Period.from_year_and_code(2026, "1T")
_SECOND = Period.from_year_and_code(2026, "2T")


@pytest.fixture(scope="module")
def two_persisted(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SeededOperatorWork]:
    with seeded_operator_work(tmp_path_factory.mktemp("portfolio-two")) as persisted:
        period = Period.from_year_and_code(2026, "2T")
        second = create_work_unit(
            bucket_id=persisted.work_unit.bucket_id,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id=str(persisted.operation.revision_for_context("130", filing_year=2026, period="2T").id),
            ports=build_work_lifecycle_ports(bucket_id=persisted.work_unit.bucket_id),
            clock=SEEDED_AT,
            operation=persisted.operation,
        )
        for unit, income in ((persisted.work_unit, "5000"), (second, "7000")):
            calculate_modelo_revision(
                unit.work_unit_id,
                ports=persisted.ports,
                clock=SEEDED_AT,
                casilla_inputs={
                    "01": Decimal(income),
                    "02": Decimal(0),
                    "06": Decimal(0),
                    "08": Decimal(0),
                    "10": Decimal(0),
                    "16": Decimal(0),
                    "18": Decimal(0),
                },
                binding_values={
                    "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                    "modelo-130-actividad-economica-rendimiento-neto-cumulative": Decimal(income),
                    "modelo-130-resultados-negativos-anteriores": Decimal(0),
                    "modelo-130-pagos-fraccionados-anteriores": Decimal(0)
                    if unit.period == _FIRST
                    else Decimal("1000"),
                },
            )
        assert len(persisted.ports.work_unit_repository.load().work_units) == 2
        assert len(persisted.ports.calculation_repository.load().revisions) == 2
        yield persisted


def _catalogues(
    persisted: SeededOperatorWork, *, stale: bool
) -> tuple[WorkUnitCatalogue, CalculationRevisionCatalogue]:
    work = persisted.ports.work_unit_repository.load()
    revisions = persisted.ports.calculation_repository.load()
    if stale:
        second = next(unit for unit in work.values() if unit.period == _SECOND)
        assert second.current_calculation_revision_id is not None
        head = revisions.revisions[second.current_calculation_revision_id]
        # The catalogues were reloaded from real encrypted storage. This
        # controlled historical read copy simulates a producing revision no
        # longer available in the pinned authority. The repository's
        # write guard is preserved; nothing corrupt is planted in storage.
        bad = head.model_copy(
            update={
                "registry_snapshot_ref": head.registry_snapshot_ref.model_copy(
                    update={"revision_id": "unavailable-historical-revision"},
                )
            }
        )
        revisions = revisions.model_copy(
            update={"revisions": {**revisions.revisions, head.calculation_revision_id: bad}}
        )
    return work, revisions


def _observations(*, declarations_unavailable: bool = False) -> tuple[DeclarationsWorkspaceZoneObservationV1, ...]:
    return tuple(
        DeclarationsWorkspaceZoneObservationV1(
            zone=zone,
            availability=DeclarationsWorkspaceAvailability.UNAVAILABLE
            if declarations_unavailable and zone is DeclarationsWorkspaceZone.DECLARATIONS
            else DeclarationsWorkspaceAvailability.AVAILABLE,
            observed_at=None
            if declarations_unavailable and zone is DeclarationsWorkspaceZone.DECLARATIONS
            else SEEDED_AT,
            reason_code="declarations.source.unavailable"
            if declarations_unavailable and zone is DeclarationsWorkspaceZone.DECLARATIONS
            else None,
        )
        for zone in DeclarationsWorkspaceZone
    )


def _no_form(*args: object, **kwargs: object) -> Never:
    raise AssertionError("a portfolio projection must never build individual editor forms")


def test_two_real_rows_survive_one_stale_coordinate_without_its_amount_or_history(
    two_persisted: SeededOperatorWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cadrumo.application.modelo.work_form.build_modelo_work_form", _no_form)
    work, revisions = _catalogues(two_persisted, stale=True)
    read_periods: list[Period] = []

    def result_box(modelo: str, year: int, period: Period) -> str:
        assert modelo == "130" and year == 2026
        read_periods.append(period)
        return "19"

    projection = project_declarations_portfolio(
        operation=two_persisted.operation,
        bucket_id=two_persisted.work_unit.bucket_id,
        work_units=work,
        calculation_revisions=revisions,
        filing_records=ModeloRecordCatalogue(),
        lifecycle_facts=(),
        zone_observations=_observations(),
        result_casilla_reader=result_box,
    )
    assert len(projection.declarations) == 2
    healthy = next(row for row in projection.declarations if row.period == _FIRST)
    bad = next(row for row in projection.declarations if row.period == _SECOND)
    assert Decimal(healthy.settled_result or "NaN") == Decimal("1000")
    assert healthy.summary is None or healthy.summary.state is not DeclarationSummaryState.UNREADABLE
    assert bad.settled_result is None
    assert bad.summary is not None and bad.summary.state is DeclarationSummaryState.UNREADABLE
    assert bad.summary.result is None and bad.summary.technical_reason
    assert "technical_reason" not in bad.summary.model_dump()
    assert read_periods == [Period.from_year_and_code(2026, "1T")]
    assert all(row.work_unit_id == healthy.work_unit_id for row in projection.calculation_revisions)
    assert len(projection.calculation_revisions) == 1
    assert projection.filings == () and projection.lifecycle == ()
    assert all(zone.availability is DeclarationsWorkspaceAvailability.STALE for zone in projection.zones)
    assert all(zone.reason_code == "workbench.declarations.partial_read" for zone in projection.zones)


def test_orphan_history_is_an_explicit_partial_source_without_erasing_valid_work(
    two_persisted: SeededOperatorWork,
) -> None:
    work, revisions = _catalogues(two_persisted, stale=False)
    orphan = DeclarationsSanitizedLifecycleFactV1(
        fact_id="portfolio-orphan",
        work_unit_id="f" * 64,
        occurred_at=SEEDED_AT,
        kind=DeclarationsLifecycleKind.CREATED,
    )
    projection = project_declarations_portfolio(
        operation=two_persisted.operation,
        bucket_id=two_persisted.work_unit.bucket_id,
        work_units=work,
        calculation_revisions=revisions,
        filing_records=ModeloRecordCatalogue(),
        lifecycle_facts=(orphan,),
        zone_observations=_observations(),
    )
    assert len(projection.declarations) == len(projection.calculation_revisions) == 2
    assert projection.lifecycle == ()
    history = next(zone for zone in projection.zones if zone.zone is DeclarationsWorkspaceZone.FILING_HISTORY)
    assert history.availability is DeclarationsWorkspaceAvailability.STALE
    assert history.reason_code == "workbench.declarations.partial_read" and history.item_count == 0


def test_unavailable_declaration_source_never_exposes_even_a_refused_row(two_persisted: SeededOperatorWork) -> None:
    work, revisions = _catalogues(two_persisted, stale=True)
    projection = project_declarations_portfolio(
        operation=two_persisted.operation,
        bucket_id=two_persisted.work_unit.bucket_id,
        work_units=work,
        calculation_revisions=revisions,
        filing_records=ModeloRecordCatalogue(),
        lifecycle_facts=(),
        zone_observations=_observations(declarations_unavailable=True),
    )
    assert projection.declarations == ()
    source = next(zone for zone in projection.zones if zone.zone is DeclarationsWorkspaceZone.DECLARATIONS)
    assert source.availability is DeclarationsWorkspaceAvailability.UNAVAILABLE
    assert source.item_count is None


def test_real_discard_remains_readable_and_the_same_target_refuses_recreation(tmp_path: Path) -> None:
    # The production identity is coordinate-addressed. A discarded root can
    # be read, but current lifecycle doors cannot create a replacement with
    # a different ID for this same address. Do not manufacture that history.
    with seeded_operator_work(tmp_path) as persisted:
        ports = build_work_lifecycle_ports(bucket_id=persisted.work_unit.bucket_id)
        discarded = discard_work_unit(
            persisted.work_unit_id,
            actor="test:portfolio",
            reason="Synthetic abandoned draft",
            ports=ports,
            clock=SEEDED_AT + timedelta(minutes=1),
        )
        with pytest.raises(WorkUnitMutationRefusedError):
            create_work_unit(
                bucket_id=discarded.bucket_id,
                modelo=str(discarded.modelo),
                filing_year=discarded.filing_year,
                period=discarded.period,
                revision_id=discarded.revision_id,
                name="Synthetic replacement",
                ports=ports,
                clock=SEEDED_AT + timedelta(minutes=2),
                operation=persisted.operation,
            )
        projection = project_declarations_portfolio(
            operation=persisted.operation,
            bucket_id=discarded.bucket_id,
            work_units=ports.work_unit_repository.load(),
            calculation_revisions=persisted.ports.calculation_repository.load(),
            filing_records=ModeloRecordCatalogue(),
            lifecycle_facts=(),
            zone_observations=_observations(),
        )
        assert len(projection.declarations) == 1
        row = projection.declarations[0]
        assert row.work_unit_id == discarded.work_unit_id
        assert row.state is WorkUnitState.DESCARTADO
        assert row.summary is None or row.summary.state is not DeclarationSummaryState.UNREADABLE
        assert row.settled_result is None
        assert all(zone.availability is DeclarationsWorkspaceAvailability.AVAILABLE for zone in projection.zones)
