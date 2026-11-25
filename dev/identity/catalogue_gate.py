"""Hold tests and fixtures to the synthetic-identifier catalogue convention.

The value-free canary in :mod:`dev.identity.tree_scan` answers whether a real
identity reached the repository and cannot tell a deliberate synthetic value from
a leak. The catalogue ``dev/fixtures/personas/identities.toml`` declares the
convention that does: a persona role binds one value, a generic pool reserves
values for tests that need any valid identifier, and refusals are the values that
fail on purpose. Inside tests and fixtures this gate accepts a checksum-valid
identifier only by that convention and reports two violations:

* ``off-convention``: bound to no role, not in the pool and not a refusal;
* ``role-reuse``: bound to a persona role but used outside that persona's own
  files and the generated projections derived from the personas.

Detection and the checksum come from :func:`dev.sanitizer.residual_identity.checksum_valid_spans`.
A finding carries a location and a class, never the matched text; the role name
is not a value and is the one datum added to a ``role-reuse`` finding so the
owner of the persona can be found.
"""

from __future__ import annotations

import tomllib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from dev.paths import UTF_8
from dev.sanitizer.residual_identity import ResidualKind, checksum_valid_spans, identity_authority_scope

from .tree_scan import (
    BLOCKING_KINDS,
    SCANNED_SUFFIXES,
    CandidateFile,
    FileTracking,
    in_scope,
    read_text,
    repository_files,
)

CATALOGUE_PATH: Final[str] = "dev/fixtures/personas/identities.toml"
PERSONAS_PREFIX: Final[str] = "dev/fixtures/personas/"

#: Suffixes the convention gate reads: the canary's classes plus the test and
#: fixture languages of the native tree and the recorded transcripts.
GATE_SUFFIXES: Final[frozenset[str]] = SCANNED_SUFFIXES | frozenset({".ts", ".tsx", ".js", ".mjs", ".rs", ".seq"})

#: A directory name that makes everything below it a test tree wherever it sits.
_TEST_DIRECTORY: Final[str] = "tests"
_TEST_ROOTS: Final[frozenset[str]] = frozenset({"src", "dev", "native"})

#: Path prefixes that are fixtures outside any ``tests`` directory.
FIXTURE_PREFIXES: Final[tuple[str, ...]] = (
    "src/cadrumo/tests/fixtures/",
    "native/desktop/frontend/src/dev/fixtures/",
    "docs/_sequences/",
)

_NIF_SHAPE: Final[str] = "nif"
_NIE_SHAPE: Final[str] = "nie"
_CIF_SHAPE: Final[str] = "cif"
#: The NIF issued to a natural person without a DNI: K, L or M, seven digits and
#: the NIF control letter.
_PREFIXED_NIF_SHAPE: Final[str] = "prefixed_nif"
_PREFIXED_NIF_LEADERS: Final[str] = "KLM"
_SPAIN_PREFIX: Final[str] = "ES"


class ConventionViolation(StrEnum):
    """Why a checksum-valid identifier is refused inside tests and fixtures.

    Attributes:
        OFF_CONVENTION: The value is bound to no role, outside the generic pool and not a refusal.
        ROLE_REUSE: The value is a persona role's and appears outside that persona's files and projections.
    """

    OFF_CONVENTION = "off-convention"
    ROLE_REUSE = "role-reuse"


class CatalogueError(ValueError):
    """The identity catalogue does not declare what the gate needs."""


@dataclass(frozen=True, slots=True)
class PoolRange:
    """A counter range of one identifier shape, reserved for generic tests.

    Attributes:
        shape: ``nif``, ``nie``, ``prefixed_nif`` or ``cif``.
        first: Lowest counter in the range.
        last: Highest counter in the range.
        letters: The leading letters admitted (``nie``, ``prefixed_nif`` and ``cif``); empty for ``nif``.
    """

    shape: str
    first: int
    last: int
    letters: frozenset[str]


@dataclass(frozen=True, slots=True)
class Catalogue:
    """The part of ``identities.toml`` the gate enforces."""

    roles: dict[str, tuple[str, str]]
    """Bound value to ``(role, persona)``."""
    pool_values: frozenset[str]
    pool_ranges: tuple[PoolRange, ...]
    refusals: frozenset[str]
    projection_prefixes: tuple[str, ...]

    def in_pool(self, value: str) -> bool:
        """Whether ``value`` is a declared pool member."""
        if value in self.pool_values:
            return True
        shape = _shape(value)
        if shape is None:
            return False
        counter = _counter(value, shape)
        letter = value[0] if shape != _NIF_SHAPE else ""
        return any(
            candidate.shape == shape
            and candidate.first <= counter <= candidate.last
            and (shape == _NIF_SHAPE or letter in candidate.letters)
            for candidate in self.pool_ranges
        )


@dataclass(frozen=True, slots=True)
class ConventionFinding:
    """One refused occurrence, WITHOUT the value."""

    path: str
    line: int
    column: int
    kind: ResidualKind
    violation: ConventionViolation
    role: str | None

    def rendered(self) -> str:
        """A value-free, deterministic description."""
        suffix = f" role={self.role}" if self.role is not None else ""
        return f"{self.path}:{self.line}:{self.column} [{self.kind.value}] {self.violation.value}{suffix}"


@dataclass(frozen=True, slots=True)
class ConventionScan:
    """The result of one convention sweep."""

    findings: tuple[ConventionFinding, ...]
    files_scanned: int
    unreadable: tuple[str, ...]

    def by_violation(self) -> Counter[ConventionViolation]:
        """How many findings fall under each violation."""
        return Counter(finding.violation for finding in self.findings)

    def files_with_findings(self) -> int:
        """How many distinct files hold at least one finding."""
        return len({finding.path for finding in self.findings})


def _shape(value: str) -> str | None:
    if len(value) != 9:
        return None
    if value[:8].isdigit() and value[8].isalpha():
        return _NIF_SHAPE
    if not (value[0].isalpha() and value[1:8].isdigit()):
        return None
    if value[8].isalpha():
        if value[0] in "XYZ":
            return _NIE_SHAPE
        if value[0] in _PREFIXED_NIF_LEADERS:
            return _PREFIXED_NIF_SHAPE
    return _CIF_SHAPE


def _counter(value: str, shape: str) -> int:
    return int(value[:8]) if shape == _NIF_SHAPE else int(value[1:8])


def _normal(candidate: str) -> str:
    """The bare identifier: the ES intra-community spelling is the same value."""
    upper = candidate.upper()
    if len(upper) == 11 and upper.startswith(_SPAIN_PREFIX):
        return upper[len(_SPAIN_PREFIX) :]
    return upper


def _pool_kind(table: dict[str, object], where: str) -> str:
    shape = table.get("kind")
    if not isinstance(shape, str) or shape not in {_NIF_SHAPE, _NIE_SHAPE, _PREFIXED_NIF_SHAPE, _CIF_SHAPE}:
        raise CatalogueError(f"{where}: kind must be nif, nie, prefixed_nif or cif")
    return shape


def _pool_bounds(table: dict[str, object], where: str) -> tuple[int, int]:
    first = table.get("first")
    last = table.get("last")
    if not isinstance(first, int) or not isinstance(last, int) or first > last:
        raise CatalogueError(f"{where}: first and last must be integers with first <= last")
    return first, last


def _pool_letters(table: dict[str, object], where: str) -> list[str]:
    letters = table.get("letters", [])
    if not isinstance(letters, list) or not all(isinstance(letter, str) for letter in letters):
        raise CatalogueError(f"{where}: letters must be a list of strings")
    return [letter for letter in letters if isinstance(letter, str)]


def _pool_range(table: dict[str, object], where: str) -> PoolRange:
    shape = _pool_kind(table, where)
    first, last = _pool_bounds(table, where)
    letters = _pool_letters(table, where)
    if shape != _NIF_SHAPE and not letters:
        raise CatalogueError(f"{where}: a {shape} range names its leading letters")
    return PoolRange(shape=shape, first=first, last=last, letters=frozenset(letters))


def _generic_pool(convention: dict[str, object]) -> tuple[list[object], list[object]]:
    pool = convention.get("generic_pool")
    if not isinstance(pool, dict):
        raise CatalogueError("convention.generic_pool must be declared")
    values = pool.get("values")
    ranges = pool.get("ranges")
    if not isinstance(values, list) or not isinstance(ranges, list) or not ranges:
        raise CatalogueError("convention.generic_pool needs values and at least one range")
    return list[object](values), list[object](ranges)


def _projection_prefixes(convention: dict[str, object]) -> list[str]:
    projections = convention.get("generated_projections")
    prefixes = projections.get("paths") if isinstance(projections, dict) else None
    if not isinstance(prefixes, list) or not all(isinstance(prefix, str) for prefix in prefixes):
        raise CatalogueError("convention.generated_projections.paths must list path prefixes")
    return [prefix for prefix in prefixes if isinstance(prefix, str)]


def parse_catalogue(document: dict[str, object]) -> Catalogue:
    """Read the convention out of a parsed ``identities.toml``."""
    convention = document.get("convention")
    if not isinstance(convention, dict):
        raise CatalogueError("convention must be a table")
    values, ranges = _generic_pool(convention)
    prefixes = _projection_prefixes(convention)
    roles: dict[str, tuple[str, str]] = {}
    for table in _tables(document.get("identities")):
        roles[_normal(str(table["value"]))] = (str(table["role"]), str(table["persona"]))
    refusals = frozenset(_normal(str(table["value"])) for table in _tables(document.get("refusals")))
    pool_values = frozenset(_normal(str(value)) for value in values)
    if pool_values & roles.keys():
        raise CatalogueError("a generic pool value is also bound to a role")
    pool_ranges = tuple(_pool_range(table, "convention.generic_pool.ranges") for table in _tables(ranges))
    catalogue = Catalogue(
        roles=roles,
        pool_values=pool_values,
        pool_ranges=pool_ranges,
        refusals=refusals,
        projection_prefixes=tuple(prefixes),
    )
    overlap = [value for value in roles if catalogue.in_pool(value)]
    if overlap:
        raise CatalogueError(f"{len(overlap)} role-bound values lie inside the generic pool")
    return catalogue


def _tables(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise CatalogueError("expected an array of tables")
    tables: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise CatalogueError("expected an array of tables")
        tables.append(item)
    return tables


def read_catalogue(repo_root: Path) -> Catalogue:
    """Parse the repository's identity catalogue."""
    text = (repo_root / CATALOGUE_PATH).read_text(encoding=UTF_8)
    return parse_catalogue(tomllib.loads(text))


def in_gate_scope(relative: str) -> bool:
    """Whether ``relative`` is a test or fixture path the convention governs."""
    if relative.startswith(FIXTURE_PREFIXES):
        return True
    parts = relative.split("/")
    return parts[0] in _TEST_ROOTS and _TEST_DIRECTORY in parts[1:-1]


def _persona_directory(relative: str) -> str | None:
    """The persona id owning ``relative`` when it lies in a persona's own directory."""
    if not relative.startswith(PERSONAS_PREFIX):
        return None
    rest = relative[len(PERSONAS_PREFIX) :]
    return rest.split("/", 1)[0] if "/" in rest else None


def _role_use_is_allowed(catalogue: Catalogue, relative: str, persona: str) -> bool:
    if relative == CATALOGUE_PATH:
        return True
    if _persona_directory(relative) == persona:
        return True
    return relative.startswith(catalogue.projection_prefixes)


def classify(catalogue: Catalogue, relative: str, value: str) -> tuple[ConventionViolation, str | None] | None:
    """The violation ``value`` commits at ``relative``, or ``None`` when the convention accepts it."""
    if value in catalogue.refusals:
        return None
    bound = catalogue.roles.get(value)
    if bound is not None:
        role, persona = bound
        if _role_use_is_allowed(catalogue, relative, persona):
            return None
        return ConventionViolation.ROLE_REUSE, role
    if catalogue.in_pool(value):
        return None
    return ConventionViolation.OFF_CONVENTION, None


def _file_findings(rules: Catalogue, candidate: CandidateFile, text: str) -> list[ConventionFinding]:
    findings: list[ConventionFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, column, match in checksum_valid_spans(line, BLOCKING_KINDS):
            verdict = classify(rules, candidate.relative, _normal(match))
            if verdict is None:
                continue
            violation, role = verdict
            findings.append(
                ConventionFinding(
                    path=candidate.relative,
                    line=line_number,
                    column=column,
                    kind=kind,
                    violation=violation,
                    role=role,
                )
            )
    return findings


def scan_convention(
    repo_root: Path,
    *,
    catalogue: Catalogue | None = None,
    files: Sequence[CandidateFile] | None = None,
) -> ConventionScan:
    """Every convention violation in the visible test and fixture files.

    Args:
        repo_root: The working tree to scan.
        catalogue: The convention to enforce, read from the tree when omitted.
        files: A pre-enumerated candidate list, narrowed here to the gate's scope.
    """
    rules = catalogue if catalogue is not None else read_catalogue(repo_root)
    candidates = files if files is not None else repository_files(repo_root, suffixes=GATE_SUFFIXES)
    findings: list[ConventionFinding] = []
    unreadable: list[str] = []
    scanned = 0
    with identity_authority_scope():
        for candidate in candidates:
            if candidate.tracking is not FileTracking.VISIBLE or not in_scope(candidate.path, GATE_SUFFIXES):
                continue
            if not in_gate_scope(candidate.relative):
                continue
            text = read_text(candidate.path)
            if text is None:
                unreadable.append(candidate.relative)
                continue
            scanned += 1
            findings.extend(_file_findings(rules, candidate, text))
    ordered = tuple(sorted(findings, key=lambda finding: (finding.path, finding.line, finding.column)))
    return ConventionScan(findings=ordered, files_scanned=scanned, unreadable=tuple(sorted(unreadable)))
