"""Production-door proofs for the descendant repeating-group editor."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput

from ....application.flows.errors import FlowRunAbandonedError
from ....application.wizard.descendant_door import run_descendant_door
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.serial]

_PROFILE_ID = "28282828-2828-4282-8282-282828282828"


@pytest.fixture
def isolated_profile(tmp_path: Path) -> TestRuntimeProfile:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        yield profile


def _run(record: Any, keys: str) -> tuple[Any, Any, Any, str]:
    output = StringIO()
    with create_pipe_input() as pipe:
        pipe.send_text(keys)
        pipe.close()
        state, projection, persisted = run_descendant_door(
            record,
            input=pipe,
            output=PlainTextOutput(output),
        )
    return state, projection, persisted, output.getvalue()


def _one_descendant_keys(*, birth_date: str = "2020-01-01") -> str:
    """Answer the visible one-row pages, accepting their safe defaults."""
    return "".join(
        (
            "1\r",
            f"{birth_date}\r",
            "\r",  # relación: first choice
            "\r",  # discapacidad: first choice
            "\r",  # fallecimiento: blank
            "\r",  # convivencia: default true
            "\r",  # custodia compartida: default false
            "\r",  # rentas anuales: blank
            "\r",  # declaración propia: default false
            "\x1b[B\r",  # prorrata mínimo: false
            "\r",  # meses de trabajo: blank
            "\r",  # alta posterior: blank
            "\r",  # gastos de guardería: blank
            "\r",  # gastos mensuales: blank
            "\r",  # nif: blank
            "\r",  # review: submit
        ),
    )


def _resume_missing_optional_answers() -> str:
    """Complete fields absent from a sparse persisted descendant record.

    The canonical fact projection deliberately omits unknown optional facts.
    A later production-door visit therefore asks only those absent pages before
    it reaches review; these enter keys preserve their empty/default meanings
    and make the subsequent review navigation deterministic.
    """
    return "\r" * 8


def _facts(record: Any) -> dict[str, str]:
    return {fact.path: str(fact.value) for fact in record.facts if fact.value is not None}


def test_happy_path_returns_and_persists_the_production_record(isolated_profile: TestRuntimeProfile) -> None:
    _state, projection, persisted, output = _run(None, _one_descendant_keys())

    facts = _facts(persisted)
    assert projection.submit_eligible
    assert facts["renta_family.descendientes_count"] == "1"
    assert facts["renta_family.descendiente.0.birth_date"] == "2020-01-01"
    assert persisted.record_revision > 0
    assert output


def test_edit_path_returns_the_updated_record(isolated_profile: TestRuntimeProfile) -> None:
    _state, _projection, created, _output = _run(None, _one_descendant_keys())

    # Sparse persisted facts leave optional answers unknown, so the production
    # door asks them before review. Then edit row 2 (the birth date) and submit.
    _state, projection, edited, _output = _run(
        created,
        _resume_missing_optional_answers() + "\x1b[B\r2\r\x152021-02-02\r\r",
    )

    assert projection.submit_eligible
    assert _facts(edited)["renta_family.descendiente.0.birth_date"] == "2021-02-02"
    assert edited.record_revision > created.record_revision


def test_restart_shrink_returns_a_record_without_orphaned_rows(isolated_profile: TestRuntimeProfile) -> None:
    _state, _projection, created, _output = _run(None, _one_descendant_keys())

    # Complete sparse optional answers -> review -> restart -> confirm ->
    # count zero -> submit. The second run proves the writer clears orphaned
    # indexed facts from the record currently stored by the first run.
    _state, projection, shrunk, _output = _run(
        created,
        _resume_missing_optional_answers() + "\x1b[B\x1b[B\ry\r0\r\r",
    )

    facts = _facts(shrunk)
    assert projection.submit_eligible
    assert facts["renta_family.descendientes_count"] == "0"
    assert not any(path.startswith("renta_family.descendiente.") for path in facts)
    assert shrunk.record_revision > created.record_revision


def test_abandoned_edit_refuses_before_the_atomic_write(isolated_profile: TestRuntimeProfile) -> None:
    _state, _projection, created, _output = _run(None, _one_descendant_keys())
    before = _facts(created)
    before_revision = created.record_revision

    with pytest.raises(FlowRunAbandonedError) as excinfo:
        _run(
            created,
            _resume_missing_optional_answers() + "\x1b[B\r2\r\x03",
        )

    assert excinfo.value.translated_message == "errors.refused.refused_flow_run_abandoned"
    assert _facts(created) == before
    assert created.record_revision == before_revision
