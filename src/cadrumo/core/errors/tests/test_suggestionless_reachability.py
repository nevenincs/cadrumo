"""Which registry entries carrying no suggestion can an operator actually reach.

Most of the registry carries no ``default_suggestion``, and that is not by itself
a defect: an entry an operator can never reach correctly carries none. The
live-read access gate is the worked example -- it reads maximally
operator-facing and fires only under pytest, where the only "fix" would have been
to set the live-tests opt-in, which arms real AEAT access. Suggesting anything
there would have been worse than the silence.

So the question worth gating is not how many entries lack a suggestion but which
of them an operator can reach, and nothing in the tree recorded that. This module
decides it from the RAISE SITES rather than from the code's name, and partitions
every suggestion-less entry into exactly one outcome:

``R1`` no direct raise site in shipped code, so the code cannot be emitted at
all. Roughly half are family ROOTS that exist to be subclassed and are never
raised themselves; binding is per-qualname, so a root that is never raised
directly can never render its own entry.

``R2`` every raise site sits behind a guard only a non-operator context enters
(pytest, the live-tests opt-in). Silence is correct.

``R3`` at least one raise site carries no such guard. Treated as reachable.
This is deliberately the conservative default -- CLI, MCP and TUI all route into
the same application, domain and adapter code -- because over-classifying here
merely enlarges the set someone must decide about, while under-classifying would
silently write an entry off as unreachable.

``R4`` the class shares its short name with another declared error, so a site
matched by name alone would be cross-attributed. Reported rather than guessed.

The gate that bites is the last test: the authoring-CANDIDATE set, the reachable
refusals an operator hits with no next step, must equal the reviewed set below.
A new one fails until somebody decides, and a stale one fails when it leaves.
Nothing here asserts a count, and nothing here authors a suggestion: a suggestion
that MISDIRECTS is worse than none, because the agent-operator this CLI targets
follows it.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from functools import cache
from pathlib import Path

import pytest

from .. import ERROR_REGISTRY, ErrorCategory
from .._registry import _DECLARED_CODE_BY_QUALNAME

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]

#: Identifier tokens marking a code path only a non-operator context can enter.
_NON_OPERATOR_TOKENS = ("pytest", "PYTEST_CURRENT_TEST", "live_tests_enabled", "cadrumo_live_tests_enabled")

_NO_RAISE_SITE = "R1_no_direct_raise_site"
_NON_OPERATOR_ONLY = "R2_non_operator_guarded_only"
_OPERATOR_REACHABLE = "R3_operator_reachable"
_AMBIGUOUS = "R4_shared_short_name"

#: Operator-reachable refusals carrying no next step, reviewed and pending an
#: authoring row. Membership is the property "an operator hits this and is told
#: nothing" -- so an entry leaves by gaining a suggestion, never by being muted.
_AUTHORING_CANDIDATES = frozenset(
    {
        "LOCKED_STORAGE_BUCKET_BUSY",
        "LOCKED_STORAGE_LOCK_ACQUISITION",
        "LOCKED_STORAGE_MASTER_KEY_KEYCHAIN",
        "REFUSED_BINDING_PREFILL_TYPE",
        "REFUSED_CALCULATIONS_CASILLA_CONSTRAINT",
        "REFUSED_CLI_BOUNDARY",
        "REFUSED_CLI_LOG_LEVEL_RESOLUTION",
        "REFUSED_CLI_NON_TTY",
        "REFUSED_CONFIG_RESET_CONFIRMATION_REQUIRED",
        "REFUSED_DIAGNOSTIC_MODEL_INVARIANT",
        "REFUSED_EINVOICE_XML_PARSE",
        "REFUSED_FILING_CALCULATE",
        "REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO",
        "REFUSED_FINANCIAL_PROVIDER_INVALID_SOURCE",
        "REFUSED_FINANCIAL_PROVIDER_VALIDATION",
        "REFUSED_FLOW_ANSWER",
        "REFUSED_FLOW_CHECKPOINT",
        "REFUSED_FLOW_NAVIGATION",
        "REFUSED_FLOW_RUN_ABANDONED",
        "REFUSED_FLOW_SUBMIT",
        "REFUSED_FLOW_UNSUPPORTED_CONSOLE",
        "REFUSED_GOOGLE_IMPERSONATION",
        "REFUSED_GOOGLE_NON_INTERACTIVE",
        "REFUSED_GOOGLE_UNSECURED_MODE",
        "REFUSED_GOOGLE_VALIDATION",
        "REFUSED_LLM_CONFIG",
        "REFUSED_LLM_CONSENT",
        "REFUSED_LLM_VALIDATION",
        "REFUSED_M145_COMMUNICATION_RECORD_EXPORT",
        "REFUSED_M145_COMMUNICATION_RECORD_TRANSITION",
        "REFUSED_M145_COMMUNICATION_RECORD_VALIDATION",
        # A record closed by a baja is terminal, but what comes next is not a
        # single verb: filing a fresh alta (resuming), doing nothing (the
        # deregistration was correct and intended), or correcting a wrongly
        # dated declaration (which no verb here supports -- declarations are
        # append-only, never amended) are all live readings, and only the
        # operator knows which. No single suggestion could name the right one
        # without risking the wrong one.
        "REFUSED_MODELO_036_TERMINAL_STATE",
        "REFUSED_MODELO_184_SHARE_SUM",
        "REFUSED_MODELO_210_AGRUPACION_RENTA_ROWS",
        "REFUSED_MODELO_347_THRESHOLD",
        "REFUSED_MODELO_349_COUNTRY_PREFIX_CONTEXT",
        "REFUSED_MODELO_APPLICABILITY_FILTER",
        "REFUSED_MODELO_EXPORT_UNSUPPORTED",
        "REFUSED_MODELO_RECIPIENT_ALREADY_REGISTERED",
        "REFUSED_MODELO_RECIPIENT_DECRYPTION",
        "REFUSED_MODELO_RECIPIENT_NOT_REGISTERED",
        "REFUSED_MODELO_RECIPIENT_PACKAGE_EXPIRED",
        "REFUSED_MODELO_RECIPIENT_PACKAGE_REPLAYED",
        "REFUSED_NO_ACTIVE_PROFILE",
        "REFUSED_OBSERVATION_CASILLA_REFERENCE",
        "REFUSED_OUTBOUND_STORAGE_QUOTA",
        "REFUSED_OUTBOUND_STORAGE_VALIDATION",
        "REFUSED_PENSION_REDUCCION_COMPUTATION",
        "REFUSED_PROFILE_ASSET_VALIDATION",
        "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION",
        "REFUSED_PROFILE_FORAL_REGIME",
        "REFUSED_PROFILE_INVENTORY_VALIDATION",
        "REFUSED_PROFILE_LIFO_FORBIDDEN",
        "REFUSED_PROFILE_LOGOUT_OVERRIDE",
        "REFUSED_PROFILE_NOT_FOUND",
        "REFUSED_PROFILE_PRORRATA_REGISTER_VALIDATION",
        "REFUSED_PROFILE_SCHEMA_VALIDATION",
        "REFUSED_RECONCILIATION_DECLARATION_SOURCE_UNSUPPORTED",
        "REFUSED_RENTA_MARITIME_EXEMPTION_INACTIVE",
        "REFUSED_SOURCE_MESH_INVARIANT",
        "REFUSED_STORAGE_BUCKET_ALREADY_PRESENT",
        "REFUSED_STORAGE_PASSPHRASE_TOO_SHORT",
        "REFUSED_STORAGE_SECRET_ALREADY_EXISTS",
        "REFUSED_STORAGE_UNSECURED_MODE",
        "REFUSED_TABULAR_SOURCE_UNREADABLE",
        "REFUSED_TAXATION_COMPARISON",
        "REFUSED_USER_PROFILE_VALIDATION",
        "REFUSED_WIZARD_UNSUPPORTED_CONSOLE",
        "REFUSED_WORKFLOW_RESUME",
    },
)

#: Categories whose refusal is operator-actionable by construction. An ERROR,
#: FAIL, INTEGRITY or INTERNAL entry reports a defect or a corruption, where a
#: "run this next" line is often not the honest answer, so those are inventoried
#: rather than nominated for authoring.
_ACTIONABLE_CATEGORIES = frozenset({ErrorCategory.REFUSED, ErrorCategory.LOCKED})


@cache
def _short_name_owners() -> dict[str, frozenset[str]]:
    """Map every declared error class's short name to the qualnames sharing it."""
    owners: dict[str, set[str]] = defaultdict(set)
    for qualname in _DECLARED_CODE_BY_QUALNAME:
        owners[qualname.rsplit(".", 1)[1]].add(qualname)
    return {short: frozenset(qualnames) for short, qualnames in owners.items()}


def _local_error_names(tree: ast.AST) -> dict[str, str]:
    """Resolve a module's local names back to the declared class short name.

    Production imports 40-odd error classes under an alias, so a bare short-name
    match would miss every raise made through one and inflate the no-raise-site
    outcome.
    """
    owners = _short_name_owners()
    local: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in owners:
                    local[alias.asname or alias.name] = alias.name
    return local


def _raised_short_name(node: ast.Raise, local: dict[str, str]) -> str | None:
    """Return the declared short name this raise targets, if it targets one."""
    if node.exc is None:
        return None
    target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
    name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else None
    if name is None:
        return None
    if name in local:
        return local[name]
    return name if name in _short_name_owners() else None


_GUARD_IDENTIFIER_COMPONENTS = frozenset({"pytest", "live_tests_enabled", "cadrumo_live_tests_enabled"})
"""Guard tokens matched as a whole underscore-delimited COMPONENT of a
``Name``, ``Attribute``, or called-function identifier appearing inside a
conditional test -- e.g. ``_running_under_pytest()`` carries the component
``pytest``, and ``self.settings.live_tests_enabled`` carries the attribute
``live_tests_enabled`` verbatim. Component matching (split on ``_``, exact
membership) rather than substring matching is what keeps a name like
``pytest_current_test`` -- an ordinary parameter threading a DI seam, not a
guard -- from being confused with one; it shares the component ``pytest``
only when actually used as a guard operand, i.e. inside a test expression this
scan visits in the first place."""

_GUARD_STRING_CONSTANTS = frozenset({"pytest", "PYTEST_CURRENT_TEST"})
"""Guard literals matched only as an exact string ``Constant`` appearing
inside a conditional test or an ``except`` handler's caught-type expression
-- e.g. ``"pytest" in sys.modules`` -- never as a docstring or any other
string elsewhere in the function, because this scan never looks outside
those two expression positions."""

_GUARD_EXCEPT_TYPE_NAMES = frozenset({"AeatLiveReadNotEnabledError"})
"""Exception types whose ``except`` clause is ITSELF the non-operator gate.

Narrow and explicit rather than a general interprocedural resolution: this
is the one class in the tree whose entire purpose is the pytest / live-test
opt-in boundary (the module's own pinned worked example -- see
``test_the_live_read_gate_is_still_the_worked_non_operator_example``), so a
handler naming it catches only what it itself raises only under that same
gate. A handler naming anything else is deliberately NOT treated as guarded:
that would readmit the very over-matching this rewrite removes, just one
hop away from the raise instead of zero."""


def _identifier_carries_guard_component(identifier: str) -> bool:
    """Whether ``identifier``'s underscore-delimited parts contain a guard token."""
    return any(part in _GUARD_IDENTIFIER_COMPONENTS for part in identifier.split("_") if part)


def _expr_is_guard(node: ast.expr) -> bool:
    """Whether ``node`` -- a conditional test, IN ISOLATION -- is itself the guard.

    Walked as its own subtree only. A docstring or an unrelated comment
    elsewhere in the enclosing function is invisible here: neither is part
    of this expression's AST at all, so there is nothing for this scan to
    mismatch against.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and _identifier_carries_guard_component(sub.id):
            return True
        if isinstance(sub, ast.Attribute) and _identifier_carries_guard_component(sub.attr):
            return True
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and sub.value in _GUARD_STRING_CONSTANTS:
            return True
    return False


def _except_type_is_guard(handler_type: ast.expr, local: dict[str, str]) -> bool:
    """Whether an ``except`` clause's caught type(s) resolve to a known guard exception."""
    candidates = handler_type.elts if isinstance(handler_type, ast.Tuple) else [handler_type]
    for candidate in candidates:
        name = (
            candidate.id
            if isinstance(candidate, ast.Name)
            else candidate.attr
            if isinstance(candidate, ast.Attribute)
            else None
        )
        if name is not None and local.get(name, name) in _GUARD_EXCEPT_TYPE_NAMES:
            return True
    return False


def _guarded_raise_sites(source: str) -> dict[str, list[bool]]:
    """Return, per declared short name, whether each raise sits behind a guard.

    Structural, not textual: a raise is guarded when it is nested inside an
    ``if`` whose test expression is itself a guard (:func:`_expr_is_guard`),
    or inside an ``except`` clause whose caught type is itself a guard
    exception (:func:`_except_type_is_guard`) -- climbing every enclosing
    conditional within the SAME function, since an early
    ``if pytest ...: raise`` must still be caught however deep the raise
    sits beneath it. A ``FunctionDef`` boundary resets the accumulated
    guard: a raise inside a nested helper is not "inside" an outer
    function's ``if`` merely by lexical nesting, because the helper only
    runs when something calls it, which this scan cannot see.

    Older revisions matched the guard tokens as a raw substring of the
    WHOLE enclosing function body, which a comment or a docstring mentioning
    "pytest" for an unrelated reason (documenting a test-environment quirk,
    for instance) satisfied just as well as a real guard -- misclassifying
    every raise in that function, guarded or not.
    """
    tree = ast.parse(source)
    local = _local_error_names(tree)
    found: dict[str, list[bool]] = defaultdict(list)

    def _visit(node: ast.AST, guarded: bool) -> None:
        """Dispatch on ``node`` ITSELF, not on its children.

        The earlier shape called itself with a body statement already bound
        to ``node`` and then asked ``ast.iter_child_nodes(node)`` -- the
        statement's own children, never the statement -- which silently
        skipped every ``Raise`` sitting directly in an ``If`` or ``except``
        body. Testing ``node``'s own type first, before ever descending,
        is what keeps a statement from being inspected only as someone
        else's child.
        """
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for stmt in node.body:
                _visit(stmt, False)
            return
        if isinstance(node, ast.If):
            body_guarded = guarded or _expr_is_guard(node.test)
            for stmt in node.body:
                _visit(stmt, body_guarded)
            for stmt in node.orelse:
                _visit(stmt, guarded)
            return
        if isinstance(node, ast.Try):
            for stmt in node.body:
                _visit(stmt, guarded)
            for handler in node.handlers:
                handler_guarded = guarded or (
                    handler.type is not None and _except_type_is_guard(handler.type, local)
                )
                for stmt in handler.body:
                    _visit(stmt, handler_guarded)
            for stmt in (*node.orelse, *node.finalbody):
                _visit(stmt, guarded)
            return
        if isinstance(node, ast.Raise):
            short = _raised_short_name(node, local)
            if short is not None:
                found[short].append(guarded)
            return  # a raise statement's own arguments cannot themselves raise
        for child in ast.iter_child_nodes(node):
            _visit(child, guarded)

    for stmt in tree.body:
        _visit(stmt, False)
    return found


@cache
def _sites_by_short_name() -> dict[str, tuple[bool, ...]]:
    """Scan every shipped module once and collect each error's raise guards."""
    collected: dict[str, list[bool]] = defaultdict(list)
    scanned = 0
    for module_path in sorted(_PACKAGE_ROOT.rglob("*.py")):
        if "tests" in module_path.parts or module_path.name == "conftest.py":
            continue
        try:
            source = module_path.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover - unreadable file in a dirty worktree
            continue
        try:
            found = _guarded_raise_sites(source)
        except SyntaxError:  # pragma: no cover - a peer's mid-edit file
            continue
        scanned += 1
        for short, guards in found.items():
            collected[short].extend(guards)
    assert scanned > 100, f"the shipped-module scan reached only {scanned} files, so every result below is vacuous"
    return {short: tuple(guards) for short, guards in collected.items()}


def _suggestionless_codes() -> dict[str, str]:
    """Return ``code -> qualname`` for every entry carrying no suggestion."""
    without = {code for code, entry in ERROR_REGISTRY.items() if not entry.default_suggestion}
    return {entry.code: qualname for qualname, entry in _DECLARED_CODE_BY_QUALNAME.items() if entry.code in without}


def _classify(qualname: str) -> str:
    """Return the single outcome ``qualname`` falls into."""
    short = qualname.rsplit(".", 1)[1]
    if len(_short_name_owners()[short]) > 1:
        return _AMBIGUOUS
    guards = _sites_by_short_name().get(short, ())
    if not guards:
        return _NO_RAISE_SITE
    return _NON_OPERATOR_ONLY if all(guards) else _OPERATOR_REACHABLE


def test_every_suggestionless_entry_lands_in_exactly_one_outcome() -> None:
    """The partition is total: no entry is left implicitly classified as fine.

    A partition with an unclassified remainder silently classifies that remainder
    as acceptable, which is the failure this row exists to prevent.
    """
    codes = _suggestionless_codes()
    assert codes, "no suggestion-less entries found, so the partition below would be vacuous"

    outcomes = {code: _classify(qualname) for code, qualname in codes.items()}
    known = {_NO_RAISE_SITE, _NON_OPERATOR_ONLY, _OPERATOR_REACHABLE, _AMBIGUOUS}
    unclassified = sorted(code for code, outcome in outcomes.items() if outcome not in known)
    assert not unclassified, f"entries fell outside every declared outcome: {unclassified}"


def test_the_classifier_does_not_collapse_every_entry_into_one_outcome() -> None:
    """Non-degeneracy: a classifier answering the same thing always proves nothing.

    Each of the three substantive outcomes must be populated. If the raise-site
    scan silently stopped seeing anything, every entry would read as
    no-raise-site; if the guard detector broke, nothing would read as
    non-operator-guarded. Either failure lands here.
    """
    outcomes = {_classify(qualname) for qualname in _suggestionless_codes().values()}
    for required in (_NO_RAISE_SITE, _NON_OPERATOR_ONLY, _OPERATOR_REACHABLE):
        assert required in outcomes, f"no suggestion-less entry classified as {required}; the scan is degenerate"


def test_the_guard_detector_separates_a_gated_raise_from_an_open_one() -> None:
    """Anti-tautology proof over the detector itself, independent of registry churn.

    Two synthetic functions raise the SAME real error class; one is reachable only
    under pytest and one is not. A detector that flagged both, or neither, would
    make the outcomes above meaningless while every count still looked plausible.
    """
    source = "\n".join(
        (
            "from cadrumo.core.access_gate._errors import AeatLiveReadNotEnabledError",
            "",
            "def gated(settings):",
            "    if under_pytest() and not settings.live_tests_enabled:",
            "        raise AeatLiveReadNotEnabledError('gated')",
            "",
            "def open_path(settings):",
            "    raise AeatLiveReadNotEnabledError('open')",
        ),
    )

    guards = _guarded_raise_sites(source)["AeatLiveReadNotEnabledError"]

    assert sorted(guards) == [False, True], (
        f"the guard detector did not separate the two raises: {guards}. "
        "Both-true means it flags everything; both-false means it flags nothing."
    )


def test_the_detector_still_recognizes_every_guard_shape_live_in_the_tree() -> None:
    """Positive control: today's real guard shapes are still detected after the rewrite.

    Two distinct shapes coexist in production and each must still resolve to
    non-operator-guarded: a direct attribute check in the ``if`` test itself
    (``core.access_gate``'s own worked example -- the class the module
    docstring reasons from), and an ``except`` clause catching THAT worked
    example's error class one call away (``application.auth``'s login
    refusal, reached through ``AeatAccessGate.require_live_read``). A
    rewrite that only proved the substring false-positive gone, while
    silently losing recognition of either real shape, would misclassify a
    genuinely non-operator-reachable refusal as reachable -- exactly the
    false-negative failure mode the module warns is as harmful as the
    false-positive it was written to fix.
    """
    direct_qualname = next(
        q for q, e in _DECLARED_CODE_BY_QUALNAME.items() if e.code == "REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED"
    )
    except_qualname = next(
        q for q, e in _DECLARED_CODE_BY_QUALNAME.items() if e.code == "REFUSED_AUTH_LOGIN_LIVE_TESTS_DISABLED"
    )
    assert _classify(direct_qualname) == _NON_OPERATOR_ONLY, (
        "the if-test attribute-check guard shape (AeatAccessGate.require_live_read) is no longer recognized"
    )
    assert _classify(except_qualname) == _NON_OPERATOR_ONLY, (
        "the except-clause guard shape (AuthLoginNotEnabledError catching AeatLiveReadNotEnabledError) "
        "is no longer recognized"
    )


def test_a_comment_or_docstring_mentioning_a_guard_token_no_longer_reclassifies_anything() -> None:
    """Regression: pin the exact defect a live comment produced today.

    ``application/workflow/_resume.py`` carried a comment reading "a pytest
    failure line" beside an UNGUARDED raise -- ``prior.aborted_reason in
    _NON_RESUMABLE_REASONS`` has nothing to do with pytest -- and the old
    substring-over-the-whole-function-body scan flagged all four raises in
    that function as non-operator-guarded regardless, moving
    ``REFUSED_WORKFLOW_RESUME`` in and out of the reviewed set between two
    runs of the very test this module exists to keep stable. The synthetic
    case here is the same shape, isolated: a docstring and a trailing
    comment both name every guard token, and an ``if`` guards nothing.
    """
    source = "\n".join(
        (
            "from cadrumo.core.access_gate._errors import AeatLiveReadNotEnabledError",
            "",
            "def refuses(prior):",
            '    """Mentions pytest, live_tests_enabled and PYTEST_CURRENT_TEST here.',
            "",
            "    None of that makes this guarded: cadrumo_live_tests_enabled too.",
            '    """',
            "    if prior.reason in _SOME_REASONS:",
            "        # a pytest failure line, live_tests_enabled, PYTEST_CURRENT_TEST,",
            "        # cadrumo_live_tests_enabled -- still just a comment",
            "        raise AeatLiveReadNotEnabledError('open')",
        ),
    )

    guards = _guarded_raise_sites(source)["AeatLiveReadNotEnabledError"]

    assert guards == [False], (
        f"a docstring/comment mentioning every guard token wrongly reclassified an unguarded raise: {guards}"
    )


def test_the_live_read_gate_is_still_the_worked_non_operator_example() -> None:
    """Fixture anchor: the entry this rule was reasoned from still has the property.

    The pinned code is cited in the module docstring as the reason a missing
    suggestion can be CORRECT. If it ever gains an unguarded raise, that reasoning
    stops holding and the reader must be told, rather than the module continuing
    to cite an example that no longer demonstrates anything.
    """
    code = "REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED"
    entry = ERROR_REGISTRY.get(code)
    assert entry is not None, f"{code} left the registry; the docstring's worked example no longer exists"
    if entry.default_suggestion:
        pytest.fail(f"{code} gained a suggestion {entry.default_suggestion!r}; confirm it is reachable first")

    qualname = next(q for q, e in _DECLARED_CODE_BY_QUALNAME.items() if e.code == code)
    assert _classify(qualname) == _NON_OPERATOR_ONLY, (
        f"{code} is no longer raised only behind a non-operator guard, so it can now reach an operator "
        "with no next step; decide whether it warrants a suggestion"
    )


def test_the_reachable_refusals_needing_a_decision_are_the_reviewed_set() -> None:
    """The gate that bites: a newly reachable refusal must be decided, not defaulted.

    Membership is derived from the live registry every run, so an entry joins by
    becoming an operator-reachable refusal with no next step and leaves by gaining
    one. Both directions fail loudly. No count is asserted: the property is the
    set's identity, and a tally would have to be edited on every legitimate
    change until nobody read it.
    """
    codes = _suggestionless_codes()
    derived = frozenset(
        code
        for code, qualname in codes.items()
        if _classify(qualname) == _OPERATOR_REACHABLE and ERROR_REGISTRY[code].category in _ACTIONABLE_CATEGORIES
    )

    appeared = sorted(derived - _AUTHORING_CANDIDATES)
    resolved = sorted(_AUTHORING_CANDIDATES - derived)
    assert not appeared, (
        "operator-reachable refusal(s) reach an operator with no next step and nobody has decided about them: "
        f"{appeared}. Either author a suggestion naming a runnable verb, or add the code here with the reason "
        "no single correct next step exists. Never add one that misdirects: the agent-operator follows it."
    )
    assert not resolved, (
        f"reviewed entries no longer qualify: {resolved}. Remove them from the reviewed set — they either gained "
        "a suggestion, changed category, or stopped being reachable, and a stale entry mutes a real one later."
    )
