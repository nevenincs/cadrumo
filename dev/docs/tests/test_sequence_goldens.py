"""Executor-level mask-honesty (anti-tautology) gate for cli-sequence goldens.

The sequence-level analogue of the substrate's own anti-tautology proof
(``cadrumo.core.observability.tests.test_golden``), enforced through the REAL
executor and comparison path (W02.P05.S18; ADR D3). Three interlocking claims:

1. **Residual determinism, pinned exactly.** A representative sequence executed
   twice in fresh hermetic sandboxes yields pre-mask differing JSON paths equal
   to the sequence's residual non-deterministic set. On today's enrollable
   surface that residual is EMPTY — with the clock frozen and the profile id
   injected, every reachable identifier is content-addressed or pinned — which
   is trivially within the central ``GOLDEN_MASK_FIELDS``.
2. **The masked-field canary.** The centrally-masked surrogate keys
   (``snapshot_id``, ``run_id``) are today emitted ONLY by live-AEAT surfaces,
   which are unenrollable by design (ADR D6), so no sandbox sequence can
   surface them organically. This gate pins that fact: if a masked key ever
   appears in an enrollable envelope, the canary fails loudly and claim 1 must
   be extended to a sequence that genuinely exercises the flap — the gate
   cannot silently rot into vacuity.
3. **The mask bites exactly the declared set — through the real compare
   path.** A masked-field value difference injected into a REAL golden/live
   pair compares CLEAN (the mask hides it), while the same difference under
   any other key compares RED (the mask hides nothing else). Together with the
   substrate proof over real live-capture envelopes, widening or shrinking the
   central mask is a loud failure at both tiers.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from cadrumo.core.observability import GOLDEN_MASK_FIELDS, differing_paths
from dev.docs.sequences import (
    ParsedSequence,
    SequenceGolden,
    SequenceTranscript,
    build_golden,
    compare_transcript_to_golden,
    execute_sequence,
    parse_sequence,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PAGE = "tutorials/anti-tautology-gate"

#: The representative sequence: a real capture-threaded JSON read chain.
_BODY = "\n".join(
    [
        "aeat --format json config profile list",
        "@capture run_status status",
        "@result aeat --format json config profile list",
        '@expect status == "success"',
        "@expect exit_code == 0",
    ],
)


def _representative_sequence() -> ParsedSequence:
    return parse_sequence(
        sequence_id="anti-tautology-gate",
        options={"verify": "Verify the profile listing succeeds."},
        body=_BODY,
    )


@pytest.fixture(scope="module")
def double_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[SequenceTranscript, SequenceTranscript]:
    """Two REAL executions of the representative sequence, fresh sandboxes."""
    first = execute_sequence(_representative_sequence(), sandbox_root=tmp_path_factory.mktemp("run-a"))
    second = execute_sequence(_representative_sequence(), sandbox_root=tmp_path_factory.mktemp("run-b"))
    return first, second


def _envelope_keys(node: object) -> frozenset[str]:
    """Collect every mapping key at any depth of an envelope document."""
    keys: set[str] = set()

    def _walk(value: object) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                keys.add(str(key))
                _walk(item)
            return
        if isinstance(value, list | tuple):
            for item in value:
                _walk(item)

    _walk(node)
    return frozenset(keys)


def _mutated_golden(golden: SequenceGolden, key: str, value: str) -> SequenceGolden:
    """Return the golden with ``key: value`` injected into frame 0's result."""
    document = golden.model_dump(mode="json")
    document["frames"][0]["envelope"]["result"][key] = value
    return SequenceGolden.model_validate_json(json.dumps(document))


def _mutated_transcript(transcript: SequenceTranscript, key: str, value: str) -> SequenceTranscript:
    """Return the transcript with ``key: value`` injected into frame 0's envelope."""
    document = transcript.model_dump(mode="json")
    document["frames"][0]["envelope"]["result"][key] = value
    return SequenceTranscript.model_validate_json(json.dumps(document))


class TestExecutorMaskHonesty:
    def test_pre_mask_residual_equals_the_declared_nondeterministic_set(
        self,
        double_run: tuple[SequenceTranscript, SequenceTranscript],
    ) -> None:
        """Claim 1: the double-execution pre-mask diff is pinned EXACTLY.

        The residual for the enrollable surface is empty (content-addressed
        ids, frozen clock, injected profile id); pinning `== frozenset()`
        rather than `<= mask` means ANY new residual path — masked or not —
        is a named regression that must be consciously enrolled, never
        silently absorbed.
        """
        first, second = double_run
        residual: set[str] = set()
        for left, right in zip(first.frames, second.frames, strict=True):
            assert left.envelope is not None and right.envelope is not None
            residual |= differing_paths(left.envelope, right.envelope)
            assert left.output == right.output
            assert left.stderr == right.stderr
        # Empty is trivially within the central mask; the equality pin is the
        # stronger claim.
        assert residual == frozenset(), sorted(residual)

    def test_masked_keys_do_not_appear_on_the_enrollable_surface_yet(
        self,
        double_run: tuple[SequenceTranscript, SequenceTranscript],
    ) -> None:
        """Claim 2 (canary): today the masked surrogate keys live only on
        unenrollable live-AEAT surfaces. If this ever fails, an enrollable
        envelope has started emitting a masked field — extend the double-run
        proof above to a sequence that genuinely exercises that flap before
        touching this assertion."""
        first, _ = double_run
        seen: set[str] = set()
        for frame in first.frames:
            seen |= _envelope_keys(frame.envelope)
        assert seen & GOLDEN_MASK_FIELDS == frozenset(), sorted(seen & GOLDEN_MASK_FIELDS)

    @pytest.mark.parametrize("masked_key", sorted(GOLDEN_MASK_FIELDS))
    def test_mask_hides_a_masked_field_flap_through_the_real_compare_path(
        self,
        double_run: tuple[SequenceTranscript, SequenceTranscript],
        masked_key: str,
    ) -> None:
        """Claim 3a: a golden/live pair differing ONLY in a masked field's
        value compares clean through ``compare_transcript_to_golden`` — the
        exact flap (a uuid tail) the central mask exists to hide."""
        first, second = double_run
        golden = _mutated_golden(build_golden(first), masked_key, "writer-run-value-1111")
        live = _mutated_transcript(second, masked_key, "checker-run-value-2222")
        assert compare_transcript_to_golden(live, golden, page=_PAGE) == ()

    def test_mask_hides_nothing_but_the_declared_fields(
        self,
        double_run: tuple[SequenceTranscript, SequenceTranscript],
    ) -> None:
        """Claim 3b: the identical value flap under an UNDECLARED key is a
        loud post-mask divergence — the mask is exactly the declared set, so
        it cannot silently widen to launder a real regression."""
        first, second = double_run
        undeclared_key = "some_other_surrogate_id"
        assert undeclared_key not in GOLDEN_MASK_FIELDS
        golden = _mutated_golden(build_golden(first), undeclared_key, "writer-run-value-1111")
        live = _mutated_transcript(second, undeclared_key, "checker-run-value-2222")
        problems = compare_transcript_to_golden(live, golden, page=_PAGE)
        assert len(problems) == 1
        assert undeclared_key in problems[0]
