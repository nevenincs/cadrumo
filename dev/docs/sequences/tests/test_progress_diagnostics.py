"""Real child-process proofs for bounded sequence-check diagnostics."""

from __future__ import annotations

import sys

import pytest

from cadrumo.tests.env_scope import scoped_env_var

from ..__main__ import _run_check_child
from .._errors import SequenceEngineError

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]


def test_timed_out_child_names_the_last_runtime_frame() -> None:
    """The actual child-to-parent journal names its parsed page, sequence and frame.

    The child uses the production parser and runner recorder, then stays alive
    beyond the same timeout the parent passes to ``subprocess.run``.  No test
    double stands in for either process boundary or the progress journal.
    """
    timeout = 5.0
    child = "\n".join(
        (
            "import os",
            "import time",
            "from dev.docs.sequences._parser import parse_sequence",
            "from dev.docs.sequences._runner import _record_frame_progress, _sequence_progress_scope",
            "sequence = parse_sequence(",
            "    sequence_id='progress-timeout',",
            "    options={'verify': 'Verify the listing.'},",
            "    body='@result aeat --format json config profile list\\n@expect exit_code == 0\\n',",
            ")",
            "frame = sequence.executed_frames[0]",
            "with _sequence_progress_scope('how-to/progress-diagnostics'):",
            "    _record_frame_progress(sequence, frame, frame_index=0, argv=frame.argv)",
            "time.sleep(float(os.environ['SEQUENCE_PROGRESS_TEST_SLEEP']))",
        ),
    )
    with scoped_env_var("SEQUENCE_PROGRESS_TEST_SLEEP", str(timeout * 2)), pytest.raises(SequenceEngineError) as raised:
        _run_check_child([sys.executable, "-c", child], timeout=timeout)

    message = str(raised.value)
    assert "how-to/progress-diagnostics" in message
    assert "progress-timeout" in message
    assert "frame 0" in message
    assert "body line 1" in message
    assert "aeat --format json config profile list" in message
