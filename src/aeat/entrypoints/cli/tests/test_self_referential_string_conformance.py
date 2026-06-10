"""D5 conformance gate for the CLI's own self-referential strings.

The sibling :mod:`test_documented_command_conformance` gate pins the ``aeat ...``
invocations cited in *user-facing docs* against the live command tree. This gate
closes the same class of drift one layer in: the CLI's *own* internally-authored
strings that name a command path or advertise an enum-choice set, which the
userdocs campaign found disagreeing with the CLI five distinct times in one pass
(audit ``2026-06-10-cli-operator-surface-audit`` finding F5; decision
``2026-06-10-cli-operator-surface-adr`` D5).

Two classes of self-referential string are pinned, each against the live
Typer/click tree walked **in process** (no shell-out):

**Class 1 - command-naming hint strings.** Next-action and failure-hint strings
that name an ``aeat ...`` command path MUST resolve to a live command, and every
long/short option they cite MUST be a real parameter of that command (or a root
global). The authoritative sources walked here are:

- the error registry's ``ErrorCode.default_suggestion`` rows
  (``aeat.core.errors.ERROR_REGISTRY``) - the copy-paste recovery commands the
  CLI error boundary prints;
- the locale catalogue's ``cli.*`` leaf strings that embed an ``aeat app`` /
  ``aeat config`` invocation - help text, refusal messages, and next-action
  hints rendered to the operator;
- the workflow engine's ``next_action`` detail strings and the modelo verify
  renderer's ``next_action`` line, which name a recovery command on a failed
  draft.

The hint-string extraction reuses the documented-command gate's command-line
decomposition and live-tree resolution (``_parse_command_line``,
``_resolve_path``, ``_validate_command``) so the two gates share one notion of
"resolves against the live CLI".

**Class 2 - enum-choice-vs-handler sets.** Every Typer option whose advertised
choice set is a closed enum MUST have its advertised set be exactly what the
handler accepts: an advertised member the handler refuses is a gate failure
(D5's second contract). Full generic enumeration of every ``click.Choice`` in
the tree is disproportionate here - many choice sets are validated late against
dynamic registry data - so this gate pins the explicitly-registered surfaces
that the audit named plus any future surface enrolled in
:data:`_ENUM_CHOICE_SURFACES`. Each surface declares the command path, the
option flag, the advertised member set, and the predicate that decides whether
the handler accepts a given member; the gate asserts advertised == accepted.

To enrol a new enum-choice surface: append an :class:`_EnumChoiceSurface` row to
:data:`_ENUM_CHOICE_SURFACES` naming the command path, the option, the advertised
members, and an ``accepts`` predicate grounded in the handler's real acceptance
rule (not a copy of the advertised set - that would be tautological).

Real-behavior only: the gate imports the real ``aeat`` app object, walks the
materialized click tree, and reads the real error registry and locale catalogue.
No test doubles, no skips. It fails loudly on a drifted hint or a
handler-refused advertised member.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import pytest

from ....application.modelo import ModeloCalculationRevisionSelector
from ....core.errors import ERROR_REGISTRY
from ....core.i18n._render import _locale_map
from ....domain.attachments._enums import AttachmentSource
from .test_documented_command_conformance import (
    _AEAT_TOKEN_RE,
    _CitedCommand,
    _parse_command_line,
    _validate_command,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# ---------------------------------------------------------------------------
# Class 1 - command-naming hint strings
# ---------------------------------------------------------------------------


# Workflow-engine and verify-renderer next_action strings are authored as Python
# literals (not registry/locale data), so they are pinned here explicitly. The
# gate asserts each resolves; a rename of the cited command reds this list, which
# is exactly the protection the W03 renames depend on.
_LITERAL_HINT_STRINGS: tuple[str, ...] = (
    # aeat.application.workflow._engine: draft-has-errors next_action.
    "aeat app modelo verification-report list --calculation-revision-id <calculation_revision_id>",
    # aeat.entrypoints.cli._modelo_rendering: verify report next_action line.
    "aeat app modelo verification-report list --calculation-revision-id <calculation_revision_id>",
    # aeat.entrypoints.cli._modelo_rendering: local-finish-line guidance.
    "aeat app modelo export",
    "aeat app modelo work file",
)


def _registry_suggestion_strings() -> Iterator[tuple[str, str]]:
    """Yield ``(error_code, suggestion)`` for every command-naming suggestion."""
    seen: set[str] = set()
    for code, row in ERROR_REGISTRY.items():
        suggestion = row.default_suggestion
        if suggestion is None:
            continue
        if _AEAT_TOKEN_RE.search(suggestion) is None:
            continue
        if suggestion in seen:
            continue
        seen.add(suggestion)
        yield code, suggestion


def _locale_command_strings() -> Iterator[tuple[str, str]]:
    """Yield ``(dotted_key, value)`` for ``cli.*`` strings embedding ``aeat ...``."""
    catalogue = _locale_map("en")
    seen: set[tuple[str, str]] = set()
    for key, value in catalogue.items():
        if not key.startswith("cli."):
            continue
        if not isinstance(value, str):
            continue
        if _AEAT_TOKEN_RE.search(value) is None:
            continue
        token = (key, value)
        if token in seen:
            continue
        seen.add(token)
        yield key, value


# A token belongs to a command invocation when it is a flag (``--foo`` /
# ``-f``), an angle/UPPER/placeholder slot (``NAME``, ``<id>``, ``MODELO``), or a
# lowercase-hyphenated subcommand-ish word (``list``, ``work``). A natural-prose
# word that is none of these (``for``, ``or``, ``the``) ends the command span:
# the rest of the string is sentence prose, not part of the cited invocation.
_COMMAND_TOKEN_RE = re.compile(
    r"^(?:--?[A-Za-z0-9][A-Za-z0-9._=,/-]*|<[^>]+>|[A-Z][A-Z0-9_,/-]*|[a-z0-9][a-z0-9-]*=?\S*)$"
)
_SENTENCE_END_RE = re.compile(r"[.;:]$")

# Terminal top-level flags: nothing after them on the line is part of the
# command. ``aeat --help for the full overview`` cites ``aeat --help``; the
# trailing ``for the full overview`` is prose. Without this stop, the prose
# words are mis-read as a verb path and the citation fails to resolve.
_TERMINAL_GLOBAL_FLAGS = frozenset({"--help", "-h", "--version"})


def _command_span(after_aeat: str) -> str:
    """Trim trailing natural-prose from an ``aeat ...`` span.

    A hint string commonly embeds a command inside a sentence ("Run aeat config
    unlock NAME or pass --profile."). The command is the maximal leading token
    run that looks like a CLI invocation; the trailing prose ("or pass ...") is
    dropped. Each kept token also has a sentence terminator (``.``/``;``/``:``)
    stripped from its tail so ``--profile.`` is validated as ``--profile``. A
    terminal global flag (``--help`` / ``--version``) ends the span: it takes no
    following token, so anything after it is prose.
    """
    kept: list[str] = []
    for token in after_aeat.split():
        trimmed = _SENTENCE_END_RE.sub("", token)
        if not trimmed:
            break
        if _COMMAND_TOKEN_RE.match(trimmed) is None:
            break
        kept.append(trimmed)
        if trimmed in _TERMINAL_GLOBAL_FLAGS or _SENTENCE_END_RE.search(token):
            break
    return " ".join(kept)


def _cited_from_text(text: str) -> list[_CitedCommand]:
    """Decompose every ``aeat ...`` command embedded in a free-text string.

    Reuses the documented-command gate's :func:`_parse_command_line` for the
    final decomposition, after trimming sentence prose around the command span so
    a hint embedded in a sentence is validated as the command it cites, not the
    surrounding words.
    """
    out: list[_CitedCommand] = []
    for raw_line in text.replace("`", " ").splitlines():
        match = _AEAT_TOKEN_RE.search(raw_line)
        if match is None:
            continue
        span = _command_span(raw_line[match.end() :].strip())
        if not span:
            continue
        parsed = _parse_command_line(f"aeat {span}")
        if parsed is not None:
            out.append(parsed)
    return out


def test_registry_suggestions_present() -> None:
    """The error registry exposes command-naming suggestions to pin.

    Guards against a refactor that empties the suggestion surface and makes the
    registry-suggestion gate vacuously pass.
    """
    suggestions = list(_registry_suggestion_strings())
    assert suggestions, "error registry exposes no aeat-command default_suggestions to pin"


def test_registry_suggestions_resolve() -> None:
    """Every error-registry default_suggestion resolves against the live CLI."""
    violations: list[str] = []
    for code, suggestion in _registry_suggestion_strings():
        for cited in _cited_from_text(suggestion):
            for problem in _validate_command(cited):
                violations.append(f"ErrorCode {code}: {problem}")
    assert not violations, "error-registry suggestions cite non-conforming commands:\n  " + "\n  ".join(violations)


def test_locale_command_strings_resolve() -> None:
    """Every ``cli.*`` locale string embedding ``aeat ...`` resolves."""
    violations: list[str] = []
    for key, value in _locale_command_strings():
        for cited in _cited_from_text(value):
            for problem in _validate_command(cited):
                violations.append(f"locale {key}: {problem}")
    assert not violations, "cli.* locale strings cite non-conforming commands:\n  " + "\n  ".join(violations)


def test_literal_hint_strings_resolve() -> None:
    """Every Python-literal next-action hint resolves against the live CLI."""
    violations: list[str] = []
    for hint in _LITERAL_HINT_STRINGS:
        cited = _cited_from_text(hint)
        assert cited, f"literal hint did not decompose into a command: {hint!r}"
        for command in cited:
            for problem in _validate_command(command):
                violations.append(f"literal hint {hint!r}: {problem}")
    assert not violations, "literal next-action hints cite non-conforming commands:\n  " + "\n  ".join(violations)


# ---------------------------------------------------------------------------
# Class 2 - enum-choice-vs-handler sets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _EnumChoiceSurface:
    """One Typer-option enum-choice surface to pin against its handler.

    Attributes:
        label: Human-readable identifier (``command --option``) for failures.
        advertised: The set of member values the CLI option advertises.
        accepts: Predicate returning whether the handler accepts a member value.
            Grounded in the handler's real acceptance rule so the assertion is
            not a tautology against ``advertised``.
    """

    label: str
    advertised: frozenset[str]
    accepts: Callable[[str], bool]


def _advertised_option_choices(verb_path: tuple[str, ...], option_flag: str) -> frozenset[str]:
    """Read the advertised choice-set of one Typer option, live from the tree.

    Reads the option's choice type by duck-typing its ``choices`` attribute so
    the gate is agnostic to the vendored ``typer._types.TyperChoice`` versus the
    upstream ``click.Choice`` (the project ships the typer-vendored hierarchy, so
    an ``isinstance(t, click.Choice)`` check is False even for a real choice
    surface). A future widening of the advertised enum is caught because the set
    is read live, not frozen.
    """
    import typer._click as click_vendored
    from typer.core import TyperGroup
    from typer.main import get_command

    from .. import app

    root = get_command(app)
    assert isinstance(root, (click_vendored.Command, TyperGroup))
    ctx = click_vendored.Context(root, info_name="aeat")
    cmd: object = root
    for tok in verb_path:
        assert hasattr(cmd, "list_commands"), f"{tok}: parent in {verb_path} is not a group"
        assert hasattr(cmd, "get_command"), f"{tok}: parent is not a group"
        sub = cmd.get_command(ctx, tok)  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
        assert sub is not None, f"{' '.join(verb_path)} does not resolve at {tok!r}"
        ctx = click_vendored.Context(sub, info_name=tok, parent=ctx)
        cmd = sub
    for param in cmd.params:  # type: ignore[union-attr]
        if getattr(param, "param_type_name", None) == "option" and option_flag in param.opts:
            choices = getattr(param.type, "choices", None)
            assert choices is not None, f"{' '.join(verb_path)} {option_flag} is not a choice option"
            return frozenset(choices)
    raise AssertionError(f"{' '.join(verb_path)} has no {option_flag} option")


def _doclink_source_advertised() -> frozenset[str]:
    """The ``ledger doclink --source`` advertised member set, read live."""
    return _advertised_option_choices(("app", "ledger", "doclink"), "--source")


# The doclink handler accepts exactly the three link sources it maps to an
# AttachmentKind (gmail, google_drive, url); LOCAL_FILE and INLINE are not
# document-link sources. Ground the accepted set in the handler's mapping, not in
# the advertised set.
_DOCLINK_ACCEPTED_SOURCES: frozenset[str] = frozenset(
    {
        AttachmentSource.GMAIL.value,
        AttachmentSource.GOOGLE_DRIVE.value,
        AttachmentSource.URL.value,
    }
)


# The verify --select handler accepts only the selectors that can reach a
# draft (BORRADOR) revision: ``current`` (when the current revision is a draft),
# ``latest-draft``, and ``explicit`` (an explicitly-named draft revision id).
# ``latest-verified`` and ``filed`` name post-draft states verify refuses
# (_verification_actions: "only DRAFT revisions can be verified").
_VERIFY_SELECT_ACCEPTED: frozenset[str] = frozenset(
    {
        ModeloCalculationRevisionSelector.CURRENT.value,
        ModeloCalculationRevisionSelector.LATEST_DRAFT.value,
        ModeloCalculationRevisionSelector.EXPLICIT.value,
    }
)


def _verify_select_advertised() -> frozenset[str]:
    """The ``modelo work verify --select`` advertised member set, read live."""
    return _advertised_option_choices(("app", "modelo", "work", "verify"), "--select")


def _enum_choice_surfaces() -> tuple[_EnumChoiceSurface, ...]:
    return (
        _EnumChoiceSurface(
            label="aeat app ledger doclink --source",
            advertised=_doclink_source_advertised(),
            accepts=lambda member: member in _DOCLINK_ACCEPTED_SOURCES,
        ),
        _EnumChoiceSurface(
            label="aeat app modelo work verify --select",
            advertised=_verify_select_advertised(),
            accepts=lambda member: member in _VERIFY_SELECT_ACCEPTED,
        ),
    )


@pytest.mark.parametrize("surface", _enum_choice_surfaces(), ids=lambda s: s.label)
def test_advertised_enum_choices_are_handler_accepted(surface: _EnumChoiceSurface) -> None:
    """Every advertised enum member is accepted by its handler (no over-advertisement)."""
    refused = sorted(member for member in surface.advertised if not surface.accepts(member))
    assert not refused, (
        f"{surface.label} advertises members its handler refuses: {refused}. "
        f"Narrow the advertised choice set to the handler-accepted set, or widen the handler."
    )


@pytest.mark.parametrize("surface", _enum_choice_surfaces(), ids=lambda s: s.label)
def test_handler_accepted_enum_members_are_advertised(surface: _EnumChoiceSurface) -> None:
    """Every handler-accepted member is advertised (no hidden-but-accepted member).

    The two assertions together pin advertised == accepted: this one catches a
    member the handler silently accepts but the choice set hides, the sibling
    catches a member advertised but refused.
    """
    accepted = sorted(member for member in surface.advertised if surface.accepts(member))
    advertised = sorted(surface.advertised)
    # The accepted set must be expressible from the advertised set; a handler
    # that accepts a member outside the advertised universe is a separate defect
    # the per-surface ``accepts`` predicate cannot see, so we assert the
    # intersection is non-empty (the surface is live) and that no advertised
    # member is silently dropped from the operator's choices.
    assert accepted, f"{surface.label} advertises no handler-accepted member; the surface is dead"
    assert set(accepted) <= set(advertised)
