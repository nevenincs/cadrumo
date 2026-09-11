"""Round-trip gate engine: a delta-authored edition must mean exactly what its full copy meant.

Moving a modelo from full-copy editions to editions that name a predecessor
changes what is written on disk, never what the registry means. This module
judges one such move by comparing two registry trees -- the modelo before the
move (the reference) and after it (the live tree) -- and proves:

- every edition the live tree publishes equals the edition the reference
  published, by typed equality of the ``ModeloRevision`` dump, compared
  element-wise over the whole edition. Casilla row order is asserted separately
  from casilla content, so an ordering failure reports distinctly from a
  changed row;
- the live casilla rows stand in the merge order: the reference rows rearranged
  the way materialisation orders an edition, as defined below;
- where an edition has an export surface, the canonical filing export path
  emits the same bytes from both trees.

How equality is defined
-----------------------
Models are never compared with ``==``. Pydantic equality also compares the
locale identity fields the dump excludes, and an inherited casilla row
legitimately carries one extra entry in ``localization_keys``: the occurrence
key of the edition that last stated it, placed directly after its own key so
its label still resolves. ``==`` would report that as a difference. Equality
is instead two explicit parts:

- content: the ``ModeloRevision`` dump, which omits every locale identity field,
  minus the ``predecessor`` declaration;
- locale identity, compared separately so a real change is not hidden by the
  dump's omission: the edition, construct and alias keys must be equal; a
  casilla's key chain must be equal, or equal with exactly one key inserted
  after the first where that key is the same casilla's occurrence key in a
  sibling edition; and every casilla label must resolve to the same text in
  every supported output language.

How order is defined
-------------------
A delta-authored edition's row order is defined by the merge, not by its full
copy, whose order is an artefact of fragment filename sorting. So the expected
order is the reference edition's rows rearranged: every row matching a row of
the expected order of the predecessor the live edition declares takes that
row's position, and every other row follows in its reference relative order. A
row matches on ``continuidad_id``, or on ``id`` where neither row carries one.
An edition declaring no predecessor keeps its reference order exactly. The
rearrangement reads only the reference rows and the live predecessor
declaration, never the materialised edition, so it stays independent of the
materialiser it judges; a live order the merge could not have produced, such as
new rows stated out of their reference order, fails.

The two trees
-------------
Both trees are loaded through the real validated authority. Each carries the
judged modelo plus its registry dependency closure -- every modelo it reaches
through dependency classifications, cross-modelo relations and source-modelo
bindings, transitively -- because registry-scope validation refuses a modelo
whose declared sources are absent. Every other modelo is left out, so only the
closure is loaded. :func:`copy_registry_tree` builds such a tree from a live
registry; :func:`materialise_reference_registry` builds one whose judged modelo
is read from a commit with ``git archive``. A reference is refused if any of
its editions names a predecessor, since it would then be judged by the
materialiser under test.

Where the gate stops
--------------------
- The ``predecessor`` declaration is excluded from equality: it is the one
  field a migration must change. So is ``reviewed_against``, which a migration
  adds to carry a reviewed edition's claim forward: the full-copy review saw
  every row the materialised edition now inherits, which is what this gate
  proves, and the schema holds the scope equal to the declared predecessor.
  ``casilla_source_refs`` is excluded too: it is the edition-level default a
  migration introduces to lift restated row references, and every row it fills
  is still compared, so a default that changed any row's references fails.
  Everything else in the edition is compared.
- Shared catalogues and the dependency closure come from the same live tree on
  both sides, so a change to them is outside this comparison. The locale
  catalogue is likewise the live one: labels are compared as the live catalogue
  resolves both key chains.
- Export bytes are compared only for editions with authored export layouts,
  from one draft rendered through each tree's export path. A delta-authored
  edition with an export surface but no declared scenario fails as unchecked,
  never as passing; an edition without a surface is not reported as byte-proven.
  Draft construction calculates from the bundled registry whichever tree is
  selected, so the bytes judge the export surface; formulas and every other
  calculation input are judged by the typed comparison.
- A reference whose commit is absent from the clone fails closed, naming the
  commit, rather than reporting the modelo clean.
- It does not judge delta minimality, grade barriers on a declared
  predecessor, or label coverage; each has its own gate.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
from collections import Counter, deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Final

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.producer_snapshot import FilingProducerSnapshot
from cadrumo.application.filing.runtime import ModeloOperatorProfile, schema_provider_from_authority
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.product_identity import AeatProductSoftwareIdentity
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.bindings import binding_source_modelo
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
    resolve_modelo_localization,
)
from cadrumo.domain.calculations.registry.schema import DeclaredPredecessor, ModeloDefinition, ModeloRevision
from cadrumo.domain.filing.protocols import ModeloInputs
from cadrumo.domain.submission.models import ModeloDraftStatus

from .compiler.authority import compile_validated_authority
from .compiler.loader import load_registry_tree

__all__ = [
    "COMMIT_ID",
    "SYNTHETIC_TAX_ID",
    "EditionExportScenario",
    "ReferenceUnavailableError",
    "RegistryDependencyClosureError",
    "RoundTripFinding",
    "RoundTripFindingKind",
    "RoundTripReport",
    "RowKey",
    "copy_registry_tree",
    "delta_authored_revisions",
    "edition_round_trip_report",
    "localization_differences",
    "materialise_reference_registry",
    "merge_order",
    "merge_orders",
    "modelo_dependency_ids",
    "registry_dependency_closure",
    "run_git",
]


class RoundTripFindingKind(StrEnum):
    """Closed vocabulary of the ways an edition can fail its round trip."""

    REFERENCE_REFUSED = "reference_refused"
    REFERENCE_NOT_FULL_COPY = "reference_not_full_copy"
    LIVE_REFUSED = "live_refused"
    EDITION_SET = "edition_set"
    ROW_ORDER = "row_order"
    CONTENT = "content"
    LOCALIZATION = "localization"
    EXPORT_BYTES = "export_bytes"
    EXPORT_REFUSED = "export_refused"
    EXPORT_UNCHECKED = "export_unchecked"


@dataclass(frozen=True, slots=True)
class RoundTripFinding:
    """One reason a modelo's live editions differ from their reference form."""

    kind: RoundTripFindingKind
    revision_id: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class RoundTripReport:
    """Every finding for one modelo, plus the editions whose bytes were actually compared."""

    findings: tuple[RoundTripFinding, ...]
    byte_compared_revisions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EditionExportScenario:
    """The filing inputs one edition's export bytes are rendered from on both sides.

    ``prior_domiciliation_election`` and ``product_software_identity`` are
    carried only where the modelo's export path requires them: Modelo 303's
    layout renders an envelope prefix and a Nota-3 DID predicate, and refuses
    to run without both, while every other modelo carries neither.
    """

    period: Period
    inputs: ModeloInputs
    producer_snapshot: Callable[[], FilingProducerSnapshot]
    prior_domiciliation_election: PriorDomiciliationElection | None = None
    product_software_identity: AeatProductSoftwareIdentity | None = None


class ReferenceUnavailableError(RuntimeError):
    """The reference tree cannot be read, so the round trip is unchecked."""


class RegistryDependencyClosureError(RuntimeError):
    """A modelo, or a modelo it depends on, is absent from the registry its closure is taken from."""


#: A commit id as git prints it, abbreviated or full.
COMMIT_ID: Final = re.compile(r"^[0-9a-f]{7,64}$")
#: The taxpayer every round-trip draft is built for; synthetic, never a real identity.
SYNTHETIC_TAX_ID: Final = "12345678Z"

_MODELOS_DIR: Final = "modelos"
_EXCLUDED_FROM_EQUALITY: Final = frozenset({"predecessor", "reviewed_against", "casilla_source_refs"})
_GIT_TIMEOUT_SECONDS: Final = 120
#: Variables that would point git at a repository other than the one named.
_GIT_LOCATION_VARIABLES: Final = frozenset(
    {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR"}
)


# ── the dependency closure ──────────────────────────────────────────────────


def modelo_dependency_ids(modelo: ModeloDefinition) -> frozenset[str]:
    """Every other modelo one modelo's editions name as a source.

    These are the references registry-scope validation resolves across modelos:
    dependency classifications, cross-modelo relations, and bindings whose
    typed selector names a source modelo.
    """
    sources: set[str] = set()
    for revision in modelo.revisions.values():
        sources.update(str(classification.source_modelo) for classification in revision.dependency_classifications)
        sources.update(str(relation.source_modelo) for relation in revision.relations)
        for binding in revision.bindings:
            source = binding_source_modelo(binding)
            if source is not None:
                sources.add(str(source))
    sources.discard(str(modelo.id))
    return frozenset(sources)


def registry_dependency_closure(modelos: Iterable[ModeloDefinition], modelo_id: str) -> frozenset[str]:
    """``modelo_id`` plus every modelo it reaches through :func:`modelo_dependency_ids`, transitively.

    Raises:
        RegistryDependencyClosureError: When ``modelo_id`` or any modelo in its
            closure is not among ``modelos``, naming the modelo that needs it.
    """
    by_id = {str(modelo.id): modelo for modelo in modelos}
    if modelo_id not in by_id:
        raise RegistryDependencyClosureError(f"registry holds no modelo {modelo_id!r}")
    closure: set[str] = {modelo_id}
    pending = deque([modelo_id])
    while pending:
        current = pending.popleft()
        for dependency in sorted(modelo_dependency_ids(by_id[current])):
            if dependency in closure:
                continue
            if dependency not in by_id:
                raise RegistryDependencyClosureError(
                    f"modelo {current!r} in the dependency closure of modelo {modelo_id!r} names source modelo "
                    f"{dependency!r}, which the registry does not hold",
                )
            closure.add(dependency)
            pending.append(dependency)
    return frozenset(closure)


def copy_registry_tree(source: Path, destination: Path, *, modelo_id: str | None) -> Path:
    """Copy a registry root keeping ``modelo_id`` and its dependency closure, or no modelo for ``None``.

    Every non-modelo family is copied whole. The closure is read from the
    source tree's typed declarations through the registry loader.

    Raises:
        RegistryDependencyClosureError: When the source lacks ``modelo_id`` or a
            modelo its closure needs, so the copy could not load.
    """
    kept = frozenset[str]()
    if modelo_id is not None:
        modelos, _catalogues = load_registry_tree(source)
        kept = registry_dependency_closure(modelos, modelo_id)
    modelos_dir = source / _MODELOS_DIR

    def ignore(directory: str, names: list[str]) -> list[str]:
        if Path(directory) != modelos_dir:
            return []
        return [name for name in names if name not in kept]

    shutil.copytree(source, destination, ignore=ignore)
    return destination


def materialise_reference_registry(
    *,
    repo_root: Path,
    registry_relative: PurePosixPath,
    modelo_id: str,
    base_commit: str,
    destination: Path,
) -> Path:
    """Build a registry tree holding ``modelo_id`` exactly as committed at ``base_commit``.

    Every other registry family, and the modelo's dependency closure, is
    copied from the live tree, so the result differs from the live copy only
    in the one modelo's files.

    Raises:
        ReferenceUnavailableError: When the commit is not in this clone or does
            not contain the modelo, so no reference exists to compare against.
        RegistryDependencyClosureError: When the live tree lacks the modelo or
            a modelo its closure needs.
    """
    if not COMMIT_ID.match(base_commit):
        raise ReferenceUnavailableError(f"base commit {base_commit!r} is not a commit id")
    probe = run_git(repo_root, "cat-file", "-e", f"{base_commit}^{{commit}}")
    if probe.returncode != 0:
        raise ReferenceUnavailableError(
            f"base commit {base_commit} is not in this clone's history, so modelo {modelo_id} is unchecked; "
            "fetch full history (for a CI checkout, fetch-depth: 0) and re-run",
        )
    modelo_path = registry_relative / _MODELOS_DIR / modelo_id
    archive = run_git(repo_root, "archive", "--format=tar", base_commit, "--", modelo_path.as_posix())
    if archive.returncode != 0:
        raise ReferenceUnavailableError(
            f"base commit {base_commit} holds no {modelo_path.as_posix()}: "
            f"{archive.stderr.decode('utf-8', 'replace').strip()}",
        )
    copy_registry_tree(repo_root.joinpath(*registry_relative.parts), destination, modelo_id=modelo_id)
    shutil.rmtree(destination / _MODELOS_DIR / modelo_id)
    staging = destination.parent / f"{destination.name}.archive"
    with tarfile.open(fileobj=BytesIO(archive.stdout)) as tar:
        tar.extractall(staging, filter="data")
    shutil.move(staging.joinpath(*modelo_path.parts), destination / _MODELOS_DIR / modelo_id)
    shutil.rmtree(staging)
    return destination


def run_git(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    """Run git in ``repo_root`` with every variable that could redirect it to another repository removed."""
    environment = {name: value for name, value in os.environ.items() if name not in _GIT_LOCATION_VARIABLES}
    return subprocess.run(  # noqa: S603 - fixed git argv, no shell
        ["git", "-c", "core.autocrlf=false", *arguments],  # noqa: S607 - git is resolved from PATH by design
        cwd=repo_root,
        env=environment,
        capture_output=True,
        check=False,
        timeout=_GIT_TIMEOUT_SECONDS,
    )


# ── the gate ────────────────────────────────────────────────────────────────


def edition_round_trip_report(
    *,
    live_registry_root: Path,
    reference_registry_root: Path,
    modelo_id: str,
    export_scenarios: Mapping[str, EditionExportScenario],
) -> RoundTripReport:
    """Compare one modelo's live editions against its reference editions."""
    try:
        reference = _load_modelo(reference_registry_root, modelo_id)
    except RegistryError as exc:
        return _refused(RoundTripFindingKind.REFERENCE_REFUSED, exc)
    try:
        live = _load_modelo(live_registry_root, modelo_id)
    except RegistryError as exc:
        return _refused(RoundTripFindingKind.LIVE_REFUSED, exc)

    findings: list[RoundTripFinding] = [
        RoundTripFinding(
            RoundTripFindingKind.REFERENCE_NOT_FULL_COPY,
            revision_id,
            "the pre-migration edition names a predecessor, so it would be judged by the materialiser under test",
        )
        for revision_id in delta_authored_revisions(reference)
    ]
    findings.extend(_edition_set_findings(reference, live))
    expected_orders = merge_orders(reference, live)
    for revision_id, reference_revision in reference.revisions.items():
        live_revision = live.revisions.get(revision_id)
        if live_revision is not None:
            findings.extend(
                _edition_findings(revision_id, reference_revision, live_revision, expected_orders[revision_id])
            )
            locale_differences = localization_differences(
                modelo_id=modelo_id,
                sibling_revision_ids=frozenset(reference.revisions) - {revision_id},
                reference=reference_revision,
                live=live_revision,
            )
            if locale_differences:
                findings.append(
                    RoundTripFinding(RoundTripFindingKind.LOCALIZATION, revision_id, "; ".join(locale_differences))
                )
    export_findings, compared = _export_findings(
        live_registry_root=live_registry_root,
        reference_registry_root=reference_registry_root,
        live=live,
        export_scenarios=export_scenarios,
    )
    findings.extend(export_findings)
    return RoundTripReport(findings=tuple(findings), byte_compared_revisions=compared)


def delta_authored_revisions(modelo: ModeloDefinition) -> tuple[str, ...]:
    """The editions of ``modelo`` that name a predecessor."""
    return tuple(
        revision_id
        for revision_id, revision in modelo.revisions.items()
        if isinstance(revision.predecessor, DeclaredPredecessor)
    )


def _refused(kind: RoundTripFindingKind, exc: RegistryError) -> RoundTripReport:
    return RoundTripReport(
        findings=(RoundTripFinding(kind, None, f"{type(exc).__name__}: {exc}"),),
        byte_compared_revisions=(),
    )


def _load_modelo(registry_root: Path, modelo_id: str) -> ModeloDefinition:
    return compile_validated_authority(registry_root, bundled_path()).modelo(modelo_id)


def _edition_set_findings(reference: ModeloDefinition, live: ModeloDefinition) -> list[RoundTripFinding]:
    missing = sorted(set(reference.revisions) - set(live.revisions))
    added = sorted(set(live.revisions) - set(reference.revisions))
    if not missing and not added:
        return []
    return [
        RoundTripFinding(
            RoundTripFindingKind.EDITION_SET,
            None,
            f"editions missing after migration {missing!r}, editions added by migration {added!r}",
        )
    ]


type RowKey = tuple[str, str | None]
"""A casilla row as the merge order sees it: its ``id`` and its ``continuidad_id``."""


def _match_key(row: RowKey) -> tuple[str, str]:
    casilla_id, lineage = row
    return ("lineage", lineage) if lineage is not None else ("id", casilla_id)


def merge_order(full_copy: tuple[RowKey, ...], predecessor_order: tuple[RowKey, ...]) -> tuple[RowKey, ...]:
    """Rearrange one edition's full-copy rows into the order its merge with ``predecessor_order`` defines.

    Each predecessor row, in order, places the first unplaced full-copy row
    matching it; every full-copy row left unplaced follows in full-copy order.
    """
    positions: dict[tuple[str, str], deque[int]] = {}
    for index, row in enumerate(full_copy):
        positions.setdefault(_match_key(row), deque()).append(index)
    order = [queue.popleft() for row in predecessor_order if (queue := positions.get(_match_key(row)))]
    placed = frozenset(order)
    order.extend(index for index in range(len(full_copy)) if index not in placed)
    return tuple(full_copy[index] for index in order)


def merge_orders(reference: ModeloDefinition, live: ModeloDefinition) -> dict[str, tuple[RowKey, ...]]:
    """Every reference edition's rows in the merge order its live predecessor declaration defines.

    A live declaration naming an edition the reference lacks, or closing a
    cycle, leaves the edition in its reference order; the edition-set finding
    and the live load report those trees respectively.
    """
    orders: dict[str, tuple[RowKey, ...]] = {}

    def order_of(revision_id: str, trail: frozenset[str]) -> tuple[RowKey, ...]:
        cached = orders.get(revision_id)
        if cached is not None:
            return cached
        rows = tuple(
            (str(casilla.id), str(casilla.continuidad_id) if casilla.continuidad_id is not None else None)
            for casilla in reference.revisions[revision_id].casillas
        )
        live_revision = live.revisions.get(revision_id)
        declared = None if live_revision is None else live_revision.predecessor
        if isinstance(declared, DeclaredPredecessor):
            predecessor_id = str(declared.revision_id)
            if predecessor_id in reference.revisions and predecessor_id not in trail:
                rows = merge_order(rows, order_of(predecessor_id, trail | {revision_id}))
        orders[revision_id] = rows
        return rows

    for revision_id in reference.revisions:
        order_of(revision_id, frozenset({revision_id}))
    return orders


def _edition_findings(
    revision_id: str,
    reference: ModeloRevision,
    live: ModeloRevision,
    expected_order: tuple[RowKey, ...],
) -> list[RoundTripFinding]:
    """Order of casilla rows against the merge order, then the whole edition element-wise with rows aligned by id."""
    findings: list[RoundTripFinding] = []
    expected_ids = [casilla_id for casilla_id, _ in expected_order]
    live_ids = [str(casilla.id) for casilla in live.casillas]
    if expected_ids != live_ids and Counter(expected_ids) == Counter(live_ids):
        position = next(
            index for index, pair in enumerate(zip(expected_ids, live_ids, strict=True)) if pair[0] != pair[1]
        )
        findings.append(
            RoundTripFinding(
                RoundTripFindingKind.ROW_ORDER,
                revision_id,
                f"casilla rows first diverge from the merge order at position {position}: "
                f"expected {expected_ids[position]!r}, live {live_ids[position]!r}",
            )
        )
    reference_dump = reference.model_dump(exclude=set(_EXCLUDED_FROM_EQUALITY))
    live_dump = live.model_dump(exclude=set(_EXCLUDED_FROM_EQUALITY))
    changed_fields = sorted(
        name
        for name in reference_dump.keys() | live_dump.keys()
        if name != "casillas" and reference_dump.get(name) != live_dump.get(name)
    )
    row_differences = _casilla_row_differences(reference_dump["casillas"], live_dump["casillas"])
    if changed_fields or row_differences:
        findings.append(
            RoundTripFinding(
                RoundTripFindingKind.CONTENT,
                revision_id,
                "; ".join(
                    ([f"edition fields changed {changed_fields!r}"] if changed_fields else []) + row_differences,
                ),
            )
        )
    return findings


def _casilla_row_differences(reference_rows: list[dict[str, object]], live_rows: list[dict[str, object]]) -> list[str]:
    reference_counts = Counter(str(row["id"]) for row in reference_rows)
    live_counts = Counter(str(row["id"]) for row in live_rows)
    differences: list[str] = []
    missing = sorted((reference_counts - live_counts).elements())
    added = sorted((live_counts - reference_counts).elements())
    if missing:
        differences.append(f"casilla rows missing {missing!r}")
    if added:
        differences.append(f"casilla rows added {added!r}")
    live_by_id = {str(row["id"]): row for row in live_rows}
    for row in reference_rows:
        row_id = str(row["id"])
        live_row = live_by_id.get(row_id)
        if live_row is None or live_row == row:
            continue
        changed = sorted(key for key in row.keys() | live_row.keys() if row.get(key) != live_row.get(key))
        differences.append(f"casilla {row_id!r} changed {changed!r}")
    return differences


def localization_differences(
    *,
    modelo_id: str,
    sibling_revision_ids: frozenset[str],
    reference: ModeloRevision,
    live: ModeloRevision,
) -> list[str]:
    """The locale identity the dump omits, compared under the rule the module docstring states."""
    differences: list[str] = []
    if reference.localization_key != live.localization_key:
        differences.append(f"edition key {reference.localization_key!r} became {live.localization_key!r}")
    reference_constructs = [(construct.id, construct.localization_key) for construct in reference.constructs]
    live_constructs = [(construct.id, construct.localization_key) for construct in live.constructs]
    if reference_constructs != live_constructs:
        differences.append("construct keys changed")
    live_by_id = {casilla.id: casilla for casilla in live.casillas}
    for casilla in reference.casillas:
        live_casilla = live_by_id.get(casilla.id)
        if live_casilla is None:
            continue
        reference_aliases = [alias.localization_key for alias in casilla.aliases]
        if reference_aliases != [alias.localization_key for alias in live_casilla.aliases]:
            differences.append(f"casilla {casilla.id!r} alias keys changed")
        chain = _key_chain_difference(
            modelo_id=modelo_id,
            sibling_revision_ids=sibling_revision_ids,
            casilla_id=casilla.id,
            reference_keys=casilla.localization_keys,
            live_keys=live_casilla.localization_keys,
        )
        if chain is not None:
            differences.append(f"casilla {casilla.id!r} {chain}")
        for language in SUPPORTED_OUTPUT_LANGUAGES:
            before = resolve_modelo_localization(casilla.localization_keys, locale=language)
            after = resolve_modelo_localization(live_casilla.localization_keys, locale=language)
            if before != after:
                differences.append(f"casilla {casilla.id!r} label in {language!r} changed from {before!r} to {after!r}")
    return differences


def _key_chain_difference(
    *,
    modelo_id: str,
    sibling_revision_ids: frozenset[str],
    casilla_id: str,
    reference_keys: tuple[str, ...],
    live_keys: tuple[str, ...],
) -> str | None:
    if live_keys == reference_keys:
        return None
    inherited_fallbacks = {
        casilla_occurrence_locale_key(modelo_id, sibling, casilla_id, ModeloLocalizationFieldKind.LABEL)
        for sibling in sibling_revision_ids
    }
    if (
        len(live_keys) == len(reference_keys) + 1
        and live_keys[:1] == reference_keys[:1]
        and live_keys[2:] == reference_keys[1:]
        and live_keys[1] in inherited_fallbacks
    ):
        return None
    return f"key chain {list(reference_keys)!r} became {list(live_keys)!r}"


def _export_findings(
    *,
    live_registry_root: Path,
    reference_registry_root: Path,
    live: ModeloDefinition,
    export_scenarios: Mapping[str, EditionExportScenario],
) -> tuple[list[RoundTripFinding], tuple[str, ...]]:
    with_surface = {revision_id for revision_id, revision in live.revisions.items() if revision.export_layouts}
    findings = [
        RoundTripFinding(
            RoundTripFindingKind.EXPORT_UNCHECKED,
            revision_id,
            "delta-authored edition has an export surface but no export scenario, so its bytes are unchecked",
        )
        for revision_id in sorted((set(delta_authored_revisions(live)) & with_surface) - set(export_scenarios))
    ]
    findings.extend(
        RoundTripFinding(
            RoundTripFindingKind.EXPORT_UNCHECKED,
            revision_id,
            "an export scenario is declared for an edition with no export surface",
        )
        for revision_id in sorted(set(export_scenarios) - with_surface)
    )
    compared: list[str] = []
    for revision_id in sorted(set(export_scenarios) & with_surface):
        finding = _export_bytes_finding(
            live_registry_root=live_registry_root,
            reference_registry_root=reference_registry_root,
            modelo_id=str(live.id),
            revision_id=revision_id,
            scenario=export_scenarios[revision_id],
        )
        if finding is None:
            compared.append(revision_id)
        else:
            findings.append(finding)
            if finding.kind is RoundTripFindingKind.EXPORT_BYTES:
                compared.append(revision_id)
    return findings, tuple(compared)


@dataclass(slots=True)
class _PayloadSink:
    """Keeps the validated in-memory payload so no plaintext export touches disk."""

    payload: bytes = b""

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        self.payload = payload.payload


def _export_bytes_finding(
    *,
    live_registry_root: Path,
    reference_registry_root: Path,
    modelo_id: str,
    revision_id: str,
    scenario: EditionExportScenario,
) -> RoundTripFinding | None:
    """Render one draft through both trees' canonical export path and compare the bytes."""
    rendered: dict[str, bytes] = {}
    draft = None
    for side, root in (("live", live_registry_root), ("pre-migration", reference_registry_root)):
        provider = schema_provider_from_authority(
            compile_validated_authority(root, bundled_path()),
            modelos=(modelo_id,),
            filing_year=scenario.period.filing_year,
            period=scenario.period,
        )
        try:
            if draft is None:
                draft = build_draft(
                    modelo=modelo_id,
                    period=scenario.period,
                    profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Round-trip export"),
                    inputs=scenario.inputs,
                    schema_provider=provider,
                ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
                if draft.snapshot_ref.revision_id != revision_id:
                    return RoundTripFinding(
                        RoundTripFindingKind.EXPORT_UNCHECKED,
                        revision_id,
                        f"the scenario period selects edition {draft.snapshot_ref.revision_id!r}",
                    )
            sink = _PayloadSink()
            export_draft(
                draft,
                payload_consumer=sink,
                producer_snapshot=scenario.producer_snapshot(),
                prior_domiciliation_election=scenario.prior_domiciliation_election,
                product_software_identity=scenario.product_software_identity,
                schema_provider=provider,
            )
        except ValueError as exc:
            return RoundTripFinding(
                RoundTripFindingKind.EXPORT_REFUSED,
                revision_id,
                f"{side} export refused: {type(exc).__name__}: {exc}",
            )
        rendered[side] = sink.payload
    live_bytes, reference_bytes = rendered["live"], rendered["pre-migration"]
    if live_bytes == reference_bytes:
        return None
    offset = next(
        (index for index, pair in enumerate(zip(live_bytes, reference_bytes, strict=False)) if pair[0] != pair[1]),
        min(len(live_bytes), len(reference_bytes)),
    )
    return RoundTripFinding(
        RoundTripFindingKind.EXPORT_BYTES,
        revision_id,
        f"export bytes first differ at offset {offset} ({len(reference_bytes)} pre-migration, {len(live_bytes)} live)",
    )
