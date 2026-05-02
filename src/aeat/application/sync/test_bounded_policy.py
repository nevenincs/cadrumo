"""Bounded auto-heal invariant suite for the sync healing dispatcher.

Encodes the safety invariant for
:class:`aeat.application.sync.HealingDispatcher`: every non-allowlisted
:class:`aeat.domain.sync.DivergenceKind` must escalate even when
``auto_heal=True``, and every breaking or suspicious kind must escalate
regardless of the allowlist. The suite is parametrised across the full
:class:`aeat.domain.sync.DivergenceKind` enum so that adding a new kind
automatically picks up coverage and a regression in either invariant
fails the build.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from ...domain.sync import (
    CasillaAddedWithDefault,
    CasillaRemoved,
    CasillaTypeChanged,
    DivergenceClassification,
    DivergenceKind,
    DivergencePayload,
    DivergenceRecord,
    FilingStatusChanged,
    FormulaChanged,
    LabelEsChanged,
    LabelTranslationAdded,
    ModeloIdentifier,
    PortalUrlChanged,
    ResolutionState,
    UnknownShape,
    VigenciaExtended,
    classify_kind,
)
from . import (
    AdditiveAllowlistStrategy,
    BenignRecordStrategy,
    EscalateStrategy,
    HealingDispatcher,
    StrategyAction,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

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
    """Verify that any non-allowlisted kind never auto-heals.

    Benign kinds (such as ``filing_status_changed``) are recorded rather
    than escalated, but neither path produces an
    :attr:`aeat.application.sync.StrategyAction.AUTO_HEALED` outcome — the
    invariant protected here is that auto-healing requires explicit
    operator opt-in via the allowlist.
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
    """Verify breaking and suspicious kinds escalate against a full allowlist.

    Even when the operator adds every
    :class:`aeat.domain.sync.DivergenceKind` to the allowlist, kinds whose
    classification is :attr:`aeat.domain.sync.DivergenceClassification.BREAKING`
    or :attr:`aeat.domain.sync.DivergenceClassification.SUSPICIOUS` must
    still escalate — the allowlist gates only additive kinds.
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
    """Verify the default allowlist auto-heals additive kinds only."""
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
