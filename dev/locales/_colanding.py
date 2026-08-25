"""Co-landing check: a catalogue key must land in the same change as its call site.

Every other locale gate in this repo compares STATE -- the current codebase key
set against the current catalogue key set. A state comparison is correct and
useless at the same moment: it turns red only after the offending commit has
landed, and it cannot say which change caused it. Three commits have shipped a
code-side key change with no catalogue-side change and passed every hook on the
way in, because at the instant they were written no gate was looking at the
change at all.

This module compares a CHANGE. It resolves a revision pair, extracts the locale
keys each modified Python module declared before and after, and holds two
invariants over that delta:

* A key the change ADDS a call site for must exist in every catalogue as the
  change leaves them. Otherwise the commit ships an operator-facing string that
  renders as its own key, or falls through to a hardcoded ``default=``.
* A key whose LAST call site the change removes must not be left standing in the
  catalogues. Otherwise the commit orphans a key nobody will attribute later.

The second invariant has one derived exemption, and it is derived rather than
allowlisted on purpose. A command family the operator surface declares but has
not built -- :attr:`FamilyMountState.DECLARED_UNIMPLEMENTED` -- HOLDS its
catalogue strings: nothing reaches them, so they have no call site, but they are
not retirement residue either, and pruning them would assert a retirement no
ruling supports. That distinction already has an owner in
``MOUNTED_COMMAND_FAMILIES``, so this reads the answer there instead of keeping a
second, hand-maintained list that could disagree with it.

Deliberately NOT checked: a catalogue key added ahead of any call site. Bulk
scaffolding and the registry authoring sweep both legitimately add catalogue
content in their own commits, so that direction fires constantly on correct work,
and a gate that cries wolf is turned off by whoever it first annoys. The standing
whole-tree audit already reports an uncatalogued surplus after the fact.

Also NOT checked, and named here so the coverage is not overstated: SEMANTIC
staleness. This compares key SETS. A catalogue value whose text names a verb that
was retired stays structurally perfect, so a change that retires the verb passes
this gate cleanly while leaving four locales instructing the operator to run a
command that no longer resolves. That is a distinct failure mode with no gate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.application.operator_surface import MOUNTED_COMMAND_FAMILIES, FamilyMountState
from cadrumo.core.external_constants import UTF_8_ENCODING

from .._paths import REPO_ROOT
from ._ast_scanner import declares_locale_keys, scan_source_text
from ._errors import LocaleError
from .manager import LocaleManager, _parse_locale

#: The change to compare when the caller names none. ``staged`` is the useful
#: default because the index is the only place a change exists before it lands.
STAGED_CHANGE: Final[str] = "staged"

#: The fallback when nothing is staged. ``prek run --all-files`` and any CI
#: invocation have an empty index, and reporting a clean result because there was
#: nothing to look at is the exact vacuity this whole module exists to avoid --
#: so the last landed commit is compared instead, and the output says which.
LAST_CHANGE: Final[str] = "last"

_INDEX_REV: Final[str] = ""
"""``git show :path`` reads the staged blob; the empty revision names the index."""


class ColandingFinding(BaseModel):
    """One key whose catalogue entry and call site did not land together."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    key: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    detail: str = Field(min_length=1)

    def render(self) -> str:
        """Render the finding as one greppable operator-facing row."""
        return f"{self.kind} key={self.key} {self.detail}"


class ColandingResult(BaseModel):
    """The outcome of comparing one change against the catalogues it leaves behind."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    change: str = Field(min_length=1)
    inspected_modules: int = Field(ge=0)
    added_keys: tuple[str, ...] = ()
    removed_keys: tuple[str, ...] = ()
    held_keys: tuple[str, ...] = ()
    findings: tuple[ColandingFinding, ...] = ()

    @property
    def ok(self) -> bool:
        """True when every key the change touched landed with its counterpart."""
        return not self.findings


def _git(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed executable, arguments are internal
        ["git", *arguments],  # noqa: S607 - resolved from PATH, as every other dev tool here is
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding=UTF_8_ENCODING,
        errors="replace",
        check=False,
    )


def _blob(repo_root: Path, revision: str, path: str) -> str:
    """Return one path's content at ``revision``, or empty when it does not exist.

    An added file has no content at the base revision and a deleted file has none
    at the head; both read as an empty module, which is exactly right -- an added
    file declares every key it carries, and a deleted file declares none.
    """
    result = _git(repo_root, "show", f"{revision}:{path}")
    return result.stdout if result.returncode == 0 else ""


def _changed_python_paths(repo_root: Path, base: str, head: str | None) -> tuple[str, ...]:
    """Return the repo-relative Python paths the change touches."""
    if head is None:
        result = _git(repo_root, "diff", "--cached", "--name-only", "--diff-filter=ACMRD", base)
    else:
        result = _git(repo_root, "diff", "--name-only", "--diff-filter=ACMRD", base, head)
    if result.returncode != 0:
        raise LocaleError(f"could not list the changed files: {result.stderr.strip()}")
    return tuple(
        line
        for line in (raw.strip() for raw in result.stdout.splitlines())
        if line.endswith(".py") and declares_locale_keys(Path(line))
    )


def _index_has_content(repo_root: Path) -> bool:
    return _git(repo_root, "diff", "--cached", "--quiet").returncode != 0


class _Change(BaseModel):
    """A resolved revision pair plus the label reported to the operator."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    label: str = Field(min_length=1)
    base: str = Field(min_length=1)
    head: str | None = None

    @property
    def head_revision(self) -> str:
        """The revision to read post-change content from; the index when staged."""
        return _INDEX_REV if self.head is None else self.head


def resolve_change(selector: str, repo_root: Path = REPO_ROOT) -> _Change:
    """Resolve a change selector to the revision pair to compare.

    ``staged`` compares the index against ``HEAD`` and falls back to ``last``
    when nothing is staged. ``last`` compares ``HEAD~1`` against ``HEAD``.
    Anything else is passed through as a ``BASE..HEAD`` range, which is the form
    a pull-request check names its own change with.
    """
    if selector == STAGED_CHANGE:
        if _index_has_content(repo_root):
            return _Change(label="staged changes against HEAD", base="HEAD")
        return resolve_change(LAST_CHANGE, repo_root)
    if selector == LAST_CHANGE:
        return _Change(label="HEAD~1..HEAD", base="HEAD~1", head="HEAD")
    base, separator, head = selector.partition("..")
    if not separator or not base.strip() or not head.strip():
        raise LocaleError(
            f"unrecognised change selector {selector!r}; expected {STAGED_CHANGE!r}, {LAST_CHANGE!r}, or BASE..HEAD",
        )
    return _Change(label=selector, base=base.strip(), head=head.strip())


def _held_family_namespaces() -> frozenset[str]:
    """Return the ``cli.<root>.<child>.`` prefixes of declared-unimplemented families."""
    return frozenset(
        f"cli.{family.root.value}.{family.child}."
        for family in MOUNTED_COMMAND_FAMILIES
        if family.mount_state is FamilyMountState.DECLARED_UNIMPLEMENTED
    )


def _catalogue_key_sets(manager: LocaleManager, repo_root: Path, revision: str) -> dict[str, set[str]]:
    """Return each catalogue's key set as the change leaves it.

    Read from the revision rather than the working tree on purpose: the question
    is whether the key lands with its call site, and an unstaged catalogue edit
    sitting in the checkout is not part of the change being judged.
    """
    key_sets: dict[str, set[str]] = {}
    for locale_path in sorted(manager.locales_dir.glob("*.yml")):
        content = _blob(repo_root, revision, locale_path.relative_to(repo_root).as_posix())
        if not content.strip():
            continue
        key_sets[locale_path.name] = manager.get_yaml_keys(_parse_locale(content))
    return key_sets


def check_colanding(
    manager: LocaleManager,
    selector: str = STAGED_CHANGE,
    repo_root: Path = REPO_ROOT,
) -> ColandingResult:
    """Compare one change's locale-key delta against the catalogues it leaves.

    The full-tree confirmation behind the orphan invariant is deliberately lazy:
    it runs only when the change actually removed a call site, so an ordinary
    commit costs one ``git diff`` and a handful of blob reads.
    """
    change = resolve_change(selector, repo_root)
    paths = _changed_python_paths(repo_root, change.base, change.head)

    before: set[str] = set()
    after: set[str] = set()
    for path in paths:
        before |= scan_source_text(_blob(repo_root, change.base, path), filename=path)
        after |= scan_source_text(_blob(repo_root, change.head_revision, path), filename=path)

    added = sorted(after - before)
    removed = sorted(before - after)

    findings: list[ColandingFinding] = []
    key_sets = _catalogue_key_sets(manager, repo_root, change.head_revision) if (added or removed) else {}

    for key in added:
        absent = tuple(name for name, keys in sorted(key_sets.items()) if key not in keys)
        if absent:
            findings.append(
                ColandingFinding(
                    key=key,
                    kind="uncatalogued-call-site",
                    detail=(
                        f"the change adds a call site but leaves no entry in {', '.join(absent)}. "
                        "Add the key in all four catalogues with `python -m dev.locales set` "
                        "before committing the call site."
                    ),
                ),
            )

    held: list[str] = []
    if removed:
        live_keys = manager.get_codebase_keys()
        held_prefixes = _held_family_namespaces()
        for key in removed:
            if key in live_keys:
                continue
            carrying = tuple(name for name, keys in sorted(key_sets.items()) if key in keys)
            if not carrying:
                continue
            if any(key.startswith(prefix) for prefix in held_prefixes):
                held.append(key)
                continue
            findings.append(
                ColandingFinding(
                    key=key,
                    kind="orphaned-catalogue-key",
                    detail=(
                        f"the change removes its last call site but leaves it in {', '.join(carrying)}. "
                        "Remove the key from all four catalogues with `python -m dev.locales remove` "
                        "in this same change, or declare the owning command family unimplemented."
                    ),
                ),
            )

    return ColandingResult(
        change=change.label,
        inspected_modules=len(paths),
        added_keys=tuple(added),
        removed_keys=tuple(removed),
        held_keys=tuple(sorted(held)),
        findings=tuple(findings),
    )


__all__ = [
    "LAST_CHANGE",
    "STAGED_CHANGE",
    "ColandingFinding",
    "ColandingResult",
    "check_colanding",
    "resolve_change",
]
