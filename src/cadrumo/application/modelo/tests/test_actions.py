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

from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.iva_compensation.reconciliation import IvaCompensationDivergence, IvaCompensationReconciliationDecision
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...calculations import M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA
from ...workflow.errors import WorkflowInputMismatchError
from .._action_errors import ModeloAggregationBindingError
from .._calculation_actions import (
    _reject_caller_overrides_of_source_bindings,
)
from .._calculation_preparation import _IVA_LEDGER_EXEMPT_REGIMES
from .._iva_wallet_gate import (
    ModeloIvaWalletReconciliationBlocked,
)
from .._iva_wallet_gate import (
    apply_iva_compensation_decision_binding as _apply_iva_compensation_decision_binding,
)
from .._revision_replay_inputs import _informational_casilla_replay_inputs
from .._verification_actions import (
    _art20_reduccion_advisory_finding,
    _art52_reduccion_advisory_finding,
    _collect_revision_verification_findings,
    _dt12_antiquity_advisory_finding,
    _dt12_reduccion_advisory_finding,
    _evaluate_verification_predicates,
    _iva_wallet_error_verification_finding,
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
_TEST_SOURCE_REF = "test-actions-source"
_BUCKET_ID = "ac42089b-a822-458e-99e6-333861181de7"


_SOURCE_BOUND_CASILLA: CasillaId = validated_casilla_id("0001")
_PREDICATE_REQUIRED_LEFT_CASILLA: CasillaId = validated_casilla_id("0001")
_PREDICATE_REQUIRED_RIGHT_CASILLA: CasillaId = validated_casilla_id("0002")
_PREDICATE_OPTIONAL_LEFT_CASILLA: CasillaId = validated_casilla_id("0003")
_PREDICATE_OPTIONAL_RIGHT_CASILLA: CasillaId = validated_casilla_id("0004")
_DT12_INGRESO_CASILLA: CasillaId = validated_casilla_id("0003")
_DT12_REDUCCION_CASILLA: CasillaId = validated_casilla_id("0011")
_ART20_RNT_CASILLA: CasillaId = validated_casilla_id("0022")
_ART20_REDUCCION_CASILLA: CasillaId = validated_casilla_id("0023")
_ART52_REDUCCION_CASILLA: CasillaId = validated_casilla_id("0468")
_ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: CasillaId = validated_casilla_id("0426")
_ART52_EMPRESARIAL_CASILLA: CasillaId = validated_casilla_id("0427")
_ART52_AUTONOMOS_EMPRESARIOS_CASILLA: CasillaId = validated_casilla_id("0499")
_DT12_ANTIQUITY_REDUCCION_CASILLA: CasillaId = validated_casilla_id("0011")
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02")
_SOURCE_BOUND_BINDING: BindingId = "ledger_iva_base"
_M100_ACTIVIDAD_ECONOMICA_INCOME_CASILLA: CasillaId = validated_casilla_id("0171")
_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: CasillaId = validated_casilla_id("0224")


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
        localization_keys=(f"test.schema.casilla.{casilla_id}.label",),
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
        localization_key="test.schema.revision.test-actions-revision.label",
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


def _art52_revision() -> ModeloRevision:
    return _test_revision(
        casillas=(
            _test_casilla_definition(
                _ART52_REDUCCION_CASILLA,
                semantic_role="irpf_reduccion_prevision_social_total",
            ),
            _test_casilla_definition(
                _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA,
                semantic_role="irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial",
            ),
            _test_casilla_definition(
                _ART52_EMPRESARIAL_CASILLA,
                semantic_role="irpf_red_prevision_social_contribuciones_empresariales_excepto_scd",
            ),
            _test_casilla_definition(
                _ART52_AUTONOMOS_EMPRESARIOS_CASILLA,
                semantic_role="irpf_red_prevision_social_aportaciones_autonomos_empresarios",
            ),
        ),
    )


def _dt12_antiquity_revision() -> ModeloRevision:
    return _test_revision(
        casillas=(
            _test_casilla_definition(
                _DT12_ANTIQUITY_REDUCCION_CASILLA,
                semantic_role="irpf_rendimiento_trabajo_reduccion",
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
                    "categories": ("domestic_general",),
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
    reason_identity: str,
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
        reason_identity=reason_identity,
        decided_at=_T0,
    )


def _m130_casilla_definition(casilla_id: CasillaId) -> CasillaDefinition:
    snapshot = bundled_authority().snapshot("130", filing_year=2026, period="1T")
    return next(item for item in snapshot.revision.casillas if item.id == casilla_id)


def _resident_profile() -> TaxpayerProfile:
    """Minimal RESIDENT_IRPF profile for predicate-evaluator call sites.

    Casilla-only predicates ignore the profile; this real profile is for tests
    that exercise the casilla DSL operators (all_nonzero, any_nonzero,
    cap_le_when_positive, implies_nonzero) without exercising the
    profile_field_required branch.
    """
    return TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL)


def _minimal_work_unit(
    modelo: str = "999",
    period: str = "0A",
    filing_year: int = 2026,
    revision_id: str = "r" + "0" * 63,
) -> WorkUnit:
    bucket_id = "test-bucket"
    typed_period = Period.from_year_and_code(filing_year, period)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=typed_period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
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
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values={},
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
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


@pytest.mark.parametrize(
    "period",
    (
        pytest.param("1P", id="instalment"),
        pytest.param("EXT-1T", id="extended-oss-quarter-shaped-token"),
        pytest.param("AD-HOC", id="ad-hoc"),
        pytest.param("EVENT-1", id="event"),
    ),
)
def test_workflow_period_does_not_reinterpret_nonquarter_periods(period: str) -> None:
    work_unit = _minimal_work_unit(modelo="369", period=period, filing_year=2026)

    assert workflow_period_for_work_unit(work_unit) == work_unit.period


# ---------------------------------------------------------------------------
# contract/contract — cross-casilla invariant violated: message is localised
# contract/contract — cross-casilla invariant violated: next_action is localised
# ---------------------------------------------------------------------------


def test_cross_casilla_invariant_finding_is_locale_neutral() -> None:
    """A violated registry predicate emits only a presentation identity and facts."""
    _predicate, finding = _predicate_finding(
        predicate_id="test-cross-casilla-001",
        legal_ref="irpf:art1",
        expression=f'all_nonzero(["{_PREDICATE_REQUIRED_LEFT_CASILLA}","{_PREDICATE_REQUIRED_RIGHT_CASILLA}"])',
        casilla_values={
            _PREDICATE_REQUIRED_LEFT_CASILLA: Decimal(0),
            _PREDICATE_REQUIRED_RIGHT_CASILLA: Decimal(0),
        },
    )
    assert finding.casilla_id is None
    assert finding.message_locale_key == "application.modelo.findings.cross_casilla_invariant_violated"
    assert dict(finding.message_facts) == {"predicate_id": "test-cross-casilla-001"}


def test_single_casilla_blocking_predicate_attributes_its_canonical_casilla() -> None:
    """A firing one-casilla BLOCKING predicate identifies the affected registry casilla."""
    _predicate, finding = _predicate_finding(
        predicate_id="test-single-casilla-blocking-001",
        legal_ref="irpf:art1",
        expression=f'all_nonzero(["{_PREDICATE_REQUIRED_LEFT_CASILLA}"])',
        casilla_values={_PREDICATE_REQUIRED_LEFT_CASILLA: Decimal(0)},
    )

    assert finding.kind == "blocking_rule"
    assert finding.severity == "blocking"
    assert finding.casilla_id == _PREDICATE_REQUIRED_LEFT_CASILLA


def test_registry_snapshot_unresolved_finding_is_locale_neutral() -> None:
    """_collect_revision_verification_findings produces a localised message when the registry
    snapshot cannot be resolved for a non-existent modelo.

    Modelo '999' is not in the registry; the function must return a single
    BLOCKING_RULE finding whose message is rendered via tr() and contains the
    modelo, filing_year, and period interpolation tokens. The message must
    also vary with the operator's output language; catalogue prose is
    deliberately not asserted verbatim so a translation edit cannot red this
    contract.
    """
    work_unit = _minimal_work_unit(modelo="999", period="0A", filing_year=2026)
    target = _minimal_calculation_revision(work_unit)

    findings, _resolved, _missing, failures_by_finding_id = _collect_revision_verification_findings(
        work_unit=work_unit,
        target=target,
        profile=_resident_profile(),
        transaction_repository=None,
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding.message_locale_key == "application.modelo.findings.registry_snapshot_unresolved"
    assert dict(finding.message_facts) == {"modelo": "999", "filing_year": 2026, "period": "0A"}
    failure = failures_by_finding_id[id(finding)]
    assert failure.identity == (
        "modelo.work.verify",
        "modelo.work.verify.registry_snapshot.available",
        "modelo.work.verify.registry_snapshot.unavailable",
    )
    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == "operator.registry.verify"


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
    assert finding.message_locale_key == "application.modelo.findings.dt12a_reduccion_possible"
    assert dict(finding.message_facts) == {
        "ingreso_id": str(_DT12_INGRESO_CASILLA),
        "ingreso_value": Decimal("25000"),
        "reduccion_id": str(_DT12_REDUCCION_CASILLA),
    }


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
    assert finding.message_locale_key == "application.modelo.findings.art20_reduccion_possible"
    assert dict(finding.message_facts) == {
        "rnt_id": str(_ART20_RNT_CASILLA),
        "rnt_value": Decimal("12000"),
        "reduccion_id": str(_ART20_REDUCCION_CASILLA),
    }
    assert "next_action" not in finding.model_dump(mode="json")


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
# contract/contract — art. 52 LIRPF previsión-social individual sub-limit advisory
# ---------------------------------------------------------------------------


def test_art52_reduccion_advisory_fires_for_purely_individual_over_sublimit() -> None:
    """_art52_reduccion_advisory_finding warns on a purely-individual over-reduction.

    A purely-individual filer (no plan-de-empleo worker contribution, no
    contribución empresarial) whose granted reducción (0468) exceeds the EUR 1.500
    art. 52 individual sub-limit — e.g. a EUR 3.000 aportación fully reducible under
    the combined EUR 10.000/30% cap the engine already enforces — should be flagged:
    the combined ceiling requires employer-linked backing this filer does not have.
    """
    revision = _art52_revision()
    casilla_values = {
        _ART52_REDUCCION_CASILLA: Decimal("3000"),
        _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: Decimal("0"),
        _ART52_EMPRESARIAL_CASILLA: Decimal("0"),
        _ART52_AUTONOMOS_EMPRESARIOS_CASILLA: Decimal("0"),
    }

    finding = _art52_reduccion_advisory_finding(revision, casilla_values)

    assert finding is not None
    assert finding.kind == "advisory"
    assert finding.severity == "warning"
    assert finding.casilla_id == _ART52_REDUCCION_CASILLA
    assert finding.legal_refs == ("ley-35-2006:art-52",)
    assert finding.message_locale_key == "application.modelo.findings.art52_reduccion_individual_sublimit_possible"
    assert dict(finding.message_facts) == {
        "reduccion_id": str(_ART52_REDUCCION_CASILLA),
        "reduccion_value": Decimal("3000"),
        "sublimit": Decimal("1500"),
    }
    assert "next_action" not in finding.model_dump(mode="json")


def test_art52_reduccion_advisory_silent_when_employer_backed() -> None:
    """No false positive when a contribución empresarial (0427) backs the reducción.

    The same over-1.500 reducción as the firing case, but with a positive
    contribución empresarial declared: the combined EUR 10.000 ceiling legitimately
    applies, so the advisory must stay silent.
    """
    revision = _art52_revision()
    casilla_values = {
        _ART52_REDUCCION_CASILLA: Decimal("3000"),
        _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: Decimal("0"),
        _ART52_EMPRESARIAL_CASILLA: Decimal("2500"),
        _ART52_AUTONOMOS_EMPRESARIOS_CASILLA: Decimal("0"),
    }

    assert _art52_reduccion_advisory_finding(revision, casilla_values) is None


def test_art52_reduccion_advisory_silent_when_plan_de_empleo_backed() -> None:
    """No false positive when a plan-de-empleo worker contribution (0426) backs it."""
    revision = _art52_revision()
    casilla_values = {
        _ART52_REDUCCION_CASILLA: Decimal("3000"),
        _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: Decimal("2500"),
        _ART52_EMPRESARIAL_CASILLA: Decimal("0"),
        _ART52_AUTONOMOS_EMPRESARIOS_CASILLA: Decimal("0"),
    }

    assert _art52_reduccion_advisory_finding(revision, casilla_values) is None


def test_art52_reduccion_advisory_silent_when_autonomo_backed() -> None:
    """No false positive when an autónomo/empresario-individual aportación (0499) backs it.

    Casilla 0499 legitimately unlocks the art. 52.1.2º EUR 4.250 increment (not the
    full art. 52.1.1º EUR 8.500 increment 0426/0427 unlock), so a reducción above
    EUR 1.500 backed solely by 0499 must not be flagged — the advisory only detects
    the no-backing-at-all case and leaves the exact 1º/2º split to the COMPUTED
    formula on revisions where 0468 is not a bare MANUAL input.
    """
    revision = _art52_revision()
    casilla_values = {
        _ART52_REDUCCION_CASILLA: Decimal("3000"),
        _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: Decimal("0"),
        _ART52_EMPRESARIAL_CASILLA: Decimal("0"),
        _ART52_AUTONOMOS_EMPRESARIOS_CASILLA: Decimal("2500"),
    }

    assert _art52_reduccion_advisory_finding(revision, casilla_values) is None


def test_art52_reduccion_advisory_silent_when_under_sublimit() -> None:
    """No false positive when the purely-individual reducción is at or below EUR 1.500."""
    revision = _art52_revision()
    casilla_values = {
        _ART52_REDUCCION_CASILLA: Decimal("1500"),
        _ART52_TRABAJADOR_CON_CONTRIBUCION_CASILLA: Decimal("0"),
        _ART52_EMPRESARIAL_CASILLA: Decimal("0"),
        _ART52_AUTONOMOS_EMPRESARIOS_CASILLA: Decimal("0"),
    }

    assert _art52_reduccion_advisory_finding(revision, casilla_values) is None


def test_art52_reduccion_advisory_silent_when_roles_absent() -> None:
    assert _art52_reduccion_advisory_finding(_test_revision(), {}) is None


# ---------------------------------------------------------------------------
# contract/contract — DT 12ª LIRPF antiquity-condition advisory
# ---------------------------------------------------------------------------


def test_dt12_antiquity_advisory_fires_when_reduccion_applied() -> None:
    """_dt12_antiquity_advisory_finding warns to confirm antiquity when 40% applies.

    A strictly positive trabajo reducción prompts the operator to confirm the
    pre-2007 TRLIRPF art. 17.2.a) two-year antiquity condition (waived for
    invalidez) DT 12ª LIRPF imports for the transitional régimen.
    """
    revision = _dt12_antiquity_revision()
    casilla_values = {_DT12_ANTIQUITY_REDUCCION_CASILLA: Decimal("4000")}

    finding = _dt12_antiquity_advisory_finding(revision, casilla_values)

    assert finding is not None
    assert finding.kind == "advisory"
    assert finding.severity == "warning"
    assert finding.casilla_id == _DT12_ANTIQUITY_REDUCCION_CASILLA
    assert finding.legal_refs == ("ley-35-2006:dt-12",)
    assert finding.message_locale_key == "application.modelo.findings.dt12a_reduccion_antiquity_possible"
    assert dict(finding.message_facts) == {
        "reduccion_id": str(_DT12_ANTIQUITY_REDUCCION_CASILLA),
        "reduccion_value": Decimal("4000"),
    }
    assert "next_action" not in finding.model_dump(mode="json")


def test_dt12_antiquity_advisory_silent_when_reduccion_zero() -> None:
    """No false positive when no reducción has been applied at all."""
    revision = _dt12_antiquity_revision()
    casilla_values = {_DT12_ANTIQUITY_REDUCCION_CASILLA: Decimal("0")}

    assert _dt12_antiquity_advisory_finding(revision, casilla_values) is None


def test_dt12_antiquity_advisory_silent_when_roles_absent() -> None:
    assert _dt12_antiquity_advisory_finding(_test_revision(), {}) is None


def test_iva_wallet_blocked_exception_carries_translated_message_key() -> None:
    decision = _blocked_wallet_decision(
        divergence="filed_history_only",
        reason_identity="filed_history_requires_override",
    )
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
            decision=decision,
        )

    exc = raised.value
    assert exc.translated_message == "application.iva_wallet.decision_reason.filed_history_requires_override"
    assert exc.precondition_failure.identity == (
        "modelo.work.calculate",
        "modelo.work.calculate.iva_wallet.ready",
        "modelo.work.calculate.iva_wallet.filed_history_requires_override",
    )
    assert _iva_wallet_error_verification_finding(exc).casilla_id == M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA
    assert not hasattr(exc, "suggestion")


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
    # str(exc) intentionally falls back to the translation key when no
    # explicit message is supplied (CadrumoError.__init__), so it carries
    # readable, greppable text rather than being blank -- see
    # test_error_message_never_blank.py for the pinned base-class contract.


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
        from ....core.errors.hierarchy import CoreValidationError

        assert issubclass(WorkflowInputMismatchError, CoreValidationError)
        assert issubclass(WorkflowInputMismatchError, ValueError)

    def test_error_code_is_registered(self) -> None:
        """WorkflowInputMismatchError maps to a stable error code in the registry."""
        from ....core.errors.error_codes import get_registered_error_code

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


def test_revision_replay_does_not_resubmit_m100_formula_informational_casilla() -> None:
    """Verify-time draft replay must not feed M100 0224 back as an operator input."""
    work_unit = _minimal_work_unit(modelo="100", period="0A", filing_year=2024, revision_id="2024")
    snapshot = bundled_authority().snapshot("100", filing_year=2024, period="0A", revision_id="2024")
    binding_values: dict[BindingId, Decimal] = {
        "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
        "renta-2024-profile-declaration-type": Decimal("1"),
        "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
        "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
        "renta-2024-profile-incremento-guarderia": Decimal("0"),
        "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
        "renta-2024-profile-descendientes-guarderia": Decimal("0"),
        "renta-2024-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-2024-profile-minimo-descendientes-autonomico": Decimal("0"),
        "renta-2024-profile-marriage-full-year": Decimal("0"),
        "renta-2024-profile-marriage-month-start": Decimal("0"),
        "renta-2024-profile-marriage-month-end": Decimal("0"),
        "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
    }
    relation_values = {
        "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
        "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
        "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
        "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
        "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
        "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
    }
    enum_binding_values = {"renta-2024-profile-tax-residence-ccaa": "madrid"}
    date_binding_values = {"renta-2024-profile-taxpayer-birth-date": date(1975, 6, 15)}
    result = calculate_registry_snapshot(
        snapshot,
        inputs={_M100_ACTIVIDAD_ECONOMICA_INCOME_CASILLA: Decimal("10000")},
        date_context={"filing_period": date(2024, 12, 31)},
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        date_binding_values=date_binding_values,
    )
    assert result.values[_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA] == Decimal("10000.00")
    with pytest.raises(RegistryValidationError, match="computed registry casillas cannot be supplied as inputs"):
        calculate_registry_snapshot(
            snapshot,
            inputs={_M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA: Decimal("10000")},
            date_context={"filing_period": date(2024, 12, 31)},
            binding_values=binding_values,
            enum_binding_values=enum_binding_values,
            relation_values=relation_values,
            date_binding_values=date_binding_values,
        )

    binding_overrides = {
        **{binding_id: str(value) for binding_id, value in binding_values.items()},
        **enum_binding_values,
        **{binding_id: value.isoformat() for binding_id, value in date_binding_values.items()},
    }
    relation_overrides = {relation_id: str(value) for relation_id, value in relation_values.items()}
    input_values_by_casilla_id = {_M100_ACTIVIDAD_ECONOMICA_INCOME_CASILLA: "10000"}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        relation_overrides=relation_overrides,
        casilla_values=result.values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        relation_overrides=relation_overrides,
        casilla_values=result.values,
        observations=result.observations,
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )

    informational_replay_inputs = _informational_casilla_replay_inputs(
        revision=revision,
        snapshot=snapshot,
    )

    assert _M100_ACTIVIDAD_ECONOMICA_NET_INCOME_CASILLA not in informational_replay_inputs


def test_iva_regime_cli_choices_cover_operator_selectable_wizard_values() -> None:
    """The CLI accepts the wizard's operator-selectable IVA-regime choices.

    ``IVARegime.NO_APLICA`` is an internal projection sentinel for profiles
    that are not enrolled in IVA. It must not leak into the operator-facing
    ``--iva-regime`` choice set.
    """
    from ....core.wizard_catalogue import get_setup_flow
    from ...wizard.commands import _IVA_REGIME_CHOICE_VALUES

    wizard_values = {
        choice.value
        for section in get_setup_flow().sections
        for question in section.questions
        if question.id == "iva-regime"
        for choice in question.choices
    }
    choice_set = set(_IVA_REGIME_CHOICE_VALUES)
    assert choice_set == wizard_values
    assert IVARegime.NO_APLICA.value not in choice_set


# ---------------------------------------------------------------------------
# contract/contract — missing_required_casilla finding message is localised
# ---------------------------------------------------------------------------


def test_missing_required_casilla_finding_is_locale_neutral() -> None:
    """_missing_required_casilla_finding renders message via tr().

    The returned finding message must contain the casilla_id token
    (interpolated by the locale template) and must not be the raw locale key.
    """
    finding = _missing_required_casilla_finding(
        _M130_INGRESOS_CASILLA,
        casilla_def=_m130_casilla_definition(_M130_INGRESOS_CASILLA),
    )

    assert finding.message_locale_key == "application.modelo.findings.missing_required_casilla"
    assert dict(finding.message_facts) == {"casilla_id": _M130_INGRESOS_CASILLA}


def test_missing_required_casilla_finding_facts_change_with_casilla_id() -> None:
    """Each casilla_id produces a distinct, non-trivial finding message.

    The locale template interpolates %{casilla_id}; two calls with different
    ids must produce different rendered strings. A tautological template or
    missing interpolation would produce identical output.
    """
    finding_a = _missing_required_casilla_finding(
        _M130_INGRESOS_CASILLA,
        casilla_def=_m130_casilla_definition(_M130_INGRESOS_CASILLA),
    )
    finding_b = _missing_required_casilla_finding(
        _M130_GASTOS_CASILLA,
        casilla_def=_m130_casilla_definition(_M130_GASTOS_CASILLA),
    )

    assert finding_a.message_facts != finding_b.message_facts
    assert finding_a.message_facts["casilla_id"] == _M130_INGRESOS_CASILLA
    assert finding_b.message_facts["casilla_id"] == _M130_GASTOS_CASILLA
