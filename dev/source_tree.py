"""The repository's files, enumerated, named and copied in-process.

Development tooling needs three answers about the repository: which files it
contains, a copy of them to build from, and a stable name for that content.
They are computed here, from the repository's own rules, rather than by asking
a version-control tool. Git is not a declared dependency, and a git process
querying the working tree takes the index lock opportunistically; one killed
mid-refresh leaves that lock behind and blocks every contributor's next commit.

Membership is the working tree minus what the repository's ``.gitignore`` files
exclude. That is the union of committed files and new files nobody has ignored,
so a checker built on it sees a change consisting entirely of new files rather
than passing it unread. Ignore rules come from ``.gitignore`` files only: a
machine's ``info/exclude`` or global excludes are one person's preferences, and
honouring them would enumerate a different tree on every machine.

Content is named and copied after the repository's ``.gitattributes`` line-ending
rules are applied, so the same committed content has the same digest on every
platform. A text file edited on Windows with CRLF line endings is the content the
repository records with LF, and it is named and copied as that. A path marked
``-text`` or ``binary`` is copied byte for byte, because corpus files are
content-addressed evidence whose declared digests a translated byte would break.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import pathspec

from ._paths import REPO_ROOT, UTF_8

__all__ = [
    "content_digest",
    "normalised_content",
    "repository_files",
    "snapshot",
]

_IGNORE_FILE: Final[str] = ".gitignore"
_ATTRIBUTES_FILE: Final[str] = ".gitattributes"

#: The version-control entry: a directory in a clone, a pointer file in a linked
#: worktree. Neither is repository content, and neither is ever descended into.
_VCS_ENTRY: Final[str] = ".git"

#: How much of a file is inspected when ``text=auto`` must decide text from
#: binary. A NUL byte within it marks the file binary, as git decides it.
_BINARY_PROBE_BYTES: Final[int] = 8000

type _TextState = Literal["text", "binary", "auto"]
type _LineEnding = Literal["lf", "crlf"]


@dataclass(frozen=True, slots=True)
class _ScopedRules:
    """One rules file, with the directory its patterns are relative to."""

    base: str
    """The directory holding the rules file, relative to the root; ``""`` at the root."""
    spec: pathspec.GitIgnoreSpec
    lines: tuple[tuple[pathspec.GitIgnoreSpec, tuple[str, ...]], ...] = ()
    """For an attributes file, each pattern paired with the attributes it sets, in file order."""


def _relative_to(base: str, relative: str) -> str | None:
    """Return ``relative`` expressed from ``base``, or ``None`` when it lies outside it."""
    if not base:
        return relative
    prefix = f"{base}/"
    return relative[len(prefix) :] if relative.startswith(prefix) else None


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding=UTF_8).splitlines()


def _ignore_rules(directory: Path, base: str) -> _ScopedRules | None:
    rules_file = directory / _IGNORE_FILE
    if not rules_file.is_file():
        return None
    return _ScopedRules(base=base, spec=pathspec.GitIgnoreSpec.from_lines(_read_lines(rules_file)))


def _is_ignored(relative: str, *, is_directory: bool, rules: Sequence[_ScopedRules]) -> bool:
    """Decide membership as git does: the deepest rule that matches wins.

    Rules files are applied shallowest first, so a nested ``.gitignore`` can
    re-include what its parent excluded and the reverse. Within one file the
    last matching pattern wins, including a ``!`` negation. A directory is
    tested with a trailing slash so that directory-only patterns apply to it.
    """
    ignored = False
    for rule in rules:
        local = _relative_to(rule.base, relative)
        if local is None:
            continue
        verdict = rule.spec.check_file(f"{local}/" if is_directory else local).include
        if verdict is not None:
            ignored = verdict
    return ignored


def repository_files(root: Path = REPO_ROOT, *, under: Iterable[str] = ()) -> tuple[str, ...]:
    """Return every repository file below ``root``, as sorted POSIX-relative paths.

    ``under`` narrows the result to the named files or directories, given
    relative to ``root``. An ignored directory is never entered, so a file
    inside one stays out even if a rule would re-include it by name, exactly
    as git treats it.
    """
    root = root.resolve()
    found: list[str] = []

    def visit(directory: Path, base: str, rules: tuple[_ScopedRules, ...]) -> None:
        own = _ignore_rules(directory, base)
        scoped = (*rules, own) if own is not None else rules
        with os.scandir(directory) as entries:
            children = sorted(entries, key=lambda entry: entry.name)
        for entry in children:
            if entry.name == _VCS_ENTRY:
                continue
            relative = f"{base}/{entry.name}" if base else entry.name
            if entry.is_dir(follow_symlinks=False):
                if not _is_ignored(relative, is_directory=True, rules=scoped):
                    visit(Path(entry.path), relative, scoped)
            elif not _is_ignored(relative, is_directory=False, rules=scoped):
                found.append(relative)

    visit(root, "", ())
    prefixes = tuple(prefix.strip("/") for prefix in under)
    if prefixes:
        found = [
            relative
            for relative in found
            if any(relative == prefix or relative.startswith(f"{prefix}/") for prefix in prefixes)
        ]
    return tuple(sorted(found))


def _attribute_rules(root: Path, files: Iterable[str]) -> tuple[_ScopedRules, ...]:
    """Load every ``.gitattributes`` among ``files``, shallowest first."""
    loaded: list[_ScopedRules] = []
    for relative in sorted(files, key=lambda item: (item.count("/"), item)):
        if Path(relative).name != _ATTRIBUTES_FILE:
            continue
        base = relative.rpartition("/")[0]
        patterns: list[tuple[pathspec.GitIgnoreSpec, tuple[str, ...]]] = []
        for line in _read_lines(root / relative):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            pattern, *attributes = stripped.split()
            patterns.append((pathspec.GitIgnoreSpec.from_lines([pattern]), tuple(attributes)))
        loaded.append(_ScopedRules(base=base, spec=pathspec.GitIgnoreSpec.from_lines([]), lines=tuple(patterns)))
    return tuple(loaded)


def _line_ending_policy(relative: str, rules: Sequence[_ScopedRules]) -> tuple[_TextState, _LineEnding]:
    """Resolve the text state and line ending ``.gitattributes`` give one path.

    Later lines override earlier ones and deeper files override shallower ones,
    which is the order the rules are walked in. ``binary`` is git's macro for
    ``-text -diff``; ``-diff`` carries no content consequence and is ignored.
    """
    text: _TextState = "auto"
    eol: _LineEnding = "lf"
    for rule in rules:
        local = _relative_to(rule.base, relative)
        if local is None:
            continue
        for spec, attributes in rule.lines:
            if not spec.match_file(local):
                continue
            for attribute in attributes:
                if attribute in {"-text", "binary"}:
                    text = "binary"
                elif attribute == "text":
                    text = "text"
                elif attribute == "text=auto":
                    text = "auto"
                elif attribute in {"eol=lf", "eol=crlf"}:
                    eol = "crlf" if attribute == "eol=crlf" else "lf"
    return text, eol


def _normalise(raw: bytes, *, text: _TextState, eol: _LineEnding) -> bytes:
    if text == "binary" or (text == "auto" and b"\0" in raw[:_BINARY_PROBE_BYTES]):
        return raw
    lf = raw.replace(b"\r\n", b"\n")
    return lf.replace(b"\n", b"\r\n") if eol == "crlf" else lf


def normalised_content(root: Path, relative: str, *, attributes: Sequence[_ScopedRules] | None = None) -> bytes:
    """Return one file's content after the repository's line-ending rules apply."""
    rules = attributes if attributes is not None else _attribute_rules(root, repository_files(root))
    text, eol = _line_ending_policy(relative, rules)
    return _normalise((root / relative).read_bytes(), text=text, eol=eol)


def content_digest(root: Path, files: Sequence[str]) -> str:
    """Name the content of ``files`` with a sha256 that is the same on every platform.

    Each file contributes its relative path and the digest of its normalised
    content, separated so that no path can be confused with content. Two trees
    with the same digest hold the same files with the same committed bytes.
    """
    rules = _attribute_rules(root, files)
    digest = hashlib.sha256()
    for relative in sorted(files):
        digest.update(relative.encode(UTF_8))
        digest.update(b"\0")
        digest.update(hashlib.sha256(normalised_content(root, relative, attributes=rules)).digest())
        digest.update(b"\n")
    return digest.hexdigest()


def snapshot(root: Path, files: Sequence[str], destination: Path) -> None:
    """Copy ``files`` into ``destination`` as the repository records their content.

    The destination must not already exist, so a snapshot never merges into a
    tree that holds something else.
    """
    if destination.exists():
        raise FileExistsError(f"snapshot destination already exists: {destination}")
    rules = _attribute_rules(root, files)
    destination.mkdir(parents=True)
    for relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        source = root / relative
        if source.is_symlink():
            shutil.copy2(source, target, follow_symlinks=False)
            continue
        target.write_bytes(normalised_content(root, relative, attributes=rules))
        shutil.copystat(source, target)
