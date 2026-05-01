"""Unit tests for individual healing strategies."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from . import (
    AdditiveAllowlistStrategy,
    BenignRecordStrategy,
    CasillaAddedWithDefault,
    DivergenceClassification,
    DivergenceKind,
    DivergenceRecord,
    EscalateStrategy,
    FilingStatusChanged,
    FormulaChanged,
    ModeloIdentifier,
    ResolutionState,
    StrategyAction,
)
from ._divergence import classify_kind

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _record(payload, classification: DivergenceClassification) -> DivergenceRecord:
    return DivergenceRecord(
        record_id=uuid.uuid4().hex,
        detected_at=datetime.now(tz=UTC),
        modelo=ModeloIdentifier("100"),
        classification=classification,
        payload=payload,
    )


@pytest.mark.asyncio
async def test_additive_allowlist_auto_heals() -> None:
    payload = CasillaAddedWithDefault(
        modelo=ModeloIdentifier("100"),
        casilla_id="C9",
        default="0",
        label={"es": "x", "en": "x", "hu": "x"},
    )
    record = _record(payload, DivergenceClassification.ADDITIVE)
    strategy = AdditiveAllowlistStrategy(allowlist=frozenset({DivergenceKind.CASILLA_ADDED_WITH_DEFAULT}))
    outcome = await strategy.apply(record, auto_heal=True)
    assert outcome.action == StrategyAction.AUTO_HEALED
    assert outcome.record.resolution_state == ResolutionState.AUTO_HEALED


@pytest.mark.asyncio
async def test_additive_allowlist_refuses_without_auto_heal_flag() -> None:
    payload = CasillaAddedWithDefault(
        modelo=ModeloIdentifier("100"),
        casilla_id="C9",
        default="0",
        label={"es": "x"},
    )
    record = _record(payload, DivergenceClassification.ADDITIVE)
    strategy = AdditiveAllowlistStrategy(allowlist=frozenset({DivergenceKind.CASILLA_ADDED_WITH_DEFAULT}))
    outcome = await strategy.apply(record, auto_heal=False)
    assert outcome.action == StrategyAction.ESCALATED
    assert outcome.record.resolution_state == ResolutionState.PENDING


@pytest.mark.asyncio
async def test_additive_allowlist_refuses_non_allowlisted_kind() -> None:
    payload = CasillaAddedWithDefault(
        modelo=ModeloIdentifier("100"),
        casilla_id="C9",
        default="0",
        label={"es": "x"},
    )
    record = _record(payload, DivergenceClassification.ADDITIVE)
    strategy = AdditiveAllowlistStrategy(allowlist=frozenset())
    outcome = await strategy.apply(record, auto_heal=True)
    assert outcome.action == StrategyAction.ESCALATED


@pytest.mark.asyncio
async def test_escalate_always_escalates() -> None:
    payload = FormulaChanged(
        modelo=ModeloIdentifier("100"),
        casilla_id="C1",
        previous_formula="A+B",
        new_formula="A-B",
    )
    record = _record(payload, DivergenceClassification.BREAKING)
    outcome = await EscalateStrategy().apply(record, auto_heal=True)
    assert outcome.action == StrategyAction.ESCALATED
    assert outcome.record.resolution_state == ResolutionState.PENDING


@pytest.mark.asyncio
async def test_benign_records_only() -> None:
    payload = FilingStatusChanged(
        modelo=ModeloIdentifier("303"),
        period="2024Q1",
        previous_status="PENDING",
        new_status="ACCEPTED",
    )
    record = _record(payload, classify_kind(payload.kind))
    outcome = await BenignRecordStrategy().apply(record, auto_heal=False)
    assert outcome.action == StrategyAction.RECORDED
    assert outcome.record.resolution_state == ResolutionState.AUTO_HEALED
