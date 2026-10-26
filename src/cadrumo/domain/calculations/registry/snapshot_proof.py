"""The proof contract shared by authority publication and runtime snapshot builds.

Publication proves that :func:`~.snapshot.build_validated_snapshot` passes for
every cell of the generation's declared selector set: each modelo, each filing
year from the support floor to the horizon, each declared period token (the
symbolic ``EVENT-N`` as itself) and each authority grade, always with ``on`` and
``revision_id`` absent. The passing cells, the validator that proved them and
the date window in which their wall-clock fact lookups resolve identically are
recorded in the published database, covered by its physical digest.

At runtime a proof only lets the same validator skip its cross-check calls; it
never selects, assembles or refuses anything. It is stated against the
:class:`RegistrySnapshot` the proven cells build. A request outside the proven set,
a validator whose sources changed, a date outside the window or a database
without proofs all run the full validation in the same function. Refusals are
never recorded: a refusal always comes from the validator itself.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from threading import Lock
from typing import TYPE_CHECKING, Final, Protocol

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.hierarchy import CadrumoError
from ....core.hashing import canonical_json_bytes, sha256_hex
from ....core.time.clock import today_madrid
from .errors import RegistryFailureCondition, RegistryValidationError

if TYPE_CHECKING:
    from .facts.resolution import GovernedFactQuery, ResolvedGovernedFact
    from .facts.schema import GovernedFact
    from .governed_fact_scope import GovernedFactSource
    from .schema import RegistrySnapshot
    from .schema_references import PeriodSelector
    from .snapshot_globals import SupportedFilingYearsCatalogue
    from .temporal import ModeloRevisionDirectory

SNAPSHOT_PROOF_DDL: Final[tuple[str, ...]] = (
    "CREATE TABLE snapshot_proof_contract (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), "
    "validator_digest TEXT NOT NULL CHECK (length(validator_digest) = 64), window_from TEXT, window_to TEXT) STRICT",
    "CREATE TABLE snapshot_proof_validator_sources (module TEXT PRIMARY KEY, "
    "sha256 TEXT NOT NULL CHECK (length(sha256) = 64)) STRICT",
    "CREATE TABLE snapshot_proofs (modelo_id TEXT NOT NULL, filing_year INTEGER NOT NULL, period TEXT NOT NULL, "
    "grade TEXT NOT NULL, revision_id TEXT NOT NULL, PRIMARY KEY (modelo_id, filing_year, period, grade)) "
    "STRICT, WITHOUT ROWID",
)
"""The proof tables of a ``cadrumo-authority-sqlite-v5`` database, one statement each.

Dates are ISO ``YYYY-MM-DD`` text with NULL meaning an open bound, and
``grade`` is a :class:`RegistryAuthorityGrade` value. The publisher creates
these tables from this single definition and the reader queries them.
"""

SNAPSHOT_PROOF_TABLES: Final[tuple[str, ...]] = (
    "snapshot_proof_contract",
    "snapshot_proof_validator_sources",
    "snapshot_proofs",
)
"""The table names :data:`SNAPSHOT_PROOF_DDL` creates, in the same order."""

_VALIDATOR_DIGEST_SCHEMA: Final = "cadrumo-snapshot-validator-closure/v1"
_CLOSURE_ROOT_PACKAGE: Final = "cadrumo"
_SNAPSHOT_MODULE: Final = "cadrumo.domain.calculations.registry.snapshot"
_SNAPSHOT_PACKAGE: Final = "cadrumo.domain.calculations.registry"


class SnapshotProofPublicationError(RegistryValidationError):
    """A declared selector cell fails at or below its revision's declared grade, so publication refuses."""


@dataclass(frozen=True, slots=True)
class SnapshotProofKey:
    """One cell of the proven selector set, after canonical period normalisation."""

    modelo_id: str
    filing_year: int
    period: str
    grade: RegistryAuthorityGrade


@dataclass(frozen=True, slots=True)
class SnapshotCrossCheckProof:
    """Publication's record that one cell passed every snapshot cross-check with this revision."""

    key: SnapshotProofKey
    revision_id: str


@dataclass(frozen=True, slots=True)
class ValidatorSource:
    """One module of the snapshot validator's import closure and its source digest."""

    module: str
    sha256: str


@dataclass(frozen=True, slots=True)
class SnapshotProofContract:
    """The validator and wall-clock window under which a database's proofs hold.

    Both window bounds are inclusive and ``None`` is open. A window whose
    ``window_from`` lies after its ``window_to`` is empty and admits no date;
    publication records it when it cannot bound a wall-clock fact lookup.
    """

    validator_sources: tuple[ValidatorSource, ...]
    validator_digest: str
    window_from: date | None
    window_to: date | None

    def admits_date(self, coordinate: date) -> bool:
        """Return whether ``coordinate`` lies inside the recorded fact-date window."""
        if self.window_from is not None and coordinate < self.window_from:
            return False
        return self.window_to is None or coordinate <= self.window_to


@dataclass(frozen=True, slots=True)
class SnapshotProofSet:
    """Everything publication writes into the proof tables."""

    contract: SnapshotProofContract
    proofs: tuple[SnapshotCrossCheckProof, ...]


class _PeriodSelected(Protocol):
    @property
    def period_selector(self) -> PeriodSelector: ...


class SnapshotProofOperation(Protocol):
    """The pinned-operation surface a publication sweep runs through."""

    def modelo_ids(self) -> tuple[str, ...]:
        """Return every modelo identity of the generation."""
        ...

    def modelo_directory(self, modelo_id: str, /) -> ModeloRevisionDirectory:
        """Return one modelo's selector-complete revision directory."""
        ...

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        """Return the generation's filing-year support envelope."""
        ...

    def governed_fact(self, fact_id: str, /) -> GovernedFact:
        """Return one raw governed fact."""
        ...

    def resolve_governed_fact(self, query: GovernedFactQuery, /) -> ResolvedGovernedFact:
        """Resolve one governed-fact query."""
        ...

    def snapshot_proof_contract(self) -> SnapshotProofContract | None:
        """Return the proof contract the generation already records, if any."""
        ...

    def build_unretained_snapshot(
        self,
        modelo_id: str,
        /,
        *,
        filing_year: int,
        period: str,
        grade: RegistryAuthorityGrade,
        governed_facts: GovernedFactSource | None = None,
    ) -> RegistrySnapshot:
        """Build one validated snapshot without retaining it in a shared cache."""
        ...


def snapshot_proof_key(
    revision: _PeriodSelected,
    *,
    modelo_id: str,
    filing_year: int,
    period: str,
    grade: RegistryAuthorityGrade,
) -> SnapshotProofKey:
    """Return the canonical proof key of a request that selected ``revision``.

    The period is normalised exactly as the snapshot validator normalises it:
    a declared token takes its declared spelling, the symbolic ``EVENT-N``
    stays itself and a concrete ``EVENT-3`` stays concrete, so only the
    symbolic selector can match a proof.
    """
    from .period_selector_match import registry_period_for_request

    normalized = registry_period_for_request(revision.period_selector.declared_periods, period) or period
    return SnapshotProofKey(modelo_id=modelo_id, filing_year=filing_year, period=normalized, grade=grade)


def _regular_source_in(directory: str, name: str) -> str | None:
    """Return the source file a path finder picks for ``name`` under ``directory``, a package before a module."""
    package_init = os.path.join(directory, name, "__init__.py")
    if os.path.isfile(package_init):
        return package_init
    module_file = os.path.join(directory, f"{name}.py")
    return module_file if os.path.isfile(module_file) else None


def _search_locations(package: str) -> tuple[str, ...] | None:
    """Return the directories ``package``'s submodules import from, without importing anything."""
    loaded = sys.modules.get(package)
    spec = getattr(loaded, "__spec__", None) if loaded is not None else None
    if spec is not None:
        locations = spec.submodule_search_locations
        return tuple(str(location) for location in locations) if locations is not None else None
    parent, _, name = package.rpartition(".")
    parent_locations = _search_locations(parent) if parent else None
    if parent_locations is None:
        return None
    for directory in parent_locations:
        init = _regular_source_in(directory, name)
        if init is not None and init.endswith("__init__.py"):
            return (os.path.dirname(init),)
    return None


def _module_origin(module: str) -> str | None:
    """Locate a module's Python source, preferring what the import system already knows.

    A loaded module states its own origin. Otherwise the file is found where
    the import system would look, in the directories of its parent package;
    only a module that resolution cannot place that way goes through
    ``find_spec``.
    """
    loaded = sys.modules.get(module)
    spec = getattr(loaded, "__spec__", None) if loaded is not None else None
    if spec is None:
        parent, _, name = module.rpartition(".")
        for directory in (_search_locations(parent) or ()) if parent else ():
            origin = _regular_source_in(directory, name)
            if origin is not None:
                return origin
        try:
            spec = importlib.util.find_spec(module)
        except (ImportError, ValueError):
            return None
    origin = getattr(spec, "origin", None) if spec is not None else None
    return origin if isinstance(origin, str) and origin.endswith(".py") else None


def _is_package(module: str) -> bool:
    origin = _module_origin(module)
    return origin is not None and origin.endswith("__init__.py")


def _source_bytes(module: str) -> bytes | None:
    origin = _module_origin(module)
    if origin is None:
        return None
    try:
        with open(origin, "rb") as stream:
            return stream.read()
    except OSError:
        return None


def _source_digest(source: bytes) -> str:
    return sha256_hex(source.replace(b"\r\n", b"\n"))


def _in_closure_root(module: str) -> bool:
    return module == _CLOSURE_ROOT_PACKAGE or module.startswith(f"{_CLOSURE_ROOT_PACKAGE}.")


def _with_ancestors(module: str) -> Iterable[str]:
    parts = module.split(".")
    return (".".join(parts[:index]) for index in range(1, len(parts) + 1))


@dataclass(frozen=True, slots=True)
class _ImportStatement:
    """One import statement as written, before it is resolved against the module's package."""

    level: int
    module: str
    names: tuple[str, ...]
    is_from: bool


_import_statements_cache: dict[str, tuple[str, tuple[_ImportStatement, ...]]] = {}
"""The parsed statements of each module's latest-seen source, with the digest they were parsed from.

Parsing about four hundred sources dominates a closure computation. A module's
statements are a pure function of its source bytes, so they are reused while
the digest is unchanged. Everything that depends on the file system (which
module is a package, which names are submodules) is resolved afresh on every
call, and every call re-reads and re-hashes every source.
"""


def _parsed_import_statements(module: str, source: bytes, digest: str) -> tuple[_ImportStatement, ...]:
    cached = _import_statements_cache.get(module)
    if cached is not None and cached[0] == digest:
        return cached[1]
    statements: list[_ImportStatement] = []
    for node in ast.walk(ast.parse(source, filename=module)):
        if isinstance(node, ast.Import):
            statements.extend(_ImportStatement(0, alias.name, (), False) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            statements.append(
                _ImportStatement(node.level, node.module or "", tuple(alias.name for alias in node.names), True)
            )
    parsed = tuple(statements)
    _import_statements_cache[module] = (digest, parsed)
    return parsed


def _imported_modules(module: str, statements: Iterable[_ImportStatement]) -> set[str]:
    """Return every ``cadrumo`` module an import statement anywhere in a module can execute."""
    package = module if _is_package(module) else module.rpartition(".")[0]
    found: set[str] = set()
    for statement in statements:
        if not statement.is_from:
            found.add(statement.module)
            continue
        target = importlib.util.resolve_name("." * statement.level + statement.module, package)
        found.add(target)
        if not _in_closure_root(target) or not _is_package(target):
            continue
        for name in statement.names:
            candidate = f"{target}.{name}"
            if name != "*" and _module_origin(candidate) is not None:
                found.add(candidate)
    return {ancestor for name in found if _in_closure_root(name) for ancestor in _with_ancestors(name)}


def snapshot_validator_closure() -> tuple[ValidatorSource, ...]:
    """Return the static import closure of the snapshot validator with each module's source digest.

    The closure starts at the snapshot module and every cross-domain check
    module it installs by name, then follows each ``import`` and ``from``
    statement anywhere in a module (function-local, lazy and type-checking
    imports included) into the ``cadrumo`` package, together with the packages
    each import executes. Each digest is the SHA-256 of the module source with
    CRLF folded to LF.

    Raises:
        RegistryValidationError: A module of the closure has no readable
            Python source, so no validator digest can be stated for it.
    """
    from .snapshot import cross_domain_check_modules

    roots = (
        _SNAPSHOT_MODULE,
        *(importlib.util.resolve_name(name, _SNAPSHOT_PACKAGE) for name in cross_domain_check_modules()),
    )
    pending = [ancestor for root in roots for ancestor in _with_ancestors(root)]
    digests: dict[str, str] = {}
    while pending:
        module = pending.pop()
        if module in digests:
            continue
        source = _source_bytes(module)
        if source is None:
            raise RegistryValidationError(f"snapshot validator module {module!r} has no readable Python source")
        digest = _source_digest(source)
        digests[module] = digest
        statements = _parsed_import_statements(module, source, digest)
        pending.extend(name for name in _imported_modules(module, statements) if name not in digests)
    return tuple(ValidatorSource(module, digests[module]) for module in sorted(digests))


def validator_digest(sources: Iterable[ValidatorSource]) -> str:
    """Return the digest naming one validator closure, independent of source order."""
    ordered = sorted((source.module, source.sha256) for source in sources)
    return sha256_hex(
        canonical_json_bytes({"schema": _VALIDATOR_DIGEST_SCHEMA, "sources": [list(item) for item in ordered]})
    )


_validator_matches: dict[str, bool] = {}
_validator_matches_lock = Lock()


def _sources_match(sources: Sequence[ValidatorSource]) -> bool:
    for source in sources:
        if not _in_closure_root(source.module):
            return False
        content = _source_bytes(source.module)
        if content is None or _source_digest(content) != source.sha256:
            return False
    return True


def runtime_validator_matches(contract: SnapshotProofContract) -> bool:
    """Return whether this process runs exactly the validator that proved ``contract``.

    Only the recorded modules are re-hashed: a new import can enter the
    closure only through an edit to a module already in it, which changes that
    module's digest. A contract whose digest does not name its own sources, a
    missing or unreadable module and any differing digest all say no. The
    answer is computed once per process for each validator digest.
    """
    if not contract.validator_sources or validator_digest(contract.validator_sources) != contract.validator_digest:
        return False
    with _validator_matches_lock:
        known = _validator_matches.get(contract.validator_digest)
        if known is None:
            known = _sources_match(contract.validator_sources)
            _validator_matches[contract.validator_digest] = known
        return known


_EMPTY_WINDOW: Final = (date.max, date.min)


@dataclass(slots=True, weakref_slot=True)
class _RecordingFactSource:
    """Delegate governed-fact resolution to the swept operation and keep the wall-clock queries."""

    operation: SnapshotProofOperation
    today: date
    wall_clock_queries: dict[GovernedFactQuery, None] = field(default_factory=dict)

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        resolved = self.operation.resolve_governed_fact(query)
        if query.effective_date == self.today:
            self.wall_clock_queries[query] = None
        return resolved

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self.operation.supported_filing_years()


def _constant_resolution_window(
    operation: SnapshotProofOperation,
    query: GovernedFactQuery,
    today: date,
) -> tuple[date | None, date | None]:
    """Return the widest window around ``today`` in which ``query``'s fact resolves the same variant.

    Resolution picks among the variants whose materialized window contains
    the date, by static precedence. Between two consecutive window endpoints
    of any variant of the fact, the containing set cannot change, so neither
    can the winner or its payload. The interval is also confined to the
    support envelope's hard gates. A fact that cannot be read, or whose
    windows do not contain ``today``, yields the empty window.
    """
    try:
        fact = operation.governed_fact(query.fact_id)
        envelope = operation.supported_filing_years().date_envelope()
        windows = tuple(fact.materialized_windows(envelope).values())
    except (CadrumoError, LookupError):
        return _EMPTY_WINDOW
    if not any(window.contains_date(today) for window in windows):
        return _EMPTY_WINDOW
    lower: date = envelope.floor
    upper: date | None = envelope.hard_ceiling
    for window in windows:
        if window.valid_from <= today:
            lower = max(lower, window.valid_from)
        else:
            boundary = window.valid_from - timedelta(days=1)
            upper = boundary if upper is None else min(upper, boundary)
        if window.valid_to is None:
            continue
        if window.valid_to < today:
            lower = max(lower, window.valid_to + timedelta(days=1))
        else:
            upper = window.valid_to if upper is None else min(upper, window.valid_to)
    return lower, upper


def _intersect_windows(
    windows: Iterable[tuple[date | None, date | None]],
) -> tuple[date | None, date | None]:
    lower: date | None = None
    upper: date | None = None
    for window_from, window_to in windows:
        if window_from is not None:
            lower = window_from if lower is None else max(lower, window_from)
        if window_to is not None:
            upper = window_to if upper is None else min(upper, window_to)
    return lower, upper


def _is_expected_ladder_refusal(error: CadrumoError, grade: RegistryAuthorityGrade) -> bool:
    """Say whether ``error`` is the grade ceiling refusing a grade above the revision's declaration.

    A revision that declares no grade claims nothing, so no grade lies at or
    below its declaration and the ceiling refusing it is always expected.
    """
    if not isinstance(error, RegistryValidationError):
        return False
    failure = error.registry_failure
    if failure is None or failure.condition is not RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT:
        return False
    graded = failure.facts.get("authority_grade_declared")
    if graded is False:
        return True
    declared = failure.facts.get("declared_authority_grade")
    if graded is not True or not isinstance(declared, str):
        return False
    ladder = tuple(RegistryAuthorityGrade)
    try:
        return ladder.index(grade) > ladder.index(RegistryAuthorityGrade(declared))
    except ValueError:
        return False


def prove_snapshot_selectors(operation: SnapshotProofOperation) -> SnapshotProofSet:
    """Sweep the declared selector set through the full validator and return the proofs to publish.

    Every cell runs :func:`~.snapshot.build_validated_snapshot` through the
    operation's normal, uncached build, without a proof and with the
    governed-fact scope bound to a recorder around ``operation``. A cell
    whose selection refuses does not exist and is skipped. A pass is recorded
    with the revision it selected. A refusal of a grade above the revision's
    declared grade is the expected ladder outcome and is not recorded. Any
    other failure is collected, and after the sweep all of them are raised
    together.

    The fact-date window is the intersection of the windows in which each
    governed-fact query made at today's Madrid date resolves the same variant.
    A query whose window cannot be determined makes the window empty, so the
    runtime never trusts the proofs; a window that intersects to nothing is
    likewise never trusted.

    Raises:
        SnapshotProofPublicationError: ``operation`` already records a proof
            contract, so its builds would not validate fully, or a cell failed
            at or below its revision's declared grade.
    """
    from .temporal import select_revision_metadata

    if operation.snapshot_proof_contract() is not None:
        raise SnapshotProofPublicationError(
            "snapshot proofs must be swept over a database that records no proof contract yet",
        )
    today = today_madrid()
    recorder = _RecordingFactSource(operation, today)
    support = operation.supported_filing_years()
    grades = tuple(RegistryAuthorityGrade)
    proofs: list[SnapshotCrossCheckProof] = []
    failures: list[str] = []
    for modelo_id in operation.modelo_ids():
        directory = operation.modelo_directory(modelo_id)
        periods = sorted(
            {token for revision in directory.revisions for token in revision.period_selector.declared_periods}
        )
        for filing_year in range(support.floor, support.horizon + 1):
            for period in periods:
                try:
                    selected = select_revision_metadata(directory, filing_year=filing_year, period=period, on=None)
                except CadrumoError:
                    continue
                for grade in grades:
                    key = snapshot_proof_key(
                        selected, modelo_id=modelo_id, filing_year=filing_year, period=period, grade=grade
                    )
                    try:
                        snapshot = operation.build_unretained_snapshot(
                            modelo_id,
                            filing_year=filing_year,
                            period=period,
                            grade=grade,
                            governed_facts=recorder,
                        )
                    except CadrumoError as exc:
                        if not _is_expected_ladder_refusal(exc, grade):
                            failures.append(f"{modelo_id} {filing_year} {period} {grade.value}: {exc}")
                        continue
                    if snapshot.revision.id != selected.id:
                        failures.append(
                            f"{modelo_id} {filing_year} {period} {grade.value}: snapshot selected "
                            f"{snapshot.revision.id!r}, directory selected {selected.id!r}"
                        )
                        continue
                    proofs.append(SnapshotCrossCheckProof(key, str(selected.id)))
    if failures:
        raise SnapshotProofPublicationError(
            "declared snapshot selectors fail at or below their declared authority grade:\n"
            + "\n".join(f" - {failure}" for failure in failures),
        )
    window_from, window_to = _intersect_windows(
        _constant_resolution_window(operation, query, today) for query in recorder.wall_clock_queries
    )
    sources = snapshot_validator_closure()
    contract = SnapshotProofContract(
        validator_sources=sources,
        validator_digest=validator_digest(sources),
        window_from=window_from,
        window_to=window_to,
    )
    return SnapshotProofSet(contract=contract, proofs=tuple(proofs))


__all__ = [
    "SNAPSHOT_PROOF_DDL",
    "SNAPSHOT_PROOF_TABLES",
    "SnapshotCrossCheckProof",
    "SnapshotProofContract",
    "SnapshotProofKey",
    "SnapshotProofOperation",
    "SnapshotProofPublicationError",
    "SnapshotProofSet",
    "ValidatorSource",
    "prove_snapshot_selectors",
    "runtime_validator_matches",
    "snapshot_proof_key",
    "snapshot_validator_closure",
    "validator_digest",
]
