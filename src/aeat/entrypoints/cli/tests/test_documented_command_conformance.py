"""Argument-level conformance gate for documented ``aeat`` commands.

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
cited in a user-facing doc, asserts:

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
Diataxis trees the sibling gate already binds — so the same class of error is
caught wherever a command is documented.

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

Real-behavior only: the gate imports the real ``aeat`` app object and walks the
materialized click command tree (which triggers the lazy-subcommand loaders).
No test doubles. It fails loudly on an invalid documented command and passes
when the docs are correct.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import cast

import click
import pytest
from typer.main import get_command

from ....core.paths import PROJECT_ROOT
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# All user-facing doc surfaces. The flat ``docs/*.md`` pages and the root
# ``README.md`` are the surfaces the verb-only conformance gate never covered.
_FLAT_DOC_GLOBS = ("docs/*.md",)
_TREE_DOC_DIRS = ("docs/tutorials", "docs/explanation", "docs/how-to")

# Inline backticks and fenced blocks are the only authoritative command
# surfaces; a bare ``aeat ...`` in prose is not a cited invocation.
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

# A line is an ``aeat`` invocation when ``aeat`` appears as a bare token
# (start of line or after shell punctuation), not as a substring (``aeat.exe``).
_AEAT_TOKEN_RE = re.compile(r"(?:^|[\s$|&(;])aeat(?=\s|$)")

# Global options declared on the root callback. Accepted at any position before
# the subcommand path and validated against the root command's own params, so
# this set is a documentation aid only — the authoritative source is the live
# root command (see :func:`_root_option_names`).
_LINE_CONTINUATION_RE = re.compile(r"\\\s*$")


def _flat_docs() -> list[Path]:
    docs: list[Path] = []
    for pat in _FLAT_DOC_GLOBS:
        docs.extend(sorted(PROJECT_ROOT.glob(pat)))
    for d in _TREE_DOC_DIRS:
        docs.extend(sorted((PROJECT_ROOT / d).rglob("*.md")))
    readme = PROJECT_ROOT / "README.md"
    if readme.is_file():
        docs.append(readme)
    return docs


# ---------------------------------------------------------------------------
# Live CLI introspection
# ---------------------------------------------------------------------------


@cache
def _root_command() -> click.Command:
    """Materialize the live ``aeat`` click command (root of the tree)."""
    # Typer vendors its own Click fork, so typer.main.get_command is typed to
    # return typer._click.core.Command. It is the same object family at runtime;
    # the cast bridges the static vendored/upstream duality so the rest of this
    # module reasons about the tree as upstream click.Command.
    return cast(click.Command, get_command(app))


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


@dataclass(frozen=True)
class _CitedCommand:
    """A single cited ``aeat`` invocation, decomposed for validation."""

    raw: str
    verb_tokens: tuple[str, ...]
    cited_options: tuple[str, ...]
    # True when at least one non-flag token follows the verb path (a value or
    # a placeholder) — used to evaluate the missing-required-positional check.
    has_positional_token: bool


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
    # Some doc lines prefix the command with a shell sigil or a tab-led label.
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
                f"`aeat {' '.join(resolved.resolved_path)}` (nor a global option)"
            )

    # Missing-required-positional (the ``profile create`` shape) is
    # deliberately NOT enforced here: see the module docstring's limitation
    # note. ``leftover`` is computed only to keep verb-vs-positional resolution
    # honest for the option-validity check above.
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


@pytest.mark.parametrize("doc", _flat_docs(), ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_documented_commands_conform(doc) -> None:
    """Every cited ``aeat`` command resolves with valid options and arguments."""
    text = doc.read_text(encoding="utf-8")
    violations: list[str] = []
    for cited in _cited_commands(text):
        violations.extend(_validate_command(cited))
    assert not violations, (
        f"{doc.relative_to(PROJECT_ROOT)} cites aeat commands that do not conform "
        f"to the live CLI:\n  " + "\n  ".join(violations)
    )
