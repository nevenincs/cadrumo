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
:mod:`locales._fstring_registry`, whose expanded keys scaffold re-inserts on
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
site's prefix and pointing at :mod:`locales._fstring_registry`. The allowlist
ratchets like the lazy-import policy gate: adding an entry is a reviewed edit
that must justify why the namespace cannot be registered.

The incident seen three times is pinned at the bottom: the
status-page setup-state labels expand exactly the ``ProfileSetupState`` values,
and the verdict-factory and required/optional badge keys stay scanner-visible.
"""

from __future__ import annotations

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.domain.user_profile.values import ProfileSetupState

from .._ast_scanner import scan_namespace_markers, scan_source_tree
from .._fstring_registry import get_registered_keys
from .._paths import SRC_DIR
from ..manager import LocaleManager, locale_catalogue_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The source tree the scanner walks. The tooling sits outside the package it
# maintains, so the root is resolved from the checkout by the shared derivation
# rather than counted from this file's own parents.
_SRC_ROOT = SRC_DIR
_LOCALES_ROOT = SRC_DIR / "locales"


def _catalogue_payload(locale: str) -> dict[str, object]:
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
# in ``locales/_fstring_registry.py`` instead so scaffold re-inserts its keys.
#
# This allowlist ratchets: adding a line is a reviewed edit that must state why
# the namespace is genuinely open-ended.
OPEN_ENDED_NAMESPACES: dict[str, str] = {
    "tui.home.reason": (
        "tui.home.reason.{item.reason_code} -- the reason code travels on a "
        "projected workbench item, not an enum the scanner can import, and the "
        "call site is written to survive that: it renders the key, compares the "
        "result against the key, and falls back to the generic action line when "
        "nothing resolved. An unregistered code degrades to honest copy rather "
        "than to a leaked identifier, so the space cannot be closed at import "
        "time and does not need to be."
    ),
    "profile.keys": (
        "profile.keys.{question.profile_key} — keyed by the wizard question's "
        "profile fact path (application/wizard/compiler.py). The fact-path "
        "space is the open-ended profile schema, not a bounded enum."
    ),
    "profile.validation": (
        "profile.validation.{issue.code} — keyed by profile-readiness issue "
        "codes surfaced at runtime (application/modelo/profile_readiness_gate.py). "
        "Issue codes are raised ad hoc by the readiness gate, not a bounded enum."
    ),
    "errors.context_labels": (
        "errors.context_labels.{key} — keyed by context dict keys in error formatting "
        "(_text_context_label in core/errors/_registry.py). Context keys are open-ended."
    ),
    "cli.registry.metrics": (
        "cli.registry.metrics.{key} — keyed by runtime registry-metric names "
        "(entrypoints/cli/registry.py). Metric keys are computed from live "
        "registry state, not a bounded enum."
    ),
    "cli.config.auth.apoderado.scope": (
        "cli.config.auth.apoderado.scope.{code} — keyed by apoderado scope "
        "catalogue codes (entrypoints/cli/config/_apoderado.py). The scope "
        "vocabulary is loaded from data, not a bounded import-time enum."
    ),
    "sheets.detalle.headers": (
        "sheets.detalle.headers.{row_field} — keyed by binding row-field names "
        "with a tr(..., default=binding.id) fallback "
        "(application/storage/calc_sheets/engine.py). The header space is "
        "binding-driven and the default makes a catalogue leaf optional."
    ),
    "topic": (
        "topic.{slug}.title / topic.{slug}.body — keyed by topic slugs loaded "
        "from the bundled topic data files (core/topics/__init__.py). Slugs are "
        "data-driven, not a bounded import-time enum."
    ),
    "wizard.errors": (
        "wizard.errors.{reason} — keyed by ad-hoc reason tokens passed at "
        "widget-validation call sites (application/wizard/widgets.py). The "
        "reason strings are literals chosen per call site, authored directly in "
        "the catalogues, not a bounded import-time enum."
    ),
}


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

    Every ``<prefix>.*`` marker the AST scanner emits across ``src/cadrumo``
    must be registry-covered (an FStringKeyRegistration expands keys under it)
    or explicitly allowlisted in ``OPEN_ENDED_NAMESPACES``. A marker in neither
    set is a bounded dynamic key site with no registration — the exact blind
    spot that has silently dropped locale leaves three times.
    """
    markers = scan_namespace_markers(_SRC_ROOT)
    assert markers, (
        "scan_namespace_markers(src/cadrumo) returned no markers. The namespace "
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
            "to dev/locales/_fstring_registry.py so scaffold "
            "re-materialises every concrete key. If the value space is genuinely "
            "OPEN-ENDED, add a reason-carrying entry to OPEN_ENDED_NAMESPACES in "
            "this gate stating why it cannot be registered."
        )


def test_allowlist_entries_are_live_and_reasoned() -> None:
    """Every allowlisted prefix is still emitted and carries a real reason.

    Anti-rot for the ratchet: an ``OPEN_ENDED_NAMESPACES`` entry whose marker no
    longer appears in the tree is dead weight and must be removed; an entry with
    an empty reason defeats the purpose of the allowlist.
    """
    emitted_prefixes = {_marker_prefix(marker) for marker in scan_namespace_markers(_SRC_ROOT)}
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
        "Update the registration in dev/locales/_fstring_registry.py."
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
            "(see locales/_ast_scanner.py)."
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
            "locales/_ast_scanner.py._extract_locale_constant_keys)."
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
        # Ctx-scoped (entered and unwound inside the command callback's
        # settings scope - safe by construction):
        ("entrypoints/cli/_root_cli.py", "root_command"),
        ("entrypoints/cli/_common.py", "activate_subcommand_output_language"),
        ("entrypoints/cli/config/custody.py", "_pin_render_language_to_target_bucket"),
        # Scope-closed before return, with nothing rendering afterwards: the
        # override is entered on an ExitStack that unwinds at the end of the
        # function body, and the only work after it is render_outcome(), which
        # is json.dumps over prose the session already produced INSIDE the
        # scope. There is no ctx here to hang the override on -- this is a
        # full-screen session subprocess entrypoint, not a Typer callback -- so
        # the ctx-scoped requirement below deliberately does not cover it.
        ("entrypoints/tui/destination_session.py", "run_requested_destination"),
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
        ("entrypoints/cli/_root_cli.py", "root_command"),
        ("entrypoints/cli/_common.py", "activate_subcommand_output_language"),
        ("entrypoints/cli/config/custody.py", "_pin_render_language_to_target_bucket"),
    },
)


def test_language_override_sites_match_the_sanctioned_inventory() -> None:
    """Every production ``override_settings(cadrumo_output_language=...)`` site is pinned.

    The wrong-language-notice class is bounded to overrides entered outside a
    ctx-scoped settings scope; the sweep that established the bound proved the
    wizard's language machinery is the only such surface. This tripwire keeps
    that proof current: a future command adding its own language override
    reds here and gets reviewed for ctx-scoping instead of silently
    re-introducing post-unwind rendering.
    """
    import ast

    def _is_language_override_call(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", getattr(node.func, "attr", None)) == "override_settings"
            and any(kw.arg == "cadrumo_output_language" for kw in node.keywords)
        )

    found: set[tuple[str, str]] = set()
    ctx_wrapped: set[tuple[str, str]] = set()
    for module in scan_directory(_SRC_ROOT, pattern="*.py", recursive=True):
        rel = module.relative_to(_SRC_ROOT).as_posix()
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


def test_a_locale_key_mapping_declares_its_values_and_not_its_lookup_tokens() -> None:
    """Incident 3: a registry's KEYS are what the runtime selects on, not translations.

    A locale-key mapping is keyed by whatever picks the entry -- an enum value,
    a route identity, a catalogue action id -- and only its values are locale
    keys. Those tokens are dotted often enough to pass for keys:
    ``workbench.home`` is a TUI route and ``operator.profile.edit`` a catalogue
    action, and collecting them made the parity gate demand translations for
    24 identifiers no catalogue should ever have carried.

    The distinction only exists for a mapping. A tuple or list under the same
    naming convention is a flat set of keys and is still collected whole, which
    is the half this must not break.
    """
    from .._ast_scanner import scan_source_text

    source = chr(10).join(
        (
            "_ROUTE_LOCALE_KEYS = {",
            '    "workbench.home": "tui.search.destination.home",',
            '    "operator.profile.edit": "tui.search.action.edit_profile",',
            "}",
            "_FLAT_LOCALE_KEYS = (",
            '    "tui.search.refusal.unknown",',
            ")",
        )
    )

    keys = scan_source_text(source, filename="probe.py")

    assert "tui.search.destination.home" in keys
    assert "tui.search.action.edit_profile" in keys
    assert "tui.search.refusal.unknown" in keys, "a flat registry must still be collected whole"
    assert "workbench.home" not in keys, "a route identity is not a locale key"
    assert "operator.profile.edit" not in keys, "a catalogue action id is not a locale key"


def test_a_row_table_is_confirmed_by_its_key_column_and_not_a_prose_sibling() -> None:
    """Incident 4: which COLUMN reaches the sink decides whether a table holds keys.

    A row table is confirmed by being iterated into a translator. Confirming on
    ANY unpacked name is too loose: the sibling columns are prose by design, so
    a table whose English refusal reaches ``raise ValueError(...)`` was read as
    a locale-key table, and its key column -- canonical COMMAND keys like
    ``ledger.review`` -- was collected as translations to demand.

    The genuine shape must keep working, so both directions are pinned here:
    the key column reaching ``tr`` still confirms.
    """
    from .._ast_scanner import scan_source_text

    prose_sink = chr(10).join(
        (
            '_GUARDS = (("review_action", "ledger.review", "injected action is not canonical"),)',
            "def guard(supplied):",
            "    for attribute, command_key, refusal in _GUARDS:",
            "        if supplied[attribute] != command_key:",
            "            raise ValueError(refusal)",
        )
    )
    key_sink = chr(10).join(
        (
            '_ROWS = (("prefix", "flows.errors.blank_required", "English source"),)',
            "def render():",
            "    for prefix, key, default in _ROWS:",
            "        tr(key)",
        )
    )

    assert "ledger.review" not in scan_source_text(prose_sink, filename="guards.py"), (
        "a command key is not a translation key because its prose sibling reached a raise"
    )
    assert "flows.errors.blank_required" in scan_source_text(key_sink, filename="rows.py"), (
        "a key column reaching tr must still confirm its table"
    )


def test_a_positional_translation_key_needs_every_same_named_helper_to_agree(tmp_path) -> None:
    """Incident 5: resolving a key by parameter NAME collides on function name.

    A command spec fills its help key positionally into a helper defined in
    another module, so the key is invisible without the callee signature.
    Resolving it by bare function name collides: eight ``_leaf`` helpers ship
    here, carrying ``help_key`` at index 3, 1 or 2, and one whose index 1 is
    ``module``. Taking the union collected module import paths as translation
    keys, and the parity gate reported them as missing translations.

    A position counts only when EVERY definition of that name carries a
    translation-key parameter there. Both halves are pinned here: the agreeing
    name resolves, the disagreeing one yields nothing rather than guessing.
    """
    from .._ast_scanner import scan_source_tree

    (tmp_path / "helpers.py").write_text(
        chr(10).join(
            (
                "def option(name, flags, help_key):",
                "    return (name, flags, help_key)",
                "def leaf(token, help_key, handler):",
                "    return (token, help_key, handler)",
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        chr(10).join(
            (
                "def leaf(token, module, parameters):",
                "    return (token, module, parameters)",
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "specs.py").write_text(
        chr(10).join(
            (
                'option("note", ("--note",), "cli.app.ledger.note_help")',
                'leaf("calculate", "cadrumo.entrypoints.cli._work_cli", "handler")',
            )
        ),
        encoding="utf-8",
    )

    keys = scan_source_tree(tmp_path)

    assert "cli.app.ledger.note_help" in keys, "an agreeing helper must resolve its positional key"
    assert "cadrumo.entrypoints.cli._work_cli" not in keys, (
        "definitions that disagree on the position must collect nothing there"
    )

def test_a_local_translator_wrapper_is_followed_but_only_when_it_forwards_its_key(tmp_path) -> None:
    """Incident 6: every TUI surface routes copy through its own boundary helper.

    `def aeat_sync_copy(key, **values): return tr(key, **values)` means the call
    sites read `aeat_sync_copy("tui.aeat_sync.column.area")` and never `tr(...)`.
    The scanner resolved aliased IMPORTS of tr but not a wrapper defined as a
    function, so every key reaching the catalogue through one of these
    boundaries read as an orphan -- 89 of them.

    The shape is deliberately tight, and the negative case is what keeps it so:
    the function must forward its OWN first parameter. A helper that calls tr on
    something else is not a key channel, and its arguments are not keys.
    """
    from .._ast_scanner import scan_source_tree

    (tmp_path / "boundary.py").write_text(
        chr(10).join((
            "def copy(key, **values):",
            "    return tr(key, **values)",
            "def shout(text):",
            '    return tr("ui.fixed.banner") + text',
        )),
        encoding="utf-8",
    )
    (tmp_path / "screen.py").write_text(
        chr(10).join((
            'copy("tui.aeat_sync.column.area")',
            'shout("tui.aeat_sync.column.not_a_key")',
        )),
        encoding="utf-8",
    )

    keys = scan_source_tree(tmp_path)

    assert "tui.aeat_sync.column.area" in keys, "a wrapper forwarding its key must be followed"
    assert "ui.fixed.banner" in keys, "the non-forwarding helper still declares its own literal"
    assert "tui.aeat_sync.column.not_a_key" not in keys, (
        "a helper that does not forward its first parameter is not a key channel"
    )


def test_a_translation_key_kwarg_is_read_through_a_conditional(tmp_path) -> None:
    """Incident 7: a key chosen by a conditional is still a key.

    `empty_key="a.b" if not rows else None` is how a surface says "this label
    depends on state". The collector read only a bare literal, so BOTH arms
    vanished -- and the failure is asymmetric in the worst direction: the key
    that ships is the one behind the condition, so the catalogue looks complete
    on the path a developer happens to exercise and is missing on the other.

    The negative arm matters as much: `None` is not a key, and a value that is
    not a dotted literal must not be invented into one.
    """
    from .._ast_scanner import scan_source_text

    source = chr(10).join((
        "def render(rows):",
        "    return table(",
        '        label_key="flows.progress.rows_present",',
        '        empty_key="flows.progress.rows_absent" if not rows else None,',
        "    )",
    ))

    keys = scan_source_text(source, filename="table.py")

    assert "flows.progress.rows_present" in keys, "a plain key kwarg must be collected"
    assert "flows.progress.rows_absent" in keys, (
        "a key inside a conditional is the key that ships on that branch"
    )
    assert not any(key.endswith("None") for key in keys), "a non-literal arm is not a key"


def test_a_key_registry_is_flow_confirmed_through_a_boundary_wrapper(tmp_path) -> None:
    """Incident 8: the same wrapper blindness as Incident 6, one layer down.

    A dict shaped as a key registry is admitted only when it is proved to
    REACH a translator -- shape alone is deliberately insufficient, because
    same-shaped lookup tables exist that never translate. That proof consulted
    only `tr` and its import aliases, so a registry read through the boundary
    helper every surface is asked to use was never confirmed, and every key in
    it read as an orphan.

    Shape alone must still not be enough, which is what the second registry
    pins: a same-shaped table nothing reads stays unconfirmed even in a module
    that has a wrapper in it.
    """
    from .._ast_scanner import scan_source_tree

    (tmp_path / "boundary.py").write_text(
        chr(10).join(("def screen_copy(key, **values):", "    return tr(key, **values)")),
        encoding="utf-8",
    )
    (tmp_path / "controller.py").write_text(
        chr(10).join((
            "_AVAILABILITY_KEYS = {",
            '    Availability.STALE: "tui.declarations.availability.stale",',
            "}",
            "_ROUTING_TABLE = {",
            '    Notice.RETRY: "notice.machine.retry",',
            "}",
            "def label(value):",
            "    return screen_copy(_AVAILABILITY_KEYS[value])",
        )),
        encoding="utf-8",
    )

    keys = scan_source_tree(tmp_path)

    assert "tui.declarations.availability.stale" in keys, (
        "a registry read through a boundary wrapper reaches the translator and is confirmed"
    )
    assert "notice.machine.retry" not in keys, (
        "shape alone must still not confirm a table nothing reads into a translator"
    )


def test_a_dynamic_namespace_is_read_when_its_prefix_is_selected_from_a_table() -> None:
    """Incident 9: a screen that renders every enum through one helper.

    The namespace rule required the f-string's HEAD to be the dotted literal.
    A workspace that renders each public enum through one helper does not write
    the prefix at the call site -- it declares a table of prefixes, selects one
    by the enum's class name, and appends the member value. The head is then an
    interpolation, so no namespace was declared at all and every key the helper
    builds read as an orphan.

    The tail is an enum member value, so the key space is bounded by the enum
    definition -- the same criterion the wizard namespaces already qualify
    under.

    The negative arm is what keeps the rule from becoming "any f-string that
    starts with a variable": the segment after the interpolation must begin
    with the dot, which is what proves the name is being used AS a dotted
    prefix rather than as ordinary leading text.
    """
    from .._ast_scanner import scan_namespace_markers_in_text

    source = chr(10).join((
        "_LABEL_PREFIXES = {",
        '    "AeatSyncCensusStatus": "tui.aeat_sync.census_status",',
        "}",
        "_GREETINGS = {",
        '    "morning": "cli.greeting.morning",',
        "}",
        "def label(value):",
        "    prefix = _LABEL_PREFIXES.get(type(value).__name__)",
        '    return copy(f"{prefix}.{value.value}")',
        "def greet(slot):",
        "    greeting = _GREETINGS.get(slot)",
        '    return f"{greeting} and welcome"',
    ))

    markers = scan_namespace_markers_in_text(source, filename="screens.py")

    assert "tui.aeat_sync.census_status.*" in markers, (
        "a prefix selected from a declared table and dotted onto is a namespace"
    )
    assert "cli.greeting.morning.*" not in markers, (
        "an interpolation not followed by a dot is not being used as a prefix"
    )


def test_a_column_table_is_read_as_an_attribute_and_confirmed_by_its_key_index() -> None:
    """Incident 10: the screen column table, held as a ClassVar and indexed.

    Three things stood between this table and the scanner, and each alone was
    enough to hide every heading key in it:

    * the row carries a WIDTH, and the shape test demanded all-string rows, so
      the table was never even a candidate;
    * it is read back as `self._COLUMNS`, an attribute, while confirmation
      required a bare name to be iterated;
    * the row is bound whole and the key taken as `column[1]`, while
      confirmation looked for an unpacked name.

    The key-column discipline is unchanged and is what the negative arm pins:
    indexing a PROSE sibling into the translator says nothing about the table,
    exactly as it says nothing when the row is unpacked. A width is no more a
    key than prose is, which is why a non-string cell is carried as a position
    that can never be a key column rather than as grounds to reject the table.
    """
    from .._ast_scanner import scan_source_text

    key_index = chr(10).join((
        "class Screen:",
        "    _COLUMNS = (",
        '        ("date", "tui.ledger.column.date", 10),',
        '        ("amount", "tui.ledger.column.amount", 14),',
        "    )",
        "    def render(self):",
        "        for column in self._COLUMNS:",
        "            yield tr(column[1])",
    ))
    prose_index = key_index.replace("tr(column[1])", "tr(column[0])")

    collected = scan_source_text(key_index, filename="entries.py")

    assert "tui.ledger.column.date" in collected, "a width sibling must not disqualify the table"
    assert "tui.ledger.column.amount" in collected, "the attribute read and the key index both confirm"
    assert "tui.ledger.column.amount" not in scan_source_text(prose_index, filename="entries.py"), (
        "indexing a prose column into the translator does not confirm the table"
    )

    # A sibling need not be a literal at all. The choice table pairs its key
    # with the ENUM member the choice sets, and demanding literal constants
    # rejected that table as surely as demanding strings rejected the one
    # above -- same shape, different sibling.
    enum_sibling = chr(10).join((
        "_CHOICES = (",
        '    (BusinessClassification.BUSINESS, "tui.ledger.classification.business"),',
        '    (BusinessClassification.PERSONAL, "tui.ledger.classification.personal"),',
        ")",
        "for classification, key in _CHOICES:",
        "    table.add_row(tr(key), key=classification.value)",
    ))

    assert "tui.ledger.classification.business" in scan_source_text(enum_sibling, filename="classification.py"), (
        "an enum member sibling must not disqualify the table either"
    )


def test_a_class_attribute_key_is_confirmed_by_the_attribute_the_base_renders(tmp_path) -> None:
    """Incident 11: a screen family names its banner on the subclass.

    The subclass declares `heading = "tui.aeat_sync.census.title"` and the base
    renders `aeat_sync_copy(self.heading)`. That declaration is not a call, a
    suffixed registry constant, or a collection, so every rule in the scanner
    looked straight past it and each subclass banner read as an orphan.

    The negative arm is the one this scanner has already been bitten by: a
    class attribute holding a dotted literal is just as likely to be a route or
    an action id as a translation key, and `workbench.home` is a lookup token,
    not copy. The attribute NAME must be read into a translator for its
    literals to count -- the same bargain the dict and row-table shapes strike.
    """
    from .._ast_scanner import scan_source_tree

    (tmp_path / "boundary.py").write_text(
        chr(10).join(("def screen_copy(key, **values):", "    return tr(key, **values)")),
        encoding="utf-8",
    )
    (tmp_path / "screens.py").write_text(
        chr(10).join((
            "class Base:",
            "    def compose(self):",
            "        yield Static(screen_copy(self.heading))",
            "class Census(Base):",
            '    heading = "tui.aeat_sync.census.title"',
            '    route = "workbench.census.home"',
        )),
        encoding="utf-8",
    )

    keys = scan_source_tree(tmp_path)

    assert "tui.aeat_sync.census.title" in keys, "the attribute the base renders carries a real key"
    assert "workbench.census.home" not in keys, (
        "a class attribute nothing renders is a route or an action id, not copy"
    )


def test_every_translation_key_annotated_parameter_is_declared_a_key_kwarg() -> None:
    """Incident 12: the kwarg set was grown one orphan at a time.

    `_TRANSLATION_KEY_KWARGS` decides which keyword arguments carry a locale
    key, and every entry in it arrived because somebody chased a key that had
    gone missing. That is discovery by casualty: a parameter is only added
    after its keys have already been invisible for a while.

    The codebase states the answer in the type. A parameter annotated
    `TranslationKey` IS a translation key, so the annotation -- not a
    maintainer's memory -- is what the set must agree with. Three names were
    missing when this gate was written (`reason_key`, `short_help_key`,
    `prompt_key`, `confirmation_prompt_key`).

    The set stays hand-written rather than derived, deliberately: it is read at
    five sites and an explicit list is auditable, while a set computed from a
    tree walk hides the surface it admits. The gate is what makes the list
    honest.
    """
    import ast

    from .._ast_scanner import _TRANSLATION_KEY_KWARGS

    def _names_the_translation_key_type(annotation: ast.expr | None) -> bool:
        if isinstance(annotation, ast.Name):
            return annotation.id == "TranslationKey"
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            return annotation.value.split("|")[0].strip() == "TranslationKey"
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            return _names_the_translation_key_type(annotation.left) or _names_the_translation_key_type(
                annotation.right
            )
        return False

    annotated: set[str] = set()
    for module in scan_directory(SRC_DIR, pattern="*.py", recursive=True):
        if "TranslationKey" not in module.read_text(encoding="utf-8"):
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if _names_the_translation_key_type(node.annotation):
                    annotated.add(node.target.id)
            elif isinstance(node, ast.arg) and _names_the_translation_key_type(node.annotation):
                annotated.add(node.arg)

    assert annotated, "no TranslationKey-annotated parameter was found, so this proved nothing"
    undeclared = sorted(annotated - set(_TRANSLATION_KEY_KWARGS))
    assert not undeclared, (
        "these parameters are annotated TranslationKey but are not declared translation-key "
        f"kwargs, so every dotted literal passed to one is invisible to the scanner: {undeclared}"
    )


def test_a_column_table_handed_to_a_shared_fitter_is_still_confirmed() -> None:
    """Incident 13: the table is not iterated where it is declared.

    Every AEAT Sync screen sizes its columns with one shared helper rather than
    repeating the rule, so the table is HANDED OVER::

        _fit_columns(self.app.size.width, self._COLUMNS, self._VALUE_COLUMNS)

    Inside the helper the parameter is iterated in a GENERATOR EXPRESSION and
    each row is translated. Two things hid that: confirmation walked only
    ``for`` statements, and a parameter name said nothing about which table had
    been passed into it.

    A parameter filled by several tables confirms all of them. That is not a
    guess -- one helper serves every screen, so if its parameter's rows reach a
    translator then every table handed to it is translated. Dropping the name
    as ambiguous, which is what a first attempt did, failed the common case for
    being common: only the table that happened to be unique was recovered.

    The key-column discipline is unchanged, and the negative arm holds it: a
    helper that indexes the PROSE column confirms nothing, however many tables
    are handed to it.
    """
    from .._ast_scanner import scan_source_text

    handed_over = chr(10).join((
        "_CENSUS = (",
        '    ("field", "tui.aeat_sync.column.field", 26),',
        ")",
        "_VALUES = (",
        '    ("local_value", "tui.aeat_sync.column.local_value", 16),',
        ")",
        "def _fit(width, standalone, pair=()):",
        "    def _sized(column):",
        "        return column[0], tr(column[1])",
        "    return [_sized(column) for column in standalone]",
        "def render(self):",
        "    return _fit(80, _CENSUS, _VALUES) + _fit(80, _VALUES)",
    ))
    prose_fitter = handed_over.replace("tr(column[1])", "tr(column[0])")

    collected = scan_source_text(handed_over, filename="screens.py")

    assert "tui.aeat_sync.column.field" in collected, "a table handed to the shared fitter is translated"
    assert "tui.aeat_sync.column.local_value" in collected, (
        "a parameter filled by several tables confirms every one of them"
    )
    assert "tui.aeat_sync.column.field" not in scan_source_text(prose_fitter, filename="screens.py"), (
        "a fitter that indexes the prose column confirms nothing"
    )


def test_a_row_table_written_inline_at_the_call_site_is_confirmed() -> None:
    """Incident 14: a column table with no name of its own.

    One screen builds its columns in the argument list rather than binding them
    first. Every rule in this scanner registers a candidate under an assignment
    target, so a table with no name was invisible -- although it is the same
    table, handed to the same fitter, doing the same job as its named siblings
    two screens away.

    It is admitted on exactly the same terms as a named one: registered under a
    synthetic name so the parameter alias and the key-column rule both apply
    unchanged, and confirmed only when that parameter's rows actually reach a
    translator. The negative arm is what proves the terms are the same -- an
    inline table handed to a helper that never translates stays out, so being
    anonymous buys no shortcut past confirmation.
    """
    from .._ast_scanner import scan_source_text

    confirmed = chr(10).join((
        "def _fit(width, standalone):",
        "    return [tr(column[1]) for column in standalone]",
        "def _measure(width, rows):",
        "    return [column[2] for column in rows]",
        "def render(self):",
        "    return _fit(",
        "        80,",
        "        (",
        '            ("declaration", "tui.aeat_sync.column.declaration", 20),',
        '            ("resolution", "tui.aeat_sync.column.resolution", 14),',
        "        ),",
        "    )",
    ))
    never_translated = chr(10).join((
        "def _measure(width, rows):",
        "    return [column[2] for column in rows]",
        "def render(self):",
        "    return _measure(",
        "        80,",
        "        (",
        '            ("declaration", "tui.aeat_sync.column.untranslated", 20),',
        '            ("resolution", "tui.aeat_sync.column.also_untranslated", 14),',
        "        ),",
        "    )",
    ))

    keys = scan_source_text(confirmed, filename="screens.py")

    assert "tui.aeat_sync.column.resolution" in keys, "an inline table reaching the translator is confirmed"
    assert "tui.aeat_sync.column.declaration" in keys, "every key column entry in it comes with it"

    unconfirmed = scan_source_text(never_translated, filename="screens.py")

    assert "tui.aeat_sync.column.untranslated" not in unconfirmed, (
        "an inline table handed to a helper that never translates must stay unconfirmed"
    )
