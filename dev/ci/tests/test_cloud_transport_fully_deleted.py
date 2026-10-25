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
eligibility bar, once the decision it was waiting on was taken. The move is
only honest because the destination has teeth:
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

**The minting side is one declared set, not a sweep.** Every reader now reads
through the agent service, which resolves the lane for the role; whether that
lane reads off the host is its catalogue flag, read at the dispatch point's
consent check. So no reader declares a provider, and every reader must stamp
the agent transport rather than claim the on-host one it cannot know. The set
is checked against the readers discovered in source, because an assertion that
said it ran over the readers that exist once named two of five.

**The set is symbols, never the word ``subprocess``.** Other product features
legitimately spawn subprocesses, so a word-sweep would delete unrelated
behavior. This gate proves the deletion was scoped by meaning rather than by
string.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.tests.inventory import SRC_CADRUMO, non_test_package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

if TYPE_CHECKING:
    pass

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
read that silently yields no text. A neighboring-transport control proves the
deletion was scoped by meaning rather than by string; it says nothing about whether the
scanner ran. This symbol is the control for the instrument itself.
"""


def _verify_settings_field(symbol: str) -> None:
    """Assert *symbol* is a live deployment setting the operator can reach."""
    assert symbol in set(_settings_model_fields()), f"{symbol} is claimed reinstated but Settings does not declare it"


def _verify_consent_predicate(symbol: str) -> None:
    """Assert the consent predicate is importable from its defining module and callable."""
    from cadrumo.adapters.outbound.llm.consent import cloud_evidence_read_permitted

    assert cloud_evidence_read_permitted.__name__ == symbol
    assert callable(cloud_evidence_read_permitted)


def _verify_capability_defaults_off(symbol: str) -> None:
    """Assert the reinstated capability is a live member AND still defaults off.

    The default is the property it was reinstated FOR. A member present but
    defaulting on would satisfy a mere membership check while removing the bar
    it names.
    """
    from cadrumo.core.capabilities import ServiceCapability

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

    assert any(_REINSTATED_CONSENT_SYMBOLS), (
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

    from cadrumo.adapters.outbound.llm.client import LLMClient

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
    from cadrumo.core.config import Settings

    return tuple(str(name) for name in Settings.model_fields)


def _transport_of(stamp: str) -> str:
    """Return the transport a stamp names, through the canonical parser.

    Read with :func:`~core.provenance_stamp_transport` rather than by slicing on
    ``:``, because the hand-rolled slice this replaces re-implemented the stamp
    grammar inside the gate that checks it. A producer and a checker that each
    carry their own copy of a grammar agree until the grammar changes, and then
    the checker keeps passing on the shape nothing writes any more.
    """
    from cadrumo.core.provenance_stamp import provenance_stamp_transport

    transport = provenance_stamp_transport(stamp)
    assert transport is not None, f"{stamp!r} does not name a transport the canonical parser can read"
    return transport


def _agent_column_role_mapper_transport() -> str:
    from cadrumo.adapters.outbound.llm.column_role_mapping import SemanticColumnRoleMapper

    return _transport_of(SemanticColumnRoleMapper().decided_by)


def _agent_supply_nature_proposer_transport() -> str:
    from cadrumo.adapters.outbound.llm.supply_nature_proposal import SupplyNatureProposer

    return _transport_of(SupplyNatureProposer().decided_by)


def _agent_text_classifier_transport() -> str:
    from cadrumo.adapters.outbound.llm.text_classifier import TextLLMClassifier
    from cadrumo.domain.transactions.llm import prompt_spec_with_every_spending_category

    with bundled_indexed_authority().operation() as operation:
        spec = prompt_spec_with_every_spending_category(year=2025, operation=operation)
        return _transport_of(TextLLMClassifier(spec=spec).decided_by)


def _agent_text_extractor_transport() -> str:
    from decimal import Decimal

    from cadrumo.adapters.outbound.llm.evidence_draft_text import TextInvoiceFieldExtractor
    from cadrumo.application.ledger.invoice_extraction_authority import (
        InvoiceExtractionAuthorityValues,
        default_invoice_extraction_period,
    )
    from cadrumo.domain.iva.schema import IvaCategory

    # Injected rather than resolved: this gate asks only what transport a stamp
    # names, and resolving real rates would couple it to registry load.
    values = InvoiceExtractionAuthorityValues(
        period=default_invoice_extraction_period(),
        iva_rate_pcts=(Decimal("21"),),
        retencion_rate_pcts=(Decimal("15"),),
        no_printed_tax_categories=(IvaCategory("domestic_zero"),),
        regime_legend_phrases=("operación exenta",),
    )
    with bundled_indexed_authority().operation() as operation:
        return _transport_of(TextInvoiceFieldExtractor(operation=operation, authority_values=values).decided_by)


def _agent_vision_classifier_transport() -> str:
    from cadrumo.adapters.outbound.llm.vision_classifier import VisionLLMClassifier
    from cadrumo.domain.transactions.llm import prompt_spec_with_every_spending_category

    with bundled_indexed_authority().operation() as operation:
        spec = prompt_spec_with_every_spending_category(year=2025, operation=operation)
        return _transport_of(VisionLLMClassifier(spec=spec).decided_by)


def _agent_vision_transcriber_transport() -> str:
    from cadrumo.adapters.outbound.llm.evidence_draft_vision import VisionDocumentTranscriber

    return VisionDocumentTranscriber().transcriber_identity("nearby/api/synthetic-vision:1").transport


def _agent_statement_reader_transport() -> str:
    from cadrumo.adapters.outbound.llm.statement_reading import StatementReader

    return _transport_of(StatementReader().decided_by)


_READERS_THROUGH_THE_AGENT: dict[str, Callable[[], str]] = {
    "TextLLMClassifier": _agent_text_classifier_transport,
    "TextInvoiceFieldExtractor": _agent_text_extractor_transport,
    "StatementReader": _agent_statement_reader_transport,
    "VisionLLMClassifier": _agent_vision_classifier_transport,
    "VisionDocumentTranscriber": _agent_vision_transcriber_transport,
    "SemanticColumnRoleMapper": _agent_column_role_mapper_transport,
    "SupplyNatureProposer": _agent_supply_nature_proposer_transport,
}
"""Readers whose every read goes through the agent service, keyed to their transport.

They declare no provider parameter: the agent resolves the lane for the role,
and whether that lane reads off the host is its catalogue flag, which the
dispatch point's consent check reads. What this module pins about them is that
their stamp never claims the on-host transport, because a stamp cannot know
which lane served the read and a consent withdrawal enumerates by transport.
"""


def test_a_reader_through_the_agent_never_stamps_the_on_host_transport() -> None:
    """Each agent reader has no provider axis and stamps the agent transport.

    Asserted on the constructed stamp, because a reader that assembled a
    hardcoded ``local`` label would satisfy any source-level pattern while
    hiding its reads from a withdrawal survey.
    """
    import inspect

    from cadrumo.adapters.outbound.llm.column_role_mapping import SemanticColumnRoleMapper
    from cadrumo.adapters.outbound.llm.evidence_draft_text import TextInvoiceFieldExtractor
    from cadrumo.adapters.outbound.llm.evidence_draft_vision import VisionDocumentTranscriber
    from cadrumo.adapters.outbound.llm.statement_reading import StatementReader
    from cadrumo.adapters.outbound.llm.supply_nature_proposal import SupplyNatureProposer
    from cadrumo.adapters.outbound.llm.text_classifier import TextLLMClassifier
    from cadrumo.adapters.outbound.llm.vision_classifier import VisionLLMClassifier
    from cadrumo.core.config_support import LLMProvider
    from cadrumo.core.provenance_stamp import LOCAL_TRANSPORT_LABEL

    classes = {
        "TextLLMClassifier": TextLLMClassifier,
        "TextInvoiceFieldExtractor": TextInvoiceFieldExtractor,
        "StatementReader": StatementReader,
        "VisionLLMClassifier": VisionLLMClassifier,
        "VisionDocumentTranscriber": VisionDocumentTranscriber,
        "SemanticColumnRoleMapper": SemanticColumnRoleMapper,
        "SupplyNatureProposer": SupplyNatureProposer,
    }
    assert set(classes) == set(_READERS_THROUGH_THE_AGENT)
    for name, build in _READERS_THROUGH_THE_AGENT.items():
        parameters = inspect.signature(classes[name].__init__).parameters
        assert "provider" not in parameters, f"{name} declares a provider again; the agent picks the lane"
        transport = build()
        assert transport == LLMProvider.AGENT.value.lower(), f"{name} stamps transport {transport!r}"
        assert transport != LOCAL_TRANSPORT_LABEL


def test_every_stamp_producing_reader_is_declared_as_a_reader_through_the_agent() -> None:
    """The declared set is total over the readers that exist, or this module stops.

    The assertion this replaced claimed to run "over the readers that actually
    exist rather than over a hand-kept list", and it did not: it built two
    classifiers by name while three further stamp producers shipped in the same
    package, one of which could already mint an off-host stamp. That is the
    failure mode of a set that has stopped driving its own verification -- the
    same one the reinstated-symbol mapping above was reshaped to remove -- so the
    declared set is checked against a discovered set rather than asserted by count.

    Discovered from source rather than by importing the package, because a
    reader class that fails to import would silently shrink the discovered set
    to something the declaration still covers.
    """
    import ast

    package = SRC_CADRUMO / "adapters" / "outbound" / "llm"
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
    declared = set(_READERS_THROUGH_THE_AGENT)
    assert discovered == declared, (
        f"the declared readers do not cover the readers that exist. Undeclared: "
        f"{sorted(discovered - declared)}. Declared but absent: {sorted(declared - discovered)}. Every "
        "stamp producer reads through the agent and is held to stamping the agent transport."
    )
