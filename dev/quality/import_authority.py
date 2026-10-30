"""Authority for the subordinate import checker."""

from __future__ import annotations

import configparser
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Final

from dev._paths import UTF_8
from dev.source_tree import repository_files

from .import_check_models import (
    Authority,
    AuthorityRead,
    ConsumerContractScope,
    ConsumerTree,
    ForbiddenContract,
    RootPackage,
)
from .import_root_candidates import inspect_root_base

_DOTTED_NAME: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


_LAYER_NAME: Final[re.Pattern[str]] = re.compile(r"^(?:\(([A-Za-z_]\w*)\)|([A-Za-z_]\w*))$")

#: Sections of the authority file that belong to the import gate rather than to
#: Import Linter, which reads only ``importlinter`` and ``importlinter:*``.
_GATE_SECTION_PREFIX: Final[str] = "import-gate:"
#: Repository-root directories or modules whose Python consumes first-party
#: roots without being importable packages; the checker governs their imports.
_CONSUMER_TREES_SECTION: Final[str] = "import-gate:consumer-trees"
#: Repository-root directories or modules holding Python that is deliberately
#: outside the gate.  This section is the only place such an exclusion exists.
_EXCLUDED_TREES_SECTION: Final[str] = "import-gate:excluded-trees"
#: ``import-gate:consumer-contract:<forbidden contract key>`` holds consumer
#: paths to that Import Linter contract's forbidden modules.
_CONSUMER_CONTRACT_PREFIX: Final[str] = "import-gate:consumer-contract:"
#: The directory holding source-layout roots; its contents are inspected as roots.
_SOURCE_CONTAINER: Final[str] = "src"
_PYTHON_SUFFIX: Final[str] = ".py"


def _validate_root_declarations(
    section: Mapping[str, str], root_packages: tuple[str, ...], findings: list[str]
) -> None:
    """Validate root declarations."""
    if not root_packages:
        findings.append("[UNCLASSIFIED_ROOT] Import Linter declares no root_packages")
    if _truthy(section.get("exclude_type_checking_imports", "false")):
        findings.append("[AUTHORITY_CONFIG] Import Linter excludes TYPE_CHECKING imports from its graph")
    if len(root_packages) != len(set(root_packages)):
        findings.append("[AUTHORITY_CONFIG] Import Linter root_packages contains duplicates")
    for package in root_packages:
        if not _DOTTED_NAME.fullmatch(package):
            findings.append(f"[UNCLASSIFIED_ROOT] invalid first-party root name {package!r}")


def _locate_declared_roots(repository: Path, root_packages: tuple[str, ...], findings: list[str]) -> list[RootPackage]:
    """Locate declared roots."""
    roots: list[RootPackage] = []
    for package in root_packages:
        located = _locate_root(repository, package)
        if located is None:
            findings.append(f"[UNCLASSIFIED_ROOT] declared root {package!r} has no Python source directory")
        else:
            roots.append(RootPackage(package, located))

    _check_root_overlaps(roots, findings)
    return roots


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

    _validate_root_declarations(section, root_packages, findings)

    roots = _locate_declared_roots(repository, root_packages, findings)

    classifications: list[tuple[str, tuple[str, ...]]] = []
    forbidden_contracts: list[ForbiddenContract] = []
    classified_containers: set[str] = set()
    for name in parser.sections():
        _read_contract_classification(
            name, parser, classifications, forbidden_contracts, classified_containers, findings
        )

    _check_root_classification(root_packages, classified_containers, findings)

    consumer_trees, excluded_trees = _read_tree_declarations(repository, parser, roots, findings)
    consumer_contracts = _read_consumer_contracts(parser, consumer_trees, forbidden_contracts, repository, findings)
    declared_trees = frozenset(tree.path for tree in (*consumer_trees, *excluded_trees))
    _check_undeclared_top_level_roots(repository, root_packages, roots, declared_trees, findings)

    for container in sorted(classified_containers):
        _check_container_coverage(container, roots, classifications, findings)

    for name in parser.sections():
        _check_contract_suppressions(name, parser, findings)

    authority = Authority(
        repository=repository,
        config_path=path,
        parser=parser,
        root_packages=root_packages,
        roots=tuple(roots),
        classifications=tuple(sorted(classifications)),
        forbidden_contracts=tuple(sorted(forbidden_contracts, key=lambda item: item.key)),
        consumer_trees=consumer_trees,
        consumer_contracts=consumer_contracts,
    )
    return AuthorityRead(authority, tuple(findings))


def _split_words(value: str) -> list[str]:
    """Split Import Linter's multiline list fields without policy semantics."""
    return [token for line in value.splitlines() for token in line.split()]


def _parse_layer_names(value: str, contract_name: str, findings: list[str]) -> tuple[str, ...]:
    """Parse layer tails so package coverage can be derived from the authority."""
    result: list[str] = []
    for raw in re.split(r"[:\n]", value):
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


def _check_undeclared_top_level_roots(
    repository: Path,
    root_packages: Sequence[str],
    roots: Sequence[RootPackage],
    declared_trees: frozenset[str],
    findings: list[str],
) -> None:
    """Find Python roots and repository trees omitted from the authority.

    A package-shaped directory is a root candidate wherever it sits.  Beyond
    that, every repository-root directory or module that holds Python under
    the repository's own inclusion policy must be a declared root, a declared
    consumer tree or a declared exclusion; the inclusion policy keeps ignored
    scratch, build and environment directories out of the census.
    """
    declared = {package.split(".", 1)[0] for package in root_packages}
    candidates: set[str] = set()
    source_modules: set[str] = set()
    for base in (repository / _SOURCE_CONTAINER, repository):
        inspect_root_base(base, repository, candidates, source_modules, findings)
    candidates -= declared_trees
    for candidate in sorted(candidates | source_modules):
        if candidate not in declared:
            findings.append(f"[UNCLASSIFIED_ROOT] Python root {candidate!r} is absent from root_packages")
    for candidate in sorted(source_modules & declared):
        findings.append(f"[AUTHORITY_CONFIG] source module {candidate!r} collides with a declared root")
    covered = frozenset({*_root_owned_entries(repository, roots), *declared_trees, *candidates})
    for name in _repository_python_entries(repository, covered, findings):
        findings.append(
            f"[UNCLASSIFIED_ROOT] repository tree {name!r} holds Python but is not a declared root, "
            f"an [{_CONSUMER_TREES_SECTION}] entry or an [{_EXCLUDED_TREES_SECTION}] entry"
        )


def _root_owned_entries(repository: Path, roots: Sequence[RootPackage]) -> frozenset[str]:
    """Return the repository-root entries whose Python the declared roots already classify."""
    owned = {_SOURCE_CONTAINER}
    for root in roots:
        try:
            owned.add(root.path.relative_to(repository).parts[0])
        except (ValueError, IndexError):
            continue
    return frozenset(owned)


def _repository_python_entries(repository: Path, covered: frozenset[str], findings: list[str]) -> tuple[str, ...]:
    """Return uncovered repository-root directories and modules holding policy-included Python."""
    try:
        entries = sorted(repository.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        findings.append(f"[AUTHORITY_CONFIG] cannot inspect repository root {repository}: {exc}")
        return ()
    names: list[str] = []
    for entry in entries:
        if entry.name == ".git" or entry.name in covered:
            continue
        if not entry.is_dir() and entry.suffix != _PYTHON_SUFFIX:
            continue
        if holds_repository_python(repository, entry.name):
            names.append(entry.name)
    return tuple(names)


def holds_repository_python(repository: Path, relative: str) -> bool:
    """Return whether ``relative`` is or contains Python the inclusion policy admits."""
    return bool(repository_python_files(repository, relative))


def repository_python_files(repository: Path, relative: str) -> tuple[str, ...]:
    """Return the policy-included Python files at or below one repository-relative path."""
    return tuple(path for path in repository_files(repository, under=(relative,)) if path.endswith(_PYTHON_SUFFIX))


def _read_tree_declarations(
    repository: Path, parser: configparser.ConfigParser, roots: Sequence[RootPackage], findings: list[str]
) -> tuple[tuple[ConsumerTree, ...], tuple[ConsumerTree, ...]]:
    """Read the consumer and excluded repository trees, each with its stated reason."""
    known_sections = {_CONSUMER_TREES_SECTION, _EXCLUDED_TREES_SECTION}
    for name in parser.sections():
        if (
            name.startswith(_GATE_SECTION_PREFIX)
            and name not in known_sections
            and not name.startswith(_CONSUMER_CONTRACT_PREFIX)
        ):
            findings.append(f"[AUTHORITY_CONFIG] unknown import-gate section {name!r}")
    owned = _root_owned_entries(repository, roots)
    consumers = _read_tree_section(repository, parser, _CONSUMER_TREES_SECTION, owned, findings)
    excluded = _read_tree_section(repository, parser, _EXCLUDED_TREES_SECTION, owned, findings)
    for path in sorted({tree.path for tree in consumers} & {tree.path for tree in excluded}):
        findings.append(f"[AUTHORITY_CONFIG] repository tree {path!r} is declared both a consumer and an exclusion")
    return consumers, excluded


def _read_tree_section(
    repository: Path, parser: configparser.ConfigParser, section: str, owned: frozenset[str], findings: list[str]
) -> tuple[ConsumerTree, ...]:
    """Read one ``path = reason`` section naming repository-root directories or modules."""
    if section not in parser:
        return ()
    trees: list[ConsumerTree] = []
    for raw_path, raw_reason in parser.items(section):
        path = raw_path.strip()
        reason = " ".join(raw_reason.split())
        if not reason:
            findings.append(f"[AUTHORITY_CONFIG] [{section}] entry {path!r} states no reason")
        if not path or path in {".", ".."} or "/" in path or "\\" in path:
            findings.append(f"[AUTHORITY_CONFIG] [{section}] entry {path!r} is not one repository-root entry")
            continue
        if path in owned:
            findings.append(f"[AUTHORITY_CONFIG] [{section}] entry {path!r} is already owned by a declared root")
            continue
        if not holds_repository_python(repository, path):
            findings.append(f"[AUTHORITY_CONFIG] [{section}] entry {path!r} holds no repository Python")
            continue
        trees.append(ConsumerTree(path, reason))
    return tuple(sorted(trees, key=lambda tree: tree.path))


def _read_consumer_contracts(
    parser: configparser.ConfigParser,
    consumer_trees: Sequence[ConsumerTree],
    forbidden_contracts: Sequence[ForbiddenContract],
    repository: Path,
    findings: list[str],
) -> tuple[ConsumerContractScope, ...]:
    """Bind consumer paths to the forbidden contracts that govern them."""
    scopes: list[ConsumerContractScope] = []
    tree_paths = tuple(tree.path for tree in consumer_trees)
    contracts = {contract.key: contract for contract in forbidden_contracts}
    for name in parser.sections():
        if not name.startswith(_CONSUMER_CONTRACT_PREFIX):
            continue
        contract = contracts.get(name.removeprefix(_CONSUMER_CONTRACT_PREFIX))
        if contract is None:
            findings.append(f"[AUTHORITY_CONFIG] section {name!r} names no forbidden Import Linter contract")
            continue
        paths = _consumer_contract_paths(parser, name, tree_paths, repository, findings)
        if not paths:
            findings.append(f"[AUTHORITY_CONFIG] section {name!r} binds no consumer path")
        scopes.append(ConsumerContractScope(contract, tuple(sorted(paths))))
    return tuple(sorted(scopes, key=lambda scope: scope.contract.key))


def _consumer_contract_paths(
    parser: configparser.ConfigParser, name: str, tree_paths: tuple[str, ...], repository: Path, findings: list[str]
) -> list[str]:
    paths: list[str] = []
    for raw_path, raw_reason in parser.items(name):
        path = PurePosixPath(raw_path.strip().replace("\\", "/")).as_posix()
        if not " ".join(raw_reason.split()):
            findings.append(f"[AUTHORITY_CONFIG] [{name}] entry {path!r} states no reason")
        if not any(path == tree or path.startswith(f"{tree}/") for tree in tree_paths):
            findings.append(f"[AUTHORITY_CONFIG] [{name}] entry {path!r} lies outside every consumer tree")
        elif not holds_repository_python(repository, path):
            findings.append(f"[AUTHORITY_CONFIG] [{name}] entry {path!r} holds no repository Python")
        else:
            paths.append(path)
    return paths


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _has_options(section: Mapping[str, str], *keys: str) -> bool:
    return any(key in section for key in keys)


def _read_contract_classification(
    name: str,
    parser: configparser.ConfigParser,
    classifications: list[tuple[str, tuple[str, ...]]],
    forbidden_contracts: list[ForbiddenContract],
    classified_containers: set[str],
    findings: list[str],
) -> None:
    """Read contract classification."""
    contract = parser[name]
    if not name.startswith("importlinter:contract:"):
        return
    contract_type = contract.get("type", "").strip().lower()
    if contract_type == "forbidden":
        _read_forbidden_contract(contract, name, forbidden_contracts, findings)
        return
    if contract_type != "layers":
        return

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


def _check_contract_suppressions(name: str, parser: configparser.ConfigParser, findings: list[str]) -> None:
    """Check contract suppressions."""
    contract = parser[name]
    if _has_options(contract, "ignore_imports", "exhaustive_ignores"):
        findings.append(f"[AUTHORITY_CONFIG] contract {name!r} contains an import suppression")
    if _truthy(contract.get("allow_indirect_imports", "false")):
        findings.append(f"[AUTHORITY_CONFIG] contract {name!r} allows indirect-import suppression")
    alerting = contract.get("unmatched_ignore_imports_alerting", "error").strip().lower()
    if alerting not in {"error", ""}:
        findings.append(f"[AUTHORITY_CONFIG] contract {name!r} treats unmatched imports as {alerting}")


def _read_forbidden_contract(
    contract: Mapping[str, str], name: str, forbidden_contracts: list[ForbiddenContract], findings: list[str]
) -> None:
    """Read forbidden contract."""
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
    return


def _check_container_coverage(
    container: str, roots: list[RootPackage], classifications: list[tuple[str, tuple[str, ...]]], findings: list[str]
) -> None:
    """Check container coverage."""
    container_path = _locate_container(roots, container)
    if container_path is None:
        findings.append(f"[UNCLASSIFIED_PACKAGE] classified container {container!r} has no source directory")
        return
    layers = next((set(values) for name, values in classifications if name == container), set[str]())
    for child in _direct_children(container_path):
        if child not in layers:
            findings.append(f"[UNCLASSIFIED_PACKAGE] {container!r} child {child!r} is absent from its declared layers")


def _check_root_classification(
    root_packages: tuple[str, ...], classified_containers: set[str], findings: list[str]
) -> None:
    """Check root classification."""
    for root in root_packages:
        if not any(container == root or container.startswith(f"{root}.") for container in classified_containers):
            findings.append(f"[UNCLASSIFIED_PACKAGE] root {root!r} has no Import Linter layer classification")
