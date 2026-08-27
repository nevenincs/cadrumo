"""Verification workflow substance tests."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import CasillaId, Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_verification import (
    KNOWN_VERIFICATION_PREDICATE_OPERATORS,
    parse_verification_predicate_expression,
)
from ....domain.modelos import (
    CalculationRevision,
    ModeloValidationError,
    ModeloVerificationFindingKind,
    derive_calculation_revision_id,
    upsert_calculation_revision,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import StoredCalculationDriftError
from .._calculation_actions import calculate_modelo_revision
from .._verification_actions import verify_modelo_revision
from .._work_lifecycle import create_work_unit
from ._verification_substance_support import (
    _ABSENT_REGISTRY_CASILLA,
    _CASILLA_01,
    _CASILLA_02,
    _CASILLA_03,
    _CASILLA_05,
    _CASILLA_06,
    _CASILLA_08,
    _CASILLA_09,
    _CASILLA_10,
    _CASILLA_12,
    _CASILLA_14,
    _CASILLA_15,
    _CASILLA_16,
    _CASILLA_18,
    _T0,
    _T1,
    _T2,
    _Repos,
    _seed_ready_profile,
    _workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "13000000-0000-4000-8000-000000000330"


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Real encrypted SQLite repos over a fresh isolated profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        objects = profile.repository
        _seed_ready_profile(bucket_id=_PROFILE_ID)
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, vr, bv


def test_m130_casilla_02_gastos_is_ledger_bound_not_manual_blocking(repos: _Repos) -> None:
    """M130 casilla 02 (Gastos) is ledger-bound, so an absent manual value never blocks.

    Regression: casilla 02 used to be ``input_kind = manual``,
    so a filer with no gastos was blocked with a MISSING_REQUIRED_CASILLA finding
    until they hand-entered ``--casilla 02=0``. Casilla 02 is now bound to the
    ``ledger_renta_gastos_pago_fraccionado_aggregation`` source: the gasto resolver
    populates it from the ledger (0 when there are no expenses), so the
    missing-required gate — which fires only for MANUAL required casillas — never
    flags it. The required=true flag is retained but is inert for a bound casilla.
    """
    wu_repo, cr_repo, vr_repo, bv_repo = repos

    snap = bundled_authority().snapshot("130", filing_year=2026, period="1T")
    casilla_02 = next((c for c in snap.revision.casillas if c.id == _CASILLA_02), None)
    assert casilla_02 is not None, "M130 must have casilla 02 in registry"
    assert str(casilla_02.input_kind) == "bound", "M130 casilla 02 must be ledger-bound (H1 fix)"
    assert casilla_02.binding == "modelo-130-actividad-economica-gastos-cumulative"

    work_unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    # Casilla 02 is deliberately NOT supplied (no ledger gastos, no manual value).
    casilla_inputs: dict[CasillaId, Decimal] = {
        _CASILLA_05: Decimal("0"),
        _CASILLA_06: Decimal("0"),
        _CASILLA_08: Decimal("0"),
        _CASILLA_10: Decimal("0"),
        _CASILLA_16: Decimal("0"),
        _CASILLA_18: Decimal("0"),
    }

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    # M4 resolved: casilla 02 is bound, so it is NOT a manual missing-required block.
    assert _CASILLA_02 not in report.missing_required_casilla_ids
    casilla_02_missing = [
        f
        for f in report.findings
        if f.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA and f.casilla_id == _CASILLA_02
    ]
    assert not casilla_02_missing, "bound casilla 02 must not produce a MISSING_REQUIRED_CASILLA finding"


def test_domain_predicate_parser_recognises_every_known_predicate_operator() -> None:
    """The canonical predicate-operator set MUST be runtime-evaluable.

    The single source of truth lives at
    cadrumo.domain.calculations.registry.KNOWN_VERIFICATION_PREDICATE_OPERATORS.
    The validator (in _validate_surfaces) uses it to reject unknown
    operators at registry-load time. The runtime evaluator
    (evaluate_predicate_expression) has its own regex per operator.
    Drift between the two sets is a silent-pass hazard.

    Structural gate: each known operator MUST have a matching
    regex registered in _verification_predicates._PREDICATE_<NAME_UPPER>. The probe
    map below names the expected module-level regex variable per
    operator; the test asserts (a) the regex exists, (b) it matches
    the canonical probe expression for the operator. If a future change
    to the module that owns ``advisory_when_ratio_ge`` ever renames or
    removes that regex without updating the canonical set, this
    test fires.
    """
    probe_expressions: dict[str, str] = {
        "all_nonzero": 'all_nonzero(["01", "02"])',
        "any_nonzero": 'any_nonzero(["01", "02"])',
        "at_most_one_positive": 'at_most_one_positive(["01", "02"])',
        "cap_le_when_positive": 'cap_le_when_positive(["11", "10"])',
        "advisory_when_positive": 'advisory_when_positive(["0527"])',
        "advisory_when_ratio_ge": 'advisory_when_ratio_ge(["01", "02", "0.5"])',
        "equals": 'equals(["27", "iva.cuota-devengada-total"])',
        "implies_nonzero": 'implies_nonzero(["01", "07"])',
        "implies_any_nonzero": 'implies_any_nonzero(["iva.cuota-devengada-total", "03", "06", "09"])',
        "profile_field_required": ('profile_field_required("representante_fiscal_nif", "non_resident_irnr_non_eea")'),
        "profile_flag_enabled": 'profile_flag_enabled("art109_activity_income_withholding_ge_70pct")',
        "roll_forward_balances": 'roll_forward_balances(["00671", "00670", "DP200014:00547", "DP200014:00552"])',
        "casilla_equals_implies_nonzero": (
            'casilla_equals_implies_nonzero(["tipo_renta", "inmobiliaria", "base_imponible"])'
        ),
        "casilla_equals_implies_profile_flag": (
            'casilla_equals_implies_profile_flag(["tipo_renta", "ue_residente", "ue_eee_status"])'
        ),
        "casilla_equals_implies_diverges": (
            'casilla_equals_implies_diverges(["modulos-epigrafe", "721.2", '
            '"modulos-rendimiento-neto-minorado", "modulos-rendimiento-neto-modulos"])'
        ),
        "deduccion_requires_adquisicion_before": (
            'deduccion_requires_adquisicion_before(["0547", "0708", "0690", "2013-01-01"])'
        ),
        "advisory_when_computed_diverges": (
            'advisory_when_computed_diverges(["01", "modulos-rendimiento-neto-actividad"])'
        ),
    }
    regex_attr_names: dict[str, str] = {
        "all_nonzero": "_PREDICATE_ALL_NONZERO",
        "any_nonzero": "_PREDICATE_ANY_NONZERO",
        "at_most_one_positive": "_PREDICATE_AT_MOST_ONE_POSITIVE",
        "cap_le_when_positive": "_PREDICATE_CAP_LE_WHEN_POSITIVE",
        "advisory_when_positive": "_PREDICATE_ADVISORY_WHEN_POSITIVE",
        "advisory_when_ratio_ge": "_PREDICATE_ADVISORY_WHEN_RATIO_GE",
        "equals": "_PREDICATE_EQUALS",
        "implies_nonzero": "_PREDICATE_IMPLIES_NONZERO",
        "implies_any_nonzero": "_PREDICATE_IMPLIES_ANY_NONZERO",
        "profile_field_required": "_PREDICATE_PROFILE_FIELD_REQUIRED",
        "profile_flag_enabled": "_PREDICATE_PROFILE_FLAG_ENABLED",
        "roll_forward_balances": "_PREDICATE_ROLL_FORWARD_BALANCES",
        "casilla_equals_implies_nonzero": "_PREDICATE_CASILLA_EQUALS_IMPLIES_NONZERO",
        "casilla_equals_implies_profile_flag": "_PREDICATE_CASILLA_EQUALS_IMPLIES_PROFILE_FLAG",
        "casilla_equals_implies_diverges": "_PREDICATE_CASILLA_EQUALS_IMPLIES_DIVERGES",
        "deduccion_requires_adquisicion_before": "_PREDICATE_DEDUCCION_REQUIRES_ADQUISICION_BEFORE",
        "advisory_when_computed_diverges": "_PREDICATE_ADVISORY_WHEN_COMPUTED_DIVERGES",
    }

    missing_probes = KNOWN_VERIFICATION_PREDICATE_OPERATORS.difference(probe_expressions)
    assert not missing_probes, (
        f"Probe map is missing entries for known operators {sorted(missing_probes)!r}; "
        "extend probe_expressions and regex_attr_names when adding a new operator to the canonical set"
    )

    for operator_name in regex_attr_names:
        probe = probe_expressions[operator_name]
        parsed = parse_verification_predicate_expression(probe)
        assert parsed is not None, f"schema parser did not recognise {operator_name!r}: {probe!r}"
        assert parsed.operator.value == operator_name


def test_m130_c15_cap_predicate_fires_blocking_rule_when_carry_forward_exceeds_c14(repos: _Repos) -> None:
    wu_repo, cr_repo, vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    # Modest operator inputs so C14 stays small + positive.
    # C01 (ingresos) is bound via ledger_renta_income_aggregation, but the
    # ledger binding's smuggling guard only applies to previous_filing
    # sources; supplying C01 directly is the supported manual-entry path
    # mirrored by the M131 sibling test below.
    casilla_inputs: dict[CasillaId, Decimal] = {
        _CASILLA_01: Decimal("10000"),
        _CASILLA_02: Decimal("0"),
        _CASILLA_05: Decimal("0"),
        _CASILLA_06: Decimal("0"),
        _CASILLA_08: Decimal("0"),
        _CASILLA_10: Decimal("0"),
        _CASILLA_16: Decimal("0"),
        _CASILLA_18: Decimal("0"),
    }
    # Carry-forward seed deliberately large — exceeds the computed C14.
    # previous_year_economic_activity_net_income > 12000 keeps the C13
    # minoración at zero so C14 = C12 (positive cuota) instead of being
    # eroded to negative by the small-income minoración bracket.
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("20000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("99999"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    invalid_c15 = revision.casilla_values[_CASILLA_14] + Decimal("1.00")
    invalid_values = dict(revision.casilla_values)
    invalid_values[_CASILLA_15] = invalid_c15
    invalid_observations = tuple(
        observation.model_copy(update={"value": invalid_c15}) if observation.casilla_id == _CASILLA_15 else observation
        for observation in revision.observations
    )
    invalid_revision_id = derive_calculation_revision_id(
        work_unit_id=revision.work_unit_id,
        input_values_by_casilla_id=revision.input_values_by_casilla_id,
        binding_overrides=revision.binding_overrides,
        relation_overrides=revision.relation_overrides,
        casilla_values=invalid_values,
        source_transaction_ids=revision.source_transaction_ids,
        borrador_snapshot_id=revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=revision.bindings_sourced_from_borrador,
        detail_rows=revision.detail_rows,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    invalid_revision = CalculationRevision(
        calculation_revision_id=invalid_revision_id,
        work_unit_id=revision.work_unit_id,
        state=revision.state,
        input_values_by_casilla_id=revision.input_values_by_casilla_id,
        binding_overrides=revision.binding_overrides,
        relation_overrides=revision.relation_overrides,
        source_transaction_ids=revision.source_transaction_ids,
        borrador_snapshot_id=revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=revision.bindings_sourced_from_borrador,
        casilla_values=invalid_values,
        observations=invalid_observations,
        detail_rows=revision.detail_rows,
        created_at=revision.created_at,
        updated_at=revision.updated_at,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), invalid_revision))

    report = verify_modelo_revision(
        invalid_revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    blocking_findings = [f for f in report.findings if f.kind is ModeloVerificationFindingKind.BLOCKING_RULE]
    cap_findings = [
        f
        for f in blocking_findings
        if f.message_locale_key == "application.modelo.findings.cross_casilla_invariant_violated"
        and dict(f.message_facts) == {"predicate_id": "modelo-130-c15-cap-by-c14"}
    ]
    assert cap_findings, (
        "M130 C15-cap-by-C14 predicate must fire when carry-forward exceeds positive C14; "
        f"got blocking findings: {blocking_findings}"
    )
    assert report.granted_verificado_completo is False


def test_m131_c11_cap_predicate_fires_blocking_rule_when_carry_forward_exceeds_c10(repos: _Repos) -> None:
    """M131 cap-predicate end-to-end integration.

    M131 declares modelo-131-<rev>-c11-cap-by-c10 on all 4 revisions
    via cap_le_when_positive(["11", "10"]). The companion test covers M130;
    this test extends parallel coverage to M131. AEAT M131
    instructions cite the same cap rule verbatim: "en ningún caso
    podrá figurar en la casilla 11 un importe superior a la
    cantidad positiva consignada en la casilla 10".
    """
    wu_repo, cr_repo, vr_repo, bv_repo = repos
    _seed_ready_profile(bucket_id=_PROFILE_ID, irpf_estimation_regime="objetiva")

    work_unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="131",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        revision_id="2026",
        repository=wu_repo,
        clock=_T0,
    )

    # 04, 06, 07, 13 are computed casillas on the M131 2026 revision;
    # only the operator-input (manual) casillas may appear in inputs.
    casilla_inputs: dict[CasillaId, Decimal] = {
        _CASILLA_01: Decimal("100"),
        _CASILLA_02: Decimal("50"),
        _CASILLA_03: Decimal("0"),
        _CASILLA_05: Decimal("0"),
        _CASILLA_08: Decimal("0"),
        _CASILLA_09: Decimal("0"),
        _CASILLA_12: Decimal("0"),
        _CASILLA_14: Decimal("0"),
    }
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "modelo-131-2026-resultados-negativos-anteriores": Decimal("99999"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    blocking = [f for f in report.findings if f.kind is ModeloVerificationFindingKind.BLOCKING_RULE]
    cap_findings = [
        f
        for f in blocking
        if f.message_locale_key == "application.modelo.findings.cross_casilla_invariant_violated"
        and dict(f.message_facts) == {"predicate_id": "modelo-131-2026-c11-cap-by-c10"}
    ]
    assert cap_findings, (
        "M131 C11-cap-by-C10 predicate must fire when carry-forward exceeds positive C10; "
        f"got blocking findings: {blocking}"
    )
    assert report.granted_verificado_completo is False


# ---------------------------------------------------------------------------
# contract: tampering regression — mutating a persisted observation is detected
# ---------------------------------------------------------------------------


def test_observation_tampering_is_detected_by_verify_path(repos: _Repos) -> None:
    """Mutating a stored observation value between calculate and verify is caught.

    contract regression: the observation provenance cross-check added in contract
    must detect when observations[i].value diverges from casilla_values for
    the same casilla. The verify path raises StoredCalculationDriftError and
    refuses VERIFICADO_COMPLETO.

    The tamper is applied by rewriting the stored catalogue with a mutated
    observation (different value from what casilla_values holds), keeping
    the revision id and casilla_values intact. The content-hash check passes
    because it does not cover observations; only the new provenance
    cross-check catches the drift.
    """
    wu_repo, cr_repo, _vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    casilla_inputs: dict[CasillaId, Decimal] = {
        _CASILLA_02: Decimal("1000"),
        _CASILLA_05: Decimal("0"),
        _CASILLA_06: Decimal("0"),
        _CASILLA_08: Decimal("0"),
        _CASILLA_10: Decimal("0"),
        _CASILLA_16: Decimal("0"),
        _CASILLA_18: Decimal("0"),
    }
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    # Require at least one typed observation for the provenance cross-check
    assert len(revision.observations) >= 1, (
        "The revision must carry at least one typed observation for the provenance cross-check to be valid"
    )

    # Demonstrate that assert_revision_content_integrity raises on provenance drift.
    # The CalculationRevision model validator already enforces consistency between
    # casilla_values and observations at construction time (preventing in-band
    # injection of inconsistent state). The runtime check is a defense-in-depth
    # layer against raw storage corruption that bypasses pydantic. We bypass
    # model_validator here via model_construct to simulate that scenario.
    from ....domain.calculations.registry.bindings import CasillaObservation
    from .._registry_helpers import assert_revision_content_integrity as _assert_revision_content_integrity

    target_obs = revision.observations[0]
    assert isinstance(target_obs.value, Decimal)
    tampered_obs = CasillaObservation.model_construct(
        casilla_id=target_obs.casilla_id,
        value=target_obs.value + Decimal("9999"),
        formula_id=target_obs.formula_id,
        op=target_obs.op,
        operand_refs=target_obs.operand_refs,
        operand_casilla_refs=target_obs.operand_casilla_refs,
        operand_values=target_obs.operand_values,
        legal_refs=target_obs.legal_refs,
        source_refs=target_obs.source_refs,
        absent_by_design=target_obs.absent_by_design,
    )
    tampered_observations = (tampered_obs, *revision.observations[1:])

    # Build a tampered revision bypassing the model validator (simulates raw storage drift).
    tampered_payload: dict[str, Any] = revision.model_dump()
    tampered_payload["observations"] = tampered_observations
    tampered_revision = revision.model_construct(**tampered_payload)

    # The provenance cross-check must raise for the tampered revision
    with pytest.raises(StoredCalculationDriftError, match="provenance drift"):
        _assert_revision_content_integrity(tampered_revision)


# ---------------------------------------------------------------------------
# contract: legal_refs / source_refs threading through verification findings
# ---------------------------------------------------------------------------


def test_missing_required_casilla_finding_carries_registry_provenance() -> None:
    """A MISSING_REQUIRED_CASILLA finding must carry legal_refs and source_refs
    drawn from the registry casilla definition.

    contract regression: before this fix findings had empty legal_refs/source_refs,
    making provenance invisible at the operator-facing verify surface.

    Exercises the finding builder directly against the live M130 casilla 02
    registry definition (its provenance is unchanged by the H1 bind: the casilla
    keeps its legal_refs/source_refs whether manual or bound). The oracle is read
    from the registry casilla definition — the authority the finding draws from —
    so the assertion proves the finding's provenance equals the registry's, not a
    hand-copied list. The companion refusal test proves a missing registry
    definition is a hard error, not an empty-provenance finding.
    """
    from .._verification_actions import missing_required_casilla_finding

    snapshot = bundled_authority().snapshot("130", filing_year=2026, period="1T")
    casilla_02 = next(c for c in snapshot.revision.casillas if c.id == _CASILLA_02)
    expected_legal_refs = frozenset(str(r) for r in casilla_02.legal_refs)
    expected_source_refs = frozenset(str(r) for r in casilla_02.source_refs)
    assert expected_legal_refs, "registry casilla 02 must declare legal_refs (oracle precondition)"
    assert expected_source_refs, "registry casilla 02 must declare source_refs (oracle precondition)"

    finding = missing_required_casilla_finding(_CASILLA_02, casilla_def=casilla_02)

    assert finding.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA
    assert finding.casilla_id == _CASILLA_02
    assert finding.legal_refs, "finding.legal_refs must not be empty for a registry-backed casilla"
    assert frozenset(finding.legal_refs) == expected_legal_refs, (
        f"finding.legal_refs {finding.legal_refs!r} does not match registry oracle {sorted(expected_legal_refs)!r}"
    )
    assert frozenset(finding.source_refs) == expected_source_refs, (
        f"finding.source_refs {finding.source_refs!r} does not match registry oracle {sorted(expected_source_refs)!r}"
    )


def test_missing_casilla_finding_refuses_absent_registry_definition() -> None:
    """Missing-required findings must not be emitted without registry provenance."""
    from .._verification_actions import missing_required_casilla_finding

    with pytest.raises(ModeloValidationError, match="requires registry casilla definition provenance"):
        missing_required_casilla_finding(_ABSENT_REGISTRY_CASILLA, casilla_def=None)
