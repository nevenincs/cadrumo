"""IS-3 full-stack E2E: a first-year modalidad-cuota M200 calculates, drafts, and verifies.

The companion unit tests
(``cadrumo.application.calculations.tests.test_modelo_200_202_pagos_fraccionados_fold``)
prove the IS-3 fix at the resolver boundary: with ``modelo_202_first_year_cuota``
set, ``resolve_relations_from_local_store`` resolves an otherwise-unresolved M202
fold-in relation to ``Decimal(0)`` instead of ``None`` (the value that crashed the
cuota-diferencial formula). But the landing commit claimed "verified end-to-end:
calculates -> verifies" while coverage stopped at that resolver unit. This module
closes that gap with the REAL operator pipeline:
``calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`` (draft build)
followed by ``verify_modelo_revision`` (verify), with the first-year flag derived
the production way - from the persisted profile, NOT passed in by the test.

Setup that triggers the live first-year flag
(:func:`_first_year_modalidad_cuota_no_m202`):
  - a legal-entity profile whose ``incn_prior_12_months`` (500.000) is at or below
    the LIS art. 40.3 INCN threshold (6.000.000), so the derived modality is
    ``ART_40_2_OPTIONAL`` (modalidad cuota); and
  - ``censo.activity_start_date`` in the filing year (2025), so 2025 is the
    taxpayer's FIRST Impuesto sobre Sociedades ejercicio (``year >= filing_year``);
  - NO Modelo 202 filed for 2025 (a first-year cuota filer has no prior IS return
    to base a pago fraccionado on - LIS art. 40.2).

Discriminator (vs the flag-OFF status quo pinned by
``test_modelo_200_fold_in_live.test_m200_missing_m202_relation_becomes_unresolved_advisory_on_live_calculate``,
which uses the SAME profile MINUS the activity-start date): with the flag OFF the
unfiled M202 pagos relation stays unresolved, the cuota-diferencial casilla
``DP200014B:00611`` is ABSENT, and a relation-prefill advisory names the missing
M202. With the flag ON (this test) the relation resolves to ``Decimal(0)``, the
cuota-diferencial formula COMPUTES (the casilla is PRESENT), and NO M202 advisory
fires - and the whole draft then VERIFIES end-to-end with no crash. So this test
fails if the first-year zero-resolution ever stops reaching the full calculate
action (the exact "coverage stopped at the resolver unit" hole).

Real-behaviour, real-adapter (encrypted-SQLite store via
:func:`isolated_runtime_profile`, real registry authority, real calculation engine,
real relation resolver + source mesh, real verify gate) - no mocks, stubs, skips,
or xfail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import RegistryAuthorityGrade
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ...calculations import CalculationObservationRepository
from ...tests import register_wizard_catalogue
from .._calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from .._verification_actions import verify_modelo_revision
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


__all__ = ["register_wizard_catalogue"]

_BUCKET_ID = "234af0d3-5002-452b-9eff-80bbc1de0c84"
_T0 = datetime(2026, 1, 12, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 12, 11, 0, tzinfo=UTC)
_M200 = "200"
_FILING_YEAR = 2025

# Cuota-diferencial: the formula operand that consumes the M202 pagos fold-in
# relation. Absent (unresolved) when the relation is None; present when the
# first-year flag resolves the unfiled relation to Decimal(0).
_CASILLA_CUOTA_DIFERENCIAL: CasillaId = validated_casilla_id(
    "DP200014B:00611",
    surface="_CASILLA_CUOTA_DIFERENCIAL",
)
_RELATION_PREFILL_SOURCE = "relation_prefill"


def _seed_first_year_modalidad_cuota_profile() -> None:
    """Seed a legal-entity profile that derives ART_40_2_OPTIONAL in its FIRST IS year.

    Mirrors the standard M200 six-binding sociedad scaffold, plus
    ``censo.activity_start_date`` in the filing year so
    :func:`_first_year_modalidad_cuota_no_m202` sees a first-ejercicio
    modalidad-cuota filer. ``incn_prior_12_months`` 500.000 <= the
    6.000.000 LIS art. 40.3 threshold -> ART_40_2_OPTIONAL (modalidad cuota).
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="identity.legal_name", value="First Year Cuota Test SL"),
            UserProfileFact(path="activities.description", value="software consultancy"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
            # First IS ejercicio: activity starts in the filing year, so a pago
            # fraccionado under modalidad cuota (art. 40.2) has no prior IS return.
            UserProfileFact(path="censo.activity_start_date", value="2025-01-01"),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    seed_test_profile_record(record)


def _calculate_m200(secure_objects: SecureObjectRepository) -> BucketAggregationCalculationResult:
    """Run the live M200/2025/0A calculate over the seeded bucket - NO M202 seeded."""
    _seed_first_year_modalidad_cuota_profile()
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = bundled_authority().snapshot(
        _M200,
        filing_year=_FILING_YEAR,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M200,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values={},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def test_first_year_modalidad_cuota_m200_calculates_drafts_and_verifies(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: a first-year cuota M200 with no M202 filed calculates (no crash) and verifies.

    The first-year flag is derived live from the persisted profile (ART_40_2_OPTIONAL
    + activity-start in the filing year), so the unfiled M202 pagos fold relation
    resolves to Decimal(0) rather than None. The cuota-diferencial formula therefore
    COMPUTES (casilla DP200014B:00611 is present) with no M202 relation advisory -
    the discriminator against the flag-OFF status quo where it stays unresolved - and
    the resulting draft then verifies end-to-end with no crash.
    """
    # 1) Draft build via the full calculate action.
    result = _calculate_m200(secure_objects)
    values = result.revision.casilla_values

    # The first-year zero-resolution reaches the FULL calculate: the cuota-diferencial
    # formula operand resolved (M202 relation -> 0), so the casilla is PRESENT.
    # (Flag-OFF status quo leaves it ABSENT - that is the discriminator.)
    assert _CASILLA_CUOTA_DIFERENCIAL in values, (
        "IS-3: a first-year modalidad-cuota M200 must resolve the unfiled M202 fold relation to 0 so the "
        f"cuota-diferencial {_CASILLA_CUOTA_DIFERENCIAL} COMPUTES on the full calculate; it is absent "
        f"(present keys sample: {sorted(values)[:8]}...)"
    )
    # And NO relation-prefill advisory names the M202 source (the flag resolved it,
    # so there is no unresolved-relation diagnostic for the missing M202 filing).
    m202_advisories = tuple(
        diag
        for diag in result.source_diagnostics
        if diag.source_kind == _RELATION_PREFILL_SOURCE and "202" in diag.message
    )
    assert m202_advisories == (), (
        "IS-3: the first-year flag must resolve the unfiled M202 relation (no unresolved advisory); "
        f"got {m202_advisories}"
    )

    # 2) Verify runs end-to-end over the draft - the closure of the overstated
    # "verified end-to-end" claim. We assert the verify gate produces a report for
    # this revision with no crash (grant/block verdict is not the subject here).
    report = verify_modelo_revision(
        result.revision.calculation_revision_id,
        actor="system",
        workflow_profile=TaxpayerProfile(tax_id="B12345674", iva_regime=IVARegime.GENERAL),
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        calculation_observation_repository=CalculationObservationRepository(objects=secure_objects),
    )
    assert report.calculation_revision_id == result.revision.calculation_revision_id, (
        "IS-3: verify must run end-to-end over the first-year M200 draft and return a report for the same "
        f"revision; got {report.calculation_revision_id!r} != {result.revision.calculation_revision_id!r}"
    )
