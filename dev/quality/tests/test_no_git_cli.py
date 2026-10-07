"""Repository-owned code must never resolve or launch the Git executable."""

from __future__ import annotations

import ast
import json
import re
from pathlib import PurePosixPath, PureWindowsPath

import pytest
import yaml

from dev._paths import REPO_ROOT, UTF_8
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXECUTORS = frozenset(
    {
        "run",
        "_run",
        "run_command",
        "Popen",
        "call",
        "check_call",
        "check_output",
        "system",
        "popen",
        "create_subprocess_exec",
        "create_subprocess_shell",
        "exec",
        "execFile",
        "execSync",
        "execFileSync",
        "spawn",
        "spawnSync",
    }
)
_SHELL_GIT = re.compile(
    r"(?:^|[;&|\n(])\s*(?:[&@]\s*)?(?:(?:then|do|else|sudo|command|env|call)\s+)?"
    r"[\"']?(?:[^\s\"';|()]*[/\\])?git(?:\.exe)?[\"']?(?=\s|$)",
    re.IGNORECASE,
)
_NATIVE_GIT = re.compile(
    r"\b(?:COMMAND|FilePath|Get-Command)\s+[\"']?git(?:\.exe)?(?:[\"']|\s|$)"
    r"|\b(?:new|exec|execFile|execSync|execFileSync|spawn|spawnSync|system)\s*\(\s*[\"']git(?:\.exe)?(?:[\"']|\s)"
    r"|\bfind_package\s*\(\s*Git\b"
    r"|\bfind_program\s*\(\s*\w+\s+(?:NAMES\s+)?git(?:\.exe)?\b",
    re.IGNORECASE,
)
_COMMAND_KEYS = frozenset({"run", "script", "entry", "entrypoint", "command"})


def _git_command(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        head = node.elts[0]
        if isinstance(head, ast.Name) and head.id in {"git", "git_executable"}:
            return True
        return _git_command(head)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (
            PureWindowsPath(node.value).name.lower() in {"git", "git.exe"} or _SHELL_GIT.search(node.value) is not None
        )
    return False


def python_invokes_git(source: str) -> bool:
    """Detect executable resolution and process calls without scanning string fixtures."""
    tree = ast.parse(source)
    aliases = {
        alias.asname: alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.asname
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = (
            node.func.attr
            if isinstance(node.func, ast.Attribute)
            else (node.func.id if isinstance(node.func, ast.Name) else "")
        )
        name = aliases.get(name, name)
        if name in {"which", "find_executable"} and node.args and _git_command(node.args[0]):
            return True
        if name in _EXECUTORS:
            arguments = [
                *node.args,
                *(item.value for item in node.keywords if item.arg in {"args", "cmd", "command", "argv"}),
            ]
            if any(_git_command(argument) for argument in arguments):
                return True
    return False


def shell_invokes_git(source: str) -> bool:
    """Detect shell, PowerShell, CMake and native process invocations."""
    commands = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith(("#", "//")))
    return _SHELL_GIT.search(commands) is not None or _NATIVE_GIT.search(commands) is not None


def _workflow_invokes_git(value: object) -> bool:
    if isinstance(value, yaml.MappingNode):
        return any(
            shell_invokes_git(item.value)
            if isinstance(key, yaml.ScalarNode) and key.value in _COMMAND_KEYS and isinstance(item, yaml.ScalarNode)
            else _workflow_invokes_git(item)
            for key, item in value.value
        )
    if isinstance(value, yaml.SequenceNode):
        return any(_workflow_invokes_git(item) for item in value.value)
    if isinstance(value, dict):
        return any(
            shell_invokes_git(item) if key in _COMMAND_KEYS and isinstance(item, str) else _workflow_invokes_git(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_workflow_invokes_git(item) for item in value)
    return False


def _package_invokes_git(value: object) -> bool:
    if not isinstance(value, dict) or not isinstance(scripts := value.get("scripts"), dict):
        return False
    return any(shell_invokes_git(command) for command in scripts.values() if isinstance(command, str))


def test_repository_code_never_invokes_git() -> None:
    files = repository_files(REPO_ROOT)
    checked: list[str] = []
    offenders: list[str] = []
    for relative in files:
        path = PurePosixPath(relative)
        if path.suffix not in {
            ".py",
            ".ps1",
            ".sh",
            ".cmake",
            ".rs",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".mjs",
            ".cjs",
            ".bash",
            ".bat",
            ".cmd",
            ".yml",
            ".yaml",
        } and path.name not in {"CMakeLists.txt", "justfile", "package.json"}:
            continue
        source = (REPO_ROOT / relative).read_text(encoding=UTF_8)
        checked.append(relative)
        if path.suffix == ".py":
            found = python_invokes_git(source)
        elif path.name == "package.json":
            found = _package_invokes_git(json.loads(source))
        elif path.suffix in {".yml", ".yaml"}:
            found = any(
                _workflow_invokes_git(document) for document in yaml.compose_all(source, Loader=yaml.SafeLoader)
            )
        else:
            found = shell_invokes_git(source)
        if found:
            offenders.append(relative)
    assert checked, "the executable-source inventory is empty"
    required = {
        "src/cadrumo/entrypoints/cli/bootstrap.py",
        "dev/env/clean.py",
        "dev/ci/change_scope.py",
        "dev/packaging/smoke_scoop.ps1",
        "native/cmake/BuildNumber.cmake",
        ".github/workflows/release.yml",
        "native/desktop/frontend/package.json",
        "justfile",
    }
    assert required <= set(checked), f"Git audit is missing executable owners: {sorted(required - set(checked))}"
    print(f"Git CLI audit: {len(checked)} executable source files; {len(offenders)} offenders.")
    assert not offenders, f"Git CLI calls are forbidden: {offenders}"


@pytest.mark.parametrize(
    "source",
    [
        'import shutil\nshutil.which("git")',
        'import subprocess\nsubprocess.run(["git", "diff"])',
        'run_command(["C:/tools/git.exe", "status"])',
        'subprocess.check_output(args=["git", "rev-parse", "HEAD"])',
        'os.system("git status")',
        'from subprocess import run as execute\nexecute(["git", "status"])',
        'subprocess.run(["C:/Program Files/Git/bin/git.exe", "status"])',
    ],
)
def test_python_detector_rejects_git_calls(source: str) -> None:
    assert python_invokes_git(source)


@pytest.mark.parametrize(
    "source",
    [
        'text = \'subprocess.run(["git", "diff"])\'',
        'sorted(["git", "cadrumo"])',
        'shutil.which("cmake")',
    ],
)
def test_python_detector_accepts_data_and_other_tools(source: str) -> None:
    assert not python_invokes_git(source)


@pytest.mark.parametrize(
    "source",
    [
        "git diff --quiet",
        'value="$(git rev-parse HEAD)"',
        'Invoke-Native -FilePath "git" -ArgumentList @("init")',
        "execute_process(COMMAND git rev-list --count HEAD)",
        "find_package(Git REQUIRED)",
        "find_program(VERSION_CONTROL NAMES git REQUIRED)",
        'Command::new("git").arg("status");',
        'child_process.execSync("git status");',
        "if ready; then git status; fi",
    ],
)
def test_native_and_shell_detector_rejects_git_calls(source: str) -> None:
    assert shell_invokes_git(source)


def test_workflow_detector_checks_nested_actions_without_running_them() -> None:
    assert _workflow_invokes_git({"jobs": {"check": {"steps": [{"run": "git diff"}]}}})
    assert not _workflow_invokes_git({"steps": [{"run": 'gh api "repos/owner/project/git/refs"'}]})


def test_yaml_detector_reads_tagged_data_without_constructing_it() -> None:
    source = "resource: !Ref Bucket\nsteps:\n  - run: git status\n"
    assert _workflow_invokes_git(yaml.compose(source, Loader=yaml.SafeLoader))


@pytest.mark.parametrize("command, expected", [("git status", True), ("node scripts/bootstrap.mjs", False)])
def test_node_package_commands_are_checked_without_running_them(command: str, expected: bool) -> None:
    assert _package_invokes_git({"scripts": {"build": command}}) is expected


def test_yaml_detector_checks_declared_hook_commands() -> None:
    assert _workflow_invokes_git(yaml.compose("hooks:\n  - entry: git diff\n", Loader=yaml.SafeLoader))
