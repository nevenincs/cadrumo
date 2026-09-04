"""The ``cli-sequence`` documentation execution engine (docs tooling).

This package is the one hermetic engine behind the ``cli-sequence`` MyST
directive: it parses a directive body into typed frames, executes each frame in a
per-sequence sandbox, compares the result against a committed golden, and drives
the refresh / check CLI. It lives under ``dev/docs`` (dev-only docs tooling,
kept separate from the shipped product) and imports the production ``cadrumo``
package from outside.

This module exposes the frame-grammar parser, the ``:seed:`` recipe loader,
the per-sequence hermetic sandbox runner with ``@capture`` threading, the
committed golden store, the golden comparison plus ``@expect`` evaluation
tier, the discovery/refresh/check engine functions behind
``python -m dev.docs.sequences`` — the one execution path the Sphinx build
hook and the pytest gate both wire — the build-time command-line tokeniser,
the static live-AEAT enrollment refusal (``refuse_live_frames`` /
``live_aeat_tokens``), and the ``@static`` blocked-reason taxonomy
(``StaticBlocker`` / ``BlockedReason``) that keeps a non-executed frame's
justification stated and cross-checkable.
"""

from __future__ import annotations

from ._compare import (
    assert_transcript_matches_golden,
    check_transcript,
    compare_transcript_to_golden,
    evaluate_expectations,
)
from ._contracts import read_sequence_contract, sequence_contract_path
from ._golden_store import (
    REPO_ROOT_TOKEN,
    SANDBOX_STORAGE_ROOT_TOKEN,
    SANDBOX_WORKDIR_TOKEN,
    GoldenFrame,
    SequenceGolden,
    build_golden,
    default_goldens_root,
    golden_path,
    masked_envelope_values,
    normalise_document_paths,
    normalise_text_output,
    read_golden,
    refresh_invocation,
    write_golden,
)
from ._parser import parse_frame_lines, parse_sequence, result_frame_asserts_result_payload
from ._runner import (
    SANDBOX_INSTANT,
    SANDBOX_PROFILE_ID,
    SANDBOX_PROFILE_LABEL,
    CapturedValue,
    EnvelopeSource,
    FrameExecution,
    SequenceSandbox,
    SequenceTranscript,
    default_fixtures_root,
    execute_page_sequences,
    execute_sequence,
    sequence_sandbox,
)
from ._runner import _live_aeat_tokens as live_aeat_tokens
from ._runner import _refuse_live_frames as refuse_live_frames
from ._schema import (
    BlockedReason,
    CaptureBinding,
    ExpectAssertion,
    FrameKind,
    ParsedSequence,
    SequenceFrame,
    StaticBlocker,
)
from ._seeds import SEED_SUFFIX, default_seeds_root, load_seed_frames
from ._tokeniser import CommandToken, TokenKind, command_path_key, tokenise_command
from .checks import (
    COHERENCE_TIER_PREFIX,
    DiscoveredSequence,
    check_page_coherence,
    check_page_coherence_in_subprocess,
    check_sequences,
    check_sequences_in_subprocess,
    default_docs_root,
    discover_sequences,
    refresh_sequences,
)

__all__ = [
    "COHERENCE_TIER_PREFIX",
    "REPO_ROOT_TOKEN",
    "SANDBOX_INSTANT",
    "SANDBOX_PROFILE_ID",
    "SANDBOX_PROFILE_LABEL",
    "SANDBOX_STORAGE_ROOT_TOKEN",
    "SANDBOX_WORKDIR_TOKEN",
    "SEED_SUFFIX",
    "BlockedReason",
    "CaptureBinding",
    "CapturedValue",
    "CommandToken",
    "DiscoveredSequence",
    "EnvelopeSource",
    "ExpectAssertion",
    "FrameExecution",
    "FrameKind",
    "GoldenFrame",
    "ParsedSequence",
    "SequenceFrame",
    "SequenceGolden",
    "SequenceSandbox",
    "SequenceTranscript",
    "StaticBlocker",
    "TokenKind",
    "assert_transcript_matches_golden",
    "build_golden",
    "check_page_coherence",
    "check_page_coherence_in_subprocess",
    "check_sequences",
    "check_sequences_in_subprocess",
    "check_transcript",
    "command_path_key",
    "compare_transcript_to_golden",
    "default_docs_root",
    "default_fixtures_root",
    "default_goldens_root",
    "default_seeds_root",
    "discover_sequences",
    "evaluate_expectations",
    "execute_page_sequences",
    "execute_sequence",
    "golden_path",
    "live_aeat_tokens",
    "load_seed_frames",
    "masked_envelope_values",
    "normalise_document_paths",
    "normalise_text_output",
    "parse_frame_lines",
    "parse_sequence",
    "read_golden",
    "read_sequence_contract",
    "refresh_invocation",
    "refresh_sequences",
    "refuse_live_frames",
    "result_frame_asserts_result_payload",
    "sequence_contract_path",
    "sequence_sandbox",
    "tokenise_command",
    "write_golden",
]
