"""Check models for the subordinate import checker."""

from __future__ import annotations

import ast
import configparser
from dataclasses import dataclass, field
from pathlib import Path

from dev.exit_codes import FAILED, TOOL_BROKEN


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
                        else finding.path.as_posix()
                        if finding.path is not None
                        else None
                    ),
                }
                for finding in self.findings
            ],
            "occurrences": [occurrence.as_dict(repository) for occurrence in self.occurrences],
            "schema_version": 2,
        }


@dataclass
class ImportBinding:
    """One module-level binding used by canonical-symbol checks."""

    kind: str
    target: str | None = None
    imported_name: str | None = None


@dataclass
class SourceModule:
    """Parsed source module and its module-level binding facts."""

    name: str
    path: Path
    tree: ast.Module
    is_package: bool
    bindings: dict[str, ImportBinding] = field(default_factory=dict)
    imported_count: int = 0
    local_definitions: int = 0
    has_imports: bool = False
