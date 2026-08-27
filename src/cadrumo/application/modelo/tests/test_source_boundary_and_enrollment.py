"""Tests for the source-boundary gate, safety net, and resolver enrollment.

Unhandled-source advisory: collect_unhandled_source_diagnostics is wired into the live
calculate path so any binding whose source has no enrolled resolver surfaces a
non-blocking advisory on source_diagnostics instead of silently blanking.

Resolver enrollment: LedgerRentaIncomeAggregationSourceResolver (M130 income),
OssIossLedgerSourceResolver (M369 OSS/IOSS), InvoiceCatalogueSourceResolver
(M349 collectible_invoice), and ForeignAssetsAggregationSourceResolver (M720
foreign_asset), and M184 attribution members (atribucion_member) are enrolled
in the live merge_source_resolutions tuple so they fire on their modelos.

Deferred source kinds: the remaining deferred source kinds (related_party_operation,
refund_operation) produce an 'unhandled_binding_source' advisory on source_diagnostics
rather than a silent blank, and are NOT on the manual_sources allowlist.

Boundary gate: assert_no_novel_source_kinds raises on a synthetic novel-source binding
so a TOML source that would resolve to blank fails fast instead of compiling silently.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import BindingSourceKind, Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.modelos import Modelo184MemberRow
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import DEFERRED_SOURCE_KINDS, ForeignAssetClass, ForeignAssetIngestObservation
from ...user_profile.preflight import build_profile_preflight_requirement
from .._action_errors import (
    ModeloAggregationBindingError,
    ModeloProfileReadinessError,
)
from .._calculation_actions import (
    BucketAggregationCalculationResult,
    assert_no_novel_source_kinds,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from .._work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)

_BUCKET_ID = "34900000-0000-4000-8000-000000000349"
_READY_PROFILE_FACTS = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Ready"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="source-boundary"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value="false"),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value="false"),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value="false"),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value="false"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
)
_ATTRIBUTION_PROFILE_FACTS = (
    UserProfileFact(path="identity.tax_id", value="E12345674"),
    UserProfileFact(path="identity.name", value="Ready CB"),
    UserProfileFact(path="activities.description", value="attribution-entity activity"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value="false"),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value="false"),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value="false"),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value="false"),
    UserProfileFact(path="taxpayer_type.entity_type", value="attribution_entity"),
    UserProfileFact(path="attribution_entity.legal_form", value="comunidad_bienes"),
    UserProfileFact(path="attribution_entity_socios.0.nif", value="22222222B"),
    UserProfileFact(path="attribution_entity_socios.0.name", value="Member Two"),
    UserProfileFact(path="attribution_entity_socios.0.share_pct", value=Decimal("40")),
    UserProfileFact(path="attribution_entity_socios.0.base_imponible_assigned", value=Decimal("4000")),
    UserProfileFact(path="attribution_entity_socios.0.participe_clave", value="1"),
    UserProfileFact(path="attribution_entity_socios.0.role", value="comunero"),
    UserProfileFact(path="attribution_entity_socios.1.nif", value="11111111A"),
    UserProfileFact(path="attribution_entity_socios.1.name", value="Member One"),
    UserProfileFact(path="attribution_entity_socios.1.share_pct", value=Decimal("60")),
    UserProfileFact(path="attribution_entity_socios.1.base_imponible_assigned", value=Decimal("6000")),
    UserProfileFact(path="attribution_entity_socios.1.participe_clave", value="1"),
    UserProfileFact(path="attribution_entity_socios.1.role", value="comunero"),
    UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
)


def _seed_ready_profile(*, bucket_id: str = _BUCKET_ID) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _seed_attribution_entity_profile(*, bucket_id: str = _BUCKET_ID) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_ATTRIBUTION_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_ready_profile()
        yield profile.repository


def _repos(
    objects: SecureObjectRepository,
) -> tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    TransactionCatalogueRepository,
    InvoiceCatalogueRepository,
]:
    return (
        WorkUnitCatalogueRepository(objects=objects),
        CalculationRevisionCatalogueRepository(objects=objects),
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
        InvoiceCatalogueRepository(objects=objects),
    )


def _seed(
    wu_repo: WorkUnitCatalogueRepository,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str,
):
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        revision_id=revision_id,
        repository=wu_repo,
        clock=_T0,
    )


# ---------------------------------------------------------------------------
# Boundary gate rejects novel source kinds
# ---------------------------------------------------------------------------


def test_s26_assert_no_novel_source_kinds_accepts_enrolled_revision() -> None:
    """A revision whose bindings use only enrolled/deferred sources passes the gate."""
    # M303 uses ledger_iva_aggregation, borrador, previous_filing, profile, manual_input —
    # all enrolled.  Gate must not raise.
    revision = bundled_authority().snapshot("303", filing_year=2026, period="1T").revision
    assert_no_novel_source_kinds(revision)  # no exception


def test_s26_assert_no_novel_source_kinds_accepts_deferred_revision() -> None:
    """A revision whose bindings use deferred source kinds still passes the gate."""
    # M190 uses 'withholding' — explicitly deferred.  Gate must not raise.
    revision = _revision("190", "2025-y-siguientes")
    assert_no_novel_source_kinds(revision)  # no exception


def test_s26_assert_no_novel_source_kinds_rejects_synthetic_novel_source() -> None:
    """A novel TOML source kind not in the enrolled or deferred set raises ModeloAggregationBindingError."""
    # Fabricate a revision with a synthetic unknown source by wrapping the real one.
    # model_construct bypasses Literal validation so we can inject a source value that
    # is not in the accepted set — exactly what the gate should detect and reject.
    from ....domain.calculations.registry.schema import DataBindingDefinition

    revision = bundled_authority().snapshot("303", filing_year=2026, period="1T").revision
    # Build a synthetic binding with a novel source kind via model_construct (no validators).
    synthetic_binding = DataBindingDefinition.model_construct(
        id="synthetic-test-binding",
        source="synthetic_novel_source_xyz",
    )
    # Graft the synthetic binding onto the revision's binding list via model_copy.
    patched = revision.model_copy(update={"bindings": (*revision.bindings, synthetic_binding)})

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        assert_no_novel_source_kinds(patched)

    message = exc_info.value.translated_message
    assert message is not None
    assert "novel_source_kind" in message
    ctx = exc_info.value.context
    assert ctx is not None
    novel_kinds = ctx["novel_source_kinds"]
    assert isinstance(novel_kinds, list)
    assert "synthetic_novel_source_xyz" in novel_kinds


# ---------------------------------------------------------------------------
# Unhandled-source advisory fires for a known-unrouted source
# ---------------------------------------------------------------------------


def test_s08_atribucion_member_profile_source_resolves_m184_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    """M184 ``atribucion_member`` rows resolve from real attribution-entity profile facts."""
    _seed_attribution_entity_profile()
    wu_repo, cr_repo, tx_repo, invoice_repo = _repos(secure_objects)
    work_unit = _seed(wu_repo, modelo="184", filing_year=2026, period="0A", revision_id="2025-y-siguientes")

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert isinstance(result, BucketAggregationCalculationResult)
    unrouted = [
        d
        for d in result.source_diagnostics
        if d.source_kind == "atribucion_member" and d.reason == "unhandled_binding_source"
    ]
    assert not unrouted, f"atribucion_member is enrolled and must not be unhandled: {unrouted}"
    assert result.revision.row_binding_values["modelo-184-member-row-nif"] == {"1": "11111111A", "2": "22222222B"}
    assert result.revision.row_binding_values["modelo-184-member-row-share"] == {"1": "60", "2": "40"}
    assert result.revision.row_binding_values["modelo-184-member-row-base-assigned"] == {
        "1": "6000",
        "2": "4000",
    }
    detail_rows = result.revision.detail_rows
    assert all(isinstance(row, Modelo184MemberRow) for row in detail_rows)
    member_rows = tuple(row for row in detail_rows if isinstance(row, Modelo184MemberRow))
    assert [row.nif for row in member_rows] == ["11111111A", "22222222B"]
    assert [row.importe for row in member_rows] == [Decimal("6000"), Decimal("4000")]


def test_s08_atribucion_member_missing_base_refuses_and_never_calculates_a_zero(
    tmp_path: Path,
) -> None:
    """A member row missing its assigned base refuses by name; nothing resolves to zero.

    The property is unchanged — a missing assigned base must never be derived
    from the share percentage or quietly become zero — but the layer that
    enforces it moved. ``attribution_entity_socios.1.base_imponible_assigned``
    is a required schema field, so the profile readiness gate refuses both work
    unit creation and calculation, naming the missing field by its operator
    label and the edit verb that fixes it. That is strictly louder than the source diagnostic it now
    shadows: the operator is told what to supply instead of reading a
    diagnostic attached to a revision that was computed anyway.

    Sequenced so the refusal under test is the CALCULATION one rather than the
    creation one: the profile is saved complete, the work unit created, and the
    fact then withdrawn. This is the reachable ordering — a work unit outliving
    a fact it depends on — and it proves the gate re-runs rather than trusting
    the readiness established at creation.
    """
    profile_facts = tuple(_ATTRIBUTION_PROFILE_FACTS)
    missing_path = "attribution_entity_socios.1.base_imponible_assigned"
    incomplete_facts = tuple(fact for fact in profile_facts if fact.path != missing_path)
    assert len(incomplete_facts) == len(profile_facts) - 1, "the withdrawn fact is not in the fixture"

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET_ID,
                facts=profile_facts,
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        wu_repo, cr_repo, tx_repo, invoice_repo = _repos(objects)
        work_unit = _seed(wu_repo, modelo="184", filing_year=2026, period="0A", revision_id="2025-y-siguientes")

        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET_ID,
                facts=incomplete_facts,
                created_at=_T0,
                updated_at=_T0,
            ),
        )

        with pytest.raises(ModeloProfileReadinessError) as refusal:
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                work_unit_repository=wu_repo,
                calculation_repository=cr_repo,
                transaction_repository=tx_repo,
                invoice_repository=invoice_repo,
                clock=_T1,
            )

        # No revision was persisted, so there is no zero-bearing row to read
        # back: the refusal happened before any value was resolved.
        assert cr_repo.load().for_work_unit(work_unit.work_unit_id) == ()

    context = refusal.value.context or {}
    # The refusal names the field the way the operator sees it in the profile
    # editor, not the internal row-indexed path. The expected label is derived
    # from the schema rather than written out here, so this asserts the refusal
    # routes through the canonical requirement builder instead of pinning one
    # spelling of the label.
    expected_label = build_profile_preflight_requirement(
        missing_path,
        schema=load_user_profile_schema(),
    ).label
    assert expected_label != missing_path, "label collapsed to the raw path; the assertion below is vacuous"
    assert expected_label in str(context.get("missing", "")), context
    assert context.get("modelo") == "184"


# ---------------------------------------------------------------------------
# Enrolled resolvers fire on their modelos
# ---------------------------------------------------------------------------


def test_s09_ledger_renta_income_resolver_enrolled_fires_on_m130(
    secure_objects: SecureObjectRepository,
) -> None:
    """LedgerRentaIncomeAggregationSourceResolver is enrolled and claims M130 source kind.

    M130 2019-y-siguientes bindings include 'ledger_renta_income_aggregation'.
    The resolver must appear in the live merge_source_resolutions execution and claim
    that source kind in the merged resolution's owned_sources.

    This test drives the resolver mesh directly (not the full formula engine) because
    M130 formulas require a 'previous_filing' value for irpf.previous_year_economic_activity_net_income
    — a prior-year carry-forward that is absent in a fresh empty bucket.  The resolver-mesh
    layer is the correct structural boundary for proving enrollment; formula execution is a
    separate concern exercised by the carry-forward continuity tests in
    test_modelo_130_carry_forward_continuity.py.
    """
    from ....core import Period
    from ...aggregation import (
        CalculationSourceContext,
        LedgerRentaIncomeAggregationSourceResolver,
        collect_unhandled_source_diagnostics,
        merge_source_resolutions,
    )
    from ...calculations import PreviousFilingSourceResolver
    from ...invoices import InvoiceCatalogueSourceResolver

    _wu_repo, _cr_repo, tx_repo, invoice_repo = _repos(secure_objects)
    revision = _revision("130", "2019-y-siguientes")
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision=revision,
        calculated_at=_T1,
    )
    from ...aggregation import (
        LedgerIvaAggregationSourceResolver,
        LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
        OssIossLedgerSourceResolver,
    )

    source_resolution = merge_source_resolutions(
        [
            LedgerIvaAggregationSourceResolver(
                transaction_repository=tx_repo,
                prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID),
            ).resolve(context),
            LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
                transaction_repository=tx_repo,
                prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID),
            ).resolve(context),
            LedgerRentaIncomeAggregationSourceResolver(transaction_repository=tx_repo).resolve(context),
            OssIossLedgerSourceResolver(candidates=()).resolve(context),
            InvoiceCatalogueSourceResolver(invoice_repository=invoice_repo).resolve(context),
            PreviousFilingSourceResolver().resolve(context),
        ],
    )

    # The merged owned_sources must include the ledger Renta income aggregation source.
    assert BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION in source_resolution.owned_sources, (
        f"LedgerRentaIncomeAggregationSourceResolver is not enrolled: owned_sources={source_resolution.owned_sources}"
    )
    # Confirm the test is non-vacuous: M130 revision must declare this source kind.
    assert any(str(b.source) == "ledger_renta_income_aggregation" for b in revision.bindings), (
        "M130 revision should contain ledger_renta_income_aggregation bindings for this test to be non-tautological"
    )
    # Unhandled advisory for this source kind must NOT appear.
    _pre_mesh_handled: frozenset[str] = frozenset({"profile", "borrador", "iva_wallet_decision"})
    handled = frozenset(source_resolution.owned_sources) | _pre_mesh_handled
    unhandled = collect_unhandled_source_diagnostics(
        revision,
        handled_sources=handled,
        manual_sources=frozenset({"manual_input"}),
    )
    unrouted_income = [d for d in unhandled if d.source_kind == "ledger_renta_income_aggregation"]
    assert not unrouted_income, (
        "LedgerRentaIncomeAggregationSourceResolver is enrolled but "
        f"'ledger_renta_income_aggregation' still appeared as unhandled: {unrouted_income}"
    )


def test_s09_oss_ioss_resolver_enrolled_fires_on_m369(
    secure_objects: SecureObjectRepository,
) -> None:
    """OssIossLedgerSourceResolver is enrolled and fires on M369 (esquema-union).

    With empty candidates the resolver returns an empty resolution but claims its
    owned source so the binding does not appear as unhandled on source_diagnostics.
    """
    wu_repo, cr_repo, tx_repo, invoice_repo = _repos(secure_objects)
    work_unit = _seed(wu_repo, modelo="369", filing_year=2026, period="1T", revision_id="esquema-union")

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert isinstance(result, BucketAggregationCalculationResult)
    unrouted_oss = [
        d
        for d in result.source_diagnostics
        if d.source_kind == "ledger_oss_aggregation" and d.reason == "unhandled_binding_source"
    ]
    assert not unrouted_oss, (
        "OssIossLedgerSourceResolver is enrolled but 'ledger_oss_aggregation' "
        f"still appeared as unhandled: {unrouted_oss}"
    )
    revision = _revision("369", "esquema-union")
    assert any(str(b.source) == "ledger_oss_aggregation" for b in revision.bindings), (
        "M369 esquema-union should contain ledger_oss_aggregation bindings for this test to be non-tautological"
    )


def test_s09_invoice_catalogue_resolver_enrolled_fires_on_m349(
    secure_objects: SecureObjectRepository,
) -> None:
    """InvoiceCatalogueSourceResolver is enrolled and fires on M349.

    With an empty invoice catalogue the resolver returns an empty resolution but
    claims its owned sources so 'collectible_invoice' does not appear as unhandled.
    """
    wu_repo, cr_repo, tx_repo, invoice_repo = _repos(secure_objects)
    work_unit = _seed(wu_repo, modelo="349", filing_year=2026, period="1T", revision_id="2020-y-siguientes")

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert isinstance(result, BucketAggregationCalculationResult)
    unrouted_invoice = [
        d
        for d in result.source_diagnostics
        if d.source_kind in {"collectible_invoice", "payable_invoice"} and d.reason == "unhandled_binding_source"
    ]
    assert not unrouted_invoice, (
        "InvoiceCatalogueSourceResolver is enrolled but invoice source kinds "
        f"still appeared as unhandled: {unrouted_invoice}"
    )
    revision = _revision("349", "2020-y-siguientes")
    assert any(str(b.source) == "collectible_invoice" for b in revision.bindings), (
        "M349 revision should contain collectible_invoice bindings for this test to be non-tautological"
    )


# ---------------------------------------------------------------------------
# Deferred source kinds produce advisory not silent blank
# ---------------------------------------------------------------------------


def test_s10_deferred_source_kinds_are_enumerated_and_non_empty() -> None:
    """DEFERRED_SOURCE_KINDS is non-empty and contains the expected deferred kinds."""
    expected = frozenset(
        {
            BindingSourceKind.RELATED_PARTY_OPERATION,
            BindingSourceKind.REFUND_OPERATION,
        },
    )
    assert expected.issubset(DEFERRED_SOURCE_KINDS), f"Missing deferred kinds: {expected - DEFERRED_SOURCE_KINDS}"
    assert BindingSourceKind.WITHHOLDING not in DEFERRED_SOURCE_KINDS
    assert BindingSourceKind.ATRIBUCION_MEMBER not in DEFERRED_SOURCE_KINDS


def _foreign_asset_observation(
    source_kind: BindingSourceKind,
    source_object_id: str,
    *,
    country: str,
    valuation: str,
    acquisition_date: str,
) -> ForeignAssetIngestObservation:
    return ForeignAssetIngestObservation(
        source_kind=source_kind,
        source_object_id=source_object_id,
        asset_class=ForeignAssetClass.ACCOUNT,
        asset_external_id=source_object_id.upper(),
        country=country,
        issuer_or_institution=f"Bank {country}",
        valuation_eur=Decimal(valuation),
        acquisition_date=acquisition_date,
    )


def test_s16_foreign_asset_source_kind_is_enrolled_not_deferred(tmp_path: Path) -> None:
    """M720 foreign_asset bindings are handled by the enrolled row-carrier resolver."""
    observations = (
        _foreign_asset_observation(
            BindingSourceKind.LEDGER_TRANSACTION,
            "a" * 64,
            country="AD",
            valuation="40000.00",
            acquisition_date="2020-01-15",
        ),
        _foreign_asset_observation(
            BindingSourceKind.PAYABLE_INVOICE,
            "asset-ch-002",
            country="CH",
            valuation="15000.00",
            acquisition_date="2021-02-20",
        ),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        _seed_ready_profile()
        wu_repo, cr_repo, tx_repo, invoice_repo = (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            InvoiceCatalogueRepository(objects=objects),
        )
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="720",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision_id="2013-y-siguientes",
            repository=wu_repo,
            clock=_T0,
        )
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            foreign_asset_observations=observations,
            clock=_T1,
        )

    assert BindingSourceKind.FOREIGN_ASSET not in DEFERRED_SOURCE_KINDS
    assert not [
        diagnostic
        for diagnostic in result.source_diagnostics
        if diagnostic.source_kind == BindingSourceKind.FOREIGN_ASSET.value
        and diagnostic.reason == "unhandled_binding_source"
    ]
    assert result.revision.row_binding_values["modelo-720-asset-row-class"] == {"1": "C", "2": "C"}
    assert result.revision.row_binding_values["modelo-720-asset-row-country"] == {"1": "AD", "2": "CH"}
    assert result.revision.row_binding_values["modelo-720-asset-row-valuation"] == {
        "1": "40000",
        "2": "15000",
    }


def test_s27_withholding_source_kind_is_enrolled_not_deferred() -> None:
    """M190 'withholding' bindings are handled by the enrolled withholding resolver."""
    from ...aggregation import collect_unhandled_source_diagnostics

    revision = _revision("190", "2025-y-siguientes")
    assert any(str(b.source) == "withholding" for b in revision.bindings), (
        "M190 2025-y-siguientes must declare withholding bindings for this test to be non-vacuous"
    )
    handled = frozenset(
        {
            BindingSourceKind.RELATION_PREFILL,
            BindingSourceKind.PROFILE,
            BindingSourceKind.BORRADOR,
            BindingSourceKind.IVA_WALLET_DECISION,
            BindingSourceKind.WITHHOLDING,
        },
    )
    unhandled = collect_unhandled_source_diagnostics(
        revision,
        handled_sources=handled,
        manual_sources=frozenset({BindingSourceKind.MANUAL_INPUT}),
    )
    withholding_advisories = [
        d for d in unhandled if d.source_kind == "withholding" and d.reason == "unhandled_binding_source"
    ]
    assert not withholding_advisories, (
        f"withholding is enrolled and must not appear as unhandled; unhandled={unhandled}"
    )
    assert BindingSourceKind.WITHHOLDING not in DEFERRED_SOURCE_KINDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@cache
def _revision(modelo: str, revision_id: str) -> ModeloRevision:
    modelo_def = bundled_authority().modelo(modelo)
    return modelo_def.revisions[revision_id]
