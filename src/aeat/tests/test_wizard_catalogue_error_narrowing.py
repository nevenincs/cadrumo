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

import ast
import decimal
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, override

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

_SRC = Path(__file__).parent.parent


def _except_handler_names(module_relative: str, function_name: str) -> tuple[tuple[str, ...], ...]:
    module_path = _SRC / module_relative
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    function_node = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
        ),
        None,
    )
    assert function_node is not None, f"{module_relative}: missing function {function_name}"

    handlers: list[tuple[str, ...]] = []

    class _HandlerVisitor(ast.NodeVisitor):
        @override
        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            handlers.append(_handler_type_names(node.type))
            self.generic_visit(node)

    _HandlerVisitor().visit(function_node)
    return tuple(handlers)


def _handler_type_names(node: ast.expr | None) -> tuple[str, ...]:
    if node is None:
        return ("<bare>",)
    if isinstance(node, ast.Tuple):
        return tuple(_single_handler_type_name(element) for element in node.elts)
    return (_single_handler_type_name(node),)


def _single_handler_type_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_single_handler_type_name(node.value)}.{node.attr}"
    raise AssertionError(f"unsupported except handler expression: {ast.dump(node)}")


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

    def test_error_classes_are_aeat_errors_with_registered_codes(self) -> None:
        for error_cls, expected_code in self._ERROR_CASES:
            assert issubclass(error_cls, AeatError), error_cls.__name__
            code = get_registered_error_code(error_cls)
            assert code.code == expected_code

    def test_envelope_roundtrip(self) -> None:
        """An instance can be built into an ErrorEnvelope without raising."""
        for error_cls, _expected_code in self._ERROR_CASES:
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

    def test_advisory_ratio_predicate_decimal_threshold_cases(self) -> None:
        from ..application.modelo._verification_actions import _evaluate_advisory_predicate_fires

        cases = (
            (
                self._INVALID_THR_EXPR,
                {"num_id": decimal.Decimal("2"), "den_id": decimal.Decimal("1")},
                False,
            ),
            (
                self._VALID_EXPR,
                {"num_id": decimal.Decimal("2"), "den_id": decimal.Decimal("1")},
                True,
            ),
            (
                self._VALID_EXPR,
                {"num_id": decimal.Decimal("0.1"), "den_id": decimal.Decimal("1")},
                False,
            ),
        )

        for expression, values, expected in cases:
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
    """Bulk classify loops capture typed errors; propagate unexpected ones."""

    def test_parse_loop_catches_only_typed_row_validation_errors(self) -> None:
        assert _except_handler_names(
            "application/ledger/_actions_classification.py",
            "_parse_bulk_classify_rows",
        ) == (("ValidationError", "ValueError", "KeyError"),)

    def test_apply_loop_catches_only_typed_apply_errors(self) -> None:
        assert _except_handler_names(
            "application/ledger/_actions_classification.py",
            "_apply_bulk_classify_rows",
        ) == (("AeatError", "ValidationError", "ValueError"),)


class TestReviewAdapterImportNarrowing:
    """_resolve_active_tax_id splits ImportError from workflow state errors."""

    def test_active_tax_id_resolution_keeps_import_and_workflow_errors_separate(self) -> None:
        assert _except_handler_names(
            "application/review/_adapters.py",
            "_resolve_active_tax_id",
        ) == (("ImportError",), ("AeatError", "AttributeError"))
