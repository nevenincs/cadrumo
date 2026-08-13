"""No migrated filing refusal authors its own sentence; every one renders as its key.

Two independent proofs, because either alone is escapable.

The AST proof walks the filing modules whose operator-facing continuation
refusals are migrated and refuses any raise of a filing-owned registered error
that supplies message text at all -- positionally or through ``message=``. That
shape is the specific defect this guard exists for: an authored sentence passed
*alongside* a registered ``translated_message`` key hides from every
key-and-context assertion, because
:class:`~cadrumo.core.errors.CadrumoError` resolves ``message or
translated_message`` and so prefers the key for locale resolution, while
``str(exc)`` prefers the positional argument and carries the English into
tracebacks, structured logs and every direct rendering, in every locale. A
key-and-context assertion therefore cannot detect it; only an absence check can.

The runtime proof drives each migrated refusal through real behaviour -- real
values, real registry-free helpers, no mock, stub, patch or skip -- and asserts
the *absence* directly: ``str(exc)`` equals the locale key exactly.

Scope is declared rather than inferred. Three modules are deliberately NOT in
the swept set, because their producers are registry-layout and renderer
structural invariants addressed to whoever authored the export layout rather
than continuation refusals addressed to the operator, and they are not migrated:
``_export.py`` field and digest declarations, ``_projection.py``, and
``_export_xml_dictionary.py``. Naming them here keeps the exclusion visible
instead of hiding it behind a matcher that would silently pass.

See Also:
    :class:`~cadrumo.application.filing.errors.ModeloCalculateError`
        Application-layer calculation refusal proven here to render as its key.
"""

from __future__ import annotations

import ast
import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core import Period
from ....domain.filing import ModeloBuilderError, ModeloImportError
from ....domain.submission import ModeloDraftStatus
from .._calculate import DeclaracionCalculateNextAction, DeclaracionCalculateSummary
from ..errors import ModeloCalculateError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILING_PACKAGE = Path(__file__).resolve().parent.parent

#: Registered filing error families this package raises. Bare ``ValueError``
#: carriers (the producer-snapshot and history-model invariants) are excluded
#: deliberately: they are internal validation carriers that cannot enter a
#: ``CadrumoError`` envelope, and policing them here would contradict their
#: standing classification.
_FILING_OWNED_ERRORS: frozenset[str] = frozenset(
    {
        "FilingExportError",
        "FilingExportValidationError",
        "ModeloApplicationError",
        "ModeloBuilderError",
        "ModeloCalculateError",
        "ModeloDraftError",
        "ModeloImportError",
        "_ModeloBuilderError",
    }
)

#: Modules whose operator-facing continuation refusals are migrated and which
#: must therefore never author message text.
_SWEPT_MODULES: tuple[str, ...] = (
    "__init__.py",
    "_calculate.py",
    "_complementaria.py",
    "_export_parity.py",
    "_import.py",
    "_m303_exonerado_390.py",
    "_m303_export_applicability.py",
    "_m303_prorrata_activity_rows.py",
    "_review.py",
    "runtime.py",
)

#: Modules carrying registry-layout and renderer structural invariants that are
#: NOT migrated. Listed so the exclusion is auditable rather than implicit.
_UNSWEPT_MODULES: tuple[str, ...] = (
    "_export.py",
    "_export_xml_dictionary.py",
    "_projection.py",
)


def _authored_message_sites(path: Path) -> list[tuple[str, int]]:
    """Return every filing-owned raise site in ``path`` that supplies message text."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if name not in _FILING_OWNED_ERRORS:
            continue
        authors = bool(node.args) or any(keyword.arg == "message" for keyword in node.keywords)
        if authors:
            offenders.append((name, node.lineno))
    return offenders


def test_the_declared_module_rosters_still_name_real_modules() -> None:
    """Keep both rosters honest against a rename, deletion or split.

    Without this anchor a renamed module would drop out of the swept set and the
    sweep would pass vacuously on the producers it stopped seeing.
    """
    present = {path.name for path in _FILING_PACKAGE.glob("*.py")}
    missing_swept = sorted(name for name in _SWEPT_MODULES if name not in present)
    missing_unswept = sorted(name for name in _UNSWEPT_MODULES if name not in present)

    assert missing_swept == [], f"the swept roster names modules that no longer exist: {missing_swept}"
    assert missing_unswept == [], f"the unswept roster names modules that no longer exist: {missing_unswept}"


def test_the_filing_owned_error_roster_still_names_reachable_errors() -> None:
    """Every rostered class must still be referenced somewhere in the package.

    A rename that left the roster untouched would shrink the sweep's reach while
    keeping every assertion green.
    """
    referenced: set[str] = set()
    for path in _FILING_PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            elif isinstance(node, ast.alias):
                referenced.add(node.asname or node.name)

    missing = sorted(_FILING_OWNED_ERRORS - referenced)
    assert missing == [], f"the roster names error families this package no longer references: {missing}"


def test_no_swept_filing_module_authors_its_own_refusal_message() -> None:
    offenders = {name: sites for name in _SWEPT_MODULES if (sites := _authored_message_sites(_FILING_PACKAGE / name))}
    assert offenders == {}, f"migrated filing refusals must carry a locale key, never authored text: {offenders}"


def test_the_authored_message_scan_detects_both_shapes_of_the_defect(tmp_path: Path) -> None:
    """Prove the AST sweep bites on the positional and the keyword shape alike."""
    positional = tmp_path / "positional.py"
    positional.write_text(
        "raise ModeloBuilderError(\n"
        '    "complementaria requires at least one changed casilla",\n'
        '    translated_message="application.filing.complementaria.errors.no_changed_casilla",\n'
        ")\n",
        encoding="utf-8",
    )
    keyword = tmp_path / "keyword.py"
    keyword.write_text(
        "raise ModeloBuilderError(\n"
        '    message="complementaria requires at least one changed casilla",\n'
        '    translated_message="application.filing.complementaria.errors.no_changed_casilla",\n'
        ")\n",
        encoding="utf-8",
    )
    clean = tmp_path / "clean.py"
    clean.write_text(
        "raise ModeloBuilderError(\n"
        '    translated_message="application.filing.complementaria.errors.no_changed_casilla",\n'
        '    context={"changed_casilla_count": 0},\n'
        ")\n",
        encoding="utf-8",
    )

    assert _authored_message_sites(positional) == [("ModeloBuilderError", 1)]
    assert _authored_message_sites(keyword) == [("ModeloBuilderError", 1)]
    assert _authored_message_sites(clean) == []


def _nested_calculate_error(excinfo: pytest.ExceptionInfo[ValidationError]) -> ModeloCalculateError:
    """Return the model-validator refusal pydantic retained inside the wrapper."""
    for detail in excinfo.value.errors(include_url=False):
        context = detail.get("ctx")
        nested = context.get("error") if isinstance(context, dict) else None
        if isinstance(nested, ModeloCalculateError):
            return nested
    pytest.fail("the calculate summary refusal did not surface a ModeloCalculateError")


def _summary(
    *,
    next_action: DeclaracionCalculateNextAction,
    repair_hints: tuple[str, ...],
    blocker_count: int,
) -> DeclaracionCalculateSummary:
    return DeclaracionCalculateSummary(
        draft_id="draft-key-absence",
        modelo="303",
        period=Period.from_year_and_code(2024, "1T"),
        status=ModeloDraftStatus.BORRADOR,
        blocker_count=blocker_count,
        warning_count=0,
        info_count=0,
        next_action=next_action,
        repair_hints=repair_hints,
        narrative="filing.calculate.default_narrative",
        calculated_at=datetime.datetime.now(datetime.UTC),
    )


def test_missing_repair_hints_refusal_renders_as_its_key() -> None:
    with pytest.raises(ValidationError) as excinfo:
        _summary(
            next_action=DeclaracionCalculateNextAction.RESOLVE_BLOCKERS,
            repair_hints=(),
            blocker_count=1,
        )

    error = _nested_calculate_error(excinfo)
    assert str(error) == "application.filing.calculate.errors.repair_hints_required"
    assert error.context == {
        "next_action": "resolve-blockers",
        "repair_hint_count": 0,
        "blocker_count": 1,
    }


def test_unexpected_repair_hints_refusal_renders_as_its_key() -> None:
    with pytest.raises(ValidationError) as excinfo:
        _summary(
            next_action=DeclaracionCalculateNextAction.REVIEW,
            repair_hints=("filing.repair.some_hint",),
            blocker_count=0,
        )

    error = _nested_calculate_error(excinfo)
    assert str(error) == "application.filing.calculate.errors.repair_hints_forbidden"


def test_decimal_input_refusal_renders_as_its_key() -> None:
    from .. import _decimal_input

    with pytest.raises(ModeloBuilderError) as excinfo:
        _decimal_input("iva.base", object())

    assert str(excinfo.value) == "application.filing.build_draft.errors.input_not_decimal"
    assert excinfo.value.context == {"input_id": "iva.base", "observed_type": "object"}


def test_binding_row_key_refusal_renders_as_its_key() -> None:
    from .. import _binding_row_index

    with pytest.raises(ModeloBuilderError) as excinfo:
        _binding_row_index("iva.rows", 0)

    assert str(excinfo.value) == "application.filing.build_draft.errors.binding_row_key_not_positive_integer"


def test_boolean_input_refusal_renders_as_its_key() -> None:
    from .. import _boolean_input

    with pytest.raises(ModeloBuilderError) as excinfo:
        _boolean_input("iva.flag", Decimal("1"))

    assert str(excinfo.value) == "application.filing.build_draft.errors.binding_value_not_boolean"


def test_import_period_token_refusal_renders_as_its_key() -> None:
    from .._import import _require_supported_period_token

    with pytest.raises(ModeloImportError) as excinfo:
        _require_supported_period_token(
            modelo="303",
            filing_year=2024,
            period_code="ANUAL",
            supported_periods={"1T", "2T", "3T", "4T"},
        )

    assert str(excinfo.value) == "application.filing.import.errors.period_token_undeclared"


def test_export_layout_not_renderable_refusal_renders_as_its_key() -> None:
    from .._export import _export_layout_not_renderable_error

    error = _export_layout_not_renderable_error("303", None)

    assert str(error) == "application.filing.export.errors.layout_not_renderable"
    assert error.context == {"modelo": "303", "reason_code": "no_complete_export_layouts"}
