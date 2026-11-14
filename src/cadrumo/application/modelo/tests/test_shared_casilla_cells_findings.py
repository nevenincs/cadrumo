"""Verification shows the shared-cell refusal instead of passing and failing at export."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..preconditions import ModeloPreconditionFailure
from ..shared_casilla_cells_findings import append_shared_casilla_cells_findings
from ..work_form_findings import finding_action_locale_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_T0 = datetime(filing_year_envelope().horizon, 1, 15, 12, 0, 0, tzinfo=UTC)
_MODELO = "200"
_MESSAGE = "application.modelo.findings.shared_casilla_cells_unadjudicated"
_TRIBUTOS_SHEETS = {"DP200007", "DP200022", "DP200031", "DP200038", "DP200047", "DP200053"}


def _casilla(value: str) -> CasillaId:
    return validated_casilla_id(value, surface="test_shared_casilla_cells_findings")


def _work_unit(filing_year: int, revision_id: str) -> WorkUnit:
    modelo = ModeloCode(_MODELO)
    period = Period.from_year_and_code(filing_year, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="shared-casilla-cells",
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id="shared-casilla-cells",
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO}-{filing_year}-{period.registry_token}",
        created_at=_T0,
        updated_at=_T0,
    )


def _revision(work_unit: WorkUnit, casilla_values: dict[CasillaId, Decimal]) -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=casilla_values,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values=casilla_values,
        observations=tuple(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=("ley-27-2014:art-41",),
                source_refs=("shared-casilla-cells-test",),
            )
            for casilla_id, value in casilla_values.items()
        ),
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _shared_cell_findings(
    filing_year: int, casilla_values: dict[CasillaId, Decimal]
) -> tuple[list[ModeloVerificationFinding], set[str]]:
    """Run the shared-cell check verification applies to a revision resolved at filing grade, for one Modelo 200 year.

    Verification adds this check only for a revision that resolves at filing grade, and the
    2025 edition of Modelo 200 is held at calculation grade, so the check is applied to the
    edition's layout directly, as verification applies it.
    """
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.reading_snapshot(_MODELO, filing_year=filing_year, period="0A")
        work_unit = _work_unit(filing_year, str(snapshot.revision.id))
        findings: list[ModeloVerificationFinding] = []
        failures: dict[int, ModeloPreconditionFailure] = {}
        append_shared_casilla_cells_findings(
            target=_revision(work_unit, casilla_values),
            snapshot=snapshot,
            findings=findings,
            failures_by_finding_id=failures,
        )
    matching = [finding for finding in findings if finding.message_locale_key == _MESSAGE]
    return matching, {failures[id(finding)].scenario_id for finding in matching}


def _filing_year() -> int:
    return max(PublishedGovernedFactSource().supported_filing_years().years)


def test_a_written_shared_box_blocks_verification_naming_its_cells() -> None:
    findings, scenarios = _shared_cell_findings(_filing_year(), {_casilla("00281"): Decimal("123.45")})

    (finding,) = findings
    assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.casilla_id == "00281"
    sheets = {cell.split(".")[1].upper() for cell in str(finding.message_facts["target_cells"]).split(",")}
    assert sheets == _TRIBUTOS_SHEETS
    assert scenarios == {"modelo.work.verify.shared_casilla_cells.unadjudicated"}


def test_the_filer_is_not_told_to_empty_the_box() -> None:
    findings, _scenarios = _shared_cell_findings(_filing_year(), {_casilla("00281"): Decimal("123.45")})

    (finding,) = findings
    assert finding_action_locale_key(finding) == "application.modelo.work_form.finding_action.shared_box_awaits_review"


@pytest.mark.parametrize(
    "values",
    [
        pytest.param({"00281": Decimal("0")}, id="zero"),
        pytest.param({}, id="absent"),
        pytest.param({"DP200014:00547": Decimal("123.45")}, id="declared-echo"),
        pytest.param({"DP200012:00004": Decimal("123.45")}, id="one-cell"),
    ],
)
def test_what_the_export_writes_correctly_raises_no_finding(values: dict[str, Decimal]) -> None:
    findings, _scenarios = _shared_cell_findings(
        _filing_year(), {_casilla(casilla): value for casilla, value in values.items()}
    )

    assert findings == []
