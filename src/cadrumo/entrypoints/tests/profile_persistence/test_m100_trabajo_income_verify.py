"""Verifying a Modelo 100 whose work-income boxes the filer has not stated reports them, it never raises.

A return resting on a work-income payer record blocks on each box no certificate fills until the
filer states it. Verification must report those boxes as blocking findings, each paired with the
verdict that names its door, and settle with a non-granted report. Real encrypted store, real
registered operations, real calculate and verify on the bundled authority.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.modelo.semantic_role_resolution import casilla_id_for_unique_revision_semantic_role
from cadrumo.application.modelo.trabajo_income_findings import TRABAJO_INCOME_STATEMENT_ROLES
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.modelos.verification_report import ModeloVerificationFindingSeverity
from cadrumo.tests.env_scope import ready_clave_settings

from .m130_m100_annual_support import (
    BUCKET_ID,
    M100_ANNUAL_PERIOD,
    OPERATOR_SCOPE_PORTS,
    T0,
    TAX_ID,
    YEAR,
    calculate_revision_from_bucket_aggregation,
    m100_non_relation_zero_bindings,
    seed_prior_year_m100,
)
from .renta_persona_support import PAYER_A, Persona, create_work, record_certificate, seed_profile, workflow_profile
from .verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

__all__ = ["secure_objects"]

_SALARIED = Persona(categories="trabajo")


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


def _statement_bindings(operation: PinnedAuthorityOperation) -> dict[str, str]:
    """The binding each box only the filer can state reads, by its casilla, from the edition itself."""
    revision = operation.snapshot("100", filing_year=YEAR, period=M100_ANNUAL_PERIOD).revision
    by_casilla = {casilla.id: casilla.binding for casilla in revision.casillas}
    bindings: dict[str, str] = {}
    for role in TRABAJO_INCOME_STATEMENT_ROLES:
        casilla_id = casilla_id_for_unique_revision_semantic_role(revision, role)
        assert casilla_id is not None
        binding = by_casilla[casilla_id]
        assert binding is not None
        bindings[str(casilla_id)] = str(binding)
    return bindings


def test_unstated_work_income_boxes_verify_to_blocking_findings_with_their_doors(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    seed_profile(_SALARIED)
    seed_prior_year_m100(secure_objects)
    record_certificate(
        operation,
        directory=tmp_path,
        payer=PAYER_A,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion="3000.00",
        importe_integro="24000.00",
    )
    statement = _statement_bindings(operation)
    # Every other box is stated; the four only the filer can state are left as the filer left them.
    bindings = {
        binding_id: value
        for binding_id, value in m100_non_relation_zero_bindings().items()
        if str(binding_id) not in statement.values()
    }
    revision = calculate_revision_from_bucket_aggregation(
        create_work(secure_objects, modelo="100", period=M100_ANNUAL_PERIOD),
        binding_values=bindings,
        work_unit_repository=WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects),
        clock=T0,
    ).revision

    with bundled_indexed_authority().operation() as verify_operation:
        result = verify_modelo_revision_with_preconditions(
            revision.calculation_revision_id,
            actor="renta-persona",
            workflow_profile=workflow_profile(_SALARIED),
            settings=ready_clave_settings(TAX_ID),
            operator_scope_ports=OPERATOR_SCOPE_PORTS,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            verification_repositories=build_test_verification_repository_bundle(),
            operation=verify_operation,
        )

    assert result.report.granted_verificado_completo is False
    unstated = {
        str(projection.finding.casilla_id): projection.precondition_failure
        for projection in result.finding_preconditions
        if projection.finding.message_locale_key.startswith("application.modelo.findings.trabajo_income_unstated.")
    }
    assert set(unstated) == set(statement)
    for box, failure in unstated.items():
        assert failure is not None
        assert failure.scenario_id == "modelo.work.verify.trabajo_income.unstated_source"
        action = failure.verdict.action
        assert action is not None
        assert action.action_id == "operator.modelo.work.attest_work_income"
        bound = {binding.argument_name: binding.value for binding in failure.verdict.argument_bindings}
        assert bound == {"work_unit_id": revision.work_unit_id}
        assert failure.verdict.missing_argument_names == ()
        # The override of the binding the box reads stays beside it, owing only the figure.
        (alternative,) = failure.verdict.alternative_actions
        assert alternative.action.action_id == "operator.modelo.work.override"
        alternative_bound = {binding.argument_name: binding.value for binding in alternative.argument_bindings}
        assert alternative_bound["binding_id"] == statement[box]
        assert alternative_bound["work_unit_id"] == revision.work_unit_id
        assert alternative.missing_argument_names == ("value",)
    # Every blocking finding carries its verdict and no warning does, so the report projects whole.
    for projection in result.finding_preconditions:
        blocks = projection.finding.severity is ModeloVerificationFindingSeverity.BLOCKING
        assert (projection.precondition_failure is not None) is blocks
