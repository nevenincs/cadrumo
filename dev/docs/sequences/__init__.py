"""The ``cli-sequence`` documentation execution engine (docs tooling).

This package is the one hermetic engine behind the ``cli-sequence`` MyST
directive: it parses a directive body into typed frames, executes each frame in a
per-sequence sandbox, compares the result against a committed golden, and drives
the refresh / check CLI. It lives under ``dev/docs`` (docs tooling per the
tooling-separation ADR) and imports the production ``cadrumo`` package from
outside.

This module exposes the frame-grammar parser (ADR rulings D1 / D4), the
``:seed:`` recipe loader (ADR D6), the per-sequence hermetic sandbox runner
with ``@capture`` threading (ADR D6 / D3), the committed golden store (ADR D2),
and the golden comparison plus ``@expect`` evaluation tier (ADR D3 / D4). The
refresh/check CLI lands in the next phase and extends this facade.
"""

from __future__ import annotations

from ._compare import (
    assert_transcript_matches_golden,
    check_transcript,
    compare_transcript_to_golden,
    evaluate_expectations,
)
from ._errors import (
    SequenceEngineError,
    SequenceExecutionError,
    SequenceGoldenError,
    SequenceGoldenMismatchError,
    SequenceParseError,
)
from ._golden_store import (
    SANDBOX_STORAGE_ROOT_TOKEN,
    SANDBOX_WORKDIR_TOKEN,
    GoldenFrame,
    SequenceGolden,
    build_golden,
    default_goldens_root,
    golden_path,
    masked_envelope_values,
    normalise_text_output,
    read_golden,
    refresh_invocation,
    write_golden,
)
from ._parser import parse_frame_lines, parse_sequence
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
    execute_sequence,
    sequence_sandbox,
)
from ._schema import (
    CaptureBinding,
    ExpectAssertion,
    FrameKind,
    ParsedSequence,
    SequenceFrame,
)
from ._seeds import SEED_SUFFIX, default_seeds_root, load_seed_frames

__all__ = [
    "SANDBOX_INSTANT",
    "SANDBOX_PROFILE_ID",
    "SANDBOX_PROFILE_LABEL",
    "SANDBOX_STORAGE_ROOT_TOKEN",
    "SANDBOX_WORKDIR_TOKEN",
    "SEED_SUFFIX",
    "CaptureBinding",
    "CapturedValue",
    "EnvelopeSource",
    "ExpectAssertion",
    "FrameExecution",
    "FrameKind",
    "GoldenFrame",
    "ParsedSequence",
    "SequenceEngineError",
    "SequenceExecutionError",
    "SequenceFrame",
    "SequenceGolden",
    "SequenceGoldenError",
    "SequenceGoldenMismatchError",
    "SequenceParseError",
    "SequenceSandbox",
    "SequenceTranscript",
    "assert_transcript_matches_golden",
    "build_golden",
    "check_transcript",
    "compare_transcript_to_golden",
    "default_fixtures_root",
    "default_goldens_root",
    "default_seeds_root",
    "evaluate_expectations",
    "execute_sequence",
    "golden_path",
    "load_seed_frames",
    "masked_envelope_values",
    "normalise_text_output",
    "parse_frame_lines",
    "parse_sequence",
    "read_golden",
    "refresh_invocation",
    "sequence_sandbox",
    "write_golden",
]
