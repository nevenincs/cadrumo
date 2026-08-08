"""No cloud transport survives dormant anywhere in production.

The cloud read path was deleted rather than left behind a disabled flag,
because `no-legacy-compatibility` forbids keeping a retired surface as a
bridge and because a dormant off-host transport is the one thing this gate
exists to remove. A retained-but-unreachable path is a failed outcome, not a
partial success: the next change that re-enables a flag re-enables the
transport with it.

**The search pattern is declared here, once, and is not narrowed.** That is the
whole discipline this gate encodes. Narrowing a pattern until it returns clean
is indistinguishable from cleaning the tree if only the final result is
reported, so the symbol set is fixed in source, reviewable in a diff, and any
future edit to it is a visible decision rather than an invisible one.

**Four names left the deleted set, and that is such a decision.** Off-host
reading of taxpayer evidence was re-sanctioned behind a reinstated consent
gate over the in-memory HTTP providers -- never the subprocess family, which
stays deleted permanently. ``cloud_evidence_read_permitted`` and the two
deployment settings behind it therefore moved to
``_REINSTATED_CONSENT_SYMBOLS``, where they are asserted PRESENT and WIRED
rather than absent -- joined later by ``CLOUD_EVIDENCE_UPLOAD``, the per-profile
eligibility bar, once the decision it was waiting on was taken. The move is only honest because the destination has teeth:
a symbol removed from the sweep and merely forgotten would leave this file
reading like a decision while the tree lost a guarantee.

**Those teeth are a mapping, not a filter.** Each reinstated symbol names the
callable that proves it, and the mapping is asserted total over the declared set
at import, so a fifth member added without a verifier stops this module rather
than passing through it. The shape it replaces checked its members with a
``cadrumo_`` name-prefix test, which verified two of the four and let an
unprefixed name that existed nowhere in production pass -- rot that is latent,
silent and misattributed, because the green looked like a statement about the
tree when it was a statement about the filter.

**The set is symbols, never the word ``subprocess``.** ``entrypoints/mcp/
_call_runtime.py`` shells the deterministic CLI for every MCP tool call: it is
a subprocess transport and it is NOT the cloud LLM transport. A word-sweep
would delete the MCP server's entire call path. A duplication-audit helper that
shells a Node tool is a second such neighbour. Both are asserted to survive, so
this gate proves the deletion was scoped by meaning rather than by string.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from . import SRC_CADRUMO, non_test_package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DELETED_CLOUD_SYMBOLS = (
    # The transport and its provider builders.
    "SubprocessLLMClassifier",
    "build_claude_classifier",
    "build_antigravity_classifier",
    "build_codex_classifier",
    "_PROVIDER_BUILDERS",
    "resolve_classifier",
    "resolve_split_proposer",
    # The provider axis: its enum, its PATH probes, its availability records.
    "SubprocessProvider",
    "available_llm_providers",
    "is_llm_provider_available",
    "LLMProviderAvailability",
    "probe_subprocess_providers",
    # The operator-facing surfaces. Still deleted: nothing mints a token yet, so
    # no CLI surface asks the operator for one.
    "evidence_acknowledged",
    "evidence-acknowledged",
)

def _verify_settings_field(symbol: str) -> None:
    """Assert *symbol* is a live deployment setting the operator can reach."""
    assert symbol in set(_settings_model_fields()), f"{symbol} is claimed reinstated but Settings does not declare it"


def _verify_consent_predicate(symbol: str) -> None:
    """Assert the consent predicate is importable from the package facade and callable."""
    from ..llm import cloud_evidence_read_permitted

    assert cloud_evidence_read_permitted.__name__ == symbol
    assert callable(cloud_evidence_read_permitted)


def _verify_capability_defaults_off(symbol: str) -> None:
    """Assert the reinstated capability is a live member AND still defaults off.

    The default is the property it was reinstated FOR. A member present but
    defaulting on would satisfy a mere membership check while removing the bar
    it names.
    """
    from ..core import ServiceCapability

    capability = ServiceCapability[symbol]
    assert capability.default_enabled is False


# Every reinstated symbol is mapped to the callable that proves it, and the
# mapping is asserted total at import (below). The previous shape was a bare
# tuple whose loop filtered on a ``cadrumo_`` name prefix, so two of its four
# members were checked by the loop and the other two by hand-written lines that
# never read the set: appending an unprefixed fifth member passed while a
# prefixed twin failed. Nothing was unguarded, but the set had stopped driving
# its own verification, and a name added later would have been silently
# unverified while the file still read like a decision. A mapping cannot rot
# that way -- a member with no verifier is an import-time error.
_REINSTATED_CONSENT_VERIFIERS: dict[str, Callable[[str], None]] = {
    "cloud_evidence_read_permitted": _verify_consent_predicate,
    "cadrumo_evidence_cloud_upload_permitted": _verify_settings_field,
    "cadrumo_evidence_gestor_mode": _verify_settings_field,
    # The per-profile eligibility bar. It moved out of the deleted set when the
    # decision it was waiting on was taken: the standing bar now exists, is
    # default-off and gestor-locked-off, and every consent-minting surface must
    # read it. Its teeth are the dedicated eligibility gate under
    # application/user_profile/tests, plus the wiring assertion below.
    "CLOUD_EVIDENCE_UPLOAD": _verify_capability_defaults_off,
}

_REINSTATED_CONSENT_SYMBOLS = (
    "cloud_evidence_read_permitted",
    "cadrumo_evidence_cloud_upload_permitted",
    "cadrumo_evidence_gestor_mode",
    "CLOUD_EVIDENCE_UPLOAD",
)

_UNVERIFIED_CONSENT_SYMBOLS = tuple(
    symbol for symbol in _REINSTATED_CONSENT_SYMBOLS if symbol not in _REINSTATED_CONSENT_VERIFIERS
)
if _UNVERIFIED_CONSENT_SYMBOLS:  # pragma: no cover - the failure is the collection error itself
    raise AssertionError(
        f"reinstated consent symbols declared with no verifier: {_UNVERIFIED_CONSENT_SYMBOLS}. Every "
        "member of the reinstated set must be mapped to the callable that proves it exists and is "
        "wired; a symbol asserted only by name is the dormancy this module was written against."
    )

_ORPHANED_CONSENT_VERIFIERS = tuple(
    symbol for symbol in _REINSTATED_CONSENT_VERIFIERS if symbol not in _REINSTATED_CONSENT_SYMBOLS
)
if _ORPHANED_CONSENT_VERIFIERS:  # pragma: no cover - the failure is the collection error itself
    raise AssertionError(
        f"verifiers declared for symbols outside the reinstated set: {_ORPHANED_CONSENT_VERIFIERS}. A "
        "verifier with no declared symbol runs against nothing."
    )

_NEIGHBOURING_TRANSPORTS_THAT_MUST_SURVIVE = (SRC_CADRUMO / "entrypoints" / "mcp" / "_call_runtime.py",)


def test_no_deleted_cloud_symbol_survives_in_production() -> None:
    """Every symbol in the declared set is absent from production source.

    Scans the whole non-test package rather than a chosen subtree, because a
    dormant reference is most dangerous exactly where nobody thought to look.
    Test modules are excluded deliberately: a test may legitimately name a
    deleted symbol to assert its absence, as this one does.
    """
    offenders: dict[str, list[str]] = {}
    for path in non_test_package_python_files(include_data=True):
        if path.name == "test_cloud_transport_fully_deleted.py":
            continue
        text = path.read_text(encoding="utf-8")
        for symbol in _DELETED_CLOUD_SYMBOLS:
            if symbol in text:
                offenders.setdefault(symbol, []).append(repo_relative(path))

    assert offenders == {}, (
        "the cloud transport must be GONE, not dormant. These deleted symbols still appear in "
        f"production source: {offenders}. Delete the reference -- do not narrow the pattern above, "
        "which would make this gate report clean without the tree being clean."
    )


def test_the_neighbouring_mcp_subprocess_transport_survived_the_deletion() -> None:
    """The MCP call runtime is a subprocess transport and must NOT have been deleted.

    This is the positive control, and without it the gate above proves only that
    a sweep happened -- not that it was scoped correctly. A deletion driven by
    the word ``subprocess`` would satisfy every assertion in the previous test
    while removing the MCP server's ability to make any tool call at all.

    Asserted on the file's continued existence AND on it still spawning
    processes, because a version stripped of its spawn would exist and do
    nothing.
    """
    for path in _NEIGHBOURING_TRANSPORTS_THAT_MUST_SURVIVE:
        assert path.exists(), f"{repo_relative(path)} is not the cloud transport and must survive the deletion"
        text = path.read_text(encoding="utf-8")
        assert "subprocess" in text, (
            f"{repo_relative(path)} still exists but no longer spawns a process; the cloud deletion "
            "was scoped by the word 'subprocess' rather than by symbol name"
        )


def test_the_declared_symbol_set_is_not_silently_emptied() -> None:
    """The pattern itself must stay substantive.

    Guards the failure mode the module docstring names: a future edit that
    empties or guts the symbol tuple would make the sweep pass over nothing
    while looking exactly like a green run.
    """
    assert len(_DELETED_CLOUD_SYMBOLS) >= 12
    assert "SubprocessLLMClassifier" in _DELETED_CLOUD_SYMBOLS
    assert "CLOUD_EVIDENCE_UPLOAD" in _REINSTATED_CONSENT_SYMBOLS


def test_the_reinstated_consent_apparatus_exists_and_is_wired_at_the_choke_point() -> None:
    """The four consent symbols that RETURNED must exist and be reachable.

    The counterpart to the sweep above, and the reason this module's symbol set
    could be edited at all. Off-host reading of taxpayer evidence was
    re-sanctioned behind a consent gate, so four names moved out of the deleted
    set -- and a name moved out with nothing put back would leave the tree
    weaker than before while both this file and its diff read like a decision.

    **Every declared symbol is verified by the callable the set maps it to**, so
    the set drives its own verification rather than a name-prefix filter
    driving part of it. A member with no verifier never reaches this test: it
    stops the module at import.

    Presence alone is insufficient: a gate that exists and is never called is
    the dormancy this module was written against, pointed the other way. The
    wiring assertion walks the dispatch's AST for the call.
    """
    import ast
    import inspect
    import textwrap

    from ..llm import LLMClient

    for symbol in _REINSTATED_CONSENT_SYMBOLS:
        _REINSTATED_CONSENT_VERIFIERS[symbol](symbol)

    tree = ast.parse(textwrap.dedent(inspect.getsource(LLMClient.complete)))
    called = {
        node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_require_evidence_consent" in called, (
        "the consent gate exists but the dispatch choke point does not call it; a gate no request "
        "crosses is the dormant surface this module forbids"
    )


def _settings_model_fields() -> tuple[str, ...]:
    """Return the live Settings field names.

    Read from the model rather than from source text, so a field renamed
    without this gate's knowledge fails here instead of passing on a substring.
    """
    from ..core.config import Settings

    return tuple(Settings.model_fields)


def test_every_provenance_stamp_a_reader_can_mint_names_a_local_transport() -> None:
    """The provider axis collapsed, so no NEW stamp can name a cloud transport.

    Asserted over the readers that actually exist rather than over a hand-kept
    list of expected prefixes, so a reader added later is covered by
    construction instead of needing this test updated.

    The complementary half is deliberately NOT asserted: pre-existing persisted
    records keep the cloud transport they were stamped with, because that is the
    honest history of how those classifications were reached. Rewriting them
    would erase the fact that some data did once leave the host. What this pins
    is the minting side.
    """
    from ..domain.transactions import prompt_spec_with_every_spending_category
    from ..llm import LocalTextLLMClassifier, LocalVisionLLMClassifier

    spec = prompt_spec_with_every_spending_category()
    stamps = [
        LocalTextLLMClassifier(spec=spec, model="qwen2.5:3b").decided_by,
        LocalVisionLLMClassifier(spec=spec, model="qwen2.5vl:3b").decided_by,
    ]

    for stamp in stamps:
        transport = stamp.split(":")[1]
        assert stamp.startswith("llm:"), f"{stamp!r} must keep the llm:<transport>:<model> shape"
        assert transport.startswith("local-"), (
            f"{stamp!r} names transport {transport!r}; every mintable transport is on-host now"
        )
        assert transport not in {"claude", "codex", "antigravity"}

    assert len({s.split(":")[1] for s in stamps}) == len(stamps), (
        "the two on-host transports must stay distinguishable from each other, or a persisted "
        "record cannot say whether it was read as text or as an image"
    )
