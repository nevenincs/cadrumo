"""The simplified-regime annual summary resolves only for a revision that declares its binding family.

A salaried taxpayer states no IVA composition, so a Modelo 100 must calculate
without ever asking for one. Modelo 390 declares the family, and there a filer
who states no regime is still refused: the annual resumen needs the regime to
decide what its boxes carry.

Real encrypted catalogues, real registry snapshot, the live calculation mesh.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.calculations.m303_regimen_simplificado_annual_summary import (
    validate_m303_regimen_simplificado_annual_summary_target_revision,
)
from cadrumo.application.modelo.action_errors import ModeloProfileReadinessError
from cadrumo.application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.casilla_help import legal_ref_id_citation
from cadrumo.application.modelo.m303_regimen_simplificado_scope import m303_regimen_simplificado_annual_summary_applies
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.entrypoints.tests.profile_persistence.general_iva_profile_facts_support import (
    renta_single_taxpayer_facts,
)

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "39000000-0000-4000-8000-000000000393"
_T0 = datetime(_YEAR, 8, 14, 9, 0, tzinfo=UTC)
_T1 = datetime(_YEAR, 8, 14, 10, 0, tzinfo=UTC)
_SUMMARY = BindingSourceKind.M303_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY
#: The sources a filer with no history states for itself: a figure nothing prior supplies is zero.
_OPERATOR_STATED_SOURCES = frozenset({BindingSourceKind.MANUAL_INPUT, BindingSourceKind.PREVIOUS_FILING})

__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _seed_profile(*extra_facts: UserProfileFact, persona_without: Collection[str] | None = None) -> None:
    """Store a complete natural-person profile with the facts a test adds to the common ones.

    ``persona_without`` puts the canonical directa normal persona beneath the profile, leaving out
    the paths it names.
    """
    stated = (
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="identity.name", value="Test"),
        UserProfileFact(path="identity.surnames", value="Operator"),
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
        *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
        *extra_facts,
    )
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=stated if persona_without is None else persona_facts_beneath(stated, without=persona_without),
            created_at=_T0,
            updated_at=_T0,
            context=profile_creation_context_for_test(),
        )
    )


def _filing_year() -> int:
    """The last year before the horizon, whose own edition every modelo here authors."""
    return published_authority_operation().supported_filing_years().horizon - 1


def _calculate(modelo: str, secure_objects: SecureObjectRepository) -> BucketAggregationCalculationResult:
    year = _filing_year()
    work_units = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    calculations = CalculationRevisionCatalogueRepository(objects=secure_objects)
    filings = ModeloRecordCatalogueRepository(objects=secure_objects)
    snapshot = published_authority_operation().snapshot(modelo, filing_year=year, period="0A")
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=work_units,
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            operation=operation,
            clock=_T0,
        )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        calculation_repository=calculations,
        filing_repository=filings,
        invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        work_unit_repository=work_units,
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            binding_values={
                binding.id: Decimal(0)
                for binding in snapshot.revision.bindings
                if binding.source in _OPERATOR_STATED_SOURCES
            },
            ports=ports,
            clock=_T1,
        )


def test_a_revision_without_the_summary_binding_calculates_for_a_filer_with_no_iva_composition(
    secure_objects: SecureObjectRepository,
) -> None:
    revision = published_authority_operation().snapshot("100", filing_year=_filing_year(), period="0A").revision
    assert not any(binding.source is _SUMMARY for binding in revision.bindings)
    _seed_profile(UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"))

    result = _calculate("100", secure_objects)

    assert result.revision.m303_regimen_simplificado_annual_summary_handoff is None
    assert not [diagnostic for diagnostic in result.source_diagnostics if diagnostic.source_kind == _SUMMARY.value]


def test_a_revision_declaring_the_summary_binding_still_refuses_an_iva_filer_with_no_composition(
    secure_objects: SecureObjectRepository,
) -> None:
    """Teeth for the case above: where the family is declared, an IVA filer without a stated composition stays refused.

    Profile readiness names the missing composition before the mesh is reached; the
    scope mapper's own refusal for an absent composition is covered where it lives.
    """
    revision = published_authority_operation().snapshot("390", filing_year=_filing_year(), period="0A").revision
    assert any(binding.source is _SUMMARY for binding in revision.bindings)
    # An IVA filer who never stated how the regimes compose: Modelo 390 applies to them, but the composition is absent.
    # The simplified regime leaves the composition open (LIVA art. 122.Dos.1.º lets general-regime activities sit
    # beside it), whereas a declared general regime settles it, so only the simplified regime still owes the answer.
    _seed_profile(
        UserProfileFact(path="activities.description", value="activity"),
        UserProfileFact(path="iva.regime", value="SIMPLIFICADO"),
        persona_without=("iva.m303_regime_composition",),
    )

    with pytest.raises(ModeloProfileReadinessError) as refusal:
        _calculate("390", secure_objects)

    context = refusal.value.context
    assert context is not None
    # The refusal cites the grounding through the one citation renderer, so the operator reads the article, not the id.
    assert legal_ref_id_citation("ley-37-1992:art-122") in str(context["profile_requirements"])


def test_the_persisted_handoff_check_never_asks_a_filer_with_no_iva_composition_for_its_regime(
    secure_objects: SecureObjectRepository,
) -> None:
    """Verification, filing and export re-check the annual-summary handoff, which a Modelo 100 does not carry.

    The regime's scope is read from the IVA profile; asking it of a salaried filer
    refuses them, so the check asks only of a revision that declares the family.
    """
    _seed_profile(UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"))
    result = _calculate("100", secure_objects)
    work_unit = (
        WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
        .load()
        .work_units[result.revision.work_unit_id]
    )
    # The real judgement refuses this filer, so a check that asked it would refuse the Modelo 100.
    with pytest.raises(ModeloProfileReadinessError):
        m303_regimen_simplificado_annual_summary_applies(work_unit)
    asked: list[bool] = []

    def applies() -> bool:
        asked.append(True)
        return m303_regimen_simplificado_annual_summary_applies(work_unit)

    with bundled_indexed_authority().operation() as operation:
        validate_m303_regimen_simplificado_annual_summary_target_revision(
            target_work_unit=work_unit,
            target_revision=result.revision,
            work_unit_repository=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
            filing_repository=ModeloRecordCatalogueRepository(objects=secure_objects),
            regimen_simplificado_applies=applies,
            operation=operation,
        )

    assert asked == []
