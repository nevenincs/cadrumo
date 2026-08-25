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

from cadrumo.core import scan_directory
from cadrumo.domain.user_profile import ProfileSetupState

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
    "profile.keys": (
        "profile.keys.{question.profile_key} — keyed by the wizard question's "
        "profile fact path (application/wizard/_compiler.py). The fact-path "
        "space is the open-ended profile schema, not a bounded enum."
    ),
    "profile.validation": (
        "profile.validation.{issue.code} — keyed by profile-readiness issue "
        "codes surfaced at runtime (application/modelo/_profile_readiness_gate.py). "
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
        "catalogue codes (entrypoints/cli/_config/_apoderado.py). The scope "
        "vocabulary is loaded from data, not a bounded import-time enum."
    ),
    "sheets.detalle.headers": (
        "sheets.detalle.headers.{row_field} — keyed by binding row-field names "
        "with a tr(..., default=binding.id) fallback "
        "(application/storage/calc_sheets/_engine.py). The header space is "
        "binding-driven and the default makes a catalogue leaf optional."
    ),
    "topic": (
        "topic.{slug}.title / topic.{slug}.body — keyed by topic slugs loaded "
        "from the bundled topic data files (core/topics/__init__.py). Slugs are "
        "data-driven, not a bounded import-time enum."
    ),
    "wizard.errors": (
        "wizard.errors.{reason} — keyed by ad-hoc reason tokens passed at "
        "widget-validation call sites (application/wizard/_widgets.py). The "
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
        ("application/wizard/_commands.py", "_enter_requested_output_language"),
        # Non-ctx-scoped, and reviewed: the credential screen has no ctx to
        # scope to - it is an inbound TUI adapter, and reaching up into the
        # entrypoint tier for one would invert the dependency direction. It
        # holds the override on an ExitStack for the screen's lifetime so the
        # operator sees the whole page re-render in the language they just
        # picked, which is the point of the chooser.
        #
        # It is bounded against the post-unwind hazard this gate exists
        # for, and the bound is structural rather than a promise. The
        # override is entered on the app's own message-pump task, and a
        # task's context is a copy, so a ContextVar set inside it is not
        # reachable from the caller that started the app - the screen
        # cannot colour the CLI's closing envelope. The stack is also
        # closed in ``RegistrationApp.leave``, which every exit path
        # routes through, but that close is hygiene on top: removing it
        # leaves the behaviour unchanged and every test green, which was
        # measured rather than assumed. The close happens in a handler
        # rather than at teardown because a ContextVar token cannot be
        # released from a context other than the one that created it.
        #
        # The enforced guarantee is the outcome, not the means:
        # ``test_the_chosen_language_does_not_outlive_the_screen`` in
        # ``entrypoints/tui/tests/test_registration_language_switch.py``
        # drives the real screen and fails if the caller's rendering
        # language moved. Swapping this site to a process-global mechanism
        # (an env var plus a settings-cache reset) reds it - that is the
        # substitution that would genuinely leak, and the one worth
        # catching.
        ("entrypoints/tui/secret/registration.py", "_activate_output_language"),
        # Ctx-scoped (entered and unwound inside the command callback's
        # settings scope - safe by construction):
        ("entrypoints/cli/__init__.py", "_root"),
        ("entrypoints/cli/_common.py", "activate_subcommand_output_language"),
        ("entrypoints/cli/_config/_custody.py", "_pin_render_language_to_target_bucket"),
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
        ("entrypoints/cli/__init__.py", "_root"),
        ("entrypoints/cli/_common.py", "activate_subcommand_output_language"),
        ("entrypoints/cli/_config/_custody.py", "_pin_render_language_to_target_bucket"),
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
