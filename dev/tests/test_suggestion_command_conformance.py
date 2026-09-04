"""Live CLI citation and production-action-observation conformance gate.

The CLI's instructive surface is wider than ``--help`` and the how-to docs:
the curated operator help documents, production prose, and the four locale
catalogues all cite ``aeat app ...`` / ``aeat config ...`` invocations. A verb
rename that misses one leaves the operator with a dead instruction.

This gate converts that hand-sweep obligation into CI enforcement. It walks
the REAL Click tree (``typer.main.get_command`` over the live Cadrumo app —
no mocks, no fixture trees) and resolves every cited command path from:

- the curated operator help documents (root / config / app surfaces);
- every string literal in production modules under ``cadrumo.adapters``,
  ``cadrumo.application``, ``cadrumo.core.errors``, and ``cadrumo.entrypoints``
  (AST-extracted, so comments cannot false-positive).

The four locale catalogues (``en``/``es``/``ca``/``hu``) carry the same class
of citations inside translated operator text and are the natural fourth
sweep. This was tracked as a follow-up when the gate first landed (the
catalogues carried three locale-divergent dead citations at that time); it is
now closed by :func:`test_locale_catalogues_cite_live_commands`, which walks
every string leaf of every catalogue through the same live-tree resolver.
Landing that sweep caught three real dead citations shipped across the
catalogues: all four locales cited a never-existing ``aeat config profile
health`` for the Google OAuth profile-repair instruction (corrected to the
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
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import cast

import click
import pytest

from cadrumo.application.operator_surface.help import build_help_document, build_root_landing_report
from cadrumo.application.operator_surface.help_models import HelpSurface
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.json_contract import EnvelopeStatus
from cadrumo.core.operator_action_enums import ActionEvidenceProvenance
from cadrumo.entrypoints.cli._verb_input_schema import DECLARED_UNIMPLEMENTED_SURFACES
from cadrumo.tests.cli_runner import cadrumo_click_command

from .._paths import REPO_ROOT
from ..agent_eval._action_coverage import LeafConditionScenario, production_leaf_condition_scenario_matrix
from ..agent_eval._models import ExitCodeScenario, ObservedProductionActionAssertion, observe_production_action
from ..agent_eval._runner import check_exit_code_scenario
from ..locales.manager import LocaleManager, LocaleNode, locale_catalogue_source

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
    so the operator-instruction surface validates cited ``--option`` tokens against the
    same authoritative live-parameter set the how-to docs are checked against.
    """
    names: set[str] = set()
    for param in command.params:
        if getattr(param, "param_type_name", None) == "option":
            names.update(param.opts)
            names.update(param.secondary_opts)
    return frozenset(names)


# An ``--option`` / ``-o`` token in operator-instruction text. ``--help`` is always valid
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
    so an operator instruction can be validated against the resolved command's parameter
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

    When ``require_runnable_leaf`` is set (the operator-instruction surface:
    curated help ``command`` fields,
    where the cited string IS the command the operator is told to run), a
    citation that resolves cleanly to a command GROUP with no trailing
    ``--help`` is ALSO a failure: a group is not executable verbatim
    (``Missing command``), so the operator is sent to a non-runnable line.
    ``<group> --help`` IS runnable and is accepted. The flag is OFF for the
    broad production-string-literal scan, where a bare ``aeat config google``
    is overwhelmingly a prose/docstring reference to a command *family*, not a
    runnable instruction, and group-termination is legitimate there.

    The flag ALSO gates option validity: under ``require_runnable_leaf`` every
    cited ``--option`` must be a real parameter of the resolved command (or a
    root-global option), so an instruction citing an option the target verb
    does not declare (e.g. ``... split <id> --dry-run`` where ``split`` carries
    only ``--yes``) is flagged. Option validity is scoped to runnable
    instructions because reference prose can legitimately mention an option in
    the abstract; a runnable instruction is the line the operator pastes
    verbatim.
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
                "append a child command or cite '... --help' so the instruction runs verbatim"
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


def test_production_string_literals_cite_live_commands() -> None:
    """Every ``aeat app/config`` literal in production modules stays live.

    The gate reads the live Click tree as the sole command authority. Comments
    cannot false-positive because the source scan visits AST string constants,
    while command-family prose may legitimately end at a group.
    """
    failures: list[str] = []
    citation_count = 0
    for module_path in _iter_production_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        relative = module_path.relative_to(_PACKAGE_ROOT.parent).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                citation_count += _count_citations(node.value)
                failures.extend(
                    _dead_citations_in(
                        node.value,
                        origin=f"{relative}:{node.lineno}",
                    )
                )
    assert not failures, "\n".join(failures)
    assert citation_count >= 550, (
        f"only {citation_count} command citations found across production string literals; "
        "the extractor appears blind — the scan roots carried 760+ when adapters/ enrolled"
    )


def _precondition_observed_from_live_profile(
    coverage: LeafConditionScenario,
) -> ObservedProductionActionAssertion:
    """Build an application verdict from one live profile row, then observe it through the action boundary.

    The builder resolves the registered modelo profile itself.  Argument names
    come from the resolved catalogue declaration, so this gate contains no
    scenario-owned action identifier, recovery command, or binding schema.
    """
    from cadrumo.application.modelo.preconditions import build_modelo_precondition_failure_for_scenario

    resolved_action = coverage.profile.resolved_action
    action_argument_values = (
        None
        if resolved_action is None
        else {
            specification.argument_name: f"s45-observation-{specification.argument_name}"
            for specification in resolved_action.declaration.argument_specifications
        }
    )
    verdict = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=coverage.subject_leaf_key,
        scenario_id=coverage.scenario_id,
        evidence_id="agent_eval.s45.live_profile",
        evidence_values={"scenario": coverage.scenario_id},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        action_argument_values=action_argument_values,
    ).verdict
    return observe_production_action(coverage, verdict)


def _assert_complete_bijective_observation_join(
    matrix: tuple[LeafConditionScenario, ...],
    observations: tuple[ObservedProductionActionAssertion, ...],
) -> None:
    """Require the declaration set and observed identities to match exactly."""
    declared = {coverage.identity for coverage in matrix}
    observed = tuple(assertion.leaf_condition_scenario for assertion in observations)
    duplicate_observations = sorted(identity for identity in set(observed) if observed.count(identity) > 1)
    missing = sorted(declared - set(observed))
    undeclared = sorted(set(observed) - declared)

    assert not duplicate_observations, f"observed identities duplicate live declarations: {duplicate_observations}"
    assert not missing, f"live declarations lack an observation: {missing}"
    assert not undeclared, f"observations lack a live declaration: {undeclared}"


def test_live_action_declarations_and_observations_join_bidirectionally() -> None:
    """Every declaration has one successful observation, and no extras survive."""
    matrix = production_leaf_condition_scenario_matrix().rows
    observations = tuple(_precondition_observed_from_live_profile(coverage) for coverage in matrix)

    assert matrix, "the production leaf-condition matrix is unexpectedly empty"
    assert all(assertion.passed for assertion in observations)
    _assert_complete_bijective_observation_join(matrix, observations)


def test_live_action_observation_join_rejects_missing_duplicate_and_undeclared_rows() -> None:
    """Mutation probes make every arm of the declaration-to-observation join bite."""
    matrix = production_leaf_condition_scenario_matrix().rows
    observations = tuple(_precondition_observed_from_live_profile(coverage) for coverage in matrix)
    first = observations[0]
    undeclared = first.model_copy(
        update={
            "leaf_condition_scenario": (
                first.leaf_condition_scenario[0],
                first.leaf_condition_scenario[1],
                f"{first.leaf_condition_scenario[2]}.s45-undeclared",
            ),
        }
    )

    with pytest.raises(AssertionError, match="lack an observation"):
        _assert_complete_bijective_observation_join(matrix, observations[1:])
    with pytest.raises(AssertionError, match="identities duplicate"):
        _assert_complete_bijective_observation_join(matrix, (*observations, first))
    with pytest.raises(AssertionError, match="lack a live declaration"):
        _assert_complete_bijective_observation_join(matrix, (*observations, undeclared))


def test_runner_observes_every_live_no_recovery_outcome() -> None:
    """The runner observes every live no-recovery outcome through its declared contract."""
    from cadrumo.application.modelo.preconditions import build_modelo_precondition_failure_for_scenario

    no_recovery_rows = tuple(
        coverage
        for coverage in production_leaf_condition_scenario_matrix().rows
        if coverage.profile.declaration.action is None
    )
    assert no_recovery_rows, "the live matrix no longer declares a terminal no-recovery outcome"

    runner_observations: list[ObservedProductionActionAssertion] = []
    for coverage in no_recovery_rows:
        verdict = build_modelo_precondition_failure_for_scenario(
            subject_leaf_key=coverage.subject_leaf_key,
            scenario_id=coverage.scenario_id,
            evidence_id="agent_eval.s45.runner_no_recovery",
            evidence_values={"scenario": coverage.scenario_id},
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        ).verdict
        result = check_exit_code_scenario(
            ExitCodeScenario(
                name=f"s45-{coverage.scenario_id}",
                command=coverage.subject_leaf_key,
                expected_exit_code=1,
                tool_result_status=EnvelopeStatus.ERROR,
                leaf_condition_scenario=coverage.identity,
            ),
            exit_code=1,
            envelope={"command": coverage.subject_leaf_key, "status": EnvelopeStatus.ERROR.value, "notices": []},
            precondition_verdict=verdict,
        )
        assert result.passed, result.failures
        runner_observations.append(result.production_action_assertion)

    _assert_complete_bijective_observation_join(no_recovery_rows, tuple(runner_observations))


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
    same class of operator-facing citations as curated help documents, inside
    translated operator and error text.
    This module's own docstring named the catalogues as the one remaining
    ungated surface; this test closes that gap.

    ``require_runnable_leaf`` is intentionally OFF here, matching
    :func:`test_production_string_literals_cite_live_commands`: a locale leaf
    is a mix of runnable instructions and reference prose (e.g. a legitimately
    bare ``aeat config repair`` citation), so scoping the check to the
    dead-token class only (a token that resolves to nothing in the live tree)
    avoids false-flagging a live bare-group citation while still catching a
    renamed or invented verb.
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

    A runnable operator instruction that cites an ``--option`` the resolved leaf does NOT
    declare is flagged; the same leaf's REAL option passes. ``aeat app ledger
    split`` is a real leaf carrying ``--yes`` (the destructive-confirm flag) but
    NOT ``--dry-run`` (only ``remove`` / ``reset`` have a dry-run preview), so a
    instruction steering the operator to ``... split <id> --dry-run`` sends them
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
