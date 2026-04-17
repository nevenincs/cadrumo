"""The bounded auto-heal invariant test suite.

This is the single most important correctness test in the feature.
Every non-allowlisted divergence kind MUST escalate — even when the
dispatcher is invoked with ``auto_heal=True`` — and every BREAKING
and SUSPICIOUS kind MUST escalate regardless of classification.

The test is parametrised across every ``DivergenceKind`` so that
adding a new kind automatically picks up coverage.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from . import (
    AdditiveAllowlistStrategy,
    BenignRecordStrategy,
    CasillaAddedWithDefault,
    CasillaRemoved,
    CasillaTypeChanged,
    DivergenceClassification,
    DivergenceKind,
    DivergencePayload,
    DivergenceRecord,
    EscalateStrategy,
    FilingStatusChanged,
    FormulaChanged,
    HealingDispatcher,
    LabelEsChanged,
    LabelTranslationAdded,
    ModeloIdentifier,
    PortalUrlChanged,
    ResolutionState,
    StrategyAction,
    UnknownShape,
    VigenciaExtended,
)
from ._divergence import classify_kind

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]

# Starting operator allowlist from the ADR.
DEFAULT_ALLOWLIST: frozenset[DivergenceKind] = frozenset(
    {
        DivergenceKind.CASILLA_ADDED_WITH_DEFAULT,
        DivergenceKind.LABEL_TRANSLATION_ADDED,
        DivergenceKind.VIGENCIA_EXTENDED,
    }
)


def _payload_for(kind: DivergenceKind) -> DivergencePayload:
    match kind:
        case DivergenceKind.CASILLA_ADDED_WITH_DEFAULT:
            return CasillaAddedWithDefault(
                modelo=ModeloIdentifier("100"),
                casilla_id="C9",
                default="0",
                label={"es": "x"},
            )
        case DivergenceKind.LABEL_TRANSLATION_ADDED:
            return LabelTranslationAdded(
                modelo=ModeloIdentifier("100"),
                casilla_id="C1",
                language="hu",
                value="Alap",
            )
        case DivergenceKind.VIGENCIA_EXTENDED:
            return VigenciaExtended(
                modelo=ModeloIdentifier("100"),
                previous_end=date(2024, 12, 31),
                new_end=date(2025, 6, 30),
            )
        case DivergenceKind.CASILLA_REMOVED:
            return CasillaRemoved(modelo=ModeloIdentifier("100"), casilla_id="C1")
        case DivergenceKind.CASILLA_TYPE_CHANGED:
            return CasillaTypeChanged(
                modelo=ModeloIdentifier("100"),
                casilla_id="C1",
                previous_type="decimal",
                new_type="text",
            )
        case DivergenceKind.FORMULA_CHANGED:
            return FormulaChanged(
                modelo=ModeloIdentifier("100"),
                casilla_id="C1",
                previous_formula="A+B",
                new_formula="A-B",
            )
        case DivergenceKind.LABEL_ES_CHANGED:
            return LabelEsChanged(
                modelo=ModeloIdentifier("100"),
                casilla_id="C1",
                previous_es="Base",
                new_es="Importe",
            )
        case DivergenceKind.PORTAL_URL_CHANGED:
            return PortalUrlChanged.model_validate(
                {
                    "portal": "sede",
                    "previous_url": "https://sede.agenciatributaria.gob.es/a",
                    "new_url": "https://sede.agenciatributaria.gob.es/b",
                }
            )
        case DivergenceKind.FILING_STATUS_CHANGED:
            return FilingStatusChanged(
                modelo=ModeloIdentifier("303"),
                period="2024Q1",
                previous_status="PENDING",
                new_status="ACCEPTED",
            )
        case DivergenceKind.UNKNOWN_SHAPE:
            return UnknownShape(detail="synthetic")


def _record_for(kind: DivergenceKind) -> DivergenceRecord:
    payload = _payload_for(kind)
    return DivergenceRecord(
        record_id=uuid.uuid4().hex,
        detected_at=datetime.now(tz=UTC),
        modelo=ModeloIdentifier("100"),
        classification=classify_kind(kind),
        payload=payload,
    )


def _dispatcher(allowlist: frozenset[DivergenceKind]) -> HealingDispatcher:
    return HealingDispatcher(
        strategies=(
            BenignRecordStrategy(),
            AdditiveAllowlistStrategy(allowlist=allowlist),
            EscalateStrategy(),
        ),
        auto_heal_allowlist=allowlist,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", list(DivergenceKind))
async def test_non_allowlisted_kind_always_escalates_even_with_auto_heal(
    kind: DivergenceKind,
) -> None:
    """Any kind not in the allowlist MUST escalate even with auto_heal=True.

    Benign kinds (e.g. filing_status_changed) are ``RECORDED`` rather
    than escalated — still not ``AUTO_HEALED``, which is what the
    invariant protects.
    """
    record = _record_for(kind)
    dispatcher = _dispatcher(frozenset())  # empty allowlist
    plan, outcomes = await dispatcher.dispatch((record,), auto_heal=True)
    [outcome] = outcomes
    assert outcome.action != StrategyAction.AUTO_HEALED
    assert plan.auto_heal == ()
    if record.classification == DivergenceClassification.BENIGN:
        assert outcome.action == StrategyAction.RECORDED
    else:
        assert outcome.action == StrategyAction.ESCALATED
        assert outcome.record.resolution_state == ResolutionState.PENDING


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", list(DivergenceKind))
async def test_breaking_and_suspicious_kinds_always_escalate_with_full_allowlist(
    kind: DivergenceKind,
) -> None:
    """Even if the operator adds every kind to the allowlist, BREAKING
    and SUSPICIOUS must still escalate.
    """
    record = _record_for(kind)
    dispatcher = _dispatcher(frozenset(DivergenceKind))  # full allowlist
    _plan, outcomes = await dispatcher.dispatch((record,), auto_heal=True)
    [outcome] = outcomes
    if record.classification in {
        DivergenceClassification.BREAKING,
        DivergenceClassification.SUSPICIOUS,
    }:
        assert outcome.action == StrategyAction.ESCALATED
        assert outcome.record.resolution_state == ResolutionState.PENDING
    elif record.classification == DivergenceClassification.ADDITIVE:
        assert outcome.action == StrategyAction.AUTO_HEALED
    else:
        assert record.classification == DivergenceClassification.BENIGN
        assert outcome.action == StrategyAction.RECORDED


@pytest.mark.asyncio
async def test_default_allowlist_only_applies_to_additive_kinds() -> None:
    dispatcher = _dispatcher(DEFAULT_ALLOWLIST)
    for kind in DivergenceKind:
        record = _record_for(kind)
        _plan, outcomes = await dispatcher.dispatch((record,), auto_heal=True)
        [outcome] = outcomes
        if kind in DEFAULT_ALLOWLIST:
            assert outcome.action == StrategyAction.AUTO_HEALED
        elif record.classification == DivergenceClassification.BENIGN:
            assert outcome.action == StrategyAction.RECORDED
        else:
            assert outcome.action == StrategyAction.ESCALATED
