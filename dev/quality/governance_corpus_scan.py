"""Detectors for the one-way ``src/`` -> governance-corpus boundary.

The ``.vault/`` decision corpus and the ``.vaultspec/`` agent harness are
removable development scaffolding layered over the product, exactly as the
development tooling tree is. By operator ruling the direction is one-way and
ABSOLUTE: the scaffolding may know about ``src/``, and no file under ``src/``
-- shipped module, test module, or shipped data -- may know about the
scaffolding, in code, in prose, or as a path literal.

Why a second scan module beside :mod:`.import_hygiene_scan`
-----------------------------------------------------------
That module's tooling-tree families (5, 6 and 10) already close their half of
the boundary for PYTHON modules, and they are proven. This module closes the
two gaps that remain, and it is scoped to exactly those:

* the governance trees ``.vault`` and ``.vaultspec``, which no family scanned
  at all; and
* every NON-Python file under ``src/``, for all three trees.
  ``src/cadrumo/_data/`` ships inside the wheel, so a TOML row naming a
  scanner under the development tree hands an installed user a locator into a
  tree they do not have. An AST scan cannot see that file, which is precisely
  how such rows accumulated while a green Python-only gate reported a clean
  boundary.

The AST walk itself is NOT re-implemented here. The docstring-identification,
comment-tokenisation and prose-string helpers are imported from
:mod:`.import_hygiene_scan`, because a second copy of a shape rule is the
failure ``modelo-export-mirrors-official-structure`` documents: the two copies
drift and then disagree about what the rule was.

Precision
---------
The governance roots are dot-prefixed, which removes the whole class of
near-miss this repo really contains on the bare tooling-root word. What it
does NOT remove is the DOTTED-ATTRIBUTE near-miss, and that one is live in the
tree today: ``storage.google_drive.errors.vault_folder_name_blank`` and the
``cadrumo-vault/`` Drive folder are product vocabulary, named for the
operator's encrypted store, and have nothing to do with the decision corpus.
The rules below therefore require the root to BEGIN a token -- the leading dot
must not be an attribute separator -- and to END at a non-word character, so
``.vault_folder``, ``.vaults`` and ``cadrumo_vault_app`` stay silent while
``.vault/adr/x.md`` and ``./.vaultspec/rules`` fire.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8
from .import_hygiene_scan import (
    DEV_TOOLING_ROOT,
    SRC_ROOT,
    _comment_lines,
    _docstring_constant_ids,
    _prose_string_lines,
)

__all__ = [
    "GOVERNANCE_TREE_ROOTS",
    "GovernanceProseViolation",
    "GovernanceRefForm",
    "GovernanceTreePathViolation",
    "ScaffoldingDataReference",
    "find_governance_path_violations",
    "find_governance_prose_violations",
    "find_scaffolding_data_references",
    "governance_path_hits",
    "live_governance_roots",
    "names_governance_directory",
    "prose_token_names_governance_tree",
    "scannable_data_files",
]

#: The removable governance trees, longest first so an alternation match
#: prefers ``.vaultspec`` over its own ``.vault`` prefix.
GOVERNANCE_TREE_ROOTS: Final[tuple[str, ...]] = (".vaultspec", ".vault")


# ---------------------------------------------------------------------------
# Token-level rules
# ---------------------------------------------------------------------------

#: A governance root standing as its own token.
#:
#: The lookbehind refuses a root that CONTINUES a word or a dotted attribute
#: path, which is what keeps ``google_drive.errors.vault_folder_name`` and
#: ``cadrumo-vault`` silent; it deliberately admits a preceding separator so
#: ``./.vault/adr`` and ``../.vaultspec/rules`` still fire. The lookahead
#: refuses a longer identifier, which keeps ``.vault_folder`` and ``.vaults``
#: silent while leaving ``.vaultspec`` to the earlier alternative.
_GOVERNANCE_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9_.\-])(" + "|".join(re.escape(root) for root in GOVERNANCE_TREE_ROOTS) + r")(?![A-Za-z0-9_])"
)

#: A relative tooling-tree path opening a token, for the free-text data scan.
#:
#: Python modules are covered far more precisely by ``import_hygiene_scan``'s
#: AST families; this pattern exists for TOML, JSON, YAML and Markdown, where
#: there is no syntax tree to consult. The lookbehind refuses any preceding
#: path or word character, so the POSIX device nodes ``/dev/null`` and
#: ``/dev/tty`` and another tree's nested tooling segment stay silent, and a
#: separator is required afterwards so the bare English word cannot fire.
#:
#: The optional leading ``./`` or ``../`` run is what lets a repo-relative
#: ``./dev/quality/baseline.json`` fire while ``/dev/null`` still does not:
#: the lookbehind is applied before the relative markers, so the marker run
#: extends the token leftwards rather than sitting where an absolute path's
#: root separator would.
_TOOLING_PATH_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9_.\-/\\])(?:\.{1,2}[/\\])*" + re.escape(DEV_TOOLING_ROOT) + r"[/\\]"
)


def names_governance_directory(value: str) -> str | None:
    """Return the governance root ``value`` names as a path, else ``None``.

    Segment-aware, never a substring test. A segment must EQUAL a governance
    root; unlike the tooling-root rule in :mod:`.import_hygiene_scan` no
    position restriction is applied, because a dot-prefixed ``.vault`` segment
    cannot arise from ordinary vocabulary the way the bare tooling word does --
    there is no device node, no Spanish stem, and no third-party host name
    that produces one. A value spanning lines is prose, never a path literal,
    and is refused here; prose is judged by
    :func:`prose_token_names_governance_tree`.
    """
    if not value or "\n" in value or "\r" in value:
        return None
    segments = value.replace("\\", "/").split("/")
    for root in GOVERNANCE_TREE_ROOTS:
        if root in segments:
            return root
    return None


def prose_token_names_governance_tree(token: str) -> str | None:
    """Return the governance root one prose token names, else ``None``.

    Prose tokens are comment, docstring and multi-line-string words. Wrapping
    punctuation is stripped first so a token cited inside backticks, brackets
    or quotes is read as the reference it is.
    """
    return _matched_governance_root(token.strip("()[]{}`'\"<>,:;"))


def _matched_governance_root(text: str) -> str | None:
    """Return the governance root ``text`` contains as a standalone token.

    The root is read back by slicing the subject rather than through
    ``Match.group``, whose return type widens to ``Any`` and would silently
    launder a typing mistake at every call site.
    """
    match = _GOVERNANCE_TOKEN_RE.search(text)
    if match is None:
        return None
    return text[match.start(1) : match.end(1)]


# ---------------------------------------------------------------------------
# Violation records
# ---------------------------------------------------------------------------


class GovernanceRefForm(StrEnum):
    """The syntactic shape a module under ``src/`` used to name a governance tree."""

    LITERAL = "literal"
    PATH_JOIN = "path_join"
    CALL_JOIN = "call_join"
    FSTRING = "fstring"


@dataclass
class GovernanceTreePathViolation:
    """A module under ``src/`` that builds a path into a governance tree."""

    module_path: str
    lineno: int
    form: GovernanceRefForm
    root: str
    detail: str


@dataclass
class GovernanceProseViolation:
    """A comment, docstring or multi-line string under ``src/`` naming a governance tree."""

    module_path: str
    lineno: int
    source_kind: str  # "comment" | "string"
    root: str
    detail: str


@dataclass
class ScaffoldingDataReference:
    """A non-Python file under ``src/`` naming a removable scaffolding tree."""

    file_path: str
    lineno: int
    tree: str
    detail: str


# ---------------------------------------------------------------------------
# Python-module families
# ---------------------------------------------------------------------------

#: ``join`` is gated on two or more arguments below: ``sep.join(iterable)`` is
#: a string operation with a single argument and is never a path assembly.
_SEGMENT_JOIN_CALLABLES: Final[frozenset[str]] = frozenset({"join"})
_PATH_FACTORY_CALLABLES: Final[frozenset[str]] = frozenset(
    {"Path", "PurePath", "PosixPath", "PurePosixPath", "WindowsPath", "PureWindowsPath", "joinpath"}
)


def _is_bare_governance_segment(node: ast.expr) -> str | None:
    """Return the root if ``node`` is a bare governance-root string constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in GOVERNANCE_TREE_ROOTS:
        return node.value
    return None


def _called_function_name(func: ast.expr) -> str | None:
    """Return the trailing callable name of ``func``, or ``None`` if unreadable."""
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _call_assembled_governance_segment(node: ast.Call) -> tuple[str, str] | None:
    """Return ``(root, detail)`` if ``node`` assembles a path from a governance segment."""
    name = _called_function_name(node.func)
    if name is None:
        return None
    if name in _SEGMENT_JOIN_CALLABLES:
        if len(node.args) < 2:
            return None
    elif name not in _PATH_FACTORY_CALLABLES:
        return None
    for arg in node.args:
        root = _is_bare_governance_segment(arg)
        if root is not None:
            return root, f'{name}(...) with a "{root}" path segment'
    return None


def governance_path_hits(tree: ast.Module) -> list[tuple[int, GovernanceRefForm, str, str]]:
    """Return every ``(lineno, form, root, detail)`` governance reach in one module.

    Four forms, matching the proven tooling-tree family, because the boundary
    breaks in all four and a scanner covering only literals cannot see the
    realistic anchored case:

    * ``literal`` -- ``".vault/adr/x.md"``, ``"./.vaultspec/rules"``
    * ``path_join`` -- ``PROJECT_ROOT / ".vault" / "adr"``
    * ``call_join`` -- ``os.path.join(root, ".vault")``, ``Path(root, ".vault")``
    * ``fstring`` -- ``f"{root}/.vault/adr/x.md"``

    Construction is the trigger, not the read: a module constant assigned once
    and consumed elsewhere depends on the corpus just as hard as an inline
    ``read_text``, and demanding an adjacent read would let exactly that shape
    through.

    Docstrings are excluded here and judged as prose instead, so no line is
    reported by two families.
    """
    skip = _docstring_constant_ids(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            skip.update(id(part) for part in node.values if isinstance(part, ast.Constant))

    hits: list[tuple[int, GovernanceRefForm, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if not (isinstance(part, ast.Constant) and isinstance(part.value, str)):
                    continue
                root = names_governance_directory(part.value)
                if root is not None:
                    hits.append((node.lineno, GovernanceRefForm.FSTRING, root, part.value))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            root = _is_bare_governance_segment(node.right) or _is_bare_governance_segment(node.left)
            if root is not None:
                detail = f'{ast.unparse(node)!s} (path join onto "{root}")'
                hits.append((node.lineno, GovernanceRefForm.PATH_JOIN, root, detail))
        elif isinstance(node, ast.Call):
            assembled = _call_assembled_governance_segment(node)
            if assembled is not None:
                hits.append((node.lineno, GovernanceRefForm.CALL_JOIN, assembled[0], assembled[1]))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            root = names_governance_directory(node.value)
            if root is not None:
                hits.append((node.lineno, GovernanceRefForm.LITERAL, root, node.value))
    return hits


def find_governance_path_violations(
    py_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[GovernanceTreePathViolation]:
    """Return every module under ``src_root`` that builds a governance-tree path.

    Args:
        py_files: Module files to scan.
        src_root: Source root used to resolve relative paths.
    """
    violations: list[GovernanceTreePathViolation] = []
    for path in py_files:
        rel = path.relative_to(src_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding=UTF_8), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        violations.extend(
            GovernanceTreePathViolation(rel, lineno, form, root, detail)
            for lineno, form, root, detail in governance_path_hits(tree)
        )
    return sorted(violations, key=lambda v: (v.module_path, v.lineno, v.form, v.detail))


def find_governance_prose_violations(
    py_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[GovernanceProseViolation]:
    """Return every prose site under ``src_root`` that names a governance tree.

    The awareness half of the boundary: a comment or docstring citing a
    decision record is a dangling reference for every reader who received the
    wheel without the corpus, and the "Code Stands Alone" mandate forbids it
    outright.

    Args:
        py_files: Module files to scan.
        src_root: Source root used to resolve relative paths.
    """
    violations: list[GovernanceProseViolation] = []
    for path in py_files:
        rel = path.relative_to(src_root).as_posix()
        try:
            source = path.read_text(encoding=UTF_8)
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for kind, lines in (("string", _prose_string_lines(tree)), ("comment", _comment_lines(source))):
            for lineno, text in lines:
                for token in text.split():
                    root = prose_token_names_governance_tree(token)
                    if root is not None:
                        violations.append(GovernanceProseViolation(rel, lineno, kind, root, text.strip()))
                        break
    return sorted(violations, key=lambda v: (v.module_path, v.lineno, v.source_kind))


# ---------------------------------------------------------------------------
# Shipped-data family: every NON-Python file under src/
# ---------------------------------------------------------------------------

#: Extensions whose bytes are not text and cannot carry a readable locator.
#: Kept as a skip list rather than an allow list so a newly introduced text
#: format is scanned by default; the cost of a wrong guess is one decode
#: failure, which is skipped, never a silent exemption.
_BINARY_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".pdf", ".xlsx", ".xls", ".xlsm", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".ofx", ".pyc", ".so", ".pyd"}
)

_PRUNED_DIRECTORIES: Final[frozenset[str]] = frozenset({"__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"})


def scannable_data_files(src_root: Path = SRC_ROOT) -> list[Path]:
    """Return every non-Python, non-binary file under ``src_root``.

    This is the population an AST scan structurally cannot reach: registry
    TOML, JSON manifests, YAML, Markdown and plain text, all of which ship in
    the wheel under ``src/cadrumo/_data/`` and all of which can carry a path
    into a tree the installed user does not have.
    """
    files: list[Path] = []
    for path in src_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _PRUNED_DIRECTORIES for part in path.parts):
            continue
        if path.suffix == ".py" or path.suffix.lower() in _BINARY_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def find_scaffolding_data_references(
    data_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[ScaffoldingDataReference]:
    """Return every non-Python file under ``src_root`` naming a removable tree.

    All three trees are checked here -- ``.vault``, ``.vaultspec`` and the
    development tooling root -- because this is the only family that reads
    these files at all. The Python-module families in
    :mod:`.import_hygiene_scan` cover the tooling root for modules and would
    report nothing about a TOML row.

    At most one reference is reported per line: a line already condemned for
    naming a governance tree does not need a second verdict, and the first hit
    is enough to locate it.

    Args:
        data_files: Files to scan; binaries are skipped by decode failure.
        src_root: Source root used to resolve relative paths.
    """
    references: list[ScaffoldingDataReference] = []
    for path in data_files:
        try:
            text = path.read_text(encoding=UTF_8)
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(src_root).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            governance = _matched_governance_root(line)
            if governance is not None:
                references.append(ScaffoldingDataReference(rel, lineno, governance, line.strip()))
                continue
            if _TOOLING_PATH_TOKEN_RE.search(line) is not None:
                references.append(ScaffoldingDataReference(rel, lineno, DEV_TOOLING_ROOT, line.strip()))
    return sorted(references, key=lambda r: (r.file_path, r.lineno))


def live_governance_roots() -> frozenset[str]:
    """Return the governance roots that actually exist at the repository root.

    A gate whose subject has been renamed away reports exactly what a clean
    tree reports. Callers assert against this so the declared roots cannot
    quietly stop naming anything real.
    """
    return frozenset(root for root in GOVERNANCE_TREE_ROOTS if (REPO_ROOT / root).is_dir())
