"""M720 foreign-asset re-declaration advisory through the REAL calculate-then-verify path.

``test_modelo_720_prior_year_baseline_fidelity.py`` exercises the advisory
function directly, with all three observations hand-constructed. This module
proves the advisory reaches an operator: it drives
:func:`calculate_modelo_revision` (real registry engine, real persistence) and
then :func:`verify_modelo_revision` (real gate assembly) and asserts the finding
appears in the persisted :class:`VerificationReport`.

Scenario, grounded in RD 1065/2007 arts. 42-bis.5 / 42-ter.5 (€20,000
re-declaration delta over the last declared baseline):

- Year N declares cuentas €60,000 and valores €55,000 (both above the €50,000
  initial floor of art. 2.1), persisted as a real observation.
- Year N+1 holds cuentas €85,000 (+€25,000 > delta) and valores €65,000
  (+€10,000 <= delta) as per-asset-row evidence, but the operator omits the
  cuentas valuation from the declaration.

The advisory must fire for cuentas and only cuentas.

THE VACUITY TRAP THIS MODULE PINS: the declared set is read from
``input_values_by_casilla_id``, never from ``casilla_values``. The engine
materialises every declared casilla, emitting ``0`` for a valuation the
operator never supplied — so a declared set derived from ``casilla_values``
would always contain all three obligation bloques and the omitted-position test
could never be satisfied. ``test_declared_set_is_not_the_engine_zero_filled_casilla_values``
asserts the zero-fill is present and the advisory fires anyway, so a future
refactor onto ``casilla_values`` reds here instead of silently disarming the
guard.

See Also:
    :func:`~cadrumo.application.modelo._m720_redeclaration_gate.modelo_720_redeclaration_findings`
        Verify-time gate under test.
    :func:`~cadrumo.application.calculations.modelo_720_evidence_observation`
        Independent per-asset-row valuation projection.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ...tests import register_wizard_catalogue

__all__ = ["register_wizard_catalogue"]

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Modelo, Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.binding_selector_utils import selector_as_dict
from ....domain.calculations.registry.schema import DataBindingDefinition
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.deadlines.models import FiscalResidency, IVARegime, TaxpayerProfile
from ....domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind, ModeloVerificationFindingSeverity, VerificationReport
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository, modelo_720_prior_baseline_observation
from .._calculation_actions import _resolve_bucket_source_mesh, calculate_modelo_revision
from .._verification_actions import verify_modelo_revision
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "9a1c0e5e-2b1c-4f0e-8f7c-9d2f5b6a7c31"
_CLOCK_N = datetime(2024, 3, 15, 9, 0, 0, tzinfo=UTC)
_CLOCK_N_PLUS_1 = datetime(2025, 3, 15, 9, 0, 0, tzinfo=UTC)
_YEAR_N = 2023
_YEAR_N_PLUS_1 = 2024
_PERIOD = "0A"

_CUENTAS_VALORACION: CasillaId = validated_casilla_id("cuentas.valoracion", surface="_CUENTAS_VALORACION")
_VALORES_VALORACION: CasillaId = validated_casilla_id("valores.valoracion", surface="_VALORES_VALORACION")
_INMUEBLES_VALORACION: CasillaId = validated_casilla_id("inmuebles.valoracion", surface="_INMUEBLES_VALORACION")

# Year N declared baseline (both above the €50,000 art. 2.1 initial floor).
_CUENTAS_N = Decimal("60000.00")
_VALORES_N = Decimal("55000.00")
_INMUEBLES_N = Decimal("0.00")

# Year N+1 per-asset-row evidence.
# cuentas +25,000 (> €20,000 delta -> re-declaration owed per art. 42-bis.5)
# valores  +10,000 (<= €20,000 delta -> not owed per art. 42-ter.5)
_CUENTAS_N1 = Decimal("85000.00")
_VALORES_N1 = Decimal("65000.00")

#: Official Modelo 720 position-102 clave for a foreign account and a security.
_ACCOUNT_CLAVE = "C"
_SECURITY_CLAVE = "V"

_REDECLARATION_LOCALE_KEY = "application.modelo.findings.foreign_asset_redeclaration"


def _source_casilla_id(binding: DataBindingDefinition) -> CasillaId:
    """Validate the selector value before using it as a typed casilla key."""
    return validated_casilla_id(
        selector_as_dict(binding)["source_casilla_id"],
        surface="test_modelo_720_redeclaration_e2e.source_casilla_id",
    )


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET_ID,
                facts=(
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="activities.description", value="Foreign asset holder"),
                    UserProfileFact(path="iva.regime", value="GENERAL"),
                    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                    UserProfileFact(path="iva.m303_regime_composition", value="general"),
                    UserProfileFact(path="iva.redeme_enrolled", value=False),
                    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                ),
                created_at=_CLOCK_N,
                updated_at=_CLOCK_N,
            ),
        )
        yield


def _resident_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.RESIDENT_IRPF,
    )


def _calculate_and_verify(
    *,
    tmp_path: Path,
    declare_cuentas: bool,
) -> tuple[CalculationRevision, VerificationReport]:
    """Run the real year-N+1 M720 pipeline over a real persisted year-N baseline."""
    with _secure_backend(tmp_path):
        observation_repository = CalculationObservationRepository()
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                registry_grounded_modelo_observation(
                    modelo=Modelo.M720.value,
                    filing_year=_YEAR_N,
                    period=_PERIOD,
                    casilla_values={
                        _CUENTAS_VALORACION: _CUENTAS_N,
                        _VALORES_VALORACION: _VALORES_N,
                        _INMUEBLES_VALORACION: _INMUEBLES_N,
                    },
                ),
                source_kind="app_filing",
                captured_at=_CLOCK_N,
            )
        )

        snapshot = bundled_authority().snapshot(
            Modelo.M720.value,
            filing_year=_YEAR_N_PLUS_1,
            period=_PERIOD,
        )
        work_repository = WorkUnitCatalogueRepository()
        calculation_repository = CalculationRevisionCatalogueRepository()
        event_repository = BucketEventHistoryRepository()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo=Modelo.M720.value,
            filing_year=_YEAR_N_PLUS_1,
            period=Period.from_year_and_code(_YEAR_N_PLUS_1, _PERIOD),
            revision_id=snapshot.revision.id,
            repository=work_repository,
            clock=_CLOCK_N_PLUS_1,
        )

        casilla_inputs: dict[CasillaId, Decimal] = {
            _VALORES_VALORACION: _VALORES_N1,
            _INMUEBLES_VALORACION: _INMUEBLES_N,
        }
        if declare_cuentas:
            casilla_inputs[_CUENTAS_VALORACION] = _CUENTAS_N1

        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs=casilla_inputs,
            row_binding_values={
                ("modelo-720-asset-row-class", 1): _ACCOUNT_CLAVE,
                ("modelo-720-asset-row-valuation", 1): _CUENTAS_N1,
                ("modelo-720-asset-row-class", 2): _SECURITY_CLAVE,
                ("modelo-720-asset-row-valuation", 2): _VALORES_N1,
            },
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=event_repository,
            clock=_CLOCK_N_PLUS_1,
        )
        report = verify_modelo_revision(
            revision.calculation_revision_id,
            actor="system",
            workflow_profile=_resident_profile(),
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            calculation_observation_repository=observation_repository,
            clock=_CLOCK_N_PLUS_1,
        )
        return revision, report


def _redeclaration_findings(report: VerificationReport) -> tuple[ModeloVerificationFinding, ...]:
    """Return the re-declaration advisories, keeping their type for the callers.

    Typed as the real finding rather than ``object``: every caller reads
    ``kind``, ``severity`` and structured identity off the result, so erasing the
    element type turned each of those assertions into an unchecked attribute
    access on the one helper whose whole job is to hand findings to them.
    """
    return tuple(finding for finding in report.findings if finding.message_locale_key == _REDECLARATION_LOCALE_KEY)


def test_source_mesh_scopes_m720_prior_baselines_to_the_intended_work_unit_coordinate(tmp_path: Path) -> None:
    """The M720 mesh admits only the prior annual coordinate declared by the work unit."""
    prior_observation = registry_grounded_modelo_observation(
        modelo=Modelo.M720.value,
        filing_year=_YEAR_N,
        period=_PERIOD,
        casilla_values={
            _CUENTAS_VALORACION: _CUENTAS_N,
            _VALORES_VALORACION: _VALORES_N,
            _INMUEBLES_VALORACION: _INMUEBLES_N,
        },
    )
    snapshot_n1 = bundled_authority().snapshot(
        Modelo.M720.value,
        filing_year=_YEAR_N_PLUS_1,
        period=_PERIOD,
    )
    snapshot_n2 = bundled_authority().snapshot(
        Modelo.M720.value,
        filing_year=_YEAR_N_PLUS_1 + 1,
        period=_PERIOD,
    )
    expected_binding_values_n1 = {
        binding.id: prior_observation.casilla_values[_source_casilla_id(binding)]
        for binding in snapshot_n1.revision.bindings
        if binding.source is BindingSourceKind.PREVIOUS_FILING
    }
    expected_binding_ids_n2 = frozenset(
        binding.id for binding in snapshot_n2.revision.bindings if binding.source is BindingSourceKind.PREVIOUS_FILING
    )
    assert expected_binding_values_n1
    assert expected_binding_ids_n2

    with _secure_backend(tmp_path):
        observation_repository = CalculationObservationRepository()
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                prior_observation,
                source_kind="app_filing",
                captured_at=_CLOCK_N,
            )
        )
        work_unit_repository = WorkUnitCatalogueRepository()
        work_unit_n1 = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo=Modelo.M720.value,
            filing_year=_YEAR_N_PLUS_1,
            period=Period.from_year_and_code(_YEAR_N_PLUS_1, _PERIOD),
            revision_id=snapshot_n1.revision.id,
            repository=work_unit_repository,
            clock=_CLOCK_N_PLUS_1,
        )
        work_unit_n2 = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo=Modelo.M720.value,
            filing_year=_YEAR_N_PLUS_1 + 1,
            period=Period.from_year_and_code(_YEAR_N_PLUS_1 + 1, _PERIOD),
            revision_id=snapshot_n2.revision.id,
            repository=work_unit_repository,
            clock=_CLOCK_N_PLUS_1,
        )
        resolution_n1 = _resolve_bucket_source_mesh(
            snapshot_n1,
            work_unit_n1,
            transaction_repository=None,
            invoice_repository=None,
            foreign_asset_observations=(),
            foreign_asset_row_observations=(),
        )
        resolution_n2 = _resolve_bucket_source_mesh(
            snapshot_n2,
            work_unit_n2,
            transaction_repository=None,
            invoice_repository=None,
            foreign_asset_observations=(),
            foreign_asset_row_observations=(),
        )

    assert work_unit_n1.work_unit_id != work_unit_n2.work_unit_id
    assert work_unit_n1.bucket_id == work_unit_n2.bucket_id
    assert dict(resolution_n1.binding_values) == expected_binding_values_n1
    assert resolution_n1.unresolved_binding_ids == ()
    assert dict(resolution_n2.binding_values) == {}
    assert frozenset(resolution_n2.unresolved_binding_ids) == expected_binding_ids_n2

    previous_filing_provenance = tuple(
        item for item in resolution_n1.provenance if item.contributor_source_kind == "previous_filing"
    )
    assert previous_filing_provenance
    assert {item.dependency_treatment for item in previous_filing_provenance} == {"factual_evidence"}
    assert {item.source_ref.rsplit(":", maxsplit=1)[-1] for item in previous_filing_provenance} == frozenset(
        expected_binding_values_n1
    )

    projected = modelo_720_prior_baseline_observation(
        binding_values=resolution_n1.binding_values,
        modelo_revision=snapshot_n1.revision,
        filing_year=work_unit_n1.filing_year,
        period=work_unit_n1.period.registry_token,
    )
    projected_by_casilla = {item.casilla_id: item for item in projected.observations}
    expected_source_casillas = {
        _source_casilla_id(binding)
        for binding in snapshot_n1.revision.bindings
        if binding.id in expected_binding_values_n1
    }
    casillas_by_id = {casilla.id: casilla for casilla in snapshot_n1.revision.casillas}
    assert projected.modelo == work_unit_n1.modelo
    assert projected.filing_year == work_unit_n1.filing_year
    assert projected.period == work_unit_n1.period.registry_token
    assert set(projected_by_casilla) == expected_source_casillas
    assert all(item.formula_id is None for item in projected_by_casilla.values())
    assert all(
        item.value == prior_observation.casilla_values[casilla_id]
        and item.legal_refs == casillas_by_id[casilla_id].legal_refs
        and item.source_refs == casillas_by_id[casilla_id].source_refs
        for casilla_id, item in projected_by_casilla.items()
    )


def test_advisory_fires_through_real_verify_for_the_omitted_grown_cuentas_position(tmp_path: Path) -> None:
    """A grown cuentas bloque absent from the declaration surfaces a non-blocking advisory."""
    _revision, report = _calculate_and_verify(tmp_path=tmp_path, declare_cuentas=False)

    findings = _redeclaration_findings(report)
    assert len(findings) == 1, f"expected exactly one re-declaration advisory, got {findings}"
    finding = findings[0]

    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert dict(finding.message_facts) == {
        "modelo_code": "720",
        "filing_year": _YEAR_N_PLUS_1,
        "position_key": "cuentas",
        "group_code": "cuentas",
        "prior_value_eur": _CUENTAS_N,
        "current_value_eur": _CUENTAS_N1,
        "delta_value_eur": _CUENTAS_N1 - _CUENTAS_N,
        "redeclaration_increase_threshold_eur": Decimal("20000"),
    }
    # Grounding travels to the operator.
    assert "rd-1065-2007:art-42-bis" in finding.legal_refs
    assert finding.source_refs

    # The valores bloque grew by only €10,000 (<= the €20,000 delta) and must not fire.
    assert all(item.message_facts["group_code"] != "valores" for item in findings)


def test_advisory_is_silent_when_the_grown_position_is_declared(tmp_path: Path) -> None:
    """Declaring the grown cuentas valuation withdraws the advisory."""
    _revision, report = _calculate_and_verify(tmp_path=tmp_path, declare_cuentas=True)

    assert _redeclaration_findings(report) == ()


def test_declared_set_is_not_the_engine_zero_filled_casilla_values(tmp_path: Path) -> None:
    """The advisory survives the engine's zero-fill of the undeclared valuation casilla.

    The engine materialises ``cuentas.valoracion`` as ``0`` even though the
    operator never supplied it. Deriving the declared set from
    ``casilla_values`` would therefore mark the bloque declared and disarm the
    guard permanently. This pins both halves: the zero-fill is real, and the
    advisory still fires.
    """
    revision, report = _calculate_and_verify(tmp_path=tmp_path, declare_cuentas=False)

    assert revision.casilla_values[_CUENTAS_VALORACION] == Decimal("0"), (
        "expected the engine to zero-fill the undeclared valuation casilla; if this "
        "assumption ever changes, the declared-set projection should be revisited"
    )
    assert _CUENTAS_VALORACION not in revision.input_values_by_casilla_id, (
        "the operator input set must not contain the casilla the scenario deliberately omits"
    )
    assert len(_redeclaration_findings(report)) == 1, (
        "the advisory must fire despite the zero-fill — the declared set must come "
        "from input_values_by_casilla_id, never from casilla_values"
    )


def test_modelo_721_declares_no_independent_evidence_source(tmp_path: Path) -> None:
    """Modelo 721 carries no bindings, so it has no evidence channel to judge a declaration against.

    The shared advisory implementation covers M721, but wiring it at verify time
    would have to feed one observation into both the evidence and the
    declaration slot, and the omitted-position test would then be unsatisfiable
    — a guard that is wired, green, and permanently silent. This asserts the
    registry fact that makes the omission correct, so that if M721 ever gains a
    row-evidence binding the omission is revisited rather than forgotten.
    """
    with _secure_backend(tmp_path):
        snapshot = bundled_authority().snapshot(
            Modelo.M721.value,
            filing_year=2024,
            period=_PERIOD,
        )

    assert snapshot.revision.bindings == (), (
        "Modelo 721 has gained bindings — re-assess whether an independent "
        "current-valuation evidence channel now exists for the re-declaration advisory"
    )
    # Operator-typed values and declarant header fields only: nothing the
    # registry derives, so there is no second channel to test a declaration against.
    assert {casilla.input_kind for casilla in snapshot.revision.casillas} <= {
        InputKind.MANUAL,
        InputKind.INFORMATIONAL,
    }, "a BOUND or COMPUTED Modelo 721 casilla would signal a new independent evidence channel"
