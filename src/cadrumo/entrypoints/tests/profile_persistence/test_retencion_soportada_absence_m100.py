"""Modelo 100 credit casillas 0596, 0597 and 0603 through the real calculation and source mesh.

A payer certificate of work income credits 1.200,00 retención plus 300,00
ingreso a cuenta, so casilla 0596 is 1.500,00 worked by hand. Capital mobiliario
(0597) and ganancias patrimoniales (0603) have no payer: they read zero only
where the profile declares those incomes absent or the operator attests that no
payer withheld on them, and stay blocking otherwise. All identifiers, notes and
amounts are synthetic.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.retencion_soportada_records import (
    RetencionSoportadaAbsenceRepositoryAdapter,
    RetencionSoportadaRecordRepositoryAdapter,
)
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.aggregation.retencion_soportada_absence_repository import (
    RetencionSoportadaAbsenceWritePorts,
    attest_retencion_soportada_absence,
)
from ....application.aggregation.retencion_soportada_repository import PinnedRetencionSoportadaWriteAuthority
from ....application.aggregation.source_precedence import CallerOverrideDisposition, precedence_ladder_sources
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_note_gate import blocking_calculation_issues
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_targets import casillas_by_binding
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.retencion_soportada_bindings import retencion_soportada_bindings
from ....domain.calculations.registry.runtime_graph import expression_binding_refs
from ....domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
    revision_covering,
)
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence
from ....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_TAXPAYER = "12345678Z"
_PAYER = "B00000001"
_YEAR = newest_authored_edition("100")
_PERIOD = "0A"
_CATEGORIES = "taxpayer_type.irpf_income_categories"
_CREDIT_CASILLAS = ("0596", "0597", "0603")
# Computed credit casillas whose formula reads a family binding as one operand.
_COMPUTED_CREDIT_CASILLAS = ("0598",)
_ABSENT_CLASSES = (RetencionSoportadaClase.CAPITAL_MOBILIARIO, RetencionSoportadaClase.GANANCIA_PATRIMONIAL)
# Sources the bucket calculation resolves itself or refuses from a caller; the locked half is
# derived from the caller-override ladder, so the suffered-withholding family is among them.
_MESH_RESOLVED_OR_LOCKED_SOURCES = frozenset(
    {"profile", "relation_prefill", BindingSourceKind.ACTIVITY_ASSET_DISPOSAL.value},
) | {kind.value for kind in precedence_ladder_sources(CallerOverrideDisposition.LOCK)}


def _revision_definition():
    return published_authority_operation().snapshot("100", filing_year=_YEAR, period=_PERIOD).revision


def _family_binding_ids() -> frozenset[BindingId]:
    return frozenset(binding.id for binding, _provider in retencion_soportada_bindings(_revision_definition()))


def _credit_targets() -> frozenset[BindingId]:
    """Every binding or relation that reaches a credit casilla, so no caller filler can stand in for the mesh."""
    revision = _revision_definition()
    targets = casillas_by_binding(revision)
    operands = {
        binding_id
        for formula in revision.formulas
        if str(formula.target_casilla_id) in _COMPUTED_CREDIT_CASILLAS
        for binding_id in expression_binding_refs(formula.expression)
    }
    return frozenset(
        binding_id for binding_id, casillas in targets.items() if set(casillas).intersection(_CREDIT_CASILLAS)
    ) | frozenset(operands)


def _zero_binding_values() -> dict[BindingId, Decimal]:
    revision = _revision_definition()
    alternates = {binding_id for casilla in revision.casillas for binding_id in casilla.alternate_bindings}
    excluded = {*alternates, *_credit_targets()}
    return {
        binding.id: Decimal("0")
        for binding in revision.bindings
        if binding.id not in excluded and binding.source not in _MESH_RESOLVED_OR_LOCKED_SOURCES
    }


def _zero_relation_values() -> dict[RelationId, Decimal]:
    revision = _revision_definition()
    credit = _credit_targets()
    return {
        binding.id: Decimal("0")
        for binding, _ in relation_prefill_bindings_for_period(revision)
        if binding.id not in credit
    }


@pytest.fixture
def objects(tmp_path: Path) -> Generator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_profile(categories: str) -> None:
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=_TAXPAYER),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    UserProfileFact(path="activities.description", value="economic activity"),
                    # A consulting activity, so no urban rental is carried on as an activity.
                    UserProfileFact(path="activities.iae_epigraph", value="844"),
                    UserProfileFact(path=_CATEGORIES, value=categories),
                    UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
                    UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                    UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
                    UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
                    UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
                    UserProfileFact(path="renta_filing.declaration_type", value="1"),
                    UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
                )
            ),
            created_at=datetime(filing_year_envelope().horizon, 4, 1, tzinfo=UTC),
            updated_at=datetime(filing_year_envelope().horizon, 4, 1, tzinfo=UTC),
            context=profile_creation_context_for_test(),
        ),
    )


def _attest_absent(objects: SecureObjectRepository, operation: PinnedAuthorityOperation) -> None:
    ports = RetencionSoportadaAbsenceWritePorts(
        attestations=RetencionSoportadaAbsenceRepositoryAdapter(objects=objects),
        records=RetencionSoportadaRecordRepositoryAdapter(objects=objects),
        authority=PinnedRetencionSoportadaWriteAuthority(operation),
    )
    for income_class in _ABSENT_CLASSES:
        attest_retencion_soportada_absence(
            RetencionSoportadaAbsence(
                ejercicio=_YEAR,
                income_class=income_class,
                note="Synthetic note: no payer withheld on this income.",
                attested_at=datetime(filing_year_envelope().horizon, 4, 2, 9, 0, tzinfo=UTC),
            ),
            ports=ports,
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )


def _calculate(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation, *, with_payer: bool = True
) -> CalculationRevision:
    work_unit_repository = WorkUnitCatalogueRepository(objects=objects)
    calculation_repository = CalculationRevisionCatalogueRepository(objects=objects)
    bucket_event_repository = BucketEventHistoryRepository(objects=objects)
    if with_payer:
        seed_payer_certificate(
            operation=operation,
            taxpayer_tax_id=_TAXPAYER,
            ejercicio=_YEAR,
            payer_tax_id=_PAYER,
            income_class=RetencionSoportadaClase.TRABAJO,
            retencion=Decimal("1200.00"),
            ingreso_a_cuenta=Decimal("300.00"),
        )
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        revision_id=str(revision_covering("100", _YEAR).id),
        ports=WorkLifecyclePorts(
            work_unit_repository=work_unit_repository, bucket_event_repository=bucket_event_repository
        ),
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator-A",
            binding_values=_zero_binding_values(),
            relation_values=_zero_relation_values(),
            ports=ports,
        ).revision


def _credit_blockers(revision: CalculationRevision) -> list[tuple[str, str | None]]:
    return sorted(
        (issue.reason, issue.casilla_id)
        for issue in blocking_calculation_issues(revision)
        if issue.binding_source is BindingSourceKind.RETENCION_SOPORTADA or issue.casilla_id in _CREDIT_CASILLAS
    )


def test_the_mesh_supplies_the_credit_casillas_and_no_caller_filler_reaches_them() -> None:
    assert _family_binding_ids() <= _credit_targets()
    assert _credit_targets().isdisjoint(_zero_binding_values())
    assert _credit_targets().isdisjoint(_zero_relation_values())


@pytest.mark.parametrize(
    ("categories", "attested"),
    [
        ("trabajo,actividad_economica", False),
        ("trabajo,actividad_economica,capital_mobiliario,ganancias_patrimoniales", True),
    ],
    ids=["declared-absent", "attested-absent"],
)
def test_a_class_with_no_payer_reads_zero_once_its_absence_is_proven(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation, categories: str, attested: bool
) -> None:
    _seed_profile(categories)
    if attested:
        _attest_absent(objects, operation)
    revision = _calculate(objects, operation)

    assert revision.casilla_values["0596"] == Decimal("1500.00")
    assert revision.casilla_values["0597"] == Decimal("0")
    assert revision.casilla_values["0603"] == Decimal("0")
    assert _credit_blockers(revision) == []


def test_a_declared_class_with_no_payer_and_no_attestation_blocks_instead_of_reading_zero(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    _seed_profile("trabajo,actividad_economica,capital_mobiliario,ganancias_patrimoniales")
    revision = _calculate(objects, operation)

    assert revision.casilla_values["0596"] == Decimal("1500.00")
    assert "0597" not in revision.casilla_values
    assert "0603" not in revision.casilla_values
    assert _credit_blockers(revision) == [("unresolved_binding", "0597"), ("unresolved_binding", "0603")]


def test_declared_work_income_with_no_payer_record_and_no_attestation_leaves_0596_unresolved(
    objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> None:
    """Work income the profile declares, with no payer certificate, cannot read as a zero credit.

    The profile declares trabajo, so the work-income credit 0596 has a payer to come from; with no
    payer record and no absence attestation nothing proves it zero, and the box stays out of the
    result with a blocking issue. Capital mobiliario and ganancias are not declared, so they read zero.
    """
    _seed_profile("trabajo,actividad_economica")
    revision = _calculate(objects, operation, with_payer=False)

    assert "0596" not in revision.casilla_values
    assert revision.casilla_values["0597"] == Decimal("0")
    assert revision.casilla_values["0603"] == Decimal("0")
    assert _credit_blockers(revision) == [("unresolved_binding", "0596")]
