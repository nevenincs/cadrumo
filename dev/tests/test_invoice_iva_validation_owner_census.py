"""Durable ownership census for invoice and IVA validation refusals."""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT = Path(__file__).resolve().parents[2]
_INVOICE_MODELS = _ROOT / "src/cadrumo/domain/invoices/models.py"
_IVA_CLASSIFICATION = _ROOT / "src/cadrumo/domain/iva/classification.py"
_BULK_IMPORT = _ROOT / "src/cadrumo/application/invoices/bulk_import.py"
_LEDGER_SUPPORT = _ROOT / "src/cadrumo/entrypoints/cli/_ledger_support.py"
_BUSINESS_INVOICES = _ROOT / "src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py"
_LEDGER_EVIDENCE = _ROOT / "src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py"

_LEDGER_TERMINAL = "ledger_terminal"
_BULK_ROW = "bulk_row_structured_result"
_PERSISTENCE = "persistence_integrity"
_ASSEMBLY_GAP = "assembly_gap"
_INTERNAL_UNREACHABLE = "internal_unreachable"
_SWALLOWED_RATE_NOT_FOUND = "swallowed_rate_not_found"


@dataclass(frozen=True)
class _InvoiceFamily:
    """One source-stable invoice error family and every current disposition."""

    owner: str
    expressions: tuple[str, ...]
    dispositions: frozenset[str]


_MODEL_TRANSPORTS = frozenset({_LEDGER_TERMINAL, _BULK_ROW, _PERSISTENCE})
_PERSISTED_CATALOGUE = frozenset({_PERSISTENCE})

# ``_coerce_date`` has three equivalent physical branches and therefore one
# family.  ``_coerce_datetime`` keeps its parsed-value and wrong-type branches
# distinct: only the former can quote a rejected lifecycle stamp.  Every other
# listed entry has one physical raise, making the durable census 34 families /
# 36 physical raises.
_INVOICE_FAMILIES = (
    _InvoiceFamily(
        "_coerce_date",
        ("str(exc)", "'expected a date or ISO-8601 string'", "'expected a date or ISO-8601 string'"),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_coerce_datetime",
        ("f'expected a datetime or ISO-8601 string, got {value!r}'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_coerce_datetime",
        ("'expected a datetime or ISO-8601 string'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily("normalise_invoice_currency", ("str(exc)",), _MODEL_TRANSPORTS),
    _InvoiceFamily("raise_first_invoice_violation", ("message",), _MODEL_TRANSPORTS),
    _InvoiceFamily("require_optional_non_negative", ("message",), _MODEL_TRANSPORTS),
    _InvoiceFamily("require_equal", ("message",), _MODEL_TRANSPORTS),
    _InvoiceFamily(
        "normalise_invoice_monetary_fields",
        (
            "f'{key} could not be parsed as a decimal: {_bounded_rejected_value(raw)}. "
            "Leave it out (or set it to null) to declare it absent; a value that "
            "cannot be read is not the same as no value.'",
        ),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily("_validated_invoice_identity_values", ("message",), _MODEL_TRANSPORTS),
    _InvoiceFamily(
        "_validated_invoice_identity_values",
        ("'counterparty_tax_id must be a string or None'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "derive_invoice_id_when_complete",
        ("'invoice_id must match the stable hash derived from identity fields'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "normalise_invoice_payment_id",
        ("'payment_id must be a 64-character lowercase hex digest'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily("_trim_description", ("'description must not be blank'",), _MODEL_TRANSPORTS),
    _InvoiceFamily(
        "_validate_spending_category_id",
        ("'spending_category_id must not be blank'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily("_require_positive_quantity", ("'quantity must be strictly positive'",), _MODEL_TRANSPORTS),
    _InvoiceFamily("_require_non_negative", ("'monetary value must be non-negative'",), _MODEL_TRANSPORTS),
    _InvoiceFamily(
        "_validate_arithmetic",
        ("'subtotal must equal quantity * unit_price within 1 cent'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_arithmetic",
        ("'iva_amount must be zero for EXEMPT / NOT_SUBJECT lines'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_arithmetic",
        ("'iva_amount must equal subtotal * iva_rate within 1 cent'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_require_non_negative_totals",
        ("'invoice totals must be non-negative'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily("_require_lines", ("'invoice must carry at least one line'",), _MODEL_TRANSPORTS),
    _InvoiceFamily(
        "_validate_line_rates_were_in_force",
        ("f'line rate {line.iva_rate.name} was not in force on {devengo_date.isoformat()}: {exc}'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_retencion_consistency",
        ("'retention_rate must be a fraction between 0 and 1 (0.15 for a 15 % retención), not a percentage'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_retencion_consistency",
        ("'retention_rate requires retention_amount; a rate alone declares no withheld figure'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_retencion_consistency",
        (
            "'retention_amount must not exceed base_total; the retención base is the "
            "base imponible (ingresos íntegros), not the IVA-inclusive total'",
        ),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_retencion_consistency",
        ("'retention_amount must equal base_total * retention_rate within 1 cent'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_recargo_consistency",
        (
            "'recargo_amount must not exceed iva_total; every recargo tier is a smaller "
            "percentage than the IVA rate it accompanies (LIVA art. 161)'",
        ),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_intracommunity_acquirer_identification",
        (
            "'an entrega intracomunitaria exenta cannot name an acquirer purchasing under a "
            "Spanish IVA identification (LIVA art. 25); its country of establishment does "
            "not change that'",
        ),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_operation_date_consistency",
        ("'operation_date and operation_date_role must be set together'",),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_operation_date_consistency",
        (
            "'a pago anticipado devengo does not apply to an entrega intracomunitaria exenta "
            "(LIVA art. 75.Dos, párrafo segundo, excludes art. 25 entregas)'",
        ),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_validate_operation_date_consistency",
        (
            "'operation_date_role ADVANCE_PAYMENT_RECEIVED requires a collected payment_status "
            "(PAID or PARTIALLY_PAID); LIVA art. 75.Dos devengues on actual cobro'",
        ),
        _MODEL_TRANSPORTS,
    ),
    _InvoiceFamily(
        "_coerce_catalogue_input",
        (
            "f\"invoice catalogue payload must carry its entries under the 'invoices' key; "
            'got a bare mapping of {len(payload)} top-level entries"',
        ),
        _PERSISTED_CATALOGUE,
    ),
    _InvoiceFamily(
        "_coerce_catalogue_input",
        ("f'duplicate invoice_id: {invoice.invoice_id}'",),
        _PERSISTED_CATALOGUE,
    ),
    _InvoiceFamily(
        "_validate_mapping_keys",
        ("f'catalogue key {key!r} does not match invoice_id {invoice.invoice_id!r}'",),
        _PERSISTED_CATALOGUE,
    ),
)

_IVA_VALIDATOR_DISPOSITIONS = {
    "_validate_member_state_consistency": _ASSEMBLY_GAP,
    "_exemption_article_consistent_with_category": _INTERNAL_UNREACHABLE,
}


class _RaiseVisitor(ast.NodeVisitor):
    """Collect exact named-error raise expressions under their owning function."""

    def __init__(self, error_name: str) -> None:
        self._error_name = error_name
        self._functions: list[str] = []
        self.occurrences: list[tuple[str, str]] = []

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._functions.append(node.name)
        self.generic_visit(node)
        self._functions.pop()

    @override
    def visit_Raise(self, node: ast.Raise) -> None:
        if (
            isinstance(node.exc, ast.Call)
            and isinstance(node.exc.func, ast.Name)
            and node.exc.func.id == self._error_name
            and node.exc.args
        ):
            assert self._functions, f"{self._error_name} raise has no owning function"
            self.occurrences.append((self._functions[-1], ast.unparse(node.exc.args[0])))
        self.generic_visit(node)


def _raises(path: Path, error_name: str) -> Counter[tuple[str, str]]:
    visitor = _RaiseVisitor(error_name)
    visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    return Counter(visitor.occurrences)


def _calls(tree: ast.AST, name: str) -> Iterable[ast.Call]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name:
            yield node


def test_invoice_validation_family_census_is_exact_and_dispositioned() -> None:
    """All 34 durable invoice families retain a deliberate boundary owner."""
    expected = Counter((family.owner, expression) for family in _INVOICE_FAMILIES for expression in family.expressions)
    assert len(_INVOICE_FAMILIES) == 34
    assert sum(expected.values()) == 36
    assert _raises(_INVOICE_MODELS, "InvoiceValidationError") == expected
    assert {disposition for family in _INVOICE_FAMILIES for disposition in family.dispositions} == {
        _LEDGER_TERMINAL,
        _BULK_ROW,
        _PERSISTENCE,
    }


def test_iva_validator_and_rate_not_found_exclusions_are_exact() -> None:
    """IVA keeps assembly, result-consistency, UNKNOWN and swallowed-rate ownership distinct."""
    expected_raises = Counter(
        {
            (
                "_validate_member_state_consistency",
                "'rate_tier is required for operations taxed at a Spanish rate: ES-to-ES domestic, "
                "and a B2C service outside the Comunidad, which LIVA art. 69.Uno.2.º keeps in "
                "the TAI. Supply GENERAL / REDUCED / SUPER_REDUCED / ZERO / EXEMPT explicitly'",
            ): 1,
            (
                "_exemption_article_consistent_with_category",
                "f'exemption_article {self.exemption_article.value!r} is only valid when "
                "category is DOMESTIC_EXEMPT; got category {self.category.value!r}'",
            ): 1,
        },
    )
    assert _raises(_IVA_CLASSIFICATION, "IvaValidationError") == expected_raises
    assert set(_IVA_VALIDATOR_DISPOSITIONS.values()) == {_ASSEMBLY_GAP, _INTERNAL_UNREACHABLE}

    tree = ast.parse(_IVA_CLASSIFICATION.read_text(encoding="utf-8"), filename=str(_IVA_CLASSIFICATION))
    result_constructors = tuple(_calls(tree, "IvaClassificationResult"))
    assert len(result_constructors) == 2
    assert all(not any(keyword.arg == "exemption_article" for keyword in call.keywords) for call in result_constructors)

    handlers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler)
        and isinstance(node.type, ast.Name)
        and node.type.id == "IvaRateNotFoundError"
    ]
    assert len(handlers) == 1
    (handler,) = handlers
    assert any(
        isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and node.value.value is None
        for node in handler.body
    )
    handler_body = ast.Module(body=handler.body, type_ignores=[])
    assert not any(isinstance(node, ast.Raise) for node in ast.walk(handler_body))
    assert _SWALLOWED_RATE_NOT_FOUND == "swallowed_rate_not_found"


def test_bulk_rows_remain_structured_and_catalogue_loads_remain_outside_ledger_projection() -> None:
    """The two non-terminal invoice paths cannot be flattened into CLI input refusal."""
    bulk_tree = ast.parse(
        _BULK_IMPORT.read_text(encoding="utf-8"),
        filename=str(_BULK_IMPORT),
    )
    row_handlers = [
        node
        for node in ast.walk(bulk_tree)
        if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name) and node.type.id == "_RowParseError"
    ]
    assert len(row_handlers) == 1
    assert any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "BulkInvoiceImportRowFailure"
        for node in ast.walk(row_handlers[0])
    )

    support_tree = ast.parse(
        _LEDGER_SUPPORT.read_text(encoding="utf-8"),
        filename=str(_LEDGER_SUPPORT),
    )
    invoice_projection = next(
        node
        for node in support_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "ledger_invoice_validation_no_recovery"
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_is_pydantic_invoice_validation"
        for node in ast.walk(invoice_projection)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"PreconditionVerdict", "ConditionEvidence"}
        for node in ast.walk(invoice_projection)
    )


def test_exactly_five_ledger_boundaries_delegate_to_one_invoice_projection() -> None:
    """No invoice command may recreate a terminal verdict or flatten it to BadParameter."""
    expected = {
        _BUSINESS_INVOICES: {"invoice_add", "invoice_wizard", "invoice_import", "invoice_update"},
        _LEDGER_EVIDENCE: {"_run_evidence_confirm"},
    }
    observed: dict[Path, set[str]] = {}
    for path, _names in expected.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        owners: list[str] = []
        for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            for handler in (node for node in function.body if isinstance(node, ast.Try) for node in node.handlers):
                caught = handler.type
                if not isinstance(caught, ast.Tuple) or {
                    item.id for item in caught.elts if isinstance(item, ast.Name)
                } != {
                    "InvoiceValidationError",
                    "ValidationError",
                }:
                    continue
                owners.append(function.name)
                rendered = ast.unparse(handler)
                assert "ledger_invoice_validation_no_recovery" in rendered
                assert "ledger_cli_no_recovery" not in rendered
                assert "BadParameter" not in rendered
        observed[path] = set(owners)
    assert observed == expected
