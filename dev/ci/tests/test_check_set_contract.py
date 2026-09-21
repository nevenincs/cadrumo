"""Repository-wide contracts for the merge check set."""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT

from ..lane_reachability import _recipe_bodies, _recipes_invoked_by
from ..workflow_delegation import calls_local_workflow
from ..workflow_run_text import executed_lines

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
    data = parse_toml((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return {entry.split(":", 1)[0].strip().casefold() for entry in data["tool"]["pytest"]["ini_options"]["markers"]}


def _tool_names() -> set[str]:
    """Derive command/tool vocabulary from the checked-in execution surfaces."""
    names: set[str] = set()
    project = parse_toml((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
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
            platforms = {"Linux", "Windows", "macOS"}
            qualified = platform and platform.split(", ", 1)[0] in platforms and "${{" in platform
            if platform and not (platform in platforms or "${{ matrix." in platform or qualified):
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
        if "timeout-minutes" not in job and not calls_local_workflow(job)
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


#: One recipe header, capturing the name and everything before the colon: the
#: parameter list, with defaults still attached.
_RECIPE_SIGNATURE: Final = re.compile(r"^(?P<name>[a-z][\w-]*)(?P<parameters>[^:\n]*):(?![=])")

#: One `just <recipe> <arguments...>` call, argument text included. The lane
#: transport's own calls are read by `_recipes_invoked_by` and carry no
#: arguments, so they are left to it.
_JUST_CALL_WITH_ARGUMENTS: Final = re.compile(r"\bjust\s+(?P<recipe>_?[a-z][\w-]*)(?P<arguments>[^|;&\n]*)")


def _recipe_parameters(text: str) -> dict[str, tuple[tuple[str, str | None], ...]]:
    """Return each recipe's declared parameters, with defaults where given."""
    signatures: dict[str, tuple[tuple[str, str | None], ...]] = {}
    for line in text.splitlines():
        match = _RECIPE_SIGNATURE.match(line)
        if match is None:
            continue
        parameters: list[tuple[str, str | None]] = []
        for token in match.group("parameters").split():
            name, separator, default = token.partition("=")
            parameters.append((name.lstrip("*+"), default.strip("\"'") if separator else None))
        signatures[match.group("name")] = tuple(parameters)
    return signatures


def _substitute(body: str, parameters: tuple[tuple[str, str | None], ...], arguments: tuple[str, ...]) -> str:
    """Return ``body`` with its `{{PARAM}}` placeholders replaced by ``arguments``.

    Without this, one parameterised recipe invoked twice with different
    arguments expands to the same text twice and reads as a command scheduled
    twice. That is not a hypothetical: it fired on two `release-runtime-matrix`
    invocations that request different phases, and it would fire on every
    future conversion to a parameterised recipe -- a standing tax on exactly
    the refactor this repository wants.

    A parameter with neither an argument nor a default keeps its placeholder,
    because inventing a value would make two genuinely identical invocations
    look different, which is the failure this check exists to catch.
    """
    substituted = body
    for index, (name, default) in enumerate(parameters):
        value = arguments[index] if index < len(arguments) else default
        if value is None:
            continue
        substituted = re.sub(r"\{\{\s*" + re.escape(name) + r"\s*\}\}", value, substituted)
    return substituted


def _invocation_arguments(text: str) -> dict[str, tuple[tuple[str, ...], ...]]:
    """Return the argument lists each recipe is invoked with in ``text``."""
    calls: dict[str, list[tuple[str, ...]]] = {}
    for line in executed_lines(text):
        for match in _JUST_CALL_WITH_ARGUMENTS.finditer(line):
            calls.setdefault(match.group("recipe"), []).append(tuple(match.group("arguments").split()))
    return {recipe: tuple(argument_lists) for recipe, argument_lists in calls.items()}


def _commands(
    job: dict[str, Any],
    recipes: dict[str, str],
    parameters: dict[str, tuple[tuple[str, str | None], ...]] | None = None,
) -> list[str]:
    """Expand recipe calls to the final command lines executed by one job."""
    commands: list[str] = []
    signatures = {} if parameters is None else parameters

    def expand(text: str, stack: frozenset[str] = frozenset(), *, recipe_body: bool = False) -> None:
        invoked = _recipes_invoked_by(text)
        if invoked:
            arguments_by_recipe = _invocation_arguments(text)
            for recipe in sorted(invoked - {"setup"}):
                if recipe in recipes and recipe not in stack:
                    body = recipes[recipe]
                    for arguments in arguments_by_recipe.get(recipe, ((),)):
                        expand(
                            _substitute(body, signatures.get(recipe, ()), arguments),
                            stack | {recipe},
                            recipe_body=True,
                        )
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


_PLATFORM_ATTRIBUTES: Final = {"[windows]": "windows", "[unix]": "unix", "[linux]": "unix", "[macos]": "unix"}


def _platform_recipe_bodies(text: str, platform: str) -> dict[str, str]:
    """Return the recipe bodies one platform executes.

    A recipe declared once per platform attribute is one recipe with two
    alternative bodies; a runner executes exactly one of them, so reading both
    would count every command of the pair twice.
    """
    kept: list[str] = []
    attributes: list[str] = []
    keep = True
    for raw in text.splitlines():
        stripped = raw.strip()
        if raw.startswith("[") and stripped.endswith("]"):
            attributes.append(stripped)
            continue
        if _RECIPE_HEADER_LINE.match(raw):
            declared = {_PLATFORM_ATTRIBUTES[item] for item in attributes if item in _PLATFORM_ATTRIBUTES}
            keep = not declared or platform in declared
            attributes = []
        elif raw.strip() and raw[:1] not in {" ", "\t", "@"}:
            keep = True
            attributes = []
        if keep:
            kept.append(raw)
    return _recipe_bodies("\n".join(kept))


_RECIPE_HEADER_LINE: Final = re.compile(r"^[a-z][\w-]*\b[^:\n]*:(?![=])")


def _job_platform(job: dict[str, Any]) -> str:
    return "windows" if "Windows" in str(job.get("runs-on", "")) else "unix"


def test_platform_variant_recipes_are_read_once_per_platform() -> None:
    """Teeth for the reader above: a pair counts once, a real repeat still counts twice."""
    justfile = (
        "[unix]\ngate:\n    uv run check\n\n[windows]\ngate:\n    uv run check\n\n"
        "twice:\n    uv run check\n    uv run check\n"
    )
    unix = _platform_recipe_bodies(justfile, "unix")
    assert Counter(_commands({"steps": [{"run": "just gate"}]}, unix))["uv run check"] == 1
    assert Counter(_commands({"steps": [{"run": "just twice"}]}, unix))["uv run check"] == 2


def test_one_parameterised_recipe_with_two_arguments_is_not_a_duplicate() -> None:
    """Teeth for the substitution: different arguments are different commands.

    The expander reads a recipe BODY, so before arguments were substituted one
    parameterised recipe invoked twice expanded to identical text twice and was
    reported as a command scheduled twice. It fired on two real
    `release-runtime-matrix` invocations requesting different phases, and it
    would have fired on every future conversion to a parameterised recipe --
    a standing tax on exactly the refactor this repository wants.
    """
    justfile = "emit PHASE:\n    uv run matrix --phase {{PHASE}}\n"
    bodies = _platform_recipe_bodies(justfile, "unix")
    parameters = _recipe_parameters(justfile)
    job = {"steps": [{"run": "just emit next"}, {"run": "just emit smoke"}]}

    counts = Counter(_commands(job, bodies, parameters))

    assert counts == Counter({"uv run matrix --phase next": 1, "uv run matrix --phase smoke": 1})


def test_one_parameterised_recipe_with_the_same_argument_twice_is_a_duplicate() -> None:
    """The half that must not be lost: substitution cannot buy silence.

    A fix that made every invocation look distinct would pass the case above
    while reporting no duplicate ever again, which is the check degrading into
    nothing. The same argument twice is still the same command twice.
    """
    justfile = "emit PHASE:\n    uv run matrix --phase {{PHASE}}\n"
    bodies = _platform_recipe_bodies(justfile, "unix")
    parameters = _recipe_parameters(justfile)
    job = {"steps": [{"run": "just emit smoke"}, {"run": "just emit smoke"}]}

    counts = Counter(_commands(job, bodies, parameters))

    assert counts["uv run matrix --phase smoke"] == 2


def test_a_declared_default_is_substituted_when_no_argument_is_given() -> None:
    """A recipe invoked bare runs its default, and the expansion must say so."""
    justfile = 'check base="origin/main":\n    uv run diff --base {{base}}\n'
    bodies = _platform_recipe_bodies(justfile, "unix")
    parameters = _recipe_parameters(justfile)

    commands = _commands({"steps": [{"run": "just check"}]}, bodies, parameters)

    assert commands == ["uv run diff --base origin/main"]


def test_a_parameter_with_no_argument_and_no_default_keeps_its_placeholder() -> None:
    """Inventing a value would make two identical invocations look different."""
    justfile = "emit PHASE:\n    uv run matrix --phase {{PHASE}}\n"
    bodies = _platform_recipe_bodies(justfile, "unix")
    parameters = _recipe_parameters(justfile)
    job = {"steps": [{"run": "just emit"}, {"run": "just emit"}]}

    counts = Counter(_commands(job, bodies, parameters))

    assert counts["uv run matrix --phase {{PHASE}}"] == 2


def test_no_command_runs_twice_in_one_workflow_run() -> None:
    """A workflow never schedules the same explicit command twice for one event."""
    duplicates: list[str] = []
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    bodies = {platform: _platform_recipe_bodies(justfile, platform) for platform in ("unix", "windows")}
    parameters = _recipe_parameters(justfile)
    for path, document in _documents():
        for key, job in (document.get("jobs") or {}).items():
            counts = Counter(_commands(job, bodies[_job_platform(job)], parameters))
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
