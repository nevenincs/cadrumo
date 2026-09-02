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
the *absence* directly: ``str(exc)`` equals the locale key exactly. It also
proves that every operator-reachable family transports an explicit terminal
precondition outcome; layout renderers and invariant-only constructors are
listed as structural exclusions, not silently omitted.

Scope is declared rather than inferred. Six modules are deliberately NOT in
the swept set, because their producers are registry-layout and renderer
structural invariants addressed to whoever authored the export layout rather
than continuation refusals addressed to the operator.  Each exclusion records
the downstream export owner that catches or projects the invariant; naming
them here keeps the exclusion visible instead of hiding it behind a matcher
that would silently pass.

See Also:
    :class:`~cadrumo.application.filing.errors.ModeloCalculateError`
        Application-layer calculation refusal proven here to render as its key.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ....core.errors.hierarchy import TerminalPreconditionErrorMixin
from ....core.operator_action_enums import ActionConditionality, NoRecoveryOutcome
from ....domain.filing.errors import FilingExportError, ModeloBuilderError, ModeloImportError
from ..errors import FilingPreconditionCondition, ModeloApplicationError

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
    "draft_construction.py",
    "_export_parity.py",
    "_import.py",
    "_m303_exonerado_390.py",
    "_m303_export_applicability.py",
    "draft_review.py",
    "runtime.py",
)

#: Modules carrying registry-layout and renderer structural invariants that are
#: NOT migrated.  The value records the downstream export boundary that catches
#: or projects the invariant, keeping every structural exclusion auditable.
_UNSWEPT_MODULE_RATIONALES: dict[str, str] = {
    "export.py": (
        "The public export/verify boundary owns field and digest declaration "
        "failures and projects them at the filed-artifact boundary."
    ),
    "_export_producer.py": (
        "Producer-snapshot completeness is consumed by export.py, whose "
        "public export boundary owns the resulting validation/catch path."
    ),
    "_export_xml_dictionary.py": (
        "XML-dictionary layout invariants are consumed by export.py, whose "
        "export/verification boundary owns their projection."
    ),
    "_projection.py": (
        "Projection-plan and value-address invariants are consumed by export.py's render-request boundary."
    ),
    "_record_field_renderer.py": (
        "Field offset, length, and role invariants are consumed by "
        "_record_renderer.py/export.py at the artifact boundary."
    ),
    "_record_renderer.py": (
        "Record ordering and occurrence invariants are consumed by export.py at the artifact boundary."
    ),
}

_UNSWEPT_MODULES: tuple[str, ...] = tuple(_UNSWEPT_MODULE_RATIONALES)

#: The complete adjudicated population whose key-only failures can reach an
#: operator through a filing application surface.  These aliases deliberately
#: resolve to the one existing registered application terminal carrier; adding
#: an undeclared exception type would bypass the registered error taxonomy.
_OPERATOR_REACHABLE_REFUSAL_ALIASES: dict[str, str] = {
    "draft_construction.py": "_ModeloBuilderError",
    "_complementaria.py": "ModeloBuilderError",
    "_export_parity.py": "FilingExportError",
    "_import.py": "ModeloImportError",
    "_m303_exonerado_390.py": "FilingExportError",
    "_m303_export_applicability.py": "FilingExportError",
    "runtime.py": "ModeloBuilderError",
}


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


def _filing_owned_authored_error_modules(root: Path = _FILING_PACKAGE) -> set[str]:
    """Return every filing module that still authors a registered-error message."""
    return {path.name for path in scan_directory(root, pattern="*.py") if _authored_message_sites(path)}


def _assert_authored_error_module_partition(
    *, root: Path, swept_modules: tuple[str, ...], unswept_modules: tuple[str, ...]
) -> None:
    """Require every authored filing-error module to have one explicit role."""
    overlap = sorted(set(swept_modules) & set(unswept_modules))
    assert overlap == [], f"a module cannot be both swept and structurally excluded: {overlap}"

    authored_modules = _filing_owned_authored_error_modules(root)
    assert authored_modules == set(unswept_modules), (
        "every filing-owned authored-error module must be explicitly unswept "
        f"with a downstream owner/catch rationale: found {sorted(authored_modules)}"
    )


def test_the_declared_module_rosters_still_name_real_modules() -> None:
    """Keep both rosters honest against a rename, deletion or split.

    Without this anchor a renamed module would drop out of the swept set and the
    sweep would pass vacuously on the producers it stopped seeing.
    """
    present = {path.name for path in scan_directory(_FILING_PACKAGE, pattern="*.py")}
    missing_swept = sorted(name for name in _SWEPT_MODULES if name not in present)
    missing_unswept = sorted(name for name in _UNSWEPT_MODULES if name not in present)

    assert missing_swept == [], f"the swept roster names modules that no longer exist: {missing_swept}"
    assert missing_unswept == [], f"the unswept roster names modules that no longer exist: {missing_unswept}"
    assert set(_UNSWEPT_MODULE_RATIONALES) == set(_UNSWEPT_MODULES)
    assert all(_UNSWEPT_MODULE_RATIONALES.values())


def _imported_application_refusal_aliases(path: Path) -> set[str]:
    """Return local names imported from the filing application error owner."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != "errors" or node.level != 1:
            continue
        for imported in node.names:
            if imported.name == "ModeloApplicationError":
                aliases.add(imported.asname or imported.name)
    return aliases


def _assert_operator_reachable_refusal_census(census: dict[str, tuple[Path, str]]) -> None:
    """Reject any reachable family that bypasses the registered terminal carrier."""
    resolved = {
        module: alias in _imported_application_refusal_aliases(path) for module, (path, alias) in census.items()
    }
    assert resolved == {module: True for module in census}


def test_each_operator_reachable_refusal_family_uses_the_registered_terminal_carrier() -> None:
    """Census every reachable family; renderer/invariant modules are excluded above."""
    _assert_operator_reachable_refusal_census(
        {module: (_FILING_PACKAGE / module, alias) for module, alias in _OPERATOR_REACHABLE_REFUSAL_ALIASES.items()}
    )


def test_operator_reachable_refusal_census_rejects_a_missing_terminal_import(tmp_path: Path) -> None:
    """Mutation proof: a legacy domain-only producer cannot slip through the census."""
    legacy = tmp_path / "legacy_refusal.py"
    legacy.write_text(
        "from cadrumo.domain.filing import ModeloBuilderError\n"
        "\n"
        "def refuse():\n"
        "    raise ModeloBuilderError(translated_message='application.filing.test.error')\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError):
        _assert_operator_reachable_refusal_census({"legacy_refusal.py": (legacy, "ModeloBuilderError")})


def test_the_filing_owned_error_roster_still_names_reachable_errors() -> None:
    """Every rostered class must still be referenced somewhere in the package.

    A rename that left the roster untouched would shrink the sweep's reach while
    keeping every assertion green.
    """
    referenced: set[str] = set()
    for path in scan_directory(_FILING_PACKAGE, pattern="*.py"):
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


def test_every_filing_owned_authored_error_module_is_explicitly_unswept() -> None:
    """The complete AST census cannot silently omit a new renderer/error module."""
    _assert_authored_error_module_partition(
        root=_FILING_PACKAGE,
        swept_modules=_SWEPT_MODULES,
        unswept_modules=_UNSWEPT_MODULES,
    )


def test_authored_error_module_partition_rejects_an_unclassified_module(tmp_path: Path) -> None:
    """Mutation proof: a newly authored error module cannot evade the roster."""
    renderer = tmp_path / "new_renderer.py"
    renderer.write_text(
        'raise FilingExportValidationError("layout field offset is invalid")\n',
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="explicitly unswept"):
        _assert_authored_error_module_partition(root=tmp_path, swept_modules=(), unswept_modules=())


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


def _assert_terminal_application_refusal(error: ModeloApplicationError) -> None:
    assert isinstance(error, TerminalPreconditionErrorMixin)
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == FilingPreconditionCondition.OPERATION_ADMISSIBLE.value
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values == {"error_type": "ModeloApplicationError"}


def test_terminal_application_refusal_preserves_the_established_domain_catch_families() -> None:
    """Transport must not make direct filing callers lose their existing catches."""
    error = ModeloApplicationError(translated_message="application.filing.test.errors.refusal")

    assert isinstance(error, ModeloBuilderError)
    assert isinstance(error, ModeloImportError)
    assert isinstance(error, FilingExportError)
    _assert_terminal_application_refusal(error)


def test_decimal_input_refusal_renders_as_its_key_and_terminal_condition() -> None:
    from ..draft_construction import _decimal_input

    with pytest.raises(ModeloApplicationError) as excinfo:
        _decimal_input("iva.base", object())

    assert str(excinfo.value) == "application.filing.build_draft.errors.input_not_decimal"
    assert excinfo.value.context == {"input_id": "iva.base", "observed_type": "object"}
    _assert_terminal_application_refusal(excinfo.value)


def test_binding_row_key_refusal_renders_as_its_key() -> None:
    from ..draft_construction import _binding_row_index

    with pytest.raises(ModeloApplicationError) as excinfo:
        _binding_row_index("iva.rows", 0)

    assert str(excinfo.value) == "application.filing.build_draft.errors.binding_row_key_not_positive_integer"
    _assert_terminal_application_refusal(excinfo.value)


def test_boolean_input_refusal_renders_as_its_key() -> None:
    from ..draft_construction import _boolean_input

    with pytest.raises(ModeloApplicationError) as excinfo:
        _boolean_input("iva.flag", Decimal("1"))

    assert str(excinfo.value) == "application.filing.build_draft.errors.binding_value_not_boolean"
    _assert_terminal_application_refusal(excinfo.value)


def test_import_period_token_refusal_renders_as_its_key() -> None:
    from .._import import _require_supported_period_token

    with pytest.raises(ModeloApplicationError) as excinfo:
        _require_supported_period_token(
            modelo="303",
            filing_year=2024,
            period_code="ANUAL",
            supported_periods={"1T", "2T", "3T", "4T"},
        )

    assert str(excinfo.value) == "application.filing.import.errors.period_token_undeclared"
    _assert_terminal_application_refusal(excinfo.value)


def test_export_layout_not_renderable_refusal_renders_as_its_key() -> None:
    from ..export import _export_layout_not_renderable_error

    error = _export_layout_not_renderable_error("303", None)

    assert str(error) == "application.filing.export.errors.layout_not_renderable"
    assert error.context == {"modelo": "303", "reason_code": "no_complete_export_layouts"}
