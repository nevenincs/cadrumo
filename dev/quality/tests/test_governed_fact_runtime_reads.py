"""Keep product runtime on the published governed-fact authority path."""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..source_import_analysis import module_name_for, resolve_relative_import

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_IVA_RETIREMENT_LEDGER = REPO_ROOT / "dev" / "registry" / "analysis" / "facts_iva_retirement.toml"
_GOVERNED_DIRECTORY_ROOT = ("registry", "aeat")
_RETIRED_OR_AUTHORITY_ONLY_DIRECTORIES = frozenset({"facts", "categories", "calendars", "treaties"})
_TECHNICAL_IVA_FILES = frozenset({"country_names.toml"})
_UNREGISTERED_LOADER_MODULES = frozenset(
    {
        "dev.registry.compiler.authority",
        "dev.registry.compiler.fact_loader",
        "dev.registry.compiler.fact_providers",
    },
)
_SOURCE_ONLY_ADAPTER_ENTRYPOINTS = {
    "src/cadrumo/core/resources/_repos/iva_catalogues.py": "IvaCatalogueRepository._load",
}


@dataclass(frozen=True)
class _RawIvaReadException:
    """One ledger-backed raw IVA reader, narrowed to its executing entrypoint."""

    source: str
    symbol: str


@cache
def _temporary_raw_iva_readers() -> Mapping[str, frozenset[_RawIvaReadException]]:
    """Return the named S80 raw-legal-table exceptions from their retirement ledger."""
    ledger = tomllib.loads(_IVA_RETIREMENT_LEDGER.read_text(encoding="utf-8"))
    exceptions: dict[str, set[_RawIvaReadException]] = {}
    for table in ledger["remaining_structured_tables"]:
        if (
            table["classification"] != "needs_typed_schema_and_fact_migration"
            or table["decision"] != "retain_until_lossless_replacement"
        ):
            continue
        data_path = Path(str(table["data_path"]))
        if data_path.parent.as_posix() != "src/cadrumo/_data/registry/aeat/iva":
            continue
        readers = exceptions.setdefault(data_path.name, set())
        for reader in table["direct_readers"]:
            source, _separator, _symbol = str(reader).partition(":")
            symbol = _symbol if _separator else _SOURCE_ONLY_ADAPTER_ENTRYPOINTS.get(source)
            if symbol is None:
                raise AssertionError(f"S80 source-only reader has no narrowed adapter entrypoint: {reader!r}")
            readers.add(_RawIvaReadException(source=source, symbol=symbol))
    return {filename: frozenset(readers) for filename, readers in exceptions.items()}


def _attribute_path(node: ast.Attribute) -> str | None:
    """Return a dotted attribute path rooted in a simple name."""
    parts = [node.attr]
    value: ast.expr = node.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if not isinstance(value, ast.Name):
        return None
    parts.append(value.id)
    return ".".join(reversed(parts))


def _literal_string_sequence(node: ast.AST, bindings: Mapping[str, tuple[str, ...]]) -> tuple[str, ...] | None:
    """Resolve a literal sequence or a name bound to one, without evaluating expressions."""
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if not isinstance(node, ast.Tuple | ast.List):
        return None
    values: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            return None
        values.append(element.value)
    return tuple(values)


def _literal_sequence_bindings(tree: ast.Module) -> Mapping[str, tuple[str, ...]]:
    """Return simple module bindings that preserve a literal path-part sequence."""
    bindings: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        sequence = _literal_string_sequence(node.value, bindings)
        if sequence is not None:
            bindings[node.targets[0].id] = sequence
    return bindings


def _literal_path_parts(call: ast.Call, bindings: Mapping[str, tuple[str, ...]]) -> tuple[str, ...] | None:
    """Return literal positional path parts, resolving only simple literal starred sequences."""
    parts: list[str] = []
    for argument in call.args:
        if isinstance(argument, ast.Starred):
            sequence = _literal_string_sequence(argument.value, bindings)
            if sequence is None:
                return None
            parts.extend(sequence)
            continue
        if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
            return None
        parts.append(argument.value)
    return tuple(parts)


def _import_aliases(
    tree: ast.Module,
    *,
    importer_module: str,
    importer_is_package: bool,
) -> tuple[dict[str, str], set[str], set[str]]:
    """Return module/function aliases relevant to bundled data and runtime imports."""
    aliases: dict[str, str] = {}
    path_readers: set[str] = set()
    import_module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".", 1)[0]
                if alias.asname is not None:
                    aliases[local] = alias.name
                if alias.name == "importlib" or (alias.asname is None and alias.name.startswith("importlib.")):
                    import_module_names.add(local)
        elif isinstance(node, ast.ImportFrom):
            target = resolve_relative_import(importer_module, importer_is_package, node.level, node.module)
            if target is None:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                if target == "cadrumo.core.resources.bundled_data" and alias.name in {"bundled_path", "packaged_data"}:
                    path_readers.add(local)
                else:
                    aliases[local] = f"{target}.{alias.name}"
                if target == "importlib" and alias.name == "import_module":
                    import_module_names.add(local)
    return aliases, path_readers, import_module_names


def _resolved_attribute_path(node: ast.AST, aliases: Mapping[str, str]) -> str | None:
    """Resolve a direct or imported-alias dotted path."""
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if not isinstance(node, ast.Attribute):
        return None
    raw = _attribute_path(node)
    if raw is None:
        return None
    head, _dot, tail = raw.partition(".")
    return f"{aliases[head]}.{tail}" if head in aliases and tail else aliases.get(head, raw)


def _is_data_path_reader(node: ast.AST, aliases: Mapping[str, str], path_readers: set[str]) -> bool:
    """Return whether a call targets either sanctioned bundled-data path seam."""
    if isinstance(node, ast.Name):
        return node.id in path_readers
    resolved = _resolved_attribute_path(node, aliases)
    return resolved in {
        "cadrumo.core.resources.bundled_data.bundled_path",
        "cadrumo.core.resources.bundled_data.packaged_data",
    }


def _is_unregistered_loader(module: str) -> bool:
    """Return whether a development compiler loader is reached from runtime."""
    return any(module == loader or module.startswith(f"{loader}.") for loader in _UNREGISTERED_LOADER_MODULES)


def _has_direct_file_read(tree: ast.Module) -> bool:
    """Return whether this module parses or reads a file rather than merely wires a path."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in {"read_toml"}:
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in {
            "load",
            "loads",
            "open",
            "read_bytes",
            "read_text",
        }:
            return True
    return False


def _parent_nodes(tree: ast.Module) -> Mapping[int, ast.AST]:
    """Return each node's parent so path accesses can be tied to their reader scope."""
    return {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _immediately_reads_path(node: ast.Call, parents: Mapping[int, ast.AST]) -> bool:
    """Return whether this path construction is directly followed by a file read."""
    parent = parents.get(id(node))
    if not isinstance(parent, ast.Attribute) or parent.value is not node:
        return False
    grandparent = parents.get(id(parent))
    return (
        isinstance(grandparent, ast.Call)
        and grandparent.func is parent
        and parent.attr
        in {
            "open",
            "read_bytes",
            "read_text",
        }
    )


def _enclosing_reader_symbols(node: ast.AST, parents: Mapping[int, ast.AST]) -> frozenset[str]:
    """Return the narrow function and class-method names that own one AST node."""
    current = parents.get(id(node))
    function: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    class_name: str | None = None
    while current is not None:
        if function is None and isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
            function = current
        elif class_name is None and isinstance(current, ast.ClassDef):
            class_name = current.name
        current = parents.get(id(current))
    if function is None:
        return frozenset()
    symbols = {function.name}
    if class_name is not None:
        symbols.add(f"{class_name}.{function.name}")
    return frozenset(symbols)


def _enclosing_function_invokes(node: ast.AST, symbol: str, parents: Mapping[int, ast.AST]) -> bool:
    """Return whether the enclosing function delegates path consumption to its named ledger reader."""
    current = parents.get(id(node))
    while current is not None and not isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
        current = parents.get(id(current))
    if current is None:
        return False
    return any(
        isinstance(candidate, ast.Call)
        and (
            (isinstance(candidate.func, ast.Name) and candidate.func.id == symbol)
            or (isinstance(candidate.func, ast.Attribute) and candidate.func.attr == symbol)
        )
        for candidate in ast.walk(current)
    )


def _direct_read_violation(
    *,
    path: tuple[str, ...],
    source: str,
    node: ast.Call,
    parents: Mapping[int, ast.AST],
) -> str | None:
    """Classify one literal bundled path access against authority ownership."""
    if path[:2] != _GOVERNED_DIRECTORY_ROOT:
        return None
    if len(path) < 3:
        return "unregistered governed registry-directory access"
    directory = path[2]
    if directory in _RETIRED_OR_AUTHORITY_ONLY_DIRECTORIES:
        return f"direct governed-directory access registry/aeat/{directory}"
    if directory != "iva":
        return None
    if len(path) < 4:
        return "unregistered governed IVA-directory access"
    filename = path[3]
    if filename in _TECHNICAL_IVA_FILES:
        return None
    readers = _temporary_raw_iva_readers().get(filename, frozenset())
    enclosing_symbols = _enclosing_reader_symbols(node, parents)
    if any(
        reader.source == source
        and (reader.symbol in enclosing_symbols or _enclosing_function_invokes(node, reader.symbol, parents))
        for reader in readers
    ):
        return None
    return f"unregistered governed IVA-table access registry/aeat/iva/{filename}"


def _runtime_violations(
    tree: ast.Module,
    *,
    importer_module: str,
    importer_is_package: bool,
    source: str,
) -> tuple[str, ...]:
    """Return runtime violations for direct data paths or compiler loaders."""
    aliases, path_readers, import_module_names = _import_aliases(
        tree,
        importer_module=importer_module,
        importer_is_package=importer_is_package,
    )
    findings: set[str] = set()
    reads_files = _has_direct_file_read(tree)
    literal_bindings = _literal_sequence_bindings(tree)
    parents = _parent_nodes(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_unregistered_loader(alias.name):
                    findings.add(f"{node.lineno}: unregistered governed-fact loader {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            target = resolve_relative_import(importer_module, importer_is_package, node.level, node.module)
            if target is not None and _is_unregistered_loader(target):
                findings.add(f"{node.lineno}: unregistered governed-fact loader {target}")
        elif isinstance(node, ast.Call):
            if _is_data_path_reader(node.func, aliases, path_readers):
                path = _literal_path_parts(node, literal_bindings)
                if path is None and _immediately_reads_path(node, parents):
                    findings.add(f"{node.lineno}: computed bundled-data path bypasses governed authority census")
                elif path is not None and reads_files:
                    violation = _direct_read_violation(path=path, source=source, node=node, parents=parents)
                    if violation is not None:
                        findings.add(f"{node.lineno}: {violation}")
            is_import_module = (isinstance(node.func, ast.Name) and node.func.id in import_module_names) or (
                _resolved_attribute_path(node.func, aliases) == "importlib.import_module"
            )
            if is_import_module and node.args:
                target = node.args[0]
                if (
                    isinstance(target, ast.Constant)
                    and isinstance(target.value, str)
                    and _is_unregistered_loader(target.value)
                ):
                    findings.add(f"{node.lineno}: unregistered governed-fact loader {target.value}")
            is_builtin_import = (isinstance(node.func, ast.Name) and node.func.id == "__import__") or (
                _resolved_attribute_path(node.func, aliases) == "builtins.__import__"
            )
            if is_builtin_import and node.args:
                target = node.args[0]
                if (
                    isinstance(target, ast.Constant)
                    and isinstance(target.value, str)
                    and _is_unregistered_loader(target.value)
                ):
                    findings.add(f"{node.lineno}: unregistered governed-fact loader {target.value}")
    return tuple(sorted(findings))


def _runtime_modules() -> Iterable[tuple[Path, str, bool]]:
    """Yield product runtime modules, deliberately excluding tests and development tooling."""
    runtime_root = REPO_ROOT / "src" / "cadrumo"
    for path in runtime_root.rglob("*.py"):
        if "tests" in path.parts or path.name.startswith("test_") or path.name == "conftest.py":
            continue
        yield path, module_name_for(path), path.name == "__init__.py"


def test_product_runtime_reads_governed_data_only_through_authority_or_named_s80_exception() -> None:
    """Direct governed-data reads must be canonical or a ledger-backed temporary exception."""
    unread: list[str] = []
    violations: list[str] = []
    for path, module, is_package in _runtime_modules():
        relative = path.relative_to(REPO_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            unread.append(f"{relative}: {exc}")
            continue
        violations.extend(
            f"{relative}: {finding}"
            for finding in _runtime_violations(
                tree,
                importer_module=module,
                importer_is_package=is_package,
                source=relative,
            )
        )
    assert unread == [], "the product-runtime authority census could not parse: " + "; ".join(sorted(unread))
    assert violations == [], "product runtime bypasses governed-fact authority: " + "; ".join(sorted(violations))


def test_detector_rejects_direct_paths_loader_aliases_and_dynamic_loader_bypasses() -> None:
    """Every governed-data bypass form is caught by a discriminating AST mutation."""
    tree = ast.parse(
        "from cadrumo.core.resources.bundled_data import bundled_path as data_path\n"
        "from cadrumo.core.resources.bundled_data import packaged_data\n"
        "data_path('registry', 'aeat', 'facts', '0001-illicit.toml').read_text()\n"
        "packaged_data('registry', 'aeat', 'iva', 'catalogues.toml').read_text()\n"
        "fact_parts = ('registry', 'aeat', 'facts', '0002-illicit.toml')\n"
        "data_path(*fact_parts).read_text()\n"
        "unknown_parts = supplied_path_parts\n"
        "data_path(*unknown_parts).read_text()\n"
        "from dev.registry.compiler.fact_loader import load_governed_facts\n"
        "import importlib\n"
        "importlib.import_module('dev.registry.compiler.fact_providers')\n",
    )

    findings = _runtime_violations(
        tree,
        importer_module="cadrumo.domain.example",
        importer_is_package=False,
        source="src/cadrumo/domain/example.py",
    )

    assert {
        "direct governed-directory access registry/aeat/facts",
        "unregistered governed IVA-table access registry/aeat/iva/catalogues.toml",
        "unregistered governed-fact loader dev.registry.compiler.fact_loader",
        "unregistered governed-fact loader dev.registry.compiler.fact_providers",
        "computed bundled-data path bypasses governed authority census",
    }.issubset({finding.split(": ", 1)[1] for finding in findings})


def test_detector_allows_named_s80_legal_table_exception_and_technical_vocabulary() -> None:
    """The only retained raw legal readers remain ledger-backed, while technical data stays technical."""
    legal_tree = ast.parse(
        "from cadrumo.core.resources.bundled_data import bundled_path\n"
        "def _excluded_territories_by_prefix():\n"
        "    return bundled_path('registry', 'aeat', 'iva', 'territories.toml')\n",
    )
    technical_tree = ast.parse(
        "from cadrumo.core.resources.bundled_data import bundled_path\n"
        "bundled_path('registry', 'aeat', 'iva', 'country_names.toml')\n",
    )

    assert (
        _runtime_violations(
            legal_tree,
            importer_module="cadrumo.domain.iva.establishment",
            importer_is_package=False,
            source="src/cadrumo/domain/iva/establishment.py",
        )
        == ()
    )
    assert (
        _runtime_violations(
            technical_tree,
            importer_module="cadrumo.domain.iva.country_vocabulary",
            importer_is_package=False,
            source="src/cadrumo/domain/iva/country_vocabulary.py",
        )
        == ()
    )


def test_detector_rejects_builtin_loader_and_source_wide_s80_exception_bypasses() -> None:
    """A S80 exception is a named reader entrypoint, never permission for its whole module."""
    bypass_tree = ast.parse(
        "import builtins as builtin_module\n"
        "__import__('dev.registry.compiler.authority')\n"
        "builtin_module.__import__('dev.registry.compiler.fact_loader')\n"
        "from cadrumo.core.resources.bundled_data import bundled_path\n"
        "def bypass():\n"
        "    return bundled_path('registry', 'aeat', 'iva', 'place_of_supply.toml').read_text()\n",
    )
    adapter_tree = ast.parse(
        "from cadrumo.core.resources.bundled_data import bundled_path\n"
        "class IvaCatalogueRepository:\n"
        "    def _load(self):\n"
        "        return bundled_path('registry', 'aeat', 'iva', 'catalogues.toml').read_text()\n",
    )

    findings = _runtime_violations(
        bypass_tree,
        importer_module="cadrumo.domain.iva.classification",
        importer_is_package=False,
        source="src/cadrumo/domain/iva/classification.py",
    )

    assert {
        "unregistered governed-fact loader dev.registry.compiler.authority",
        "unregistered governed-fact loader dev.registry.compiler.fact_loader",
        "unregistered governed IVA-table access registry/aeat/iva/place_of_supply.toml",
    }.issubset({finding.split(": ", 1)[1] for finding in findings})
    assert (
        _runtime_violations(
            adapter_tree,
            importer_module="cadrumo.core.resources._repos.iva_catalogues",
            importer_is_package=False,
            source="src/cadrumo/core/resources/_repos/iva_catalogues.py",
        )
        == ()
    )
