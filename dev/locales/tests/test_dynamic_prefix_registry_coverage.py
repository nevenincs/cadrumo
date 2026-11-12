"""Structural gate: every dynamic translation prefix is registry-covered or allowlisted.

The recurring blind spot this gate closes: a ``tr()`` call site that builds
its key over a *bounded* enumeration at runtime (an f-string like
``f"flows.status.profiles.status.{status}"`` or a concatenation like
``tr("cli.registry.metrics." + key)``) is invisible to the literal-key
scanner. The AST scanner emits a ``<prefix>.*`` namespace marker for such a
site, and the parity check merely asserts that *at least one* concrete
catalogue leaf exists under that prefix. That is not enough: if the concrete
leaves are only ever authored by hand, a catalogue strip (or a new enum member)
silently drops them, and nothing re-materialises them on scaffold. The
bounded-enumeration fix is an :class:`FStringKeyRegistration` in
:mod:`locales.fstring_registry`, whose expanded keys scaffold re-inserts on
every run.

This gate makes that fix non-optional. Every namespace marker the scanner emits
across ``src/cadrumo`` MUST be either:

* **(a) registry-covered** — expanded by at least one
  :class:`FStringKeyRegistration` whose generated concrete keys fall under the
  marker's prefix; or
* **(b) explicitly allowlisted** — declared in :data:`OPEN_ENDED_NAMESPACES`
  below, each entry carrying a stated reason why the value space is not a
  bounded import-time enumeration (a profile fact path, a registry-driven
  predicate id, a runtime metric name, and the like).

A marker in neither set reds this gate with an instructive message naming the
site's prefix and pointing at :mod:`locales.fstring_registry`. The allowlist
ratchets like the lazy-import policy gate: adding an entry is a reviewed edit
that must justify why the namespace cannot be registered.

The incident seen three times is pinned at the bottom: the
status-page setup-state labels expand exactly the ``ProfileSetupState`` values,
and the verdict-factory and required/optional badge keys stay scanner-visible.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from cadrumo.application.overview.home import HOME_ACTION_REASON_CODES
from cadrumo.application.user_profile.validation import PROFILE_VALIDATION_ISSUE_CODES
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.application.wizard.widgets import WIZARD_VALIDATION_REASON_CODES
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.errors.error_codes import ERROR_CONTEXT_LABEL_KEYS
from cadrumo.domain.auth.apoderamientos.catalogue import load_default_catalogue
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState
from dev.docs.terminology_handbook.topics import load_topic_catalogue

from .. import registry_scanner
from ..ast_scanner import scan_namespace_markers, scan_source_tree
from ..fstring_registry import get_registered_keys
from ..locale_nodes import LocaleNode
from ..locale_yaml import locale_catalogue_source
from ..manager import LocaleManager
from ..paths import PRODUCT_SOURCE_DIRS, SRC_DIR
from ..registry_scanner import LocaleRegistryEnumerationError, scan_detail_row_fields
from ..signal_policy import OPEN_ENDED_NAMESPACES
from ..wizard_translation_audit import wizard_descriptor_keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The product source trees the scanner walks. The tooling sits outside the
# packages it measures, so the roots come from the shared checkout derivation.
_SRC_ROOT = SRC_DIR
_LOCALES_ROOT = SRC_DIR / "locales"
_RUNTIME_COMMANDS_ROOT = SRC_DIR.parent / "cadrumo_runtime" / "commands"
_CLIENT_COMMANDS_ROOT = SRC_DIR.parent / "cadrumo_client" / "commands"


def _catalogue_payload(locale: str) -> dict[str, LocaleNode]:
    """Return one committed catalogue's parsed content, whatever shape it ships in.

    Routed through the manager rather than :func:`yaml.safe_load` on a path,
    because a catalogue ships either as a shard DIRECTORY or a flat file and
    only the manager reads both. Reading the path directly is what made these
    two assertions raise instead of check once the catalogues were resharded.
    """
    source = locale_catalogue_source(_LOCALES_ROOT, locale)
    if source is None:
        raise AssertionError(f"no committed catalogue found for locale {locale!r}")
    payload = LocaleManager(src_dir=SRC_DIR, locales_dir=_LOCALES_ROOT).load_locale(source)
    inner = payload.get(locale, payload)
    return inner if isinstance(inner, dict) else payload


# ---------------------------------------------------------------------------
# Open-ended namespace allowlist
# ---------------------------------------------------------------------------
#
# Each entry maps a scanner prefix (the ``<prefix>`` of a ``<prefix>.*`` marker,
# with the trailing ``.*`` stripped) to the reason its value space is NOT a
# bounded import-time enumeration and therefore cannot be materialised by an
# FStringKeyRegistration. A bounded namespace does NOT belong here — register it
# in ``locales/fstring_registry.py`` instead so scaffold re-inserts its keys.
#
# This allowlist ratchets: adding a line is a reviewed edit that must state why
# the namespace is genuinely open-ended.


def _marker_prefix(marker: str) -> str:
    """Return the dotted prefix of a ``<prefix>.*`` namespace marker."""
    return marker.rstrip("*").rstrip(".")


def _registry_covers(prefix: str, registered_keys: frozenset[str]) -> bool:
    """Return True when some registered key falls under ``prefix``.

    A registered key ``K`` falls under ``prefix`` when ``prefix`` is a
    dot-bounded ancestor path of ``K`` (matching both top-level and
    wrapper-wrapped placement), i.e. the registration expands into concrete
    keys inside the marker's namespace.
    """
    needle = f".{prefix}."
    return any(needle in f".{key}." for key in registered_keys)


def test_every_dynamic_prefix_is_registry_covered_or_allowlisted() -> None:
    """No dynamic translation prefix may be bounded-but-unregistered.

    Every ``<prefix>.*`` marker the AST scanner emits across the product source
    roots
    must be registry-covered (an FStringKeyRegistration expands keys under it)
    or explicitly allowlisted in ``OPEN_ENDED_NAMESPACES``. A marker in neither
    set is a bounded dynamic key site with no registration — the exact blind
    spot that has silently dropped locale leaves three times.
    """
    markers = set().union(*(scan_namespace_markers(root) for root in PRODUCT_SOURCE_DIRS))
    assert markers, (
        "scan_namespace_markers(product source roots) returned no markers. The namespace "
        "scanner is broken or misconfigured; fix it rather than passing this gate "
        "vacuously."
    )

    registered_keys = frozenset(get_registered_keys())
    assert registered_keys, (
        "get_registered_keys() returned an empty set. The f-string registry is "
        "broken; fix it rather than passing this gate vacuously."
    )

    uncovered: list[str] = []
    for marker in sorted(markers):
        prefix = _marker_prefix(marker)
        if not prefix:
            continue
        if _registry_covers(prefix, registered_keys):
            continue
        if prefix in OPEN_ENDED_NAMESPACES:
            continue
        uncovered.append(prefix)

    if uncovered:
        detail = "\n".join(
            f"  - {prefix!r}: dynamic tr() prefix with no FStringKeyRegistration and no OPEN_ENDED_NAMESPACES entry"
            for prefix in uncovered
        )
        pytest.fail(
            "Dynamic translation prefix(es) are neither registry-covered nor "
            "allowlisted:\n"
            f"{detail}\n\n"
            "If the tail is a BOUNDED enumeration, add an FStringKeyRegistration "
            "to dev/locales/fstring_registry.py so scaffold "
            "re-materialises every concrete key. If the value space is genuinely "
            "OPEN-ENDED, add a reason-carrying entry to OPEN_ENDED_NAMESPACES in "
            "dev/locales/signal_policy.py stating why it cannot be registered."
        )


def test_allowlist_entries_are_live_and_reasoned() -> None:
    """Every allowlisted prefix is still emitted and carries a real reason.

    Anti-rot for the ratchet: an ``OPEN_ENDED_NAMESPACES`` entry whose marker no
    longer appears in the tree is dead weight and must be removed; an entry with
    an empty reason defeats the purpose of the allowlist.
    """
    markers = set().union(*(scan_namespace_markers(root) for root in PRODUCT_SOURCE_DIRS))
    emitted_prefixes = {_marker_prefix(marker) for marker in markers}
    registered_keys = frozenset(get_registered_keys())

    stale = sorted(prefix for prefix in OPEN_ENDED_NAMESPACES if prefix not in emitted_prefixes)
    assert not stale, (
        f"OPEN_ENDED_NAMESPACES carries prefix(es) the scanner no longer emits; remove the dead entries: {stale}"
    )

    empty_reasons = sorted(prefix for prefix, reason in OPEN_ENDED_NAMESPACES.items() if not reason.strip())
    assert not empty_reasons, f"OPEN_ENDED_NAMESPACES entries carry no reason: {empty_reasons}"

    # An allowlisted namespace that has BECOME registry-covered should graduate
    # out of the allowlist rather than live in both sets.
    redundant = sorted(prefix for prefix in OPEN_ENDED_NAMESPACES if _registry_covers(prefix, registered_keys))
    assert not redundant, (
        "OPEN_ENDED_NAMESPACES prefix(es) are now registry-covered; drop the "
        f"allowlist entry and rely on the registration: {redundant}"
    )


def test_dynamic_family_registrations_match_their_producer_sources() -> None:
    """Every formerly-unbounded family expands from its real producer set."""
    with bundled_indexed_authority().operation() as operation:
        flow = build_setup_flow(operation)
        profile_keys = {
            question.profile_key
            for section in flow.sections
            for question in section.questions
            if question.profile_key is not None
        }
    with bundled_indexed_authority().operation() as operation:
        scope_codes = {scope.code.lower() for scope in load_default_catalogue(operation=operation).scopes}
    topic_slugs = {topic.slug for topic in load_topic_catalogue().topics}
    expected = {
        "cli.config.auth.apoderado.scope": {f"cli.config.auth.apoderado.scope.{value}" for value in scope_codes},
        "errors.context_labels": {f"errors.context_labels.{value}" for value in ERROR_CONTEXT_LABEL_KEYS},
        "profile.keys": {f"profile.keys.{value}" for value in profile_keys},
        "profile.validation": {f"profile.validation.{value}" for value in PROFILE_VALIDATION_ISSUE_CODES},
        "sheets.detalle.headers": {f"sheets.detalle.headers.{value}" for value in scan_detail_row_fields()},
        "topic": {
            *(f"topic.{value}.title" for value in topic_slugs),
            *(f"topic.{value}.body" for value in topic_slugs),
        },
        "tui.home.reason": {f"tui.home.reason.{value}" for value in HOME_ACTION_REASON_CODES},
        "wizard.errors": {f"wizard.errors.{value}" for value in WIZARD_VALIDATION_REASON_CODES},
    }
    registered = frozenset(get_registered_keys())
    for prefix, source_keys in expected.items():
        actual = {key for key in registered if key.startswith(f"{prefix}.")}
        assert actual == source_keys, (
            f"{prefix} registration diverged from its producer source; "
            f"missing={sorted(source_keys - actual)}, extra={sorted(actual - source_keys)}"
        )


def _producer_states() -> set[str]:
    """Return the row states the declaration-list producer can emit and translate."""
    from cadrumo.application.modelo.declaration_summary import DeclarationSummaryState
    from cadrumo.application.modelo.declarations_list import declaration_list_rows, state_words

    producer_module = inspect.getmodule(declaration_list_rows)
    assert producer_module is not None
    producer = ast.parse(inspect.getsource(producer_module))
    states = {member.value for member in DeclarationSummaryState}
    for node in ast.walk(producer):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "state" for t in node.targets):
            states.update(
                c.value for c in ast.walk(node.value) if isinstance(c, ast.Constant) and isinstance(c.value, str)
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "DeclarationListRow"
            and len(node.args) > 3
            and isinstance(node.args[3], ast.Constant)
            and isinstance(node.args[3].value, str)
        ):
            states.add(node.args[3].value)
    # The row's state words branch on the states they say in their own words; only the rest
    # translate a state tail.
    worder = next(
        node for node in ast.walk(producer) if isinstance(node, ast.FunctionDef) and node.name == state_words.__name__
    )
    for node in ast.walk(worder):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            comparison = node.test
            if (
                isinstance(comparison.left, ast.Attribute)
                and isinstance(comparison.left.value, ast.Name)
                and comparison.left.value.id == "row"
                and comparison.left.attr == "state"
                and len(comparison.ops) == 1
                and isinstance(comparison.ops[0], ast.Eq)
                and isinstance(comparison.comparators[0], ast.Constant)
                and isinstance(comparison.comparators[0].value, str)
                and any(isinstance(statement, ast.Return) for statement in node.body)
            ):
                states.discard(comparison.comparators[0].value)
    return states


def _screen_choice_vocabulary() -> dict[str, set[str]]:
    """Return the filter and sort choices the grouped declarations screen declares."""
    from cadrumo.entrypoints.tui.declarations.grouped import GroupedDeclarationsScreen

    screen_module = inspect.getmodule(GroupedDeclarationsScreen)
    assert screen_module is not None
    choices: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(inspect.getsource(screen_module))):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Tuple):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in {"_FILTERS", "_SORTS"}:
                continue
            values: set[str] = set()
            for element in node.value.elts:
                assert isinstance(element, ast.Constant) and isinstance(element.value, str)
                values.add(element.value)
            choices[target.id] = values
    return choices


def test_declaration_list_families_cover_the_live_producer_vocabularies() -> None:
    """A new choice or row state cannot vanish behind a registered wildcard."""
    from cadrumo.application.modelo.declarations_list import (
        DECLARATION_GROUP_LOCALE_KEYS,
        DeclarationListGroup,
        DeclarationListNextStep,
    )
    from cadrumo.application.overview.coverage import CoverageAdviceReason

    states = _producer_states()
    # Every step a row can offer is a member of the application's step vocabulary.
    next_choices = {step.value for step in DeclarationListNextStep}
    assert states and next_choices, "the actual state and action producers must remain discoverable"
    choices = _screen_choice_vocabulary()
    assert choices.keys() == {"_FILTERS", "_SORTS"}, "the actual screen choice vocabulary must remain discoverable"
    assert set(DECLARATION_GROUP_LOCALE_KEYS) == set(DeclarationListGroup)
    assert (
        DECLARATION_GROUP_LOCALE_KEYS[DeclarationListGroup.AEAT_UNLINKED]
        == "workspace.declarations.list.state.aeat_unlinked"
    )
    assert "workspace.declarations.list.group.aeat_unlinked" not in get_registered_keys()
    expected = {
        "advice": {member.value for member in CoverageAdviceReason},
        "filter": choices["_FILTERS"],
        "sort": choices["_SORTS"],
        "state": states,
        "next": next_choices,
    }
    registered = set(get_registered_keys())
    for family, values in expected.items():
        prefix = f"workspace.declarations.list.{family}."
        assert {key for key in registered if key.startswith(prefix)} == {prefix + value for value in values}


def test_declaration_list_enrolment_keeps_open_reason_namespaces_unbounded() -> None:
    """Bounded feature copy must not admit arbitrary optional reason codes."""
    from ..signal_discovery import dynamic_key_families

    bounded = {f"workspace.declarations.list.{family}.*" for family in ("advice", "filter", "sort", "state", "next")}
    open_reasons = {prefix + ".*" for prefix in OPEN_ENDED_NAMESPACES}
    finite, unresolved = dynamic_key_families(bounded | open_reasons)
    assert set(finite) == bounded
    assert set(unresolved) == open_reasons


def test_registry_row_field_enumeration_reports_invalid_source(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """A malformed registry source is a discovery failure, never an empty set."""
    bad_source = tmp_path / "broken.toml"
    bad_source.write_text("[broken\n", encoding="utf-8")
    monkeypatch.setattr(registry_scanner, "bundled_path", lambda *_parts: tmp_path)
    scan_detail_row_fields.cache_clear()
    try:
        with pytest.raises(LocaleRegistryEnumerationError, match="cannot enumerate"):
            scan_detail_row_fields()
    finally:
        scan_detail_row_fields.cache_clear()


# ---------------------------------------------------------------------------
# Seed incidents — the three blind-spot fires already paid for
# ---------------------------------------------------------------------------


def test_status_page_registration_expands_exactly_profile_setup_state() -> None:
    """Incident 3: flows.status.profiles.status.* expands setup-state values.

    The status-page lifecycle labels are built by
    ``f"flows.status.profiles.status.{status.value}"`` and were caught only after
    a live English render. The registration must expand to exactly the
    ``ProfileSetupState`` members — no more (dead leaves), no fewer (silent
    blanks) — so a new lifecycle state cannot ship unlocalised.
    """
    registered_keys = get_registered_keys()
    expanded = {key for key in registered_keys if key.startswith("flows.status.profiles.status.")}
    expected = {f"flows.status.profiles.status.{member.value}" for member in ProfileSetupState}
    assert expanded == expected, (
        "flows.status.profiles.status.* registration is out of sync with "
        f"ProfileSetupState.\n  registered: {sorted(expanded)}\n  expected:   {sorted(expected)}\n"
        "Update the registration in dev/locales/fstring_registry.py."
    )


def test_verdict_factory_keys_remain_scanner_visible() -> None:
    """Incident 1: ValidationVerdict.failed("flows.errors.*") keys stay collected.

    The flow substrate declares its operator-facing message key as the first
    positional argument to ``ValidationVerdict.failed(...)`` — not a tr() call
    or a message_key kwarg — so the scanner needs first-class collection or the
    authored leaves are pruned as orphans. Assert the real verdict keys are in
    the concrete-key scan.
    """
    concrete_keys = scan_source_tree(_SRC_ROOT)
    for key in ("flows.errors.blank_required", "flows.errors.invalid_confirm"):
        assert key in concrete_keys, (
            f"{key!r} is not collected by scan_source_tree — the "
            "ValidationVerdict.failed() first-positional collection regressed "
            "(see locales/ast_scanner.py)."
        )


def test_required_optional_badge_keys_remain_scanner_visible() -> None:
    """Incident 2: the required/optional badge pair stays collected via its constant.

    The badge keys are selected behind a variable ``tr()`` call the scanner
    cannot see, so they are centralised in a ``*_LOCALE_KEYS`` constant that the
    AST constant-registry collector picks up. Assert both keys are in the
    concrete-key scan so a catalogue strip cannot silently drop them.
    """
    concrete_keys = scan_source_tree(_SRC_ROOT)
    for key in ("flows.progress.required", "flows.progress.optional"):
        assert key in concrete_keys, (
            f"{key!r} is not collected by scan_source_tree — the "
            "_*_LOCALE_KEYS constant collection regressed (see "
            "locales/ast_scanner.py._extract_locale_constant_keys)."
        )


def test_wizard_descriptor_keys_remain_discoverable_by_the_manager(committed_locale_manager: LocaleManager) -> None:
    """The wizard flow-help keys stay in the manager's codebase-key set.

    ``_walk_keys`` builds ``cli.config.<flow id>.help`` by interpolation, so no
    source scan can see it and the descriptors are its only declaration. The
    wizard audit asserts the key resolves in every locale; parity independently
    asks whether anything reads it. Without the descriptor discovery path those
    two authorities disagree, and the catalogue entry looks unused while a live
    surface still renders it.
    """
    codebase_keys = committed_locale_manager.get_codebase_keys()
    missing = sorted(key for key in wizard_descriptor_keys() if key not in codebase_keys)
    assert not missing, (
        f"the manager no longer discovers {len(missing)} wizard descriptor key(s): "
        f"{missing} - the descriptor discovery path in manager.get_codebase_keys "
        "regressed, and these keys would read as unused catalogue entries."
    )


def test_no_catalogue_leaf_is_a_self_referencing_placeholder() -> None:
    """A leaf whose value equals its own dotted key is a scaffold echo, repo-wide.

    The catalogue lookup treats ``value == key`` as a miss and falls back to
    humanised English, so a self-referencing placeholder passes the parity and
    honesty gates while rendering untranslated for every operator. The class
    shipped twice: the ``flows.*`` validation leaves were stripped to echoes by
    a scaffold pass, and ``application.wizard.notices.*`` placeholders reached
    the branch before value inspection caught them. The assertion is
    namespace-unscoped on purpose.
    """
    total_leaves = 0
    echoes: list[str] = []
    for locale in ("en", "es", "ca", "hu"):
        payload = _catalogue_payload(locale)
        for key, value in _flatten_leaves(payload.get(locale, payload)):
            total_leaves += 1
            if value == key:
                echoes.append(f"{locale}:{key}")
    assert total_leaves > 1000, "catalogue flattening returned implausibly few leaves - the walk regressed"
    assert not echoes, (
        "self-referencing placeholder leaves (value == key) found; author real "
        "values via `python -m dev.locales set`:\n" + "\n".join(echoes)
    )


def test_no_catalogue_value_carries_a_doubled_apostrophe() -> None:
    """A doubled apostrophe surviving YAML parsing renders literally to the operator.

    ``''`` inside a single-quoted YAML scalar is the correct escape for one
    apostrophe, and the catalogues carry over a thousand of them legitimately.
    The defect is the escape surviving *into the parsed value*, which happens
    when a string is authored by copying single-quoted YAML source into a
    ``locales set`` call so the escape rides along. A raw grep cannot separate
    the two, so the scan runs after parsing. Twelve shipped this way in Catalan,
    one of them also hiding a lost opening quote around a command name.
    """
    total_values = 0
    doubled: list[str] = []
    for locale in ("en", "es", "ca", "hu"):
        payload = _catalogue_payload(locale)
        for key, value in _flatten_leaves(payload.get(locale, payload)):
            if not isinstance(value, str):
                continue
            total_values += 1
            if "''" in value:
                doubled.append(f"{locale}:{key} -> {value}")
    assert total_values > 1000, "catalogue flattening returned implausibly few string values - the walk regressed"
    assert not doubled, (
        "catalogue values carrying a doubled apostrophe after YAML parsing; the "
        "escape belongs in the file, never in the value - re-author via "
        "`python -m dev.locales set`:\n" + "\n".join(doubled)
    )


def _flatten_leaves(node: object, prefix: str = "") -> list[tuple[str, object]]:
    if not isinstance(node, dict):
        return [(prefix, node)]
    leaves: list[tuple[str, object]] = []
    for key, value in node.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        leaves.extend(_flatten_leaves(value, dotted))
    return leaves


#: The complete sanctioned inventory of production call sites that override
#: the output language outside a ctx-scoped settings override: the wizard's
#: pre-command requested-language entry, whose ExitStack spans the command
#: body. The mid-walk activation hook that used to sit beside it went with
#: the interactive walk - there is no walk to re-render mid-way any more.
#: Any new site must be reviewed here with a reason:
#: an override entered outside a ctx scope keeps rendering AFTER the command
#: callback unwinds, which is how a notice renders in the wrong language.
_SANCTIONED_LANGUAGE_OVERRIDE_SITES: frozenset[tuple[str, str]] = frozenset(
    {
        # Non-ctx-scoped (one ExitStack spanning the command body) - the
        # surface the wrong-language bound was proven against:
        ("application/wizard/commands.py", "_enter_requested_output_language"),
        # Context manager around the terminal crash render only: the command
        # context has already closed when a refusal escapes, and the override
        # unwinds before the payload is written.
        ("entrypoints/cli/terminal_errors.py", "_requested_output_language"),
        # Ctx-scoped (entered and unwound inside the command callback's
        # settings scope - safe by construction):
        ("entrypoints/cli/root_commands.py", "root_command"),
        ("client/commands/output.py", "activate_subcommand_output_language"),
        ("client/commands/custody.py", "_pin_render_language_to_target_bucket"),
        ("runtime/commands/profile_admission.py", "bind_runtime_root_context"),
        # Registered reads materialize translated projections within a with-block
        # using the exact request language. ContextVar settings are restored before
        # the result leaves the worker; no CLI callback owns these read scopes.
        ("application/user_profile/view_reader.py", "read_profile_view_page"),
        # The grouped record read words its rows and relations inside one synchronous
        # with-block and returns plain values; the language is restored before it returns.
        ("application/user_profile/record_groups.py", "read_profile_record_groups"),
        ("application/modelo/query_read_operation.py", "_read_requires"),
        ("application/modelo/query_read_operation.py", "read_modelo_readiness"),
        ("application/modelo/wizard_attempt_operation.py", "follow_up"),
        ("application/modelo/wizard_context_operation.py", "discover"),
        ("application/overview/pipeline_operation.py", "_capture_overview_pipeline"),
        ("application/overview/read_operation.py", "_capture"),
        ("application/review/read_operation.py", "_capture"),
        # CSV row refusals are rendered synchronously inside the worker handoff;
        # the invocation language is restored before the batch result returns.
        ("application/ledger/bulk_classify_operation.py", "classify"),
        # The terminal interface's installation area returns the override as a context
        # manager its callers enter only around synchronous rendering, never across a wait,
        # so the first-profile page can word an area before any profile holds a language.
        ("entrypoints/tui/installation/texts.py", "worded_in"),
        # The runtime entrypoint can outlive the command callback while it renders a
        # captured refusal; it restores the request language only inside that render.
        ("runtime/commands/main.py", "emit_error"),
    },
)

#: The ctx-scoped half of the inventory: these sites MUST enter their
#: override through ``ctx.with_resource(...)`` so the override unwinds with
#: the command callback. Pinning WHERE they live is not enough — a site that
#: kept its name but switched to a bare ``with override_settings(...)`` (or
#: an ExitStack outliving the callback) would silently become post-unwind
#: exposed while the location tuple stayed green, which is exactly the drift
#: this gate exists to catch.
_CTX_SCOPED_OVERRIDE_SITES: frozenset[tuple[str, str]] = frozenset(
    {
        ("entrypoints/cli/root_commands.py", "root_command"),
        ("client/commands/output.py", "activate_subcommand_output_language"),
        ("client/commands/custody.py", "_pin_render_language_to_target_bucket"),
        ("runtime/commands/profile_admission.py", "bind_runtime_root_context"),
    },
)

# Synchronous projection reads must finish their language scope before returning
# stored/transported values. Pin the with-block as well as the defining site.
_PROJECTION_SCOPED_OVERRIDE_SITES: frozenset[tuple[str, str]] = frozenset(
    {
        ("application/user_profile/view_reader.py", "read_profile_view_page"),
        # The grouped record read words its rows and relations inside one synchronous
        # with-block and returns plain values; the language is restored before it returns.
        ("application/user_profile/record_groups.py", "read_profile_record_groups"),
        ("application/modelo/query_read_operation.py", "_read_requires"),
        ("application/modelo/query_read_operation.py", "read_modelo_readiness"),
        ("application/modelo/wizard_attempt_operation.py", "follow_up"),
        ("application/modelo/wizard_context_operation.py", "discover"),
        ("application/overview/pipeline_operation.py", "_capture_overview_pipeline"),
        ("application/overview/read_operation.py", "_capture"),
        ("application/review/read_operation.py", "_capture"),
        ("application/ledger/bulk_classify_operation.py", "classify"),
    }
)


def test_language_override_sites_match_the_sanctioned_inventory() -> None:
    """Every production language override in the app, command packages and moved TUI is pinned.

    Command overrides follow callback lifetime, while registered projection
    reads materialize translated values inside their synchronous with-blocks.
    Each admitted site must retain its reviewed scope mechanism.
    """
    import ast

    def _is_language_override_call(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        if isinstance(node.func, ast.Name):
            function_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            function_name = node.func.attr
        else:
            function_name = None
        return function_name == "override_settings" and any(kw.arg == "cadrumo_output_language" for kw in node.keywords)

    found: set[tuple[str, str]] = set()
    ctx_wrapped: set[tuple[str, str]] = set()
    projection_wrapped: set[tuple[str, str]] = set()
    for root in (_CLIENT_COMMANDS_ROOT, _RUNTIME_COMMANDS_ROOT):
        assert root.is_dir(), f"moved locale-aware source root is missing: {root}"
    source_roots = (
        (_SRC_ROOT, ""),
        (_CLIENT_COMMANDS_ROOT, "client/commands/"),
        (_RUNTIME_COMMANDS_ROOT, "runtime/commands/"),
    )
    for source_root, rel_prefix in source_roots:
        for module in scan_directory(source_root, pattern="*.py", recursive=True):
            rel = f"{rel_prefix}{module.relative_to(source_root).as_posix()}"
            if "/tests/" in f"/{rel}" or module.name.startswith("test_"):
                continue
            tree = ast.parse(module.read_text(encoding="utf-8"), filename=rel)
            functions = [func for func in ast.walk(tree) if isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef)]

            def _innermost_site(
                node: ast.AST,
                rel_path: str = rel,
                funcs: list[ast.FunctionDef | ast.AsyncFunctionDef] = functions,
            ) -> tuple[str, str]:
                # Attribute the call to its INNERMOST enclosing function so a
                # nested closure is not double-counted under its parent.
                assert isinstance(node, ast.Call)
                containing = [func for func in funcs if func.lineno <= node.lineno <= (func.end_lineno or func.lineno)]
                if containing:
                    return (rel_path, max(containing, key=lambda f: f.lineno).name)
                return (rel_path, "<module>")

            for node in ast.walk(tree):
                if _is_language_override_call(node):
                    found.add(_innermost_site(node))
                if isinstance(node, ast.With):
                    for item in node.items:
                        if _is_language_override_call(item.context_expr):
                            projection_wrapped.add(_innermost_site(item.context_expr))
                # HOW the ctx-scoped sites enter matters, not only WHERE: record
                # every override call that is a direct argument of a
                # ``*.with_resource(...)`` call, so a ctx site downgrading to a
                # bare ``with override_settings(...)`` loses its wrapped mark.
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "with_resource"
                ):
                    for argument in node.args:
                        if _is_language_override_call(argument):
                            ctx_wrapped.add(_innermost_site(argument))

    assert found == set(_SANCTIONED_LANGUAGE_OVERRIDE_SITES), (
        "production cadrumo_output_language override sites drifted from the "
        f"sanctioned inventory.\nfound: {sorted(found)}\n"
        f"sanctioned: {sorted(_SANCTIONED_LANGUAGE_OVERRIDE_SITES)}\n"
        "A new site must be ctx-scoped or reviewed into the inventory with a reason."
    )
    unwrapped = set(_CTX_SCOPED_OVERRIDE_SITES) - ctx_wrapped
    assert not unwrapped, (
        "ctx-scoped override sites no longer enter through ctx.with_resource(...) - "
        f"they have silently become post-callback-unwind exposed: {sorted(unwrapped)}"
    )
    unscoped_projections = set(_PROJECTION_SCOPED_OVERRIDE_SITES) - projection_wrapped
    assert not unscoped_projections, (
        f"projection language overrides no longer use their bounded with-block: {sorted(unscoped_projections)}"
    )
