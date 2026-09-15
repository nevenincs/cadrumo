"""Narrowed except-clause contracts for modelo result-summary helpers.

Verifies:
  The narrowed except clauses in the advisory predicate evaluator,
      result-summary lookup, and ledger bulk-classify loop honestly handle
      typed failures without swallowing unrelated behavior.
"""

from __future__ import annotations

import decimal
from datetime import UTC, datetime
from typing import NoReturn

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.hierarchy import CadrumoError
from ....core.period import Period
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..action_errors import WorkUnitRevisionDivergenceError
from ..verification_predicates import evaluate_advisory_predicate_fires

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORK_UNIT_BUCKET = "result-summary-narrowing-test"
_WORK_UNIT_REVISION = "2026-y-siguientes"
_WORK_UNIT_NOW = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_WORK_UNIT_BUCKET,
            modelo="303",
            filing_year=2026,
            period=period,
            revision_id=_WORK_UNIT_REVISION,
        ),
        bucket_id=_WORK_UNIT_BUCKET,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id=_WORK_UNIT_REVISION,
        name="303-2026-1T",
        created_at=_WORK_UNIT_NOW,
        updated_at=_WORK_UNIT_NOW,
    )


# ---------------------------------------------------------------------------
# (b) Narrowed except clauses propagate non-typed exceptions
# ---------------------------------------------------------------------------


class TestAdvisoryPredicateDecimalNarrowing:
    """evaluate_advisory_predicate_fires only catches InvalidOperation on threshold parse."""

    _VALID_EXPR = 'advisory_when_ratio_ge(["num_id", "den_id", "0.5"])'
    _INVALID_THR_EXPR = 'advisory_when_ratio_ge(["num_id", "den_id", "notadecimal"])'

    @pytest.mark.parametrize(
        ("expression", "values", "expected"),
        (
            pytest.param(
                _INVALID_THR_EXPR,
                {"num_id": decimal.Decimal("2"), "den_id": decimal.Decimal("1")},
                False,
                id="invalid-threshold",
            ),
            pytest.param(
                _VALID_EXPR,
                {"num_id": decimal.Decimal("2"), "den_id": decimal.Decimal("1")},
                True,
                id="ratio-meets-threshold",
            ),
            pytest.param(
                _VALID_EXPR,
                {"num_id": decimal.Decimal("0.1"), "den_id": decimal.Decimal("1")},
                False,
                id="ratio-below-threshold",
            ),
        ),
    )
    def test_advisory_ratio_predicate_decimal_threshold_cases(
        self,
        expression: str,
        values: dict[str, decimal.Decimal],
        expected: bool,
    ) -> None:
        result = evaluate_advisory_predicate_fires(expression, values)
        assert result is expected, expression


class TestResultSummaryNarrowing:
    """calculation_result_summary returns None on typed errors, propagates unexpected ones."""

    def _revision(self) -> CalculationRevision:
        work_unit_id = _work_unit().work_unit_id
        revision_id = derive_calculation_revision_id(
            work_unit_id=work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )
        return CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=work_unit_id,
            registry_snapshot_ref=RegistrySnapshotRef(
                modelo="303",
                revision_id="2026-y-siguientes",
                modelo_year=2026,
                period="1T",
            ),
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id={},
            casilla_values={},
            created_at=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
            updated_at=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
            filing_instance_evidence=None,
            source_provenance=(),
        )

    def test_cadrumo_error_from_get_work_unit_returns_none(self, operation: PinnedAuthorityOperation) -> None:
        """An CadrumoError from get_work_unit is caught and returns None."""
        from ..result_summary import calculation_result_summary

        def _raising(work_unit_id: str) -> NoReturn:
            del work_unit_id
            raise CadrumoError("typed failure")

        result = calculation_result_summary(self._revision(), work_unit_resolver=_raising, operation=operation)

        assert result is None

    def test_lookup_error_from_get_work_unit_returns_none(self, operation: PinnedAuthorityOperation) -> None:
        """A LookupError from get_work_unit returns None."""
        from ..result_summary import calculation_result_summary

        def _raising(work_unit_id: str) -> NoReturn:
            del work_unit_id
            raise LookupError("not found")

        result = calculation_result_summary(self._revision(), work_unit_resolver=_raising, operation=operation)

        assert result is None

    def test_summary_requests_calculation_grade_snapshot(
        self, monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation
    ) -> None:
        """Displaying a calculation must not strengthen authority to filing grade."""
        from .. import result_summary

        observed: list[RegistryAuthorityGrade] = []

        def _capture_grade(_work_unit: object, *, grade: RegistryAuthorityGrade) -> NoReturn:
            observed.append(grade)
            raise CadrumoError("stop after observing the requested grade")

        monkeypatch.setattr(result_summary, "_resolve_registry_snapshot_for_work_unit", _capture_grade)

        assert (
            result_summary.calculation_result_summary(
                self._revision(), work_unit_resolver=lambda _work_unit_id: _work_unit(), operation=operation
            )
            is None
        )
        assert observed == [RegistryAuthorityGrade.CALCULATION]

    def test_runtime_error_from_get_work_unit_propagates(self, operation: PinnedAuthorityOperation) -> None:
        """A RuntimeError from get_work_unit propagates — not swallowed."""
        from ..result_summary import calculation_result_summary

        def _raising(work_unit_id: str) -> NoReturn:
            del work_unit_id
            raise RuntimeError("unexpected db failure")

        with pytest.raises(RuntimeError, match="unexpected db failure"):
            calculation_result_summary(self._revision(), work_unit_resolver=_raising, operation=operation)

    def test_stale_registry_coordinate_refuses_before_summary_projection(
        self, operation: PinnedAuthorityOperation
    ) -> None:
        """A display fallback cannot expose values from a drifted revision."""
        from ..result_summary import calculation_result_summary

        revision = self._revision().model_copy(
            update={
                "registry_snapshot_ref": self._revision().registry_snapshot_ref.model_copy(
                    update={"revision_id": "persisted-stale-revision"}
                )
            }
        )

        with pytest.raises(WorkUnitRevisionDivergenceError):
            calculation_result_summary(
                revision, work_unit_resolver=lambda _work_unit_id: _work_unit(), operation=operation
            )
