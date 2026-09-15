"""Repository-wide TOML and YAML syntax, lint, and safe-format checks."""

from __future__ import annotations

import argparse
import os
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Final

from yamllint.config import YamlLintConfig
from yamllint.linter import run as run_yamllint

from dev._paths import REPO_ROOT, UTF_8
from dev.source_tree import repository_files

_SUFFIXES: Final[frozenset[str]] = frozenset({".toml", ".yaml", ".yml"})
_BYTE_EXACT_PREFIX: Final[str] = "src/cadrumo/_data/corpus/"
_YAML_CONFIG: Final[YamlLintConfig] = YamlLintConfig("""
extends: relaxed
rules:
  document-start: disable
  indentation:
    indent-sequences: consistent
  line-length: disable
  truthy: disable
""")


def data_files(root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Return checked TOML/YAML files from the live source tree."""
    return tuple(
        path
        for path in repository_files(root, under=_enumeration_roots(root))
        if Path(path).suffix.lower() in _SUFFIXES and not path.startswith(_BYTE_EXACT_PREFIX)
    )


def _enumeration_roots(root: Path) -> tuple[str, ...]:
    """Partition the tree so enumeration never descends into byte-exact evidence."""
    excluded = _BYTE_EXACT_PREFIX.rstrip("/")

    def partition(relative: str) -> tuple[str, ...]:
        if relative == excluded:
            return ()
        if not excluded.startswith(f"{relative}/"):
            return (relative,)
        directory = root / relative
        try:
            children = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError:
            return (relative,)
        return tuple(
            nested
            for child in children
            if child.name != ".git"
            for nested in partition(f"{relative}/{child.name}" if relative else child.name)
        )

    try:
        top_level = sorted(os.scandir(root), key=lambda entry: entry.name)
    except OSError:
        return ()
    return tuple(nested for entry in top_level if entry.name != ".git" for nested in partition(entry.name))


def check_file(path: Path, *, display: str | None = None) -> tuple[str, ...]:
    """Return syntax, lint, and safe-format findings for one data file."""
    label = display or path.as_posix()
    try:
        raw = path.read_bytes()
        text = raw.decode(UTF_8)
    except (OSError, UnicodeError) as exc:
        return (f"{label}: unreadable UTF-8: {exc}",)
    findings: list[str] = []
    if raw and not raw.endswith(b"\n"):
        findings.append(f"{label}: missing final newline")
    logical_text = "\n".join(text.splitlines())
    if text.endswith(("\n", "\r")):
        logical_text += "\n"
    if path.suffix.lower() == ".toml":
        try:
            tomllib.loads(logical_text)
        except tomllib.TOMLDecodeError as exc:
            findings.append(f"{label}: invalid TOML: {exc}")
    else:
        findings.extend(
            f"{label}:{problem.line}:{problem.column}: {problem.message} ({problem.rule})"
            for problem in run_yamllint(logical_text, _YAML_CONFIG, filepath=label)
        )
    return tuple(findings)


def check(root: Path = REPO_ROOT, paths: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Return findings for explicit paths or every governed data file."""
    selected = paths or data_files(root)

    def inspect(relative: str) -> tuple[str, ...]:
        return check_file(root / relative, display=relative)

    with ThreadPoolExecutor() as pool:
        return tuple(finding for file_findings in pool.map(inspect, selected) for finding in file_findings)


def main(argv: list[str] | None = None) -> int:
    """Run the data-file quality command."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    if args.command == "check":
        findings = check(paths=tuple(args.paths))
        if findings:
            print("\n".join(findings))
        return 1 if findings else 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
