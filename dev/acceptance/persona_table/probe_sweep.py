"""Collector of the verify probe: verifies each owed return once, before the persona's statements are entered.

This module is not a test of the suite. ``python -m dev.acceptance.persona_table probe``
names it explicitly to pytest, which collects it in spite of its name; the
suite never does. Each case replays one persona under one horizon exactly as the table does, through the
table's planner and its return sequence. Before a selected owed return's first calculation, which is where the
table enters the persona's work inputs, the probe calculates it without them and verifies it once, then lets the
table's own sequence run, so the returns that follow find the world the table gives them. It appends one JSON line
per probed return to the file ``PERSONA_PROBE_OUT`` names.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from typing import override

import pytest
from pydantic import BaseModel

from cadrumo.application.modelo.operation_shared import (
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from cadrumo.application.modelo.work_calculation_contracts import ModeloWorkCalculatePublicResultV3
from cadrumo.application.modelo.work_verification_contracts import ModeloWorkVerifyRequest
from cadrumo.core.logging import flush_logging
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import (
    PERSONA_ACTOR,
    PersonaWorld,
    materialised_persona,
    settle_operation,
    year_envelope,
)
from cadrumo.tests.personas import YearEnvelope, read_persona

from .probe import EXECUTOR_LOGGER, PROBE_OUT_ENV, ProbeLine, classify
from .rows import PlannedRow
from .sweep import PreparedReturn, cases, plan_rows, replay_scope, run_return, stated_values

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@cache
def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


class _FailureRecords(logging.Handler):
    """The supervisor's records of failed operations, which name the exception a failure serves no sentence for."""

    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.messages: list[str] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@contextmanager
def _failure_records() -> Generator[_FailureRecords]:
    """Collect the supervisor's failure records of the operations settled inside the block, delivered by its end."""
    handler = _FailureRecords()
    logger = logging.getLogger(EXECUTOR_LOGGER)
    logger.addHandler(handler)
    try:
        yield handler
        flush_logging()
    finally:
        logger.removeHandler(handler)


def _observed(
    world: PersonaWorld, definition_id: str, payload: BaseModel, *, subject: str
) -> tuple[BaseModel | Exception, str]:
    """What one operation settled to, or the exception that stopped it, with the supervisor's record of a failure."""
    with _failure_records() as records:
        try:
            result: BaseModel | Exception = settle_operation(
                world, definition_id, payload, subject=subject
            ) or RuntimeError("no public result")
        except Exception as error:
            result = error
    return result, records.messages[-1] if records.messages else ""


def probe_return(world: PersonaWorld, plan: PlannedRow, prepared: PreparedReturn) -> ProbeLine:
    """Calculate the prepared return with nothing more stated, verify it once and classify the answer.

    The calculation uses the request the table builds, so the carries and evidence it states beforehand stand,
    but it is submitted without the persona's work inputs, which only the table's calculate operation enters.
    """
    unit = prepared.work_unit_id
    stage = "calculate"
    observed, failure = _observed(world, MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID, prepared.request, subject=unit)
    if isinstance(observed, ModeloWorkCalculatePublicResultV3):
        stage = "verify"
        observed, failure = _observed(
            world,
            MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
            ModeloWorkVerifyRequest(calculation_revision_id=observed.calculation_revision_id, actor=PERSONA_ACTOR),
            subject=unit,
        )
    answer = classify(stage, observed, failure=failure)
    return ProbeLine(
        persona=plan.persona,
        modelo=plan.modelo,
        year=plan.year,
        period=plan.period,
        horizon=plan.horizon,
        stage=stage,
        outcome=answer.outcome,
        code=answer.code,
        message=answer.message,
        raised_in=answer.raised_in,
        owner=answer.owner,
    )


def _append(path: Path, line: ProbeLine) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line.to_json() + "\n")


def _probing(out: Path, world: PersonaWorld, plan: PlannedRow) -> Callable[[PreparedReturn], None]:
    """The hook that probes ``plan`` once its return is prepared and appends the line to ``out``."""

    def probe(prepared: PreparedReturn) -> None:
        _append(out, probe_return(world, plan, prepared))

    return probe


@pytest.mark.parametrize(("persona_id", "horizon"), cases())
def test_persona_probe(tmp_path: Path, persona_id: str, horizon: int) -> None:
    """Replay one persona under one horizon and append a probe line for each selected owed return."""
    out = Path(os.environ[PROBE_OUT_ENV])
    plans, emitted = plan_rows(persona_id, horizon)
    persona = read_persona(persona_id, envelope=_envelope())
    with materialised_persona(persona_id, tmp_path, replay_scope(persona), reuse=True, horizon=horizon) as materialised:
        for plan in plans:
            values = stated_values(materialised.persona, materialised.world.envelope, plan)
            probed = plan.key in emitted and plan.owed
            run_return(
                materialised,
                plan,
                values,
                tmp_path / "exports",
                before_calculate=_probing(out, materialised.world, plan) if probed else None,
            )
