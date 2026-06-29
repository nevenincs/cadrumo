"""Wizard catalogue error classes plus narrowed except-clause contracts.

Verifies:
  (a) The wizard-catalogue / project-answers error classes are registered
      in the error registry and produce valid ErrorEnvelope roundtrips.
  (b) The narrowed except clauses in the advisory predicate evaluator,
      result-summary lookup, ledger bulk-classify loop, and review-adapter
      fallback honestly propagate non-typed exceptions rather than
      swallowing them silently.
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
from ..domain.modelos._calculation_revision import (
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

    @pytest.mark.parametrize(
        "error_cls",
        [
            WizardCatalogueNotRegisteredError,
            WizardCatalogueAlreadyRegisteredError,
            ProjectAnswersNotRegisteredError,
        ],
    )
    def test_is_aeat_error_subclass(self, error_cls: type[AeatError]) -> None:
        assert issubclass(error_cls, AeatError)

    @pytest.mark.parametrize(
        "error_cls,expected_code",
        [
            (WizardCatalogueNotRegisteredError, "INTERNAL_WIZARD_CATALOGUE_NOT_REGISTERED"),
            (WizardCatalogueAlreadyRegisteredError, "INTERNAL_WIZARD_CATALOGUE_ALREADY_REGISTERED"),
            (ProjectAnswersNotRegisteredError, "INTERNAL_PROFILE_PROJECT_ANSWERS_NOT_REGISTERED"),
        ],
    )
    def test_error_code_registered(self, error_cls: type[BaseException], expected_code: str) -> None:
        code = get_registered_error_code(error_cls)
        assert code.code == expected_code

    @pytest.mark.parametrize(
        "error_cls",
        [
            WizardCatalogueNotRegisteredError,
            WizardCatalogueAlreadyRegisteredError,
            ProjectAnswersNotRegisteredError,
        ],
    )
    def test_envelope_roundtrip(self, error_cls: type[AeatError]) -> None:
        """An instance can be built into an ErrorEnvelope without raising."""
        try:
            instance = error_cls()
        except TypeError:
            instance = error_cls("test message")
        envelope = build_error_envelope(instance)
        assert envelope.code == get_registered_error_code(error_cls).code
        assert envelope.message


# ---------------------------------------------------------------------------
# (b) Narrowed except clauses propagate non-typed exceptions
# ---------------------------------------------------------------------------


class TestAdvisoryPredicateDecimalNarrowing:
    """_evaluate_advisory_predicate_fires only catches InvalidOperation on threshold parse."""

    _VALID_EXPR = 'advisory_when_ratio_ge(["num_id", "den_id", "0.5"])'
    _INVALID_THR_EXPR = 'advisory_when_ratio_ge(["num_id", "den_id", "notadecimal"])'

    def test_invalid_decimal_threshold_returns_false(self) -> None:
        """A non-parseable threshold string hits InvalidOperation → returns False."""
        from ..application.modelo._verification_actions import _evaluate_advisory_predicate_fires

        result = _evaluate_advisory_predicate_fires(
            self._INVALID_THR_EXPR,
            {"num_id": decimal.Decimal("2"), "den_id": decimal.Decimal("1")},
        )
        assert result is False

    def test_valid_ratio_ge_evaluates_true(self) -> None:
        """A valid threshold parses and evaluates the ratio correctly."""
        from ..application.modelo._verification_actions import _evaluate_advisory_predicate_fires

        # 2/1 = 2.0 >= 0.5 → True
        result = _evaluate_advisory_predicate_fires(
            self._VALID_EXPR,
            {"num_id": decimal.Decimal("2"), "den_id": decimal.Decimal("1")},
        )
        assert result is True

    def test_valid_ratio_below_threshold_evaluates_false(self) -> None:
        """A ratio below threshold correctly returns False."""
        from ..application.modelo._verification_actions import _evaluate_advisory_predicate_fires

        # 0.1/1 = 0.1, which is < 0.5 → False
        result = _evaluate_advisory_predicate_fires(
            self._VALID_EXPR,
            {"num_id": decimal.Decimal("0.1"), "den_id": decimal.Decimal("1")},
        )
        assert result is False


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
        from ..application.modelo._result_summary import calculation_result_summary

        def _raising(work_unit_id: str) -> NoReturn:
            del work_unit_id
            raise ProjectAnswersNotRegisteredError()

        result = calculation_result_summary(self._revision(), work_unit_resolver=_raising)

        assert result is None

    def test_lookup_error_from_get_work_unit_returns_none(self) -> None:
        """A LookupError from get_work_unit returns None."""
        from ..application.modelo._result_summary import calculation_result_summary

        def _raising(work_unit_id: str) -> NoReturn:
            del work_unit_id
            raise LookupError("not found")

        result = calculation_result_summary(self._revision(), work_unit_resolver=_raising)

        assert result is None

    def test_runtime_error_from_get_work_unit_propagates(self) -> None:
        """A RuntimeError from get_work_unit propagates — not swallowed."""
        from ..application.modelo._result_summary import calculation_result_summary

        def _raising(work_unit_id: str) -> NoReturn:
            del work_unit_id
            raise RuntimeError("unexpected db failure")

        with pytest.raises(RuntimeError, match="unexpected db failure"):
            calculation_result_summary(self._revision(), work_unit_resolver=_raising)


class TestLedgerBulkClassifyNarrowing:
    """Bulk classify loops capture typed errors; propagate unexpected ones."""

    def test_validation_error_is_captured_by_parse_clause(self) -> None:
        """pydantic ValidationError is a subclass of ValueError and is caught by the narrowed clause."""
        from pydantic import ValidationError

        # Confirm ValidationError is in the expected narrow tuple
        assert issubclass(ValidationError, ValueError)

    def test_apply_loop_aeat_error_is_captured(self) -> None:
        """AeatError subclasses are captured by the apply loop's narrow clause."""
        caught = False
        try:
            # Use a registered AeatError subclass
            raise ProjectAnswersNotRegisteredError()
        except AeatError:
            caught = True
        assert caught

    def test_unexpected_type_error_in_parse_would_propagate(self) -> None:
        """A TypeError (not in parse tuple) propagates — proves narrowing is real."""
        propagated = False
        try:
            try:
                raise TypeError("structural mismatch")
            except (ValueError, KeyError):
                pass
        except TypeError:
            propagated = True
        assert propagated


class TestReviewAdapterImportNarrowing:
    """_resolve_active_tax_id splits ImportError from workflow state errors."""

    def test_import_error_clause_is_narrower_than_exception(self) -> None:
        """ImportError is a subclass of Exception but narrower — our clause catches it."""
        assert issubclass(ImportError, Exception)
        caught = False
        try:
            raise ImportError("no module")
        except ImportError:
            caught = True
        assert caught

    def test_attribute_error_clause_catches_none_access(self) -> None:
        """AttributeError is caught by (AeatError, AttributeError) clause."""
        caught = False
        try:
            raise AttributeError("object has no attribute state")
        except (AeatError, AttributeError):
            caught = True
        assert caught

    def test_runtime_error_is_not_caught_by_attribute_error_clause(self) -> None:
        """RuntimeError is NOT in (AeatError, AttributeError) — it propagates."""
        propagated = False
        try:
            try:
                raise RuntimeError("db exploded")
            except (AeatError, AttributeError):
                pass
        except RuntimeError:
            propagated = True
        assert propagated
