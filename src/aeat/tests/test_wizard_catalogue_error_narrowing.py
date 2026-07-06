"""Wizard catalogue error classes plus narrowed except-clause contracts.

Verifies:
  (a) The wizard-catalogue / project-answers error classes are registered
      in the error registry and produce valid ErrorEnvelope roundtrips.
  (b) The narrowed except clauses in the advisory predicate evaluator,
      result-summary lookup, and ledger bulk-classify loop honestly handle
      typed failures without swallowing unrelated behavior.
"""

from __future__ import annotations

import decimal
from datetime import UTC, datetime
from typing import NoReturn

import pytest

from ..core.errors import (
    AeatError,
    build_error_envelope,
    get_registered_error_code,
)
from ..core.setup_answers import ProjectAnswersNotRegisteredError
from ..core.wizard_catalogue import (
    WizardCatalogueAlreadyRegisteredError,
    WizardCatalogueNotRegisteredError,
)
from ..domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# (a) Registry + envelope roundtrip for the three new error classes
# ---------------------------------------------------------------------------


class TestNewErrorClassesRegistered:
    """The three new error classes are AeatError subclasses with registry entries."""

    # Declared as ``type[AeatError]`` (not inferred from the literal subclasses)
    # so ``test_envelope_roundtrip``'s fallback construction below type-checks
    # against the common base constructor rather than each member's own
    # override — two of the three hardcode a message and take no positional
    # arg, one inherits ``AeatError``'s optional-message constructor.
    _ERROR_CASES: tuple[tuple[type[AeatError], str], ...] = (
        (WizardCatalogueNotRegisteredError, "INTERNAL_WIZARD_CATALOGUE_NOT_REGISTERED"),
        (WizardCatalogueAlreadyRegisteredError, "INTERNAL_WIZARD_CATALOGUE_ALREADY_REGISTERED"),
        (ProjectAnswersNotRegisteredError, "INTERNAL_PROFILE_PROJECT_ANSWERS_NOT_REGISTERED"),
    )

    @pytest.mark.parametrize(("error_cls", "expected_code"), _ERROR_CASES)
    def test_error_classes_are_aeat_errors_with_registered_codes(
        self,
        error_cls: type[AeatError],
        expected_code: str,
    ) -> None:
        assert issubclass(error_cls, AeatError), error_cls.__name__
        code = get_registered_error_code(error_cls)
        assert code.code == expected_code

    @pytest.mark.parametrize(("error_cls", "_expected_code"), _ERROR_CASES)
    def test_envelope_roundtrip(self, error_cls: type[AeatError], _expected_code: str) -> None:
        """An instance can be built into an ErrorEnvelope without raising."""
        del _expected_code
        try:
            instance = error_cls()
        except TypeError:
            instance = error_cls("test message")
        envelope = build_error_envelope(instance)
        assert envelope.code == get_registered_error_code(error_cls).code
        assert envelope.message, error_cls.__name__


# ---------------------------------------------------------------------------
# (b) Narrowed except clauses propagate non-typed exceptions
# ---------------------------------------------------------------------------


class TestAdvisoryPredicateDecimalNarrowing:
    """_evaluate_advisory_predicate_fires only catches InvalidOperation on threshold parse."""

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
        from ..application.modelo._verification_actions import _evaluate_advisory_predicate_fires

        result = _evaluate_advisory_predicate_fires(expression, values)
        assert result is expected, expression


class TestResultSummaryNarrowing:
    """calculation_result_summary returns None on typed errors, propagates unexpected ones."""

    def _revision(self) -> CalculationRevision:
        work_unit_id = "0" * 64
        revision_id = derive_calculation_revision_id(
            work_unit_id=work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
        )
        return CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=work_unit_id,
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id={},
            casilla_values={},
            created_at=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
            updated_at=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
        )

    def test_aeat_error_from_get_work_unit_returns_none(self) -> None:
        """An AeatError from get_work_unit is caught and returns None."""
        from ..application.modelo import calculation_result_summary

        def _raising(work_unit_id: str) -> NoReturn:
            del work_unit_id
            raise ProjectAnswersNotRegisteredError()

        result = calculation_result_summary(self._revision(), work_unit_resolver=_raising)

        assert result is None

    def test_lookup_error_from_get_work_unit_returns_none(self) -> None:
        """A LookupError from get_work_unit returns None."""
        from ..application.modelo import calculation_result_summary

        def _raising(work_unit_id: str) -> NoReturn:
            del work_unit_id
            raise LookupError("not found")

        result = calculation_result_summary(self._revision(), work_unit_resolver=_raising)

        assert result is None

    def test_runtime_error_from_get_work_unit_propagates(self) -> None:
        """A RuntimeError from get_work_unit propagates — not swallowed."""
        from ..application.modelo import calculation_result_summary

        def _raising(work_unit_id: str) -> NoReturn:
            del work_unit_id
            raise RuntimeError("unexpected db failure")

        with pytest.raises(RuntimeError, match="unexpected db failure"):
            calculation_result_summary(self._revision(), work_unit_resolver=_raising)


class TestLedgerBulkClassifyNarrowing:
    """Bulk classify parsing reports typed row failures without aborting valid rows."""

    def test_parse_loop_collects_invalid_classification_and_keeps_valid_rows(self) -> None:
        from ..application.ledger._actions_classification import _parse_bulk_classify_rows
        from ..domain.transactions import BusinessClassification

        parsed_rows, failures = _parse_bulk_classify_rows(
            "\n".join(
                (
                    "transaction_id,classification",
                    "tx-valid,BUSINESS",
                    "tx-invalid,NOT_A_CLASSIFICATION",
                    "tx-personal,PERSONAL",
                ),
            ),
        )

        assert [row.transaction_id for _idx, row, _provided_columns in parsed_rows] == ["tx-valid", "tx-personal"]
        assert [row.classification for _idx, row, _provided_columns in parsed_rows] == [
            BusinessClassification.BUSINESS,
            BusinessClassification.PERSONAL,
        ]
        (failure,) = failures
        assert failure.row_index == 1
        assert failure.transaction_id == "tx-invalid"
        assert "NOT_A_CLASSIFICATION" in failure.reason

    def test_parse_loop_reports_malformed_row_without_dropping_later_rows(self) -> None:
        from ..application.ledger._actions_classification import _parse_bulk_classify_rows

        parsed_rows, failures = _parse_bulk_classify_rows(
            "\n".join(
                (
                    "transaction_id,classification",
                    "tx-extra,BUSINESS,unexpected-cell",
                    "tx-valid,PERSONAL",
                ),
            ),
        )

        assert [row.transaction_id for _idx, row, _provided_columns in parsed_rows] == ["tx-valid"]
        (failure,) = failures
        assert failure.row_index == 0
        assert failure.transaction_id == "tx-extra"
        assert failure.reason == "bulk classify CSV row has more cells than header columns"
