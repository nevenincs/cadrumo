"""The ``cli-sequence`` documentation execution engine (docs tooling).

This package is the one hermetic engine behind the ``cli-sequence`` MyST
directive: it parses a directive body into typed frames, executes each frame in a
per-sequence sandbox, compares the result against a committed golden, and drives
the refresh / check CLI. It lives under ``dev/docs`` (docs tooling per the
tooling-separation ADR) and imports the production ``cadrumo`` package from
outside.

This module exposes the frame-grammar parser (ADR rulings D1 / D4), the
``:seed:`` recipe loader (ADR D6), and the per-sequence hermetic sandbox runner
with ``@capture`` threading (ADR D6 / D3). The golden store, comparison, and
CLI land in later phases and extend this facade.
"""

from __future__ import annotations

from ._errors import SequenceEngineError, SequenceExecutionError, SequenceParseError
from ._parser import parse_frame_lines, parse_sequence
from ._runner import (
    SANDBOX_INSTANT,
    SANDBOX_PROFILE_ID,
    SANDBOX_PROFILE_LABEL,
    CapturedValue,
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
    "SEED_SUFFIX",
    "CaptureBinding",
    "CapturedValue",
    "ExpectAssertion",
    "FrameExecution",
    "FrameKind",
    "ParsedSequence",
    "SequenceEngineError",
    "SequenceExecutionError",
    "SequenceFrame",
    "SequenceParseError",
    "SequenceSandbox",
    "SequenceTranscript",
    "default_fixtures_root",
    "default_seeds_root",
    "execute_sequence",
    "load_seed_frames",
    "parse_frame_lines",
    "parse_sequence",
    "sequence_sandbox",
]
