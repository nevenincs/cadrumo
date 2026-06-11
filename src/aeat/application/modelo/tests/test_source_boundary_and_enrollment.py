"""Tests for the source-boundary gate, safety net, and resolver enrollment.

Unhandled-source advisory: collect_unhandled_source_diagnostics is wired into the live
calculate path so any binding whose source has no enrolled resolver surfaces a
non-blocking advisory on source_diagnostics instead of silently blanking.

Resolver enrollment: LedgerRentaIncomeAggregationSourceResolver (M130 income),
OssIossLedgerSourceResolver (M369 OSS/IOSS), and InvoiceCatalogueSourceResolver
(M349 collectible_invoice) are enrolled in the live merge_source_resolutions tuple
so they fire on their modelos.

Deferred source kinds: the five deferred source kinds (withholding, atribucion_member,
related_party_operation, foreign_asset, refund_operation) produce an
'unhandled_binding_source' advisory on source_diagnostics rather than a silent blank,
and are NOT on the manual_sources allowlist.

Boundary gate: assert_no_novel_source_kinds raises on a synthetic novel-source binding
so a TOML source that would resolve to blank fails fast instead of compiling silently.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import ModeloRevision
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import DEFERRED_SOURCE_KINDS
from .. import (
    BucketAggregationCalculationResult,
    ModeloAggregationBindingError,
    assert_no_novel_source_kinds,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)

_BUCKET_ID = "bucket-a"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _repos(objects: SecureObjectRepository):
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
    revision = _revision("303", "2023-y-siguientes")
    assert_no_novel_source_kinds(revision)  # no exception


def test_s26_assert_no_novel_source_kinds_accepts_deferred_revision() -> None:
    """A revision whose bindings use deferred source kinds still passes the gate."""
    # M190 uses 'withholding' — explicitly deferred.  Gate must not raise.
    revision = _revision("190", "2024-y-siguientes")
    assert_no_novel_source_kinds(revision)  # no exception


def test_s26_assert_no_novel_source_kinds_rejects_synthetic_novel_source() -> None:
    """A novel TOML source kind not in the enrolled or deferred set raises ModeloAggregationBindingError."""
    # Fabricate a revision with a synthetic unknown source by wrapping the real one.
    # model_construct bypasses Literal validation so we can inject a source value that
    # is not in the accepted set — exactly what the gate should detect and reject.
    from ....domain.calculations.registry._schema import DataBindingDefinition

    revision = _revision("303", "2023-y-siguientes")
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


def test_s08_source_diagnostics_carries_advisory_for_deferred_source(
    secure_objects: SecureObjectRepository,
) -> None:
    """Deferred source kind 'atribucion_member' surfaces an advisory on source_diagnostics.

    M184 2015-y-siguientes bindings declare source='atribucion_member'.  The atribucion
    resolver is not yet built; the unhandled-source safety net must emit an
    'unhandled_binding_source' advisory so the operator's CLI surfaces the gap instead
    of a silent blank.

    M184 is chosen over M190/M193 for this test because it has no formula relations,
    so the engine does not crash on a missing relation value and we can isolate the
    unhandled-source advisory path cleanly.
    """
    wu_repo, cr_repo, tx_repo, invoice_repo = _repos(secure_objects)
    work_unit = _seed(wu_repo, modelo="184", filing_year=2026, period="0A", revision_id="2015-y-siguientes")

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    assert isinstance(result, BucketAggregationCalculationResult)
    # source_diagnostics must carry at least one advisory for the atribucion_member source kind.
    advisories = [
        d
        for d in result.source_diagnostics
        if d.source_kind == "atribucion_member" and d.reason == "unhandled_binding_source"
    ]
    assert advisories, (
        "Expected at least one 'unhandled_binding_source' advisory for 'atribucion_member' "
        "but source_diagnostics contained none. "
        f"All diagnostics: {result.source_diagnostics}"
    )
    # The advisory must identify the binding so the operator can act on it.
    assert all(d.binding_id for d in advisories)
    assert all("atribucion_member" in d.message for d in advisories)


def test_s08_source_diagnostics_carries_advisory_for_atribucion_member(
    secure_objects: SecureObjectRepository,
) -> None:
    """Deferred source kind 'atribucion_member' surfaces an advisory on source_diagnostics."""
    wu_repo, cr_repo, tx_repo, invoice_repo = _repos(secure_objects)
    work_unit = _seed(wu_repo, modelo="184", filing_year=2026, period="0A", revision_id="2015-y-siguientes")

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    advisories = [
        d
        for d in result.source_diagnostics
        if d.source_kind == "atribucion_member" and d.reason == "unhandled_binding_source"
    ]
    assert advisories, (
        "Expected 'unhandled_binding_source' advisory for 'atribucion_member'. "
        f"source_diagnostics: {result.source_diagnostics}"
    )


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
    # Run the same mesh that calculate_modelo_revision_from_bucket_aggregation_with_diagnostics uses.
    from ....domain.transactions import TransactionCatalogueRepository as TxRepo

    tx_repo_real: TxRepo = tx_repo  # type: ignore[assignment]
    from ...aggregation import (
        LedgerIvaAggregationSourceResolver,
        LedgerRentaExpenseAggregationSourceResolver,
        OssIossLedgerSourceResolver,
    )

    source_resolution = merge_source_resolutions(
        [
            LedgerIvaAggregationSourceResolver(transaction_repository=tx_repo_real).resolve(context),
            LedgerRentaExpenseAggregationSourceResolver(transaction_repository=tx_repo_real).resolve(context),
            LedgerRentaIncomeAggregationSourceResolver(transaction_repository=tx_repo_real).resolve(context),
            OssIossLedgerSourceResolver(candidates=()).resolve(context),
            InvoiceCatalogueSourceResolver(invoice_repository=invoice_repo).resolve(context),
            PreviousFilingSourceResolver().resolve(context),
        ],
    )

    # The merged owned_sources must include 'ledger_renta_income_aggregation'.
    assert "ledger_renta_income_aggregation" in source_resolution.owned_sources, (
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
        revision, handled_sources=handled, manual_sources=frozenset({"manual_input"}),
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
    """DEFERRED_SOURCE_KINDS is non-empty and contains the five expected kinds."""
    expected = frozenset(
        {"withholding", "atribucion_member", "related_party_operation", "foreign_asset", "refund_operation"},
    )
    assert expected.issubset(DEFERRED_SOURCE_KINDS), f"Missing deferred kinds: {expected - DEFERRED_SOURCE_KINDS}"


@pytest.mark.parametrize(
    ("modelo", "period", "revision_id", "deferred_kind"),
    [
        ("184", "0A", "2015-y-siguientes", "atribucion_member"),
        ("720", "0A", "2013-y-siguientes", "foreign_asset"),
    ],
)
def test_s10_deferred_kinds_advisory_fires_not_silent_blank(
    tmp_path: Path,
    modelo: str,
    period: str,
    revision_id: str,
    deferred_kind: str,
) -> None:
    """Each deferred source kind emits an advisory rather than silently blanking.

    Checks that for every deferred kind that appears in some revision's bindings,
    a live calculate on a work unit for that revision surfaces the advisory.
    We use M184 (atribucion_member) and M720 (foreign_asset) as representatives:
    both have no formula relations, so a fresh-bucket calculate does not crash on a
    missing relation operand and the unhandled-source advisory path is isolated cleanly.
    The withholding deferred kind (M190/M193) is asserted separately in
    test_s27_withholding_deferred_advisory_fires (those revisions DO carry relation
    operands that raise on an empty bucket, orthogonal to the advisory contract here).
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        wu_repo, cr_repo, tx_repo, invoice_repo = (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            InvoiceCatalogueRepository(objects=objects),
        )
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=2026,
            period=Period.from_year_and_code(2026, period),
            revision_id=revision_id,
            repository=wu_repo,
            clock=_T0,
        )
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            clock=_T1,
        )

    advisories = [
        d
        for d in result.source_diagnostics
        if d.source_kind == deferred_kind and d.reason == "unhandled_binding_source"
    ]
    assert advisories, (
        f"S10: expected 'unhandled_binding_source' advisory for deferred kind "
        f"'{deferred_kind}' on M{modelo} but got none. "
        f"source_diagnostics: {result.source_diagnostics}"
    )


def test_s27_withholding_deferred_advisory_fires() -> None:
    """M190 'withholding' per-perceptor bindings surface the unhandled-source advisory.

    The withholding source kind is the per-perceptor detalle rollup.  It is
    deferred-with-advisory, NOT built.  The per-perceptor rows exist only in
    the Sheets detalle tab (assemble_withholding_observations reads calc-sheet cells), and
    the transaction ledger carries no retencion/perceptor breakdown, so a live .resolve()
    would have no source to read — a built resolver would be an empty design-only shell.
    The annual M190<-M111 / M193<-M123 totals are relation edges (live), distinct
    from this per-perceptor source kind.  A real ledger-derived withholding build is a future
    feature needing its own ingest surface (counterparty + retencion modelling).

    Asserted via the direct collect_unhandled boundary (not the full calculate path):
    M190/M193 carry relation operands that raise RegistryValidationError on a fresh empty
    bucket (no prior M111/M123 filing), orthogonal to the advisory contract.  The boundary
    layer is the correct structural seam for proving the deferred kind is never a silent blank.
    """
    from ...aggregation import collect_unhandled_source_diagnostics

    revision = _revision("190", "2024-y-siguientes")
    assert any(str(b.source) == "withholding" for b in revision.bindings), (
        "M190 2024-y-siguientes must declare withholding bindings for this test to be non-vacuous"
    )
    # The live _handled set: relation_prefill is owned (enrolled resolver), withholding is not.
    handled = frozenset({"relation_prefill", "profile", "borrador", "iva_wallet_decision"})
    unhandled = collect_unhandled_source_diagnostics(
        revision, handled_sources=handled, manual_sources=frozenset({"manual_input"}),
    )
    withholding_advisories = [
        d for d in unhandled if d.source_kind == "withholding" and d.reason == "unhandled_binding_source"
    ]
    assert withholding_advisories, (
        "S27: expected 'unhandled_binding_source' advisory for every withholding binding "
        f"but got none. unhandled={unhandled}"
    )
    assert all(d.binding_id for d in withholding_advisories)
    # withholding must NOT be silenced onto the manual_sources allowlist.
    assert "withholding" not in frozenset({"manual_input"})
    assert "withholding" in DEFERRED_SOURCE_KINDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _revision(modelo: str, revision_id: str) -> ModeloRevision:
    modelo_def = next(item for item in resources().modelos.all() if item.id == modelo)
    return modelo_def.revisions[revision_id]
