"""Repository-wide TOML and YAML syntax, lint, and safe-format checks."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Final

from yamllint.config import YamlLintConfig
from yamllint.linter import run as run_yamllint

from dev._paths import REPO_ROOT, UTF_8
from dev.source_tree import repository_files

_SUFFIXES: Final = frozenset({".toml", ".yaml", ".yml"})
_BYTE_EXACT_PREFIX: Final = "src/cadrumo/_data/corpus/"
_LOCALE_PREFIX: Final = "src/cadrumo/locales/"
_YAML_CONFIG: Final = YamlLintConfig("""
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
    return tuple(path for path in repository_files(root) if Path(path).suffix.lower() in _SUFFIXES and not path.startswith(_BYTE_EXACT_PREFIX))


def check_file(path: Path, *, display: str | None = None) -> tuple[str, ...]:
    """Return syntax, lint, and safe-format findings for one data file."""
    label = display or path.as_posix()
    try:
        raw = path.read_bytes()
        text = raw.decode(UTF_8)
    except (OSError, UnicodeError) as exc:
        return (f"{label}: unreadable UTF-8: {exc}",)
    findings: list[str] = []
    if b"\r" in raw:
        findings.append(f"{label}: contains CR or CRLF line endings; expected LF")
    if raw and not raw.endswith(b"\n"):
        findings.append(f"{label}: missing final newline")
    findings.extend(f"{label}:{number}: trailing whitespace" for number, line in enumerate(text.splitlines(), 1) if line.rstrip(" \t") != line)
    if path.suffix.lower() == ".toml":
        try:
            tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            findings.append(f"{label}: invalid TOML: {exc}")
    else:
        findings.extend(f"{label}:{problem.line}:{problem.column}: {problem.message} ({problem.rule})" for problem in run_yamllint(text, _YAML_CONFIG, filepath=label))
    return tuple(findings)


def check(root: Path = REPO_ROOT, paths: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Return findings for explicit paths or every governed data file."""
    findings: list[str] = []
    for relative in paths or data_files(root):
        findings.extend(check_file(root / relative, display=relative))
    return tuple(findings)


def _resolve_owned_path(root: Path, raw_path: str) -> tuple[Path, str]:
    candidate = Path(raw_path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("path must stay inside the repository") from exc
    if Path(relative).suffix.lower() not in _SUFFIXES:
        raise ValueError("path must name a TOML or YAML file")
    if relative.startswith(_BYTE_EXACT_PREFIX):
        raise ValueError("byte-exact corpus files must never be rewritten")
    if relative.startswith(_LOCALE_PREFIX):
        raise ValueError("locale catalogue mutations belong to the locale CLI")
    if not resolved.is_file():
        raise ValueError("path must name an existing file")
    return resolved, relative


def fix_file(root: Path, raw_path: str) -> str:
    """Apply safe whitespace repairs to one explicitly owned file."""
    path, relative = _resolve_owned_path(root, raw_path)
    text = path.read_text(encoding=UTF_8)
    repaired = "\n".join(line.rstrip(" \t") for line in text.splitlines()) + "\n"
    path.write_text(repaired, encoding=UTF_8, newline="\n")
    return relative


def main(argv: list[str] | None = None) -> int:
    """Run the data-file quality command."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("paths", nargs="*")
    fix_parser = subparsers.add_parser("fix")
    fix_parser.add_argument("path")
    args = parser.parse_args(argv)
    if args.command == "check":
        findings = check(paths=tuple(args.paths))
        print("\n".join(findings))
        return 1 if findings else 0
    try:
        fixed = fix_file(REPO_ROOT, args.path)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"refusing data-file repair: {exc}", file=sys.stderr)
        return 2
    findings = check(REPO_ROOT, (fixed,))
    print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
