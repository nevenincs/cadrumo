"""Subordinate import-form checks behind the authoritative import gate.

Import Linter owns the dependency graph and every layer decision.  This module
only checks import properties the graph cannot express reliably: canonical
spelling, package-facade consumption, private ownership, inert initialisers,
and closed dynamic-import targets.  First-party roots and package lanes are
read from the Import Linter configuration; no dependency matrix is defined
here.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import hashlib
import itertools
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.exit_codes import FAILED, TOOL_BROKEN
from cadrumo.tests.module_target_inventory import MetadataTargetSetError, load_all_target_sets, load_target_set

_DOTTED_NAME: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
_LAYER_NAME: Final[re.Pattern[str]] = re.compile(r"^(?:\(([A-Za-z_]\w*)\)|([A-Za-z_]\w*))$")
_MAX_ENUMERATED_VALUES: Final[int] = 128
_MAX_CLOSED_DYNAMIC_TARGETS: Final[int] = 4096


@dataclass(frozen=True)
class RootPackage:
    """One first-party root declared by Import Linter."""

    name: str
    path: Path

    @property
    def source_root(self) -> Path:
        """Return the directory from which the root is importable."""
        source_root = self.path
        for _ in self.name.split("."):
            source_root = source_root.parent
        return source_root


@dataclass(frozen=True)
class Authority:
    """Parsed Import Linter roots and the classification it declares."""

    repository: Path
    config_path: Path
    parser: configparser.ConfigParser
    root_packages: tuple[str, ...]
    roots: tuple[RootPackage, ...]
    classifications: tuple[tuple[str, tuple[str, ...]], ...]
    forbidden_contracts: tuple[ForbiddenContract, ...] = ()

    @property
    def root_names(self) -> frozenset[str]:
        """Return the configured first-party roots as immutable data."""
        return frozenset({name for name in self.root_packages})

    def layers_for(self, container: str) -> frozenset[str]:
        """Return the layer tails declared for one Import Linter container."""
        for name, layers in self.classifications:
            if name == container:
                return frozenset(layers)
        return frozenset[str]()


@dataclass(frozen=True)
class AuthorityRead:
    """Result of reading and preflighting the Import Linter authority."""

    authority: Authority | None
    findings: tuple[str, ...] = ()

    @property
    def broken(self) -> bool:
        """Whether authority or closed-classification preflight failed."""
        return bool(self.findings)


@dataclass(frozen=True)
class ForbiddenContract:
    """One dependency-direction contract derived from Import Linter authority."""

    key: str
    name: str
    source_modules: tuple[str, ...]
    forbidden_modules: tuple[str, ...]


@dataclass(frozen=True)
class ImportOccurrence:
    """One normalized direct first-party import that violates a contract."""

    fingerprint: str
    source_module: str
    target_module: str
    imported_symbols: tuple[str, ...]
    import_form: str
    lexical_scope: str
    contract: str
    path: Path
    lineno: int

    def as_dict(self, repository: Path) -> dict[str, object]:
        """Return the stable identity plus movable source-location evidence."""
        try:
            path = self.path.relative_to(repository).as_posix()
        except ValueError:
            path = self.path.as_posix()
        return {
            "contract": self.contract,
            "fingerprint": self.fingerprint,
            "import_form": self.import_form,
            "imported_symbols": list(self.imported_symbols),
            "lexical_scope": self.lexical_scope,
            "location": {"line": self.lineno, "path": path},
            "source_module": self.source_module,
            "target_module": self.target_module,
        }


@dataclass(frozen=True)
class Finding:
    """One subordinate checker diagnostic."""

    category: str
    message: str
    path: Path | None = None
    lineno: int | None = None
    fatal: bool = False
    advisory: bool = False

    def render(self, repository: Path) -> str:
        """Render a stable category and repository-relative location."""
        if self.path is None:
            location = ""
        else:
            try:
                relative = self.path.relative_to(repository).as_posix()
            except ValueError:
                relative = self.path.as_posix()
            location = relative
            if self.lineno is not None:
                location += f":{self.lineno}"
            location += ": "
        prefix = f"[ADVISORY:{self.category}]" if self.advisory else f"[{self.category}]"
        return f"{prefix} {location}{self.message}"


@dataclass(frozen=True)
class CheckResult:
    """Result of one complete subordinate source traversal."""

    findings: tuple[Finding, ...]
    files_scanned: int
    occurrences: tuple[ImportOccurrence, ...] = ()

    @property
    def returncode(self) -> int:
        """Return a finding code or a tool-broken code for an incomplete scan."""
        if any(finding.fatal for finding in self.findings):
            return TOOL_BROKEN
        return FAILED if any(not finding.advisory for finding in self.findings) else 0

    def render(self, repository: Path) -> str:
        """Render diagnostics in deterministic order."""
        return "\n".join(finding.render(repository) for finding in self.findings)

    def as_dict(self, repository: Path) -> dict[str, object]:
        """Return complete machine-readable checker evidence."""
        return {
            "files_scanned": self.files_scanned,
            "findings": [
                {
                    "advisory": finding.advisory,
                    "category": finding.category,
                    "fatal": finding.fatal,
                    "line": finding.lineno,
                    "message": finding.message,
                    "path": (
                        finding.path.relative_to(repository).as_posix()
                        if finding.path is not None and finding.path.is_relative_to(repository)
                        else finding.path.as_posix() if finding.path is not None else None
                    ),
                }
                for finding in self.findings
            ],
            "occurrences": [occurrence.as_dict(repository) for occurrence in self.occurrences],
            "schema_version": 2,
        }


def read_authority(repository: Path, config_path: Path | None = None) -> AuthorityRead:
    """Read Import Linter roots and validate its closed boundary.

    The checks are deliberately generic: they verify that the declared roots
    and exhaustive layer containers cover the source tree, while all
    dependency direction remains in Import Linter's own contracts.
    """
    repository = repository.resolve()
    if not repository.is_dir():
        return AuthorityRead(None, (f"[AUTHORITY_CONFIG] repository root is not a directory: {repository}",))

    path = (
        (repository / ".importlinter")
        if config_path is None
        else (config_path if config_path.is_absolute() else repository / config_path)
    )
    path = path.resolve()
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with path.open("r", encoding=UTF_8) as stream:
            parser.read_file(stream)
    except (OSError, UnicodeError, configparser.Error) as exc:
        return AuthorityRead(None, (f"[AUTHORITY_CONFIG] cannot read {path}: {exc}",))

    if "importlinter" not in parser:
        return AuthorityRead(None, (f"[AUTHORITY_CONFIG] {path} has no [importlinter] section",))

    section = parser["importlinter"]
    raw_roots = section.get("root_packages", section.get("root_package", ""))
    root_packages = tuple(_split_words(raw_roots))
    findings: list[str] = []

    if not root_packages:
        findings.append("[UNCLASSIFIED_ROOT] Import Linter declares no root_packages")
    if _truthy(section.get("exclude_type_checking_imports", "false")):
        findings.append("[AUTHORITY_CONFIG] Import Linter excludes TYPE_CHECKING imports from its graph")
    if len(root_packages) != len(set(root_packages)):
        findings.append("[AUTHORITY_CONFIG] Import Linter root_packages contains duplicates")
    for package in root_packages:
        if not _DOTTED_NAME.fullmatch(package):
            findings.append(f"[UNCLASSIFIED_ROOT] invalid first-party root name {package!r}")

    roots: list[RootPackage] = []
    for package in root_packages:
        located = _locate_root(repository, package)
        if located is None:
            findings.append(f"[UNCLASSIFIED_ROOT] declared root {package!r} has no Python source directory")
        else:
            roots.append(RootPackage(package, located))

    _check_root_overlaps(roots, findings)
    _check_undeclared_top_level_roots(repository, root_packages, findings)

    classifications: list[tuple[str, tuple[str, ...]]] = []
    forbidden_contracts: list[ForbiddenContract] = []
    classified_containers: set[str] = set()
    for name in parser.sections():
        contract = parser[name]
        if not name.startswith("importlinter:contract:"):
            continue
        contract_type = contract.get("type", "").strip().lower()
        if contract_type == "forbidden":
            sources = tuple(_split_words(contract.get("source_modules", "")))
            forbidden = tuple(_split_words(contract.get("forbidden_modules", "")))
            display_name = contract.get("name", name.removeprefix("importlinter:contract:")).strip()
            contract_key = name.removeprefix("importlinter:contract:")
            if not sources:
                findings.append(f"[AUTHORITY_CONFIG] forbidden contract {name!r} has no source_modules")
            if not forbidden:
                findings.append(f"[AUTHORITY_CONFIG] forbidden contract {name!r} has no forbidden_modules")
            forbidden_contracts.append(
                ForbiddenContract(
                    key=contract_key,
                    name=display_name,
                    source_modules=tuple(sorted(sources)),
                    forbidden_modules=tuple(sorted(forbidden)),
                )
            )
            continue
        if contract_type != "layers":
            continue

        containers = _split_words(contract.get("containers", ""))
        layers = _parse_layer_names(contract.get("layers", ""), name, findings)
        if not containers:
            findings.append(f"[UNCLASSIFIED_PACKAGE] layer contract {name!r} has no containers")
        if not layers:
            findings.append(f"[UNCLASSIFIED_PACKAGE] layer contract {name!r} declares no layers")
        if not _truthy(contract.get("exhaustive", "false")):
            findings.append(f"[UNCLASSIFIED_PACKAGE] layer contract {name!r} is not exhaustive")
        for container in containers:
            if container in classified_containers:
                findings.append(f"[AUTHORITY_CONFIG] container {container!r} has duplicate classifications")
            classified_containers.add(container)
            classifications.append((container, tuple(sorted(layers))))

    for root in root_packages:
        if not any(container == root or container.startswith(f"{root}.") for container in classified_containers):
            findings.append(f"[UNCLASSIFIED_PACKAGE] root {root!r} has no Import Linter layer classification")

    for container in sorted(classified_containers):
        container_path = _locate_container(roots, container)
        if container_path is None:
            findings.append(f"[UNCLASSIFIED_PACKAGE] classified container {container!r} has no source directory")
            continue
        layers = next((set(values) for name, values in classifications if name == container), set())
        for child in _direct_children(container_path):
            if child not in layers:
                findings.append(
                    f"[UNCLASSIFIED_PACKAGE] {container!r} child {child!r} is absent from its declared layers"
                )

    for name in parser.sections():
        contract = parser[name]
        if _has_options(contract, "ignore_imports", "exhaustive_ignores"):
            findings.append(f"[AUTHORITY_CONFIG] contract {name!r} contains an import suppression")
        if _truthy(contract.get("allow_indirect_imports", "false")):
            findings.append(f"[AUTHORITY_CONFIG] contract {name!r} allows indirect-import suppression")
        alerting = contract.get("unmatched_ignore_imports_alerting", "error").strip().lower()
        if alerting not in {"error", ""}:
            findings.append(f"[AUTHORITY_CONFIG] contract {name!r} treats unmatched imports as {alerting}")

    authority = Authority(
        repository=repository,
        config_path=path,
        parser=parser,
        root_packages=root_packages,
        roots=tuple(roots),
        classifications=tuple(sorted(classifications)),
        forbidden_contracts=tuple(sorted(forbidden_contracts, key=lambda item: item.key)),
    )
    return AuthorityRead(authority, tuple(findings))


def _split_words(value: str) -> list[str]:
    """Split Import Linter's multiline list fields without policy semantics."""
    return [token for line in value.splitlines() for token in line.split()]


def _parse_layer_names(value: str, contract_name: str, findings: list[str]) -> tuple[str, ...]:
    """Parse layer tails so package coverage can be derived from the authority."""
    result: list[str] = []
    for raw in value.replace("\n", " ").split(":"):
        token = raw.strip()
        if not token:
            continue
        match = _LAYER_NAME.fullmatch(token)
        if match is None:
            findings.append(f"[UNCLASSIFIED_PACKAGE] invalid layer {token!r} in {contract_name!r}")
            continue
        result.append(match.group(1) or match.group(2))
    if len(result) != len(set(result)):
        findings.append(f"[AUTHORITY_CONFIG] layer contract {contract_name!r} repeats a layer")
    return tuple(result)


def _locate_root(repository: Path, package: str) -> Path | None:
    """Locate one configured root without importing it."""
    relative = Path(*package.split("."))
    candidates = (repository / "src" / relative, repository / relative)
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        if (candidate / "__init__.py").is_file() or any(candidate.rglob("*.py")):
            return candidate.resolve()
    return None


def _locate_container(roots: Sequence[RootPackage], container: str) -> Path | None:
    """Resolve a classified container below one configured root."""
    for root in sorted(roots, key=lambda item: len(item.name), reverse=True):
        if container == root.name:
            return root.path
        prefix = f"{root.name}."
        if container.startswith(prefix):
            suffix = container[len(prefix) :]
            candidate = root.path.joinpath(*suffix.split("."))
            if candidate.is_dir():
                return candidate
    return None


def _direct_children(path: Path) -> tuple[str, ...]:
    """Return Python direct-child tails in a classified container."""
    children: set[str] = set()
    try:
        entries = tuple(path.iterdir())
    except OSError:
        return ()
    for entry in entries:
        if entry.is_file() and entry.suffix == ".py" and entry.name != "__init__.py":
            children.add(entry.stem)
        elif entry.is_dir() and any(entry.rglob("*.py")):
            children.add(entry.name)
    return tuple(sorted(children))


def _check_root_overlaps(roots: Sequence[RootPackage], findings: list[str]) -> None:
    """Reject nested configured roots that would double-count module identity."""
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            try:
                right.path.relative_to(left.path)
            except ValueError:
                try:
                    left.path.relative_to(right.path)
                except ValueError:
                    continue
            findings.append(f"[AUTHORITY_CONFIG] configured roots {left.name!r} and {right.name!r} overlap")


def _check_undeclared_top_level_roots(repository: Path, root_packages: Sequence[str], findings: list[str]) -> None:
    """Find regular or namespace-like Python roots omitted from the authority."""
    declared = {package.split(".", 1)[0] for package in root_packages}
    candidates: set[str] = set()
    source_modules: set[str] = set()
    for base in (repository / "src", repository):
        if not base.is_dir():
            continue
        try:
            entries = tuple(base.iterdir())
        except OSError as exc:
            findings.append(f"[AUTHORITY_CONFIG] cannot inspect source-root directory {base}: {exc}")
            continue
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if base == repository / "src" and entry.is_file() and entry.suffix == ".py":
                source_modules.add(entry.stem)
                continue
            if not entry.is_dir():
                continue
            if (entry / "__init__.py").is_file() or (base == repository / "src" and any(entry.rglob("*.py"))):
                candidates.add(entry.name)
    for candidate in sorted(candidates | source_modules):
        if candidate not in declared:
            findings.append(f"[UNCLASSIFIED_ROOT] Python root {candidate!r} is absent from root_packages")
    for candidate in sorted(source_modules & declared):
        findings.append(f"[AUTHORITY_CONFIG] source module {candidate!r} collides with a declared root")


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _has_options(section: Mapping[str, str], *keys: str) -> bool:
    return any(key in section for key in keys)


@dataclass
class _Binding:
    """One module-level binding used by canonical-symbol checks."""

    kind: str
    target: str | None = None
    imported_name: str | None = None


@dataclass
class _Module:
    """Parsed source module and its module-level binding facts."""

    name: str
    path: Path
    tree: ast.Module
    is_package: bool
    bindings: dict[str, _Binding] = field(default_factory=dict)
    imported_count: int = 0
    local_definitions: int = 0
    has_imports: bool = False


def check_authority(authority: Authority) -> CheckResult:
    """Run one complete syntax/canonical/dynamic traversal."""
    try:
        modules, findings = _read_modules(authority)
        if not modules:
            findings.append(Finding("ZERO_FILES", "no governed Python files were scanned", fatal=True))
            return _result(findings, 0, authority.repository)
        _check_initializers(authority, modules, findings)
        _check_static_imports(authority, modules, findings)
        known = frozenset((*modules, *authority.root_packages))
        closed_attribute_targets = _closed_attribute_targets(modules, authority.root_names, known)
        _check_dynamic_imports(authority, modules, findings, closed_attribute_targets)
        occurrences = _collect_import_occurrences(authority, modules, closed_attribute_targets)
        return _result(findings, len(modules), authority.repository, occurrences)
    except Exception as exc:  # broad: the checker boundary must fail closed
        return CheckResult(
            (Finding("INTERNAL_CHECKER", f"subordinate checker aborted: {exc}", fatal=True),),
            0,
        )


def _result(
    findings: list[Finding],
    files_scanned: int,
    repository: Path,
    occurrences: Sequence[ImportOccurrence] = (),
) -> CheckResult:
    """Sort diagnostics before returning the component result."""
    ordered = sorted(
        findings,
        key=lambda finding: (
            finding.path.relative_to(repository).as_posix() if finding.path is not None else "",
            finding.lineno or 0,
            finding.category,
            finding.message,
        ),
    )
    ordered_occurrences = sorted(
        occurrences,
        key=lambda occurrence: (
            occurrence.fingerprint,
            occurrence.path.as_posix(),
            occurrence.lineno,
        ),
    )
    return CheckResult(tuple(ordered), files_scanned, tuple(ordered_occurrences))


def _read_modules(authority: Authority) -> tuple[dict[str, _Module], list[Finding]]:
    modules: dict[str, _Module] = {}
    findings: list[Finding] = []
    for root in authority.roots:
        try:
            paths = sorted(root.path.rglob("*.py"), key=lambda item: item.as_posix())
        except OSError as exc:
            findings.append(Finding("READ_FAILURE", f"cannot enumerate governed root: {exc}", root.path, fatal=True))
            continue
        if not paths:
            findings.append(
                Finding(
                    "ZERO_FILES",
                    f"root {root.name!r} contains no governed Python files",
                    root.path,
                    fatal=True,
                )
            )
        for path in paths:
            try:
                source = path.read_text(encoding=UTF_8)
            except (OSError, UnicodeError) as exc:
                findings.append(Finding("READ_FAILURE", f"cannot read governed file: {exc}", path, fatal=True))
                continue
            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError as exc:
                findings.append(
                    Finding("PARSE_FAILURE", f"cannot parse governed file: {exc.msg}", path, exc.lineno, True)
                )
                continue
            name = _module_name(path, root)
            if name in modules:
                findings.append(Finding("INTERNAL_CHECKER", f"duplicate module identity {name!r}", path, fatal=True))
                continue
            modules[name] = _Module(name, path, tree, path.name == "__init__.py")

    for module in modules.values():
        _collect_bindings(module, authority.root_names)
    return modules, findings


def _collect_import_occurrences(
    authority: Authority,
    modules: Mapping[str, _Module],
    closed_attribute_targets: frozenset[str],
) -> tuple[ImportOccurrence, ...]:
    """Collect direct, occurrence-level violations from the declared authority."""
    known = frozenset((*modules, *authority.root_packages))
    occurrences: list[ImportOccurrence] = []
    for module in modules.values():
        visitor = _OccurrenceVisitor(
            authority=authority,
            module=module,
            modules=modules,
            known=known,
            closed_attribute_targets=closed_attribute_targets,
            occurrences=occurrences,
        )
        visitor.visit(module.tree)
    return tuple(occurrences)


class _OccurrenceVisitor(ast.NodeVisitor):
    """Traverse one module while retaining scope and TYPE_CHECKING context."""

    def __init__(
        self,
        *,
        authority: Authority,
        module: _Module,
        modules: Mapping[str, _Module],
        known: frozenset[str],
        closed_attribute_targets: frozenset[str],
        occurrences: list[ImportOccurrence],
    ) -> None:
        self.authority = authority
        self.module = module
        self.modules = modules
        self.known = known
        self.closed_attribute_targets = closed_attribute_targets
        self.occurrences = occurrences
        self.context = _EvaluationContext(module.tree, module.name)
        self.import_module_names, self.importlib_names, self.raw_import_names = _dynamic_aliases(module)
        self.scopes: list[str] = []
        self.type_checking_depth = 0

    def visit_If(self, node: ast.If) -> None:
        is_type_checking = _is_type_checking_guard(node.test)
        self.visit(node.test)
        if is_type_checking:
            self.type_checking_depth += 1
        for statement in node.body:
            self.visit(statement)
        if is_type_checking:
            self.type_checking_depth -= 1
        for statement in node.orelse:
            self.visit(statement)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node)

    def _visit_scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        self.scopes.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.scopes.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if _is_first_party(alias.name, self.authority.root_names):
                self._record(alias.name, (), node.lineno, self._static_form())

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        target = _resolve_from(self.module.name, self.module.is_package, node.level, node.module)
        if target is None or not _is_first_party(target, self.authority.root_names):
            return
        for alias in node.names:
            child = f"{target}.{alias.name}"
            if alias.name != "*" and _is_package(target, self.modules, self.authority.root_names) and child in self.known:
                self._record(child, (), node.lineno, self._static_form())
            else:
                self._record(target, (alias.name,), node.lineno, self._static_form())

    def visit_Call(self, node: ast.Call) -> None:
        qualified = _qualified_name(node.func)
        is_import_module = qualified in self.import_module_names or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in self.importlib_names
        )
        is_raw_import = qualified in self.raw_import_names or qualified in {"__import__", "builtins.__import__"}
        if is_import_module or is_raw_import:
            target_node = (
                node.args[0]
                if node.args
                else next((keyword.value for keyword in node.keywords if keyword.arg == "name"), None)
            )
            if target_node is not None:
                targets = self.context.values_for(target_node, node.lineno)
                if targets is None or not targets:
                    targets = _metadata_target_set_targets(
                        target_node,
                        node.lineno,
                        self.module,
                        self.context,
                        self.authority.repository,
                    )
                if targets is None or not targets:
                    targets = _computed_attribute_targets(
                        target_node,
                        node.lineno,
                        self.context,
                        self.closed_attribute_targets,
                    )
                for target in sorted(targets or ()):
                    resolved = _dynamic_target(self.module, target, node, self.context)
                    if resolved and resolved in self.known and _is_first_party(resolved, self.authority.root_names):
                        self._record(resolved, (), node.lineno, "dynamic")
        self.generic_visit(node)

    def _static_form(self) -> str:
        if self.type_checking_depth:
            return "type_checking"
        return "local" if self.scopes else "static"

    def _record(self, target: str, symbols: tuple[str, ...], lineno: int, import_form: str) -> None:
        lexical_scope = ".".join(self.scopes) if self.scopes else "<module>"
        for contract in self.authority.forbidden_contracts:
            if not _matches_any_module(self.module.name, contract.source_modules):
                continue
            if _matches_any_module(self.module.name, contract.forbidden_modules):
                continue
            if not _matches_any_module(target, contract.forbidden_modules):
                continue
            fingerprint = import_occurrence_fingerprint(
                source_module=self.module.name,
                target_module=target,
                imported_symbols=symbols,
                import_form=import_form,
                lexical_scope=lexical_scope,
                contract=contract.key,
            )
            self.occurrences.append(
                ImportOccurrence(
                    fingerprint=fingerprint,
                    source_module=self.module.name,
                    target_module=target,
                    imported_symbols=tuple(sorted(symbols)),
                    import_form=import_form,
                    lexical_scope=lexical_scope,
                    contract=contract.key,
                    path=self.module.path,
                    lineno=lineno,
                )
            )
        source_lane = _adapter_lane(self.module.name)
        target_lane = _adapter_lane(target)
        if source_lane is not None and target_lane is not None and source_lane != target_lane:
            contract = "advisory:adapter-top-level-coupling"
            fingerprint = import_occurrence_fingerprint(
                source_module=self.module.name,
                target_module=target,
                imported_symbols=symbols,
                import_form=import_form,
                lexical_scope=lexical_scope,
                contract=contract,
            )
            self.occurrences.append(
                ImportOccurrence(
                    fingerprint=fingerprint,
                    source_module=self.module.name,
                    target_module=target,
                    imported_symbols=tuple(sorted(symbols)),
                    import_form=import_form,
                    lexical_scope=lexical_scope,
                    contract=contract,
                    path=self.module.path,
                    lineno=lineno,
                )
            )


def _is_type_checking_guard(node: ast.AST) -> bool:
    """Recognize the conventional static-only import guard."""
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    if isinstance(node, ast.Attribute):
        return node.attr == "TYPE_CHECKING"
    if isinstance(node, ast.BoolOp):
        return any(_is_type_checking_guard(value) for value in node.values)
    return False


def _matches_any_module(module: str, prefixes: Sequence[str]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _adapter_lane(module: str) -> str | None:
    """Return the top-level adapter namespace without asserting peer legality."""
    prefix = "cadrumo.adapters."
    if not module.startswith(prefix):
        return None
    tail = module.removeprefix(prefix)
    return tail.partition(".")[0] or None


def import_occurrence_fingerprint(
    *,
    source_module: str,
    target_module: str,
    imported_symbols: Sequence[str],
    import_form: str,
    lexical_scope: str,
    contract: str,
) -> str:
    """Return the stable identity of one occurrence-contract record."""
    identity = {
        "contract": contract,
        "import_form": import_form,
        "imported_symbols": sorted(imported_symbols),
        "lexical_scope": lexical_scope,
        "source_module": source_module,
        "target_module": target_module,
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(UTF_8)).hexdigest()


def _module_name(path: Path, root: RootPackage) -> str:
    relative = path.relative_to(root.source_root)
    parts = list(relative.parts)
    if parts[-1] == "__init__.py":
        parts.pop()
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def _collect_bindings(module: _Module, root_names: frozenset[str]) -> None:
    imported_names: set[str] = set()
    for node in _iter_binding_statements(module.tree.body):
        if isinstance(node, ast.Import):
            module.has_imports = True
            for alias in node.names:
                local = alias.asname or alias.name.split(".", 1)[0]
                module.bindings[local] = _Binding("import", target=alias.name)
                imported_names.add(local)
                if _is_first_party(alias.name, root_names):
                    module.imported_count += 1
        elif isinstance(node, ast.ImportFrom):
            module.has_imports = True
            target = _resolve_from(module.name, module.is_package, node.level, node.module)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                kind = "import" if target is not None and _is_first_party(target, root_names) else "external-import"
                module.bindings[local] = _Binding(kind, target=target, imported_name=alias.name)
                imported_names.add(local)
                if kind == "import":
                    module.imported_count += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module.local_definitions += 1
            module.bindings[node.name] = _Binding("definition")
        elif isinstance(node, ast.Assign):
            kind = "alias" if _is_import_alias(node.value, imported_names) else "definition"
            for name in _assigned_names(node.targets):
                if name == "__all__":
                    continue
                module.bindings[name] = _Binding(kind)
                if kind == "definition":
                    module.local_definitions += 1
        elif isinstance(node, ast.AnnAssign):
            kind = "alias" if node.value is not None and _is_import_alias(node.value, imported_names) else "definition"
            for name in _assigned_names((node.target,)):
                if name == "__all__":
                    continue
                module.bindings[name] = _Binding(kind)
                if kind == "definition":
                    module.local_definitions += 1
        elif isinstance(node, ast.TypeAlias):
            module.local_definitions += 1
            module.bindings[node.name.id] = _Binding("definition")


def _iter_binding_statements(nodes: Iterable[ast.stmt]) -> Iterable[ast.stmt]:
    """Yield module-scope bindings from guarded and exception-handling blocks."""
    for node in nodes:
        yield node
        if isinstance(node, ast.If):
            yield from _iter_binding_statements((*node.body, *node.orelse))
        elif isinstance(node, ast.Try):
            yield from _iter_binding_statements(node.body)
            for handler in node.handlers:
                yield from _iter_binding_statements(handler.body)
            yield from _iter_binding_statements(node.orelse)
            yield from _iter_binding_statements(node.finalbody)


def _assigned_names(targets: Iterable[ast.expr]) -> tuple[str, ...]:
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.extend(_assigned_names(target.elts))
    return tuple(names)


def _is_import_alias(node: ast.AST, imported: set[str]) -> bool:
    """Return true for a direct imported-name or imported-attribute alias."""
    if isinstance(node, ast.Name):
        return node.id in imported
    if isinstance(node, ast.Attribute):
        return _is_import_alias(node.value, imported)
    return False


def _check_initializers(authority: Authority, modules: Mapping[str, _Module], findings: list[Finding]) -> None:
    del authority
    for module in modules.values():
        if not module.is_package:
            continue
        for node in module.tree.body:
            if _is_allowed_initializer_node(module.tree, node):
                continue
            findings.append(
                Finding(
                    "ACTIVE_INITIALIZER",
                    "package initializer must contain only documentation, future imports, pass, or empty __all__",
                    module.path,
                    getattr(node, "lineno", None),
                )
            )


def _is_allowed_initializer_node(tree: ast.Module, node: ast.stmt) -> bool:
    if _is_docstring_node(tree, node) or isinstance(node, ast.Pass):
        return True
    if isinstance(node, ast.ImportFrom) and node.module == "__future__":
        return True
    return _is_empty_all_assignment(node)


def _is_docstring_node(tree: ast.Module, node: ast.stmt) -> bool:
    return bool(
        tree.body
        and tree.body[0] is node
        and isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_empty_all_assignment(node: ast.stmt) -> bool:
    if isinstance(node, ast.Assign):
        names = _assigned_names(node.targets)
        value: ast.expr | None = node.value
    elif isinstance(node, ast.AnnAssign):
        names = _assigned_names((node.target,))
        value = node.value
    else:
        return False
    return names == ("__all__",) and isinstance(value, (ast.Tuple, ast.List)) and not value.elts


def _check_static_imports(authority: Authority, modules: Mapping[str, _Module], findings: list[Finding]) -> None:
    known = frozenset((*modules, *authority.root_packages))
    root_names = authority.root_names
    for module in modules.values():
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    if _names_dunder_init_submodule(target):
                        findings.append(
                            Finding(
                                "DUNDER_INIT_SUBMODULE",
                                "do not import a package through a submodule named __init__",
                                module.path,
                                node.lineno,
                            )
                        )
                    if not _is_first_party(target, root_names):
                        continue
                    _check_absolute_spelling(module, target, node, findings)
                    _check_private(module, target, alias.name, modules, authority, findings, node.lineno)
                    if target not in known:
                        findings.append(
                            Finding(
                                "STATIC_TARGET_UNRESOLVED",
                                f"first-party import target {target!r} does not exist",
                                module.path,
                                node.lineno,
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                target = _resolve_from(module.name, module.is_package, node.level, node.module)
                if _names_dunder_init_submodule(node.module or ""):
                    findings.append(
                        Finding(
                            "DUNDER_INIT_SUBMODULE",
                            "do not import a package through a submodule named __init__",
                            module.path,
                            node.lineno,
                        )
                    )
                if target is None:
                    findings.append(
                        Finding(
                            "UNSUPPORTED_IMPORT",
                            "relative import escapes its configured package root",
                            module.path,
                            node.lineno,
                        )
                    )
                    continue
                if not _is_first_party(target, root_names):
                    continue
                _check_absolute_spelling(module, target, node, findings)
                if target not in known:
                    findings.append(
                        Finding(
                            "STATIC_TARGET_UNRESOLVED",
                            f"first-party import target {target!r} does not exist",
                            module.path,
                            node.lineno,
                        )
                    )
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        findings.append(
                            Finding(
                                "UNSUPPORTED_IMPORT",
                                "wildcard first-party imports cannot prove a canonical home",
                                module.path,
                                node.lineno,
                            )
                        )
                        continue
                    child = f"{target}.{alias.name}"
                    if _is_package(target, modules, root_names) and child in known:
                        _check_private(module, child, alias.name, modules, authority, findings, node.lineno)
                        continue
                    _check_private(module, target, alias.name, modules, authority, findings, node.lineno)
                    target_module = modules.get(target)
                    if target_module is None:
                        continue
                    if target_module.is_package or target in root_names:
                        findings.append(
                            Finding(
                                "PACKAGE_FACADE",
                                f"symbol {alias.name!r} is consumed from package facade {target!r}",
                                module.path,
                                node.lineno,
                            )
                        )
                        continue
                    binding = target_module.bindings.get(alias.name)
                    if binding is None:
                        findings.append(
                            Finding(
                                "CANONICAL_TARGET_MISSING",
                                f"{target!r} does not define imported symbol {alias.name!r}",
                                module.path,
                                node.lineno,
                            )
                        )
                    elif binding.kind in {"import", "alias", "external-import"}:
                        category = (
                            "FORWARDING_MODULE"
                            if target_module.local_definitions == 0 and target_module.has_imports
                            else "REEXPORT_OR_ALIAS"
                        )
                        findings.append(
                            Finding(
                                category,
                                f"{target}.{alias.name} is not a canonical defining-module symbol",
                                module.path,
                                node.lineno,
                            )
                        )


def _check_absolute_spelling(
    module: _Module, target: str, node: ast.Import | ast.ImportFrom, findings: list[Finding]
) -> None:
    """Require relative spelling only inside the ``cadrumo`` distribution root."""
    is_absolute = isinstance(node, ast.Import) or node.level == 0
    in_cadrumo = module.name == "cadrumo" or module.name.startswith("cadrumo.")
    if is_absolute and in_cadrumo and (target == "cadrumo" or target.startswith("cadrumo.")):
        findings.append(
            Finding(
                "ABSOLUTE_INTRA_CADRUMO",
                f"absolute canonical import of {target!r}; relative spelling is optional style",
                module.path,
                node.lineno,
                advisory=True,
            )
        )


def _names_dunder_init_submodule(dotted: str) -> bool:
    """Recognise the spelling that addresses ``package.__init__`` itself."""
    return dotted == "__init__" or dotted.endswith(".__init__")


def _check_private(
    module: _Module,
    target: str,
    imported_name: str,
    modules: Mapping[str, _Module],
    authority: Authority,
    findings: list[Finding],
    lineno: int,
) -> None:
    components = target.split(".")
    private_index = next(
        (
            index
            for index, component in enumerate(components)
            if component.startswith("_") and component not in {"__init__"}
        ),
        None,
    )
    if private_index is not None:
        owner = ".".join(components[:private_index])
        if not _is_descendant(module.name, owner):
            findings.append(
                Finding(
                    "PRIVATE_CROSS_PACKAGE",
                    f"{module.name!r} reaches private module {target!r}",
                    module.path,
                    lineno,
                )
            )
    if imported_name.startswith("_") and not imported_name.startswith("__"):
        owner = _module_package(target, modules, authority.root_names)
        if owner and not _is_descendant(module.name, owner):
            findings.append(
                Finding(
                    "PRIVATE_CROSS_PACKAGE",
                    f"{module.name!r} reaches private symbol {imported_name!r}",
                    module.path,
                    lineno,
                )
            )


def _module_package(name: str, modules: Mapping[str, _Module], root_names: frozenset[str]) -> str:
    parts = name.split(".")
    for index in range(len(parts), 0, -1):
        candidate = ".".join(parts[:index])
        if candidate in root_names:
            return candidate
        record = modules.get(candidate)
        if record is not None and record.is_package:
            return candidate
    return name.rpartition(".")[0]


def _is_descendant(module: str, owner: str) -> bool:
    return bool(owner) and (module == owner or module.startswith(f"{owner}."))


def _is_package(name: str, modules: Mapping[str, _Module], root_names: frozenset[str]) -> bool:
    return name in root_names or (name in modules and modules[name].is_package)


def _check_dynamic_imports(
    authority: Authority,
    modules: Mapping[str, _Module],
    findings: list[Finding],
    closed_attribute_targets: frozenset[str],
) -> None:
    known = frozenset((*modules, *authority.root_packages))
    for module in modules.values():
        context = _EvaluationContext(module.tree, module.name)
        import_module_names, importlib_names, raw_import_names = _dynamic_aliases(module)
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.Call):
                continue
            qualified = _qualified_name(node.func)
            is_import_module = qualified in import_module_names or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in importlib_names
            )
            is_raw_import = qualified in raw_import_names or qualified in {"__import__", "builtins.__import__"}
            if not (is_import_module or is_raw_import):
                continue
            target_node = (
                node.args[0]
                if node.args
                else next(
                    (keyword.value for keyword in node.keywords if keyword.arg == "name"),
                    None,
                )
            )
            if target_node is None:
                findings.append(
                    Finding(
                        "UNSUPPORTED_DYNAMIC",
                        "dynamic import has no module target argument",
                        module.path,
                        node.lineno,
                    )
                )
                continue
            targets = context.values_for(target_node, node.lineno)
            metadata_backed = False
            if targets is None or not targets:
                targets = _metadata_target_set_targets(target_node, node.lineno, module, context, authority.repository)
                metadata_backed = targets is not None
            computed_projection = metadata_backed
            if targets is None or not targets:
                targets = _computed_attribute_targets(target_node, node.lineno, context, closed_attribute_targets)
                computed_projection = targets is not None
            if targets is None or not targets:
                findings.append(
                    Finding(
                        "UNRESOLVED_DYNAMIC_TARGET",
                        "computed dynamic import is not a finite closed target set",
                        module.path,
                        node.lineno,
                    )
                )
                continue
            for target in sorted(targets):
                resolved = _dynamic_target(module, target, node, context)
                if resolved is None or not resolved:
                    findings.append(
                        Finding(
                            "UNRESOLVED_DYNAMIC_TARGET",
                            f"dynamic target {target!r} cannot be resolved",
                            module.path,
                            node.lineno,
                        )
                    )
                    continue
                if is_raw_import:
                    if _is_first_party(resolved, authority.root_names):
                        findings.append(
                            Finding(
                                "RAW_FIRST_PARTY_IMPORT",
                                f"raw __import__ loads first-party target {resolved!r}",
                                module.path,
                                node.lineno,
                            )
                        )
                    continue
                if not _is_first_party(resolved, authority.root_names):
                    continue
                in_cadrumo = module.name == "cadrumo" or module.name.startswith("cadrumo.")
                if (
                    in_cadrumo
                    and not computed_projection
                    and not target.startswith(".")
                    and _is_first_party(resolved, frozenset({"cadrumo"}))
                ):
                    findings.append(
                        Finding(
                            "ABSOLUTE_INTRA_CADRUMO",
                            f"absolute canonical dynamic target {resolved!r}; relative spelling is optional style",
                            module.path,
                            node.lineno,
                            advisory=True,
                        )
                    )
                _check_private(module, resolved, resolved.rsplit(".", 1)[-1], modules, authority, findings, node.lineno)
                if resolved not in known:
                    findings.append(
                        Finding(
                            "DYNAMIC_TARGET_UNRESOLVED",
                            f"first-party dynamic target {resolved!r} does not exist",
                            module.path,
                            node.lineno,
                        )
                    )


def _closed_attribute_targets(
    modules: Mapping[str, _Module], root_names: frozenset[str], known: frozenset[str]
) -> frozenset[str]:
    """Derive the finite module values carried by object ``.module`` fields.

    The product's outer resolvers pass immutable target records into
    ``import_module`` rather than keeping a second import map beside the
    declarations.  A checker that only evaluates bare strings would therefore
    mistake ``import_module(target.module)`` for an open computation.  Harvest
    the literal constructor values that can populate a module field, resolving
    relative values against the constructor's explicit package argument.  This
    is a closed set derived from source, not an allowlist: an unknown or
    unbounded constructor expression contributes nothing and remains a finding.
    """
    targets: set[str] = set()
    module_record_classes = _module_record_classes(modules)
    for module in modules.values():
        context = _EvaluationContext(module.tree, module.name)
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_module_record_constructor(module, node, module_record_classes):
                continue
            module_node = _constructor_argument(node, "module", positional_index=0)
            if module_node is None:
                continue
            values = context.values_for(module_node, node.lineno)
            if values is None:
                continue
            package_node = _constructor_argument(node, "package", positional_index=2)
            for value in values:
                resolved = _resolve_constructor_target(module, value, package_node, node, context)
                if resolved is None or not _is_first_party(resolved, root_names) or resolved not in known:
                    continue
                targets.add(resolved)
                if len(targets) > _MAX_CLOSED_DYNAMIC_TARGETS:
                    return frozenset()
    return frozenset(targets)


def _module_record_classes(modules: Mapping[str, _Module]) -> frozenset[str]:
    """Find record classes that declare a ``module`` field."""
    classes: set[str] = set()
    for module in modules.values():
        for node in module.tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            fields = {
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            }
            fields.update(
                item.targets[0].id
                for item in node.body
                if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name)
            )
            if "module" in fields:
                classes.add(f"{module.name}.{node.name}")
    return frozenset(classes)


def _is_module_record_constructor(module: _Module, call: ast.Call, module_record_classes: frozenset[str]) -> bool:
    """Return whether a call names a locally or explicitly imported module record."""
    if not isinstance(call.func, ast.Name):
        return False
    local_name = call.func.id
    if f"{module.name}.{local_name}" in module_record_classes:
        return True
    binding = module.bindings.get(local_name)
    if binding is None or binding.target is None or binding.imported_name is None:
        return False
    return f"{binding.target}.{binding.imported_name}" in module_record_classes


def _constructor_argument(node: ast.Call, name: str, *, positional_index: int) -> ast.AST | None:
    """Return one constructor field expression without naming a product class."""
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return node.args[positional_index] if len(node.args) > positional_index else None


def _resolve_constructor_target(
    module: _Module,
    value: str,
    package_node: ast.AST | None,
    call: ast.Call,
    context: _EvaluationContext,
) -> str | None:
    """Resolve one literal constructor module value, or reject it as open."""
    if not value.startswith("."):
        return value
    if package_node is None:
        return None
    if isinstance(package_node, ast.Name) and package_node.id == "__package__":
        package = module.name if module.is_package else module.name.rpartition(".")[0]
    else:
        package_values = context.values_for(package_node, call.lineno)
        if package_values is None or len(package_values) != 1:
            return None
        package = next(iter(package_values))
    level = len(value) - len(value.lstrip("."))
    remainder = value[level:] or None
    return _resolve_from(package, True, level, remainder)


def _computed_attribute_targets(
    target_node: ast.AST,
    lineno: int,
    context: _EvaluationContext,
    closed_attribute_targets: frozenset[str],
) -> frozenset[str] | None:
    """Return the closed set for a projected module field, if one exists."""
    if isinstance(target_node, ast.Attribute) and target_node.attr == "module" and closed_attribute_targets:
        return closed_attribute_targets
    if isinstance(target_node, ast.Name) and closed_attribute_targets:
        scope = context._nearest_function(target_node)
        assignments = context._latest_values(target_node.id, lineno, scope)
        if assignments and any(
            _is_module_projection_expression(assignment.value, context, lineno, scope, set())
            for assignment in assignments
        ):
            return closed_attribute_targets
    return None


def _metadata_target_set_targets(
    target_node: ast.AST,
    lineno: int,
    module: _Module,
    context: _EvaluationContext,
    repository: Path,
) -> frozenset[str] | None:
    """Resolve a generic declared-metadata target-set loader call.

    The loader's checked-in JSON is the finite authority.  This deliberately
    recognises the reusable loader origin rather than a caller, artifact path,
    or target-set name, so any governed module can use a declared inventory.
    """
    targets: set[str] = set()
    resolved_any = False
    for candidate in _metadata_target_set_candidate_nodes(target_node, lineno, context, set()):
        if not isinstance(candidate, ast.Call):
            continue
        loader = _metadata_target_set_loader(module, candidate.func)
        if loader is None:
            continue
        path_node = _call_argument(candidate, "metadata_path", positional_index=0)
        paths = context.values_for(path_node, candidate.lineno)
        if paths is None:
            return None
        resolved_any = True
        try:
            for path in paths:
                if loader == "all":
                    targets.update(load_all_target_sets(path, repository=repository))
                else:
                    set_node = _call_argument(candidate, "target_set", positional_index=1)
                    names = context.values_for(set_node, candidate.lineno)
                    if names is None:
                        return None
                    for name in names:
                        targets.update(load_target_set(path, name, repository=repository))
        except MetadataTargetSetError:
            return None
        if len(targets) > _MAX_CLOSED_DYNAMIC_TARGETS:
            return None
    return frozenset(targets) if resolved_any and targets else None


def _metadata_target_set_candidate_nodes(
    node: ast.AST,
    lineno: int,
    context: _EvaluationContext,
    resolving: set[tuple[int, str]],
) -> Iterable[ast.AST]:
    """Yield *node* and the finite assignment chain that can name its loader call."""
    yield node
    if not isinstance(node, ast.Name):
        return
    scope = context._nearest_function(node)
    key = (id(scope) if scope is not None else 0, node.id)
    if key in resolving:
        return
    assignments = context._latest_values(node.id, lineno, scope)
    if not assignments:
        return
    resolving.add(key)
    for assignment in assignments:
        yield from _metadata_target_set_candidate_nodes(assignment.value, assignment.lineno - 1, context, resolving)
    resolving.remove(key)


def _call_argument(node: ast.Call, name: str, *, positional_index: int) -> ast.AST | None:
    """Return a named or positional call argument without caller-specific syntax."""
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return node.args[positional_index] if len(node.args) > positional_index else None


def _metadata_target_set_loader(module: _Module, function: ast.AST) -> str | None:
    """Return the generic metadata loader kind resolved by *function*."""
    qualified = _qualified_name(function)
    if qualified is None:
        return None
    expected = {
        "cadrumo.tests.module_target_inventory.load_all_target_sets": "all",
        "cadrumo.tests.module_target_inventory.load_target_set": "named",
    }
    if qualified in expected:
        return expected[qualified]
    head, separator, tail = qualified.partition(".")
    binding = module.bindings.get(head)
    if binding is None or binding.target is None:
        return None
    if not separator:
        resolved = f"{binding.target}.{binding.imported_name}"
    else:
        resolved = f"{binding.target}.{tail}"
    return expected.get(resolved)


def _is_module_projection_expression(
    node: ast.AST,
    context: _EvaluationContext,
    lineno: int,
    scope: ast.AST | None,
    resolving: set[str],
) -> bool:
    """Recognise a finite expression that projects target records' module fields."""
    if isinstance(node, (ast.SetComp, ast.ListComp, ast.GeneratorExp)):
        return isinstance(node.elt, ast.Attribute) and node.elt.attr == "module"
    if isinstance(node, ast.Name) and node.id not in resolving:
        assignments = context._latest_values(node.id, lineno, scope)
        if assignments:
            resolving.add(node.id)
            result = any(
                _is_module_projection_expression(assignment.value, context, lineno, scope, resolving)
                for assignment in assignments
            )
            resolving.remove(node.id)
            return result
    return False


def _dynamic_aliases(module: _Module) -> tuple[set[str], set[str], set[str]]:
    import_module_names = {"importlib.import_module"}
    importlib_names = {"importlib"}
    raw_import_names = {"builtins.__import__", "__import__"}
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".", 1)[0]
                if alias.name == "importlib":
                    importlib_names.add(local)
                elif alias.name == "importlib.import_module" and alias.asname:
                    import_module_names.add(local)
                elif alias.name == "builtins":
                    raw_import_names.add(f"{local}.__import__")
                elif alias.name == "builtins.__import__" and alias.asname:
                    raw_import_names.add(local)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module == "importlib":
                for alias in node.names:
                    if alias.name == "*":
                        import_module_names.add("import_module")
                    elif alias.name == "import_module":
                        import_module_names.add(alias.asname or alias.name)
            elif node.module == "builtins":
                for alias in node.names:
                    if alias.name == "*":
                        raw_import_names.add("__import__")
                    elif alias.name == "__import__":
                        raw_import_names.add(alias.asname or alias.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if value is None:
                continue
            qualified = _qualified_name(value)
            for local in _assigned_names(node.targets if isinstance(node, ast.Assign) else (node.target,)):
                if qualified == "importlib" or qualified in importlib_names:
                    importlib_names.add(local)
                if qualified == "builtins":
                    raw_import_names.add(f"{local}.__import__")
                if (
                    qualified == "importlib.import_module"
                    or qualified in import_module_names
                    or (
                        isinstance(value, ast.Attribute)
                        and value.attr == "import_module"
                        and isinstance(value.value, ast.Name)
                        and value.value.id in importlib_names
                    )
                ):
                    import_module_names.add(local)
                if qualified == "builtins.__import__" or qualified in raw_import_names:
                    raw_import_names.add(local)
    return import_module_names, importlib_names, raw_import_names


def _dynamic_target(module: _Module, target: str, call: ast.Call, context: _EvaluationContext) -> str | None:
    if not target.startswith("."):
        return target
    package_node = next((keyword.value for keyword in call.keywords if keyword.arg == "package"), None)
    if package_node is None and len(call.args) > 1:
        package_node = call.args[1]
    if isinstance(package_node, ast.Name) and package_node.id == "__package__":
        package = module.name if module.is_package else module.name.rpartition(".")[0]
    else:
        package_values = context.values_for(package_node, call.lineno)
        if package_values is None or len(package_values) != 1:
            return None
        package = next(iter(package_values))
    level = len(target) - len(target.lstrip("."))
    remainder = target[level:] or None
    return _resolve_from(package, True, level, remainder)


def _is_first_party(name: str, root_names: frozenset[str]) -> bool:
    return any(name == root or name.startswith(f"{root}.") for root in root_names)


def _resolve_from(importer: str, importer_is_package: bool, level: int, module: str | None) -> str | None:
    if level == 0:
        return module
    parts = importer.split(".")
    base = parts if importer_is_package else parts[:-1]
    strip = level - 1
    if strip > len(base):
        return None
    if strip:
        base = base[: len(base) - strip]
    if module:
        return ".".join((*base, *module.split(".")))
    return ".".join(base) if base else None


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _qualified_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


@dataclass(frozen=True)
class _Assignment:
    lineno: int
    value: ast.AST
    projection: tuple[int, ...] = ()
    unpack: bool = False


class _EvaluationContext:
    """Conservative finite-string evaluator for dynamic import arguments."""

    def __init__(self, tree: ast.Module, module_name: str | None = None) -> None:
        self._module_name = module_name
        self._parents: dict[int, ast.AST] = {}
        self._module_assignments: dict[str, list[_Assignment]] = {}
        self._function_assignments: dict[int, dict[str, list[_Assignment]]] = {}
        self._function_params: dict[int, set[str]] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self._parents[id(child)] = parent
        self._collect_assignments(tree)

    def _collect_assignments(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                self._function_assignments[id(node)] = {}
                arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
                self._function_params[id(node)] = {argument.arg for argument in arguments}
                if node.args.vararg:
                    self._function_params[id(node)].add(node.args.vararg.arg)
                if node.args.kwarg:
                    self._function_params[id(node)].add(node.args.kwarg.arg)
            if isinstance(node, ast.Assign):
                self._save_assignment(node.targets, node.value, node)
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                self._save_assignment((node.target,), node.value, node)
            elif isinstance(node, ast.For):
                self._save_assignment((node.target,), node.iter, node, unpack=True)

    def _save_assignment(
        self, targets: Iterable[ast.expr], value: ast.AST, node: ast.AST, *, unpack: bool = False
    ) -> None:
        scope = self._nearest_function(node)
        target_map = self._module_assignments if scope is None else self._function_assignments.setdefault(id(scope), {})
        for target in targets:
            self._save_target_assignment(target_map, target, value, node, unpack=unpack)

    def _save_target_assignment(
        self,
        target_map: dict[str, list[_Assignment]],
        target: ast.expr,
        value: ast.AST,
        node: ast.AST,
        *,
        unpack: bool,
    ) -> None:
        if isinstance(target, ast.Name):
            target_map.setdefault(target.id, []).append(_Assignment(getattr(node, "lineno", 0), value, unpack=unpack))
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for index, element in enumerate(target.elts):
                self._save_target_projection(target_map, element, value, node, (index,), unpack=unpack)

    def _save_target_projection(
        self,
        target_map: dict[str, list[_Assignment]],
        target: ast.expr,
        value: ast.AST,
        node: ast.AST,
        projection: tuple[int, ...],
        *,
        unpack: bool,
    ) -> None:
        if isinstance(target, ast.Name):
            target_map.setdefault(target.id, []).append(
                _Assignment(getattr(node, "lineno", 0), value, projection, unpack)
            )
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for index, element in enumerate(target.elts):
                self._save_target_projection(target_map, element, value, node, (*projection, index), unpack=unpack)

    def _nearest_function(self, node: ast.AST) -> ast.AST | None:
        parent = self._parents.get(id(node))
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return parent
            parent = self._parents.get(id(parent))
        return None

    def values_for(self, node: ast.AST | None, lineno: int) -> frozenset[str] | None:
        if node is None:
            return None
        return self._values(node, lineno, set(), self._nearest_function(node))

    def _values(
        self,
        node: ast.AST,
        lineno: int,
        resolving: set[tuple[int, str]],
        scope: ast.AST | None,
    ) -> frozenset[str] | None:
        if isinstance(node, ast.Constant):
            value = node.value
            return frozenset({value}) if isinstance(value, str) else None
        if isinstance(node, ast.Name):
            if node.id == "__name__" and self._module_name is not None:
                return frozenset({self._module_name})
            key = (id(scope) if scope is not None else 0, node.id)
            if key in resolving:
                return None
            assignments = self._latest_values(node.id, lineno, scope)
            if assignments is None:
                return None
            resolving.add(key)
            result: set[str] = set()
            for assignment in assignments:
                if assignment.unpack:
                    evaluated = self._unpacked_values(
                        assignment.value,
                        assignment.projection,
                        assignment.lineno - 1,
                        resolving,
                        scope,
                    )
                elif assignment.projection:
                    evaluated = self._values_at_indices(
                        assignment.value,
                        assignment.projection,
                        assignment.lineno - 1,
                        resolving,
                        scope,
                    )
                else:
                    evaluated = self._values(assignment.value, assignment.lineno - 1, resolving, scope)
                if evaluated is None:
                    resolving.remove(key)
                    return None
                result.update(evaluated)
            resolving.remove(key)
            return _bounded(result)
        if isinstance(node, ast.JoinedStr):
            values: frozenset[str] | None = frozenset({""})
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    pieces = frozenset({part.value})
                elif isinstance(part, ast.FormattedValue) and part.format_spec is None and part.conversion == -1:
                    pieces = self._values(part.value, lineno, resolving, scope)
                else:
                    return None
                values = _combine(values, pieces)
                if values is None:
                    return None
            return values
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return _combine(
                self._values(node.left, lineno, resolving, scope),
                self._values(node.right, lineno, resolving, scope),
            )
        if isinstance(node, ast.IfExp):
            return _union(
                self._values(node.body, lineno, resolving, scope),
                self._values(node.orelse, lineno, resolving, scope),
            )
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            result: set[str] = set()
            for element in node.elts:
                evaluated = self._values(element, lineno, resolving, scope)
                if evaluated is None:
                    return None
                result.update(evaluated)
            return _bounded(result)
        if isinstance(node, ast.Subscript):
            values = self._sequence_values(node.value, lineno, resolving, scope)
            if values is None:
                return None
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                try:
                    return frozenset({values[node.slice.value]})
                except IndexError:
                    return None
            return frozenset(values)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            bases = self._values(node.func.value, lineno, resolving, scope)
            if bases is None:
                return None
            positional: list[frozenset[str]] = []
            for argument in node.args:
                values = self._values(argument, lineno, resolving, scope)
                if values is None:
                    return None
                positional.append(values)
            keyword_names: list[str] = []
            keyword_values: list[frozenset[str]] = []
            for keyword in node.keywords:
                if keyword.arg is None:
                    return None
                values = self._values(keyword.value, lineno, resolving, scope)
                if values is None:
                    return None
                keyword_names.append(keyword.arg)
                keyword_values.append(values)
            result: set[str] = set()
            for base in bases:
                for values in _products(positional):
                    for named in _products(keyword_values):
                        try:
                            result.add(base.format(*values, **dict(zip(keyword_names, named, strict=True))))
                        except (IndexError, KeyError, ValueError):
                            return None
            return _bounded(result)
        return None

    def _unpacked_values(
        self,
        node: ast.AST,
        projection: tuple[int, ...],
        lineno: int,
        resolving: set[tuple[int, str]],
        scope: ast.AST | None,
    ) -> frozenset[str] | None:
        """Evaluate a finite iterable assignment made by tuple unpacking."""
        elements = self._sequence_nodes(node, lineno, resolving, scope)
        if elements is None:
            return None
        result: set[str] = set()
        for element in elements:
            values = self._values_at_indices(element, projection, lineno, resolving, scope)
            if values is None:
                return None
            result.update(values)
        return _bounded(result)

    def _values_at_indices(
        self,
        node: ast.AST,
        indexes: tuple[int, ...],
        lineno: int,
        resolving: set[tuple[int, str]],
        scope: ast.AST | None,
    ) -> frozenset[str] | None:
        """Evaluate one finite tuple/list/dict-items projection."""
        if not indexes:
            return self._values(node, lineno, resolving, scope)
        elements = self._sequence_nodes(node, lineno, resolving, scope)
        if elements is None or indexes[0] >= len(elements):
            return None
        return self._values_at_indices(elements[indexes[0]], indexes[1:], lineno, resolving, scope)

    def _sequence_nodes(
        self,
        node: ast.AST,
        lineno: int,
        resolving: set[tuple[int, str]],
        scope: ast.AST | None,
    ) -> tuple[ast.AST, ...] | None:
        if isinstance(node, (ast.Tuple, ast.List)):
            elements: list[ast.AST] = []
            for element in node.elts:
                if isinstance(element, ast.Starred):
                    expanded = self._sequence_nodes(element.value, lineno, resolving, scope)
                    if expanded is None:
                        return None
                    elements.extend(expanded)
                else:
                    elements.append(element)
            return tuple(elements)
        if isinstance(node, ast.Dict):
            if any(key is None for key in node.keys):
                return None
            return tuple(
                ast.Tuple(elts=[key, value], ctx=ast.Load()) for key, value in zip(node.keys, node.values, strict=True)
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "items":
            if node.args or node.keywords:
                return None
            return self._sequence_nodes(node.func.value, lineno, resolving, scope)
        if isinstance(node, ast.Name):
            key = (id(scope) if scope is not None else 0, node.id)
            if key in resolving:
                return None
            assignments = self._latest_values(node.id, lineno, scope)
            if not assignments:
                return None
            resolving.add(key)
            sequences: list[ast.AST] = []
            for assignment in assignments:
                if assignment.projection:
                    resolving.remove(key)
                    return None
                values = self._sequence_nodes(assignment.value, assignment.lineno - 1, resolving, scope)
                if values is None:
                    resolving.remove(key)
                    return None
                sequences.extend(values)
            resolving.remove(key)
            return tuple(sequences)
        return None

    def _sequence_values(
        self,
        node: ast.AST,
        lineno: int,
        resolving: set[tuple[int, str]],
        scope: ast.AST | None,
    ) -> tuple[str, ...] | None:
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            values: list[str] = []
            for element in node.elts:
                evaluated = self._values(element, lineno, resolving, scope)
                if evaluated is None:
                    return None
                values.extend(sorted(evaluated))
            return tuple(values)
        if isinstance(node, ast.Name):
            assignments = self._latest_values(node.id, lineno, scope)
            if not assignments:
                return None
            result: list[str] = []
            for assignment in assignments:
                values = self._sequence_values(assignment.value, assignment.lineno - 1, resolving, scope)
                if values is None:
                    return None
                result.extend(values)
            return tuple(result)
        return None

    def _latest_values(self, name: str, lineno: int, scope: ast.AST | None) -> tuple[_Assignment, ...] | None:
        if scope is not None:
            if name in self._function_params.get(id(scope), set()):
                return None
            local = tuple(
                assignment
                for assignment in self._function_assignments.get(id(scope), {}).get(name, ())
                if assignment.lineno <= lineno
            )
            if local:
                return local
        module = tuple(
            assignment for assignment in self._module_assignments.get(name, ()) if assignment.lineno <= lineno
        )
        return module or None


def _combine(left: frozenset[str] | None, right: frozenset[str] | None) -> frozenset[str] | None:
    if left is None or right is None:
        return None
    return _bounded({a + b for a, b in itertools.product(left, right)})


def _products(groups: Sequence[Iterable[str]]) -> tuple[tuple[str, ...], ...]:
    """Return a bounded Cartesian product for finite formatter arguments."""
    products: list[tuple[str, ...]] = [()]
    for group in groups:
        products = [(*prefix, value) for prefix in products for value in group]
        if len(products) > _MAX_ENUMERATED_VALUES:
            return ()
    return tuple(products)


def _union(left: frozenset[str] | None, right: frozenset[str] | None) -> frozenset[str] | None:
    if left is None or right is None:
        return None
    return _bounded(set(left) | set(right))


def _bounded(values: Iterable[str]) -> frozenset[str] | None:
    result = frozenset(values)
    return result if len(result) <= _MAX_ENUMERATED_VALUES else None


def has_architectural_warning(output: str) -> bool:
    """Return true when native Import Linter output names a warning/advisory."""
    for line in output.splitlines():
        lowered = line.strip().lower()
        if not lowered or lowered.startswith("no warning") or lowered.startswith("no advisory"):
            continue
        if re.search(r"\b(?:warnings?|advisories?)\s*[:=]\s*0\b", lowered):
            continue
        if re.search(r"\b(?:warning|warnings|advisory|advisories)\b", lowered):
            return True
    return False


def main(argv: Sequence[str] | None = None) -> int:
    """Run the internal subordinate component for diagnostics and isolation tests."""
    parser = argparse.ArgumentParser(
        description="Internal import-quality component; use just check-import-boundaries for the verdict."
    )
    parser.add_argument("--internal", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path, default=None, help="repository/source root to scan")
    parser.add_argument("--config", type=Path, default=None, help="Import Linter configuration path")
    parser.add_argument("--report", type=Path, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.internal:
        print("[INTERNAL_CHECKER] subordinate checker is internal; use just check-import-boundaries")
        return TOOL_BROKEN
    root = args.root or Path(os.environ.get("CADRUMO_IMPORT_GATE_ROOT", REPO_ROOT))
    try:
        read = read_authority(root, args.config)
    except Exception as exc:  # broad: direct component execution must fail closed
        print(f"[INTERNAL_CHECKER] authority preflight aborted: {exc}")
        return TOOL_BROKEN
    if read.authority is None:
        for finding in read.findings:
            print(finding)
        return TOOL_BROKEN
    result = check_authority(read.authority)
    if args.report is not None:
        args.report.write_text(
            json.dumps(result.as_dict(read.authority.repository), indent=2, sort_keys=True) + "\n",
            encoding=UTF_8,
            newline="\n",
        )
    for finding in read.findings:
        print(finding)
    if result.findings:
        rendered = result.render(read.authority.repository)
        if rendered:
            print(rendered)
    else:
        print(f"import-checker: scanned {result.files_scanned} governed Python file(s)")
    return TOOL_BROKEN if read.broken and result.returncode == 0 else result.returncode


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "Authority",
    "AuthorityRead",
    "CheckResult",
    "ForbiddenContract",
    "Finding",
    "ImportOccurrence",
    "RootPackage",
    "check_authority",
    "has_architectural_warning",
    "import_occurrence_fingerprint",
    "main",
    "read_authority",
]
