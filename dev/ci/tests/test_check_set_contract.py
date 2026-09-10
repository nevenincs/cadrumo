"""Repository-wide contracts for the merge check set."""

from __future__ import annotations

import ast
import re
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from ..._paths import REPO_ROOT
from ..lane_reachability import _recipe_bodies, _recipes_invoked_by

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS: Final = REPO_ROOT / ".github" / "workflows"
_MAIN_GROUP_SUFFIX = "${{ github.ref == 'refs/heads/main' && format('-{0}', github.sha) || '' }}"
_CHECK_GROUPS = frozenset({"check", "test", "build"})


def _documents(root: Path = _WORKFLOWS) -> list[tuple[Path, dict[str, Any]]]:
    paths = sorted((*root.glob("*.yml"), *root.glob("*.yaml")))
    assert paths, f"no workflows found below {root}"
    return [(path, yaml.safe_load(path.read_text(encoding="utf-8"))) for path in paths]


def _events(document: dict[str, Any]) -> set[str]:
    trigger = document.get("on", document.get(True, {}))
    if isinstance(trigger, str):
        return {trigger}
    if isinstance(trigger, list):
        return {str(item) for item in trigger}
    return {str(item) for item in (trigger or {})}


def _registered_markers() -> set[str]:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return {entry.split(":", 1)[0].strip().casefold() for entry in data["tool"]["pytest"]["ini_options"]["markers"]}


def _tool_names() -> set[str]:
    """Derive command/tool vocabulary from the checked-in execution surfaces."""
    names: set[str] = set()
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names.update(name.casefold() for name in project.get("project", {}).get("scripts", {}))
    dependency_groups = project.get("dependency-groups", {})
    dependencies = list(project.get("project", {}).get("dependencies", []))
    dependencies.extend(item for group in dependency_groups.values() for item in group if isinstance(item, str))
    for requirement in dependencies:
        match = re.match(r"[A-Za-z0-9_.-]+", requirement)
        if match:
            names.add(match.group().casefold().replace("_", "-"))
    for _, document in _documents():
        for job in (document.get("jobs") or {}).values():
            for step in job.get("steps") or []:
                uses = str(step.get("uses", "")).split("@", 1)[0]
                if uses:
                    names.add(uses.rsplit("/", 1)[-1].casefold().removesuffix("-action"))
    return names


def _just_groups() -> set[str]:
    return set(re.findall(r"^\[group\('([^']+)'\)\]$", (REPO_ROOT / "justfile").read_text(encoding="utf-8"), re.M))


def test_every_job_name_describes_coverage_with_the_shared_vocabulary() -> None:
    """Job rows use ``<Kind>: <Subject> [(Platform)]`` and never tool or marker subjects."""
    forbidden = _tool_names() | _registered_markers()
    groups = _just_groups()
    assert groups >= _CHECK_GROUPS, f"merge vocabulary is not backed by just groups: {sorted(_CHECK_GROUPS - groups)}"
    job_name = re.compile(
        rf"^({'|'.join(word.title() for word in sorted(_CHECK_GROUPS))}): ([^()]+?)(?: \(([^()]+)\))?$"
    )
    violations: list[str] = []
    for path, document in _documents():
        for key, job in (document.get("jobs") or {}).items():
            name = str(job.get("name", ""))
            if name == "${{ matrix.check-name }}":
                producer_text = "\n".join(
                    str(step.get("run", ""))
                    for producer in (document.get("jobs") or {}).values()
                    for step in producer.get("steps") or []
                )
                if not all(
                    token in producer_text for token in ('"check-name"', "row.minor", "row.phase.value", "os[1]")
                ):
                    violations.append(
                        f"{path.name}:{key}: dynamic row names are not unique by runtime, phase, platform"
                    )
                continue
            match = job_name.fullmatch(name)
            if match is None:
                violations.append(f"{path.name}:{key}: invalid job name {name!r}")
                continue
            subject_words = {word.casefold() for word in re.findall(r"[A-Za-z0-9_-]+", match.group(2))}
            leaked = sorted(subject_words & forbidden)
            if leaked:
                violations.append(f"{path.name}:{key}: subject names tools/markers {leaked}")
            platform = match.group(3)
            if platform and not (platform in {"Linux", "Windows", "macOS"} or "${{ matrix." in platform):
                violations.append(f"{path.name}:{key}: unsupported platform label {platform!r}")
            matrix = (job.get("strategy") or {}).get("matrix")
            if matrix and "${{ matrix." not in name:
                violations.append(f"{path.name}:{key}: matrix rows are not distinguished in the job name")
    assert violations == [], "job naming contract violations:\n" + "\n".join(violations)


def test_every_self_hosted_job_has_a_timeout() -> None:
    """All fleet jobs, including matrix-indirect jobs, declare ``timeout-minutes``."""
    missing = [
        f"{path.name}:{key}"
        for path, document in _documents()
        for key, job in (document.get("jobs") or {}).items()
        if "timeout-minutes" not in job
    ]
    assert missing == [], f"self-hosted jobs without timeout-minutes: {missing}"


def test_every_default_branch_push_reaches_a_verdict() -> None:
    """Push runs on main have SHA-isolated pending queues and never cancel in progress."""
    violations: list[str] = []
    for path, document in _documents():
        if "push" not in _events(document):
            continue
        push = document.get("on", document.get(True, {})).get("push", {})
        if isinstance(push, dict) and push.get("branches") and "main" not in push["branches"]:
            continue
        concurrency = document.get("concurrency") or {}
        group = str(concurrency.get("group", ""))
        cancel = str(concurrency.get("cancel-in-progress", ""))
        if _MAIN_GROUP_SUFFIX not in group:
            violations.append(f"{path.name}: main concurrency group has no SHA suffix")
        if cancel != "${{ github.ref != 'refs/heads/main' }}":
            violations.append(f"{path.name}: main runs can be cancelled: {cancel!r}")
        for key, job in (document.get("jobs") or {}).items():
            job_concurrency = job.get("concurrency")
            if not job_concurrency:
                continue
            job_group = str(job_concurrency.get("group", ""))
            job_cancel = str(job_concurrency.get("cancel-in-progress", ""))
            if _MAIN_GROUP_SUFFIX not in job_group or job_cancel != "${{ github.ref != 'refs/heads/main' }}":
                violations.append(f"{path.name}:{key}: job concurrency can destroy a main verdict")
    assert violations == [], "default-branch verdict violations:\n" + "\n".join(violations)


def _commands(job: dict[str, Any], recipes: dict[str, str]) -> list[str]:
    """Expand recipe calls to the final command lines executed by one job."""
    commands: list[str] = []

    def expand(text: str, stack: frozenset[str] = frozenset(), *, recipe_body: bool = False) -> None:
        invoked = _recipes_invoked_by(text)
        if invoked:
            for recipe in sorted(invoked - {"init"}):
                if recipe in recipes and recipe not in stack:
                    expand(recipes[recipe], stack | {recipe}, recipe_body=True)
            return
        if not recipe_body:
            commands.append(re.sub(r"\s+", " ", text).strip())
            return
        for line in text.splitlines():
            normalized = re.sub(r"\s+", " ", line.strip().lstrip("@"))
            if normalized and not normalized.startswith(("#", "$", "echo ", "Write-", "else", "fi", "}", ")", "-")):
                commands.append(normalized)

    for step in job.get("steps") or []:
        run = str(step.get("run", "")).strip()
        if run:
            expand(run)
    return commands


def test_no_command_runs_twice_in_one_workflow_run() -> None:
    """A workflow never schedules the same explicit command twice for one event."""
    duplicates: list[str] = []
    recipes = _recipe_bodies((REPO_ROOT / "justfile").read_text(encoding="utf-8"))
    for path, document in _documents():
        for key, job in (document.get("jobs") or {}).items():
            counts = Counter(_commands(job, recipes))
            duplicates.extend(
                f"{path.name}:{key}: {command!r} x{count}" for command, count in counts.items() if count > 1
            )
    assert duplicates == [], "duplicate commands:\n" + "\n".join(duplicates)


def test_shipped_packages_cannot_detect_the_test_runner() -> None:
    """Executable shipped code has no pytest or under-test detection tokens."""
    violations: list[str] = []
    for package in (REPO_ROOT / "src" / "cadrumo", REPO_ROOT / "src" / "cadrumo_harness"):
        for path in package.rglob("*.py"):
            if "tests" in path.parts or path.name == "conftest.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            docstrings = {
                id(node.value)
                for node in ast.walk(tree)
                if isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            }
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    modules = (
                        [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    )
                    if any(module.split(".", 1)[0].casefold() == "pytest" for module in modules):
                        violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: pytest import")
                if isinstance(node, ast.Name) and (
                    "pytest" in node.id.casefold() or "under_test" in node.id.casefold()
                ):
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {node.id}")
                if (
                    id(node) not in docstrings
                    and isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and (
                        node.value.casefold() == "pytest"
                        or node.value.startswith("PYTEST_")
                        or "under_test" in node.value.casefold()
                        or "guarded_read_context" in node.value.casefold()
                    )
                ):
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {node.value!r}")
    assert violations == [], "shipped test-runner awareness:\n" + "\n".join(violations)
