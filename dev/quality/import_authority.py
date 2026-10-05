"""Authority for the subordinate import checker."""

from __future__ import annotations

import configparser
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from dev._paths import UTF_8

from .import_check_models import Authority, AuthorityRead, ForbiddenContract, RootPackage

_DOTTED_NAME: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


_LAYER_NAME: Final[re.Pattern[str]] = re.compile(r"^(?:\(([A-Za-z_]\w*)\)|([A-Za-z_]\w*))$")


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
    _check_undeclared_top_level_roots(repository, root_packages, findings)
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
        _inspect_root_base(base, repository, candidates, source_modules, findings)
    for candidate in sorted(candidates | source_modules):
        if candidate not in declared:
            findings.append(f"[UNCLASSIFIED_ROOT] Python root {candidate!r} is absent from root_packages")
    for candidate in sorted(source_modules & declared):
        findings.append(f"[AUTHORITY_CONFIG] source module {candidate!r} collides with a declared root")


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


def _collect_root_candidate(
    entry: Path, base: Path, repository: Path, candidates: set[str], source_modules: set[str]
) -> None:
    """Collect root candidate."""
    if entry.name.startswith("."):
        return
    if base == repository / "src" and entry.is_file() and entry.suffix == ".py":
        source_modules.add(entry.stem)
        return
    if not entry.is_dir():
        return
    if (entry / "__init__.py").is_file() or (base == repository / "src" and any(entry.rglob("*.py"))):
        candidates.add(entry.name)


def _inspect_root_base(
    base: Path, repository: Path, candidates: set[str], source_modules: set[str], findings: list[str]
) -> None:
    """Inspect root base."""
    if not base.is_dir():
        return
    try:
        entries = tuple(base.iterdir())
    except OSError as exc:
        findings.append(f"[AUTHORITY_CONFIG] cannot inspect source-root directory {base}: {exc}")
        return
    for entry in entries:
        _collect_root_candidate(entry, base, repository, candidates, source_modules)


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
