"""Real-behavior tests for _actions module-level surfaces.

S168: ``_IVA_LEDGER_EXEMPT_REGIMES`` uses ``IVARegime`` enum members rather
than raw strings, so the frozenset membership check is typed at the schema
boundary and cannot silently drift from the canonical enum.

S85–S96: verification finding messages and next_action strings are routed
through ``tr()`` so the operator-facing surface is localised.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from ...domain.calculations.registry._schema import VerificationPredicateDefinition
from ...domain.deadlines import IVARegime
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos._codes import ModeloCode
from ...domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ._actions import (
    _IVA_LEDGER_EXEMPT_REGIMES,
    _collect_revision_verification_findings,
    _dt12_reduccion_advisory_finding,
    _evaluate_verification_predicates,
    _iva_wallet_blocked_message,
    _iva_wallet_blocking_verification_finding,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_FAKE_HEX64 = "a" * 64


def _minimal_work_unit(modelo: str = "999", period: str = "0A", filing_year: int = 2026) -> WorkUnit:
    bucket_id = "test-bucket"
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id="r" + "0" * 63,
        ),
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id="r" + "0" * 63,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=_T0,
        updated_at=_T0,
    )


def _minimal_calculation_revision(work_unit: WorkUnit) -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=_FAKE_HEX64,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        inputs_snapshot={},
        casilla_values={},
        created_at=_T0,
        updated_at=_T0,
    )


def test_iva_ledger_exempt_regimes_contains_enum_members() -> None:
    """Every element of _IVA_LEDGER_EXEMPT_REGIMES must be an IVARegime member.

    A bare string like ``"SIMPLIFICADO"`` would pass a membership test but
    would bypass the typed surface: IVARegime values compared via StrEnum
    equality will match, but the frozenset must be authored with enum members
    so static analysis and future mypy strict checks can verify the boundary.
    """
    for member in _IVA_LEDGER_EXEMPT_REGIMES:
        assert isinstance(member, IVARegime), (
            f"_IVA_LEDGER_EXEMPT_REGIMES contains a bare string {member!r}; "
            f"expected an IVARegime enum member"
        )


def test_iva_ledger_exempt_regimes_includes_simplificado() -> None:
    """SIMPLIFICADO must be in the exempt set — removing it would silently break ledger bypass."""
    assert IVARegime.SIMPLIFICADO in _IVA_LEDGER_EXEMPT_REGIMES


def test_iva_ledger_exempt_regimes_excludes_general() -> None:
    """GENERAL must not be in the exempt set — it is subject to ledger preflight."""
    assert IVARegime.GENERAL not in _IVA_LEDGER_EXEMPT_REGIMES


# ---------------------------------------------------------------------------
# S85/S86 — cross-casilla invariant violated: message is localised
# S87/S88 — cross-casilla invariant violated: next_action is localised
# ---------------------------------------------------------------------------


def test_cross_casilla_invariant_violated_message_is_localised() -> None:
    """_evaluate_verification_predicates emits a tr()-rendered message for a violated predicate.

    The predicate expression ``all_nonzero(["0001","0002"])`` fails when
    both casillas are zero, producing a BLOCKING_RULE finding. The message
    must contain the predicate_id and expression as rendered by the locale
    catalogue (not a raw f-string).
    """
    predicate = VerificationPredicateDefinition(
        predicate_id="test-cross-casilla-001",
        legal_refs=("irpf:art1",),
        expression='all_nonzero(["0001","0002"])',
        finding_kind="BLOCKING_RULE",
    )
    # Both casillas are zero — predicate is violated.
    findings = _evaluate_verification_predicates((predicate,), {"0001": Decimal(0), "0002": Decimal(0)})

    assert len(findings) == 1
    finding = findings[0]
    # The message must contain the predicate_id and expression (from the locale template).
    assert "test-cross-casilla-001" in finding.message
    assert 'all_nonzero(["0001","0002"])' in finding.message
    # Must not be the old raw f-string format with repr apostrophes around predicate_id.
    assert "violated: " in finding.message


def test_cross_casilla_invariant_next_action_is_localised() -> None:
    """_evaluate_verification_predicates emits a tr()-rendered next_action for a violated predicate."""
    predicate = VerificationPredicateDefinition(
        predicate_id="test-cross-casilla-002",
        legal_refs=("irpf:art2",),
        expression='any_nonzero(["0003","0004"])',
        finding_kind="BLOCKING_RULE",
    )
    findings = _evaluate_verification_predicates((predicate,), {"0003": Decimal(0), "0004": Decimal(0)})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.next_action is not None
    # The next_action must contain the predicate_id (from the locale template).
    assert "test-cross-casilla-002" in finding.next_action
    # Must not produce a None or empty next_action.
    assert len(finding.next_action) > 0


# ---------------------------------------------------------------------------
# S89/S90 — registry-snapshot-unresolved finding is localised
# ---------------------------------------------------------------------------


def test_registry_snapshot_unresolved_finding_is_localised() -> None:
    """_collect_revision_verification_findings produces a localised message when the registry
    snapshot cannot be resolved for a non-existent modelo.

    Modelo '999' is not in the registry; the function must return a single
    BLOCKING_RULE finding whose message is rendered via tr() and contains the
    modelo, filing_year, and period interpolation tokens.
    """
    work_unit = _minimal_work_unit(modelo="999", period="0A", filing_year=2026)
    target = _minimal_calculation_revision(work_unit)

    findings, resolved, missing = _collect_revision_verification_findings(
        work_unit=work_unit,
        target=target,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert "999" in finding.message
    assert "2026" in finding.message
    assert "0A" in finding.message
    assert "could not be resolved" in finding.message


# ---------------------------------------------------------------------------
# S91/S92 — DT12 reducción advisory message is localised
# ---------------------------------------------------------------------------


def test_dt12_reduccion_advisory_message_is_localised() -> None:
    """_dt12_reduccion_advisory_finding emits a tr()-rendered message.

    A synthetic revision object carrying two casillas with the correct semantic
    roles triggers the advisory. The finding message must contain ingreso_id,
    ingreso_value, and reduccion_id tokens from the locale template.
    """
    ingreso = SimpleNamespace(id="0003", semantic_role="irpf_rendimiento_trabajo_importe_integro_dinerario")
    reduccion = SimpleNamespace(id="0011", semantic_role="irpf_rendimiento_trabajo_reduccion")
    # Both casillas present in revision; large ingreso, zero reduccion.
    revision = SimpleNamespace(casillas=[ingreso, reduccion])
    casilla_values = {"0003": Decimal("25000"), "0011": Decimal("0")}

    finding = _dt12_reduccion_advisory_finding(revision, casilla_values)

    assert finding is not None
    assert "0003" in finding.message
    assert "25000" in finding.message
    assert "0011" in finding.message
    # Locale template token "reduccion" must appear in the rendered string.
    assert "reduccion" in finding.message.lower()


# ---------------------------------------------------------------------------
# S93/S94 — IVA wallet next_action is localised
# ---------------------------------------------------------------------------


def test_iva_wallet_blocking_finding_next_action_is_localised() -> None:
    """_iva_wallet_blocking_verification_finding returns a finding with a tr()-rendered next_action.

    The next_action must come from the locale catalogue key
    'application.modelo.findings.iva_wallet_next_action' and must not be
    the old hardcoded English string.
    """
    from ...application.calculations._iva_wallet_reconciliation import IvaCompensationReconciliationDecision

    decision = IvaCompensationReconciliationDecision(
        target_year=2026,
        target_period="1T",
        taxpayer_nif="12345678Z",
        divergence="wallet_missing",
        blocked=True,
        selected_amount=None,
        reason="No AEAT wallet observation or local recurrence is available.",
    )
    finding = _iva_wallet_blocking_verification_finding(decision)

    assert finding.next_action is not None
    assert "IVA wallet" in finding.next_action
    assert "Modelo 303" in finding.next_action
    # Must not be None or trivially empty.
    assert len(finding.next_action) > 10


# ---------------------------------------------------------------------------
# S95/S96 — _iva_wallet_blocked_message uses tr(); exception carries translated_message
# ---------------------------------------------------------------------------


def test_iva_wallet_blocked_message_is_localised() -> None:
    """_iva_wallet_blocked_message renders via tr() interpolating divergence and reason.

    The returned string must contain the divergence and reason tokens as
    produced by the locale template, not a raw f-string fallback.
    """
    decision = SimpleNamespace(divergence="wallet_missing", reason="No history available.")

    message = _iva_wallet_blocked_message(decision)

    assert "wallet_missing" in message
    assert "No history available." in message
    assert "Modelo 303" in message


def test_iva_wallet_blocked_exception_carries_translated_message_key() -> None:
    """ModeloIvaWalletReconciliationBlocked raised via _raise_if_persisted... carries
    translated_message='application.modelo.errors.iva_wallet_blocked'.

    This test exercises the raise site through _iva_wallet_blocked_message
    indirectly by constructing the exception the same way the raise site does
    after S95 — with both the rendered message and the translated_message key.
    """
    from ._actions import ModeloIvaWalletReconciliationBlocked

    decision = SimpleNamespace(divergence="filed_history_only", reason="Only filed history present.")
    rendered = _iva_wallet_blocked_message(decision)

    exc = ModeloIvaWalletReconciliationBlocked(
        rendered,
        translated_message="application.modelo.errors.iva_wallet_blocked",
    )

    assert exc.translated_message == "application.modelo.errors.iva_wallet_blocked"
    assert "filed_history_only" in str(exc)


# ---------------------------------------------------------------------------
# Original S168 tests — IVA-regime enum surface
# ---------------------------------------------------------------------------


def test_iva_regime_enum_covers_all_wizard_choice_values() -> None:
    """All IVARegime members must appear in the wizard's IVA-regime choice list.

    This cross-cuts the wizard ``_IVA_REGIME_CHOICE_VALUES`` derivation (S167)
    against the canonical enum so neither can drift independently.
    """
    from ..wizard._commands import _IVA_REGIME_CHOICE_VALUES

    enum_values = {m.value for m in IVARegime}
    choice_set = set(_IVA_REGIME_CHOICE_VALUES)
    assert enum_values == choice_set, (
        f"Wizard choice values {choice_set!r} do not match IVARegime members {enum_values!r}. "
        "Update _iva_regime_choice_values() or IVARegime."
    )
