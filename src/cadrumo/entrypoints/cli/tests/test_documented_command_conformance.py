"""Argument-level conformance gate for documented ``aeat`` commands.

``aeat`` is the sole human CLI executable (the ``cadrumo`` package ships it as
its one console entry point per ``aeat-naming``); every
documented CLI invocation therefore begins with the ``aeat`` token, and this
gate anchors on it. The package name ``cadrumo``, ``cadrumo-vault/`` storage,
and ``src/cadrumo/`` paths are product
and package references, never ``aeat``-CLI invocations, so they are outside
this gate's scope — treating them as CLI lines would only manufacture false
positives from prose. (This anchor was previously swept to the bare
``cadrumo`` token by the package rename, which made the gate near-vacuous: the
docs cite ``aeat`` and almost nothing matched.)

The sibling :mod:`test_educational_docs_conformance` gate binds only the
*leading verb path* of a cited ``aeat ...`` invocation: it checks that the
longest verb prefix accepts ``--help``. That left a blind spot — a doc could
cite a real command with a *wrong option name* or the *wrong argument shape*
and the verb-only gate stayed green. Two such defects shipped and were caught
only because a human ran the commands by hand:

- ``aeat app modelo describe --modelo 130`` — ``--modelo`` is not an option of
  ``describe`` (the modelo is a positional argument); the real form is
  ``aeat app modelo describe 130``; and
- ``aeat config profile create`` — missing the required ``PROFILE_NAME``
  positional.

This gate closes that blind spot. It walks the *live* Typer/click command tree
**in process** (no shell-out, no ``uv``) and, for every ``aeat ...`` invocation
cited in a user-facing doc or its keyed private sequence contract, asserts:

- **(a) Command-path resolution.** The leading verb tokens resolve to a real
  command in the tree.
- **(b) Option validity.** Every cited long/short option (``--foo`` / ``-f``)
  is a real parameter of the resolved command — or a global option declared on
  the root callback (``--language`` / ``--format`` / ``--profile`` / etc.).
  Option *names* are validated, never their values: a token after ``=`` or one
  consumed as an option value is treated as a value, and angle / UPPER / dotted
  placeholders (``<id>``, ``NAME``, ``<work-unit-id>``, ``./path``) are treated
  as positional placeholders, not flags. This is the high-signal check that
  catches the ``--modelo`` class of defect.

Scope is *all* user-facing docs — the flat ``docs/*.md`` pages and the root
``README.md`` that the educational-surface gate never covered, plus the
Diataxis trees the sibling gate already binds — and every private
``docs/_sequences/contracts/**/*.seq`` execution contract. The private
contracts are authoritative for command execution metadata, while Markdown
remains reader-facing.

**Limitation: missing-required-positional is deliberately NOT enforced.**
The original ``profile create`` defect (a required ``PROFILE_NAME`` positional
shown with no placeholder) is one shape of error, but reliable detection of it
across this doc surface produces systematic false positives and is therefore
out of scope. The dominant doc idiom is to cite a leaf command *by its bare
verb* for narrative reference: a heading or sentence naming
``aeat app modelo export`` to introduce the command, with the full
placeholder-bearing form (``aeat app modelo export <work_unit_id> --output
<path>``) shown separately in an adjacent example. A naive
"required-positional-with-no-token" rule cannot tell a legitimate bare-verb
*reference* apart from an invocation that genuinely *omits* a required argument:
both show the verb with no following token. Flagging the reference form would
red the gate on correct docs (a survey of the current surface produced ~15 such
false positives across the educational trees alone). The high-signal,
zero-false-positive check is option validity (b): a cited ``--foo`` that is not
a real parameter is unambiguously wrong regardless of narrative context, which
is exactly the ``--modelo`` class the verb-only sibling gate missed. The
``profile create`` defect is independently covered because the corrected doc now
shows the placeholder (``aeat config profile create <name>``), and the
verb-resolution check (a) here plus the sibling verb-only gate keep the verb
path honest. The live ``required``/``nargs`` parameter shape is still
introspected and asserted in
:func:`test_live_introspection_matches_reality` so the introspection machinery
cannot silently rot.

Real-behavior only: the gate imports the real Cadrumo app object and walks the
materialized click command tree (which triggers the lazy-subcommand loaders).
No test doubles. It fails loudly on an invalid documented command and passes
when the docs are correct.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import cast

import click
import pytest

from ....core import scan_directory
from ....tests import REPO_ROOT
from ....tests.cli_runner import cadrumo_click_command

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# All user-facing doc surfaces. The flat ``docs/*.md`` pages and the root
# ``README.md`` are the surfaces the verb-only conformance gate never covered.
_FLAT_DOC_GLOBS = ("docs/*.md",)
_TREE_DOC_DIRS = (
    "docs/explanation",
    "docs/how-to",
    "docs/reference",
    "docs/verification",
    "docs/architecture",
)

# Inline backticks and fenced blocks are the only authoritative command
# surfaces; a bare ``aeat ...`` in prose is not a cited invocation.
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

# A line is an ``aeat`` invocation when the ``aeat`` executable token appears as
# a bare token (start of line or after shell punctuation), not as a substring
# (``aeat-config``) — ``aeat`` is the one human CLI executable the docs cite.
_AEAT_TOKEN_RE = re.compile(r"(?:^|[\s$|&(;])aeat(?=\s|$)")

# cli-sequence directives whose payload is FREE PROSE, not an invocation. A
# reason sentence may legitimately name the product ("No aeat verb creates an
# evidence bundle"), and without this the sentence after that word is parsed as
# a verb path and reported as a command that does not resolve.
_PROSE_DIRECTIVE_RE = re.compile(r"^@(?:blocked|capture|expect|note)\b")

# Global options declared on the root callback. Accepted at any position before
# the subcommand path and validated against the root command's own params, so
# this set is a documentation aid only — the authoritative source is the live
# root command (see :func:`_root_option_names`).
_LINE_CONTINUATION_RE = re.compile(r"\\\s*$")


def _flat_docs() -> list[Path]:
    docs: list[Path] = []
    for pat in _FLAT_DOC_GLOBS:
        docs.extend(sorted(REPO_ROOT.glob(pat)))
    for d in _TREE_DOC_DIRS:
        docs.extend(scan_directory(REPO_ROOT / d, pattern="*.md", recursive=True))
    readme = REPO_ROOT / "README.md"
    if readme.is_file():
        docs.append(readme)
    return docs


def _sequence_contracts() -> tuple[Path, ...]:
    """Return every private CLI sequence contract in stable path order."""
    return scan_directory(REPO_ROOT / "docs" / "_sequences" / "contracts", pattern="*.seq", recursive=True)


def _command_surfaces() -> list[Path]:
    """Return reader docs plus their private executable contracts."""
    return [*_flat_docs(), *_sequence_contracts()]


# ---------------------------------------------------------------------------
# Live CLI introspection
# ---------------------------------------------------------------------------


@cache
def _root_command() -> click.Command:
    """Materialize the live ``cadrumo`` click command (root of the tree)."""
    return cadrumo_click_command()


@cache
def _root_option_names() -> frozenset[str]:
    """Long/short option strings declared on the root callback."""
    names: set[str] = set()
    for param in _root_command().params:
        if getattr(param, "param_type_name", None) == "option":
            names.update(param.opts)
            names.update(param.secondary_opts)
    return frozenset(names)


@dataclass(frozen=True)
class _Resolved:
    """Resolution outcome for a cited verb path."""

    command: click.Command | None
    # The verb path that resolved (may be a prefix of the cited tokens when
    # trailing tokens are arguments rather than subcommands).
    resolved_path: tuple[str, ...]


def _resolve_path(tokens: tuple[str, ...]) -> _Resolved:
    """Walk the live tree for the longest verb prefix of ``tokens``.

    Returns the deepest command reachable by treating leading tokens as
    subcommand names. Resolution stops at the first token that is not a
    subcommand of the current group (that token and the rest are arguments).
    """
    cmd: click.Command = _root_command()
    ctx = click.Context(cmd, info_name="aeat")
    resolved: list[str] = []
    for tok in tokens:
        if not hasattr(cmd, "list_commands"):
            break
        # ``list_commands`` is the structural group marker; the vendored
        # TyperGroup is not a guaranteed upstream ``click.Group`` subclass, so
        # narrow by interface (cast) rather than isinstance to stay
        # vendor-robust while exposing ``get_command`` to the checker.
        group = cast(click.Group, cmd)
        sub = group.get_command(ctx, tok)
        if sub is None:
            break
        ctx = click.Context(sub, info_name=tok, parent=ctx)
        cmd = sub
        resolved.append(tok)
    return _Resolved(command=cmd, resolved_path=tuple(resolved))


def _command_option_names(cmd: click.Command) -> frozenset[str]:
    names: set[str] = set()
    for param in cmd.params:
        if getattr(param, "param_type_name", None) == "option":
            names.update(param.opts)
            names.update(param.secondary_opts)
    return frozenset(names)


def _value_consuming_option_names(cmd: click.Command) -> frozenset[str]:
    """Option strings on ``cmd`` that consume a following value token.

    A boolean flag (``--force`` / ``--no-force``) or a counting option
    (``-v -v``) takes no value; every other option consumes the next token as
    its value. Knowing this set for the *resolved* command lets the
    dead-subcommand check tell an option value (``--layout plugin``) apart from
    a subcommand name — the root-global heuristic in the string parser cannot,
    because it runs before the command is known.
    """
    names: set[str] = set()
    for param in cmd.params:
        if getattr(param, "param_type_name", None) != "option":
            continue
        if getattr(param, "is_flag", False) or getattr(param, "count", False):
            continue
        names.update(param.opts)
        names.update(param.secondary_opts)
    return frozenset(names)


def _option_value_tokens(tokens: tuple[str, ...], value_consuming: frozenset[str]) -> set[str]:
    """Tokens in ``tokens`` consumed as the value of a value-consuming option.

    Walks the ordered stream and, for each cited value-consuming option written
    without an inline ``=value``, marks the next token as its value. Used to
    exclude an option value from the dead-subcommand check.
    """
    consumed: set[str] = set()
    expect_value = False
    for tok in tokens:
        if expect_value:
            consumed.add(tok)
            expect_value = False
            continue
        if tok.startswith("-") and tok != "-":
            name = tok.split("=", 1)[0]
            if "=" not in tok and name in value_consuming:
                expect_value = True
    return consumed


def _required_positional_count(cmd: click.Command) -> int:
    """Number of required, non-variadic positional arguments on ``cmd``."""
    count = 0
    for param in cmd.params:
        if getattr(param, "param_type_name", None) == "argument" and param.required and param.nargs != -1:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Command-line extraction
# ---------------------------------------------------------------------------

# A token that is a placeholder rather than a concrete value or a flag:
# ``<id>``, ``<work-unit-id>``, ``NAME``, ``MODELO``, ``<YYYY>``. These fill a
# positional slot and are never validated as option names.
_PLACEHOLDER_RE = re.compile(r"^(<[^>]+>|[A-Z][A-Z0-9_-]*)$")

# A ``{name}`` interpolation token — the cli-sequence directive's placeholder
# class: a value captured at build time from a prior
# frame's envelope and threaded into a later frame's command line. It fills a
# positional slot exactly like ``<id>`` and is never validated as an option
# name. The inner name matches the engine's capture-identifier grammar.
_INTERP_PLACEHOLDER_RE = re.compile(r"^\{[A-Za-z_][A-Za-z0-9_]*\}$")


@dataclass(frozen=True)
class _CitedCommand:
    """A single cited ``aeat`` invocation, decomposed for validation."""

    raw: str
    verb_tokens: tuple[str, ...]
    cited_options: tuple[str, ...]
    # True when at least one non-flag token follows the verb path (a value or
    # a placeholder) — used to evaluate the missing-required-positional check.
    has_positional_token: bool
    # The full ordered token stream after the executable token (verb tokens,
    # options, option values, positionals), preserved so the dead-subcommand
    # check can consult the resolved command's value-consuming options and tell
    # an option *value* apart from a subcommand. Defaults to empty for the
    # directly-constructed fixtures in the tests, which exercise the option-name
    # and verb-resolution paths that do not need the ordered stream.
    tokens: tuple[str, ...] = ()


def _strip_inline_comment(line: str) -> str:
    """Drop a trailing ``# ...`` shell comment outside any quotes."""
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
    return line


def _is_value_placeholder(tok: str) -> bool:
    """A token that occupies a positional slot but is not a real flag.

    Covers angle/UPPER placeholders (``<id>``, ``NAME``) plus concrete value
    tokens a doc may show (``./path``, ``130``, ``2024-01``, ``KEY=VALUE``).
    Anything that does not start with ``-`` is positional.
    """
    return not tok.startswith("-")


def _parse_command_line(line: str) -> _CitedCommand | None:
    """Decompose one ``aeat ...`` line into verb path + cited options.

    Returns ``None`` for lines that are not concretely-resolvable invocations:
    the bare ``aeat`` token, an ``aeat ...`` ellipsis reference, the machine-format
    ``aeat 1.2.3`` version echo, or a line whose only verb is a top-level flag
    (``aeat --version``).
    """
    cleaned = _strip_inline_comment(line).strip()
    cleaned = _LINE_CONTINUATION_RE.sub("", cleaned).strip()
    # Prose-carrying cli-sequence directives are skipped EXPLICITLY rather than
    # incidentally. ``@capture`` and ``@expect`` were skipped only because their
    # syntax happens to exclude the ``aeat`` token, which made the whole scheme
    # depend on documentation prose never using the product name -- and
    # ``@blocked`` broke it: a reason reading "No aeat verb creates an evidence
    # bundle" was parsed as a citation, and the remainder of the sentence was
    # resolved as a verb path. Naming the prose directives states the rule
    # instead of relying on a coincidence of vocabulary.
    if _PROSE_DIRECTIVE_RE.match(cleaned):
        return None
    # Some doc lines prefix the command with a shell sigil or a tab-led label.
    # A cli-sequence frame's ``@setup`` / ``@result`` sigil precedes the ``aeat``
    # token and is dropped here by anchoring on ``aeat``, so a frame line
    # validates like any other cited invocation.
    m = _AEAT_TOKEN_RE.search(cleaned)
    if m is None:
        return None
    after = cleaned[m.end() :].strip()
    if not after:
        return None  # bare ``aeat``
    try:
        tokens = _shlex_split(after)
    except ValueError:
        return None
    if not tokens:
        return None
    # An ellipsis placeholder (``aeat app ...``) is a narrative reference, not a
    # concrete invocation; the trailing ``...`` is the tell.
    if any(t == "..." for t in tokens):
        return None
    # The machine-format version echo ``aeat 1.2.3`` / ``aeat 0.1.0`` is output,
    # not an invocation: a single token that is a dotted version literal.
    if len(tokens) == 1 and re.fullmatch(r"\d+\.\d+\.\d+", tokens[0]):
        return None

    verb_tokens: list[str] = []
    cited_options: list[str] = []
    has_positional = False
    # Track which root-global options consume a following value (so the value
    # is not mistaken for the start of the verb path).
    value_consuming_globals = {"--language", "--lang", "--format", "--profile"}
    expect_value = False
    seen_verb = False
    for tok in tokens:
        if expect_value:
            expect_value = False
            continue
        if tok.startswith("-") and tok != "-":
            # Split ``--opt=value`` to the option name.
            name = tok.split("=", 1)[0]
            cited_options.append(name)
            if "=" not in tok and name in value_consuming_globals:
                expect_value = True
            continue
        # A non-flag token. Before the verb path is established it may be a
        # version literal already handled above; otherwise it is either a verb
        # token (lowercase subcommand-ish) or a positional argument/placeholder.
        if not seen_verb:
            verb_tokens.append(tok)
            seen_verb = True
        elif _INTERP_PLACEHOLDER_RE.match(tok):
            # A ``{name}`` interpolation is always a positional placeholder, never
            # a subcommand — a cli-sequence threaded capture.
            has_positional = True
        else:
            # Decide: is this still a verb token or a positional? Lowercase
            # hyphenated words *may* be subcommands; resolution settles it. We
            # over-collect into verb_tokens and let resolution split the path.
            if re.fullmatch(r"[a-z0-9][a-z0-9-]*", tok):
                verb_tokens.append(tok)
            else:
                has_positional = True
    if not verb_tokens:
        return None  # only top-level flags (``aeat --version``)
    return _CitedCommand(
        raw=line.strip(),
        verb_tokens=tuple(verb_tokens),
        cited_options=tuple(cited_options),
        has_positional_token=has_positional,
        tokens=tuple(tokens),
    )


def _shlex_split(text: str) -> list[str]:
    """Whitespace-aware split that keeps quoted spans intact.

    A light shlex: respects single/double quotes so ``--notes "a b"`` is one
    value token, without importing the full POSIX shlex (which chokes on the
    angle-bracket placeholders the docs use).
    """
    tokens: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    for ch in text:
        if quote is not None:
            if ch == quote:
                quote = None
            else:
                buf.append(ch)
        elif ch in ("'", '"'):
            quote = ch
        elif ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def _cited_commands(text: str) -> list[_CitedCommand]:
    spans = [m.group(1) for m in _INLINE_CODE_RE.finditer(text)]
    spans += [m.group(1) for m in _FENCE_RE.finditer(text)]
    out: list[_CitedCommand] = []
    seen: set[tuple[tuple[str, ...], tuple[str, ...], bool]] = set()
    for span in spans:
        # Join shell line continuations within a fenced block before splitting.
        joined = span.replace("\\\n", " ")
        for line in joined.splitlines():
            if _AEAT_TOKEN_RE.search(line) is None:
                continue
            parsed = _parse_command_line(line)
            if parsed is None:
                continue
            key = (parsed.verb_tokens, parsed.cited_options, parsed.has_positional_token)
            if key in seen:
                continue
            seen.add(key)
            out.append(parsed)
    return out


def _surface_commands(path: Path) -> list[_CitedCommand]:
    """Extract invocations from one reader doc or private sequence contract."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".seq":
        return _cited_commands(f"```\n{text}\n```")
    return _cited_commands(text)


# ---------------------------------------------------------------------------
# Enrollment detection
# ---------------------------------------------------------------------------

# A backtick-fenced ``cli-sequence`` directive: ```` ```{cli-sequence} <id> ````.
# The info string is the fence's first line after the opening backticks; a page
# carrying at least one such fence is *enrolled* — it hosts at least one executed,
# golden-backed sequence. Enrollment is NOT exclusionary: an enrolled page may
# ALSO carry ordinary executable ``aeat`` fences, and those fences receive the
# same base verb-path and option-name checks every fence gets (the executed vs.
# static distinction is visual and golden-backed, not a refusal (the amended
# documented-command decision). ``_FENCE_WITH_INFO_RE`` captures the info string
# alongside the body.
_CLI_SEQUENCE_INFO_RE = re.compile(r"^\{cli-sequence\}")
_FENCE_WITH_INFO_RE = re.compile(r"```([^\n]*)\n(.*?)```", re.DOTALL)


def _page_is_enrolled(text: str) -> bool:
    """A page is enrolled when it carries at least one ``{cli-sequence}`` directive."""
    return any(_CLI_SEQUENCE_INFO_RE.match(info.strip()) for info, _ in _FENCE_WITH_INFO_RE.findall(text))


# ---------------------------------------------------------------------------
# Mandatory-display gate (ratcheting): no plain ``aeat`` fences in user docs
# ---------------------------------------------------------------------------

# Operator doctrine (2026-07-14): every ``aeat`` CLI command shown in user docs
# MUST render through the implemented cli-sequence display (a step header +
# tokenised command card + output), not a plain ```` ```bash ```` fence — a
# plain fence carrying an ``aeat`` invocation is remediated by converting it to a
# ``{cli-sequence}`` executed directive (or an ``@static`` frame where hermetic
# execution is impossible: live AEAT, Google OAuth, interactive wizards,
# operator-machine-specific paths). Non-``aeat`` commands (pip, playwright,
# ollama, ``python -m``, ``/plugin``) stay allowed in plain fences.
#
# The gate ships with a checked-in per-page baseline of the current violations
# and only ratchets DOWN: a page may never exceed its baseline count (a new plain
# ``aeat`` fence reds the gate), and a page absent from the baseline may carry
# none. Converter agents burn the baseline down page by page; an empty baseline
# means the doctrine is fully applied. It does not red the tree on partial
# progress (a page below its baseline passes), so the conversion can proceed in
# parallel.
_USER_DOC_TREE_DIRS = ("how-to", "explanation", "reference")
_USER_DOC_FLAT_FILES = ("index.md", "workstation-setup.md", "updates.md", "disclaimer.md")

# Fence languages that denote a shell command block (where an ``aeat`` invocation
# is a rendered command, not sample data). A bare fence (no info string) counts.
_PLAIN_SHELL_FENCE_LANGS = frozenset({"bash", "sh", "pwsh", "shell", "console", "powershell", ""})

_AEAT_FENCE_BASELINE_PATH = REPO_ROOT / "src/cadrumo/entrypoints/cli/tests/aeat_plain_fence_baseline.json"


def _user_doc_pages() -> list[Path]:
    """Return the user-docs pages the mandatory-display gate governs."""
    docs = REPO_ROOT / "docs"
    pages: list[Path] = []
    for tree in _USER_DOC_TREE_DIRS:
        pages.extend(scan_directory(docs / tree, pattern="*.md", recursive=True))
    for flat in _USER_DOC_FLAT_FILES:
        page = docs / flat
        if page.is_file():
            pages.append(page)
    return pages


def _aeat_plain_fences(text: str) -> list[int]:
    """Return the 1-based line numbers of plain shell fences that carry an ``aeat`` invocation.

    A ``{cli-sequence}`` directive fence is the sanctioned executed surface and is
    exempt; a non-shell fence (python, toml, json) is data, not a command block.
    A plain shell fence counts once when its body carries at least one concrete
    ``aeat`` invocation line (``_parse_command_line`` resolves it — bare ``aeat``,
    ellipsis references, and the version echo do not count).
    """
    offending: list[int] = []
    for match in _FENCE_WITH_INFO_RE.finditer(text):
        info = match.group(1).strip()
        lang = info.split()[0] if info else ""
        if lang.startswith("{"):
            continue  # a directive fence — the executed surface
        if lang and lang not in _PLAIN_SHELL_FENCE_LANGS:
            continue  # a non-shell code/data fence
        body = match.group(2)
        if any(_AEAT_TOKEN_RE.search(line) and _parse_command_line(line) is not None for line in body.splitlines()):
            offending.append(text[: match.start()].count("\n") + 1)
    return offending


def _current_aeat_fence_counts() -> dict[str, int]:
    """Return the live per-page count of plain ``aeat`` fences, keyed by docs-relative path."""
    docs = REPO_ROOT / "docs"
    counts: dict[str, int] = {}
    for page in _user_doc_pages():
        fences = _aeat_plain_fences(page.read_text(encoding="utf-8"))
        if fences:
            counts[page.relative_to(docs).as_posix()] = len(fences)
    return counts


_INLINE_AEAT_SPAN_BASELINE_PATH = REPO_ROOT / "src/cadrumo/entrypoints/cli/tests/inline_aeat_span_baseline.json"


def _inline_command_complexity(span: str) -> int | None:
    """Return an inline ``aeat`` span's option/argument-token count, or ``None``.

    ``None`` when the span is not a concrete ``aeat`` invocation (a bare verb, an
    ellipsis reference, the version echo). Otherwise the count of option flags
    plus positional arguments beyond the resolved verb path; an option's value
    rides its option and is not counted separately, and leading global options
    are handled. So a bare verb reference (``aeat config login``) is 0, a
    single-flag or single-argument mention (``aeat app modelo describe 303``,
    ``aeat config auth configure --file``) is 1, and a real command
    (``aeat app modelo export --modelo 130 --output ./x.boe``) is 2 or more.
    """
    cited = _parse_command_line(span)
    if cited is None:
        return None
    resolved = _resolve_path(cited.verb_tokens)
    value_consuming = _value_consuming_option_names(_root_command())
    if resolved.command is not None:
        value_consuming = value_consuming | _value_consuming_option_names(resolved.command)
    verb_path = list(resolved.resolved_path)
    verb_index = 0
    count = 0
    expect_value = False
    for tok in cited.tokens:
        if expect_value:
            expect_value = False
            continue  # an option value, ridden by its option
        if tok.startswith("-") and tok != "-":
            count += 1
            name = tok.split("=", 1)[0]
            if "=" not in tok and name in value_consuming:
                expect_value = True
            continue
        if verb_index < len(verb_path) and tok == verb_path[verb_index]:
            verb_index += 1
            continue  # part of the verb path
        count += 1  # a positional argument
    return count


#: A markdown paragraph boundary — a blank (whitespace-only) line. An inline code
#: span cannot cross one (CommonMark inline content is block-scoped), so soft line
#: wraps are joined only WITHIN a paragraph, never across a paragraph break.
_PARAGRAPH_BOUNDARY_RE = re.compile(r"\n[ \t]*\n")

#: An opening/closing fenced-code line: an optionally-indented run of three or
#: more backticks or tildes. Matches a fence at ANY indentation (a cli-sequence
#: directive nested inside a list item is indented) and either fence character.
_FENCE_LINE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def _strip_fenced_blocks(text: str) -> str:
    """Return the text with every fenced block replaced by a paragraph break.

    A line-based stripper (not the ``.*?`` regex): it tracks the open fence's
    character and length, so a fenced block — code, CLI output, or a
    ``{cli-sequence}`` directive body — is excluded in FULL regardless of its
    indentation (a directive nested in a list item), its fence character
    (``` ``` ``` or ``~~~``), or a longer fence run (```` ```` ````). A block that is
    never closed drops to end of input rather than mis-pairing with a later
    fence (the ``.*?`` regex's failure mode), so a directive body can never leak
    a bare ``@result``/``@static`` command line into the inline-span scan. Each
    stripped block becomes a blank line, i.e. a paragraph boundary, so a soft-wrap
    join never bridges across it.
    """
    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    for line in text.split("\n"):
        match = _FENCE_LINE_RE.match(line)
        run = match.group(1) if match else ""
        if fence_char is None:
            if match:
                fence_char = run[0]
                fence_len = len(run)
                out.append("")
            else:
                out.append(line)
            continue
        # Inside a fence: a close is the same character, at least as long, and
        # carries no trailing info string. Everything else inside is dropped.
        if match and run[0] == fence_char and len(run) >= fence_len and line.strip()[len(run) :].strip() == "":
            fence_char = None
            out.append("")
        # else: still inside the fence — drop the line.
    return "\n".join(out)


def _inline_aeat_command_spans(text: str) -> list[str]:
    """Return inline code spans in prose that are ``aeat`` commands with 2+ option/arg tokens.

    Fenced blocks (code, CLI output, ``{cli-sequence}`` directive bodies) are
    stripped first via :func:`_strip_fenced_blocks` — a line-based strip that
    excludes a directive body in full regardless of indentation (nested in a list
    item), fence character, or fence length — so only reader-facing inline ``code``
    spans are scanned and a directive frame line never leaks in. Because markdown
    joins a code span wrapped across source lines into ONE rendered span — and
    ``_INLINE_CODE_RE`` deliberately does not match across a newline — each
    blank-line-delimited paragraph has its soft line wraps collapsed to spaces
    before span extraction, so a command dissolved into an inline span and then
    wrapped across two source lines is caught exactly as its single-line form is.
    The two-token threshold keeps bare verb references and single-flag/argument
    mentions legal while flagging a full command moved inline (the fence-ratchet
    loophole).
    """
    prose = _strip_fenced_blocks(text)
    offending: list[str] = []
    for paragraph in _PARAGRAPH_BOUNDARY_RE.split(prose):
        joined = " ".join(line.strip() for line in paragraph.split("\n"))
        for match in _INLINE_CODE_RE.finditer(joined):
            span = match.group(1)
            if _AEAT_TOKEN_RE.search(span) is None:
                continue
            complexity = _inline_command_complexity(span)
            if complexity is not None and complexity >= 2:
                offending.append(span.strip())
    return offending


def _current_inline_aeat_span_counts() -> dict[str, int]:
    """Return the live per-page count of complex inline ``aeat`` spans, keyed by docs-relative path."""
    docs = REPO_ROOT / "docs"
    counts: dict[str, int] = {}
    for page in _user_doc_pages():
        spans = _inline_aeat_command_spans(page.read_text(encoding="utf-8"))
        if spans:
            counts[page.relative_to(docs).as_posix()] = len(spans)
    return counts


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _split_verb_and_positionals(cited: _CitedCommand) -> tuple[_Resolved, tuple[str, ...]]:
    """Resolve the verb path, returning the leftover (positional) verb tokens."""
    resolved = _resolve_path(cited.verb_tokens)
    leftover = cited.verb_tokens[len(resolved.resolved_path) :]
    return resolved, leftover


def _validate_command(cited: _CitedCommand) -> list[str]:
    """Return human-readable violations for a single cited command."""
    violations: list[str] = []
    resolved, leftover = _split_verb_and_positionals(cited)
    cmd = resolved.command
    if cmd is None or not resolved.resolved_path:
        violations.append(f"command path does not resolve in the live CLI: `{cited.raw}`")
        return violations

    # (b) Option validity: every cited option must be a param of the resolved
    # command or a root-global option.
    valid_options = _command_option_names(cmd) | _root_option_names()
    for opt in cited.cited_options:
        if opt not in valid_options:
            violations.append(
                f"`{cited.raw}` cites option `{opt}`, which is not a parameter of "
                f"`aeat {' '.join(resolved.resolved_path)}` (nor a global option)",
            )

    # (c) Dead subcommand of a live group: longest-prefix resolution stops at
    # the deepest reachable command and treats the rest as "arguments", but a
    # GROUP takes no positional arguments — a leftover verb token under a
    # group can only be a subcommand name that does not exist (the shape that
    # let `aeat app ledger payable-invoice` pass while uninvokable after the
    # invoice unification rename). A leftover token that is really the *value*
    # of a value-consuming option on the resolved group (`aeat app quickfile
    # --modelo 130`) is NOT a dead subcommand: the string parser cannot know
    # the group's options, so it over-collects the value into the verb path;
    # exclude those values by consulting the resolved command's real params.
    if hasattr(cmd, "list_commands") and leftover:
        value_consuming = _value_consuming_option_names(cmd) | _value_consuming_option_names(_root_command())
        option_values = _option_value_tokens(cited.tokens, value_consuming)
        dead = [tok for tok in leftover if tok not in option_values]
        if dead:
            violations.append(
                f"`{cited.raw}` cites `{dead[0]}`, which is not a subcommand of "
                f"the group `aeat {' '.join(resolved.resolved_path)}`",
            )
            return violations

    # Missing-required-positional (the ``profile create`` shape) is
    # deliberately NOT enforced here: see the module docstring's limitation
    # note. ``leftover`` is otherwise computed only to keep verb-vs-positional
    # resolution honest for the option-validity check above.
    _ = leftover
    return violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_doc_surface_present() -> None:
    """The user-facing doc surface this gate binds is present."""
    docs = _flat_docs()
    assert docs, "no user-facing docs found under docs/ or README.md"
    names = {d.name for d in docs}
    assert "README.md" in names, "root README.md must be in the gate's scope"
    assert "index.md" in names, "docs/index.md must be in the gate's scope"
    contracts = _sequence_contracts()
    assert contracts, "no private CLI sequence contracts found"


# The floor below which the gate is presumed vacuous. The live doc surface
# cites ``aeat`` roughly 591 times (post per-doc dedup); a count that collapses
# toward zero means the invocation-token anchor was swept off the real
# executable again (the rename-vacuity defect repaired here), so the gate
# would be silently scanning nothing. The floor is set well below the observed
# count and well above zero: it is a vacuity tripwire, not a brittle exact
# assertion, so ordinary doc churn never trips it while a re-broken anchor does.
_VACUITY_FLOOR = 200


def test_gate_scans_a_realistic_invocation_count() -> None:
    """The repaired gate parses hundreds of real ``aeat`` invocations, not ~zero.

    Anti-vacuity tripwire: the token anchor was once swept by the package rename
    onto the ``cadrumo`` token while every documented invocation uses ``aeat``,
    which left the gate parsing almost nothing and passing vacuously. This test
    fails loudly if the parsed-invocation count ever collapses back toward zero,
    so the vacuity regression cannot recur silently behind a green suite.
    """
    total = sum(len(_surface_commands(surface)) for surface in _command_surfaces())
    assert total >= _VACUITY_FLOOR, (
        f"documented-command gate parsed only {total} aeat invocations across the "
        f"doc surface (floor {_VACUITY_FLOOR}); the invocation-token anchor "
        f"(`_AEAT_TOKEN_RE`) has likely been swept off the `aeat` executable, "
        f"making the gate vacuous — re-anchor it on the real CLI executable token"
    )


def test_live_introspection_matches_reality() -> None:
    """Spot-check the in-process walk against the known CLI shape.

    Guards against an introspection regression (e.g. the lazy loaders failing
    to materialize) that would make the gate vacuously pass.
    """
    # `describe` is a leaf with one required positional and no `--modelo`.
    resolved = _resolve_path(("app", "modelo", "describe"))
    assert resolved.resolved_path == ("app", "modelo", "describe")
    describe = resolved.command
    assert describe is not None
    assert not hasattr(describe, "list_commands")
    assert _required_positional_count(describe) == 1
    assert "--modelo" not in _command_option_names(describe)
    assert "--period" in _command_option_names(describe)
    # `--language` / `--format` are root globals.
    assert {"--language", "--format", "--profile"} <= _root_option_names()
    # A genuinely-wrong option must be rejected by the validator.
    bad = _CitedCommand(
        raw="aeat app modelo describe --modelo 130",
        verb_tokens=("app", "modelo", "describe"),
        cited_options=("--modelo",),
        has_positional_token=True,
    )
    assert _validate_command(bad), "validator must flag a non-existent option"
    # A dead subcommand of a LIVE group must be rejected, not absorbed as an
    # "argument" by longest-prefix resolution (the `ledger payable-invoice`
    # regression shape).
    dead_subcommand = _CitedCommand(
        raw="aeat app ledger payable-invoice",
        verb_tokens=("app", "ledger", "payable-invoice"),
        cited_options=(),
        has_positional_token=False,
    )
    flagged = _validate_command(dead_subcommand)
    assert flagged, "validator must flag a dead subcommand under a live group"
    assert "payable-invoice" in flagged[0]
    # ...while a live leaf with a genuine positional argument stays accepted.
    live_with_positional = _CitedCommand(
        raw="aeat config login myprofile",
        verb_tokens=("config", "login", "myprofile"),
        cited_options=(),
        has_positional_token=True,
    )
    assert not _validate_command(live_with_positional)


def test_value_consuming_option_value_is_not_a_dead_subcommand() -> None:
    """A value-consuming option's value under a group is not a dead subcommand.

    ``aeat app quickfile --modelo 130`` cites the real ``--modelo`` option of the
    ``app quickfile`` group with the value ``130``. The string parser cannot know
    the group's options, so it over-collects ``130`` into the verb path and
    longest-prefix resolution leaves it as a leftover under a live group. Without
    consulting the resolved command's params, the gate wrongly flagged the value
    as a dead subcommand. The validator must treat it as the option value it is,
    while still refusing a genuinely non-existent subcommand under the same
    group.
    """
    # Precondition: `app quickfile` is a live group and `--modelo` is a real,
    # value-consuming option of it (guards the fixture against CLI drift).
    quickfile = _resolve_path(("app", "quickfile"))
    assert quickfile.resolved_path == ("app", "quickfile")
    assert quickfile.command is not None
    assert hasattr(quickfile.command, "list_commands")
    assert "--modelo" in _value_consuming_option_names(quickfile.command)

    option_value = _parse_command_line("aeat app quickfile --modelo 130")
    assert option_value is not None
    assert option_value.tokens == ("app", "quickfile", "--modelo", "130")
    assert not _validate_command(option_value), (
        "the value of a value-consuming option must not be flagged as a dead subcommand"
    )

    # A fabricated, genuinely non-existent subcommand under the same live group
    # (with no option consuming it) must still be refused.
    dead = _parse_command_line("aeat app quickfile totally-fake-subcommand")
    assert dead is not None
    flagged = _validate_command(dead)
    assert flagged, "a genuinely dead subcommand under a live group must be refused"
    assert "totally-fake-subcommand" in flagged[0]


@pytest.mark.parametrize("surface", _command_surfaces(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_documented_commands_conform(surface: Path) -> None:
    """Every cited ``aeat`` command resolves with valid options and arguments."""
    violations: list[str] = []
    for cited in _surface_commands(surface):
        violations.extend(_validate_command(cited))
    assert not violations, (
        f"{surface.relative_to(REPO_ROOT)} cites aeat commands that do not conform "
        f"to the live CLI:\n  " + "\n  ".join(violations)
    )


def test_product_docs_have_no_external_client_awareness() -> None:
    """Product docs must never advertise or identify an external client.

    External consumers do not belong to the base application's command model.
    No user page or sequence contract may teach an ``app agent`` path or name a
    client-specific distribution, executable, artifact, or guide.
    """
    forbidden = re.compile(
        r"\bapp\s+agent\b",
        re.IGNORECASE,
    )
    violations: list[str] = []
    for surface in _command_surfaces():
        text = surface.read_text(encoding="utf-8")
        if match := forbidden.search(text):
            line = text.count("\n", 0, match.start()) + 1
            violations.append(f"{surface.relative_to(REPO_ROOT)}:{line}")
    assert not violations, (
        "the base application documentation must have no external-client "
        "awareness; found forbidden marker(s): " + ", ".join(violations)
    )


# ---------------------------------------------------------------------------
# cli-sequence grammar and enrolled-page tier
# ---------------------------------------------------------------------------

# A cli-sequence directive body: ``@setup`` / ``@result`` frame sigils precede
# the ``aeat`` token, and ``{name}`` interpolations fill positional slots. The
# gate must scan its frame lines as ordinary invocations (they get the verb-path
# and option-name checks for free) while ``@capture`` / ``@expect`` lines (no
# ``aeat`` token) are ignored.
_CLI_SEQUENCE_BODY_FIXTURE = """```{cli-sequence} modelo-303-first-quarter
:seed: autonomo-basic-2026
:verify: Verify the calculation before exporting.
@setup aeat app ledger import --file fixtures/2026-1t-statement.csv
aeat app modelo work create 303 --year 2026 --period 1T
@capture work_unit_id result.work_unit_id
aeat app modelo work calculate {work_unit_id}
@result aeat app modelo work verify {work_unit_id}
@expect result.status == "verified_complete"
```
"""

# An enrolled page that ALSO carries a plain ```bash fence with a CORRECT
# executable ``aeat`` invocation — permitted, and scanned by the base checks
# (which pass); enrollment does not refuse or exempt the plain fence.
_ENROLLED_WITH_PLAIN_FENCE_FIXTURE = (
    _CLI_SEQUENCE_BODY_FIXTURE + "\nThen import more data:\n\n```bash\naeat app ledger import --file extra.csv\n```\n"
)

# An enrolled page whose plain ```bash fence cites a genuinely WRONG option —
# proves the base verb-path/option-name checks fire on an enrolled page's plain
# fence exactly as on a non-enrolled page (enrollment does not exempt it).
_ENROLLED_WITH_BAD_OPTION_FENCE_FIXTURE = (
    _CLI_SEQUENCE_BODY_FIXTURE + "\nThen import more data:\n\n```bash\naeat app ledger import --bogus-option\n```\n"
)

# A non-enrolled page with a plain executable fence — it keeps exactly today's
# verb-path and option-name checks (the same checks an enrolled page's fence gets).
_NON_ENROLLED_FIXTURE = "# How-to\n\n```bash\naeat app ledger import --file extra.csv\n```\n"


def test_cli_sequence_frame_lines_conform_as_ordinary_invocations() -> None:
    """A directive body's frame lines are scanned and validated like any invocation.

    The ``@setup`` / ``@result`` sigils are dropped (the ``aeat`` anchor) and the
    ``{name}`` interpolation is a positional placeholder, so every real ``aeat``
    frame line is extracted and conforms to the live CLI; the ``@capture`` /
    ``@expect`` annotation lines (no ``aeat`` token) are not scanned as commands.
    """
    cited = _cited_commands(_CLI_SEQUENCE_BODY_FIXTURE)
    # The four aeat frame lines are extracted; the @capture/@expect annotation
    # lines (no aeat token) are not scanned as commands.
    assert len(cited) == 4
    resolved_paths = {_resolve_path(c.verb_tokens).resolved_path for c in cited}
    assert ("app", "ledger", "import") in resolved_paths
    assert ("app", "modelo", "work", "create") in resolved_paths
    assert ("app", "modelo", "work", "calculate") in resolved_paths
    assert ("app", "modelo", "work", "verify") in resolved_paths
    # No annotation line leaked in as a command (a @capture/@expect sigil token).
    assert all("@" not in tok for c in cited for tok in c.verb_tokens)
    # Every frame line — including the {name}-placeholder calculate/verify frames —
    # conforms to the live CLI (real verb path, real options).
    violations = [v for c in cited for v in _validate_command(c)]
    assert not violations, f"cli-sequence frame lines must conform to the live CLI: {violations}"


def test_shipped_enrolled_page_scan_is_not_vacuous() -> None:
    """At least one shipped page is enrolled, so the enrolled surface is not vacuous.

    The sequence-grammar frame validation and the co-located golden gate only
    protect a real surface if a shipped page actually carries a
    ``{cli-sequence}`` directive. This tripwire (the enrolled-page analogue of
    :func:`test_gate_scans_a_realistic_invocation_count`) fails loudly if the
    enrolled surface ever silently collapses back to zero.
    """
    enrolled = [
        doc.relative_to(REPO_ROOT) for doc in _flat_docs() if _page_is_enrolled(doc.read_text(encoding="utf-8"))
    ]
    assert enrolled, (
        "no shipped page carries a `{cli-sequence}` directive — the enrolled doc "
        "surface has collapsed to zero, so the sequence-grammar and golden gates are vacuous"
    )


# A non-enrolled page whose plain fence cites a genuinely WRONG option, and an
# enrolled page whose plain fence cites the same wrong option — proving the base
# verb-path/option-name checks fire identically regardless of enrollment.
_NON_ENROLLED_BAD_OPTION_FIXTURE = "# How-to\n\n```bash\naeat app ledger import --bogus-option\n```\n"


def test_enrolled_and_non_enrolled_pages_get_the_same_base_checks() -> None:
    """Enrolled and non-enrolled pages alike get the base verb-path/option checks.

    The enrolled/executed distinction is visual and golden-backed, not
    exclusionary (per the amended documented-command decision): an enrolled page MAY carry ordinary
    executable ``aeat`` fences, and those fences receive exactly the same base
    verb-path and option-name validation every fence gets — enrollment neither
    refuses nor exempts them, and never displaces the base checks. This pins the
    contract in one place so a future change that silently drops the base checks
    on an enrolled page's plain fence, or re-introduces a plain-fence refusal,
    reds loudly.
    """
    # A non-enrolled page's plain fence keeps the base checks (a wrong option flags).
    assert not _page_is_enrolled(_NON_ENROLLED_BAD_OPTION_FIXTURE)
    non_enrolled_violations = [
        v for c in _cited_commands(_NON_ENROLLED_BAD_OPTION_FIXTURE) for v in _validate_command(c)
    ]
    assert any("--bogus-option" in v for v in non_enrolled_violations), (
        "a non-enrolled page must keep the verb-path and option-name checks on its plain fence"
    )

    # A correct non-enrolled plain fence passes cleanly.
    assert not _page_is_enrolled(_NON_ENROLLED_FIXTURE)
    assert [v for c in _cited_commands(_NON_ENROLLED_FIXTURE) for v in _validate_command(c)] == [], (
        "a non-enrolled page whose plain-fence command is correct passes the base checks"
    )

    # An ENROLLED page's plain executable fence is NOT refused and IS scanned: a
    # correct command passes, and a wrong option is flagged exactly as on a
    # non-enrolled page (its directive frame lines conform too, so the only
    # violation is the deliberate wrong option in the plain fence).
    assert _page_is_enrolled(_ENROLLED_WITH_PLAIN_FENCE_FIXTURE)
    assert [v for c in _cited_commands(_ENROLLED_WITH_PLAIN_FENCE_FIXTURE) for v in _validate_command(c)] == [], (
        "an enrolled page's correct plain fence and its directive frame lines all pass the base checks"
    )

    assert _page_is_enrolled(_ENROLLED_WITH_BAD_OPTION_FENCE_FIXTURE)
    enrolled_violations = [
        v for c in _cited_commands(_ENROLLED_WITH_BAD_OPTION_FENCE_FIXTURE) for v in _validate_command(c)
    ]
    assert any("--bogus-option" in v for v in enrolled_violations), (
        "an enrolled page's plain executable fence must still receive the base checks — "
        "enrollment does not exempt or refuse it"
    )


# ---------------------------------------------------------------------------
# Mandatory-display ratchet gate tests
# ---------------------------------------------------------------------------


def test_no_new_aeat_plain_fences_in_user_docs() -> None:
    """No user-docs page carries more plain ``aeat`` fences than its ratcheting baseline.

    Every ``aeat`` command in user docs must render through the cli-sequence
    display (an executed ``{cli-sequence}`` directive, or an ``@static`` frame
    where hermetic execution is impossible). This gate ratchets DOWN from a
    committed per-page baseline: a page may never EXCEED its baseline count (a new
    plain ``aeat`` fence reds the gate, naming the page and remediation), and a
    page absent from the baseline may carry none. A page below its baseline passes
    (so the parallel conversion never reds the tree); converter agents tighten the
    baseline down as they land, and an empty baseline means the doctrine is fully
    applied.
    """
    baseline: dict[str, int] = json.loads(_AEAT_FENCE_BASELINE_PATH.read_text(encoding="utf-8"))
    current = _current_aeat_fence_counts()
    docs = REPO_ROOT / "docs"
    problems: list[str] = []
    for page in sorted(current):
        count = current[page]
        allowed = baseline.get(page, 0)
        if count > allowed:
            lines = _aeat_plain_fences((docs / page).read_text(encoding="utf-8"))
            new_line = lines[allowed] if allowed < len(lines) else lines[-1]
            problems.append(
                f"docs/{page}: {count} plain aeat fence(s), baseline allows {allowed} "
                f"(a new one at/after line {new_line}) — render every aeat command through a "
                "{cli-sequence} executed directive, or an @static frame where hermetic "
                f"execution is impossible; then tighten the entry in {_AEAT_FENCE_BASELINE_PATH.name}"
            )
    assert not problems, (
        "user docs must render aeat commands through the cli-sequence display, not plain "
        "fences (mandatory-display doctrine, 2026-07-14):\n  " + "\n  ".join(problems)
    )


def test_no_new_inline_aeat_command_spans_in_user_docs() -> None:
    """No user-docs page inlines more complex ``aeat`` commands than its ratcheting baseline.

    Closes the fence-ratchet loophole: moving a plain ``aeat`` fence into an
    inline ``code`` span shrinks the fence baseline while recreating the
    readability complaint. An inline ``aeat ...`` span carrying two or more
    option/argument tokens is a violation, remediated the same way (render through
    a ``{cli-sequence}`` directive, or ``@static`` where hermetic execution is
    impossible). Bare verb references (``aeat config login``) and single
    flag/argument mentions stay legal. Ratchets DOWN from a committed per-page
    baseline, the same discipline as the fence gate, so it never reds the tree
    during the parallel conversion.
    """
    baseline: dict[str, int] = json.loads(_INLINE_AEAT_SPAN_BASELINE_PATH.read_text(encoding="utf-8"))
    current = _current_inline_aeat_span_counts()
    docs = REPO_ROOT / "docs"
    problems: list[str] = []
    for page in sorted(current):
        count = current[page]
        allowed = baseline.get(page, 0)
        if count > allowed:
            spans = _inline_aeat_command_spans((docs / page).read_text(encoding="utf-8"))
            example = spans[allowed] if allowed < len(spans) else spans[-1]
            problems.append(
                f"docs/{page}: {count} inline aeat command span(s) with 2+ option/arg tokens, "
                f"baseline allows {allowed} (e.g. `{example}`). Render every aeat command through a "
                "{cli-sequence} executed directive, or an @static frame where hermetic execution is "
                f"impossible; then tighten the entry in {_INLINE_AEAT_SPAN_BASELINE_PATH.name}"
            )
    assert not problems, (
        "user docs must render aeat commands through the cli-sequence display, not inline command "
        "spans (mandatory-display doctrine, 2026-07-14):\n  " + "\n  ".join(problems)
    )


def test_inline_span_detector_catches_line_wrapped_commands() -> None:
    """A dissolved command wrapped across source lines is caught as its single-line form.

    The extension that closes the wrapped-span loophole: markdown joins a code
    span split across a soft line break into ONE rendered span, so the detector
    joins each paragraph's wraps before extraction. A paragraph break (which a
    code span cannot cross) and a stripped fenced block never bridge two spans.
    """
    wrapped = "Export the draft with `aeat app modelo export --modelo 130\n--output ./x.boe`; upload it yourself.\n"
    spans = _inline_aeat_command_spans(wrapped)
    assert spans == ["aeat app modelo export --modelo 130 --output ./x.boe"]

    # The same command on a single source line is caught identically.
    single = "Export the draft with `aeat app modelo export --modelo 130 --output ./x.boe`.\n"
    assert _inline_aeat_command_spans(single) == spans

    # A fenced command block is stripped, and the legal inline mentions around it
    # (a bare verb, a single-flag reference) never merge across the paragraph
    # breaks into a spurious 2+-token span.
    with_fence = (
        "Bare `aeat config login` here.\n\n"
        "```bash\naeat app modelo export --modelo 130 --output ./x.boe\n```\n\n"
        "A single flag `aeat config auth configure --file` there.\n"
    )
    assert _inline_aeat_command_spans(with_fence) == []


def test_inline_span_detector_excludes_indented_and_alternate_fenced_directives() -> None:
    """A cli-sequence directive body never leaks a command line as an inline span.

    The directive-strip is line-based, so a directive nested inside a list item
    (indented), a tilde-fenced block, and a longer-run fence are all excluded in
    full — a multi-option ``@result`` / ``@static`` command line inside them
    contributes zero inline spans. Only a genuine inline ``code`` span in prose is
    flagged.
    """
    indented_in_list = (
        "- Prepare the draft:\n"
        "\n"
        "  ```{cli-sequence} demo\n"
        "  :verify: check\n"
        "  @setup aeat --format json app modelo work create --modelo 130 --year 2026 --period 1T\n"
        "  @result aeat --format json app modelo export --modelo 130 --output ./x.boe\n"
        "  @expect exit_code == 0\n"
        "  ```\n"
    )
    assert _inline_aeat_command_spans(indented_in_list) == []

    tilde_fenced = (
        "Intro paragraph.\n\n"
        "~~~{cli-sequence} demo\n"
        "@static aeat app live filed pull-sources --modelo 390 --year 2025 --period 0A\n"
        "~~~\n\n"
        "Outro.\n"
    )
    assert _inline_aeat_command_spans(tilde_fenced) == []

    # A genuine inline prose span in the same document is still flagged, so the
    # strip excludes only directive bodies, not real inline commands.
    mixed = indented_in_list + "\nExport with `aeat app modelo export --modelo 130 --output ./x.boe` yourself.\n"
    assert _inline_aeat_command_spans(mixed) == ["aeat app modelo export --modelo 130 --output ./x.boe"]


def test_aeat_fence_baseline_is_well_formed_and_the_gate_scans_the_live_surface() -> None:
    """The ratchet baseline is well-formed and the gate scans the real user-docs surface.

    Non-vacuity tripwire for the mandatory-display gate: it must govern the actual
    user-docs surface (not an empty set), and the baseline must be a well-formed
    page→positive-count map. The baseline is deliberately NOT asserted equal to
    the live counts: a page below its baseline is legitimate mid-conversion
    progress, so requiring equality would red the tree while the converter agents
    work. The one-directional guarantee (no page exceeds its baseline) lives in
    :func:`test_no_new_aeat_plain_fences_in_user_docs`; tightening the baseline
    toward empty is the converters' committed step.
    """
    pages = _user_doc_pages()
    assert len(pages) >= 20, (
        f"the mandatory-display gate scans only {len(pages)} user-docs pages; the surface "
        "the gate governs has collapsed — its scan is vacuous"
    )
    for baseline_path in (_AEAT_FENCE_BASELINE_PATH, _INLINE_AEAT_SPAN_BASELINE_PATH):
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        assert isinstance(baseline, dict), f"{baseline_path.name} must be a JSON object mapping page → count"
        for page, allowed in baseline.items():
            assert isinstance(page, str) and page, (
                f"{baseline_path.name} keys must be non-empty docs-relative page paths"
            )
            # A non-negative int: a converter may zero a fully-converted page's
            # entry rather than delete the key (a 0 allowance enforces zero for
            # that page, same as an absent key), and the count never goes negative.
            assert isinstance(allowed, int) and not isinstance(allowed, bool) and allowed >= 0, (
                f"{baseline_path.name} entry {page!r} must be a non-negative integer count, got {allowed!r}"
            )


def test_a_blocked_reason_naming_the_product_is_not_parsed_as_a_command() -> None:
    """Prose directives are skipped by rule, not by vocabulary coincidence.

    ``@capture`` and ``@expect`` were skipped only because their syntax happens
    to exclude the product name, which made the scheme depend on documentation
    prose never using that word. A ``@blocked`` reason reading "No aeat verb
    creates an evidence bundle" broke exactly that assumption: the sentence
    after the product name was resolved as a verb path and reported as a
    command that does not exist.
    """
    reason = "@blocked unconverted No aeat verb creates an evidence bundle, so no id exists to address."
    assert _parse_command_line(reason) is None

    for directive in ("@capture work_unit_id result.work_unit_id", '@expect result.status == "ok"'):
        assert _parse_command_line(directive) is None

    # The skip is scoped to prose directives: a real frame still parses, so the
    # fix cannot hide an invocation that should have been checked.
    frame = _parse_command_line("@setup aeat app modelo work create --modelo 303")
    assert frame is not None
    assert frame.verb_tokens[:3] == ("app", "modelo", "work")
