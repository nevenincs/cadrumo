"""Round-trip gate over the bundled corpus, and detector teeth for the gate itself.

The gate engine lives in ``dev.registry.edition_round_trip``; its module
docstring defines equality, order, the two compared trees and where the
comparison stops. This module holds the corpus gate that applies it to every
migrated bundled modelo, and the proofs that each rule bites.

Eligibility and the reference
-----------------------------
Eligibility comes from what editions declare. A modelo with an edition naming a
predecessor must carry an entry below; an entry for a modelo none of whose
editions names one is refused as stale. A modelo with neither is unmigrated and
has nothing to accept.

The reference is the modelo's own directory as committed at a recorded base
commit -- the last commit holding its full-copy form -- read with ``git
archive`` into a temporary registry tree and loaded through the real
authority. That reference is the literal pre-migration materialisation: the
loader over the files the migration replaced. It is not a frozen value: nothing
is generated, stored, or regenerated from the code being judged, so it cannot
drift into agreement with a defect. A stored digest was rejected because it
would have to be produced by the implementation it later judges, and a failure
against it could name no row. The base commit must be present in the clone; a
shallow checkout that lacks it fails closed. A successor authored delta-first
has no full-copy form and no baseline; nothing here can say whether it
inherited a row its author meant to drop.

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
import re
import shutil
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

import pytest

from cadrumo.core.i18n.render import override_locales_root
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
)
from cadrumo.domain.calculations.registry.schema import DeclaredPredecessor, ModeloDefinition, ModeloRevision

from ..._paths import REPO_ROOT
from ..compiler.authority import compile_validated_authority, compiled_bundled_authority
from ..compiler.loader import load_registry_tree
from ..edition_export_scenarios import edition_export_scenarios
from ..edition_round_trip import (
    COMMIT_ID,
    ReferenceUnavailableError,
    RegistryDependencyClosureError,
    RoundTripFindingKind,
    RoundTripReport,
    RowKey,
    copy_registry_tree,
    delta_authored_revisions,
    edition_round_trip_report,
    localization_differences,
    materialise_reference_registry,
    merge_order,
    modelo_dependency_ids,
    registry_dependency_closure,
    run_git,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@dataclass(frozen=True, slots=True)
class PreMigrationBaseline:
    """A migrated modelo compared against its directory at ``base_commit``.

    Its export bytes are rendered from the scenarios the canonical scenario
    module declares for the modelo.
    """

    base_commit: str


@dataclass(frozen=True, slots=True)
class AcceptedMigration:
    """A migrated modelo whose round trip passed at ``accepted_commit`` and is no longer compared."""

    accepted_commit: str
    reason: str


#: One entry per modelo whose editions name a predecessor; see the module
#: docstring for the entry lifecycle.
_MIGRATIONS: Final[Mapping[str, PreMigrationBaseline | AcceptedMigration]] = {
    "303": PreMigrationBaseline(base_commit="784c7cdd3eef1df8abd5524fd71be6c79f65a656"),
}

_BUNDLED_REGISTRY: Final = bundled_path("registry", "aeat")
_MODELOS_DIR: Final = "modelos"


def _load_modelo(registry_root: Path, modelo_id: str) -> ModeloDefinition:
    return compile_validated_authority(registry_root, bundled_path()).modelo(modelo_id)


# ── the bundled corpus ──────────────────────────────────────────────────────


def _bundled_modelo_ids() -> tuple[str, ...]:
    return tuple(sorted(path.name for path in (_BUNDLED_REGISTRY / _MODELOS_DIR).iterdir() if path.is_dir()))


@pytest.mark.parametrize("modelo_id", sorted(set(_bundled_modelo_ids()) | set(_MIGRATIONS)))
def test_every_bundled_modelo_either_is_unmigrated_or_round_trips(modelo_id: str, tmp_path: Path) -> None:
    """A modelo naming a predecessor anywhere must round-trip against its recorded full-copy form."""
    modelo = compiled_bundled_authority().modelo(modelo_id)
    delta_authored = delta_authored_revisions(modelo)
    entry = _MIGRATIONS.get(modelo_id)
    if entry is None:
        assert not delta_authored, (
            f"modelo {modelo_id} editions {delta_authored!r} name a predecessor but no pre-migration "
            "baseline is recorded, so the migration is unchecked"
        )
        return
    assert delta_authored, f"modelo {modelo_id} has a migration entry but no edition names a predecessor"
    if isinstance(entry, AcceptedMigration):
        assert COMMIT_ID.match(entry.accepted_commit), entry
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
        export_scenarios=edition_export_scenarios(modelo_id),
    )
    assert report.findings == ()


# ── the dependency closure of a staged tree ─────────────────────────────────
#
# Modelo 390, the annual IVA summary, sources figures from Modelo 303's
# periodic returns, so a tree holding 390 alone cannot pass registry-scope
# validation. Nothing below hardcodes that edge into the code under test: the
# closure is derived from 390's declarations, and the proofs check it against
# the loader and the authority.

_M390: Final = "390"
_M390_SOURCE: Final = "303"


def _copied_modelo_ids(registry: Path) -> frozenset[str]:
    return frozenset(path.name for path in (registry / _MODELOS_DIR).iterdir() if path.is_dir())


def test_a_staged_tree_carries_the_modelos_dependency_closure_and_nothing_else(tmp_path: Path) -> None:
    staged = copy_registry_tree(_BUNDLED_REGISTRY, tmp_path / "registry" / "aeat", modelo_id=_M390)

    copied = _copied_modelo_ids(staged)
    assert {_M390, _M390_SOURCE} <= copied
    assert len(copied) < len(_bundled_modelo_ids())
    modelos, _catalogues = load_registry_tree(staged)
    assert frozenset(str(modelo.id) for modelo in modelos) == copied
    # Closed under dependency: nothing a copied modelo names as a source was left out.
    for modelo in modelos:
        assert modelo_dependency_ids(modelo) <= copied, modelo.id
    # And it passes the real authority, which refuses an unresolved source.
    assert str(_load_modelo(staged, _M390).id) == _M390


def test_a_tree_missing_a_dependency_is_refused_by_the_closure_and_by_the_authority(tmp_path: Path) -> None:
    complete = copy_registry_tree(_BUNDLED_REGISTRY, tmp_path / "complete" / "registry" / "aeat", modelo_id=_M390)
    planted = shutil.copytree(complete, tmp_path / "planted" / "registry" / "aeat")
    shutil.rmtree(planted / _MODELOS_DIR / _M390_SOURCE)

    modelos, _catalogues = load_registry_tree(planted)
    with pytest.raises(RegistryDependencyClosureError, match=f"names source modelo '{_M390_SOURCE}'"):
        registry_dependency_closure(modelos, _M390)
    with pytest.raises(RegistryDependencyClosureError, match=f"names source modelo '{_M390_SOURCE}'"):
        copy_registry_tree(planted, tmp_path / "copy" / "registry" / "aeat", modelo_id=_M390)
    assert not (tmp_path / "copy").exists()
    with pytest.raises(RegistryDependencyClosureError, match="holds no modelo '999'"):
        registry_dependency_closure(modelos, "999")

    # The dropped dependency is exactly what the authority refuses, so the closure is load-bearing.
    report = edition_round_trip_report(
        live_registry_root=planted, reference_registry_root=complete, modelo_id=_M390, export_scenarios={}
    )
    assert [(finding.kind, finding.revision_id) for finding in report.findings] == [
        (RoundTripFindingKind.LIVE_REFUSED, None)
    ]
    assert f"unknown source modelo '{_M390_SOURCE}'" in report.findings[0].detail


# ── detector teeth on temporary trees ───────────────────────────────────────
#
# Each proof commits real bundled modelo directories into a throwaway git
# repository, reads the reference back through ``git archive`` exactly as the
# corpus gate does, then plants a migration in a separate live tree. Modelo 303
# carries the inheritance proofs: its 2025 edition restates two rows identically
# to the September-2024 edition, so a correct migration genuinely inherits
# them; its 2026 edition inserts a row mid-sequence, which inheritance appends,
# and its September-2024 edition adds several rows, whose stated order the merge
# keeps. Those proofs declare no export scenario, so 303's bytes are reported
# unchecked there; the byte proofs render the canonical scenarios, for Modelo 131
# from general filing facts and for Modelo 303 through its full filing envelope.

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
        completed = run_git(root, *arguments)
        assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    head = run_git(root, "rev-parse", "HEAD")
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
    # reported unchecked rather than passed; the byte proofs are separate.
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
    scenarios = edition_export_scenarios(_M131)
    assert set(scenarios) == {_M131_2025}

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


_M303_RESULTADOS_RECORD = "id = 'm303-resultados'"
_M303_RESULTADOS_IDENTITY_LITERAL = "literal = '03000'"
_M303_PLANTED_IDENTITY_LITERAL = "literal = '03009'"


def _fragment_declaring(directory: Path, declaration: str) -> Path:
    (fragment,) = (path for path in sorted(directory.glob("*.toml")) if declaration in path.read_text(encoding="utf-8"))
    return fragment


def test_modelo_303_export_bytes_are_compared_through_its_filing_envelope(
    scratch_repository: _ScratchRepository, m303_reference: Path, tmp_path: Path
) -> None:
    """A correct 303 migration renders the same envelope; one changed byte in its export layout does not.

    The plant rewrites one character of the 2025 resultados record's identity
    literal in the migrated tree only. The reference still renders the edition
    as committed, so the only difference the gate can see is that byte.
    """
    scenarios = {_M303_2025: edition_export_scenarios(_M303)[_M303_2025]}
    live = _live_tree(scratch_repository, _M303, tmp_path / "registry" / "aeat")
    modelo_dir = live / _MODELOS_DIR / _M303
    _migrate(modelo_dir, successor=_M303_2025, predecessor=_M303_SEPTEMBER_2024)

    passing = edition_round_trip_report(
        live_registry_root=live, reference_registry_root=m303_reference, modelo_id=_M303, export_scenarios=scenarios
    )
    assert passing.findings == ()
    assert passing.byte_compared_revisions == (_M303_2025,)

    fragment = _fragment_declaring(modelo_dir / "revisions" / _M303_2025 / "export", _M303_RESULTADOS_RECORD)
    text = fragment.read_text(encoding="utf-8")
    assert text.count(_M303_RESULTADOS_IDENTITY_LITERAL) == 1
    fragment.write_text(
        text.replace(_M303_RESULTADOS_IDENTITY_LITERAL, _M303_PLANTED_IDENTITY_LITERAL), encoding="utf-8", newline="\n"
    )

    failing = edition_round_trip_report(
        live_registry_root=live, reference_registry_root=m303_reference, modelo_id=_M303, export_scenarios=scenarios
    )
    assert _kinds(failing) == [
        (RoundTripFindingKind.CONTENT, _M303_2025),
        (RoundTripFindingKind.EXPORT_BYTES, _M303_2025),
    ]
    assert failing.findings[0].detail == "edition fields changed ['export_layouts']"
    assert failing.findings[1].detail.startswith("export bytes first differ at offset ")
    assert failing.byte_compared_revisions == (_M303_2025,)


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
