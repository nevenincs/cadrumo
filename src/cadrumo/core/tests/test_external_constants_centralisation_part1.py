"""Centralisation contract tests for shared external constants.

This first constants sweep pins MIME payload types, the default currency,
manual-classification sentinels, and statutory threshold amounts to
``core.external_constants``. Identity checks prove known consumers import the
shared objects, while AST scans catch bare MIME strings and Decimal threshold
literals reintroduced outside the canonical registry.

See Also:
    :mod:`~core.external_constants`
        Canonical registry that owns the shared MIME, currency, sentinel, and
        threshold constants under test.
    :mod:`~tests._inventory`
        AST inventory helpers used to scan production consumers for local
        literal shadow definitions.
    :class:`~core.config.Settings`
        Configuration surface that must inherit default currency from the core
        constant rather than a second local literal.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from ...tests import ast_for_path, package_ast_items, repo_path, repo_relative
from ..config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DECIMAL_CONSTANT_CASES = (
    ("M347_THRESHOLD_EUR", "3005.06"),
    ("ART_7P_EXEMPTION_CAP_EUR", "60100"),
    ("MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR", "1500"),
    ("WORK_INCOME_GENERAL_DECLARATION_LIMIT_EUR", "22000"),
)
_DECIMAL_CONSTANT_IDS = tuple(name.lower() for name, _ in _DECIMAL_CONSTANT_CASES)

_STRING_CONSTANT_CASES = (
    ("BINARY_MIME_TYPE", "application/octet-stream"),
    ("DEFAULT_CURRENCY", "EUR"),
    ("CLASSIFIED_BY_MANUAL", "manual"),
    ("JSON_MIME_TYPE", "application/json"),
    ("CSV_MIME_TYPE", "text/csv"),
    ("JSONL_MIME_TYPE", "application/x-ndjson"),
    ("XLSX_MIME_TYPE", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
)
_STRING_CONSTANT_IDS = tuple(name.lower() for name, _ in _STRING_CONSTANT_CASES)

_M347_PUBLIC_FACADE_CONSUMERS = (
    ("src/cadrumo/application/aggregation/_counterpart.py", 3),
    ("src/cadrumo/application/modelo/calculate_input.py", 3),
    ("src/cadrumo/domain/modelos/row_models.py", 3),
    # The two binding families used to read the constant directly and compare it
    # themselves, byte-identically. 5c6873b64c collapsed that onto the leaf
    # _m347_threshold module, so the constant now has ONE registry consumer and
    # naming the old two here would demand the duplication back.
    ("src/cadrumo/domain/calculations/registry/_m347_threshold.py", 4),
)


def _assert_module_constant_identity(
    *,
    module_name: str,
    attr_name: str,
    expected: object,
    import_message: str,
) -> None:
    mod = importlib.import_module(module_name)

    assert hasattr(mod, attr_name), import_message
    assert getattr(mod, attr_name) is expected, module_name


def _read_ast(path: Path, source_tree_ast: Mapping[Path, ast.AST]) -> ast.AST:
    tree = ast_for_path(path, source_tree_ast)
    if tree is None:
        raise AssertionError(f"unable to parse {repo_relative(path)}")
    return tree


def _decimal_call_literal_offenders(
    path: Path,
    *,
    literal: str,
    replacement: str,
    source_tree_ast: Mapping[Path, ast.AST],
) -> list[str]:
    offenders: list[str] = []
    for node in ast.walk(_read_ast(path, source_tree_ast)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == literal:
            offenders.append(f"{path.name}:{node.lineno}: bare Decimal('{literal}'); use {replacement}")
    return offenders


def _string_literal_offenders(
    path: Path,
    *,
    literal: str,
    replacement: str,
    source_tree_ast: Mapping[Path, ast.AST],
) -> list[str]:
    offenders: list[str] = []
    for node in ast.walk(_read_ast(path, source_tree_ast)):
        if not isinstance(node, ast.Constant) or node.value != literal:
            continue
        offenders.append(f"{path.name}:{node.lineno}: bare {literal!r} literal; use {replacement}")
    return offenders


def test_string_external_constant_values() -> None:
    """String external constants carry their authoritative literal values."""

    from .. import external_constants

    for case_id, (constant_name, expected) in zip(_STRING_CONSTANT_IDS, _STRING_CONSTANT_CASES, strict=True):
        value = getattr(external_constants, constant_name)
        assert value == expected, case_id
        if constant_name != "BINARY_MIME_TYPE":
            assert isinstance(value, str), case_id


def test_decimal_external_constant_values_and_types() -> None:
    """Decimal external constants carry their legal scalar values as ``Decimal`` instances."""

    from .. import external_constants

    for case_id, (constant_name, expected) in zip(_DECIMAL_CONSTANT_IDS, _DECIMAL_CONSTANT_CASES, strict=True):
        value = getattr(external_constants, constant_name)
        assert Decimal(expected) == value, case_id
        assert isinstance(value, Decimal), case_id


# ---------------------------------------------------------------------------
# contract — BINARY_MIME_TYPE centralisation tests
# ---------------------------------------------------------------------------


def test_binary_mime_consumers_alias_core_constant() -> None:
    """Binary MIME consumers import ``BINARY_MIME_TYPE`` from core."""

    import inspect

    from ...adapters.persistence.storage.blob_store.blob_store import EncryptedBlobStore
    from ..external_constants import BINARY_MIME_TYPE

    _assert_module_constant_identity(
        module_name="cadrumo.adapters.outbound.storage._google_drive",
        attr_name="_BINARY_MIME_TYPE",
        expected=BINARY_MIME_TYPE,
        import_message="_google_drive must import BINARY_MIME_TYPE from cadrumo.core.external_constants",
    )
    # The sede consumer is the artefact FETCH path, which stamps the content
    # type on a downloaded declaration. It was split out of _declarations in
    # 0c21a98804; the constant travelled with the code that uses it, so this
    # names the module that reads it today rather than the one it left.
    _assert_module_constant_identity(
        module_name="cadrumo.adapters.outbound.aeat.sede._declarations_fetch",
        attr_name="_BINARY_MIME_TYPE",
        expected=BINARY_MIME_TYPE,
        import_message="_declarations_fetch must import BINARY_MIME_TYPE under the alias _BINARY_MIME_TYPE",
    )

    sig = inspect.signature(EncryptedBlobStore.put)
    assert sig.parameters["content_type"].default == BINARY_MIME_TYPE
    declarations_fetch = importlib.import_module("cadrumo.adapters.outbound.aeat.sede._declarations_fetch")
    assert declarations_fetch._BINARY_MIME_TYPE == "application/octet-stream"


# ---------------------------------------------------------------------------
# contract / contract — DEFAULT_CURRENCY centralisation tests
# ---------------------------------------------------------------------------


def test_default_currency_consumers_alias_core_constant() -> None:
    """Default-currency consumers import ``DEFAULT_CURRENCY`` from core."""

    from ...application.ledger.models import ManualLedgerTransactionCommand
    from ..external_constants import DEFAULT_CURRENCY

    for module_name, attr_name, message in (
        (
            "cadrumo.application.ledger.models",
            "DEFAULT_CURRENCY",
            "_models module must import DEFAULT_CURRENCY from external_constants",
        ),
        (
            "cadrumo.domain.currency.service",
            "DEFAULT_CURRENCY",
            "_service module must import DEFAULT_CURRENCY from external_constants",
        ),
        (
            "cadrumo.application.aggregation._currency_predicates",
            "DEFAULT_CURRENCY",
            "_currency_predicates must import DEFAULT_CURRENCY from external_constants",
        ),
    ):
        _assert_module_constant_identity(
            module_name=module_name,
            attr_name=attr_name,
            expected=DEFAULT_CURRENCY,
            import_message=message,
        )

    schema = ManualLedgerTransactionCommand.model_json_schema()
    props = schema.get("properties", {})
    currency_prop = props.get("currency", {})
    assert currency_prop.get("default") == DEFAULT_CURRENCY
    assert Settings().financial_base_currency == DEFAULT_CURRENCY


# ---------------------------------------------------------------------------
# contract / contract / contract — CLASSIFIED_BY_MANUAL single-source-of-truth tests
# ---------------------------------------------------------------------------


def test_classified_by_manual_consumers_alias_core_constant() -> None:
    """Application/domain consumers bind ``CLASSIFIED_BY_MANUAL`` from core.

    The application layer must not define a local copy; every consuming module
    must import the canonical constant from ``cadrumo.core.external_constants``
    so the identity check below cannot pass against a shadow.

    The owning package ``__init__`` is deliberately NOT asserted: package
    namespaces are inert and may not re-export project symbols, so a namespace
    assertion here would demand exactly what the import-centralization boundary
    forbids. Consumers are enrolled by their defining module instead.
    """

    from ..external_constants import CLASSIFIED_BY_MANUAL

    for module_name, message in (
        ("cadrumo.application.ledger.models", "_models must import CLASSIFIED_BY_MANUAL from core"),
        (
            "cadrumo.domain.transactions.service",
            "_service must import CLASSIFIED_BY_MANUAL from cadrumo.core.external_constants",
        ),
    ):
        _assert_module_constant_identity(
            module_name=module_name,
            attr_name="CLASSIFIED_BY_MANUAL",
            expected=CLASSIFIED_BY_MANUAL,
            import_message=message,
        )


def test_no_local_classified_by_manual_shadow_in_application_or_domain(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No production file in application/ or domain/ may define a local ``classified_by``
    sentinel by assigning the bare string ``"manual"`` to a module-level variable whose
    name contains ``classified_by`` or ``manual_classified``.

    This is the regression guard against the pattern removed in contract/contract:
    ``_MANUAL_CLASSIFIED_BY = "manual"`` or ``CLASSIFIED_BY_MANUAL = "manual"`` defined
    locally instead of imported from ``cadrumo.core.external_constants``.
    """

    # Names that signal a classified_by sentinel re-definition.
    _SENTINEL_NAME_FRAGMENTS = ("classified_by", "manual_classified")

    offenders: list[str] = []
    for py_file, tree in package_ast_items(source_tree_ast):
        relative_path = repo_relative(py_file)
        if not relative_path.startswith(("src/cadrumo/application/", "src/cadrumo/domain/")):
            continue
        for node in ast.walk(tree):
            # Look for module-level or function-level simple assignments:
            # TARGET = "manual"
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            if not isinstance(value, ast.Constant) or value.value != "manual":
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                name_lower = target.id.lower()
                if any(frag in name_lower for frag in _SENTINEL_NAME_FRAGMENTS):
                    offenders.append(
                        f"{relative_path}:{node.lineno}: "
                        f"local classified_by sentinel '{target.id} = \"manual\"'; "
                        f"import CLASSIFIED_BY_MANUAL from cadrumo.core.external_constants",
                    )

    assert offenders == [], (
        "Local classified_by manual sentinels found; "
        "import CLASSIFIED_BY_MANUAL from cadrumo.core.external_constants instead:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# contract / contract / contract — JSON_MIME_TYPE and CSV_MIME_TYPE centralisation tests
# ---------------------------------------------------------------------------


def test_export_mime_consumers_alias_core_constants() -> None:
    """Declaration and tabular exporters import MIME constants from core."""

    from .. import external_constants

    for module_name, attr_name, constant_name, message in (
        (
            "cadrumo.adapters.outbound.aeat.sede.declarations",
            "_JSON_MIME_TYPE",
            "JSON_MIME_TYPE",
            "_declarations must import JSON_MIME_TYPE under the alias _JSON_MIME_TYPE",
        ),
        (
            "cadrumo.application.export.tabular",
            "_CSV_MIME_TYPE",
            "CSV_MIME_TYPE",
            "tabular must import CSV_MIME_TYPE under the alias _CSV_MIME_TYPE",
        ),
        (
            "cadrumo.application.export.tabular",
            "_JSONL_MIME_TYPE",
            "JSONL_MIME_TYPE",
            "tabular must import JSONL_MIME_TYPE under the alias _JSONL_MIME_TYPE",
        ),
        (
            "cadrumo.application.export.tabular",
            "_XLSX_MIME_TYPE",
            "XLSX_MIME_TYPE",
            "tabular must import XLSX_MIME_TYPE under the alias _XLSX_MIME_TYPE",
        ),
    ):
        _assert_module_constant_identity(
            module_name=module_name,
            attr_name=attr_name,
            expected=getattr(external_constants, constant_name),
            import_message=message,
        )

    declarations = importlib.import_module("cadrumo.adapters.outbound.aeat.sede.declarations")
    tabular = importlib.import_module("cadrumo.application.export.tabular")
    assert declarations._JSON_MIME_TYPE == "application/json"
    assert tabular._CSV_MIME_TYPE == "text/csv"


def test_no_bare_json_or_csv_mime_literals_in_exporters(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No bare JSON/CSV MIME literals remain in exporter argument positions.

    Anti-tautology: parses the real AST so any future re-introduction of
    either literal triggers immediate failure.
    """

    offenders: list[str] = []
    for relative_path, literal, replacement in (
        ("src/cadrumo/adapters/outbound/aeat/sede/declarations.py", "application/json", "_JSON_MIME_TYPE"),
        ("src/cadrumo/application/export/tabular.py", "text/csv", "_CSV_MIME_TYPE"),
    ):
        offenders.extend(
            _string_literal_offenders(
                repo_path(relative_path),
                literal=literal,
                replacement=replacement,
                source_tree_ast=source_tree_ast,
            )
        )

    assert offenders == [], "Bare JSON/CSV MIME literals found; import the core MIME constants instead:\n" + "\n".join(
        offenders
    )


# ---------------------------------------------------------------------------
# contract — M347_THRESHOLD_EUR centralisation tests
# ---------------------------------------------------------------------------


def test_threshold_consumers_alias_core_constants() -> None:
    """Threshold consumers import or re-export the core Decimal constants."""

    from .. import external_constants
    from ..external_constants import M347_THRESHOLD_EUR

    assert M347_THRESHOLD_EUR is external_constants.M347_THRESHOLD_EUR

    for module_name, attr_name, constant_name, message in (
        (
            "cadrumo.application.aggregation._counterpart",
            "M347_THRESHOLD_EUR",
            "M347_THRESHOLD_EUR",
            "_counterpart must import M347_THRESHOLD_EUR from cadrumo.core",
        ),
        (
            "cadrumo.application.modelo.calculate_input",
            "M347_THRESHOLD_EUR",
            "M347_THRESHOLD_EUR",
            "_calculate_input must import M347_THRESHOLD_EUR from cadrumo.core",
        ),
        (
            "cadrumo.domain.modelos.row_models",
            "M347_THRESHOLD_EUR",
            "M347_THRESHOLD_EUR",
            "_row_models must import M347_THRESHOLD_EUR from cadrumo.core",
        ),
        (
            "cadrumo.domain.calculations.registry._m347_threshold",
            "M347_THRESHOLD_EUR",
            "M347_THRESHOLD_EUR",
            "_m347_threshold must import M347_THRESHOLD_EUR from cadrumo.core",
        ),
        (
            "cadrumo.domain.renta.maritime_exemption",
            "ART_7P_EXEMPTION_CAP_EUR",
            "ART_7P_EXEMPTION_CAP_EUR",
            "_maritime_exemption must import ART_7P_EXEMPTION_CAP_EUR from cadrumo.core.external_constants",
        ),
        (
            # Named the domain.renta namespace, which re-exported this. That
            # namespace is inert, so the claim moves to the module that
            # actually imports and uses the constant.
            "cadrumo.domain.renta.maritime_exemption",
            "ART_7P_EXEMPTION_CAP_EUR",
            "ART_7P_EXEMPTION_CAP_EUR",
            "maritime_exemption must alias ART_7P_EXEMPTION_CAP_EUR from core.external_constants",
        ),
        (
            "cadrumo.domain.deadlines.models",
            "MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR",
            "MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR",
            "_models must import MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR from cadrumo.core.external_constants",
        ),
    ):
        _assert_module_constant_identity(
            module_name=module_name,
            attr_name=attr_name,
            expected=M347_THRESHOLD_EUR
            if constant_name == "M347_THRESHOLD_EUR"
            else getattr(external_constants, constant_name),
            import_message=message,
        )


def test_m347_consumers_use_public_core_facade_in_source(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    for relative_path, expected_level in _M347_PUBLIC_FACADE_CONSUMERS:
        tree = _read_ast(repo_path(relative_path), source_tree_ast)
        facade_imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.level == expected_level
            and node.module == "core"
            and any(alias.name == "M347_THRESHOLD_EUR" for alias in node.names)
        ]
        private_leaf_imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "core.external_constants"
            and any(alias.name == "M347_THRESHOLD_EUR" for alias in node.names)
        ]

        # The polarity here is now inverted, deliberately. This required the
        # constant to come from the `core` FACADE and forbade the module that
        # defines it, calling that module a "private leaf" -- but
        # `core/external_constants.py` is public, and the facade is inert. So
        # the defining module is the required source and the facade is the one
        # that must not be used.
        assert facade_imports == [], relative_path
        assert len(private_leaf_imports) == 1, relative_path

    row_models_tree = _read_ast(repo_path("src/cadrumo/domain/modelos/row_models.py"), source_tree_ast)
    assert isinstance(row_models_tree, ast.Module)
    export_assignments = [
        node
        for node in row_models_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
    ]
    assert len(export_assignments) == 1
    export_value = export_assignments[0].value
    assert isinstance(export_value, (ast.List, ast.Tuple))
    exported_names = {
        element.value
        for element in export_value.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    }
    assert "M347_THRESHOLD_EUR" not in exported_names


def test_no_bare_threshold_decimal_literals_in_consumers(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No local ``Decimal(...)`` threshold literals remain in threshold consumers."""

    offenders: list[str] = []
    for relative_path, literal, replacement in (
        ("src/cadrumo/application/aggregation/_counterpart.py", "3005.06", "M347_THRESHOLD_EUR"),
        ("src/cadrumo/domain/renta/maritime_exemption.py", "60100", "ART_7P_EXEMPTION_CAP_EUR"),
        (
            "src/cadrumo/domain/deadlines/models.py",
            "1500",
            "MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR",
        ),
    ):
        offenders.extend(
            _decimal_call_literal_offenders(
                repo_path(relative_path),
                literal=literal,
                replacement=replacement,
                source_tree_ast=source_tree_ast,
            ),
        )

    assert offenders == [], (
        "Local threshold literals found; import the core threshold constants instead:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# contract — Art. 96.2.a)/96.3 LIRPF work-income filing-exemption limits
# ---------------------------------------------------------------------------


def test_multiple_pagadores_reduced_limit_per_year_values() -> None:
    """Reduced limit schedule matches the dated statutory amounts (Art. 96.3 LIRPF).

    14.000 EUR base (post-Ley 26/2014), 15.000 EUR for 2023 (Ley 31/2022,
    BOE-A-2022-22128), 15.876 EUR for 2024 onward (RD-Ley 4/2024,
    BOE-A-2024-13066; confirmed by the bundled consolidated LIRPF art-96 corpus).
    """

    from ..external_constants import WORK_INCOME_MULTIPLE_PAGADORES_REDUCED_LIMIT_EUR_BY_YEAR

    table = WORK_INCOME_MULTIPLE_PAGADORES_REDUCED_LIMIT_EUR_BY_YEAR
    assert table[2022] == Decimal("14000")
    assert table[2023] == Decimal("15000")
    assert table[2024] == Decimal("15876")
    assert table[2025] == Decimal("15876")
    assert all(isinstance(v, Decimal) for v in table.values())


def test_multiple_pagadores_reduced_limit_table_is_immutable() -> None:
    """The per-year schedule is a read-only mapping; it cannot be mutated in place."""

    from ..external_constants import WORK_INCOME_MULTIPLE_PAGADORES_REDUCED_LIMIT_EUR_BY_YEAR

    table = WORK_INCOME_MULTIPLE_PAGADORES_REDUCED_LIMIT_EUR_BY_YEAR
    # Immutability is the absence of a mutation method, not a raised exception
    # from one: the real backing mappingproxy exposes no `__setitem__` at all,
    # so item assignment has no dispatch target to reach.
    assert not hasattr(table, "__setitem__")
