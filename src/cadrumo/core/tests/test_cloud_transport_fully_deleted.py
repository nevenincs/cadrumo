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

**The minting side is now a partition, not a sweep.** Every stamp a reader could
mint once named an on-host transport, because the provider axis had collapsed
with the deletion. It has not stayed collapsed: three readers took a provider
back when off-host evidence reading was re-sanctioned. So the readers are
partitioned by whether a caller can reach them off-host at all -- those with no
provider parameter must stamp on-host, and those with one must stamp the
transport they actually ran at. The partition is checked against the readers
discovered in source, because the assertion this replaced said it ran over the
readers that exist while naming two of five.

**The set is symbols, never the word ``subprocess``.** ``cadrumo_harness/mcp/
_call_runtime.py`` shells the deterministic CLI for every MCP tool call: it is
a subprocess transport and it is NOT the cloud LLM transport. A word-sweep
would delete the MCP server's entire call path. A duplication-audit helper that
shells a Node tool is a second such neighbour. Both are asserted to survive, so
this gate proves the deletion was scoped by meaning rather than by string.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest

from ...tests import SRC_CADRUMO, non_test_package_python_files, repo_relative
from .. import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

if TYPE_CHECKING:
    from ...application.ledger import InvoiceExtractionAuthorityValues
    from ..config import LLMProvider

_DELETED_CLOUD_SYMBOL_FAMILIES: dict[str, tuple[str, ...]] = {
    "transport and provider builders": (
        "SubprocessLLMClassifier",
        "build_claude_classifier",
        "build_antigravity_classifier",
        "build_codex_classifier",
        "_PROVIDER_BUILDERS",
        "resolve_classifier",
        "resolve_split_proposer",
    ),
    "provider axis: its enum, its PATH probes, its availability records": (
        "SubprocessProvider",
        "available_llm_providers",
        "is_llm_provider_available",
        "LLMProviderAvailability",
        "probe_subprocess_providers",
    ),
    # Still deleted, and the reason changed: a CLI surface does now ask the
    # operator for a consent token, but it asks through `--off-host-provider`
    # and `--acknowledge-off-host`. These two names belonged to the subprocess
    # family and are not the reinstated spelling of anything.
    "operator-facing surfaces of the deleted transport": (
        "evidence_acknowledged",
        "evidence-acknowledged",
    ),
}
"""The deleted symbol set, grouped by the family each name belonged to.

Grouped rather than flat because the non-vacuity floor below asserts a PROPERTY
of this declaration -- that no family was silently gutted -- and a flat tuple can
only be measured by its length. A length floor encodes the moment it was
written: it is satisfied by twelve names from one family after the other two are
deleted, and the first person to trip it is trained to raise the constant.
"""

_DELETED_CLOUD_SYMBOLS: tuple[str, ...] = tuple(
    symbol for family in _DELETED_CLOUD_SYMBOL_FAMILIES.values() for symbol in family
)

_SCANNER_CONTROL_SYMBOL = "build_provenance_stamp"
"""A symbol that IS present in production, swept by the same machinery.

The sweep below reports clean when it finds nothing, and finding nothing is also
exactly what a broken scanner reports: an empty file list, a changed helper, a
read that silently yields no text. The MCP control proves the DELETION was
scoped by meaning rather than by string; it says nothing about whether the
scanner ran. This symbol is the control for the instrument itself.
"""


def _verify_settings_field(symbol: str) -> None:
    """Assert *symbol* is a live deployment setting the operator can reach."""
    assert symbol in set(_settings_model_fields()), f"{symbol} is claimed reinstated but Settings does not declare it"


def _verify_consent_predicate(symbol: str) -> None:
    """Assert the consent predicate is importable from the package facade and callable."""
    from ...llm import cloud_evidence_read_permitted

    assert cloud_evidence_read_permitted.__name__ == symbol
    assert callable(cloud_evidence_read_permitted)


def _verify_capability_defaults_off(symbol: str) -> None:
    """Assert the reinstated capability is a live member AND still defaults off.

    The default is the property it was reinstated FOR. A member present but
    defaulting on would satisfy a mere membership check while removing the bar
    it names.
    """
    from .. import ServiceCapability

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

#: The MCP call runtime now ships in the harness distribution beside the
#: package rather than under ``entrypoints/mcp``. It is still the neighbouring
#: transport this gate must see survive, so the path follows it; asserting the
#: old location would report the cloud transport's deletion as having taken a
#: live neighbour with it.
_NEIGHBOURING_TRANSPORTS_THAT_MUST_SURVIVE = (
    SRC_CADRUMO.parent / "cadrumo-harness" / "src" / "cadrumo_harness" / "mcp" / "_call_runtime.py",
)


def _production_sites_naming(symbols: tuple[str, ...]) -> dict[str, list[str]]:
    """Return, per symbol, every production file naming it.

    Factored out so the sweep and its scanner control run the SAME machinery
    over the SAME file set. A control that re-implements the walk proves its own
    copy works and says nothing about the one that reports clean.

    Scans the whole non-test package rather than a chosen subtree, because a
    dormant reference is most dangerous exactly where nobody thought to look.
    Test modules are excluded deliberately: a test may legitimately name a
    deleted symbol to assert its absence, as this one does.
    """
    sites: dict[str, list[str]] = {}
    for path in non_test_package_python_files(include_data=True):
        if path.name == "test_cloud_transport_fully_deleted.py":
            continue
        text = path.read_text(encoding="utf-8")
        for symbol in symbols:
            if symbol in text:
                sites.setdefault(symbol, []).append(repo_relative(path))
    return sites


def test_no_deleted_cloud_symbol_survives_in_production() -> None:
    """Every symbol in the declared set is absent from production source."""
    offenders = _production_sites_naming(_DELETED_CLOUD_SYMBOLS)

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


def test_the_scanner_finds_a_symbol_that_is_actually_present() -> None:
    """The sweep's clean result must mean the tree is clean, not that nothing ran.

    This is the non-vacuity floor, re-based onto a property. The shape it
    replaces was ``len(_DELETED_CLOUD_SYMBOLS) >= 12``, which is a tally: it
    encodes the moment it was written, it is satisfied by twelve names drawn
    from one family after the other two are deleted, and the first person to
    trip it is trained to raise the constant rather than to ask what it was
    protecting. It also measured the wrong thing entirely -- a full symbol tuple
    scanned over an empty file list still reports clean.

    Driven through the same helper the sweep uses, over the same file set. A
    control with its own copy of the walk proves that copy works.
    """
    found = _production_sites_naming((_SCANNER_CONTROL_SYMBOL,))

    assert _SCANNER_CONTROL_SYMBOL in found, (
        f"the scanner did not find {_SCANNER_CONTROL_SYMBOL!r}, which IS present in production. The "
        "sweep's clean result is therefore evidence about the scanner and not about the tree: the "
        "file walk, the read, or the match has stopped working."
    )


def test_no_declared_family_is_silently_gutted() -> None:
    """Every declared deletion family still contributes names to the sweep.

    The property the tally was reaching for, stated directly: what must not
    happen is a family quietly emptied while the set still looks substantial.
    Asserted per family, so deleting the provider-axis names reds even though
    the remaining two families would satisfy any plausible length floor.

    The reinstated set gets a non-emptiness assertion of its own because its two
    totality checks pass VACUOUSLY when the declared set and its verifier
    mapping are emptied together -- each only asserts the two agree.
    """
    empty = sorted(family for family, symbols in _DELETED_CLOUD_SYMBOL_FAMILIES.items() if not symbols)
    assert empty == [], (
        f"these deletion families declare no symbols: {empty}. An emptied family makes the sweep pass "
        "over that family's names while the declaration still reads like a decision."
    )
    assert _DELETED_CLOUD_SYMBOL_FAMILIES, "every deletion family is gone; the sweep scans for nothing"

    duplicated = sorted({symbol for symbol in _DELETED_CLOUD_SYMBOLS if _DELETED_CLOUD_SYMBOLS.count(symbol) > 1})
    assert duplicated == [], (
        f"these symbols are declared in more than one family: {duplicated}. A name in two families "
        "makes a family look populated while its own membership is borrowed."
    )

    assert _REINSTATED_CONSENT_SYMBOLS, (
        "the reinstated consent set is empty, so both totality checks above pass over nothing and no "
        "consent symbol is asserted present or wired at the choke point"
    )


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

    from ...llm import LLMClient

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
    from ..config import Settings

    return tuple(str(name) for name in Settings.model_fields)


def _transport_of(stamp: str) -> str:
    """Return the transport a stamp names, through the canonical parser.

    Read with :func:`~core.provenance_stamp_transport` rather than by slicing on
    ``:``, because the hand-rolled slice this replaces re-implemented the stamp
    grammar inside the gate that checks it. A producer and a checker that each
    carry their own copy of a grammar agree until the grammar changes, and then
    the checker keeps passing on the shape nothing writes any more.
    """
    from .. import provenance_stamp_transport

    transport = provenance_stamp_transport(stamp)
    assert transport is not None, f"{stamp!r} does not name a transport the canonical parser can read"
    return transport


def _text_classifier_transport() -> str:
    from ...domain.transactions import prompt_spec_with_every_spending_category
    from ...llm import LocalTextLLMClassifier

    spec = prompt_spec_with_every_spending_category()
    return _transport_of(LocalTextLLMClassifier(spec=spec, model="qwen2.5:3b").decided_by)


def _vision_classifier_transport() -> str:
    from ...domain.transactions import prompt_spec_with_every_spending_category
    from ...llm import LocalVisionLLMClassifier

    spec = prompt_spec_with_every_spending_category()
    return _transport_of(LocalVisionLLMClassifier(spec=spec, model="qwen2.5vl:3b").decided_by)


def _pinned_authority_values() -> InvoiceExtractionAuthorityValues:
    """Return injected regulatory values for the text extractor's compiled prompt.

    Injected rather than resolved through the registry because this gate asks
    only what TRANSPORT a stamp names; resolving real rates would couple a
    transport assertion to registry load, which in this tree fails under
    concurrent writes and would red this gate for a reason that has nothing to
    do with the property it pins.
    """
    from decimal import Decimal

    from ...application.ledger import InvoiceExtractionAuthorityValues, default_invoice_extraction_period
    from ...domain.iva import IvaCategory

    return InvoiceExtractionAuthorityValues(
        period=default_invoice_extraction_period(),
        iva_rate_pcts=(Decimal("21"),),
        retencion_rate_pcts=(Decimal("15"),),
        no_printed_tax_categories=(IvaCategory.DOMESTIC_ZERO,),
        regime_legend_phrases=("operación exenta",),
    )


def _text_extractor_transport(provider: LLMProvider | None = None) -> str:
    from ...llm import TextInvoiceFieldExtractor
    from ..config import LLMProvider

    resolved = provider if provider is not None else LLMProvider.LOCAL
    model = "qwen3:1.7b" if resolved is LLMProvider.LOCAL else "gpt-4.1"
    reader = TextInvoiceFieldExtractor(
        model=model,
        provider=resolved,
        authority_values=_pinned_authority_values(),
    )
    return _transport_of(reader.decided_by)


def _vision_transcriber_transport(provider: LLMProvider | None = None) -> str:
    from ...llm import LocalVisionDocumentTranscriber
    from ..config import LLMProvider

    resolved = provider if provider is not None else LLMProvider.LOCAL
    model = "qwen2.5vl:3b" if resolved is LLMProvider.LOCAL else "claude-haiku-4-5-20251001"
    return LocalVisionDocumentTranscriber(model=model, provider=resolved).transcriber_identity.transport


def _column_role_mapper_transport(provider: LLMProvider | None = None) -> str:
    from ...llm import SemanticColumnRoleMapper
    from ..config import LLMProvider

    resolved = provider if provider is not None else LLMProvider.LOCAL
    model = "qwen3:1.7b" if resolved is LLMProvider.LOCAL else "gpt-4.1"
    # The model is pinned rather than left to resolve, because resolution runs
    # the on-host hardware admission check and would make this gate's result a
    # property of the machine it ran on.
    return _transport_of(SemanticColumnRoleMapper(model=model, provider=resolved).decided_by)


def _supply_nature_proposer_transport(provider: LLMProvider | None = None) -> str:
    from ...llm import SupplyNatureProposer
    from ..config import LLMProvider

    resolved = provider if provider is not None else LLMProvider.LOCAL
    model = "qwen3:1.7b" if resolved is LLMProvider.LOCAL else "gpt-4.1"
    # Pinned for the reason the column-role mapper's builder states: resolving
    # the role would run the on-host hardware admission check and make this
    # gate's result a property of the machine it ran on.
    return _transport_of(SupplyNatureProposer(model=model, provider=resolved).decided_by)


_READERS_WITH_NO_PROVIDER_AXIS: dict[str, Callable[[], str]] = {
    "LocalTextLLMClassifier": _text_classifier_transport,
    "LocalVisionLLMClassifier": _vision_classifier_transport,
}
"""Readers a caller can reach with no consent token, keyed to their transport.

Their constructors declare no ``provider`` parameter at all, so no call site can
ask them for an off-host read. That structural claim is asserted below rather
than trusted: it is what makes their on-host transport a property of the class
instead of an observation about the one instance this module builds.
"""

_READERS_WITH_A_PROVIDER_AXIS: dict[str, Callable[[LLMProvider | None], str]] = {
    "TextInvoiceFieldExtractor": _text_extractor_transport,
    "LocalVisionDocumentTranscriber": _vision_transcriber_transport,
    "SemanticColumnRoleMapper": _column_role_mapper_transport,
    "SupplyNatureProposer": _supply_nature_proposer_transport,
}
"""Readers that accept a provider, keyed to a builder taking the provider.

Reaching one of these off-host with a taxpayer's document requires a
per-invocation consent token at the dispatch choke point. What this module pins
about them is not that they refuse -- the consent suite owns that -- but that
when they do run off-host they SAY SO. A stamp reading ``local`` for a read
served off-host is the artefact a consent withdrawal enumerates by transport and
therefore cannot see, which is precisely the artefact most needing
re-derivation.
"""


def test_every_transport_mintable_without_a_consent_token_is_on_host() -> None:
    """A reader with no provider axis can only ever stamp an on-host transport.

    This is the narrowed descendant of an assertion that once swept every
    reader. It was true when the cloud transport had just been deleted and the
    provider axis really had collapsed; it is not true now, because off-host
    evidence reading was re-sanctioned behind the consent gate and three readers
    took a provider back. Left unnarrowed it would have been a gate asserting a
    property the tree no longer has -- and the honest narrowing is by the
    property that still holds, not by dropping the readers that stopped
    satisfying it. Those move to the honesty assertion below rather than out of
    the module.

    The complementary half is deliberately NOT asserted: pre-existing persisted
    records keep the cloud transport they were stamped with, because that is the
    honest history of how those classifications were reached. Rewriting them
    would erase the fact that some data did once leave the host. What this pins
    is the minting side.
    """
    import inspect

    from ...llm import LocalTextLLMClassifier, LocalVisionLLMClassifier
    from .. import LOCAL_TRANSPORT_LABEL

    classes = {
        "LocalTextLLMClassifier": LocalTextLLMClassifier,
        "LocalVisionLLMClassifier": LocalVisionLLMClassifier,
    }
    assert set(classes) == set(_READERS_WITH_NO_PROVIDER_AXIS)

    transports: dict[str, str] = {}
    for name, build in _READERS_WITH_NO_PROVIDER_AXIS.items():
        parameters = inspect.signature(classes[name].__init__).parameters
        assert "provider" not in parameters, (
            f"{name} now declares a provider parameter, so it is no longer mintable on-host by "
            "construction; move it to the provider-axis set, where its off-host stamp is checked "
            "for honesty instead of asserted absent"
        )
        transport = build()
        assert transport == LOCAL_TRANSPORT_LABEL, (
            f"{name} stamps transport {transport!r}; a reader reachable with no consent token must "
            "never name an off-host transport"
        )
        transports[name] = transport

    assert transports, "no reader was checked at all; this gate would pass over nothing"


def test_a_reader_reachable_only_under_consent_stamps_the_transport_it_actually_used() -> None:
    """Both directions, because either alone is indistinguishable from a broken reader.

    The on-host direction is this test's positive control: without it, an
    off-host reader that had stopped stamping anything meaningful -- or one whose
    constructor silently ignored the provider -- could still satisfy "not local"
    by accident. And the off-host direction is what stops the gate degrading into
    a restatement of the on-host default, which every reader satisfies while
    saying nothing about the case the consent apparatus exists for.

    Asserted on the CONSTRUCTED stamp rather than on source text, because a
    reader that assembled a hardcoded label would satisfy any source-level
    pattern while storing the same lie.
    """
    from .. import LOCAL_TRANSPORT_LABEL
    from ..config import LLMProvider

    off_host = {
        "TextInvoiceFieldExtractor": LLMProvider.OPENAI,
        "LocalVisionDocumentTranscriber": LLMProvider.ANTHROPIC,
        "SemanticColumnRoleMapper": LLMProvider.OPENAI,
        "SupplyNatureProposer": LLMProvider.ANTHROPIC,
    }
    assert set(off_host) == set(_READERS_WITH_A_PROVIDER_AXIS)

    for name, build in _READERS_WITH_A_PROVIDER_AXIS.items():
        provider = off_host[name]
        on_host_transport = build(LLMProvider.LOCAL)
        assert on_host_transport == LOCAL_TRANSPORT_LABEL, (
            f"{name} stamps {on_host_transport!r} for an on-host read; the positive control fails, so "
            "its off-host result below proves nothing"
        )

        off_host_transport = build(provider)
        assert off_host_transport == provider.value.lower(), (
            f"{name} ran at {provider.value} and stamped transport {off_host_transport!r}; a consented "
            "off-host read must record the transport it used or the withdrawal survey cannot find it"
        )
        assert off_host_transport != on_host_transport, (
            f"{name} stamps the same transport whether or not a provider was named, so the provider it "
            "was given reaches the stamp not at all"
        )


def test_every_stamp_producing_reader_is_declared_in_one_of_the_two_sets() -> None:
    """The partition is total over the readers that exist, or this module stops.

    The assertion this replaced claimed to run "over the readers that actually
    exist rather than over a hand-kept list", and it did not: it built two
    classifiers by name while three further stamp producers shipped in the same
    package, one of which could already mint an off-host stamp. That is the
    failure mode of a set that has stopped driving its own verification -- the
    same one the reinstated-symbol mapping above was reshaped to remove -- so the
    partition is checked against a discovered set rather than asserted by count.

    Discovered from source rather than by importing the package, because a
    reader class that fails to import would silently shrink the discovered set
    to something the declaration still covers.
    """
    import ast

    package = SRC_CADRUMO / "llm"
    discovered: set[str] = set()
    for path in scan_directory(package, pattern="*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            members = {
                member.name for member in node.body if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef)
            }
            if members & {"decided_by", "transcriber_identity"}:
                discovered.add(node.name)

    assert discovered, "no stamp-producing reader was discovered; this gate is pointed at nothing"
    declared = set(_READERS_WITH_NO_PROVIDER_AXIS) | set(_READERS_WITH_A_PROVIDER_AXIS)
    assert discovered == declared, (
        f"the declared reader partition does not cover the readers that exist. Undeclared: "
        f"{sorted(discovered - declared)}. Declared but absent: {sorted(declared - discovered)}. Every "
        "stamp producer belongs in exactly one set -- on-host by construction, or provider-bearing and "
        "held to stamping the transport it actually used."
    )
