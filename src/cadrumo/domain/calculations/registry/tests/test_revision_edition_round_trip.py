"""Round-trip gate: a delta-authored edition must mean exactly what its full copy meant.

Moving a modelo from full-copy editions to editions that name a predecessor
changes what is written on disk, never what the registry means. This gate is
the acceptance evidence for each such move. For a migrated modelo it proves:

- every edition the live authority publishes equals the edition the
  pre-migration authority published, by typed equality of the
  ``ModeloRevision`` dump, compared element-wise over the whole edition. Casilla
  row order is asserted separately from casilla content, so an ordering failure
  reports distinctly from a changed row;
- the live casilla rows stand in the merge order: the pre-migration rows
  rearranged the way materialisation orders an edition, as defined below;
- where an edition has an export surface, the canonical filing export path
  emits the same bytes from both authorities.

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
order is the pre-migration edition's rows rearranged: every row matching a row
of the expected order of the predecessor the live edition declares takes that
row's position, and every other row follows in its pre-migration relative
order. A row matches on ``continuidad_id``, or on ``id`` where neither row
carries one. An edition declaring no predecessor keeps its pre-migration order
exactly. The rearrangement reads only the pre-migration rows and the live
predecessor declaration, never the materialised edition, so it stays
independent of the materialiser it judges; a live order the merge could not
have produced, such as new rows stated out of their pre-migration order, fails.

What the reference is, and why
------------------------------
The reference is the modelo's own directory as committed at a recorded base
commit -- the last commit holding its full-copy form -- read with ``git
archive`` into a temporary registry tree and loaded through the real
authority. The live side is the working-tree directory loaded the same way.
Both trees share the live non-modelo catalogues, so the only difference
between them is the modelo's own files: exactly what a migration touches.

That reference is the literal pre-migration materialisation: the loader over
the files the migration replaced. It is independent of the code under test
because a full-copy edition never enters inheritance -- the reference is
refused outright if any of its editions names a predecessor -- and it is not a
frozen value: nothing is generated, stored, or regenerated from the code being
judged, so it cannot drift into agreement with a defect. A stored digest was
rejected because it would have to be produced by the implementation it later
judges, and a failure against it could name no row.

Where the gate stops
--------------------
- Eligibility comes from what editions declare. A modelo with an edition
  naming a predecessor must carry an entry below; an entry for a modelo none of
  whose editions names one is refused as stale. A modelo with neither is
  unmigrated and has nothing to accept.
- The ``predecessor`` declaration is excluded from equality: it is the one
  field a migration must change. So is ``reviewed_against``, which a migration
  adds to carry a reviewed edition's claim forward: the full-copy review saw
  every row the materialised edition now inherits, which is what this gate
  proves, and the schema holds the scope equal to the declared predecessor.
  ``casilla_source_refs`` is excluded too: it is the edition-level default a
  migration introduces to lift restated row references, and every row it fills
  is still compared, so a default that changed any row's references fails.
  Everything else in the edition is compared.
- Shared catalogues are taken from the live tree on both sides, so a change to
  the legal, source, or category catalogues is outside this comparison. The
  locale catalogue is likewise the live one: labels are compared as the live
  catalogue resolves both key chains, not against the catalogue as committed at
  the base.
- Export bytes are compared only for editions with authored export layouts,
  from one draft rendered through each tree's export path. A delta-authored
  edition with an export surface but no declared scenario fails as unchecked,
  never as passing; an edition without a surface is not reported as byte-proven.
  Draft construction calculates from the bundled registry whichever tree is
  selected, so the bytes judge the export surface; formulas and every other
  calculation input are judged by the typed comparison.
- The base commit must be present in the clone. A shallow checkout that lacks
  it fails closed, naming the commit, rather than reporting the modelo clean.
- A successor authored delta-first has no full-copy form and no baseline;
  nothing here can say whether it inherited a row its author meant to drop.
- It does not judge delta minimality, grade barriers on a declared
  predecessor, or label coverage; each has its own gate.

Lifecycle and retirement
------------------------
An entry is added in the change that migrates its modelo, naming the commit
immediately before that change. Once the migration has landed and a later,
deliberate change alters that modelo's meaning, the entry is converted to an
accepted migration naming the commit whose round trip passed; comparison stops
for that modelo and the conversion is the reviewable record of why. The gate
is retired, with its table, after the last modelo's migration is accepted:
from then on every edition is authored delta-first and has no full-copy form
to round-trip against.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tarfile
import tomllib
from collections import Counter, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Final

import pytest

from .....application.filing.draft_construction import build_draft
from .....application.filing.export import export_draft
from .....application.filing.export_verification import FilingExportValidatedPayload
from .....application.filing.producer_snapshot import (
    FilingElectionFacts,
    FilingProducerSnapshot,
    GeneralFilingProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from .....application.filing.runtime import ModeloOperatorProfile, build_runtime_schema_provider
from .....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from .....core.i18n.render import override_locales_root
from .....core.modelo import Modelo
from .....core.payment_election import PaymentElection
from .....core.period import Period
from .....core.prior_domiciliation_election import PriorDomiciliationElection
from .....core.refund_election import RefundElection
from .....core.resources.bundled_data import bundled_path
from .....core.result_disposition import ResultDisposition
from .....domain.filing.protocols import ModeloInputs
from .....domain.submission.models import ModeloDraftStatus
from .....tests.inventory import REPO_ROOT
from ..authority import ValidatedRegistryAuthority, bundled_authority
from ..errors import RegistryError
from ..modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
    resolve_modelo_localization,
)
from ..schema import DeclaredPredecessor, ModeloDefinition, ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
    """One reason a modelo's live editions differ from their pre-migration form."""

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
    """The filing inputs one edition's export bytes are rendered from on both sides."""

    period: Period
    inputs: ModeloInputs
    producer_snapshot: Callable[[], FilingProducerSnapshot]


@dataclass(frozen=True, slots=True)
class PreMigrationBaseline:
    """A migrated modelo compared against its directory at ``base_commit``."""

    base_commit: str
    export_scenarios: Mapping[str, EditionExportScenario] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AcceptedMigration:
    """A migrated modelo whose round trip passed at ``accepted_commit`` and is no longer compared."""

    accepted_commit: str
    reason: str


class ReferenceUnavailableError(RuntimeError):
    """The pre-migration tree cannot be read, so the round trip is unchecked."""


#: One entry per modelo whose editions name a predecessor. Empty until the
#: first modelo migrates; see the module docstring for the entry lifecycle.
_MIGRATIONS: Final[Mapping[str, PreMigrationBaseline | AcceptedMigration]] = dict[
    str, PreMigrationBaseline | AcceptedMigration
]()

_BUNDLED_REGISTRY: Final = bundled_path("registry", "aeat")
_MODELOS_DIR: Final = "modelos"
_EXCLUDED_FROM_EQUALITY: Final = frozenset({"predecessor", "reviewed_against", "casilla_source_refs"})
_COMMIT_ID = re.compile(r"^[0-9a-f]{7,64}$")
_GIT_TIMEOUT_SECONDS: Final = 120
#: Variables that would point git at a repository other than the one named.
_GIT_LOCATION_VARIABLES: Final = frozenset(
    {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR"}
)
_SYNTHETIC_TAX_ID: Final = "12345678Z"


# ── the gate ────────────────────────────────────────────────────────────────


def materialise_reference_registry(
    *,
    repo_root: Path,
    registry_relative: PurePosixPath,
    modelo_id: str,
    base_commit: str,
    destination: Path,
) -> Path:
    """Build a registry tree holding ``modelo_id`` exactly as committed at ``base_commit``.

    Every other registry family is copied from the live tree, so the result
    differs from the live registry only in the one modelo's files.

    Raises:
        ReferenceUnavailableError: When the commit is not in this clone or does
            not contain the modelo, so no reference exists to compare against.
    """
    if not _COMMIT_ID.match(base_commit):
        raise ReferenceUnavailableError(f"base commit {base_commit!r} is not a commit id")
    probe = _git(repo_root, "cat-file", "-e", f"{base_commit}^{{commit}}")
    if probe.returncode != 0:
        raise ReferenceUnavailableError(
            f"base commit {base_commit} is not in this clone's history, so modelo {modelo_id} is unchecked; "
            "fetch full history (for a CI checkout, fetch-depth: 0) and re-run",
        )
    modelo_path = registry_relative / _MODELOS_DIR / modelo_id
    archive = _git(repo_root, "archive", "--format=tar", base_commit, "--", modelo_path.as_posix())
    if archive.returncode != 0:
        raise ReferenceUnavailableError(
            f"base commit {base_commit} holds no {modelo_path.as_posix()}: "
            f"{archive.stderr.decode('utf-8', 'replace').strip()}",
        )
    copy_registry_tree(repo_root.joinpath(*registry_relative.parts), destination, modelo_id=None)
    staging = destination.parent / f"{destination.name}.archive"
    with tarfile.open(fileobj=BytesIO(archive.stdout)) as tar:
        tar.extractall(staging, filter="data")
    shutil.move(staging.joinpath(*modelo_path.parts), destination / _MODELOS_DIR / modelo_id)
    shutil.rmtree(staging)
    return destination


def copy_registry_tree(source: Path, destination: Path, *, modelo_id: str | None) -> Path:
    """Copy a registry root keeping at most one modelo, so only that modelo is loaded."""
    modelos = source / _MODELOS_DIR

    def ignore(directory: str, names: list[str]) -> list[str]:
        if Path(directory) != modelos:
            return []
        return [name for name in names if name != modelo_id]

    shutil.copytree(source, destination, ignore=ignore)
    return destination


def edition_round_trip_report(
    *,
    live_registry_root: Path,
    reference_registry_root: Path,
    modelo_id: str,
    export_scenarios: Mapping[str, EditionExportScenario],
) -> RoundTripReport:
    """Compare one modelo's live editions against its pre-migration editions."""
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
        for revision_id in _delta_authored(reference)
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


def _refused(kind: RoundTripFindingKind, exc: RegistryError) -> RoundTripReport:
    return RoundTripReport(
        findings=(RoundTripFinding(kind, None, f"{type(exc).__name__}: {exc}"),),
        byte_compared_revisions=(),
    )


def _load_modelo(registry_root: Path, modelo_id: str) -> ModeloDefinition:
    return ValidatedRegistryAuthority.load(registry_root, source_root=bundled_path()).modelo(modelo_id)


def _delta_authored(modelo: ModeloDefinition) -> tuple[str, ...]:
    return tuple(
        revision_id
        for revision_id, revision in modelo.revisions.items()
        if isinstance(revision.predecessor, DeclaredPredecessor)
    )


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
    """Every pre-migration edition's rows in the merge order its live predecessor declaration defines.

    A live declaration naming an edition the reference lacks, or closing a
    cycle, leaves the edition in its pre-migration order; the edition-set
    finding and the live load report those trees respectively.
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
        for revision_id in sorted((set(_delta_authored(live)) & with_surface) - set(export_scenarios))
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
        provider = build_runtime_schema_provider(
            root,
            source_root=bundled_path(),
            modelos=(modelo_id,),
            filing_year=scenario.period.filing_year,
            period=scenario.period,
        )
        try:
            if draft is None:
                draft = build_draft(
                    modelo=modelo_id,
                    period=scenario.period,
                    profile=ModeloOperatorProfile(tax_id=_SYNTHETIC_TAX_ID, display_name="Round-trip export"),
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


def _git(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    environment = {name: value for name, value in os.environ.items() if name not in _GIT_LOCATION_VARIABLES}
    return subprocess.run(  # noqa: S603 - fixed git argv, no shell
        ["git", "-c", "core.autocrlf=false", *arguments],  # noqa: S607 - git is resolved from PATH by design
        cwd=repo_root,
        env=environment,
        capture_output=True,
        check=False,
        timeout=_GIT_TIMEOUT_SECONDS,
    )


# ── the bundled corpus ──────────────────────────────────────────────────────


def _bundled_modelo_ids() -> tuple[str, ...]:
    return tuple(sorted(path.name for path in (_BUNDLED_REGISTRY / _MODELOS_DIR).iterdir() if path.is_dir()))


@pytest.mark.parametrize("modelo_id", sorted(set(_bundled_modelo_ids()) | set(_MIGRATIONS)))
def test_every_bundled_modelo_either_is_unmigrated_or_round_trips(modelo_id: str, tmp_path: Path) -> None:
    """A modelo naming a predecessor anywhere must round-trip against its recorded full-copy form."""
    modelo = bundled_authority().modelo(modelo_id)
    delta_authored = _delta_authored(modelo)
    entry = _MIGRATIONS.get(modelo_id)
    if entry is None:
        assert not delta_authored, (
            f"modelo {modelo_id} editions {delta_authored!r} name a predecessor but no pre-migration "
            "baseline is recorded, so the migration is unchecked"
        )
        return
    assert delta_authored, f"modelo {modelo_id} has a migration entry but no edition names a predecessor"
    if isinstance(entry, AcceptedMigration):
        assert _COMMIT_ID.match(entry.accepted_commit), entry
        assert entry.reason.strip(), entry
        return
    registry_relative = PurePosixPath(_BUNDLED_REGISTRY.resolve().relative_to(REPO_ROOT.resolve()).as_posix())
    reference = materialise_reference_registry(
        repo_root=REPO_ROOT,
        registry_relative=registry_relative,
        modelo_id=modelo_id,
        base_commit=entry.base_commit,
        destination=tmp_path / "pre-migration" / "registry" / "aeat",
    )
    live = copy_registry_tree(_BUNDLED_REGISTRY, tmp_path / "live" / "registry" / "aeat", modelo_id=modelo_id)
    report = edition_round_trip_report(
        live_registry_root=live,
        reference_registry_root=reference,
        modelo_id=modelo_id,
        export_scenarios=entry.export_scenarios,
    )
    assert report.findings == ()


# ── detector teeth on temporary trees ───────────────────────────────────────
#
# Each proof commits real bundled modelo directories into a throwaway git
# repository, reads the reference back through ``git archive`` exactly as the
# corpus gate does, then plants a migration in a separate live tree. Modelo 303
# carries the inheritance proofs: its 2025 edition restates two rows identically
# to the September-2024 edition, so a correct migration genuinely inherits
# them; its 2026 edition inserts a row mid-sequence, which inheritance appends,
# and its September-2024 edition adds several rows, whose stated order the merge
# keeps. Modelo 131 carries the byte proof, exporting from general filing facts.

_CASILLA_ROW_HEADER = re.compile(r'^\[\[revisions\.(?:"[^"\n]+"|[^".\]\n]+)\.casillas\]\]$', re.MULTILINE)
_SCRATCH_REGISTRY = PurePosixPath("registry/aeat")
_M303 = "303"
_M303_SUMMER_2024 = "2024-hasta-08-y-2t"
_M303_SEPTEMBER_2024 = "2024-desde-09-y-3t"
_M303_2025 = "2025"
_M303_2026 = "2026-y-siguientes"
_M131 = "131"
_M131_2024 = "2024"
_M131_2025 = "2025"


@dataclass(frozen=True, slots=True)
class _ScratchRepository:
    root: Path
    base_commit: str


def _init_scratch_repository(root: Path, modelo_ids: tuple[str, ...]) -> _ScratchRepository:
    registry = root.joinpath(*_SCRATCH_REGISTRY.parts)
    copy_registry_tree(_BUNDLED_REGISTRY, registry, modelo_id=None)
    for modelo_id in modelo_ids:
        shutil.copytree(_BUNDLED_REGISTRY / _MODELOS_DIR / modelo_id, registry / _MODELOS_DIR / modelo_id)
    identity = ("-c", "user.name=Round trip", "-c", "user.email=round-trip@example.invalid")
    for arguments in (
        ("init", "--quiet"),
        ("add", "--all"),
        (*identity, "-c", "commit.gpgsign=false", "commit", "--quiet", "--no-verify", "-m", "full-copy corpus"),
    ):
        completed = _git(root, *arguments)
        assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    head = _git(root, "rev-parse", "HEAD")
    return _ScratchRepository(root=root, base_commit=head.stdout.decode("ascii").strip())


def _reference_for(repository: _ScratchRepository, modelo_id: str, destination: Path) -> Path:
    return materialise_reference_registry(
        repo_root=repository.root,
        registry_relative=_SCRATCH_REGISTRY,
        modelo_id=modelo_id,
        base_commit=repository.base_commit,
        destination=destination,
    )


def _live_tree(repository: _ScratchRepository, modelo_id: str, destination: Path) -> Path:
    return copy_registry_tree(repository.root.joinpath(*_SCRATCH_REGISTRY.parts), destination, modelo_id=modelo_id)


def _split_casilla_rows(text: str) -> tuple[str, list[str]]:
    starts = [match.start() for match in _CASILLA_ROW_HEADER.finditer(text)]
    if not starts:
        return text, []
    bounds = [*starts, len(text)]
    return text[: starts[0]], [text[bounds[index] : bounds[index + 1]] for index in range(len(starts))]


def _row_of(block: str) -> dict[str, object]:
    (revision,) = tomllib.loads(block)["revisions"].values()
    (row,) = revision["casillas"]
    assert isinstance(row, dict), block
    return dict[str, object](row)


def _raw_rows(edition_dir: Path) -> list[dict[str, object]]:
    return [
        _row_of(block)
        for fragment in sorted((edition_dir / "casillas").glob("*.toml"))
        for block in _split_casilla_rows(fragment.read_text(encoding="utf-8"))[1]
    ]


def _rows_stated_identically(modelo_dir: Path, *, successor: str, predecessor: str) -> frozenset[str]:
    """Successor rows whose authored table equals the predecessor row carrying the same lineage.

    A row stating a lineage claim is never among them: an inherited row carries
    no ``continuidad_origin`` or ``continuidad_evidence``, so dropping it would
    lose the claim however identical it is.
    """
    by_lineage = {
        row["continuidad_id"]: row
        for row in _raw_rows(modelo_dir / "revisions" / predecessor)
        if row.get("continuidad_id") is not None
    }
    return frozenset(
        str(row["id"])
        for row in _raw_rows(modelo_dir / "revisions" / successor)
        if row.get("continuidad_id") is not None
        and by_lineage.get(row["continuidad_id"]) == row
        and not {"continuidad_origin", "continuidad_evidence"} & row.keys()
    )


def _drop_rows(edition_dir: Path, row_ids: frozenset[str]) -> None:
    for fragment in sorted((edition_dir / "casillas").glob("*.toml")):
        preamble, blocks = _split_casilla_rows(fragment.read_text(encoding="utf-8"))
        kept = [block for block in blocks if str(_row_of(block)["id"]) not in row_ids]
        if len(kept) == len(blocks):
            continue
        if kept:
            fragment.write_text(preamble + "".join(kept), encoding="utf-8", newline="\n")
        else:
            fragment.unlink()


def _rewrite_row(edition_dir: Path, row_id: str, old: str, new: str) -> None:
    for fragment in sorted((edition_dir / "casillas").glob("*.toml")):
        preamble, blocks = _split_casilla_rows(fragment.read_text(encoding="utf-8"))
        for index, block in enumerate(blocks):
            if str(_row_of(block)["id"]) == row_id:
                assert block.count(old) == 1, (row_id, old)
                blocks[index] = block.replace(old, new)
                fragment.write_text(preamble + "".join(blocks), encoding="utf-8", newline="\n")
                return
    raise AssertionError(f"no casilla row {row_id!r} under {edition_dir}")


def _manifest(edition_dir: Path) -> dict[str, object]:
    (revision,) = tomllib.loads((edition_dir / "revision.toml").read_text(encoding="utf-8"))["revisions"].values()
    assert isinstance(revision, dict), edition_dir
    return dict[str, object](revision)


def _declare_predecessor(edition_dir: Path, declaration: str) -> None:
    manifest = edition_dir / "revision.toml"
    text = manifest.read_text(encoding="utf-8")
    header = re.compile(
        rf'^\[revisions\.(?:"{re.escape(edition_dir.name)}"|{re.escape(edition_dir.name)})\]\n', re.MULTILINE
    )
    match = header.search(text)
    assert match is not None, manifest
    manifest.write_text(text[: match.end()] + declaration + text[match.end() :], encoding="utf-8", newline="\n")


def _declare_forest(modelo_dir: Path, named: Mapping[str, str]) -> None:
    """Name the given predecessors and make every other edition but the earliest an explicit root."""
    editions = sorted(
        (path for path in (modelo_dir / "revisions").iterdir()), key=lambda path: str(_manifest(path)["valid_from"])
    )
    for edition_dir in editions[1:]:
        predecessor = named.get(edition_dir.name)
        if predecessor is not None:
            reviewed = _manifest(edition_dir).get("review_status", "pending_review") != "pending_review"
            scope = f'reviewed_against = "{predecessor}"\n' if reviewed else ""
            _declare_predecessor(edition_dir, f'predecessor = "{predecessor}"\n{scope}')
            continue
        manifest = _manifest(edition_dir)
        legal_refs, source_refs = manifest["legal_refs"], manifest["source_refs"]
        assert isinstance(legal_refs, list) and isinstance(source_refs, list)
        _declare_predecessor(
            edition_dir,
            'predecessor = { none = { reason = "Authored as its own full copy; it inherits from no sibling edition.", '
            f'legal_refs = ["{legal_refs[0]}"], source_refs = ["{source_refs[0]}"] }} }}\n',
        )


def _migrate(modelo_dir: Path, *, successor: str, predecessor: str) -> frozenset[str]:
    """Author ``successor`` relative to ``predecessor``: drop every row it states identically."""
    inherited = _rows_stated_identically(modelo_dir, successor=successor, predecessor=predecessor)
    _declare_forest(modelo_dir, {successor: predecessor})
    _drop_rows(modelo_dir / "revisions" / successor, inherited)
    return inherited


@pytest.fixture(scope="module")
def scratch_repository(tmp_path_factory: pytest.TempPathFactory) -> _ScratchRepository:
    return _init_scratch_repository(tmp_path_factory.mktemp("full-copy-repository"), (_M303, _M131))


@pytest.fixture(scope="module")
def m303_reference(scratch_repository: _ScratchRepository, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _reference_for(scratch_repository, _M303, tmp_path_factory.mktemp("m303-reference") / "registry" / "aeat")


@pytest.fixture(scope="module")
def m131_reference(scratch_repository: _ScratchRepository, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _reference_for(scratch_repository, _M131, tmp_path_factory.mktemp("m131-reference") / "registry" / "aeat")


def _kinds(report: RoundTripReport) -> list[tuple[RoundTripFindingKind, str | None]]:
    return [(finding.kind, finding.revision_id) for finding in report.findings]


def test_a_correct_migration_inherits_rows_and_round_trips(
    scratch_repository: _ScratchRepository, m303_reference: Path, tmp_path: Path
) -> None:
    live = _live_tree(scratch_repository, _M303, tmp_path / "registry" / "aeat")
    inherited = _migrate(live / _MODELOS_DIR / _M303, successor=_M303_2025, predecessor=_M303_SEPTEMBER_2024)

    report = edition_round_trip_report(
        live_registry_root=live, reference_registry_root=m303_reference, modelo_id=_M303, export_scenarios={}
    )

    # Typed content and locale identity round-trip. Modelo 303 has an export
    # surface and this proof declares no scenario for it, so its bytes are
    # reported unchecked rather than passed; the byte proof is modelo 131's.
    assert _kinds(report) == [(RoundTripFindingKind.EXPORT_UNCHECKED, _M303_2025)]
    # Non-vacuity: the rows really were removed from disk and came back only by
    # inheritance, carrying the extra fallback key the chain rule must admit.
    assert inherited
    assert not inherited & {str(row["id"]) for row in _raw_rows(live / _MODELOS_DIR / _M303 / "revisions" / _M303_2025)}
    edition = _load_modelo(live, _M303).revisions[_M303_2025]
    before = {casilla.id: casilla for casilla in _load_modelo(m303_reference, _M303).revisions[_M303_2025].casillas}
    assert edition.predecessor == DeclaredPredecessor(revision_id=_M303_SEPTEMBER_2024)
    for casilla in edition.casillas:
        extra = len(casilla.localization_keys) - len(before[casilla.id].localization_keys)
        assert extra == (1 if casilla.id in inherited else 0), casilla.id


def test_a_migration_that_changes_a_restated_rows_meaning_fails_on_content(
    scratch_repository: _ScratchRepository, m303_reference: Path, tmp_path: Path
) -> None:
    """The same migration as the passing one, except that one superseding row now says something else."""
    live = _live_tree(scratch_repository, _M303, tmp_path / "registry" / "aeat")
    modelo_dir = live / _MODELOS_DIR / _M303
    _migrate(modelo_dir, successor=_M303_2025, predecessor=_M303_SEPTEMBER_2024)
    _rewrite_row(modelo_dir / "revisions" / _M303_2025, "22", "required = false", "required = true")

    report = edition_round_trip_report(
        live_registry_root=live, reference_registry_root=m303_reference, modelo_id=_M303, export_scenarios={}
    )

    assert _kinds(report) == [
        (RoundTripFindingKind.CONTENT, _M303_2025),
        (RoundTripFindingKind.EXPORT_UNCHECKED, _M303_2025),
    ]
    assert report.findings[0].detail == "casilla '22' changed ['required']"


def test_a_migration_that_drops_a_row_its_successor_restated_differently_fails(
    scratch_repository: _ScratchRepository, m303_reference: Path, tmp_path: Path
) -> None:
    """Dropping a row the successor did NOT state identically inherits the predecessor's meaning for it."""
    live = _live_tree(scratch_repository, _M303, tmp_path / "registry" / "aeat")
    modelo_dir = live / _MODELOS_DIR / _M303
    inherited = _migrate(modelo_dir, successor=_M303_2025, predecessor=_M303_SEPTEMBER_2024)
    assert "22" not in inherited
    _drop_rows(modelo_dir / "revisions" / _M303_2025, frozenset({"22"}))

    report = edition_round_trip_report(
        live_registry_root=live, reference_registry_root=m303_reference, modelo_id=_M303, export_scenarios={}
    )

    # The inherited row takes its export slot from the successor's own layout,
    # so what it inherits is the predecessor's meaning, which the gate reports
    # as a content change on that row rather than as a clean edition.
    assert _kinds(report) == [
        (RoundTripFindingKind.CONTENT, _M303_2025),
        (RoundTripFindingKind.EXPORT_UNCHECKED, _M303_2025),
    ]
    detail = report.findings[0].detail
    assert detail.startswith("casilla '22' changed [")
    assert "export_refs" not in detail


def test_a_migration_moving_an_inserted_row_to_the_end_round_trips_in_merge_order(
    scratch_repository: _ScratchRepository, m303_reference: Path, tmp_path: Path
) -> None:
    """2026 inserts a row mid-sequence; the merge appends it, and that order is the defined one."""
    live = _live_tree(scratch_repository, _M303, tmp_path / "registry" / "aeat")
    inherited = _migrate(live / _MODELOS_DIR / _M303, successor=_M303_2026, predecessor=_M303_2025)
    assert inherited

    report = edition_round_trip_report(
        live_registry_root=live, reference_registry_root=m303_reference, modelo_id=_M303, export_scenarios={}
    )

    assert _kinds(report) == [(RoundTripFindingKind.EXPORT_UNCHECKED, _M303_2026)]
    # Non-vacuity: the materialised edition really is in a different order from
    # its full copy, so the order assertion judged a rearrangement, not a copy.
    before = [casilla.id for casilla in _load_modelo(m303_reference, _M303).revisions[_M303_2026].casillas]
    after = [casilla.id for casilla in _load_modelo(live, _M303).revisions[_M303_2026].casillas]
    assert sorted(before) == sorted(after)
    assert before != after


def _move_row_to_first_fragment(edition_dir: Path, row_id: str) -> None:
    """Restate one row in a fragment that sorts before every other, changing only where it is stated."""
    for fragment in sorted((edition_dir / "casillas").glob("*.toml")):
        preamble, blocks = _split_casilla_rows(fragment.read_text(encoding="utf-8"))
        moved = [block for block in blocks if str(_row_of(block)["id"]) == row_id]
        if not moved:
            continue
        kept = [block for block in blocks if block not in moved]
        fragment.write_text(preamble + "".join(kept), encoding="utf-8", newline="\n")
        (edition_dir / "casillas" / "c0-moved.toml").write_text(moved[0], encoding="utf-8", newline="\n")
        return
    raise AssertionError(f"no casilla row {row_id!r} under {edition_dir}")


def test_new_rows_stated_out_of_their_pre_migration_order_fail_on_order_alone(
    scratch_repository: _ScratchRepository, m303_reference: Path, tmp_path: Path
) -> None:
    """The merge admits one order; a content-perfect edition in any other order is still refused.

    September 2024 adds several rows the edition before it lacks. The correct
    migration round-trips; the same migration with the last of those rows
    stated first among them is identical in content and fails on order alone.
    """
    reference = _load_modelo(m303_reference, _M303)
    earlier = {casilla.continuidad_id for casilla in reference.revisions[_M303_SUMMER_2024].casillas}
    new_rows = [
        str(casilla.id)
        for casilla in reference.revisions[_M303_SEPTEMBER_2024].casillas
        if casilla.continuidad_id not in earlier
    ]
    assert len(new_rows) >= 2, new_rows

    correct = _live_tree(scratch_repository, _M303, tmp_path / "correct" / "registry" / "aeat")
    _migrate(correct / _MODELOS_DIR / _M303, successor=_M303_SEPTEMBER_2024, predecessor=_M303_SUMMER_2024)
    passing = edition_round_trip_report(
        live_registry_root=correct, reference_registry_root=m303_reference, modelo_id=_M303, export_scenarios={}
    )
    assert _kinds(passing) == [(RoundTripFindingKind.EXPORT_UNCHECKED, _M303_SEPTEMBER_2024)]

    reordered = _live_tree(scratch_repository, _M303, tmp_path / "reordered" / "registry" / "aeat")
    modelo_dir = reordered / _MODELOS_DIR / _M303
    _migrate(modelo_dir, successor=_M303_SEPTEMBER_2024, predecessor=_M303_SUMMER_2024)
    _move_row_to_first_fragment(modelo_dir / "revisions" / _M303_SEPTEMBER_2024, new_rows[-1])
    failing = edition_round_trip_report(
        live_registry_root=reordered, reference_registry_root=m303_reference, modelo_id=_M303, export_scenarios={}
    )
    assert _kinds(failing) == [
        (RoundTripFindingKind.ROW_ORDER, _M303_SEPTEMBER_2024),
        (RoundTripFindingKind.EXPORT_UNCHECKED, _M303_SEPTEMBER_2024),
    ]
    assert f"expected {new_rows[0]!r}, live {new_rows[-1]!r}" in failing.findings[0].detail


def test_the_merge_order_is_the_predecessors_order_then_new_rows_in_full_copy_order() -> None:
    """Derived from the ordering rule alone, on rows exercising every case it names.

    The predecessor carries ``a``, ``b``, ``c`` and a row without lineage. The
    successor's full copy lists a new row first, supersedes ``b`` under a new
    id, drops ``c``, keeps ``a`` and the lineage-less row, and adds a second
    new row last.
    """
    predecessor: tuple[RowKey, ...] = (("01", "a"), ("02", "b"), ("03", "c"), ("04", None))
    full_copy: tuple[RowKey, ...] = (("10", "x"), ("22", "b"), ("01", "a"), ("04", None), ("11", "y"))

    assert merge_order(full_copy, predecessor) == (("01", "a"), ("22", "b"), ("04", None), ("10", "x"), ("11", "y"))
    # With nothing to inherit from, the full copy's own order is the order.
    assert merge_order(full_copy, ()) == full_copy
    # A lineage-less row matches on id only: under another id it is new.
    assert merge_order((("05", None), ("01", "a")), predecessor) == (("01", "a"), ("05", None))


def _m131_producer_snapshot() -> FilingProducerSnapshot:
    return build_filing_producer_snapshot(
        modelo=Modelo.M131,
        taxpayer_tax_id=_SYNTHETIC_TAX_ID,
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None, given_name="Ana", surnames="Prueba", full_name="Ana Prueba"
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.INGRESO,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


_M131_2025_SCENARIO: Final = EditionExportScenario(
    period=Period.from_year_and_code(2025, "1T"),
    inputs={
        "03": Decimal("1000"),
        "05": Decimal("500"),
        "modelo-131.page1.110-113.actividad-1-epigrafe": "722",
        "modelo-131.page1.114-130.actividad-1-rendimiento-neto": Decimal("1200.50"),
        "modelo-131.dpa.013-016.epigrafe-iae": ["722"],
        "modelo-131.dpa.031-032.vehiculos-afectos": {"1": "2"},
        "modelo-131.did.012-045.iban": "ES9121000418450200051332",
    },
    producer_snapshot=_m131_producer_snapshot,
)
_M131_2025_LAYOUTS = PurePosixPath("revisions/2025/export_layouts/0001-export-layouts.toml")
_M131_03_FIELD_TARGET = 'casilla_id = "03"\ndata_type'
_M131_05_FIELD_TARGET = 'casilla_id = "05"\ndata_type'


def test_export_bytes_are_compared_through_the_canonical_export_path(
    scratch_repository: _ScratchRepository, m131_reference: Path, tmp_path: Path
) -> None:
    """A correct migration renders identical bytes; one that swaps two restated rows' export slots does not.

    The defect restates casillas 03 and 05 with each other's export slot and
    retargets the two layout fields to match, so every cross-reference still
    validates and only the filed positions of 1000 and 500 change.
    """
    correct = _live_tree(scratch_repository, _M131, tmp_path / "correct" / "registry" / "aeat")
    _migrate(correct / _MODELOS_DIR / _M131, successor=_M131_2025, predecessor=_M131_2024)
    scenarios = {_M131_2025: _M131_2025_SCENARIO}

    passing = edition_round_trip_report(
        live_registry_root=correct, reference_registry_root=m131_reference, modelo_id=_M131, export_scenarios=scenarios
    )
    assert passing.findings == ()
    assert passing.byte_compared_revisions == (_M131_2025,)

    unchecked = edition_round_trip_report(
        live_registry_root=correct, reference_registry_root=m131_reference, modelo_id=_M131, export_scenarios={}
    )
    assert _kinds(unchecked) == [(RoundTripFindingKind.EXPORT_UNCHECKED, _M131_2025)]

    altered = _live_tree(scratch_repository, _M131, tmp_path / "altered" / "registry" / "aeat")
    modelo_dir = altered / _MODELOS_DIR / _M131
    _migrate(modelo_dir, successor=_M131_2025, predecessor=_M131_2024)
    layouts = modelo_dir.joinpath(*_M131_2025_LAYOUTS.parts)
    text = layouts.read_text(encoding="utf-8")
    assert text.count(_M131_03_FIELD_TARGET) == 1
    assert text.count(_M131_05_FIELD_TARGET) == 1
    swapped = (
        text.replace(_M131_03_FIELD_TARGET, "\0")
        .replace(_M131_05_FIELD_TARGET, _M131_03_FIELD_TARGET)
        .replace("\0", _M131_05_FIELD_TARGET)
    )
    layouts.write_text(swapped, encoding="utf-8", newline="\n")

    failing = edition_round_trip_report(
        live_registry_root=altered, reference_registry_root=m131_reference, modelo_id=_M131, export_scenarios=scenarios
    )
    assert _kinds(failing) == [
        (RoundTripFindingKind.CONTENT, _M131_2025),
        (RoundTripFindingKind.EXPORT_BYTES, _M131_2025),
    ]
    assert failing.findings[0].detail == (
        "edition fields changed ['export_layouts']; casilla '03' changed ['export_refs']; "
        "casilla '05' changed ['export_refs']"
    )
    assert failing.byte_compared_revisions == (_M131_2025,)


def _with_casilla_keys(revision: ModeloRevision, casilla_id: str, keys: tuple[str, ...]) -> ModeloRevision:
    casillas = tuple(
        casilla.model_copy(update={"localization_keys": keys}) if casilla.id == casilla_id else casilla
        for casilla in revision.casillas
    )
    return revision.model_copy(update={"casillas": casillas})


def test_locale_identity_admits_only_the_inherited_fallback_and_never_a_changed_label(
    m131_reference: Path, tmp_path: Path
) -> None:
    """The one key inheritance adds is admitted; a foreign key, or a fallback that changes the text, is not."""
    reference = _load_modelo(m131_reference, _M131).revisions[_M131_2025]
    siblings = frozenset(_load_modelo(m131_reference, _M131).revisions) - {_M131_2025}
    (casilla,) = (item for item in reference.casillas if item.id == "03")
    own, *rest = casilla.localization_keys
    fallback = casilla_occurrence_locale_key(_M131, _M131_2024, "03", ModeloLocalizationFieldKind.LABEL)
    inherited = _with_casilla_keys(reference, "03", (own, fallback, *rest))

    def differences(live: ModeloRevision) -> list[str]:
        return localization_differences(modelo_id=_M131, sibling_revision_ids=siblings, reference=reference, live=live)

    assert differences(reference) == []
    assert differences(inherited) == []
    foreign = casilla_occurrence_locale_key(_M131, _M131_2025, "04", ModeloLocalizationFieldKind.LABEL)
    assert differences(_with_casilla_keys(reference, "03", (own, foreign, *rest))) == [
        f"casilla '03' key chain {[own, *rest]!r} became {[own, foreign, *rest]!r}"
    ]

    # A catalogue where the edition's own entry is untranslated: the inherited
    # fallback now decides the label, and its text differs from the lineage text.
    catalogue = {own: None, fallback: "Texto heredado", **dict.fromkeys(rest, "Texto de continuidad")}
    (tmp_path / "es.yml").write_text(json.dumps(catalogue, ensure_ascii=False), encoding="utf-8")
    with override_locales_root(tmp_path):
        changed = differences(inherited)
    assert "casilla '03' label in 'es' changed from 'Texto de continuidad' to 'Texto heredado'" in changed


def test_a_reference_that_is_itself_delta_authored_is_refused(
    scratch_repository: _ScratchRepository, tmp_path: Path
) -> None:
    """A base commit taken after the migration would judge the materialiser with itself."""
    migrated = _live_tree(scratch_repository, _M131, tmp_path / "registry" / "aeat")
    _migrate(migrated / _MODELOS_DIR / _M131, successor=_M131_2025, predecessor=_M131_2024)

    report = edition_round_trip_report(
        live_registry_root=migrated, reference_registry_root=migrated, modelo_id=_M131, export_scenarios={}
    )

    assert _kinds(report) == [
        (RoundTripFindingKind.REFERENCE_NOT_FULL_COPY, _M131_2025),
        (RoundTripFindingKind.EXPORT_UNCHECKED, _M131_2025),
    ]


def test_a_base_commit_missing_from_the_clone_fails_closed(
    scratch_repository: _ScratchRepository, tmp_path: Path
) -> None:
    with pytest.raises(ReferenceUnavailableError, match="is not in this clone's history"):
        materialise_reference_registry(
            repo_root=scratch_repository.root,
            registry_relative=_SCRATCH_REGISTRY,
            modelo_id=_M131,
            base_commit="0" * 40,
            destination=tmp_path / "registry" / "aeat",
        )
    with pytest.raises(ReferenceUnavailableError, match="holds no registry/aeat/modelos/999"):
        materialise_reference_registry(
            repo_root=scratch_repository.root,
            registry_relative=_SCRATCH_REGISTRY,
            modelo_id="999",
            base_commit=scratch_repository.base_commit,
            destination=tmp_path / "absent" / "registry" / "aeat",
        )
