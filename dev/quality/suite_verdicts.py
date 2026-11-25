"""Clean-verdict reuse for the static quality suite, keyed on the content of each check's declared inputs.

A static check whose verdict is a pure function of the files it reads, the
code that reads them and the installed tools gives the same answer for the
same inputs. When a recorded clean verdict carries exactly the key the current
inputs produce, the suite reports the check as reused instead of running it.

The key is a digest of:

* the root-relative path and SHA-256 of every file the check declares, chosen
  from the repository's filesystem inclusion policy
  (:func:`dev.source_tree.repository_files`), never from version control and
  never from modification times;
* every first-party Python module, every development-tool file and the root
  configuration files (``pyproject.toml``, ``uv.lock``, ``.importlinter`` and
  the ignore and attribute rules), because a check's own implementation and
  configuration are inputs too;
* the interpreter, every installed distribution and version, the resolved
  executables the check launches, and the values of the environment variables
  that can change what a check or the modules it imports do;
* the check's command and the pytest node ids of its positive control.

Only a clean result is recorded, and only when the check's positive control
passed in the same run and the inputs still had the same key after the run.
Anything missing, unreadable or ambiguous selects the full run.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from cadrumo.core.atomic_write import atomic_write_text
from cadrumo.core.hashing import content_hash_hex, hash_file
from dev.paths import UTF_8
from dev.source_tree import repository_files

__all__ = [
    "IMPLEMENTATION_INPUTS",
    "REUSE",
    "REUSE_DISABLED",
    "Environment",
    "InputSelection",
    "KeyRefusal",
    "ReuseDeclaration",
    "TreeSnapshot",
    "VerdictKey",
    "current_environment",
    "keyed_variable",
    "positive_control_command",
    "publish_verdict",
    "read_verdict",
    "reusable",
    "take_tree_snapshot",
    "verdict_key",
    "verdict_record",
]

VERDICT_SCHEMA: Final[str] = "cadrumo-static-check-verdict/v1"
_KEY_SCHEMA: Final[str] = "cadrumo-static-check-key/v1"

_PYTHON_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi"})
_TYPESCRIPT_SUFFIXES: Final[frozenset[str]] = frozenset({".ts", ".tsx", ".mts", ".cts"})
_DATA_SUFFIXES: Final[frozenset[str]] = frozenset({".toml", ".yaml", ".yml"})

#: Roots whose Python a check may reach by walking the directory itself rather
#: than through the inclusion policy; a Python file there that the policy does
#: not list would be read without being keyed, so its presence disables reuse.
_RAW_WALKED_PYTHON_ROOTS: Final[tuple[str, ...]] = ("src", "dev", "stubs")

#: Environment variables whose values enter every key. The product reads its
#: settings from ``CADRUMO_`` variables at import time; the others select the
#: interpreter, its import path and the uv environment the type checkers run in.
_KEYED_VARIABLE_PREFIXES: Final[tuple[str, ...]] = ("CADRUMO_", "PYTHON", "VIRTUAL_ENV", "UV_")

#: Keyed-prefix variables left out of every key. Each only chooses where a run
#: writes its reports, logs, scratch or caches, or how many pytest workers run;
#: none selects what a static check reads or decides, and the gate runner and
#: test launcher give most of them a fresh per-run value that would otherwise
#: make every key new. A variable not named here stays in the key.
_UNKEYED_VARIABLES: Final[Mapping[str, str]] = {
    "CADRUMO_CI_REPORTS_DIR": "where JUnit and gate reports are written; a fresh path per gate node",
    "CADRUMO_CI_REPORT_NAME": "the file name of a written report",
    "CADRUMO_PYTEST_WORKERS": "how many pytest workers run, not which tests or what they assert",
    "CADRUMO_GATE_BUDGET": "the gate runner's global worker budget, a scheduling bound only",
    "CADRUMO_DEV_RUN_ROOT": "the per-run record directory the test-run launcher creates",
    "CADRUMO_DEV_ARTIFACTS_DIR": "where a run's artifacts (the import loadability report) are written",
    "CADRUMO_DEV_CACHE_DIR": "the per-run cache directory the test-run launcher creates",
    "CADRUMO_DEV_SCRATCH_DIR": "the per-run scratch directory the test-run launcher creates",
    "CADRUMO_RUN_ARTIFACT_ROOT": "where content-keyed run artifacts are cached; entries are keyed by their own inputs",
    "CADRUMO_LANE_RUN_ROOT": "the per-run directory of a test lane",
    "CADRUMO_TEST_LOG_ROOT": "where test-run logs are written",
    "CADRUMO_TEST_RUN_ROOT": "the per-run directory the pytest logger creates",
    "CADRUMO_TEST_RUN_SCRATCH": "the per-run scratch directory the pytest logger creates",
    "CADRUMO_TEST_COVERAGE_FILE": "where a coverage data file is written",
    "CADRUMO_TEST_COVERAGE_WORKER_PID": "the process id of a coverage-collecting worker",
    "CADRUMO_SCRATCH_BASE": "the parent directory of per-run scratch",
}


@dataclass(frozen=True, slots=True)
class InputSelection:
    """Repository files under ``under`` (``""`` is the whole tree) whose suffix is in ``suffixes`` (``None``: any)."""

    under: tuple[str, ...]
    suffixes: frozenset[str] | None = None

    def selects(self, relative: str) -> bool:
        """Whether ``relative`` is one of this selection's files."""
        if self.suffixes is not None and PurePosixPath(relative).suffix not in self.suffixes:
            return False
        return any(not root or relative == root or relative.startswith(f"{root}/") for root in self.under)


#: The implementation and configuration every check depends on: all
#: first-party Python (the checks, the product modules they import, the
#: stubs), every file under the development tree (checker metadata, baselines,
#: positive-control fixtures) and the root configuration.
IMPLEMENTATION_INPUTS: Final[tuple[InputSelection, ...]] = (
    InputSelection(("",), _PYTHON_SUFFIXES),
    InputSelection(("dev", "stubs")),
    InputSelection(
        (
            "pyproject.toml",
            "uv.lock",
            ".importlinter",
            ".python-version",
            ".gitignore",
            ".gitattributes",
            "conftest.py",
        )
    ),
)


@dataclass(frozen=True, slots=True)
class ReuseDeclaration:
    """What one check reads, which tools it runs and the positive control that proves it can fail."""

    scanned: tuple[InputSelection, ...]
    """The files the check scans; resolving to none is a failure, never a clean verdict."""
    tools: tuple[str, ...]
    """Distributions whose installed versions enter the key; a missing one disables reuse."""
    executables: tuple[str, ...]
    """Executables the check resolves from ``PATH``; their resolved paths enter the key."""
    positive_control: tuple[str, ...]
    """Pytest node ids that plant a defect and require the check's detector to report it."""


_WHOLE_PYTHON: Final[InputSelection] = InputSelection(("",), _PYTHON_SUFFIXES)
_SOURCE_TREE: Final[InputSelection] = InputSelection(("src",))

REUSE: Final[Mapping[str, ReuseDeclaration]] = {
    "check-data-format": ReuseDeclaration(
        scanned=(InputSelection(("",), _DATA_SUFFIXES),),
        tools=("yamllint",),
        executables=(),
        positive_control=(
            "dev/quality/tests/test_data_files.py::test_reports_toml_syntax",
            "dev/quality/tests/test_data_files.py::test_check_discovers_untracked_files",
        ),
    ),
    "check-types": ReuseDeclaration(
        scanned=(_WHOLE_PYTHON, _SOURCE_TREE),
        tools=("ty", "pyrefly", "basedpyright"),
        executables=("uv", "ty", "pyrefly", "basedpyright"),
        positive_control=(
            "dev/quality/tests/test_types_gate.py::test_ty_uses_the_harness_interpreter_when_virtual_env_is_broken",
            "dev/quality/tests/test_types_gate.py::test_pyrefly_resolves_project_dependencies_without_losing_type_errors",
            "dev/quality/tests/test_types_gate.py::test_basedpyright_resolves_project_dependencies_and_reports_a_planted_type_error",
        ),
    ),
    "complexity-gate": ReuseDeclaration(
        scanned=(_WHOLE_PYTHON,),
        tools=("radon", "complexipy"),
        executables=(),
        positive_control=(
            "dev/audit/tests/test_complexity_scan.py::test_gate_detects_length_in_each_root_then_accepts_repair",
            "dev/audit/tests/test_complexity_scan.py::test_cognitive_detector_turns_the_same_planted_function_red_then_green",
            "dev/audit/tests/test_complexity_scan.py::test_population_refuses_an_empty_source_root",
        ),
    ),
    "check-module-size": ReuseDeclaration(
        scanned=(InputSelection(("",), _TYPESCRIPT_SUFFIXES),),
        tools=(),
        executables=(),
        positive_control=(
            "dev/quality/tests/test_typescript_module_size.py::test_the_command_fails_on_a_module_over_the_bound",
            "dev/quality/tests/test_typescript_module_size.py::test_a_tree_without_typescript_is_refused_rather_than_read_as_clean",
        ),
    ),
    "check-year-literals": ReuseDeclaration(
        scanned=(InputSelection(("",), _PYTHON_SUFFIXES | _TYPESCRIPT_SUFFIXES),),
        tools=(),
        executables=(),
        positive_control=(
            "dev/quality/tests/test_year_literals.py::test_a_defect_planted_in_a_copied_tree_is_found_wherever_it_stands",
            "dev/quality/tests/test_year_literals.py::test_the_gate_fails_on_a_finding_and_passes_a_clean_tree",
            "dev/quality/tests/test_year_literals.py::test_a_walk_that_reads_nothing_is_refused",
        ),
    ),
    "check-surface-redeclaration": ReuseDeclaration(
        scanned=(InputSelection(("native/desktop/frontend/src",)), _WHOLE_PYTHON),
        tools=(),
        executables=(),
        positive_control=(
            "dev/quality/tests/test_surface_redeclaration.py::test_a_hand_copied_wire_type_fails",
            "dev/quality/tests/test_surface_redeclaration.py::test_a_copied_entry_point_helper_fails",
            "dev/quality/tests/test_surface_redeclaration.py::test_the_baseline_refuses_to_grow",
        ),
    ),
    "check-import-boundaries": ReuseDeclaration(
        scanned=(_WHOLE_PYTHON, _SOURCE_TREE),
        tools=("import-linter",),
        executables=("lint-imports",),
        positive_control=(
            "dev/tests/test_import_quality_gate.py::test_every_graph_defect_fails_through_one_real_gate",
            "dev/tests/test_import_quality_gate.py::test_every_authority_defect_fails_preflight_through_one_real_gate",
            "dev/tests/test_import_quality_gate.py::test_every_subordinate_defect_fails_through_one_real_gate",
            "dev/tests/test_import_quality_gate.py::test_zero_file_subordinate_scan_is_tool_broken",
            "dev/tests/test_import_quality_gate.py::test_clean_fixture_has_a_nonzero_governed_scan_and_passes_the_component",
        ),
    ),
    "check-module-reachability": ReuseDeclaration(
        scanned=(_WHOLE_PYTHON, _SOURCE_TREE),
        tools=(),
        executables=(),
        positive_control=(
            "dev/quality/tests/test_unreachable_module_coverage.py::test_a_dev_imported_module_is_in_use_and_a_test_only_module_is_not",
            "dev/quality/tests/test_unreachable_module_coverage.py::test_an_empty_audited_population_is_unavailable_not_clean",
            "dev/quality/tests/test_unreachable_module_coverage.py::test_the_gate_exits_distinctly_for_unavailable_findings_and_clean",
        ),
    ),
    "check-symbol-usage": ReuseDeclaration(
        scanned=(_WHOLE_PYTHON, _SOURCE_TREE),
        tools=(),
        executables=(),
        positive_control=(
            "dev/quality/tests/test_unused_symbol_coverage.py::test_an_exact_symbol_and_orphaned_test_are_both_reported",
            "dev/audit/tests/test_unreachable_code.py::test_symbol_layer_reports_only_definitions_shipped_code_never_references",
            "dev/audit/tests/test_unreachable_code.py::test_test_module_whose_every_shipped_subject_is_dead_is_an_orphaned_test",
        ),
    ),
    "check-export-consumption": ReuseDeclaration(
        scanned=(_WHOLE_PYTHON, _SOURCE_TREE),
        tools=(),
        executables=(),
        positive_control=(
            "dev/quality/tests/test_unconsumed_export_coverage.py::test_an_exact_unused_export_without_a_production_importer_is_reported",
            "dev/quality/tests/test_unconsumed_export_coverage.py::test_an_unreadable_module_refuses_to_claim_zero",
        ),
    ),
    "check-secure-store-write-paths": ReuseDeclaration(
        scanned=(_WHOLE_PYTHON, _SOURCE_TREE),
        tools=(),
        executables=(),
        positive_control=(
            "dev/quality/tests/test_secure_store_write_path.py::test_reports_a_store_that_is_read_and_never_written",
            "dev/quality/tests/test_secure_store_write_path.py::test_an_absent_source_root_is_refused",
        ),
    ),
    "check-persistence-write-paths": ReuseDeclaration(
        scanned=(_WHOLE_PYTHON, _SOURCE_TREE),
        tools=(),
        executables=(),
        positive_control=(
            "dev/tests/test_write_path_coverage_gate.py::test_a_readable_surface_with_no_production_writer_is_reported",
            "dev/tests/test_write_path_coverage_gate.py::test_an_unscannable_tree_refuses_rather_than_reporting_clean",
        ),
    ),
    "check-docstring-references": ReuseDeclaration(
        scanned=(_WHOLE_PYTHON,),
        tools=(),
        executables=(),
        positive_control=(
            "dev/quality/tests/test_docstring_reference_targets.py::test_the_gate_refuses_a_dangling_target_and_accepts_a_resolved_one",
            "dev/quality/tests/test_docstring_reference_targets.py::test_an_absent_source_root_refuses",
        ),
    ),
    "check-operation-contract-manifest": ReuseDeclaration(
        scanned=(_SOURCE_TREE,),
        tools=(),
        executables=(),
        positive_control=(
            "dev/operation_contract_manifest/tests/test_generate.py::test_check_fails_on_a_manifest_with_a_stale_fingerprint",
            "dev/operation_contract_manifest/tests/test_generate.py::test_check_fails_when_an_operation_is_missing",
        ),
    ),
}

#: Checks that always run, each with the reason its verdict is not reused.
REUSE_DISABLED: Final[Mapping[str, str]] = {
    "check-style": "ruff has no positive control that plants a lint defect; it also runs in under a second",
    "check-format": "ruff format has no positive control that plants format drift; it also runs in under a second",
    "check-dependency-declarations": (
        "deptry has no positive control, and its verdict depends on the declared dependencies of the installed "
        "environment as well as the source; the dependency checks always run"
    ),
    "check-frontend": (
        "runs through CMake configure and npm tooling whose inputs (build tree, node_modules, generated contract) "
        "are not declarable from the repository inclusion policy"
    ),
    "check-rust": (
        "runs through CMake configure and cargo whose inputs (build tree, crate registry, advisory database) "
        "are not declarable from the repository inclusion policy"
    ),
}


@dataclass(frozen=True, slots=True)
class Environment:
    """The installed tooling a verdict depends on beyond the repository's files."""

    interpreter: str
    distributions: Mapping[str, str]
    variables: tuple[tuple[str, str], ...]
    executables: Mapping[str, str | None]


def keyed_variable(name: str) -> bool:
    """Whether the environment variable ``name`` enters verdict keys."""
    upper = name.upper()
    return upper.startswith(_KEYED_VARIABLE_PREFIXES) and upper not in _UNKEYED_VARIABLES


def current_environment(executables: Iterable[str] = ()) -> Environment:
    """Describe the running interpreter, its installed distributions, keyed variables and resolved executables."""
    distributions: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        if name:
            distributions[_canonical_distribution(name)] = distribution.version
    variables = tuple(sorted((name, value) for name, value in os.environ.items() if keyed_variable(name)))
    return Environment(
        interpreter=f"{platform.python_implementation()} {sys.version} {platform.machine()} {sys.platform}",
        distributions=distributions,
        variables=variables,
        executables={name: shutil.which(name) for name in sorted(set(executables))},
    )


def _canonical_distribution(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


@dataclass(frozen=True, slots=True)
class TreeSnapshot:
    """The content digest of every repository file any declaration selects, read once."""

    files: Mapping[str, str]
    """Root-relative POSIX path to SHA-256 of its bytes."""
    unreadable: frozenset[str]
    unlisted_python: tuple[str, ...]
    """Python files under the raw-walked roots that the inclusion policy does not list."""


def _selected(relative: str, selections: Iterable[InputSelection]) -> bool:
    return any(selection.selects(relative) for selection in selections)


def take_tree_snapshot(root: Path, declarations: Iterable[ReuseDeclaration]) -> TreeSnapshot:
    """Hash every file the implementation inputs or any of ``declarations`` select under ``root``."""
    selections = (*IMPLEMENTATION_INPUTS, *(selection for item in declarations for selection in item.scanned))
    listed = repository_files(root)
    files: dict[str, str] = {}
    unreadable: set[str] = set()
    for relative in listed:
        if not _selected(relative, selections):
            continue
        try:
            files[relative] = hash_file(root / relative)[0]
        except OSError:
            unreadable.add(relative)
    return TreeSnapshot(
        files=files,
        unreadable=frozenset(unreadable),
        unlisted_python=_unlisted_python(root, frozenset(listed)),
    )


def _unlisted_python(root: Path, listed: frozenset[str]) -> tuple[str, ...]:
    unlisted: list[str] = []
    for top in _RAW_WALKED_PYTHON_ROOTS:
        for directory, _, names in os.walk(root / top):
            for name in names:
                if PurePosixPath(name).suffix not in _PYTHON_SUFFIXES:
                    continue
                relative = PurePosixPath(*Path(directory, name).relative_to(root).parts).as_posix()
                if relative not in listed:
                    unlisted.append(relative)
    return tuple(sorted(unlisted))


@dataclass(frozen=True, slots=True)
class VerdictKey:
    """A computed key and the number of scanned files behind it."""

    key: str
    scanned_files: int


@dataclass(frozen=True, slots=True)
class KeyRefusal:
    """Why no key could be computed; the check then runs in full."""

    reason: str
    scanned_files: int


def verdict_key(
    name: str,
    command: tuple[str, ...],
    declaration: ReuseDeclaration,
    snapshot: TreeSnapshot,
    environment: Environment,
) -> VerdictKey | KeyRefusal:
    """Return the content key of one check's inputs, or the reason none can be trusted."""
    scanned = sorted(path for path in snapshot.files if _selected(path, declaration.scanned))
    unreadable = sorted(path for path in snapshot.unreadable if _selected(path, declaration.scanned))
    refusal = _key_refusal(declaration, snapshot, environment, unreadable)
    if refusal is not None:
        return KeyRefusal(refusal, len(scanned))
    if not scanned:
        return KeyRefusal("the declared input set resolved to zero files", 0)
    selections = (*IMPLEMENTATION_INPUTS, *declaration.scanned)
    payload = {
        "schema": _KEY_SCHEMA,
        "check": name,
        "command": [_portable_argument(part) for part in command],
        "files": sorted([path, digest] for path, digest in snapshot.files.items() if _selected(path, selections)),
        "interpreter": environment.interpreter,
        "distributions": sorted(environment.distributions.items()),
        "tools": [[tool, environment.distributions[_canonical_distribution(tool)]] for tool in declaration.tools],
        "executables": [[name, environment.executables[name]] for name in sorted(declaration.executables)],
        "variables": [list(item) for item in environment.variables],
        "positive_control": list(declaration.positive_control),
    }
    return VerdictKey(content_hash_hex(payload), len(scanned))


def _key_refusal(
    declaration: ReuseDeclaration, snapshot: TreeSnapshot, environment: Environment, unreadable: list[str]
) -> str | None:
    if snapshot.unlisted_python:
        return f"Python outside the inclusion policy would be read unkeyed: {snapshot.unlisted_python[0]}"
    implementation_unreadable = sorted(path for path in snapshot.unreadable if _selected(path, IMPLEMENTATION_INPUTS))
    if unreadable or implementation_unreadable:
        return f"an input could not be read: {(unreadable or implementation_unreadable)[0]}"
    missing_tools = [
        tool for tool in declaration.tools if _canonical_distribution(tool) not in environment.distributions
    ]
    if missing_tools:
        return f"tool version unavailable: {missing_tools[0]}"
    unresolved = [name for name in declaration.executables if environment.executables.get(name) is None]
    if unresolved:
        return f"executable unresolved: {unresolved[0]}"
    if not declaration.positive_control:
        return "no positive control is declared"
    return None


def _portable_argument(argument: str) -> str:
    return "<python>" if argument == sys.executable else argument


def positive_control_command(declaration: ReuseDeclaration) -> tuple[str, ...]:
    """Run the declared positive-control tests alone, selecting them by node id and no marker."""
    return (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-n",
        "0",
        "-p",
        "no:cacheprovider",
        "-m",
        "",
        *declaration.positive_control,
    )


def verdict_record(
    name: str, key: str, declaration: ReuseDeclaration, *, scanned_files: int, seconds: float
) -> dict[str, object]:
    """The record of one clean verdict whose positive control passed under ``key``."""
    return {
        "schema": VERDICT_SCHEMA,
        "check": name,
        "key": key,
        "verdict": "clean",
        "scanned_files": scanned_files,
        "seconds": round(seconds, 3),
        "positive_control": {"nodes": list(declaration.positive_control), "passed": True},
    }


def _verdict_path(directory: Path, name: str) -> Path:
    if not name or PurePosixPath(name).name != name or name.startswith("."):
        raise ValueError(f"check name must be one plain path segment, got {name!r}")
    return directory / f"{name}.json"


def read_verdict(directory: Path, name: str) -> Mapping[str, object] | None:
    """Return the recorded verdict for ``name``; ``None`` when absent, unreadable or not a JSON object."""
    try:
        decoded: object = json.loads(_verdict_path(directory, name).read_text(encoding=UTF_8))
    except (OSError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    return {str(field): value for field, value in decoded.items()}


def reusable(record: Mapping[str, object] | None, name: str, key: VerdictKey, declaration: ReuseDeclaration) -> bool:
    """Whether ``record`` is a clean verdict for exactly this check, key and positive control."""
    if record is None:
        return False
    control = record.get("positive_control")
    if not isinstance(control, dict):
        return False
    passed: object = control.get("passed")
    nodes: object = control.get("nodes")
    scanned = record.get("scanned_files")
    return (
        record.get("schema") == VERDICT_SCHEMA
        and record.get("check") == name
        and record.get("key") == key.key
        and record.get("verdict") == "clean"
        and type(scanned) is int
        and scanned > 0
        and passed is True
        and nodes == list(declaration.positive_control)
    )


def publish_verdict(directory: Path, name: str, record: Mapping[str, object]) -> None:
    """Publish ``record`` atomically, so a reader sees the previous verdict or this one, never a torn file."""
    if record.get("verdict") != "clean":
        raise ValueError(f"only a clean verdict is recorded, not {record.get('verdict')!r}")
    atomic_write_text(
        _verdict_path(directory, name), json.dumps(record, indent=2, sort_keys=True) + "\n", encoding=UTF_8
    )
