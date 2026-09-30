"""A declaration's form states the latest file exported for it, and whether it still matches.

Driven over real encrypted storage: a revision is seeded, exported through the
real export service, which appends the durable export event, and the form is
read back through the real form loader with the profile's event history. A
declaration never exported states no export; one exported from its current
calculation states that file as current; once a newer calculation becomes the
declaration's current one, the same file is still stated, naming the older
calculation, and no longer current.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.modelo_export_support import (
    _M130_RESULT_CASILLA,
    export_taxpayer_profile,
    isolated_backend,
    seed_profile,
    seed_revision,
)
from cadrumo.application.modelo.export import ModeloExportCommand, export_modelo_revision
from cadrumo.application.modelo.export_ports import ModeloExportPorts
from cadrumo.application.modelo.work_form_models import ModeloWorkForm
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.work_unit import WorkUnitCatalogue

__all__ = ["isolated_backend"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FILING_YEAR = 2026
_PERIOD_CODE = "4T"
_PERIOD = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
_MODELO = ModeloCode("130")
# The profile's activity starts in the quarter, so no earlier quarter is owed
# and the cross-period gate has nothing to demand before the export.
_ACTIVITY_START = date(_FILING_YEAR, 10, 1)
_INGRESOS_CASILLA = validated_casilla_id("01", surface="work form last export test")
_GASTOS_CASILLA = validated_casilla_id("02", surface="work form last export test")
_FIRST_INPUTS = {_INGRESOS_CASILLA: "250.00", _GASTOS_CASILLA: "0.00"}
_LATER_INPUTS = {_INGRESOS_CASILLA: "300.00", _GASTOS_CASILLA: "0.00"}
_ZERO_PRIOR_BINDINGS: dict[BindingId, str] = {
    "modelo-130-pagos-fraccionados-anteriores": "0",
    "modelo-130-resultados-negativos-anteriores": "0",
    "irpf.previous_year_economic_activity_net_income": "0",
}
_RESULT = Decimal("-50.00")
_EXPORTED_AT = datetime(_FILING_YEAR + 1, 1, 20, 12, 0, tzinfo=UTC)
_REFERENCE_DAY = date(_FILING_YEAR + 1, 1, 20)


def _seed(bucket_id: str, inputs: dict[CasillaId, str]) -> tuple[str, str]:
    return seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo=str(_MODELO),
        filing_year=_FILING_YEAR,
        period=_PERIOD_CODE,
        input_values_by_casilla_id=dict(inputs),
        binding_overrides=dict(_ZERO_PRIOR_BINDINGS),
        casilla_values={_M130_RESULT_CASILLA: _RESULT},
    )


def _make_current(ports: ModeloExportPorts, work_unit_id: str, calculation_revision_id: str) -> None:
    """Advance the work unit's current-calculation pointer, as a new calculation commits it.

    Seeding persists the calculation record only; the pointer the declaration
    reads its current calculation through is this one catalogue write.
    """

    def advance(catalogue: WorkUnitCatalogue) -> WorkUnitCatalogue:
        unit = catalogue.get(work_unit_id)
        assert unit is not None
        return upsert_work_unit(
            catalogue, unit.model_copy(update={"current_calculation_revision_id": calculation_revision_id})
        )

    ports.work_unit.mutate(advance)
    unit = ports.work_unit.load().get(work_unit_id)
    assert unit is not None
    assert unit.current_calculation_revision_id == calculation_revision_id


def _export(
    tmp_path: Path, ports: ModeloExportPorts, calculation_revision_id: str, operation: PinnedAuthorityOperation
) -> None:
    result = export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=calculation_revision_id,
            output_path=tmp_path / f"modelo-{_MODELO}-{_FILING_YEAR}-{_PERIOD_CODE}.txt",
            actor="operator",
        ),
        workflow_profile=export_taxpayer_profile().model_copy(update={"activity_start_date": _ACTIVITY_START}),
        export_ports=ports,
        clock=_EXPORTED_AT,
        operation=operation,
    )
    assert result.modelo == str(_MODELO)


def _form(
    bucket_id: str, ports: ModeloExportPorts, operation: PinnedAuthorityOperation, *, with_events: bool = True
) -> ModeloWorkForm:
    return load_modelo_work_form(
        bucket_id,
        _MODELO,
        _FILING_YEAR,
        _PERIOD,
        operation=operation,
        work_unit_repository=ports.work_unit,
        calculation_repository=ports.calculation,
        verification_repository=VerificationReportCatalogueRepository(bucket_id=bucket_id),
        admission=None,
        language=OutputLanguage.ES,
        reference_on=_REFERENCE_DAY,
        bucket_events=ports.bucket_event if with_events else None,
    ).form


def test_a_declaration_never_exported_states_no_export(isolated_backend: None) -> None:
    with bundled_indexed_authority().operation() as operation:
        bucket_id = seed_profile()
        ports = modelo_export_ports_for_test(bucket_id=bucket_id)
        work_unit_id, revision_id = _seed(bucket_id, _FIRST_INPUTS)
        _make_current(ports, work_unit_id, revision_id)
        form = _form(bucket_id, ports, operation)

    assert form.calculation_revision_id == revision_id
    assert form.last_export is None


def test_an_export_of_the_current_calculation_reads_back_as_current(isolated_backend: None, tmp_path: Path) -> None:
    with bundled_indexed_authority().operation() as operation:
        bucket_id = seed_profile()
        ports = modelo_export_ports_for_test(bucket_id=bucket_id)
        work_unit_id, revision_id = _seed(bucket_id, _FIRST_INPUTS)
        _make_current(ports, work_unit_id, revision_id)
        _export(tmp_path, ports, revision_id, operation)
        form = _form(bucket_id, ports, operation)
        without_events = _form(bucket_id, ports, operation, with_events=False)

    assert form.last_export is not None
    assert form.last_export.calculation_revision_id == revision_id
    assert form.last_export.current is True
    assert form.last_export.exported_at == _EXPORTED_AT
    # The event history is what states the export; without it the loader claims none.
    assert without_events.last_export is None


def test_an_export_of_an_earlier_calculation_reads_back_as_no_longer_current(
    isolated_backend: None, tmp_path: Path
) -> None:
    with bundled_indexed_authority().operation() as operation:
        bucket_id = seed_profile()
        ports = modelo_export_ports_for_test(bucket_id=bucket_id)
        work_unit_id, exported_revision_id = _seed(bucket_id, _FIRST_INPUTS)
        _make_current(ports, work_unit_id, exported_revision_id)
        _export(tmp_path, ports, exported_revision_id, operation)
        later_work_unit_id, later_revision_id = _seed(bucket_id, _LATER_INPUTS)
        assert later_work_unit_id == work_unit_id
        assert later_revision_id != exported_revision_id
        _make_current(ports, work_unit_id, later_revision_id)
        form = _form(bucket_id, ports, operation)

    assert form.calculation_revision_id == later_revision_id
    assert form.last_export is not None
    assert form.last_export.calculation_revision_id == exported_revision_id
    assert form.last_export.current is False
    assert form.last_export.exported_at == _EXPORTED_AT
