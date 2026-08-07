"""No cloud transport survives dormant anywhere in production.

The cloud read path was deleted rather than left behind a disabled flag,
because `no-legacy-compatibility` forbids keeping a retired surface as a
bridge and because a dormant off-host transport is the one thing this campaign
exists to remove. A retained-but-unreachable path is a failed outcome, not a
partial success: the next change that re-enables a flag re-enables the
transport with it.

**The search pattern is declared here, once, and is not narrowed.** That is the
whole discipline this gate encodes. Narrowing a pattern until it returns clean
is indistinguishable from cleaning the tree if only the final result is
reported, so the symbol set is fixed in source, reviewable in a diff, and any
future edit to it is a visible decision rather than an invisible one.

**The set is symbols, never the word ``subprocess``.** ``entrypoints/mcp/
_call_runtime.py`` shells the deterministic CLI for every MCP tool call: it is
a subprocess transport and it is NOT the cloud LLM transport. A word-sweep
would delete the MCP server's entire call path. A duplication-audit helper that
shells a Node tool is a second such neighbour. Both are asserted to survive, so
this gate proves the deletion was scoped by meaning rather than by string.
"""

from __future__ import annotations

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
    # The consent gate and the settings behind it.
    "cloud_evidence_read_permitted",
    "CLOUD_EVIDENCE_UPLOAD",
    "cadrumo_evidence_gestor_mode",
    "cadrumo_evidence_cloud_upload_permitted",
    # The operator-facing surfaces.
    "evidence_acknowledged",
    "evidence-acknowledged",
)

_NEIGHBOURING_TRANSPORTS_THAT_MUST_SURVIVE = (
    SRC_CADRUMO / "entrypoints" / "mcp" / "_call_runtime.py",
)


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
    assert len(_DELETED_CLOUD_SYMBOLS) >= 15
    assert "SubprocessLLMClassifier" in _DELETED_CLOUD_SYMBOLS
    assert "CLOUD_EVIDENCE_UPLOAD" in _DELETED_CLOUD_SYMBOLS


def test_every_provenance_stamp_a_reader_can_mint_names_a_local_transport() -> None:
    """S78: the provider axis collapsed, so no NEW stamp can name a cloud transport.

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
