"""Suggestion-string command-citation conformance gate.

The CLI's instructive surface is wider than ``--help`` and the how-to docs:
the curated operator help documents, ``next_action`` builder strings, the
runtime write-policy, and the four locale catalogues all cite ``aeat app ...`` /
``aeat config ...``
invocations that an operator is told to run next. The pull/--file standard
rule (``cadrumo-pull-and-file-standard``) records that NONE of these strings
were covered by a conformance gate: ``test_documented_command_conformance``
scans only the how-to docs, and ``test_json_schema_conformance`` only the
envelope ``command=`` identifiers, so "a verb rename MUST be swept by hand"
through every suggestion surface. A rename that misses one leaves a dead
operator instruction — the error path tells the operator to run a command
that no longer exists, which is a silent failure of the first instructive
surface.

This gate converts that hand-sweep obligation into CI enforcement. It walks
the REAL Click tree (``typer.main.get_command`` over the live Cadrumo app —
no mocks, no fixture trees) and resolves every cited command path from:

- the curated operator help documents (root / config / app surfaces);
- every string literal in production modules under ``cadrumo.adapters``,
  ``cadrumo.application``, ``cadrumo.core.errors``, and ``cadrumo.entrypoints``
  (AST-extracted, so comments cannot false-positive and ``next_action`` /
  write-policy / envelope-builder / adapter-refusal strings are all swept).

The four locale catalogues (``en``/``es``/``ca``/``hu``) carry the same class
of citations inside translated suggestion text and are the natural fourth
sweep. This was tracked as a follow-up when the gate first landed (the
catalogues carried three locale-divergent dead citations at that time); it is
now closed by :func:`test_locale_catalogues_cite_live_commands`, which walks
every string leaf of every catalogue through the same live-tree resolver.
Landing that sweep caught three real dead citations shipped across the
catalogues: all four locales cited a never-existing ``aeat config profile
health`` for the Google OAuth profile-repair suggestion (corrected to the
real ``aeat config profile status``); the Hungarian catalogue alone cited a
retired ``aeat config doctor`` path where the sibling locales already cited
the real ``aeat config repair`` (corrected to match); and the Spanish and
Catalan catalogues each hardcoded a stale ``aeat config first-run`` inside
the no-active-profile landing message, duplicating — and diverging from —
the ``%{command}`` interpolation the message template already appends
(:func:`application.operator_surface.build_root_landing_report` supplies that
command as ``aeat config profile create NAME``; the English and Hungarian
catalogues never hardcoded a command there, and es/ca were corrected to
match that bare-message shape).
Locale edits route through ``python -m dev.locales set`` per the
locale-CLI workflow, never a hand-edit of the YAML.

Citation grammar: ``aeat`` followed by a root family (``app`` / ``config``)
and a run of lowercase kebab-case tokens. Resolution walks group-by-group and
accepts trailing tokens once a leaf command is reached (they are arguments);
uppercase placeholders (``NAME``), options (``--file``), and ``<id>`` forms
terminate the token run by construction. Each suite asserts a minimum
citation count so a regression in the extractor cannot silently scan nothing,
and the scanner itself is proven against a synthetic dead citation.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import cast

import click
import pytest

from cadrumo.application.operator_surface import HelpSurface, build_help_document, build_root_landing_report
from cadrumo.core import scan_directory
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.entrypoints.cli._verb_input_schema import DECLARED_UNIMPLEMENTED_SURFACES
from cadrumo.tests.cli_runner import cadrumo_click_command
from dev._paths import REPO_ROOT
from dev.locales import LocaleManager, LocaleNode
from dev.locales.manager import locale_catalogue_source
from dev.quality.cli_action_census import census
from dev.quality.cli_action_census_dispositions import (
    DEFAULT_DISPOSITIONS_PATH,
    DispositionRole,
    DispositionValidationError,
    checked_in_dispositions,
    validate_dispositions,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PACKAGE_ROOT = REPO_ROOT / "src" / "cadrumo"
_LOCALES_DIR = _PACKAGE_ROOT / "locales"
_AST_SCAN_ROOTS = (
    _PACKAGE_ROOT / "adapters",
    _PACKAGE_ROOT / "application",
    _PACKAGE_ROOT / "core" / "errors",
    _PACKAGE_ROOT / "entrypoints",
)

# ``aeat`` + a root family + a run of kebab-case tokens. A token is lowercase
# kebab-case OR a bare modelo code (three digits, e.g. ``100``/``303``), the
# only digit-leading command segments in the live tree (``aeat app live
# borrador 100 list``). Uppercase placeholders, ``--option`` forms, and
# ``<value>`` forms end the run, so only verb-path candidates (plus possibly
# lowercase argument VALUES, which the resolver tolerates past a leaf) are
# captured. Admitting the modelo code keeps a runnable ``... borrador 100 list``
# citation from terminating prematurely on the ``borrador`` group.
# ``an aeat app`` is ordinary prose about an AEAT web application, not an
# operator invocation, so the article boundary is excluded explicitly.
_CITATION_PATTERN = re.compile(r"(?<!an )\baeat (app|config)((?: (?:[a-z][a-z0-9-]*|\d{3}))*)")


@cache
def _root_command() -> click.Command:
    """Build the live Click tree once for the whole module."""
    return cadrumo_click_command()


def _is_group(command: click.Command) -> bool:
    """Return whether ``command`` is a structural group (not a runnable leaf).

    ``list_commands`` is the structural group marker; the vendored TyperGroup
    is not a guaranteed upstream ``click.Group`` subclass, so narrow by
    interface rather than isinstance — an isinstance check silently treats
    every group as a leaf (caught by ``test_scanner_flags_a_group_citation``).
    """
    return hasattr(command, "list_commands")


def _resolve_citation(tokens: tuple[str, ...]) -> tuple[str | None, bool]:
    """Walk ``tokens`` through the live tree.

    Returns ``(dead_token, terminates_on_group)``:

    - ``dead_token`` is the first token that does not resolve, or ``None`` when
      every token resolves. Tokens beyond a leaf command are positional
      argument values and are accepted.
    - ``terminates_on_group`` is ``True`` when the citation resolves cleanly but
      the final resolved command is a group (e.g. ``config repair integrity``),
      which is NOT runnable verbatim — the operator must pick a child or be
      pointed at ``... --help``.
    """
    command: click.Command = _root_command()
    context = click.Context(command, info_name="aeat")
    for token in tokens:
        if not _is_group(command):
            # Already at a leaf; remaining tokens are argument values.
            return None, False
        group = cast("click.Group", command)
        subcommand = group.get_command(context, token)
        if subcommand is None:
            return token, False
        context = click.Context(subcommand, info_name=token, parent=context)
        command = subcommand
    return None, _is_group(command)


@cache
def _root_option_names() -> frozenset[str]:
    """Long/short option strings declared on the root callback.

    Root-global options (``--language`` / ``--format`` / ``--profile`` /
    ``--help`` / etc.) are accepted on any leaf, so the option-validity check
    unions them with the resolved command's own params. Mirrors
    :func:`test_documented_command_conformance._root_option_names`.
    """
    names: set[str] = set()
    for param in _root_command().params:
        if getattr(param, "param_type_name", None) == "option":
            names.update(param.opts)
            names.update(param.secondary_opts)
    return frozenset(names)


def _command_option_names(command: click.Command) -> frozenset[str]:
    """Long/short option strings declared on ``command``.

    Mirrors :func:`test_documented_command_conformance._command_option_names`
    so the suggestion surface validates cited ``--option`` tokens against the
    same authoritative live-parameter set the how-to docs are checked against.
    """
    names: set[str] = set()
    for param in command.params:
        if getattr(param, "param_type_name", None) == "option":
            names.update(param.opts)
            names.update(param.secondary_opts)
    return frozenset(names)


# An ``--option`` / ``-o`` token in suggestion text. ``--help`` is always valid
# (it is a root global), so it never reaches the option-validity check; the
# pattern still captures it so the citation's trailing-help recovery works.
# A trailing ``=`` form (``--format=json``) is split to the bare option name.
_OPTION_TOKEN_PATTERN = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*|-[a-zA-Z])(?=[\s=.,;)\]'\"]|$)")


def _resolve_leaf_command(tokens: tuple[str, ...]) -> click.Command | None:
    """Return the deepest live command the verb tokens resolve to, or ``None``.

    Walks group-by-group exactly like :func:`_resolve_citation` but returns the
    resolved command object (the leaf, or the deepest group) so its parameter
    set can be introspected. Returns ``None`` when any token fails to resolve —
    the dead-token check already reports that as a failure, so option validity
    is only evaluated on a citation whose verb path is sound.
    """
    command: click.Command = _root_command()
    context = click.Context(command, info_name="aeat")
    for token in tokens:
        if not _is_group(command):
            return command
        group = cast("click.Group", command)
        subcommand = group.get_command(context, token)
        if subcommand is None:
            return None
        context = click.Context(subcommand, info_name=token, parent=context)
        command = subcommand
    return command


def _cited_options_after(text: str, start: int) -> list[str]:
    """Extract ``--option`` tokens that belong to the citation ending at ``start``.

    Scans forward from the end of the matched verb path until the next ``aeat``
    citation begins or the text ends, so options trailing one suggested command
    are not mis-attributed to a later one. ``--help`` is dropped (a universal
    root global that is always runnable). ``--opt=value`` is reduced to the bare
    option name.
    """
    next_match = _CITATION_PATTERN.search(text, start)
    end = next_match.start() if next_match is not None else len(text)
    window = text[start:end]
    options: list[str] = []
    for match in _OPTION_TOKEN_PATTERN.finditer(window):
        name = match.group(1)
        if name == "--help":
            continue
        options.append(name)
    return options


def _iter_citations(text: str) -> Iterator[tuple[str, tuple[str, ...], bool, tuple[str, ...]]]:
    """Yield ``(cited_text, verb_tokens, has_trailing_help, cited_options)`` per citation.

    ``has_trailing_help`` records whether ``--help`` immediately follows the
    cited verb path in the source text. The citation regex stops at the first
    ``--option`` form, so a runnable ``aeat config repair integrity --help``
    citation parses as the bare-group token run; this flag recovers the
    operator-runnable distinction the regex drops.

    ``cited_options`` are the ``--option`` / ``-o`` tokens the regex drops,
    recovered from the text following the verb path (up to the next citation),
    so a suggestion can be validated against the resolved command's parameter
    set — catching a dead option (e.g. ``... split <id> --dry-run`` where
    ``split`` has no ``--dry-run``) the verb-only check could never see.
    """
    for match in _CITATION_PATTERN.finditer(text):
        remainder = text[match.end() :]
        has_trailing_help = bool(re.match(r"\s+--help\b", remainder))
        cited_options = tuple(_cited_options_after(text, match.end()))
        verb = match.group(1)
        path_tokens = match.group(2)
        assert isinstance(verb, str)
        assert isinstance(path_tokens, str)
        yield (
            match.group(0),
            (verb, *path_tokens.split()),
            has_trailing_help,
            cited_options,
        )


def _dead_citations_in(text: str, *, origin: str, require_runnable_leaf: bool = False) -> list[str]:
    """Return instructive failure rows for every non-runnable citation in ``text``.

    A citation is dead when one of its tokens does not resolve in the live tree
    — always a failure.

    When ``require_runnable_leaf`` is set (the operator-suggestion surface:
    curated help ``command`` fields,
    where the cited string IS the command the operator is told to run), a
    citation that resolves cleanly to a command GROUP with no trailing
    ``--help`` is ALSO a failure: a group is not executable verbatim
    (``Missing command``), so the operator is sent to a non-runnable line.
    ``<group> --help`` IS runnable and is accepted. The flag is OFF for the
    broad production-string-literal scan, where a bare ``aeat config google``
    is overwhelmingly a prose/docstring reference to a command *family*, not a
    runnable suggestion, and group-termination is legitimate there.

    The flag ALSO gates option validity: under ``require_runnable_leaf`` every
    cited ``--option`` must be a real parameter of the resolved command (or a
    root-global option), so a suggestion citing an option the target verb does
    not declare (e.g. ``... split <id> --dry-run`` where ``split`` carries only
    ``--yes``) is flagged. Option validity is scoped to the runnable-suggestion
    surfaces because reference prose can legitimately mention an option in the
    abstract; a runnable suggestion is the line the operator pastes verbatim.
    """
    failures: list[str] = []
    for cited, tokens, has_trailing_help, cited_options in _iter_citations(text):
        dead_token, terminates_on_group = _resolve_citation(tokens)
        if dead_token is not None:
            # A surface whose verb was deliberately withdrawn while its
            # capability stayed live is declared, not dead. The declaration is
            # the only visible evidence that a capability lost its door, so
            # naming it must not be an error -- but the judgement is READ from
            # the one register that holds it, never restated here, or the two
            # lists drift and a genuinely dead verb hides behind the copy.
            # CLI verbs are hyphenated ("subject-access-request") while the
            # register keys them by schema name ("subject_access_request"),
            # so the two spellings are reconciled here rather than in either.
            if ".".join(tokens).replace("-", "_") in DECLARED_UNIMPLEMENTED_SURFACES:
                continue
            failures.append(f"{origin}: cites {cited!r} but {dead_token!r} does not resolve in the live CLI tree")
            continue
        if require_runnable_leaf and terminates_on_group and not has_trailing_help:
            failures.append(
                f"{origin}: cites {cited!r} which resolves to a command GROUP, not a runnable leaf; "
                "append a child command or cite '... --help' so the suggestion runs verbatim"
            )
        if require_runnable_leaf and cited_options:
            command = _resolve_leaf_command(tokens)
            if command is not None and not _is_group(command):
                valid_options = _command_option_names(command) | _root_option_names()
                for option in cited_options:
                    if option not in valid_options:
                        failures.append(
                            f"{origin}: cites {cited!r} with option {option!r}, which is not a parameter of "
                            f"'aeat {' '.join(tokens)}' (nor a root-global option)"
                        )
    return failures


def _count_citations(text: str) -> int:
    return sum(1 for _ in _iter_citations(text))


def _option_validity_failures(text: str, *, origin: str) -> list[str]:
    """Return only the option-validity failures for ``text`` under strict mode.

    A thin focused wrapper used by the anti-tautology proof so it asserts the
    option check in isolation from the verb-path and group-termination checks.
    """
    return [
        failure
        for failure in _dead_citations_in(text, origin=origin, require_runnable_leaf=True)
        if "with option" in failure
    ]


def _iter_production_modules() -> Iterator[Path]:
    for scan_root in _AST_SCAN_ROOTS:
        for module_path in scan_directory(scan_root, pattern="*.py", recursive=True):
            if "tests" in module_path.parts:
                continue
            yield module_path


def test_checked_in_action_dispositions_reconcile_bidirectionally_with_the_real_census(tmp_path: Path) -> None:
    """The ledger covers every current site and rejects every coverage escape.

    This is deliberately a real-HEAD reconciliation, not a hand-built list of
    expected rows: the census defines the production denominator, while the
    checked-in TOML supplies the independent adjudication.  The mutation probes
    make each rejection arm bite against that actual pair without reimplementing
    either scanner or validator in test code.
    """
    candidates = census("HEAD")
    rows = checked_in_dispositions("HEAD")
    assert candidates, "the production action census is unexpectedly empty"
    assert rows, "the checked-in action-disposition ledger is unexpectedly empty"
    assert validate_dispositions(candidates, rows) == rows

    current = rows[0]
    missing = tuple(row for row in rows if row.key != current.key)
    with pytest.raises(DispositionValidationError, match="missing disposition for current census candidate"):
        validate_dispositions(candidates, missing)

    with pytest.raises(DispositionValidationError, match="duplicate current disposition"):
        validate_dispositions(candidates, (*rows, current))

    stale = replace(current, key=replace(current.key, action_identity=f"{current.key.action_identity}<stale>"))
    replaced_with_stale = tuple(stale if row.key == current.key else row for row in rows)
    with pytest.raises(DispositionValidationError, match="stale disposition has no current census candidate"):
        validate_dispositions(candidates, replaced_with_stale)

    excluded = next(row for row in rows if row.role is DispositionRole.EXCLUDED)
    ungrounded = replace(excluded, exclusion=None)
    replaced_with_ungrounded = tuple(ungrounded if row.key == excluded.key else row for row in rows)
    with pytest.raises(DispositionValidationError, match="requires symbol and enclosing_function grounding"):
        validate_dispositions(candidates, replaced_with_ungrounded)

    malformed = tmp_path / DEFAULT_DISPOSITIONS_PATH.name
    malformed.write_text(
        DEFAULT_DISPOSITIONS_PATH.read_text(encoding="utf-8").replace(
            "[[disposition]]",
            "[[disposition]]\nunrecognized_row = true",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(DispositionValidationError, match="unrecognized field\\(s\\): unrecognized_row"):
        checked_in_dispositions("HEAD", path=malformed)


def test_action_ledger_marks_known_return_and_provenance_clusters_as_producers() -> None:
    """Known action-chain helpers must not regress to syntactic exclusions.

    These are deliberately real census rows rather than stand-in records.  Each
    tuple exercises a distinct transport from a literal to the operator or
    durable action chain: workflow recovery, wizard readiness, auth guidance,
    modelo binding recovery, profile repair, and application/CLI ledger
    ``source_command`` provenance.
    """
    rows = checked_in_dispositions("HEAD")
    by_identity = {(row.key.path, row.key.enclosing_symbol, row.key.action_identity): row for row in rows}
    expected = {
        (
            "src/cadrumo/application/workflow/_profile_health.py",
            "_no_active_profile_next_action",
            "aeat config login NAME",
        ),
        (
            "src/cadrumo/application/wizard/_status.py",
            "_next_wizard_action",
            "aeat config profile create NAME",
        ),
        (
            "src/cadrumo/application/auth/_operator.py",
            "_auth_configure_next_action",
            "aeat config auth configure --provider ",
        ),
        (
            "src/cadrumo/entrypoints/cli/_modelo.py",
            "_bindings_discovery_command",
            "aeat app modelo bindings list --missing",
        ),
        (
            "src/cadrumo/entrypoints/cli/_config/_repair_profile.py",
            "_profile_record_repair_next_action",
            "aeat config repair profile --clear-active --yes",
        ),
        (
            "src/cadrumo/application/ledger/_actions_lifecycle.py",
            "archive_manual_transaction",
            "aeat app ledger archive",
        ),
        (
            "src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py",
            "ledger_archive",
            "aeat app ledger archive",
        ),
    }

    missing = expected - by_identity.keys()
    assert not missing, f"the real census lost action-chain rows: {sorted(missing)}"
    misclassified = {
        identity: by_identity[identity].role.value
        for identity in expected
        if by_identity[identity].role is not DispositionRole.PRODUCER
    }
    assert not misclassified, f"action-chain command literals were not adjudicated as producers: {misclassified}"


def test_action_ledger_exclusions_have_specific_non_action_contexts() -> None:
    """An exclusion needs a non-action role, not absence of a scanner sink.

    The remaining exclusions are static CRUD contract identifiers, MCP resource
    names, or the schema-derived CLI rendering prefix.  They each carry a
    source-specific reason; this rejects the former generic syntactic rationale
    without introducing a fragile numerical baseline.
    """
    rows = checked_in_dispositions("HEAD")
    exclusions = [row for row in rows if row.role is DispositionRole.EXCLUDED]
    assert exclusions, "the non-action static-contract rows were unexpectedly lost"
    reasons = [row.reason for row in exclusions]
    stale_generic = (
        "without an action alias",
        "source reference/example",
        "action-bearing assignment",
        "renderer sink",
    )
    assert not [reason for reason in reasons if any(marker in reason for marker in stale_generic)]
    assert len(reasons) == len(set(reasons)), "each exclusion needs its own source-context reason"

    category_templates: Counter[tuple[str, str]] = Counter()
    for row in exclusions:
        path = row.key.path
        reason = row.reason
        if path == "src/cadrumo/application/operator_surface/_crud_registry.py":
            assert "static cli_path on MutatingNounGroupContract" in reason
            category = "static-crud-contract"
        elif path == "src/cadrumo-harness/src/cadrumo_harness/mcp/_resources.py":
            assert "_DESCRIPTIONS resource label" in reason
            category = "mcp-resource-name"
        elif path == "src/cadrumo-harness/src/cadrumo_harness/mcp/_tools.py":
            assert row.key.action_identity == "aeat "
            assert "fixed textual prefix used by _cli_form" in reason
            category = "cli-render-prefix"
        else:
            pytest.fail(f"exclusion has no approved non-action source context: {row.key.render()}")

        # The source coordinate and quoted identity distinguish individual rows,
        # but neither proves the explanation is semantic.  Strip those volatile
        # values while retaining the exclusion category, then cap one repeated
        # generic template at six: the current CRUD and resource catalogues each
        # have six explicit members.  A seventh needs its own behavior detail,
        # not another copy of a mechanically generated rationale.
        normalized = re.sub(r"^src/[^:]+:\d+ [^:]+: ", "<source>: ", reason)
        normalized = re.sub(r"'[^']*'", "<quoted-identity>", normalized)
        category_templates[(category, normalized)] += 1

    def repeated_template_overflow(
        templates: Counter[tuple[str, str]],
    ) -> dict[tuple[str, str], int]:
        return {(category, template): count for (category, template), count in templates.items() if count > 6}

    over_repeated = repeated_template_overflow(category_templates)
    assert not over_repeated, f"generic exclusion reason template repeated too broadly: {over_repeated}"

    # Prove the normalized-template ratchet is active against a real current
    # exclusion reason, rather than merely observing that today's six-member
    # categories happen to sit below the threshold.
    category, template = next(iter(category_templates))
    repeated = category_templates.copy()
    repeated[(category, template)] = 7
    assert repeated_template_overflow(repeated) == {(category, template): 7}


def _iter_help_entry_commands() -> Iterator[tuple[str, str]]:
    """Yield ``(origin, command)`` for every curated help row on every surface.

    Walks the TYPED documents rather than their rendered JSON, so the
    denominator is structural: every :class:`HelpEntry` reachable from every
    :class:`HelpSurface`. There is no extractor between the surface and the
    check that could narrow it.
    """
    for surface in HelpSurface:
        document = build_help_document(surface)
        for section in document.sections:
            for entry in section.entries:
                yield f"operator help surface {surface.value}", entry.command


def _iter_landing_report_commands() -> Iterator[tuple[str, str]]:
    """Yield ``(origin, command)`` for every arm of the bare-root landing report.

    The landing report is the FIRST surface a new operator meets, and it emits
    its command outside :func:`build_help_document` — so the curated-help walk
    above cannot see it. Each arm is exercised by driving the builder's real
    inputs, because the arms differ precisely in which command they hand over:
    an operator with no profile at all is sent somewhere different from one
    whose selection cannot be resolved.
    """
    yield "landing arm active-profile", build_root_landing_report("operator").command
    yield (
        "landing arm selection-unresolvable",
        build_root_landing_report(None, profile_selected=True).command,
    )
    yield (
        "landing arm registered-none-active",
        build_root_landing_report(None, profile_selected=False, registered_profile_count=1).command,
    )
    yield (
        "landing arm first-run",
        build_root_landing_report(None, profile_selected=False, registered_profile_count=0).command,
    )


# A root-global option may precede the command family (``aeat --format json
# config repair``), which the family-rooted citation grammar cannot parse. The
# family token is where the tree walk begins, so the path is read from there.
_COMMAND_FAMILY_PATTERN = re.compile(r"\b(app|config)\b")


def _advertised_command_failures(command: str, *, origin: str) -> list[str]:
    """Report why ``command`` is not registered, or nothing when it resolves.

    An advertised command falls into exactly one of two domains, and BOTH are
    checked — neither is skipped, because a skipped entry is how this class of
    gate goes quietly vacuous:

    - it names a command family, so every token from that family onward must
      resolve in the live tree;
    - it names no family at all (``aeat --version --detail``), so it is a bare
      root invocation and every option it cites must be a real root option.
    """
    family = _COMMAND_FAMILY_PATTERN.search(command)
    if family is None:
        cited = _OPTION_TOKEN_PATTERN.findall(command)
        if not cited:
            return [
                f"{origin}: advertised command {command!r} names neither a command family nor a root "
                "option, so nothing about it is checked against the live tree"
            ]
        unknown = sorted(option for option in cited if option not in _root_option_names())
        if not unknown:
            return []
        return [
            f"{origin}: advertised command {command!r} cites root option(s) {unknown} the live root callback "
            "does not declare"
        ]

    path = f"aeat {command[family.start() :]}"
    if _count_citations(path) == 0:
        return [
            f"{origin}: advertised command {command!r} yields no parseable citation, so it is "
            "not checked against the live tree at all"
        ]
    return _dead_citations_in(path, origin=origin)


def _unregistered_advertised_commands() -> list[str]:
    """Report every advertised operator command the live tree does not register."""
    return [
        failure
        for origin, command in (*_iter_help_entry_commands(), *_iter_landing_report_commands())
        for failure in _advertised_command_failures(command, origin=origin)
    ]


def test_every_advertised_operator_command_is_registered_in_the_live_tree() -> None:
    """A verb may never be advertised to the operator without being registered.

    The curated help surfaces and the bare-root landing report are the two
    places the application tells an operator which command to run next. Both
    are hand-authored beside a command tree they do not import, so nothing but
    this check binds them together: ``aeat config profile create NAME`` was
    advertised across both while its registration had been dropped, leaving
    first-run profile creation reachable only through the terminal manager.

    The asserted property is registration, not navigability: a curated entry
    may legitimately advertise a browsable GROUP (``aeat app modelo work``),
    and every such group prints its own help when invoked bare. What may never
    happen is a token in an advertised path resolving to nothing.
    """
    failures = _unregistered_advertised_commands()
    assert not failures, "the operator is advertised commands the live CLI tree does not register:\n" + "\n".join(
        failures
    )


def test_the_advertised_command_gate_flags_an_unregistered_verb() -> None:
    """Anti-tautology proof for the advertised-versus-registered check.

    Drives the gate's own classifier over an unregistered verb, over the live
    first-run command that must pass, over a root-global-option form whose
    family sits past the options, and over a bare root invocation that names no
    family. Without this, the gate above would keep reporting green if the
    resolver started accepting everything or the classifier started skipping.
    """
    unregistered = _advertised_command_failures("aeat config profile bootstrap NAME", origin="synthetic")
    assert len(unregistered) == 1, unregistered
    assert "'bootstrap'" in unregistered[0]

    assert not _advertised_command_failures("aeat config profile create NAME", origin="synthetic")
    assert not _advertised_command_failures("aeat --format json config repair", origin="synthetic")
    assert not _advertised_command_failures("aeat --version --detail", origin="synthetic")

    # A root-only form citing an option the root callback does not declare is
    # caught rather than waved through as "no family, nothing to check".
    invented_root_option = _advertised_command_failures("aeat --invented-root-flag", origin="synthetic")
    assert len(invented_root_option) == 1, invented_root_option
    assert "--invented-root-flag" in invented_root_option[0]


def test_operator_help_documents_cite_live_commands() -> None:
    """Every curated help row's ``command`` resolves in the live tree."""
    failures: list[str] = []
    citation_count = 0
    for surface in HelpSurface:
        rendered = build_help_document(surface).model_dump_json()
        citation_count += _count_citations(rendered)
        failures.extend(_dead_citations_in(rendered, origin=f"operator help surface {surface.value}"))
    assert not failures, "\n".join(failures)
    assert citation_count >= 60, (
        f"only {citation_count} command citations found across operator help documents; "
        "the extractor appears blind — the curated surface carried 100+ when this gate landed"
    )


# The runnable-suggestion fields: a string assigned to one of these — as a
# keyword argument (``suggestion=...``) or a dict value (``{"recovery": ...}``)
# — is a command the operator is told to run, so it MUST resolve to a runnable
# leaf, never a bare command group. Other literals (docstrings, ``cli_path=``
# path-root declarations, help-document heading/paragraph prose) name a command
# *family* in reference and legitimately terminate on a group; they stay under
# the dead-token check only.
_RUNNABLE_SUGGESTION_KEYS = frozenset({"suggestion", "recovery", "next_action"})


def _runnable_suggestion_node_ids(tree: ast.AST) -> set[int]:
    """Collect ``id()`` of every string ``Constant`` used as a runnable-suggestion value.

    Matches both ``suggestion="aeat ..."`` keyword arguments and
    ``{"recovery": "aeat ..."}`` / ``{"next_action": "aeat ..."}`` dict
    entries, where the operator is directed to run the cited command verbatim.
    """
    suggestion_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in _RUNNABLE_SUGGESTION_KEYS:
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                suggestion_ids.add(id(node.value))
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and key.value in _RUNNABLE_SUGGESTION_KEYS
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    suggestion_ids.add(id(value))
    return suggestion_ids


def _dotted_name(node: ast.expr) -> tuple[str, ...] | None:
    """Return a dotted reference path when ``node`` is made only of names/attributes."""
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return (*parent, node.attr) if parent is not None else None
    return None


def _canonical_notice_constructor_references(tree: ast.Module) -> tuple[frozenset[str], frozenset[tuple[str, ...]]]:
    """Return local and qualified references to the envelope ``Notice`` model.

    The boundary is import-derived rather than based on a class name alone:
    LLM proposal objects and exception metadata also use ``suggestion``, but
    neither is the envelope ``Notice`` imported from ``core.json_contract``.
    """
    names: set[str] = set()
    qualified: set[tuple[str, ...]] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.endswith("core.json_contract"):
                for imported in node.names:
                    if imported.name in {"Notice", "*"}:
                        names.add(imported.asname or "Notice")
            elif node.module.endswith("core"):
                for imported in node.names:
                    if imported.name == "json_contract":
                        qualified.add((imported.asname or imported.name, "Notice"))
            continue
        if not isinstance(node, ast.Import):
            continue
        for imported in node.names:
            if not imported.name.endswith("core.json_contract"):
                continue
            if imported.asname is not None:
                qualified.add((imported.asname, "Notice"))
            else:
                qualified.add((*imported.name.split("."), "Notice"))

    # A source-level alias is still the same constructor. Repeating until the
    # set stabilises also follows a short chain such as ``Notice2 = Notice1``.
    while True:
        aliases = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            and ((isinstance(node.value, ast.Name) and node.value.id in names) or _dotted_name(node.value) in qualified)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        if aliases <= names:
            break
        names.update(aliases)
    return frozenset(names), frozenset(qualified)


def _is_canonical_notice_constructor(
    call: ast.Call, names: frozenset[str], qualified: frozenset[tuple[str, ...]]
) -> bool:
    """Return whether ``call`` constructs the imported envelope ``Notice``."""
    if isinstance(call.func, ast.Name):
        return call.func.id in names
    return _dotted_name(call.func) in qualified


def _function_parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """Return every declared parameter name without inferring values or types."""
    parameters = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
    if node.args.vararg is not None:
        parameters = (*parameters, node.args.vararg)
    if node.args.kwarg is not None:
        parameters = (*parameters, node.args.kwarg)
    return frozenset(parameter.arg for parameter in parameters)


def _notice_suggestion_transport_failures(module_path: Path) -> list[str]:
    """Report every remaining legacy transport into or out of ``Notice``.

    The migration removes free-text ``suggestion`` from the typed notice
    envelope. This is a structural scan of production source, covering three
    ways that retired transport can survive:

    * a canonical ``Notice(..., suggestion=...)`` producer;
    * a helper parameter named ``suggestion`` that projects it into such a
      ``Notice``; and
    * a direct ``notice.suggestion`` consumer.

    The canonical import check is intentional context: it excludes domain LLM
    suggestion objects and exception ``suggestion`` metadata without a
    path/line allowlist or a fragile current-count baseline.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    notice_names, qualified_notice_names = _canonical_notice_constructor_references(tree)
    relative = module_path.relative_to(_PACKAGE_ROOT.parent).as_posix()
    failures: list[str] = []
    notice_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _is_canonical_notice_constructor(node, notice_names, qualified_notice_names)
    ]

    for call in notice_calls:
        for keyword in call.keywords:
            if keyword.arg == "suggestion":
                failures.append(f"{relative}:{call.lineno}: canonical Notice producer passes suggestion=")

    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if "suggestion" not in _function_parameter_names(function):
            continue
        projects_parameter = any(
            keyword.arg == "suggestion"
            and any(isinstance(value, ast.Name) and value.id == "suggestion" for value in ast.walk(keyword.value))
            for call in ast.walk(function)
            if isinstance(call, ast.Call)
            and _is_canonical_notice_constructor(call, notice_names, qualified_notice_names)
            for keyword in call.keywords
        )
        if projects_parameter:
            failures.append(
                f"{relative}:{function.lineno}: helper {function.name} accepts suggestion "
                "for canonical Notice projection"
            )

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "suggestion"
            and isinstance(node.value, ast.Name)
            and node.value.id == "notice"
        ):
            failures.append(f"{relative}:{node.lineno}: direct notice.suggestion consumer")
    return failures


def _iter_notice_transport_production_modules() -> Iterator[Path]:
    """Yield every real package module, excluding only test code."""
    for module_path in scan_directory(_PACKAGE_ROOT, pattern="*.py", recursive=True):
        if "tests" not in module_path.parts:
            yield module_path


def test_no_legacy_notice_suggestion_transport_survives() -> None:
    """The typed ``Notice.action`` projection owns all executable recovery data."""
    failures: list[str] = []
    for module_path in _iter_notice_transport_production_modules():
        failures.extend(_notice_suggestion_transport_failures(module_path))

    assert not failures, "legacy Notice suggestion transport remains:\n" + "\n".join(failures)


def test_production_string_literals_cite_live_commands() -> None:
    """Every ``aeat app/config`` literal in production modules stays live.

    AST extraction covers exactly the surfaces the pull/--file rule names as
    ungated: write-policy allowlists, ``next_action`` builders, envelope
    builders, and any future suggestion string a feature module grows.
    Comments cannot false-positive (they are not AST constants).

    Two checks per literal: every citation's tokens must resolve (dead-token
    check, all literals), and a literal assigned to a runnable-suggestion field
    (``suggestion=`` / ``recovery`` / ``next_action``)
    must additionally resolve to a runnable LEAF — a bare command group with no
    trailing ``--help`` is not executable verbatim and fails. Reference prose
    (docstrings, ``cli_path=`` path roots, help headings) names a command
    family and legitimately terminates on a group, so the runnable-leaf check
    is scoped to the suggestion fields only.
    """
    failures: list[str] = []
    citation_count = 0
    for module_path in _iter_production_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        relative = module_path.relative_to(_PACKAGE_ROOT.parent).as_posix()
        suggestion_ids = _runnable_suggestion_node_ids(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                citation_count += _count_citations(node.value)
                failures.extend(
                    _dead_citations_in(
                        node.value,
                        origin=f"{relative}:{node.lineno}",
                        require_runnable_leaf=id(node) in suggestion_ids,
                    )
                )
    assert not failures, "\n".join(failures)
    assert citation_count >= 550, (
        f"only {citation_count} command citations found across production string literals; "
        "the extractor appears blind — the scan roots carried 760+ when adapters/ enrolled"
    )


def _iter_locale_leaves(node: LocaleNode, prefix: str = "") -> Iterator[tuple[str, str]]:
    """Yield ``(dotted_key, value)`` for every string leaf in a parsed locale tree.

    Mirrors :meth:`LocaleManager.get_yaml_keys`'s recursive walk but also
    returns the leaf value, which the key-only helper drops.
    """
    if isinstance(node, dict):
        for key, child in node.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from _iter_locale_leaves(child, child_prefix)
    elif node is not None:
        # A null leaf is an absent translation, not a string leaf; the callers
        # below all treat what they receive as citable text.
        yield prefix, node


def test_locale_catalogues_cite_live_commands() -> None:
    """Every ``aeat app/config`` citation inside the four locale catalogues stays live.

    The four shipped locale catalogues (``en``/``es``/``ca``/``hu``) carry the
    same class of operator-facing citations as the error-registry suggestions
    and curated help documents, inside translated suggestion and error text.
    This module's own docstring named the catalogues as the one remaining
    ungated surface; this test closes that gap.

    ``require_runnable_leaf`` is intentionally OFF here, matching
    :func:`test_production_string_literals_cite_live_commands` rather than
    :func:`test_error_registry_suggestions_cite_live_commands`: a locale leaf
    is a mix of runnable suggestions and reference prose (e.g. a legitimately
    bare ``aeat config repair`` citation, a command GROUP that is genuinely
    runnable because its Typer callback executes with no subcommand), so
    scoping the check to the dead-token class only (a token that resolves to
    nothing in the live tree) avoids false-flagging a live bare-group
    citation while still catching a renamed or invented verb.
    """
    manager = LocaleManager(_PACKAGE_ROOT, _LOCALES_DIR)
    # Resolved per language rather than by scanning for "*.yml": a catalogue
    # ships as a shard DIRECTORY, which a non-recursive glob of the root
    # does not see at all.
    locale_paths = [
        source
        for language in SUPPORTED_OUTPUT_LANGUAGES
        if (source := locale_catalogue_source(_LOCALES_DIR, str(language))) is not None
    ]
    assert locale_paths, f"no locale catalogues found under {_LOCALES_DIR}"
    failures: list[str] = []
    citations_by_locale: dict[str, int] = {}
    for path in locale_paths:
        data = manager.load_locale(path)
        counted = 0
        for key, value in _iter_locale_leaves(data):
            if not isinstance(value, str):
                continue
            counted += _count_citations(value)
            failures.extend(_dead_citations_in(value, origin=f"{path.name}:{key}"))
        citations_by_locale[path.name] = counted
    assert not failures, "\n".join(failures)
    # Non-vacuity is asserted as a PROPERTY, not a pinned tally. A count
    # calibrated to the corpus of the day fails whenever content legitimately
    # changes -- retiring the dead `config profile sandbox` leaves dropped it
    # by ~240 -- which trains everyone to edit the constant, and a constant
    # everyone edits detects nothing. Blindness has a shape instead: an
    # extractor that cannot see a catalogue yields nothing for it, and one
    # that half-sees yields an outlier against its siblings, which carry
    # translations of the same prose and so cite comparably.
    blind = sorted(name for name, count in citations_by_locale.items() if count == 0)
    assert not blind, f"no command citations extracted from {blind}; the extractor is blind to those catalogues"

    highest = max(citations_by_locale.values())
    outliers = sorted(name for name, count in citations_by_locale.items() if count * 2 < highest)
    assert not outliers, (
        f"{outliers} carry fewer than half the citations of the richest catalogue "
        f"({citations_by_locale}); the extractor is partially blind or those catalogues lost content"
    )


def test_scanner_flags_the_locale_defects_this_gate_closed() -> None:
    """Anti-tautology proof: the scanner catches the two real defects this gate found.

    Reproduces, as inline synthetic text (not a disk read — the live
    catalogues are already fixed), the exact dead citations that shipped in
    all four locale catalogues (``aeat config profile health``, a command
    that never existed) and in the Hungarian catalogue alone (``aeat config
    doctor``, a retired command path — the sibling locales already cited the
    real ``aeat config repair``). If this test ever fails, the extractor
    would have shipped both defects undetected.
    """
    dead_health = _dead_citations_in(
        "Run `aeat config profile health` and repair or switch the active profile before retrying the Google command.",
        origin="synthetic",
    )
    assert len(dead_health) == 1, dead_health
    assert "'health'" in dead_health[0]

    dead_doctor = _dead_citations_in(
        "Diagnosztikához és helyreállításhoz futtasd aeat config doctor.",
        origin="synthetic",
    )
    assert len(dead_doctor) == 1, dead_doctor
    assert "'doctor'" in dead_doctor[0]

    # The live corrected forms now shipped in the catalogues pass cleanly.
    assert not _dead_citations_in(
        "Run `aeat config profile status` and repair or switch the active profile.",
        origin="synthetic",
    )
    assert not _dead_citations_in(
        "Diagnosztikához és helyreállításhoz futtasd aeat config repair.",
        origin="synthetic",
    )


def test_scanner_flags_a_dead_citation() -> None:
    """Anti-tautology proof: the scanner reports a dead verb and passes a live one.

    If this test ever fails, every green result above is meaningless — the
    resolver would be accepting everything (or seeing nothing).
    """
    dead = _dead_citations_in(
        "Run aeat app modelo capture to refresh the state.",
        origin="synthetic",
    )
    assert len(dead) == 1
    assert "'capture'" in dead[0]

    # A retired multiplex-flag era verb on a live group is also caught.
    dead_leaf = _dead_citations_in("Use aeat app ledger refresh next.", origin="synthetic")
    assert len(dead_leaf) == 1
    assert "'refresh'" in dead_leaf[0]

    # The live canonical forms pass, and argument values past a leaf are tolerated.
    assert not _dead_citations_in("Run aeat app ledger import --file STATEMENT.csv.", origin="synthetic")
    assert not _dead_citations_in("Run aeat app modelo work calculate yourworkunit.", origin="synthetic")
    assert _count_citations("Open an aeat app through the external selector.") == 0


def test_scanner_flags_a_group_citation() -> None:
    """Anti-tautology proof for the group-termination rule.

    A citation that resolves to a command GROUP with no trailing ``--help`` is
    NOT runnable verbatim ('Missing command'); the scanner must flag it under
    ``require_runnable_leaf``. The same path with ``--help`` IS runnable and
    must pass. ``config repair integrity`` is a real group (children:
    ``objects``, ``registry``). A trailing ``.`` terminates the token run so
    the citation resolves exactly to the group.
    """
    group_cited = _dead_citations_in("aeat config repair integrity.", origin="synthetic", require_runnable_leaf=True)
    assert len(group_cited) == 1
    assert "GROUP" in group_cited[0]

    # The runnable help form on the same group is accepted even when strict.
    assert not _dead_citations_in(
        "aeat config repair integrity --help.", origin="synthetic", require_runnable_leaf=True
    )

    # A real runnable leaf under that group is accepted.
    assert not _dead_citations_in(
        "aeat config repair integrity objects.", origin="synthetic", require_runnable_leaf=True
    )

    # Without the strict flag, a bare group citation is tolerated (prose-family
    # references in docstrings legitimately terminate on a group).
    assert not _dead_citations_in("aeat config repair integrity.", origin="synthetic")


def test_scanner_flags_a_dead_option_citation() -> None:
    """Anti-tautology proof for the option-validity rule.

    A runnable suggestion that cites an ``--option`` the resolved leaf does NOT
    declare is flagged; the same leaf's REAL option passes. ``aeat app ledger
    split`` is a real leaf carrying ``--yes`` (the destructive-confirm flag) but
    NOT ``--dry-run`` (only ``remove`` / ``reset`` have a dry-run preview), so a
    suggestion steering the operator to ``... split <id> --dry-run`` sends them
    to a flag the command does not accept. This is the dead-option class the
    verb-only check could never see.
    """
    dead_option = _option_validity_failures(
        "Re-run aeat app ledger split TX123 --dry-run to preview.", origin="synthetic"
    )
    assert len(dead_option) == 1, dead_option
    assert "--dry-run" in dead_option[0]
    assert "split" in dead_option[0]

    # The real ``--yes`` flag on the same leaf passes.
    assert not _option_validity_failures("Re-run aeat app ledger split TX123 --yes to confirm.", origin="synthetic")

    # A leaf that genuinely has ``--dry-run`` (``remove``) accepts it.
    assert not _option_validity_failures(
        "Re-run aeat app ledger remove TX123 --dry-run to preview.", origin="synthetic"
    )

    # Root-global options (``--format`` / ``--language``) are valid on any leaf.
    assert not _option_validity_failures("Run aeat app ledger split TX123 --format json --yes.", origin="synthetic")

    # Option validity is OFF for reference prose (no strict flag), so an abstract
    # mention of an option does not false-positive.
    assert not _dead_citations_in("The aeat app ledger split verb has no --dry-run preview.", origin="synthetic")


# ── suggestions must survive the redaction funnel ──────────────────
#
# The citation checks above prove a suggested command EXISTS. They cannot
# prove it is USABLE, and those are different failures: a suggestion rides
# the notices channel, so it is redacted with the rest of the envelope
# before the operator ever sees it. A verb that resolves is worthless if its
# arguments arrive hashed.
#
# The evidence-extract hint embedded the extracted supplier NIF and reached
# the operator as ``--counterparty-nif sha256:1c9f9632``. It broke for
# natural-person suppliers -- most freelance invoices -- and kept working for
# companies, so the common path was broken and the uncommon one hid it.
#
# The literal scanner above could never have caught it. The extracted
# ``ast.Constant`` was ``"...catalogue create --kind received "``; the NIF
# arrived in a separate ``FormattedValue`` of the same f-string, invisible to
# a check that only reads constants. That is why this scans INTERPOLATIONS.

#: Rule name -> the identifier-name tokens that carry a value that rule redacts.
#:
#: This is the one hand-written half, and it is hand-written because the two
#: vocabularies genuinely differ: the funnel matches VALUE SHAPES, while this
#: gate can only see the NAME of an interpolated expression. The defect that
#: prompted the gate is the proof -- its identifier was ``supplier_tax_id``,
#: which contains no rule name, so deriving tokens from ``default_rules()``
#: alone would have missed the very case this exists to prevent.
#:
#: The coupling is therefore made LOUD rather than left implicit:
#: :func:`test_every_redaction_rule_declares_its_identifier_vocabulary` fails
#: when a rule ships without an entry here, naming it. The funnel gained three
#: arms in one day (NIF/NIE, CIF, then IBAN); a quietly hand-maintained set
#: would have rotted on the first of them.
_REDACTABLE_IDENTIFIER_TOKENS: dict[str, frozenset[str]] = {
    "nif-hash": frozenset({"nif", "nie", "tax_id", "taxid", "dni"}),
    "nif-separated-hash": frozenset({"nif", "nie", "tax_id", "taxid", "dni"}),
    "cif-hash": frozenset({"cif"}),
    "nif-iva-hash": frozenset({"nif_iva", "iva_id", "iva_number"}),
    "iban-hash": frozenset({"iban"}),
    "url-host-only": frozenset({"url", "endpoint", "href"}),
    # Bare ``token`` is deliberately absent. It is ordinary computing
    # vocabulary here -- a period token (``1T``), a registry token, a parse
    # token -- and including it flagged ``registry_token`` on the
    # calculation-preparation hint, which carries a filing period and nothing
    # redactable. The names that actually carry a credential are qualified, so
    # the vocabulary is qualified too. The stated cost: a variable named
    # exactly ``token`` carrying a real bearer value would not be seen. That
    # is a narrower hole than a gate whose false positives get it disabled.
    "token-fingerprint": frozenset({"secret", "credential", "api_key"}),
    "bearer-token-fingerprint": frozenset({"bearer", "access_token", "refresh_token"}),
}


def _redactable_identifier_tokens() -> frozenset[str]:
    """Return every identifier token that marks an interpolation as redactable."""
    tokens: set[str] = set()
    for values in _REDACTABLE_IDENTIFIER_TOKENS.values():
        tokens.update(values)
    return frozenset(tokens)


def _interpolated_names(node: ast.AST) -> Iterator[str]:
    """Yield the identifier name behind each value interpolated into ``node``.

    Recurses through the expression forms a suggestion actually uses. The
    ``or`` fallback shape is not hypothetical -- the original defect was
    ``{draft.supplier_tax_id or '<nif>'}``, an :class:`ast.BoolOp` whose
    redactable operand sits one level down, so a check reading only the
    outermost expression would have passed it.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.FormattedValue):
            for expression in ast.walk(child.value):
                name = (
                    expression.attr
                    if isinstance(expression, ast.Attribute)
                    else expression.id
                    if isinstance(expression, ast.Name)
                    else None
                )
                # A SCREAMING_CASE name is a declared module constant, never a
                # taxpayer's value: the redactable shapes all arrive at runtime.
                # Skipping them is a rule about what a constant IS rather than an
                # exemption for a site, which matters because the alternative was
                # allowlisting ``_NIF_IVA_AUTH_LOCKED_DESCRIPTOR`` -- a label
                # naming AEAT's NIF-IVA service, carrying no identity at all.
                if name is None or name.isupper():
                    continue
                yield name


def _redactable_interpolations_in(tree: ast.AST, *, origin: str) -> list[str]:
    """Report every suggestion in ``tree`` that interpolates a redactable name."""
    tokens = _redactable_identifier_tokens()
    failures: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.keyword) and node.arg in _RUNNABLE_SUGGESTION_KEYS):
            continue
        for name in _interpolated_names(node.value):
            lowered = name.lower()
            matched = sorted(token for token in tokens if token in lowered)
            if matched:
                failures.append(f"{origin}:{node.value.lineno} interpolates {name!r} (matches {', '.join(matched)})")
    return failures


def test_every_redaction_rule_declares_its_identifier_vocabulary() -> None:
    """A new redaction arm must state which identifier names carry its values.

    This is the loud half of the coupling. The gate below can only match
    NAMES, while the funnel matches VALUE SHAPES, so the bridge between them
    cannot be derived -- but it can be forced to stay complete. A fourth arm
    landing without an entry fails HERE, naming the rule, instead of silently
    narrowing what the gate can see.
    """
    from cadrumo.core.redaction import default_rules

    declared = frozenset(_REDACTABLE_IDENTIFIER_TOKENS)
    shipped = frozenset(default_rules())

    assert shipped - declared == frozenset(), (
        f"redaction rules ship without an identifier vocabulary: {sorted(shipped - declared)}. "
        "Add the identifier-name tokens that carry a value this rule redacts, so the "
        "suggestion gate can see them."
    )
    assert declared - shipped == frozenset(), (
        f"identifier vocabulary names rules that no longer ship: {sorted(declared - shipped)}. "
        "Remove the stale entry rather than leaving the gate matching a retired arm."
    )


def test_no_suggestion_interpolates_a_redactable_identifier() -> None:
    """No runnable suggestion may embed a value the funnel would hash.

    This is REGRESSION PREVENTION, not defect discovery: the tree was swept
    when this landed and the evidence hint was the only instance, so a green
    run here is the expected result rather than evidence the scan works.
    :func:`test_the_gate_flags_a_reconstructed_evidence_defect` is what proves
    it can fail.
    """
    scanned = 0
    failures: list[str] = []
    for module_path in _iter_production_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        scanned += 1
        failures.extend(_redactable_interpolations_in(tree, origin=str(module_path)))

    assert scanned > 0, "the module scan matched nothing, so a green result here would be vacuous"
    assert not failures, (
        "a runnable suggestion embeds a value the redaction funnel hashes, so the operator "
        "cannot run it as printed:\n" + "\n".join(failures)
    )


def test_the_gate_flags_a_reconstructed_evidence_defect() -> None:
    """The scanner must fail on the shape that prompted it.

    Reconstructs the retired evidence hint verbatim, including the ``or``
    fallback that puts the redactable operand one level below the
    interpolation. Without this the gate above passes for any tree with no
    suggestions at all, and would keep passing if the extractor broke.
    """
    source = "\n".join(
        (
            "Notice(",
            "    suggestion=(",
            '        "aeat app ledger invoice add --kind received "',
            "        f\"--counterparty-nif {draft.supplier_tax_id or '<nif>'} \"",
            '        f"--invoice-number {draft.invoice_number}"',
            "    ),",
            ")",
        ),
    )

    failures = _redactable_interpolations_in(ast.parse(source), origin="synthetic")

    assert len(failures) == 1, failures
    assert "supplier_tax_id" in failures[0]
    assert "tax_id" in failures[0]


def test_the_gate_does_not_flag_an_ordinary_interpolated_id() -> None:
    """The control: a reference that survives the funnel must pass.

    Work-unit, transaction and invoice ids are content-addressed digests the
    funnel leaves alone by design, and every shipped suggestion embeds one of
    those. A gate that flagged them would be refused on its first run and
    rewritten into an allowlist, which is how this class of check dies.
    """
    source = "\n".join(
        (
            'Notice(suggestion=f"aeat app modelo work calculate {unit.work_unit_id}")',
            'Notice(suggestion=f"aeat app ledger link <tx> --invoice-id {invoice.invoice_id}")',
        ),
    )

    assert _redactable_interpolations_in(ast.parse(source), origin="synthetic") == []
