"""Result-summary labels follow the active output language."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.modelo._result_summary import calculation_result_summary
from ....application.workflow.persistence import workflow_state_repository
from ....core.period import Period
from ....core.config import override_settings
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.registry_observations import registry_grounded_observations
from .._modelo_rendering import result_summary_lines, result_summary_payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "33333333-3333-4333-8333-333333333333"
_NOW = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")
_REVISION_ID = "2019-y-siguientes"

_isolated_backend = active_profile_isolated_backend_fixture(bucket_id=_PROFILE_ID, dispose_engine_around=True)


def _seed_m130_work_unit() -> WorkUnit:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        revision_id=_REVISION_ID,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=_PERIOD,
        revision_id=_REVISION_ID,
        name="130-2026-1T",
        created_at=_NOW,
        updated_at=_NOW,
    )
    repository = WorkUnitCatalogueRepository()
    repository.save(upsert_work_unit(repository.load(), work_unit))
    return work_unit


def _m130_revision(work_unit: WorkUnit) -> CalculationRevision:
    casilla_values = {"03": Decimal("123.45")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=casilla_values,
        ),
        created_at=_NOW,
        updated_at=_NOW,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_result_summary_rows_render_requested_localized_label() -> None:
    """Modelo result-summary labels resolve for the active output language.

    The row label is the display projection of the casilla label and is
    resolved once, in the application layer, so it follows the requested
    language rather than carrying a locale map the renderer has to unpack.
    Under ``es`` it is the official Spanish label the registry grounds, which
    is the channel regulatory and export consumers read; the summary itself is
    an operator display surface and localizes.
    """

    work_unit = _seed_m130_work_unit()
    revision = _m130_revision(work_unit)

    with override_settings(cadrumo_output_language="es"):
        summary = calculation_result_summary(revision)
        assert summary is not None
        row = next(item for item in summary.rows if item.casilla_id == "03")
        assert row.label == "Rendimiento neto"
        assert "localized_labels" not in row.model_dump()

    with override_settings(cadrumo_output_language="ca"):
        lines = result_summary_lines(revision)
        payload = result_summary_payload(revision)

    rendered = "\n".join(lines)
    assert "key_figure\t03\t123.45\tRendiment net" in rendered
    assert "Rendimiento neto" not in rendered

    payload_row = next(item for item in payload if item.casilla_id == "03")
    assert payload_row.label == "Rendiment net"
    assert "localized_labels" not in payload_row.model_dump()


def test_result_summary_row_refuses_an_unknown_role() -> None:
    """The application and CLI rows both refuse a role outside the closed taxonomy."""
    from pydantic import ValidationError

    from ....application.modelo._result_summary import ResultSummaryRow
    from .._modelo_revision_payload_parts import ResultSummaryRowPayload

    with pytest.raises(ValidationError):
        ResultSummaryRow(casilla_id="03", label="Rendimiento neto", value=Decimal("123.45"), role="bogus")

    with pytest.raises(ValidationError):
        ResultSummaryRowPayload(casilla_id="03", label="Rendimiento neto", value="123.45", role="bogus")


def test_result_summary_row_accepts_every_canonical_role() -> None:
    """Every canonical role round-trips through both the application row and the CLI payload."""
    from ....application.modelo._result_summary import (
        ResultSummaryRole,
        ResultSummaryRow,
    )
    from .._modelo_revision_payload_parts import ResultSummaryRowPayload

    for role in ResultSummaryRole:
        row = ResultSummaryRow(casilla_id="03", label="Rendimiento neto", value=Decimal("123.45"), role=role)
        assert row.role is role
        payload = ResultSummaryRowPayload(casilla_id="03", label="Rendimiento neto", value="123.45", role=role)
        assert payload.role is role
