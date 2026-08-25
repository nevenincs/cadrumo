"""One constructor builds every provenance stamp, and nothing hand-formats one.

A canonical constructor that producers MAY use is a convention, and a convention
is exactly what produced five hand-formatted stamps in the first place -- one of
which omitted the transport segment entirely and parsed its own reader name as
its transport. The constructor is the fix; this module is the guarantee.

**Two assertions, because either alone is escapable.** Scanning for the ``llm:``
prefix catches a sixth hand-formatted string but not a producer that assembles
the same shape by concatenation. Asserting every ``decided_by`` calls the
constructor catches that, but not a stamp built somewhere that is not a
``decided_by``. Together they close both doors.

The stamp matters because a consent withdrawal enumerates cloud-derived
artefacts BY its transport segment: a stamp that omits or misformats that
segment describes an artefact the withdrawal cannot see, which is precisely the
artefact most needing re-derivation.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ...core import build_provenance_stamp
from ...core.directory_scan import scan_directory
from ...core.config import LLMProvider
from ...tests import non_test_package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CANONICAL_MODULE = "_provenance_stamp.py"
_STAMP_PREFIX = "llm:"


def _hand_built_stamps(tree: ast.AST) -> list[str]:
    """Return literals that BUILD a stamp, excluding those that merely test for one.

    The distinction is the whole difficulty. A bare ``"llm:"`` constant is a
    prefix check -- a consumer asking "was this classified by a model?" -- and
    those are legitimate. But the literal segment of a hand-built
    ``f"llm:{transport}-{reader}:{model}"`` is ALSO exactly ``"llm:"``, so
    exempting the bare string by value would blind this gate to the precise
    shape it exists to catch.

    Discriminated structurally instead: a prefix inside an f-string is being
    CONSTRUCTED, and a literal carrying content past the prefix is a fully
    hand-written stamp. A standalone bare prefix is a test and is allowed.
    """
    built: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if (
                    isinstance(part, ast.Constant)
                    and isinstance(part.value, str)
                    and part.value.startswith(_STAMP_PREFIX)
                ):
                    built.append(f"f-string starting {part.value!r}")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith(_STAMP_PREFIX)
            and node.value != _STAMP_PREFIX
        ):
            built.append(node.value)
    return built


def test_no_production_module_hand_formats_a_provenance_stamp() -> None:
    """Only the canonical module may name the stamp prefix.

    Scans the whole non-test package rather than the inference subpackage,
    because a stamp assembled in the application or adapter layer would be just
    as unparseable and is exactly where nobody would think to look.
    """
    offenders: dict[str, list[str]] = {}
    for path in non_test_package_python_files():
        if path.name == _CANONICAL_MODULE:
            continue
        source = path.read_text(encoding="utf-8")
        # Screen before parsing: every finding is a string literal starting with
        # the stamp prefix, so a module whose source never mentions ``llm`` has
        # nothing to find. This skips 1,534 of 1,712 parses.
        #
        # Screened on ``llm`` rather than the full ``llm:`` prefix deliberately.
        # A literal can spell its colon as an escape, and ``"llm\x3a..."`` would
        # slip past the tighter screen while still parsing to a stamp. Screening
        # on the bare letters costs 166 extra parses and closes that. It is not
        # airtight either -- a fully escaped ``"\x6c\x6cm:"`` would evade it --
        # and that is accepted: this gate exists to catch a stamp assembled by
        # hand, not one hidden on purpose.
        if _STAMP_PREFIX.rstrip(":") not in source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:  # a peer mid-write; not this gate's finding to make
            continue
        literals = _hand_built_stamps(tree)
        if literals:
            offenders[repo_relative(path)] = literals

    assert offenders == {}, (
        "these modules hand-format a provenance stamp instead of calling "
        f"build_provenance_stamp: {offenders}. The grammar lives in core/{_CANONICAL_MODULE}; a stamp "
        "built anywhere else is one the consent withdrawal survey may not be able to classify."
    )


def test_every_reader_builds_its_stamp_through_the_constructor() -> None:
    """Each ``decided_by`` in the inference package calls the canonical builder.

    Closes the door the prefix scan leaves open: a producer that assembles the
    same shape by concatenation names no ``llm:`` literal and would pass the
    scan while emitting a stamp nothing agreed to.
    """
    package = Path(__file__).resolve().parents[1]
    routed: dict[str, bool] = {}
    for path in scan_directory(package, pattern="*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name != "decided_by":
                continue
            calls = {
                call.func.id
                for call in ast.walk(node)
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            }
            # Keyed by LINE, not by name: two producers in one module share a
            # name, and keying by name let a compliant one silently overwrite a
            # bypassing one. A mutation caught that before this gate shipped.
            routed[f"{path.name}:{node.lineno}"] = "build_provenance_stamp" in calls

    assert routed, "no decided_by producer was found at all; this gate would pass over nothing"
    unrouted = sorted(site for site, ok in routed.items() if not ok)
    assert unrouted == [], (
        f"these readers build a provenance stamp without the canonical constructor: {unrouted}. "
        "Route them through build_provenance_stamp so the grammar stays in one place."
    )


def test_the_scan_is_not_vacuous() -> None:
    """The canonical module really does carry the prefix the scan looks for.

    Without this, deleting the prefix from the grammar would make the sweep
    above pass over nothing while reading exactly like a clean run -- the same
    silent-emptying failure the cloud-deletion gate guards against.
    """
    canonical = Path(__file__).resolve().parents[2] / "core" / _CANONICAL_MODULE
    assert canonical.exists(), "the canonical stamp module has moved; this gate is pointed at nothing"
    assert _STAMP_PREFIX in canonical.read_text(encoding="utf-8")


def test_a_stamp_built_here_is_readable_by_the_parser_that_classifies_it() -> None:
    """Round-trip: what the constructor writes, the parser must classify.

    The two halves live in one module precisely so they cannot drift, and this
    is the assertion that would notice if they did. Both directions are
    covered, because a constructor that only ever produced on-host stamps would
    satisfy a local-only check while being unable to express the case the whole
    apparatus exists for.
    """
    from ...core import provenance_stamp_transport

    local = build_provenance_stamp(provider=LLMProvider.LOCAL, reader="text-extract", model="m")
    cloud = build_provenance_stamp(provider=LLMProvider.OPENAI, reader="text-extract", model="gpt-4.1")

    assert provenance_stamp_transport(local) == "local"
    assert provenance_stamp_transport(cloud) == "openai"
    assert provenance_stamp_transport(local) != provenance_stamp_transport(cloud)


def test_no_transcriber_identity_folds_its_transport_into_a_name() -> None:
    """The identity records transport as data, never inside another field.

    A third provenance grammar is what this module exists to prevent, and the
    identity was carrying one: the vision reader folded its transport into
    ``name`` as ``vision-<transport>:<model>``, which no parser knew and which
    broke ``name``'s own contract against coarse labels. The fix was a first
    class ``transport`` field, so the way that regresses is someone folding it
    back into a name.

    Asserted over the CONSTRUCTED identities rather than over source text: what
    matters is the value that reaches storage, and a reader assembling the name
    from parts would satisfy any source-level pattern while storing the same
    smuggled shape.
    """
    from ...application.ledger.evidence_textlayer import text_layer_transcriber_identity
    from ...core import LOCAL_TRANSPORT_LABEL
    from .._evidence_draft_vision import LocalVisionDocumentTranscriber

    identities = [
        text_layer_transcriber_identity(),
        LocalVisionDocumentTranscriber(model="qwen2.5vl:3b").transcriber_identity,
        LocalVisionDocumentTranscriber(
            model="claude-haiku-4-5-20251001",
            provider=LLMProvider.ANTHROPIC,
        ).transcriber_identity,
    ]

    assert any(identity.transport != LOCAL_TRANSPORT_LABEL for identity in identities), (
        "every identity here is on-host, so this gate cannot tell a recorded transport from a "
        "hardcoded one; include an off-host reader or it proves nothing"
    )
    for identity in identities:
        assert identity.transport, f"{identity.name} records no transport"
        assert identity.transport not in identity.name, (
            f"{identity.name!r} folds its transport {identity.transport!r} back into the name; "
            "transport is its own axis so that nothing has to parse a name to find it"
        )
