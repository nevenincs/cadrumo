"""Real line-mode descendant-door walks over the encrypted profile record."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput

from ....application.flows._line_frontend import LineFlowFrontend
from ....application.flows._review import ReviewProjection
from ....application.wizard._descendant_door import (
    build_descendant_door,
    build_descendant_door_definition,
    persist_descendant_door_answers,
)
from ....application.wizard._persistence import descendant_facts_from_answers
from ....application.user_profile._profile_record_repository import ProfileRecordRepository
from ....application.user_profile._projections import record_to_path_values
from ....core.flows import FlowMode
from ....tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "38383838-3838-4383-8383-383838383838"


def _line_run(
    definition,
    keystrokes: str,
    *,
    resume_state=None,
) -> tuple[object, ReviewProjection]:
    """Drive the real line frontend through prompt-toolkit pipe IO."""
    with create_pipe_input() as pipe:
        pipe.send_text(keystrokes)
        frontend = LineFlowFrontend(
            definition,
            input=pipe,
            output=PlainTextOutput(StringIO()),
        )
        return frontend.run(mode=FlowMode.MODIFY, resume_state=resume_state)


def test_descendant_line_walk_seeds_resumes_converts_and_persists(tmp_path: Path) -> None:
    """A submitted line walk reaches the canonical descendant fact writer.

    The first walk answers one complete row through the actual line frontend.
    The record is then read back, projected into the door's page-keyed seed,
    resumed through the engine, and submitted once more from review.  The
    assertions use the encrypted record and the real conversion output rather
    than the frontend's echoed state alone.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        definition = build_descendant_door_definition()
        # Count, birth date, the ordinary first relationship, and the optional
        # pages' honest defaults/empty answers; the final enter submits review.
        keystrokes = "1\r2020-01-01\r" + "\r" * 14 + "\r"
        state, projection = _line_run(definition, keystrokes)

        assert projection.submit_eligible
        converted = dict(descendant_facts_from_answers(state.answers))
        assert converted["renta_family.descendiente.0.birth_date"] == "2020-01-01"
        assert converted["renta_family.descendientes_count"] == "1"

        persist_descendant_door_answers(state.answers)
        stored = ProfileRecordRepository.for_current_session(profile.bucket_id).load(profile.bucket_id)
        stored_values = record_to_path_values(stored)
        assert stored_values["renta_family.descendiente.0.birth_date"] == "2020-01-01"
        assert stored_values["renta_family.descendientes_count"] == "1"

        resumed_definition, resumed = build_descendant_door(stored)
        assert resumed.answers["descendientes-count"] == "1"
        assert resumed.answers["descendientes#0.birth-date"] == "2020-01-01"
        assert resumed.instance_counts["descendientes"] == 1

        resumed_state, resumed_projection = _line_run(
            resumed_definition,
            "\r",  # submit the already-seeded state from the review menu
            resume_state=resumed,
        )
        assert resumed_projection.submit_eligible
        assert resumed_state.answers == resumed.answers


def test_descendant_line_refusal_and_abandonment_leave_profile_unchanged(tmp_path: Path) -> None:
    """A failing answer followed by Ctrl-C never reaches the persistence door."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        definition = build_descendant_door_definition()
        with create_pipe_input() as pipe:
            pipe.send_text("1\rnot-a-date\r\x03")
            frontend = LineFlowFrontend(
                definition,
                input=pipe,
                output=PlainTextOutput(StringIO()),
            )
            from ....application.flows._errors import FlowRunAbandonedError

            with pytest.raises(FlowRunAbandonedError) as excinfo:
                frontend.run(mode=FlowMode.MODIFY)

        assert excinfo.value.translated_message == "errors.refused.refused_flow_run_abandoned"
        record = ProfileRecordRepository.for_current_session(profile.bucket_id).load(profile.bucket_id)
        assert not any(fact.path.startswith("renta_family.descendiente") for fact in record.facts)

