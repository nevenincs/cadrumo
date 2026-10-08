"""Derive and verify the complete shipped-data payload from the current source tree."""

from __future__ import annotations

import ast
import zipfile
from pathlib import Path, PurePosixPath

from dev._paths import UTF_8
from dev.first_party_source import is_test_source
from dev.quality.source_import_analysis import wheel_exclude_globs
from dev.source_tree import repository_files

from .authority_staging import selected_published_authority
from .google_oauth import GOOGLE_OAUTH_RESOURCE
from .proof_ledger import (
    record_proof,
)

SOURCE_DATA_ROOTS = ("src/cadrumo/_data",)


_SOURCE_DATA_PREFIX = "src/cadrumo/_data/"


_WHEEL_DATA_PREFIX = "cadrumo/_data"


# Corpus source binaries excluded from the compact command-bearing ``cadrumo`` wheel
# by the build config; they ship in the three mandatory ``cadrumo-data-*`` distributions. A
# source path is one of these when it lives under ``_data/corpus`` and
# carries a binary suffix, so the wheel-bundling parity check must not expect it
# in the
# ``cadrumo`` archive.
_CORPUS_SOURCE_PREFIX = "src/cadrumo/_data/corpus/"


_COMPANION_HOOKS = (
    "packaging/cadrumo_data_manuals/hatch_build.py",
    "packaging/cadrumo_data_official/hatch_build.py",
    "packaging/cadrumo_data_normatives/hatch_build.py",
)


# Every practical-manual PDF the manuals companion must carry. Stated as explicit
# literals rather than derived from a walk of the corpus: a floor computed from the
# tree it is meant to police cannot detect that tree losing a member. Covering
# Renta alone would leave the IVA and Sociedades manuals free to drop out of the
# shipped inventory with this floor still green.
_MANUAL_PDF_PRESENCE_FLOOR = (
    {
        f"src/cadrumo/_data/corpus/manuals/renta/{year}/part1/source.pdf"
        for year in ("2020", "2021", "2022", "2023", "2024", "2025")
    }
    | {
        f"src/cadrumo/_data/corpus/manuals/iva/{year}/source.pdf"
        for year in ("2020", "2021", "2022", "2023", "2024", "2025")
    }
    | {
        f"src/cadrumo/_data/corpus/manuals/renta/{year}/part2-deducciones-autonomicas/source.pdf"
        for year in ("2024", "2025")
    }
    | {f"src/cadrumo/_data/corpus/manuals/sociedades/{year}/source.pdf" for year in ("2024", "2025")}
)


def _format_path_sample(paths: list[str], *, limit: int = 20) -> str:
    """Format a bounded path list for actionable gate failures."""
    sample = paths[:limit]
    if len(paths) <= limit:
        return repr(sample)
    return f"{sample!r}; plus {len(paths) - limit} more"


def _validated_source_data_inventory(source_root: Path, inventory: set[str], *, origin: str) -> set[str]:
    """Validate one shipped-data inventory against the source tree that must carry it."""
    if not inventory:
        raise SystemExit(f"{origin} reported no shipped data under {_SOURCE_DATA_PREFIX} in {source_root}")
    outside = sorted(path for path in inventory if not path.startswith(_SOURCE_DATA_PREFIX))
    if outside:
        raise SystemExit(f"{origin} returned paths outside {_SOURCE_DATA_PREFIX}: {outside[:10]!r}")
    absent = sorted(path for path in inventory if not (source_root / path).is_file())
    if absent:
        raise SystemExit(
            f"{len(absent)} shipped-data files named by {origin} are absent from {source_root}: "
            f"{_format_path_sample(absent)}. Reconcile these paths before packaging: restore the files, "
            "or remove them from the repository if they were intentionally retired."
        )
    return inventory


def source_data_paths(repo_root: Path) -> set[str]:
    """Return repository-visible shipped-data paths relative to the repository root."""
    source_paths = set(repository_files(repo_root, under=SOURCE_DATA_ROOTS))
    source_paths = _validated_source_data_inventory(repo_root, source_paths, origin="the repository file enumeration")
    missing_floor = sorted(_MANUAL_PDF_PRESENCE_FLOOR - source_paths)
    if missing_floor:
        raise SystemExit(f"source data is missing required manual PDFs: {missing_floor!r}")
    return source_paths


def build_source_data_paths(source_root: Path) -> set[str]:
    """Return the shipped-data inventory a build from this source tree will carry.

    The inventory is the enumerated tree, never what the filesystem happens to
    hold beside it. A working tree also carries ignored artifacts beside the
    sources -- bytecode caches, registry transaction mutexes -- which the same
    ignore rules the wheel build's file selection uses already exclude, so
    counting them would demand payload the wheel can never contain. A snapshot
    build root (:func:`build_root_snapshot`) holds exactly the enumerated
    files, so reading either one this way answers the same question.
    """
    inventory = set(repository_files(source_root, under=SOURCE_DATA_ROOTS))
    return _validated_source_data_inventory(source_root, inventory, origin="the repository file enumeration")


def _configured_corpus_binary_suffixes(repo_root: Path) -> tuple[str, ...]:
    """Return corpus suffixes excluded by the root wheel configuration."""
    excluded = wheel_exclude_globs(repo_root / "pyproject.toml")
    prefix = f"{_CORPUS_SOURCE_PREFIX}**/*"
    suffixes = tuple(sorted({Path(pattern).suffix.lower() for pattern in excluded if pattern.startswith(prefix)}))
    if not suffixes or "" in suffixes:
        raise SystemExit("root wheel config declares no precise corpus binary suffix exclusions")
    return suffixes


def _ownership_literal_value(value: ast.expr) -> frozenset[str]:
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "frozenset":
        value = value.args[0]
    return frozenset(str(item).lower() for item in ast.literal_eval(value))


def _companion_hook_literals(tree: ast.Module, relative_hook: str) -> dict[str, frozenset[str]]:
    literals: dict[str, frozenset[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name not in {"_CORPUS_BINARY_SUFFIXES", "_OWNED_SUBDIRS"}:
            continue
        literals[name] = _ownership_literal_value(node.value)
    missing = {"_CORPUS_BINARY_SUFFIXES", "_OWNED_SUBDIRS"} - literals.keys()
    if missing:
        raise SystemExit(
            f"companion hook {relative_hook} is missing literal ownership declarations: {sorted(missing)!r}"
        )
    return literals


def _companion_corpus_ownership(repo_root: Path) -> dict[str, frozenset[str]]:
    """Return top-level corpus partitions and suffixes owned by companion hooks."""
    ownership: dict[str, frozenset[str]] = {}
    for relative_hook in _COMPANION_HOOKS:
        tree = ast.parse((repo_root / relative_hook).read_text(encoding=UTF_8))
        literals = _companion_hook_literals(tree, relative_hook)
        suffixes = literals["_CORPUS_BINARY_SUFFIXES"]
        for subdir in literals["_OWNED_SUBDIRS"]:
            if subdir in ownership:
                raise SystemExit(f"corpus companion ownership overlaps at top-level partition: {subdir}")
            ownership[str(subdir)] = suffixes
    return ownership


def _is_corpus_source_binary(source_relative: str, suffixes: tuple[str, ...]) -> bool:
    """Return True for a source ``_data/corpus`` path that is an excluded source binary."""
    return source_relative.startswith(_CORPUS_SOURCE_PREFIX) and source_relative.lower().endswith(suffixes)


def _assert_split_files_have_companion_owners(repo_root: Path, paths: set[str]) -> None:
    """Verify every root-excluded corpus file is selected by one companion hook."""
    ownership = _companion_corpus_ownership(repo_root)
    unowned: list[str] = []
    for path in sorted(paths):
        relative = path.removeprefix(_CORPUS_SOURCE_PREFIX)
        subdir = relative.partition("/")[0]
        if Path(path).suffix.lower() not in ownership.get(subdir, frozenset()):
            unowned.append(path)
    if unowned:
        raise SystemExit(
            f"{len(unowned)} root-excluded corpus binaries have no companion hook owner: {_format_path_sample(unowned)}"
        )


def expected_wheel_data_paths(repo_root: Path) -> set[str]:
    """Return expected bundled-data paths inside the command-bearing wheel.

    Corpus source binaries declared by the root Hatch exclusion list are excluded:
    the wheel-split build config sheds them from this wheel and ships them in the
    three mandatory ``cadrumo-data-*`` distributions, so they are absent from the
    archive.
    Test modules under a ``_data`` ``tests/`` folder are excluded by the
    data-budget wheel boundary (tests serve no installed consumer) and are
    likewise legitimately absent.
    """
    source_paths = source_data_paths(repo_root)
    if not source_paths:
        # The sealed-source sibling below already refuses this. A derivation
        # that found no shipped data cannot describe a payload, and comparing
        # an empty expectation against an empty archive would pass.
        raise SystemExit(f"no shipped source data found under {repo_root}; the expectation would be empty")
    return _expected_wheel_data_paths(repo_root, source_paths)


def expected_wheel_data_paths_from_source_tree(source_root: Path) -> set[str]:
    """Derive wheel data expectations solely from the source tree a build reads.

    Both the inventory and the split-ownership configuration come from
    ``source_root``, so the expectation describes the tree the wheel is actually
    built from rather than an unrelated checkout. The inventory is the
    enumerated tree (:func:`build_source_data_paths`), which is what keeps the
    result identical whether that tree is a live working tree or a snapshot
    build root.
    """
    return _expected_wheel_data_paths(source_root, build_source_data_paths(source_root))


def _is_configured_exclusion(path: str, patterns: tuple[str, ...]) -> bool:
    """Return whether one source path is shed by a declared wheel exclusion."""
    candidate = PurePosixPath(path)
    return any(candidate.full_match(pattern) or candidate.is_relative_to(pattern) for pattern in patterns)


def _expected_wheel_data_paths(repo_root: Path, source_paths: set[str]) -> set[str]:
    """Project source data and the selected published authority into wheel paths."""
    suffixes = _configured_corpus_binary_suffixes(repo_root)
    split_owned = {
        path for path in source_paths if not is_test_source(path) and _is_corpus_source_binary(path, suffixes)
    }
    _assert_split_files_have_companion_owners(repo_root, split_owned)
    # The build sheds authoring inputs by directory as well as by suffix, so an
    # expectation derived from the source tree alone demands payload the wheel
    # can never carry.
    exclusions = wheel_exclude_globs(repo_root / "pyproject.toml")
    expected: set[str] = set()
    for path in source_paths:
        if path in split_owned:
            continue
        if is_test_source(path):
            continue
        if _is_configured_exclusion(path, exclusions):
            continue
        expected.add(f"{_WHEEL_DATA_PREFIX}/{path.removeprefix(_SOURCE_DATA_PREFIX)}")
    descriptor, database = selected_published_authority(repo_root)
    expected.update(f"{_WHEEL_DATA_PREFIX}/registry/authority/{path.name}" for path in (descriptor, database))
    # The build hook creates this validated runtime input even when the source
    # checkout keeps its publisher configuration outside tracked package data.
    expected.add(GOOGLE_OAUTH_RESOURCE.removeprefix("src/"))
    return expected


def assert_wheel_contains_source_data(repo_root: Path, wheel: Path, expected: set[str] | None = None) -> None:
    """Verify the wheel's complete data payload equals the source runtime set."""
    expected_paths = expected_wheel_data_paths(repo_root) if expected is None else expected
    with zipfile.ZipFile(wheel) as archive:
        actual_paths = {
            info.filename
            for info in archive.infolist()
            if not info.is_dir() and info.filename.startswith(f"{_WHEEL_DATA_PREFIX}/")
        }
    missing = sorted(expected_paths - actual_paths)
    unexpected = sorted(actual_paths - expected_paths)
    if missing or unexpected:
        raise SystemExit(
            "wheel data payload differs from the source runtime set: "
            f"missing={_format_path_sample(missing)}, unexpected={_format_path_sample(unexpected)}"
        )
    record_proof("wheel source shipped-data payload")
