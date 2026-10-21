"""Real-behaviour tests for ApiStubManager scaffold, check, and audit."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from dev._paths import REPO_ROOT
from dev.first_party_source import CLIENT_PACKAGE, FIRST_PARTY_ROOTS

from ..manager import (
    _NON_OWNER_GENERIC_IMPORTS,
    API_SOURCE_PACKAGE,
    API_SOURCE_ROOTS,
    ApiDocsError,
    ApiStubManager,
    DriftResult,
    ScaffoldResult,
    _type_alias_declarations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


#: Floor for the stub population ``scaffold`` derives from the source tree.
#: Live it expects 1822 stubs. Every claim in this module reads a corpus
#: that an empty expected set empties: ``scaffold`` writes each expected
#: stub and then unlinks every ``.rst`` absent from that set, so a
#: discovery that found no module deletes the whole reference while
#: reporting the removal each case here asks for.
_MINIMUM_STUB_POPULATION = 1000


def _module_tree(module_name: str) -> ast.Module:
    """Read a declared documentation target without executing its module body."""
    spec = importlib.util.find_spec(module_name)
    assert spec is not None and spec.origin is not None, f"documentation target module is absent: {module_name}"
    return ast.parse(Path(spec.origin).read_text(encoding="utf-8"))


def _source_path_for_module(module_name: str, is_package: bool) -> Path:
    """Map an admitted dotted module back to its canonical source file."""
    for source_root in API_SOURCE_ROOTS:
        package_name = Path(source_root).name
        if module_name == package_name or module_name.startswith(package_name + "."):
            relative_parts = module_name.split(".")[1:]
            source_path = REPO_ROOT.joinpath(*Path(source_root).parts, *relative_parts)
            return source_path / "__init__.py" if is_package else source_path.with_suffix(".py")
    raise AssertionError(f"discovered API module is outside canonical roots: {module_name}")


def _bound_names(tree: ast.Module) -> set[str]:
    """Return names the target module binds directly in source."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            targets = node.targets
            names.update(target.id for target in targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, ast.TypeAlias):
            names.add(node.name.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name.rsplit(".", 1)[-1] for alias in node.names)
    return names


def _defines_class_or_function(tree: ast.Module, name: str) -> bool:
    """Return whether a module binds *name* to a class or function definition."""
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name
        for node in tree.body
    )


def test_every_generic_exclusion_names_a_symbol_its_module_does_not_own() -> None:
    """Each ``_NON_OWNER_GENERIC_IMPORTS`` entry re-derives its own condition.

    The entry's warrant is that the named generic base is IMPORTED into the
    module, not defined there, so excluding it from that module's stub removes a
    duplicate index rather than real API. Both halves are checked against the
    imported object: the name must resolve at the consumer (else the exclusion
    is dead weight), and its ``__module__`` must be some other module (else the
    consumer OWNS the symbol and ``:exclude-members:`` silently erases a genuine
    public class from the generated reference, with no drift the generator could
    report against its own output).
    """
    assert _NON_OWNER_GENERIC_IMPORTS, "the exclusion table is empty; every claim below is vacuous"
    unresolved: list[str] = []
    owned_here: list[str] = []
    for module_name, excluded in sorted(_NON_OWNER_GENERIC_IMPORTS.items()):
        assert excluded, f"{module_name!r} excludes no member at all"
        tree = _module_tree(module_name)
        for name in excluded:
            if name not in _bound_names(tree):
                unresolved.append(f"{module_name}.{name}")
                continue
            if _defines_class_or_function(tree, name):
                owned_here.append(f"{module_name}.{name}")
    assert unresolved == [], f"generic exclusions name symbols their module does not import; remove them: {unresolved}"
    assert owned_here == [], (
        "generic exclusions name symbols their module DEFINES, so the stub erases real public API "
        f"from the generated reference: {owned_here}"
    )


def test_public_type_aliases_have_one_canonical_module_target(tmp_path: Path) -> None:
    """Every public PEP 695 alias gets a type target at its defining module."""
    manager = ApiStubManager.for_repository(REPO_ROOT, docs_api=tmp_path / "api")

    manager.scaffold()

    targets: list[tuple[str, str]] = []
    modules = manager.discover_modules()
    for module_name, is_package in modules:
        source_path = _source_path_for_module(module_name, is_package)
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        targets.extend(
            (module_name, statement.name.id)
            for statement in tree.body
            if isinstance(statement, ast.TypeAlias) and not statement.name.id.startswith("_")
        )

    for module_name, alias in targets:
        stub = (tmp_path / "api" / f"{module_name}.rst").read_text(encoding="utf-8")
        directive = f".. py:type:: {alias}\n   :module: {module_name}"
        assert stub.count(directive) == 1, f"{module_name}.{alias} must have one owner target"

    for module_name, is_package in modules:
        aliases = _type_alias_declarations(_source_path_for_module(module_name, is_package))
        if not aliases:
            continue
        stub = (tmp_path / "api" / f"{module_name}.rst").read_text(encoding="utf-8")
        alias_names = {name for name, _ in aliases}
        exclusion_line = next(
            (line for line in stub.splitlines() if line.strip().startswith(":exclude-members:")),
            "",
        )
        excluded_names = set(exclusion_line.partition(":")[2].partition(":")[2].strip().split(","))
        assert alias_names <= excluded_names, (
            f"{module_name} must leave generated type-alias targets to their explicit directives: "
            f"{sorted(alias_names - excluded_names)}"
        )
        for alias, _ in aliases:
            directive = f".. py:type:: {alias}\n   :module: {module_name}"
            assert stub.count(directive) == 1, f"{module_name}.{alias} must have one explicit target"

    assert targets, "the canonical source roots contain no public PEP 695 aliases"
    assert ("cadrumo_client.transport.automation_decision", "AutomationDecision") in targets
    deadline_window_projection = (tmp_path / "api" / "cadrumo.domain.deadlines.engine.rst").read_text(encoding="utf-8")
    assert (
        deadline_window_projection.count(
            ".. py:type:: DeadlineWindowProjection\n   :module: cadrumo.domain.deadlines.engine"
        )
        == 1
    )
    cli_program = (tmp_path / "api" / "cadrumo_agent_service.providers.domain.catalog.rst").read_text(encoding="utf-8")
    assert ".. py:type:: CliProgram\n   :module: cadrumo_agent_service.providers.domain.catalog" in cli_program
    assert "CliProgram = Annotated[str, StringConstraints" in cli_program
    binding_selector = (tmp_path / "api" / "cadrumo.domain.calculations.registry.binding_selector_utils.rst").read_text(
        encoding="utf-8"
    )
    calc_sheet_records = (tmp_path / "api" / "cadrumo.application.storage.calc_sheets.records.rst").read_text(
        encoding="utf-8"
    )
    m145_records = (tmp_path / "api" / "cadrumo.application.modelo.m145_communication_records.rst").read_text(
        encoding="utf-8"
    )
    filing_schema = (tmp_path / "api" / "cadrumo.domain.filing.schema.rst").read_text(encoding="utf-8")
    secure_object_records = (
        tmp_path / "api" / "cadrumo.adapters.persistence.storage.sql.secure_object_records.rst"
    ).read_text(encoding="utf-8")
    iva_components = (tmp_path / "api" / "cadrumo.domain.iva.components.rst").read_text(encoding="utf-8")
    binding_alias = (
        ".. py:type:: BindingExportDataType\n   :module: cadrumo.domain.calculations.registry.binding_selector_utils"
    )
    decimal_alias = ".. py:type:: DecimalValue\n   :module: cadrumo.application.storage.calc_sheets.records"
    assert binding_alias in binding_selector
    assert decimal_alias in calc_sheet_records
    assert ".. py:type:: M145CommunicationRecordId" in m145_records
    assert ".. py:type:: ModeloDraftContentAddress" in filing_schema
    assert ".. py:type:: SecureObjectListItem" in secure_object_records
    assert ".. py:type:: ComponentCatalogue" in iva_components


def test_pep604_alias_detection_rejects_value_unions(tmp_path: Path) -> None:
    """Union syntax is a type alias only when its operands are type expressions."""
    source = tmp_path / "union_aliases.py"
    source.write_text(
        "class Left:\n    pass\n\n"
        "class Right:\n    pass\n\n"
        "PublicUnion = Left | Right\n"
        "PrimitiveUnion = str | int | None\n"
        "ACTION_SET = frozenset({'read'})\n"
        "COMMIT_ACTIONS = ACTION_SET | frozenset({'commit'})\n",
        encoding="utf-8",
    )

    aliases = dict(_type_alias_declarations(source))

    assert set(aliases) == {"PublicUnion", "PrimitiveUnion"}


def test_type_alias_factories_resolve_imports_and_reject_shadowed_values(tmp_path: Path) -> None:
    """Generic factories need canonical type bindings, not matching attribute names."""
    source_root = tmp_path / "src" / "fixture_api"
    source_root.mkdir(parents=True)
    (source_root / "__init__.py").write_text('"""Fixture API."""\n', encoding="utf-8")
    canonical = source_root / "canonical.py"
    canonical.write_text(
        "from typing import Mapping, NewType, TypeAliasType\n"
        "import typing as typing_module\n"
        "import collections.abc as collections_abc\n\n"
        "Mapping: object\n"
        "ImportedMapping = Mapping[str, int]\n"
        "QualifiedMapping = typing_module.Mapping[str, int]\n"
        "CollectionsMapping = collections_abc.Mapping[str, int]\n"
        "UserIdentifier = NewType('UserIdentifier', int)\n"
        "TextAlias = TypeAliasType('TextAlias', str)\n",
        encoding="utf-8",
    )
    (source_root / "generic_factory.py").write_text(
        "class LocalGeneric:\n    pass\n\n"
        "GenericAlias = LocalGeneric[str]\n"
        "INSTANCE = LocalGeneric()\n"
        "CONFIG = dict()\n",
        encoding="utf-8",
    )
    shadowed = source_root / "shadowed.py"
    shadowed.write_text(
        "from typing import Mapping, NewType, TypeAliasType\n"
        "Mapping = {'kind': str}\n"
        "POLICY = Mapping['kind']\n"
        "namespace = object()\n"
        "NAMESPACE_POLICY = namespace.Mapping['kind']\n"
        "NewType = lambda *args: args\n"
        "NotAType = NewType('NotAType', str)\n"
        "TypeAliasType = lambda *args: args\n"
        "AnotherNotAType = TypeAliasType('AnotherNotAType', str)\n",
        encoding="utf-8",
    )

    canonical_aliases = dict(_type_alias_declarations(canonical))
    generic_aliases = dict(_type_alias_declarations(source_root / "generic_factory.py"))
    shadowed_aliases = dict(_type_alias_declarations(shadowed))

    assert set(canonical_aliases) == {
        "ImportedMapping",
        "QualifiedMapping",
        "CollectionsMapping",
        "UserIdentifier",
        "TextAlias",
    }
    assert set(generic_aliases) == {"GenericAlias"}
    assert shadowed_aliases == {}

    manager = ApiStubManager(src_cadrumo=source_root, docs_api=tmp_path / "api")
    manager.scaffold()
    canonical_stub = (tmp_path / "api" / "fixture_api.canonical.rst").read_text(encoding="utf-8")
    shadowed_stub = (tmp_path / "api" / "fixture_api.shadowed.rst").read_text(encoding="utf-8")
    assert ".. py:type:: ImportedMapping" in canonical_stub
    assert ".. py:type:: TextAlias" in canonical_stub
    assert ":exclude-members: CollectionsMapping,ImportedMapping,QualifiedMapping,TextAlias,UserIdentifier" in (
        canonical_stub
    )
    assert ".. py:type:: POLICY" not in shadowed_stub
    assert ".. py:type:: NAMESPACE_POLICY" not in shadowed_stub
    assert ".. py:type:: NotAType" not in shadowed_stub
    assert ".. py:type:: AnotherNotAType" not in shadowed_stub
    assert ":exclude-members:" not in shadowed_stub
    generic_stub = (tmp_path / "api" / "fixture_api.generic_factory.rst").read_text(encoding="utf-8")
    assert ".. py:type:: GenericAlias" in generic_stub
    assert ".. py:type:: INSTANCE" not in generic_stub
    assert ".. py:type:: CONFIG" not in generic_stub


def test_type_checking_aliases_are_source_targets_only_for_canonical_guards(tmp_path: Path) -> None:
    """Direct TYPE_CHECKING aliases are indexed without treating arbitrary branches as declarations."""
    source_root = tmp_path / "src" / "fixture_api"
    source_root.mkdir(parents=True)
    (source_root / "__init__.py").write_text('"""Fixture API."""\n', encoding="utf-8")
    guarded = source_root / "guarded.py"
    guarded.write_text(
        "from typing import TYPE_CHECKING as STATIC_ONLY\n"
        "import typing as typing_module\n\n"
        "STATIC_ONLY: object\n"
        "typing_module: object\n\n"
        "if STATIC_ONLY:\n"
        "    type ImportedGuardAlias = tuple[int, str]\n"
        "    if FEATURE_ENABLED:\n"
        "        type NestedGuardAlias = tuple[int, str]\n\n"
        "def local_types() -> None:\n"
        "    if STATIC_ONLY:\n"
        "        type FunctionLocalAlias = tuple[int, str]\n\n"
        "if typing_module.TYPE_CHECKING:\n"
        "    type QualifiedGuardAlias = tuple[int, str]\n\n"
        "if FEATURE_ENABLED:\n"
        "    type UnrelatedGuardAlias = tuple[int, str]\n\n"
        "namespace = object()\n"
        "if namespace.TYPE_CHECKING:\n"
        "    type NamespaceGuardAlias = tuple[int, str]\n\n"
        "if STATIC_ONLY:\n"
        "    type ReboundAlias = tuple[int, str]\n"
        "ReboundAlias = 'ordinary public value'\n",
        encoding="utf-8",
    )
    shadowed = source_root / "shadowed_guard.py"
    shadowed.write_text(
        "from typing import TYPE_CHECKING as STATIC_ONLY\n"
        "STATIC_ONLY = True\n"
        "if STATIC_ONLY:\n"
        "    type ShadowedGuardAlias = tuple[int, str]\n",
        encoding="utf-8",
    )

    aliases = dict(_type_alias_declarations(guarded))
    assert set(aliases) == {"ImportedGuardAlias", "QualifiedGuardAlias"}
    assert _type_alias_declarations(shadowed) == ()

    manager = ApiStubManager(source_root, tmp_path / "api")
    manager.scaffold()
    stub = (tmp_path / "api" / "fixture_api.guarded.rst").read_text(encoding="utf-8")
    for alias in aliases:
        target = f".. py:type:: {alias}\n   :module: fixture_api.guarded"
        assert stub.count(target) == 1
    excluded_members = next(line.strip() for line in stub.splitlines() if line.strip().startswith(":exclude-members:"))
    assert excluded_members == ":exclude-members: ImportedGuardAlias,QualifiedGuardAlias"
    for non_target in (
        "NestedGuardAlias",
        "FunctionLocalAlias",
        "UnrelatedGuardAlias",
        "NamespaceGuardAlias",
        "ReboundAlias",
    ):
        assert f".. py:type:: {non_target}" not in stub
        assert non_target not in excluded_members
    shadowed_stub = (tmp_path / "api" / "fixture_api.shadowed_guard.rst").read_text(encoding="utf-8")
    assert ".. py:type:: ShadowedGuardAlias" not in shadowed_stub
    assert ":exclude-members:" not in shadowed_stub


def test_alias_targets_require_type_syntax_not_a_suffix_match(tmp_path: Path) -> None:
    """Source-derived targets exclude same-suffix ordinary value aliases."""
    source_root = tmp_path / "src" / "fixture_api"
    (source_root / "__init__.py").parent.mkdir(parents=True)
    (source_root / "__init__.py").write_text(
        '"""Fixture API."""\nfrom .values import CanonicalPolicy\nPublishedPolicy = CanonicalPolicy\n',
        encoding="utf-8",
    )
    (source_root / "values.py").write_text(
        'class CanonicalPolicy:\n    """Type fixture."""\n\n\nDEFAULT_POLICY = "encrypted"\n',
        encoding="utf-8",
    )
    (source_root / "contracts.py").write_text(
        "from collections.abc import Mapping\n"
        "from typing import Annotated, Literal\n"
        "from .values import CanonicalPolicy, DEFAULT_POLICY\n\n"
        "type DeclaredMode = Literal['read', 'write']\n"
        "Lookup = Mapping[str, str]\n"
        "BoundedText = Annotated[str, 'bounded']\n"
        "ExportedPolicy = CanonicalPolicy\n"
        "PublicPolicy = DEFAULT_POLICY\n"
        "AnnotationOnlyAlias = Mapping[str, str]\n"
        "AnnotationOnlyAlias: object\n"
        "ReboundAssignment = Mapping[str, str]\n"
        "ReboundAssignment = 'ordinary public value'\n"
        "ReboundAnnotation = Mapping[str, str]\n"
        "ReboundAnnotation: object = 'ordinary public value'\n"
        "ReboundImport = Mapping[str, str]\n"
        "from typing import Any as ReboundImport\n"
        "ReboundClass = Mapping[str, str]\n"
        "class ReboundClass:\n    pass\n"
        "ReboundFunction = Mapping[str, str]\n"
        "def ReboundFunction():\n    pass\n",
        encoding="utf-8",
    )
    api_root = tmp_path / "api"
    manager = ApiStubManager(source_root, api_root)

    manager.scaffold()

    stub = (api_root / "fixture_api.contracts.rst").read_text(encoding="utf-8")
    package_stub = (api_root / "fixture_api.rst").read_text(encoding="utf-8")
    assert ".. py:type:: DeclaredMode\n   :module: fixture_api.contracts" in stub
    assert "type DeclaredMode = Literal['read', 'write']" in stub
    assert ".. py:type:: Lookup\n   :module: fixture_api.contracts" in stub
    assert ".. py:type:: BoundedText\n   :module: fixture_api.contracts" in stub
    assert ".. py:type:: ExportedPolicy\n   :module: fixture_api.contracts" in stub
    assert ".. py:type:: AnnotationOnlyAlias\n   :module: fixture_api.contracts" in stub
    assert ".. py:type:: PublicPolicy" not in stub
    assert ".. py:type:: PublishedPolicy\n   :module: fixture_api" in package_stub
    overwritten_names = {
        "ReboundAssignment",
        "ReboundAnnotation",
        "ReboundImport",
        "ReboundClass",
        "ReboundFunction",
    }
    assert not any(f".. py:type:: {name}" in stub for name in overwritten_names)
    excluded_members = next(
        line.partition(":exclude-members:")[2] for line in stub.splitlines() if ":exclude-members:" in line
    )
    assert not overwritten_names.intersection(name.strip() for name in excluded_members.split(","))


def test_imported_generic_models_are_excluded_only_at_consumers(tmp_path: Path) -> None:
    """Pydantic generic consumers must not re-index their defining objects."""
    manager = ApiStubManager(src_cadrumo=REPO_ROOT / "src" / "cadrumo", docs_api=tmp_path / "api")
    manager.scaffold()

    owner = (tmp_path / "api" / "cadrumo.application.aggregation._models.rst").read_text(encoding="utf-8")
    consumer = (tmp_path / "api" / "cadrumo.application.aggregation.renta_ledger.rst").read_text(
        encoding="utf-8",
    )
    assert "LedgerAggregationResultBase" not in owner
    assert ":exclude-members: LedgerAggregationResultBase" in consumer


def test_imported_journal_repository_base_is_excluded_only_at_consumers(tmp_path: Path) -> None:
    """Journal repositories keep their shared generic base at its defining stub."""
    manager = ApiStubManager(src_cadrumo=REPO_ROOT / "src" / "cadrumo", docs_api=tmp_path / "api")
    manager.scaffold()

    config_reset = (tmp_path / "api" / "cadrumo.application.config_reset_repository.rst").read_text(
        encoding="utf-8",
    )
    bundle_export = (tmp_path / "api" / "cadrumo.application.user_profile.bundle_export_operation.rst").read_text(
        encoding="utf-8"
    )
    assert ":exclude-members: JournalRepositoryBase" in config_reset
    assert ":exclude-members: JournalRepositoryBase" in bundle_export


def test_repository_api_scope_covers_every_canonical_package_and_cross_package_owner(tmp_path: Path) -> None:
    """The published API tree includes each first-party package and the missing type owners."""
    canonical_roots = tuple(root for root in FIRST_PARTY_ROOTS if root.startswith("src/"))
    assert canonical_roots == API_SOURCE_ROOTS

    manager = ApiStubManager.for_repository(REPO_ROOT, docs_api=tmp_path / "api")
    assert manager.src_cadrumo == REPO_ROOT / "src" / API_SOURCE_PACKAGE
    discovered = manager.discover_modules()
    assert discovered == sorted(discovered)
    modules = set(discovered)
    package_roots = {name for name, is_package in modules if is_package and "." not in name}
    expected_package_roots = {Path(root).name for root in canonical_roots}
    assert package_roots == expected_package_roots

    owners = {
        "cadrumo_client.transport.frontend_client",
        "cadrumo_client.transport.automation_decision",
        "cadrumo_client.contracts.profile_access",
        "cadrumo_client.transport.profile_password_rotation",
        "cadrumo_runtime.commands.main",
        "cadrumo_harness.mcp.main",
        "cadrumo_agent_service.main",
    }
    discovered_names = {name for name, _ in modules}
    assert owners <= discovered_names, f"missing API owner modules: {sorted(owners - discovered_names)}"

    manager.scaffold()
    for package_name in expected_package_roots:
        page = tmp_path / "api" / f"{package_name}.rst"
        assert page.is_file(), f"canonical package root has no generated page: {package_name}"
        assert f".. automodule:: {package_name}" in page.read_text(encoding="utf-8")

    automation_decision = (tmp_path / "api" / "cadrumo_client.transport.automation_decision.rst").read_text(
        encoding="utf-8"
    )
    assert (
        ".. py:type:: AutomationDecision\n   :module: cadrumo_client.transport.automation_decision"
        in automation_decision
    )

    index = (REPO_ROOT / "docs" / "api" / "index.md").read_text(encoding="utf-8")
    toctree = index.split("```{toctree}", maxsplit=1)[1].split("```", maxsplit=1)[0]
    entries = {line.strip() for line in toctree.splitlines() if line.strip() and not line.strip().startswith(":")}
    assert entries == expected_package_roots, f"the authored API index does not reach every package root: {entries}"


def test_repository_api_scope_refuses_a_missing_canonical_package_root(tmp_path: Path) -> None:
    """A broken checkout cannot silently publish a partial first-party API tree."""
    repo_root = tmp_path / "repo"
    missing = Path("src/cadrumo_client")
    for source_root in API_SOURCE_ROOTS:
        if Path(source_root) != missing:
            (repo_root / source_root).mkdir(parents=True)

    with pytest.raises(ApiDocsError) as raised:
        ApiStubManager.for_repository(repo_root, docs_api=tmp_path / "api")

    assert str(repo_root / missing) in str(raised.value)


def test_cli_reference_exclusion_is_limited_to_the_primary_application(tmp_path: Path) -> None:
    """A sibling package's similarly named CLI modules remain API documentation."""
    source_parent = tmp_path / "src"
    application_root = source_parent / API_SOURCE_PACKAGE
    client_root = tmp_path.joinpath(*Path(CLIENT_PACKAGE).parts)
    for root in (application_root, client_root):
        for relative in (
            "__init__.py",
            "entrypoints/__init__.py",
            "entrypoints/cli/__init__.py",
            "entrypoints/cli/main.py",
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('"""Fixture module."""\n', encoding="utf-8", newline="\n")

    manager = ApiStubManager(
        src_cadrumo=application_root,
        docs_api=tmp_path / "api",
        source_roots=(application_root, client_root),
    )
    modules = set(manager.discover_modules())

    assert ("cadrumo.entrypoints.cli", True) not in modules
    assert ("cadrumo.entrypoints.cli.main", False) not in modules
    assert ("cadrumo_client.entrypoints.cli", True) in modules
    assert ("cadrumo_client.entrypoints.cli.main", False) in modules


def test_scaffold_produces_conformant_tree(tmp_path: Path) -> None:
    """scaffold() followed by check() returns an empty DriftResult.

    A freshly scaffolded tree must be immediately conformant: every
    source module has a stub and no stubs are orphaned.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    result = manager.scaffold()

    assert isinstance(result, ScaffoldResult)
    assert result.written >= _MINIMUM_STUB_POPULATION, (
        f"the run wrote only {result.written} stubs, so the conformance claim below "
        "compares a tree that is not the source tree"
    )

    drift = manager.check()
    assert isinstance(drift, DriftResult)
    assert drift.is_conformant, (
        f"Drift after scaffold — missing: {drift.missing_stubs!r}, orphans: {drift.orphan_stubs!r}"
    )


def test_check_detects_missing_stub(tmp_path: Path) -> None:
    """check() reports a module as missing when its stub file is absent.

    After scaffolding, deleting one stub file causes check() to report
    that module in missing_stubs.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()

    # Remove one known stub and verify check() surfaces it.
    target = docs_api / "cadrumo.core.errors.rst"
    assert target.exists(), f"Expected stub not found: {target}"
    target.unlink()

    drift = manager.check()
    assert "cadrumo.core.errors" in drift.missing_stubs
    assert not drift.is_conformant


def test_check_detects_orphan_stub(tmp_path: Path) -> None:
    """check() reports an RST file as orphaned when no module backs it.

    Injecting a stub for a non-existent module causes check() to list it
    in orphan_stubs.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()

    ghost = docs_api / "cadrumo.does_not_exist.rst"
    ghost.write_text(".. automodule:: cadrumo.does_not_exist\n", encoding="utf-8")

    drift = manager.check()
    assert "cadrumo.does_not_exist" in drift.orphan_stubs
    assert not drift.is_conformant


def test_check_detects_stale_stub_content(tmp_path: Path) -> None:
    """check() reports a generated stub whose content was hand-edited."""

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()

    target = docs_api / "cadrumo.core.errors.rst"
    target.write_text("cadrumo.core.errors module\n=======================\n\nmanual drift\n", encoding="utf-8")

    drift = manager.check()
    assert "cadrumo.core.errors" in drift.stale_stubs
    assert not drift.is_conformant


def test_check_detects_a_terminator_translated_stub(tmp_path: Path) -> None:
    """check() reports a stub whose terminators were translated after it was written.

    This is the case a decoded-text comparison structurally cannot reach.
    ``Path.read_text`` is universal-newline, so the planted CRLF bytes decode
    to exactly the canonical string — the middle assertion below asserts that
    equality outright, which is the comparison the check used to perform and
    pass. Git is equally blind: the repository normalises to LF on the index
    side, so the same file shows no diff. The stale verdict at the end is
    therefore the only reader in the system that can see this drift at all.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()
    assert manager.check().is_conformant, "the tree must be clean before the drift is planted"

    target = docs_api / "cadrumo.core.errors.rst"
    canonical = target.read_bytes()
    assert b"\r\n" not in canonical, "the generator must emit line feeds for the plant to mean anything"

    target.write_bytes(canonical.replace(b"\n", b"\r\n"))

    assert target.read_text(encoding="utf-8") == canonical.decode("utf-8"), (
        "the planted file must still decode to the canonical text, or this proves nothing "
        "about the comparison that normalised terminators away"
    )

    drift = manager.check()
    assert "cadrumo.core.errors" in drift.stale_stubs
    assert not drift.is_conformant


def test_scaffold_writes_line_feed_terminators(tmp_path: Path) -> None:
    """Every stub the generator writes carries line feeds, on every platform.

    Without the explicit newline the writer translates on write, which is how
    a check that reads through the same translation came to be blind to its
    own output.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    result = manager.scaffold()

    rst_paths = scan_directory(docs_api, pattern="*.rst")
    # The equality alone does not establish that the run covered the source
    # tree: an empty expected set writes nothing and scans nothing, ``0 == 0``
    # holds, and ``translated`` is then empty for the absence claim below.
    assert result.written >= _MINIMUM_STUB_POPULATION, (
        f"the run wrote only {result.written} stubs, so the terminator claim below reads almost nothing"
    )
    assert len(rst_paths) == result.written, "the scan must cover every stub the run reported writing"

    translated = [rst_path.name for rst_path in rst_paths if b"\r\n" in rst_path.read_bytes()]
    assert not translated, f"the generator translated terminators in {len(translated)} stubs: {translated[:5]}"


def test_scaffold_rewrites_a_terminator_translated_stub(tmp_path: Path) -> None:
    """scaffold() restores a translated stub instead of counting it unchanged.

    The skip-if-current branch shares the comparison with check(), so a text
    comparison would have skipped this file forever and left the drift on disk
    permanently.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    manager.scaffold()

    target = docs_api / "cadrumo.core.errors.rst"
    canonical = target.read_bytes()
    target.write_bytes(canonical.replace(b"\n", b"\r\n"))

    second = manager.scaffold()

    assert second.written == 1, f"expected the one translated stub to be rewritten, got {second.written}"
    assert target.read_bytes() == canonical


def test_scaffold_removes_stale_stub(tmp_path: Path) -> None:
    """scaffold() removes stubs whose backing module no longer exists.

    A pre-existing stub for a phantom module is deleted on the next scaffold
    run and the removal is reported in ScaffoldResult.removed_names.
    """

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"
    docs_api.mkdir(parents=True)

    phantom = docs_api / "cadrumo.phantom_module.rst"
    phantom.write_text(".. automodule:: cadrumo.phantom_module\n", encoding="utf-8")

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    result = manager.scaffold()

    # Pinned rather than a membership test, and floored beside it: the
    # generator removes every ``.rst`` absent from its expected set, so a
    # collapsed expectation deletes the entire reference and still satisfies
    # both halves of "the stale stub was removed". Measured live: 1822
    # stubs expected, exactly this one file removed.
    assert result.removed_names == ["cadrumo.phantom_module.rst"]
    assert result.written >= _MINIMUM_STUB_POPULATION, (
        f"the run wrote only {result.written} stubs, so the removal above may be the whole reference"
    )
    assert not phantom.exists()


def test_scaffold_leaves_unchanged_stubs_untouched(tmp_path: Path) -> None:
    """A second scaffold run writes no files when the tree is already current."""

    repo_root = REPO_ROOT
    src_cadrumo = repo_root / "src" / "cadrumo"
    docs_api = tmp_path / "api"

    manager = ApiStubManager(src_cadrumo=src_cadrumo, docs_api=docs_api)
    first = manager.scaffold()
    second = manager.scaffold()

    assert first.written > 0
    assert second.written == 0
    assert second.unchanged == first.written
