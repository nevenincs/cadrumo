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


def _guarded_raise_sites(source: str) -> dict[str, list[bool]]:
    """Return, per declared short name, whether each raise sits behind a guard.

    A raise is guarded when its enclosing function mentions a token only a
    non-operator context produces. Enclosing-function scope is deliberately
    coarse: a narrower window would miss an early ``if pytest ...: return`` that
    makes the whole body unreachable for an operator.
    """
    tree = ast.parse(source)
    lines = source.splitlines()
    local = _local_error_names(tree)
    found: dict[str, list[bool]] = defaultdict(list)

    def _walk(node: ast.AST, enclosing: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                body = "\n".join(lines[child.lineno - 1 : (child.end_lineno or child.lineno)])
                _walk(child, body)
                continue
            if isinstance(child, ast.Raise):
                short = _raised_short_name(child, local)
                if short is not None:
                    found[short].append(any(token in enclosing for token in _NON_OPERATOR_TOKENS))
            _walk(child, enclosing)

    _walk(tree, "")
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
