"""Real-behavior tests for modelo action module surfaces.

contract: ``_IVA_LEDGER_EXEMPT_REGIMES`` uses ``IVARegime`` enum members rather
than raw strings, so the frozenset membership check is typed at the schema
boundary and cannot silently drift from the canonical enum.

contract: verification finding messages and next_action strings are routed
through ``tr()`` so the operator-facing surface is localised.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core import Period
from ....core.aggregation import BindingSourceKind
from ....core.resources import resources
from ....domain.calculations.registry import (
    BindingId,
    CasillaDefinition,
    CasillaId,
    DataBindingDefinition,
    InputKind,
    validated_casilla_id,
)
from ....domain.calculations.registry._schema import ModeloRevision, PeriodSelector, VerificationPredicateDefinition
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.iva_compensation._reconciliation import (
    IvaCompensationDivergence,
    IvaCompensationReconciliationDecision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ...workflow import WorkflowInputMismatchError
from .. import ModeloAggregationBindingError
from .._calculation_actions import (
    _IVA_LEDGER_EXEMPT_REGIMES,
    _reject_caller_overrides_of_source_bindings,
)
from .._iva_wallet_gate import (
    ModeloIvaWalletReconciliationBlocked,
    iva_wallet_blocked_message,
)
from .._iva_wallet_gate import (
    apply_iva_compensation_decision_binding as _apply_iva_compensation_decision_binding,
)
from .._verification_actions import (
    _art20_reduccion_advisory_finding,
    _collect_revision_verification_findings,
    _dt12_reduccion_advisory_finding,
    _evaluate_verification_predicates,
    _iva_wallet_blocking_verification_finding,
    _missing_required_casilla_finding,
)
from .._workflow_gate import (
    _RevisionInputsProvider,
    workflow_period_for_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_TEST_LEGAL_REF = "test-actions:legal"
_TEST_SOURCE_REF = "test-actions:source"
_BUCKET_ID = "ac42089b-a822-458e-99e6-333861181de7"


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"actions test fixture casilla key {value!r} is not a CasillaId") from exc


_SOURCE_BOUND_CASILLA: CasillaId = _casilla_id("0001")
_PREDICATE_REQUIRED_LEFT_CASILLA: CasillaId = _casilla_id("0001")
_PREDICATE_REQUIRED_RIGHT_CASILLA: CasillaId = _casilla_id("0002")
_PREDICATE_OPTIONAL_LEFT_CASILLA: CasillaId = _casilla_id("0003")
_PREDICATE_OPTIONAL_RIGHT_CASILLA: CasillaId = _casilla_id("0004")
_DT12_INGRESO_CASILLA: CasillaId = _casilla_id("0003")
_DT12_REDUCCION_CASILLA: CasillaId = _casilla_id("0011")
_ART20_RNT_CASILLA: CasillaId = _casilla_id("0022")
_ART20_REDUCCION_CASILLA: CasillaId = _casilla_id("0023")
_M130_INGRESOS_CASILLA: CasillaId = _casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = _casilla_id("02")
_SOURCE_BOUND_BINDING: BindingId = "ledger_iva_base"


def _test_casilla_definition(
    casilla_id: CasillaId,
    *,
    semantic_role: str | None = None,
    input_kind: InputKind = InputKind.MANUAL,
    binding: BindingId | None = None,
) -> CasillaDefinition:
    return CasillaDefinition(
        id=casilla_id,
        number=casilla_id,
        label=f"Test casilla {casilla_id}",
        section=("test",),
        input_kind=input_kind,
        binding=binding,
        semantic_role=semantic_role,
        legal_refs=(_TEST_LEGAL_REF,),
        source_refs=(_TEST_SOURCE_REF,),
    )


def _test_revision(
    *,
    casillas: tuple[CasillaDefinition, ...] = (),
    bindings: tuple[DataBindingDefinition, ...] = (),
) -> ModeloRevision:
    return ModeloRevision(
        id="test-actions-revision",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("0A", "1T")),
        legal_refs=(_TEST_LEGAL_REF,),
        source_refs=(_TEST_SOURCE_REF,),
        casillas=casillas,
        bindings=bindings,
    )


def _dt12_revision() -> ModeloRevision:
    return _test_revision(
        casillas=(
            _test_casilla_definition(
                _DT12_INGRESO_CASILLA,
                semantic_role="irpf_rendimiento_trabajo_importe_integro_dinerario",
            ),
            _test_casilla_definition(
                _DT12_REDUCCION_CASILLA,
                semantic_role="irpf_rendimiento_trabajo_reduccion",
            ),
        ),
    )


def _art20_revision() -> ModeloRevision:
    return _test_revision(
        casillas=(
            _test_casilla_definition(
                _ART20_RNT_CASILLA,
                semantic_role="irpf_rendimiento_trabajo_rendimiento_neto",
            ),
            _test_casilla_definition(
                _ART20_REDUCCION_CASILLA,
                semantic_role="irpf_rendimiento_trabajo_reduccion_gastos_generales",
            ),
        ),
    )


def _source_bound_revision() -> ModeloRevision:
    return _test_revision(
        bindings=(
            # A well-shaped ``ledger_iva_aggregation`` selector so the binding
            # clears the F8 construction-time selector gate; the test exercises
            # the override-error localisation against the matching owned source,
            # not selector shape.
            DataBindingDefinition(
                id=_SOURCE_BOUND_BINDING,
                source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
                selector={
                    "categories": ("domestic_general_21",),
                    "rate_kinds": ("general",),
                    "flow_direction": "repercutido",
                    "fact": "iva_amount_sum",
                },
                legal_refs=(_TEST_LEGAL_REF,),
                source_refs=(_TEST_SOURCE_REF,),
            ),
        ),
        casillas=(
            _test_casilla_definition(
                _SOURCE_BOUND_CASILLA,
                input_kind=InputKind.BOUND,
                binding=_SOURCE_BOUND_BINDING,
            ),
        ),
    )


def _predicate_finding(
    *,
    predicate_id: str,
    legal_ref: str,
    expression: str,
    casilla_values: dict[CasillaId, Decimal],
):
    predicate = VerificationPredicateDefinition(
        predicate_id=predicate_id,
        legal_refs=(legal_ref,),
        expression=expression,
        finding_kind="BLOCKING_RULE",
    )
    findings = _evaluate_verification_predicates((predicate,), casilla_values, _resident_profile())
    assert len(findings) == 1
    return predicate, findings[0]


def _blocked_wallet_decision(
    *,
    divergence: IvaCompensationDivergence,
    reason: str,
) -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        selected_authority="missing",
        selected_amount=None,
        divergence=divergence,
        blocked=True,
        stale_wallet=False,
        reason=reason,
        decided_at=_T0,
    )


def _m130_casilla_definition(casilla_id: CasillaId) -> CasillaDefinition:
    snapshot = resources().modelos.authority.snapshot("130", filing_year=2026, period="1T")
    return next(item for item in snapshot.revision.casillas if item.id == casilla_id)


def _resident_profile() -> TaxpayerProfile:
    """Minimal RESIDENT_IRPF profile for predicate-evaluator call sites.

    Casilla-only predicates ignore the profile; this real profile is for tests
    that exercise the casilla DSL operators (all_nonzero, any_nonzero,
    cap_le_when_positive, implies_nonzero) without exercising the
    profile_field_required branch.
    """
    return TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL)


def _minimal_work_unit(modelo: str = "999", period: str = "0A", filing_year: int = 2026) -> WorkUnit:
    bucket_id = "test-bucket"
    typed_period = Period.from_year_and_code(filing_year, period)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=typed_period,
            revision_id="r" + "0" * 63,
        ),
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id="r" + "0" * 63,
        name=f"{modelo}-{filing_year}-{typed_period.registry_token}",
        created_at=_T0,
        updated_at=_T0,
    )


def _minimal_calculation_revision(work_unit: WorkUnit) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
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
            f"_IVA_LEDGER_EXEMPT_REGIMES contains a bare string {member!r}; expected an IVARegime enum member"
        )


@pytest.mark.parametrize(
    ("regime", "expected_member"),
    (
        pytest.param(IVARegime.SIMPLIFICADO, True, id="simplificado-bypasses-ledger"),
        pytest.param(IVARegime.GENERAL, False, id="general-requires-ledger"),
    ),
)
def test_iva_ledger_exempt_regime_membership_matches_contract(regime: IVARegime, expected_member: bool) -> None:
    """Only exempt IVA regimes bypass ledger preflight."""
    assert (regime in _IVA_LEDGER_EXEMPT_REGIMES) is expected_member


@pytest.mark.parametrize(
    "modelo",
    (
        pytest.param("130", id="m130-yyyyqn-deadline-shape"),
        pytest.param("303", id="m303-yyyy-nt-deadline-shape"),
    ),
)
def test_workflow_period_resolves_quarter_from_registry_deadline_shape(modelo: str) -> None:
    work_unit = _minimal_work_unit(modelo=modelo, period="1T", filing_year=2026)

    assert workflow_period_for_work_unit(work_unit) == Period.from_year_and_code(2026, "1T")


# ---------------------------------------------------------------------------
# contract/contract — cross-casilla invariant violated: message is localised
# contract/contract — cross-casilla invariant violated: next_action is localised
# ---------------------------------------------------------------------------


def test_cross_casilla_invariant_violated_message_is_localised() -> None:
    """_evaluate_verification_predicates emits a tr()-rendered message for a violated predicate.

    The predicate expression ``all_nonzero(["0001","0002"])`` fails when
    both casillas are zero, producing a BLOCKING_RULE finding. The message
    must contain the predicate_id and expression as rendered by the locale
    catalogue (not a raw f-string).
    """
    predicate, finding = _predicate_finding(
        predicate_id="test-cross-casilla-001",
        legal_ref="irpf:art1",
        expression=f'all_nonzero(["{_PREDICATE_REQUIRED_LEFT_CASILLA}","{_PREDICATE_REQUIRED_RIGHT_CASILLA}"])',
        casilla_values={_PREDICATE_REQUIRED_LEFT_CASILLA: Decimal(0), _PREDICATE_REQUIRED_RIGHT_CASILLA: Decimal(0)},
    )

    # The message must contain the predicate_id and expression (from the locale template).
    assert "test-cross-casilla-001" in finding.message
    assert predicate.expression in finding.message
    # Must not be the old raw f-string format with repr apostrophes around predicate_id.
    assert "violated: " in finding.message


def test_cross_casilla_invariant_next_action_is_localised() -> None:
    """_evaluate_verification_predicates emits a tr()-rendered next_action for a violated predicate."""
    _, finding = _predicate_finding(
        predicate_id="test-cross-casilla-002",
        legal_ref="irpf:art2",
        expression=f'any_nonzero(["{_PREDICATE_OPTIONAL_LEFT_CASILLA}","{_PREDICATE_OPTIONAL_RIGHT_CASILLA}"])',
        casilla_values={_PREDICATE_OPTIONAL_LEFT_CASILLA: Decimal(0), _PREDICATE_OPTIONAL_RIGHT_CASILLA: Decimal(0)},
    )

    assert finding.next_action is not None
    # The next_action must contain the predicate_id (from the locale template).
    assert "test-cross-casilla-002" in finding.next_action
    # Must not produce a None or empty next_action.
    assert len(finding.next_action) > 0


# ---------------------------------------------------------------------------
# contract/contract — registry-snapshot-unresolved finding is localised
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

    findings, _resolved, _missing = _collect_revision_verification_findings(
        work_unit=work_unit,
        target=target,
        profile=_resident_profile(),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert "999" in finding.message
    assert "2026" in finding.message
    assert "0A" in finding.message
    assert "could not be resolved" in finding.message


# ---------------------------------------------------------------------------
# contract/contract — DT12 reducción advisory message is localised
# ---------------------------------------------------------------------------


def test_dt12_reduccion_advisory_message_is_localised() -> None:
    """_dt12_reduccion_advisory_finding emits a tr()-rendered message.

    A real revision object carrying two casillas with the correct semantic
    roles triggers the advisory. The finding message must contain ingreso_id,
    ingreso_value, and reduccion_id tokens from the locale template.
    """
    revision = _dt12_revision()
    casilla_values = {_DT12_INGRESO_CASILLA: Decimal("25000"), _DT12_REDUCCION_CASILLA: Decimal("0")}

    finding = _dt12_reduccion_advisory_finding(revision, casilla_values)

    assert finding is not None
    assert str(_DT12_INGRESO_CASILLA) in finding.message
    assert "25000" in finding.message
    assert str(_DT12_REDUCCION_CASILLA) in finding.message
    # Locale template token "reduccion" must appear in the rendered string.
    assert "reduccion" in finding.message.lower()


# ---------------------------------------------------------------------------
# contract/contract — art. 20 LIRPF reducción advisory
# ---------------------------------------------------------------------------


def test_art20_reduccion_advisory_fires_within_band_and_is_localised() -> None:
    """_art20_reduccion_advisory_finding warns when RNT is in-band but reduction is zero.

    A real revision carrying the rendimiento-neto-del-trabajo role and the
    art. 20 general-reducción role triggers the ADVISORY finding when RNT is strictly
    positive and below the art. 20 ceiling while the reducción casilla is zero. The
    finding is non-blocking (ADVISORY / WARNING) and its tr()-rendered message carries
    the rnt_id, rnt_value, and reduccion_id tokens.
    """
    revision = _art20_revision()
    casilla_values = {_ART20_RNT_CASILLA: Decimal("12000"), _ART20_REDUCCION_CASILLA: Decimal("0")}

    finding = _art20_reduccion_advisory_finding(revision, casilla_values)

    assert finding is not None
    # Non-blocking advisory: the eligibility gate (otras rentas <= 6.500) is not engine-visible.
    assert finding.kind == "advisory"
    assert finding.severity == "warning"
    assert finding.casilla_id == _ART20_REDUCCION_CASILLA
    assert finding.legal_refs == ("ley-35-2006:art-20",)
    assert str(_ART20_RNT_CASILLA) in finding.message
    assert "12000" in finding.message
    assert str(_ART20_REDUCCION_CASILLA) in finding.message
    assert finding.next_action
    # The advisory message must be the rendered locale value, not the raw key.
    assert finding.message != "application.modelo.findings.art20_reduccion_possible"


@pytest.mark.parametrize(
    "casilla_values",
    (
        pytest.param(
            {_ART20_RNT_CASILLA: Decimal("25000"), _ART20_REDUCCION_CASILLA: Decimal("0")},
            id="above-ceiling",
        ),
        pytest.param(
            {_ART20_RNT_CASILLA: Decimal("12000"), _ART20_REDUCCION_CASILLA: Decimal("3500")},
            id="reduction-already-declared",
        ),
        pytest.param({_ART20_RNT_CASILLA: Decimal("0"), _ART20_REDUCCION_CASILLA: Decimal("0")}, id="zero-rnt"),
    ),
)
def test_art20_reduccion_advisory_silent_for_declared_or_ineligible_values(
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    """The art. 20 advisory must NOT fire when there is nothing to surface.

    No false positive when: RNT is at/above the ceiling (reduction is genuinely zero),
    the reducción is already declared, or RNT is zero.
    """
    assert _art20_reduccion_advisory_finding(_art20_revision(), casilla_values) is None


def test_art20_reduccion_advisory_silent_when_roles_absent() -> None:
    assert _art20_reduccion_advisory_finding(_test_revision(), {}) is None


# ---------------------------------------------------------------------------
# contract/contract — IVA wallet next_action is localised
# ---------------------------------------------------------------------------


def test_iva_wallet_blocking_finding_next_action_is_localised() -> None:
    """_iva_wallet_blocking_verification_finding returns a finding with a tr()-rendered next_action.

    The next_action must come from the locale catalogue key
    'application.modelo.findings.iva_wallet_next_action' and must not be
    the old hardcoded English string.
    """
    decision = IvaCompensationReconciliationDecision(
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        taxpayer_nif="12345678Z",
        divergence="wallet_missing",
        blocked=True,
        selected_authority="missing",
        selected_amount=None,
        stale_wallet=False,
        decided_at=_T0,
        reason="No AEAT wallet observation or local recurrence is available.",
    )
    finding = _iva_wallet_blocking_verification_finding(decision)

    assert finding.next_action is not None
    # Must not be None or trivially empty.
    assert len(finding.next_action) > 10
    # Must not be the raw locale key (self-referencing fallback).
    assert finding.next_action != "application.modelo.findings.iva_wallet_next_action"
    # Must reference Modelo 303 (invariant across all authored locales).
    assert "303" in finding.next_action


# ---------------------------------------------------------------------------
# contract/contract — iva_wallet_blocked_message uses tr(); exception carries translated_message
# ---------------------------------------------------------------------------


def test_iva_wallet_blocked_message_is_localised() -> None:
    """iva_wallet_blocked_message renders via tr() interpolating divergence and reason.

    The returned string must contain the divergence and reason tokens as
    produced by the locale template, not a raw f-string fallback.
    """
    decision = _blocked_wallet_decision(divergence="wallet_missing", reason="No history available.")

    message = iva_wallet_blocked_message(decision)

    # The divergence and reason tokens must appear in the rendered message.
    assert "wallet_missing" in message
    assert "No history available." in message
    # Must not be the raw locale key (self-referencing fallback).
    assert message != "application.modelo.errors.iva_wallet_blocked"
    # Must reference the model number (invariant across all authored locales).
    assert "303" in message


def test_iva_wallet_blocked_exception_carries_translated_message_key() -> None:
    """ModeloIvaWalletReconciliationBlocked raised via _raise_if_persisted... carries
    translated_message='application.modelo.errors.iva_wallet_blocked'.

    This test exercises the raise site through iva_wallet_blocked_message
    indirectly by constructing the exception the same way the raise site does
    after contract — with both the rendered message and the translated_message key.
    """
    decision = _blocked_wallet_decision(divergence="filed_history_only", reason="Only filed history present.")
    rendered = iva_wallet_blocked_message(decision)

    exc = ModeloIvaWalletReconciliationBlocked(
        rendered,
        translated_message="application.modelo.errors.iva_wallet_blocked",
    )

    assert exc.translated_message == "application.modelo.errors.iva_wallet_blocked"
    assert "filed_history_only" in str(exc)


def test_iva_wallet_unsupported_decision_type_is_localised() -> None:
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as raised:
        _apply_iva_compensation_decision_binding(
            "303",
            2026,
            Period.from_year_and_code(2026, "1T"),
            bucket_id=_BUCKET_ID,
            revision=_test_revision(),
            taxpayer_nif="12345678Z",
            caller_binding_values={},
            backend_binding_values={},
            decision=object(),
        )

    assert raised.value.translated_message == "application.modelo.errors.iva_wallet_unsupported_decision_type"
    assert raised.value.context == {"decision_type": "object"}
    assert "application.modelo.errors.iva_wallet_unsupported_decision_type" not in str(raised.value)


def test_source_bound_casilla_override_error_is_localised() -> None:
    revision = _source_bound_revision()

    with pytest.raises(ModeloAggregationBindingError) as raised:
        _reject_caller_overrides_of_source_bindings(
            revision=revision,
            owned_sources=frozenset({BindingSourceKind.LEDGER_IVA_AGGREGATION}),
            caller_binding_values={},
            caller_casilla_inputs={_SOURCE_BOUND_CASILLA: Decimal("12.34")},
        )

    assert raised.value.translated_message == "application.modelo.errors.caller_casilla_source_binding_conflict"
    assert raised.value.context == {"casillas": [_SOURCE_BOUND_CASILLA]}
    assert raised.value.context is not None
    rejected_casillas = raised.value.context["casillas"]
    assert isinstance(rejected_casillas, list)
    assert _SOURCE_BOUND_CASILLA in rejected_casillas


# ---------------------------------------------------------------------------
# Original contract tests — IVA-regime enum surface
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# contract -- WorkflowInputMismatchError raised and registered
# ---------------------------------------------------------------------------


class TestWorkflowInputMismatchError:
    """Real-behavior tests for WorkflowInputMismatchError.

    _RevisionInputsProvider.load_inputs raises WorkflowInputMismatchError when
    the requested (modelo, period) pair does not match the revision's stored
    work-unit axes. The error must be a CoreValidationError (ValueError) subclass
    and must carry structured context.
    """

    def _make_provider(self, modelo: str = "100", period: str = "0A") -> _RevisionInputsProvider:
        work_unit = _minimal_work_unit(modelo=modelo, period=period)
        revision = _minimal_calculation_revision(work_unit)
        return _RevisionInputsProvider(revision=revision, work_unit=work_unit)

    def _resident_profile(self) -> TaxpayerProfile:
        """Return a minimal real profile (load_inputs discards it via ``del``)."""
        return TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL)

    def test_matching_request_does_not_raise(self) -> None:
        """load_inputs with the correct modelo and workflow period returns inputs."""
        from .._workflow_gate import workflow_period_for_work_unit

        work_unit = _minimal_work_unit(modelo="100", period="0A")
        revision = _minimal_calculation_revision(work_unit)
        provider = _RevisionInputsProvider(revision=revision, work_unit=work_unit)
        expected_period = workflow_period_for_work_unit(work_unit)
        result = provider.load_inputs(
            modelo="100",
            period=expected_period,
            profile=self._resident_profile(),
        )
        assert isinstance(result, dict)

    def test_mismatched_modelo_raises_workflow_input_mismatch_error(self) -> None:
        """load_inputs with a wrong modelo raises WorkflowInputMismatchError."""
        from .._workflow_gate import workflow_period_for_work_unit

        work_unit = _minimal_work_unit(modelo="100", period="0A")
        revision = _minimal_calculation_revision(work_unit)
        provider = _RevisionInputsProvider(revision=revision, work_unit=work_unit)
        correct_period = workflow_period_for_work_unit(work_unit)

        with pytest.raises(WorkflowInputMismatchError) as exc_info:
            provider.load_inputs(
                modelo="303",
                period=correct_period,
                profile=self._resident_profile(),
            )

        exc = exc_info.value
        assert "workflow input request does not match calculation revision" in str(exc)
        assert exc.context is not None
        assert exc.context["expected_modelo"] == "100"
        assert exc.context["requested_modelo"] == "303"

    def test_mismatched_period_raises_workflow_input_mismatch_error(self) -> None:
        """load_inputs with a wrong period raises WorkflowInputMismatchError."""
        work_unit = _minimal_work_unit(modelo="303", period="1T")
        revision = _minimal_calculation_revision(work_unit)
        provider = _RevisionInputsProvider(revision=revision, work_unit=work_unit)

        with pytest.raises(WorkflowInputMismatchError) as exc_info:
            provider.load_inputs(
                modelo="303",
                period=Period.from_year_and_code(2026, "2T"),
                profile=self._resident_profile(),
            )

        exc = exc_info.value
        assert exc.context is not None
        assert exc.context["expected_period"] == "2026 1T"
        assert exc.context["requested_period"] == "2026 2T"

    def test_error_is_core_validation_error_and_value_error(self) -> None:
        """WorkflowInputMismatchError is a CoreValidationError and ValueError subclass."""
        from ....core.errors import CoreValidationError

        assert issubclass(WorkflowInputMismatchError, CoreValidationError)
        assert issubclass(WorkflowInputMismatchError, ValueError)

    def test_error_code_is_registered(self) -> None:
        """WorkflowInputMismatchError maps to a stable error code in the registry."""
        from ....core.errors import get_registered_error_code

        work_unit = _minimal_work_unit(modelo="100", period="0A")
        revision = _minimal_calculation_revision(work_unit)
        provider = _RevisionInputsProvider(revision=revision, work_unit=work_unit)

        try:
            provider.load_inputs(
                modelo="999",
                period=Period.from_year_and_code(2026, "0A"),
                profile=self._resident_profile(),
            )
        except WorkflowInputMismatchError as exc:
            code = get_registered_error_code(exc)
            assert code.code == "REFUSED_WORKFLOW_INPUT_MISMATCH"
        else:
            pytest.fail("WorkflowInputMismatchError was not raised")


def test_iva_regime_enum_covers_all_wizard_choice_values() -> None:
    """All IVARegime members must appear in the wizard's IVA-regime choice list.

    This cross-cuts the wizard ``_IVA_REGIME_CHOICE_VALUES`` derivation (contract)
    against the canonical enum so neither can drift independently.
    """
    from ...wizard._commands import _IVA_REGIME_CHOICE_VALUES

    enum_values = {m.value for m in IVARegime}
    choice_set = set(_IVA_REGIME_CHOICE_VALUES)
    assert enum_values == choice_set, (
        f"Wizard choice values {choice_set!r} do not match IVARegime members {enum_values!r}. "
        "Update _iva_regime_choice_values() or IVARegime."
    )


# ---------------------------------------------------------------------------
# contract/contract — missing_required_casilla finding message is localised
# ---------------------------------------------------------------------------


def test_missing_required_casilla_finding_message_is_localised() -> None:
    """_missing_required_casilla_finding renders message via tr().

    The returned finding message must contain the casilla_id token
    (interpolated by the locale template) and must not be the raw locale key.
    """
    finding = _missing_required_casilla_finding(
        _M130_INGRESOS_CASILLA,
        "wu-abc123",
        casilla_def=_m130_casilla_definition(_M130_INGRESOS_CASILLA),
    )

    assert finding.message is not None
    # The casilla_id must appear in the rendered message.
    assert _M130_INGRESOS_CASILLA in finding.message
    # Must not be the raw locale key surfaced as a self-referencing fallback.
    assert finding.message != "application.modelo.findings.missing_required_casilla"


def test_missing_required_casilla_finding_message_changes_with_casilla_id() -> None:
    """Each casilla_id produces a distinct, non-trivial finding message.

    The locale template interpolates %{casilla_id}; two calls with different
    ids must produce different rendered strings. A tautological template or
    missing interpolation would produce identical output.
    """
    finding_a = _missing_required_casilla_finding(
        _M130_INGRESOS_CASILLA,
        "wu-1",
        casilla_def=_m130_casilla_definition(_M130_INGRESOS_CASILLA),
    )
    finding_b = _missing_required_casilla_finding(
        _M130_GASTOS_CASILLA,
        "wu-1",
        casilla_def=_m130_casilla_definition(_M130_GASTOS_CASILLA),
    )

    assert finding_a.message != finding_b.message
    assert _M130_INGRESOS_CASILLA in finding_a.message
    assert _M130_GASTOS_CASILLA in finding_b.message


# ---------------------------------------------------------------------------
# contract/contract — DT12 advisory next_action is localised
# ---------------------------------------------------------------------------


def test_dt12_reduccion_advisory_next_action_is_localised() -> None:
    """_dt12_reduccion_advisory_finding next_action renders via tr().

    The next_action must be sourced from the locale catalogue key
    'application.modelo.findings.dt12a_reduccion_next_action' and must
    not be the old hardcoded English string.
    """
    revision = _dt12_revision()
    casilla_values = {_DT12_INGRESO_CASILLA: Decimal("25000"), _DT12_REDUCCION_CASILLA: Decimal("0")}

    finding = _dt12_reduccion_advisory_finding(revision, casilla_values)

    assert finding is not None
    assert finding.next_action is not None
    # Must not be the raw locale key surfaced as a self-referencing fallback.
    assert finding.next_action != "application.modelo.findings.dt12a_reduccion_next_action"
    # Must contain a substantive reference to the DT 12 legal provision.
    assert "12" in finding.next_action
    # Must reference the CLI verb or the DT provision (either locale will satisfy this).
    assert len(finding.next_action) > 20


def test_dt12_reduccion_advisory_next_action_differs_from_hardcoded_string() -> None:
    """next_action is no longer the old hardcoded English string.

    After contract the next_action is locale-catalogue-driven. The pre-contract
    value was a specific English sentence; asserting it is gone proves
    the catalogue path is active.
    """
    revision = _dt12_revision()
    casilla_values = {_DT12_INGRESO_CASILLA: Decimal("25000"), _DT12_REDUCCION_CASILLA: Decimal("0")}

    finding = _dt12_reduccion_advisory_finding(revision, casilla_values)

    assert finding is not None
    assert finding.next_action is not None
    # The pre-contract hardcoded substring that should no longer appear.
    assert "to aeat app modelo work calculate to auto-inject" not in finding.next_action
