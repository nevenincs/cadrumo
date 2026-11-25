"""The discovery paths of the codebase-key scan, each declared with the inputs it reads.

The shared codebase-key scan is keyed on the content of every file the scan
reads. A hand-kept list of those files drifts from the readers, so each
discovery path that is not a walk of the scan roots is declared here as one
:class:`DiscoveryPath`: the function that yields its keys and the function that
names its inputs sit in one row. The scan runs exactly the rows of
:data:`DISCOVERY_PATHS` and the cache key is built from the same rows, so a path
cannot run without declaring its inputs.

The walks of the scan roots (the literal call-site scan and the AST scan) read
only the Python of their roots and are keyed by the manager from those roots.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from dev.first_party_source import is_test_source
from dev.paths import REPO_ROOT
from dev.quality.source_import_analysis import walk_module_imports

#: Directories no input of the scan lives in: bytecode and the test surface.
NOT_SCANNED = ("__pycache__", "tests")

#: Suffixes of the product files the scan reads: Python source, which it parses
#: and whose command and wizard registries it imports, and the TOML registry,
#: schema and navigation data it reads keys from.
PRODUCT_SUFFIXES = frozenset({".py", ".toml"})

_LOCALES_PACKAGE = REPO_ROOT / "dev" / "locales"


@dataclass(frozen=True)
class DiscoveryPath:
    """One way the scan finds keys, with every input that decides what it finds."""

    name: str
    keys: Callable[[], Iterable[str]]
    inputs: tuple[Callable[[], Iterable[Path]], ...]
    """The readers of the files this path reads; a reader shared by several paths runs once."""
    identity: Callable[[], str] = lambda: ""
    """Facts the path reads that are not files, rendered as text; changes with them."""

    def files(self) -> tuple[Path, ...]:
        """Every file this path reads, over-approximated."""
        return tuple(sorted({path for reader in self.inputs for path in reader()}))


def product_source_inputs() -> tuple[Path, ...]:
    """Every production Python and TOML file under ``src``, over-approximated, never under.

    Registries are imported from anywhere under ``src`` and packaged TOML data
    is read there, so the whole tree is an input.
    """
    return tuple(
        path
        for path in scan_directory(REPO_ROOT / "src", pattern="*", recursive=True, prune_directories=NOT_SCANNED)
        if path.suffix in PRODUCT_SUFFIXES and path.is_file() and not is_test_source(path, root=REPO_ROOT / "src")
    )


def locales_package_inputs() -> tuple[Path, ...]:
    """Every production module of this package: its key constants and scanners."""
    return tuple(
        path
        for path in scan_directory(_LOCALES_PACKAGE, pattern="*.py", recursive=True, prune_directories=NOT_SCANNED)
        if not is_test_source(path, root=_LOCALES_PACKAGE)
    )


_IMPORT_CACHE: dict[Path, tuple[tuple[int, int], tuple[Path, ...]]] = {}


def _module_file(module: str) -> Path | None:
    """The ``dev`` file a dotted module name resolves to, or ``None`` outside ``dev``."""
    parts = module.split(".")
    if parts[0] != "dev":
        return None
    candidate = REPO_ROOT.joinpath(*parts)
    for resolved in (candidate.with_suffix(".py"), candidate / "__init__.py"):
        if resolved.is_file():
            return resolved
    return None


def _direct_dev_imports(path: Path) -> tuple[Path, ...]:
    """The ``dev`` modules ``path`` imports anywhere, including inside functions."""
    stat = path.stat()
    stamp = (stat.st_mtime_ns, stat.st_size)
    remembered = _IMPORT_CACHE.get(path)
    if remembered is not None and remembered[0] == stamp:
        return remembered[1]
    found: set[Path] = set()
    for site in walk_module_imports(path, src_root=REPO_ROOT):
        for name in (site.target_mod, *(f"{site.target_mod}.{imported}" for imported in site.imported_names)):
            resolved = _module_file(name)
            if resolved is not None:
                found.add(resolved)
    parents = tuple(sorted(found))
    _IMPORT_CACHE[path] = (stamp, parents)
    return parents


def dev_import_closure(seeds: Iterable[Path]) -> tuple[Path, ...]:
    """``seeds`` and every ``dev`` module they import, directly or through another, as source files."""
    pending = list(seeds)
    seen: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        pending.extend(_direct_dev_imports(path))
        # A package's ``__init__`` runs when any of its modules is imported.
        pending.extend(
            initialiser
            for parent in path.relative_to(REPO_ROOT).parents
            if (initialiser := REPO_ROOT / parent / "__init__.py").is_file()
        )
    return tuple(sorted(seen))


def tooling_inputs() -> tuple[Path, ...]:
    """The development modules whose code decides the key set: this package and what it imports."""
    return dev_import_closure(locales_package_inputs())


def registry_inputs() -> tuple[Path, ...]:
    """The registry data trees the registry scanners read: every packaged TOML under the registry root."""
    from cadrumo.core.resources.bundled_data import bundled_path

    root = bundled_path("registry").resolve()
    return tuple(sorted(path for path in root.rglob("*.toml") if path.is_file()))


def docs_metadata_inputs() -> tuple[Path, ...]:
    """The documentation metadata TOML the f-string registry's terminology and legal catalogues read."""
    root = REPO_ROOT / "dev" / "docs" / "metadata"
    return tuple(sorted(path for path in root.rglob("*.toml") if path.is_file()))


def navigation_register_inputs() -> tuple[Path, ...]:
    """The navigation register file the client's validating loader reads."""
    from cadrumo_client.contracts import navigation

    return (Path(navigation.__file__).resolve().with_name("navigation.toml"),)


def authority_identity() -> str:
    """The published authority generation the wizard descriptors are built against."""
    from cadrumo.domain.calculations.registry.authority_location import published_authority_generation

    return str(published_authority_generation())


def _fstring_keys() -> Iterable[str]:
    from .fstring_registry import get_registered_keys

    return get_registered_keys()


def _command_spec_keys() -> Iterable[str]:
    from .command_spec_scanner import scan_command_spec_keys

    return scan_command_spec_keys()


def _category_profile_keys() -> Iterable[str]:
    from .registry_scanner import scan_registry_keys

    return scan_registry_keys()


def _user_profile_schema_keys() -> Iterable[str]:
    from .registry_scanner import scan_profile_schema_keys

    return scan_profile_schema_keys()


def _modelo_schema_keys() -> Iterable[str]:
    from .registry_scanner import scan_modelo_schema_keys

    return scan_modelo_schema_keys()


def _wizard_descriptor_keys() -> Iterable[str]:
    from .wizard_translation_audit import wizard_descriptor_keys

    return wizard_descriptor_keys()


def _desktop_chrome_keys() -> Iterable[str]:
    from .desktop_chrome import DESKTOP_CHROME_KEYS

    return DESKTOP_CHROME_KEYS


def _manager_chrome_keys() -> Iterable[str]:
    from .manager_chrome import MANAGER_CHROME_KEYS

    return MANAGER_CHROME_KEYS


def _navigation_keys() -> Iterable[str]:
    from cadrumo_client.contracts.navigation import load_navigation_register

    return (key for element in load_navigation_register().elements for key in (element.label, element.keywords))


DISCOVERY_PATHS: tuple[DiscoveryPath, ...] = (
    DiscoveryPath("f-string registry", _fstring_keys, (tooling_inputs, product_source_inputs, docs_metadata_inputs)),
    DiscoveryPath("command specs", _command_spec_keys, (tooling_inputs, product_source_inputs)),
    DiscoveryPath("category profile registry", _category_profile_keys, (tooling_inputs, registry_inputs)),
    DiscoveryPath("user-profile schema", _user_profile_schema_keys, (tooling_inputs, registry_inputs)),
    DiscoveryPath("Modelo schemas", _modelo_schema_keys, (tooling_inputs, registry_inputs)),
    DiscoveryPath(
        "wizard descriptors",
        _wizard_descriptor_keys,
        (tooling_inputs, product_source_inputs),
        identity=authority_identity,
    ),
    DiscoveryPath("desktop chrome", _desktop_chrome_keys, (tooling_inputs,)),
    DiscoveryPath("manager chrome", _manager_chrome_keys, (tooling_inputs,)),
    DiscoveryPath("navigation register", _navigation_keys, (tooling_inputs, navigation_register_inputs)),
)


def discovery_path_inputs() -> tuple[Path, ...]:
    """The union of every declared discovery path's inputs."""
    found: set[Path] = set()
    for reader in {reader for declared in DISCOVERY_PATHS for reader in declared.inputs}:
        found.update(reader())
    return tuple(sorted(found))


def discovery_identity() -> str:
    """The non-file facts the discovery paths read, in declaration order."""
    return "\n".join(f"{declared.name}={declared.identity()}" for declared in DISCOVERY_PATHS)
