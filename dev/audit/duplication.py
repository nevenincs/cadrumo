#!/usr/bin/env python
"""The single duplication runner: invoke jscpd, parse it, classify it honestly.

This module owns the WHOLE duplication measurement: source selection, command
construction, execution, timeout, stdout/stderr/returncode handling, parsing,
clone records, and availability classification. Both consumers -- the
``just audit-dead-weight`` recipe (through ``dev.audit.dead_weight``) and the
``dev.audit.report`` health dashboard's D2 dimension (``just report-code-health``)
-- go through :func:`run_duplication_scan`. There is
deliberately no second jscpd command anywhere in the tree: a measurement tool
that duplicates itself is the very defect it exists to detect.

The result is a typed value with exactly three states, and the distinction
between the first and the third is the point of this module:

* :attr:`DuplicationOutcome.OBSERVED_ZERO` -- jscpd ran, demonstrably inspected
  the production tree (``files_analyzed > 0``), and reported no clones.
* :attr:`DuplicationOutcome.CLONES` -- jscpd ran and reported clones.
* :attr:`DuplicationOutcome.UNAVAILABLE` -- no signal: missing executable,
  timeout, non-zero exit, or output carrying no parseable summary (which
  includes the scan-inspected-nothing case).

An unavailable scan is NEVER reported as zero. jscpd prints ``Found 0 clones.``
plus a summary table on a genuine clean run, but prints ONLY a timing line when
it matches no files at all -- so "no clones seen" and "nothing was looked at"
are different facts that a naive ``total == 0`` parse silently merges into a
false green. ``files_analyzed`` is the discriminator, and it is why
``observed_zero`` carries it.

The clone COUNT is advisory debt, not a gate: this module always exits 0 and
the health report renders clones as AMBER. Honest closure is valid evidence
plus no false green -- not zero clones.

Two limits are deliberate, recorded here so neither is re-derived as a defect:

* **Scope is the product tree.** :data:`_PRODUCT_SOURCE_ROOT` is
  :data:`dev.first_party_source.PRODUCT_PACKAGE` alone, because the governing audit scopes every instrument to
  "the intended production scope" and the duplication the campaign cares about
  is duplicate AUTHORITY in shipped code -- a second writer with weaker guards,
  not two similar-looking dev scripts. ``dev/`` is therefore unmeasured by the
  standing recipe and by the health report's D2 dimension. It is not
  unmeasurABLE: pass a different ``source_root`` to scan it on demand.
  Widening the default would fold tooling debt into the product number.

* **jscpd matches token sequences.** A concept implemented twice in different
  syntax is invisible to it, and that is exactly the duplication this project's
  rules treat as a blocker. Five ledger projections once shared one casilla fold
  differing only in an accumulator loop versus a comprehension; this runner
  reported none of them, and flagged their shared import preambles instead. A
  low percentage from this module means little COPY-PASTE survives. It has never
  meant little duplication survives, and no change to this module can make it
  mean that.

See Also:
    :func:`run_duplication_scan`
        The one runner both consumers call.
    :class:`DuplicationResult`
        The typed three-state result.
    :mod:`~dev.audit.report`
        The health dashboard that consumes this runner for its D2 dimension.
"""

from __future__ import annotations

import ast
import io
import re
import shutil
import subprocess
import sys
import tokenize
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.exit_codes import ADVISORY_BROKEN, OK
from dev.first_party_source import PRODUCT_PACKAGE, production_exclusion_globs
from dev.packaging.command_execution import run_command

_UTF_8: Final[str] = UTF_8
_ANSI: Final = re.compile(r"\x1b\[[0-9;]*m")
_FOUND: Final = re.compile(r"Found (\d+) clones?")
_TABLE_PCT: Final = re.compile(r"\((\d+(?:\.\d+)?)%\)")
_CLONE_CAP: Final[int] = 20

_JSCPD_SPEC: Final[str] = "jscpd@4.2.0"
_JSCPD_TIMEOUT_SECONDS: Final[float] = 300.0
_PRODUCT_SOURCE_ROOT: Final[Path] = Path(PRODUCT_PACKAGE)
_JSCPD_IGNORE: Final[str] = ",".join(production_exclusion_globs())

# The jscpd summary table's "Total:" row, post-ANSI-strip, reads:
#   | Total: | 1252 | 290727 | 1676107 | 65 | 1185 (0.41%) | 10882 (0.65%) |
# with box-drawing verticals. Cells are indexed against the header:
# Format | Files analyzed | Total lines | Total tokens | Clones found |
# Duplicated lines | Duplicated tokens.
_TABLE_VERTICAL: Final[str] = "│"
_TABLE_TOTAL_LABEL: Final[str] = "Total:"
_CELL_FILES_ANALYZED: Final[int] = 2
_CELL_DUPLICATED_LINES: Final[int] = 6
_MIN_TABLE_CELLS: Final[int] = 8
_CLONE_SITE: Final = re.compile(
    r"^\s*(?:-|\s)\s*(?P<path>.+?) \[(?P<start>\d+):(?P<start_column>\d+) - (?P<end>\d+):(?P<end_column>\d+)\]"
)


class DuplicationOutcome(StrEnum):
    """The three honest states a duplication scan can land in."""

    OBSERVED_ZERO = "observed_zero"
    CLONES = "clones"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CloneGroup:
    """One jscpd ``Clone found`` block, ANSI-stripped and path-normalised."""

    lines: tuple[str, ...]

    def render(self) -> str:
        """Render the block as its original multi-line console text."""
        return "\n".join(self.lines)

    def sites(self) -> tuple[tuple[str, int, int, int, int], ...]:
        """Return the source spans named by jscpd's console block."""
        sites: list[tuple[str, int, int, int, int]] = []
        for line in self.lines[1:]:
            match = _CLONE_SITE.match(line)
            if match is not None:
                sites.append(
                    (
                        match.group("path"),
                        int(match.group("start")),
                        int(match.group("start_column")),
                        int(match.group("end")),
                        int(match.group("end_column")),
                    )
                )
        return tuple(sites)


@dataclass(frozen=True)
class DuplicationResult:
    """A duplication scan's typed outcome.

    Construct through :meth:`observed_zero`, :meth:`from_clones`, or
    :meth:`unavailable` rather than directly, so the invariants binding each
    outcome to its evidence hold by construction.
    """

    outcome: DuplicationOutcome
    files_analyzed: int = 0
    clone_count: int = 0
    duplicated_pct: str = ""
    groups: tuple[CloneGroup, ...] = ()
    raw_groups: tuple[CloneGroup, ...] = ()
    declaration_groups: tuple[CloneGroup, ...] = ()
    reason: str = ""

    @classmethod
    def observed_zero(cls, files_analyzed: int) -> DuplicationResult:
        """A successful scan that inspected ``files_analyzed`` files and saw no clones."""
        if files_analyzed <= 0:
            msg = "observed_zero requires a scan that demonstrably inspected files"
            raise ValueError(msg)
        return cls(outcome=DuplicationOutcome.OBSERVED_ZERO, files_analyzed=files_analyzed)

    @classmethod
    def from_clones(
        cls,
        *,
        files_analyzed: int,
        clone_count: int,
        duplicated_pct: str,
        groups: tuple[CloneGroup, ...],
    ) -> DuplicationResult:
        """A successful scan that found ``clone_count`` clones."""
        if clone_count <= 0:
            msg = "from_clones requires a positive clone count"
            raise ValueError(msg)
        return cls(
            outcome=DuplicationOutcome.CLONES,
            files_analyzed=files_analyzed,
            clone_count=clone_count,
            duplicated_pct=duplicated_pct,
            groups=groups,
            raw_groups=groups,
        )

    @classmethod
    def unavailable(cls, reason: str) -> DuplicationResult:
        """No duplication signal this cycle; ``reason`` says why."""
        return cls(outcome=DuplicationOutcome.UNAVAILABLE, reason=reason)

    @property
    def is_green(self) -> bool:
        """Whether this result honestly earns a GREEN verdict.

        Only a scan that looked at the tree and found nothing qualifies. An
        unavailable scan is not green, and clones are advisory AMBER.
        """
        return self.outcome is DuplicationOutcome.OBSERVED_ZERO

    def headline(self) -> str:
        """One-line human summary of the outcome."""
        if self.outcome is DuplicationOutcome.UNAVAILABLE:
            return f"duplication signal unavailable this cycle: {self.reason}"
        if self.outcome is DuplicationOutcome.OBSERVED_ZERO:
            return f"no clones found across {self.files_analyzed} analysed file(s)"
        pct_clause = f", {self.duplicated_pct}% duplicated lines" if self.duplicated_pct else ""
        return (
            f"{self.clone_count} clone cluster(s){pct_clause} "
            f"across {self.files_analyzed} analysed file(s) (advisory); "
            f"{len(self.groups)} executable or unclassified, {len(self.declaration_groups)} declaration-only"
        )


def jscpd_command(npx: str, source_root: Path = _PRODUCT_SOURCE_ROOT) -> list[str]:
    r"""Build the one jscpd command line.

    ``source_root`` is passed via :meth:`~pathlib.PurePath.as_posix` so it
    renders ``src/cadrumo`` on every OS. A Windows-native ``src\cadrumo``
    matches no files inside jscpd's glob engine, and jscpd then exits 0 having
    silently scanned nothing -- the false-green this module exists to prevent.
    """
    return [
        npx,
        "--yes",
        _JSCPD_SPEC,
        source_root.as_posix(),
        "--format",
        "python",
        "--min-lines",
        "6",
        "--min-tokens",
        "80",
        "--max-size",
        "250kb",
        "--ignore",
        _JSCPD_IGNORE,
        "--gitignore",
        "--reporters",
        "console",
        "--noTips",
    ]


def _parse_total_row(lines: list[str]) -> tuple[int, str] | None:
    """Extract ``(files_analyzed, duplicated_pct)`` from the summary table's Total row.

    Returns ``None`` when the table is absent, which is jscpd's signature for a
    run that matched no files at all.
    """
    for line in lines:
        if _TABLE_VERTICAL not in line:
            continue
        cells = [cell.strip() for cell in line.split(_TABLE_VERTICAL)]
        if len(cells) < _MIN_TABLE_CELLS or cells[1] != _TABLE_TOTAL_LABEL:
            continue
        try:
            files_analyzed = int(cells[_CELL_FILES_ANALYZED])
        except ValueError:
            return None
        pct_match = _TABLE_PCT.search(cells[_CELL_DUPLICATED_LINES])
        duplicated_pct = ""
        if pct_match is not None:
            captured = pct_match.group(1)
            if isinstance(captured, str):
                duplicated_pct = captured
        return files_analyzed, duplicated_pct
    return None


def _parse_clone_groups(lines: list[str]) -> tuple[CloneGroup, ...]:
    """Collect the ``Clone found`` blocks, normalising Windows paths to POSIX."""
    blocks: list[CloneGroup] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("Clone found"):
            if current:
                blocks.append(CloneGroup(tuple(current)))
            current = [line]
            continue
        if not current:
            continue
        if line.strip():
            current.append(line.replace("\\", "/").rstrip())
        else:
            blocks.append(CloneGroup(tuple(current)))
            current = []
    if current:
        blocks.append(CloneGroup(tuple(current)))
    return tuple(blocks)


def classify_jscpd_output(raw_stdout: str) -> DuplicationResult:
    """Classify jscpd's stdout into the typed three-state result.

    A run is only trusted when it carries BOTH a parseable ``Found N clones``
    line and a summary table proving files were analysed. Anything else is
    :attr:`DuplicationOutcome.UNAVAILABLE` -- never a zero.
    """
    lines = _ANSI.sub("", raw_stdout).splitlines()

    found = None
    for line in lines:
        match = _FOUND.search(line)
        if match:
            found = int(match.group(1))
    total_row = _parse_total_row(lines)

    if found is None or total_row is None:
        return DuplicationResult.unavailable(
            "jscpd produced no parseable summary (it reported no clone total or no analysed-file table, "
            "which is also how it renders a run that matched zero files)",
        )

    files_analyzed, duplicated_pct = total_row
    if files_analyzed <= 0:
        return DuplicationResult.unavailable(
            "jscpd analysed 0 files, so the scan proves nothing about duplication",
        )
    if found <= 0:
        return DuplicationResult.observed_zero(files_analyzed)
    return DuplicationResult.from_clones(
        files_analyzed=files_analyzed,
        clone_count=found,
        duplicated_pct=duplicated_pct,
        groups=_parse_clone_groups(lines),
    )


def _source_span(source: str, node: ast.stmt) -> tuple[tuple[int, int], tuple[int, int]]:
    """Translate AST UTF-8 byte columns into tokenizer character columns."""
    rows = source.splitlines()

    def position(line: int, column: int) -> tuple[int, int]:
        return line, len(rows[line - 1].encode(_UTF_8)[:column].decode(_UTF_8))

    if node.end_lineno is None or node.end_col_offset is None:
        raise ValueError("Parsed statement has no source extent")
    return position(node.lineno, node.col_offset), position(node.end_lineno, node.end_col_offset)


def _site_span(site: tuple[str, int, int, int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    _, start, start_column, end, end_column = site
    return (start, start_column - 1), (end, end_column)


def _intersects(left: tuple[tuple[int, int], tuple[int, int]], right: tuple[tuple[int, int], tuple[int, int]]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _span_is_import_preamble(repo_root: Path, site: tuple[str, int, int, int, int]) -> bool:
    path = site[0]
    try:
        source = (repo_root / path).read_text(encoding=_UTF_8)
        tree = ast.parse(source, filename=path)
    except (OSError, UnicodeError, SyntaxError):
        return False
    span = _site_span(site)
    statements = [node for node in tree.body if _intersects(_source_span(source, node), span)]
    return bool(statements) and all(isinstance(node, ast.Import | ast.ImportFrom) for node in statements)


def _span_contains(left: tuple[str, int, int, int, int], right: tuple[str, int, int, int, int]) -> bool:
    return (
        left[0] == right[0]
        and _site_span(left)[0] <= _site_span(right)[0]
        and _site_span(right)[1] <= _site_span(left)[1]
    )


def _span_is_declaration(repo_root: Path, site: tuple[str, int, int, int, int]) -> bool:
    """Prove every cloned token is inert, retaining unknown and executable spans."""
    path = site[0]
    try:
        source = (repo_root / path).read_text(encoding=_UTF_8)
        tree = ast.parse(source, filename=path)
    except (OSError, UnicodeError, SyntaxError):
        return False
    declared: list[tuple[tuple[int, int], tuple[int, int]]] = []
    executable: list[tuple[tuple[int, int], tuple[int, int]]] = []

    def imported_names(module: str, name: str) -> set[str]:
        aliases = {
            alias.asname or alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == module and not node.level
            for alias in node.names
            if alias.name == name
        }
        rebound = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
        rebound.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        )
        rebound.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
        rebound.update(
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
            if not (
                isinstance(node, ast.ImportFrom) and node.module == module and alias.name == name and not node.level
            )
        )
        return aliases - rebound

    type_checking = imported_names("typing", "TYPE_CHECKING")
    fields = imported_names("pydantic", "Field")
    protocols = imported_names("typing", "Protocol") | imported_names("typing_extensions", "Protocol")

    def inert(value: ast.AST | None) -> bool:
        if value is None or isinstance(value, ast.Constant | ast.Name):
            return True
        if isinstance(value, ast.Tuple | ast.List | ast.Set):
            return all(inert(item) for item in value.elts)
        if isinstance(value, ast.Dict):
            return all(
                key is not None and inert(key) and inert(item)
                for key, item in zip(value.keys, value.values, strict=True)
            )
        return (
            isinstance(value, ast.UnaryOp)
            and isinstance(value.op, ast.UAdd | ast.USub)
            and isinstance(value.operand, ast.Constant)
        )

    def docstring(node: ast.stmt) -> bool:
        return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)

    def has_call(nodes: Sequence[ast.AST]) -> bool:
        return any(isinstance(part, ast.Call) for node in nodes for part in ast.walk(node))

    def visit(body: list[ast.stmt], *, in_class: bool = False, protocol: bool = False) -> None:
        for index, node in enumerate(body):
            span = _source_span(source, node)
            if isinstance(node, ast.Import | ast.ImportFrom) or (index == 0 and docstring(node)):
                declared.append(span)
            elif isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id in type_checking:
                declared.append((span[0], _source_span(source, node.body[-1])[1]))
                visit(node.orelse, in_class=in_class, protocol=protocol)
            elif isinstance(node, ast.ClassDef):
                header = (span[0], _source_span(source, node.body[0])[0])
                declared.append(header)
                if has_call(node.bases + node.decorator_list + [keyword.value for keyword in node.keywords]):
                    executable.append(header)
                is_protocol = any(isinstance(base, ast.Name) and base.id in protocols for base in node.bases)
                visit(node.body, in_class=True, protocol=is_protocol)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                header = (span[0], _source_span(source, node.body[0])[0])
                declared.append(header)
                defaults = node.args.defaults + [value for value in node.args.kw_defaults if value is not None]
                annotations = [
                    arg.annotation
                    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                    if arg.annotation is not None
                ]
                for variadic in (node.args.vararg, node.args.kwarg):
                    if variadic is not None and variadic.annotation is not None:
                        annotations.append(variadic.annotation)
                if node.returns is not None:
                    annotations.append(node.returns)
                if has_call(defaults + node.decorator_list + annotations):
                    executable.append(header)
                arguments = {arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
                if node.args.vararg is not None:
                    arguments.add(node.args.vararg.arg)
                if node.args.kwarg is not None:
                    arguments.add(node.args.kwarg.arg)
                for number, stmt in enumerate(node.body):
                    stub = protocol and (
                        isinstance(stmt, ast.Pass)
                        or (
                            isinstance(stmt, ast.Expr)
                            and isinstance(stmt.value, ast.Constant)
                            and stmt.value.value is Ellipsis
                        )
                        or (
                            isinstance(stmt, ast.Delete)
                            and all(isinstance(target, ast.Name) and target.id in arguments for target in stmt.targets)
                        )
                    )
                    (declared if stub or (number == 0 and docstring(stmt)) else executable).append(
                        _source_span(source, stmt)
                    )
            elif isinstance(node, ast.AnnAssign | ast.Assign):
                value = node.value
                targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
                safe = all(isinstance(target, ast.Name) for target in targets) and inert(value)
                if in_class and isinstance(node, ast.AnnAssign) and isinstance(value, ast.Call):
                    safe = (
                        isinstance(value.func, ast.Name)
                        and value.func.id in fields
                        and not value.args
                        and all(
                            item.arg not in {None, "default_factory"} and inert(item.value) for item in value.keywords
                        )
                    )
                if isinstance(node, ast.AnnAssign) and has_call([node.annotation]):
                    safe = False
                (declared if safe else executable).append(span)
            else:
                executable.append(span)

    visit(tree.body)
    span = _site_span(site)
    try:
        relevant = [
            (token.start, token.end)
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type
            not in {
                tokenize.ENCODING,
                tokenize.COMMENT,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENDMARKER,
            }
            and _intersects((token.start, token.end), span)
        ]
    except (tokenize.TokenError, IndentationError):
        return False
    return bool(relevant) and all(
        any(interval[0] <= token[0] and token[1] <= interval[1] for interval in declared)
        and not any(_intersects(token, interval) for interval in executable)
        for token in relevant
    )


def classify_clone_spans(result: DuplicationResult, repo_root: Path) -> DuplicationResult:
    """Retain raw measurements while separating proven declarations from review leads."""
    if result.outcome is not DuplicationOutcome.CLONES:
        return result
    groups = actionable_clone_groups(result.raw_groups, repo_root)
    declarations = tuple(
        group
        for group in groups
        if len(group.sites()) >= 2 and all(_span_is_declaration(repo_root, site) for site in group.sites())
    )
    return replace(
        result, groups=tuple(group for group in groups if group not in declarations), declaration_groups=declarations
    )


def actionable_clone_groups(groups: tuple[CloneGroup, ...], repo_root: Path) -> tuple[CloneGroup, ...]:
    """Remove structural noise and duplicate reports without hiding executable clones."""
    retained: list[CloneGroup] = []
    retained_sites: list[tuple[tuple[str, int, int, int, int], ...]] = []
    for group in groups:
        sites = group.sites()
        if len(sites) >= 2 and all(_span_is_import_preamble(repo_root, site) for site in sites):
            continue
        if len(sites) == 2 and any(
            len(previous) == 2 and _span_contains(previous[0], sites[0]) and _span_contains(previous[1], sites[1])
            for previous in retained_sites
        ):
            continue
        retained.append(group)
        retained_sites.append(sites)
    return tuple(retained)


def run_duplication_scan(
    repo_root: Path,
    *,
    source_root: Path = _PRODUCT_SOURCE_ROOT,
    timeout: float = _JSCPD_TIMEOUT_SECONDS,
    which: Callable[[str], str | None] = shutil.which,
) -> DuplicationResult:
    """Run jscpd over ``source_root`` and classify the outcome.

    This is the single entry point for every duplication consumer. ``npx`` is
    resolved through ``which`` -- :func:`shutil.which` in production -- because
    on Windows the real executable is a ``.cmd`` shim that ``CreateProcess``
    cannot launch by bare name (the same idiom as ``dev/docs/build.py``). The
    resolver is an injected seam (the prompt_toolkit ``input=``/``output=``
    contract, not a patch): a caller may supply a real resolver that returns
    ``None`` to exercise the missing-executable path, or one pointing at a
    different real executable to exercise the non-zero-exit path, without
    mutating global process state.
    """
    npx = which("npx")
    if npx is None:
        return DuplicationResult.unavailable("npx was not found on PATH")

    try:
        completed = run_command(
            jscpd_command(npx, source_root),
            errors="replace",
            cwd=repo_root,
            timeout_seconds=timeout,
        )
    except subprocess.TimeoutExpired:
        return DuplicationResult.unavailable(f"jscpd exceeded its {timeout:g}s timeout")
    except OSError as exc:
        return DuplicationResult.unavailable(f"jscpd could not be launched ({exc})")

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "no diagnostic output"
        return DuplicationResult.unavailable(f"jscpd exited {completed.returncode}: {tail}")

    result = classify_jscpd_output(completed.stdout)
    if result.outcome is not DuplicationOutcome.CLONES:
        return result
    return classify_clone_spans(result, repo_root)


def render_console_report(result: DuplicationResult) -> str:
    """Render the operator-facing console report for ``python -m dev.audit.duplication``."""
    if result.outcome is DuplicationOutcome.UNAVAILABLE:
        return f"duplication: {result.headline()}"
    if result.outcome is DuplicationOutcome.OBSERVED_ZERO:
        return f"duplication: {result.headline()}."

    out = [f"duplication: {result.headline()}."]
    omitted = len(result.raw_groups) - len(result.groups) - len(result.declaration_groups)
    missing = max(0, result.clone_count - len(result.raw_groups))
    out.append(
        f"Raw evidence: {omitted} import-only or overlapping reports; {missing} reports without parsed locations."
    )
    for group in result.groups[:_CLONE_CAP]:
        out.append("")
        out.append(group.render())
    if len(result.groups) > _CLONE_CAP:
        out.append(f"\n... {len(result.groups) - _CLONE_CAP} more clones")
    for group in result.declaration_groups:
        out.extend(("", "Declaration-only token overlap:", group.render()))
    return "\n".join(out)


def main() -> int:
    """Run the duplication scan and print the reduced console report.

    Findings are advisory and return 0. An unavailable scan returns the shared
    advisory-broken status so it cannot pose as a clean run.
    """
    repo_root = REPO_ROOT
    result = run_duplication_scan(repo_root)
    print(render_console_report(result))
    return ADVISORY_BROKEN if result.outcome is DuplicationOutcome.UNAVAILABLE else OK


if __name__ == "__main__":
    sys.exit(main())
