"""Internal live-submit confirmation hook."""

from __future__ import annotations

import os
import sys
from typing import TextIO

from aeat.submission._errors import (
    AeatLiveSubmitConfirmationRefusedError,
    AeatPytestLiveWriteRefusedError,
)
from aeat.submission._protocols import FilingDraftLike


def confirm_live_submission(
    *,
    draft: FilingDraftLike,
    draft_checksum_sha256: str,
    stdin: TextIO | None = None,
    stderr: TextIO | None = None,
) -> None:
    """Require the exact live-submit confirmation phrase from the operator."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        raise AeatPytestLiveWriteRefusedError("live submission confirmation is unavailable under pytest")

    input_stream = stdin or sys.stdin
    error_stream = stderr or sys.stderr
    expected_phrase = f"CONFIRMO FILING {draft.modelo} {draft.period}"

    print("LIVE AEAT submission requested.", file=error_stream)
    print(f"modelo={draft.modelo} period={draft.period} draft_id={draft.draft_id}", file=error_stream)
    print(f"draft_checksum_sha256={draft_checksum_sha256}", file=error_stream)
    print(f"type exactly: {expected_phrase}", file=error_stream)
    error_stream.flush()

    if input_stream.readline().strip() != expected_phrase:
        raise AeatLiveSubmitConfirmationRefusedError("live submission confirmation phrase did not match")
