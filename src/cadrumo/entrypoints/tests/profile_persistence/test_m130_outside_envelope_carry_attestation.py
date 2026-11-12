"""A filer states the previous ejercicio's net income for a Modelo 130 whose Modelo 100 the product cannot hold.

The first-quarter Modelo 130 reads the previous ejercicio's net activity income from that
year's Modelo 100 (RIRPF art. 110.3.c). At the support floor that Modelo 100 lies below the
floor, so no return for it can ever be held and no filing can prove the figure. The filer
states it instead: the operator layer keeps the figure apart from one merely typed, the
dependency reads clean on that statement, and verification reports it as stated. A source
year the envelope admits keeps the plain override surface and blocks as before.

Real behaviour throughout: an isolated encrypted profile, the bundled authority, the
production admission, edit executor and verification, with every year taken from the
published support envelope.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....application.calculations.cross_period_clean_state import cross_period_dependency_requirements
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditDomainRefusalV1,
    ModeloEditRefusalCode,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
)
from ....application.modelo.edit_services import validate_binding_intent
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....application.modelo.work_form_findings import ModeloFormAttention, finding_attention
from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.calculation_revision_operator_layer import ValueAttestation
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .observation_seeding_support import save_stamped_observation
from .verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The carry a first-quarter Modelo 130 reads from the previous ejercicio's Modelo 100.
_BINDING = "irpf.previous_year_economic_activity_net_income"
_ATTESTED_KEY = "application.modelo.findings.cross_period_dependency_operator_attested"
_CONFLICT_KEY = "application.modelo.findings.cross_period_dependency_attestation_conflict"
_STATED = Decimal("12846.30")
_STATED_CANONICAL = "12846.3"


def _support_floor() -> int:
    support = published_supported_filing_years()
    assert support is not None
    return support.floor


def _intent(kind: ModeloEditBindingIntentKind, value: Decimal | None = None) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(address=ModeloEditBindingAddressV1(binding_id=_BINDING), kind=kind, value=value)


def _attest(value: Decimal = _STATED) -> ModeloBindingEditIntentV1:
    return _intent(ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE, value)


def _set(value: Decimal = _STATED) -> ModeloBindingEditIntentV1:
    return _intent(ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE, value)


def _offered_intents(work: SeededOperatorWork) -> tuple[ModeloEditBindingIntentKind, ...]:
    (entry,) = (
        entry
        for entry in work.baseline().permitted_surface
        if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1) and entry.binding_id == _BINDING
    )
    return tuple(entry.allowed_intents)


def _verify(work: SeededOperatorWork) -> tuple[ModeloVerificationFinding, ...]:
    """Verify the work unit's current revision through the production gate; its findings."""
    result = verify_modelo_revision_with_preconditions(
        work.require_head().calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="operator-test",
        workflow_profile=TaxpayerProfile(tax_id="X0001500M", iva_regime=IVARegime("GENERAL")),
        operator_scope_ports=build_operator_scope_ports(),
        operation=work.operation,
    )
    return tuple(result.report.findings)


def _source_findings(
    findings: tuple[ModeloVerificationFinding, ...], kind: ModeloVerificationFindingKind
) -> list[ModeloVerificationFinding]:
    return [
        finding for finding in findings if finding.kind is kind and finding.message_facts.get("source_modelo") == "100"
    ]


def _hold_the_source(work: SeededOperatorWork, value: Decimal) -> None:
    """Capture the earlier Modelo 100 this declaration reads its carry from, with ``value`` in the box it reads."""
    snapshot = work.operation.snapshot(
        "130",
        filing_year=work.work_unit.filing_year,
        period="1T",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    (requirement,) = [item for item in cross_period_dependency_requirements(snapshot) if _BINDING in item.origin_ids]
    save_stamped_observation(
        CalculationObservationRepository(),
        registry_grounded_modelo_observation(
            modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=requirement.period.registry_token,
            casilla_values={requirement.source_casilla_ids[0]: value},
        ),
        source_kind="app_filing",
    )


@pytest.mark.parametrize("offset", [0, 1], ids=["floor", "floor-plus-one"])
def test_the_statement_is_offered_while_no_source_is_held(tmp_path: Path, offset: int) -> None:
    year = _support_floor() + offset
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=year, period_code="1T") as work,
    ):
        offered = _offered_intents(work)

    assert ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE in offered
    assert ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE in offered


def test_the_statement_is_refused_once_a_source_is_held(tmp_path: Path) -> None:
    year = _support_floor() + 1
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=year, period_code="1T") as work,
    ):
        # Inside the envelope the source can be held; once it is, the dependency follows it.
        _hold_the_source(work, Decimal("500"))
        offered = _offered_intents(work)
        refusal = validate_binding_intent(
            work.baseline(),
            ModeloEditBindingAddressV1(binding_id=_BINDING),
            ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
        )
        applied = work.apply(binding=(_attest(),))

    assert ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE not in offered
    assert ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE in offered
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert refusal.code is ModeloEditRefusalCode.DISALLOWED_INTENT
    # The executor refuses it too, and nothing is recorded.
    assert applied.refusal is not None
    assert applied.calculation_revision_id is None


def test_a_stated_figure_clears_the_dependency_as_stated_and_verification_reports_it(tmp_path: Path) -> None:
    floor = _support_floor()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=floor, period_code="1T") as work,
    ):
        assert work.apply(binding=(_attest(),)).refusal is None
        layer = work.require_head().operator_layer
        assert layer is not None
        assert layer.binding_overrides[_BINDING] == _STATED_CANONICAL
        assert layer.value_attestations == {
            _BINDING: ValueAttestation(source_modelo="100", source_filing_year=floor - 1, source_period="0A")
        }

        # Calculating again keeps the statement as the filer made it.
        recalculated = work.recalculate().operator_layer
        assert recalculated is not None
        assert recalculated.value_attestations == layer.value_attestations

        findings = _verify(work)

    assert not _source_findings(findings, ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN)
    (reported,) = [finding for finding in findings if finding.message_locale_key == _ATTESTED_KEY]
    assert reported.kind is ModeloVerificationFindingKind.ADVISORY
    assert reported.severity is ModeloVerificationFindingSeverity.WARNING
    assert reported.message_facts["source_modelo"] == "100"
    assert reported.message_facts["source_filing_year"] == floor - 1
    assert reported.message_facts["source_period"] == "0A"
    assert reported.message_facts["binding_id"] == _BINDING
    assert reported.message_facts["value"] == _STATED_CANONICAL
    assert reported.message_facts["target_modelo"] == "130"
    assert reported.message_facts["target_filing_year"] == floor
    # The statement is a disclosed limitation, so the form places it on its own level, never as a blocker.
    assert reported.disclosed_limitation is True
    assert finding_attention(reported) is ModeloFormAttention.LIMITATION


def test_a_stated_zero_is_one_statement_and_is_not_counted_again_as_a_zero_exemption(tmp_path: Path) -> None:
    floor = _support_floor()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=floor, period_code="1T") as work,
    ):
        assert work.apply(binding=(_attest(Decimal(0)),)).refusal is None
        findings = _verify(work)

    assert [finding.message_locale_key for finding in findings if "cross_period" in finding.message_locale_key] == [
        _ATTESTED_KEY
    ]


def test_a_figure_merely_typed_does_not_clear_the_dependency(tmp_path: Path) -> None:
    floor = _support_floor()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=floor, period_code="1T") as work,
    ):
        assert work.apply(binding=(_set(),)).refusal is None
        layer = work.require_head().operator_layer
        assert layer is not None
        assert layer.binding_overrides[_BINDING] == _STATED_CANONICAL
        assert layer.value_attestations == {}

        findings = _verify(work)

    blocking = _source_findings(findings, ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN)
    assert [finding.severity for finding in blocking] == [ModeloVerificationFindingSeverity.BLOCKING]
    assert not [finding for finding in findings if finding.message_locale_key == _ATTESTED_KEY]


def test_a_typed_figure_over_the_statement_withdraws_it_and_the_dependency_blocks_again(tmp_path: Path) -> None:
    floor = _support_floor()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=floor, period_code="1T") as work,
    ):
        assert work.apply(binding=(_attest(),)).refusal is None
        assert work.apply(binding=(_set(Decimal("100")),)).refusal is None
        layer = work.require_head().operator_layer
        assert layer is not None
        findings = _verify(work)

    assert layer.value_attestations == {}
    assert layer.binding_overrides[_BINDING] == "100"
    assert _source_findings(findings, ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN)
    assert not [finding for finding in findings if finding.message_locale_key == _ATTESTED_KEY]


def test_removing_the_override_withdraws_the_statement_with_the_figure(tmp_path: Path) -> None:
    floor = _support_floor()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=floor, period_code="1T") as work,
    ):
        assert work.apply(binding=(_attest(),)).refusal is None
        assert work.apply(binding=(_intent(ModeloEditBindingIntentKind.REMOVE_OVERRIDE),)).refusal is None
        layer = work.require_head().operator_layer

    assert layer is not None
    assert layer.value_attestations == {}
    assert _BINDING not in layer.binding_overrides


def test_a_blank_statement_is_refused_at_the_boundary() -> None:
    with pytest.raises(ValueError, match="requires a typed value"):
        _intent(ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE)


def test_a_stated_figure_clears_a_source_inside_the_envelope_the_application_does_not_hold(tmp_path: Path) -> None:
    floor = _support_floor()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=floor + 1, period_code="1T") as work,
    ):
        assert work.apply(binding=(_attest(),)).refusal is None
        findings = _verify(work)

    assert not _source_findings(findings, ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN)
    (reported,) = [finding for finding in findings if finding.message_locale_key == _ATTESTED_KEY]
    assert reported.message_facts["source_filing_year"] == floor


def test_a_figure_typed_over_a_source_inside_the_envelope_blocks_as_before(tmp_path: Path) -> None:
    floor = _support_floor()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=floor + 1, period_code="1T") as work,
    ):
        assert work.apply(binding=(_set(),)).refusal is None
        findings = _verify(work)

    blocking = _source_findings(findings, ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN)
    assert [finding.severity for finding in blocking] == [ModeloVerificationFindingSeverity.BLOCKING]
    assert blocking[0].message_facts["source_filing_year"] == floor
    assert not [finding for finding in findings if finding.message_locale_key == _ATTESTED_KEY]


def test_a_recorded_statement_and_a_source_that_later_appears_with_another_value_conflict(tmp_path: Path) -> None:
    floor = _support_floor()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=floor + 1, period_code="1T") as work,
    ):
        assert work.apply(binding=(_attest(),)).refusal is None
        _hold_the_source(work, Decimal("500"))
        findings = _verify(work)

    conflicts = [finding for finding in findings if finding.message_locale_key == _CONFLICT_KEY]
    assert [finding.severity for finding in conflicts] == [ModeloVerificationFindingSeverity.BLOCKING]
    assert conflicts[0].message_facts["value"] == _STATED_CANONICAL
    assert not [finding for finding in findings if finding.message_locale_key == _ATTESTED_KEY]


def test_a_recorded_statement_that_the_source_later_confirms_does_not_conflict(tmp_path: Path) -> None:
    floor = _support_floor()
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="130", filing_year=floor + 1, period_code="1T") as work,
    ):
        assert work.apply(binding=(_attest(),)).refusal is None
        _hold_the_source(work, _STATED)
        findings = _verify(work)

    assert not [finding for finding in findings if finding.message_locale_key == _CONFLICT_KEY]
