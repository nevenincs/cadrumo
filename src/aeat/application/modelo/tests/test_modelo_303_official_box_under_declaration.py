"""Modelo 303 official Diseño-de-Registros box projection (Stage 2).

The M303 2023-y-siguientes revision carries two casilla layers: the semantic
aggregate cuota casillas (``iva.repercutido.general``, ``iva.soportado.interiores``,
...) that the ledger source mesh populates and that feed the resultado chain, and
the official numbered Diseño-de-Registros boxes (ids "01".."77") that carry the
official ``export_refs`` the operator transcribes to the AEAT sede.

Stage 1 (commit 330ab6771) made the silent under-declaration non-silent: a
ledger-driven calculate folded real cuota into the semantic layer while every
official numbered cuota box stayed zero (``input_kind = "manual"``), and the
calculate path emitted an ``official_box_unpopulated`` advisory plus two ADVISORY
``implies_any_nonzero`` verify predicates.

Stage 2 (2026-06-13 dual-keying ADR, this module) POPULATES every in-scope cuota
box by a single-source PROJECTION: each numbered box flips to
``input_kind = "computed"`` with a single-leaf formula copying its semantic source
id, evaluated by the formula engine in topological order. The box therefore equals
its semantic source on every calculate — the projection's defining contract — and
the Stage-1 under-declaration advisory is retired (no manual cuota box remains).
The Stage-1 ADVISORY predicates are replaced by per-box ``equals`` BLOCKING_RULE
consistency predicates (box == semantic source) that catch a future mis-edit.

Real adapters (encrypted SQLite via ``isolated_runtime_profile`` →
``SecureObjectRepository`` + ``EphemeralMasterKeyProvider``), real catalogue
repositories, real registry authority, real calculation engine and verify gate. No
mocks/stubs/skips/xfail. The two seeded transactions carry DISTINCT non-equal cuotas
so a copy/contamination cannot satisfy the equality assertions, and each box-equals-
source assertion is registry-authoritative (the source is itself the registry-
computed value, never a hand-summed Decimal — no-tautological-calculation-tests).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import RegistryValidationError
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._verification_report import ModeloVerificationFindingKind
from ....domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import IvaWalletDecisionRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
    verify_modelo_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_BUCKET = "bucket-303-official-box"

# DISTINCT non-equal cuotas so the wiring is unmistakable: one INCOMING general-21
# sale (cuota → semantic iva.repercutido.general → official box 09) and one
# OUTGOING general-21 purchase (cuota → semantic iva.soportado.interiores →
# official box 29). The bases/cuotas are distinct across the two rows.
_SALE_BASE = Decimal("800.00")
_SALE_CUOTA = Decimal("168.00")
_PURCHASE_BASE = Decimal("200.00")
_PURCHASE_CUOTA = Decimal("42.00")

# The official numbered boxes the sale/purchase fixtures populate via projection.
_OFFICIAL_DEVENGADO_GENERAL_CUOTA = "09"
_OFFICIAL_DEDUCIBLE_INTERIORES_CUOTA = "29"

# Full Stage-2 box → semantic-source projection map (the ten in-scope cuota boxes).
# Each numbered box is projection-populated from the single semantic source it
# copies; on any calculate box == source must hold (the projection contract).
_BOX_SOURCE_MAP: dict[str, str] = {
    "09": "iva.repercutido.general",
    "06": "iva.repercutido.reducido",
    "03": "iva.repercutido.super-reducido",
    "11": "iva.autorepercutido.intracomunitaria.devengado",
    "13": "iva.autorepercutido.interior.devengado",
    "27": "iva.cuota-devengada-total",
    "29": "iva.soportado.interiores",
    "33": "iva.soportado.importaciones",
    "37": "iva.autorepercutido.intracomunitaria.deducible",
    "45": "iva.cuota-deducible-total",
}


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        yield profile.repository


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _store_profile(objects: SecureObjectRepository) -> None:
    UserProfileLifecycleRepository(bucket_id=_BUCKET, objects=objects).save(
        UserProfileRecord(
            profile_id=_BUCKET,
            display_name="Test runtime profile",
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                transaction_id=provider_id,
                booked_date=date(2026, 2, 10),
                value_date=date(2026, 2, 10),
                amount=amount,
                currency="EUR",
                counterparty="Cliente o proveedor",
                description=f"iva row {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="d" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "ledger_transaction"},
            ),
            "direction": direction,
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _wallet_decision() -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=Decimal("0.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason="official-box advisory fixture",
        wallet_captured_at=_T1,
        decided_at=_T1,
    )


def _seed_work_unit(wu_repo: WorkUnitCatalogueRepository):
    return create_work_unit(
        bucket_id=_BUCKET,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2023-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )


def _seeded_calculation(
    secure_objects: SecureObjectRepository,
) -> BucketAggregationCalculationResult:
    _store_profile(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(_wallet_decision())

    sale = _iva_transaction(
        "general-sale",
        direction=TransactionDirection.INCOMING,
        amount=_SALE_BASE + _SALE_CUOTA,
        taxable_base=_SALE_BASE,
        iva_amount=_SALE_CUOTA,
    )
    purchase = _iva_transaction(
        "general-purchase",
        direction=TransactionDirection.OUTGOING,
        amount=_PURCHASE_BASE + _PURCHASE_CUOTA,
        taxable_base=_PURCHASE_BASE,
        iva_amount=_PURCHASE_CUOTA,
    )
    # Non-vacuity: the two seeded cuotas are distinct, so the semantic-layer fold is
    # unmistakable (no copy/contamination can satisfy both legs).
    assert _SALE_CUOTA != _PURCHASE_CUOTA

    work_unit = _seed_work_unit(wu_repo)
    tx_repo.save(TransactionCatalogue.from_transactions((sale, purchase)))
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        actor="operator-A",
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=_wallet_decision(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_T1,
    )


# ---------------------------------------------------------------------------
# Stage 2a — calculate-path projection (box == semantic source)
# ---------------------------------------------------------------------------


def test_calculate_projects_official_boxes_from_semantic_sources(
    secure_objects: SecureObjectRepository,
) -> None:
    """A ledger-folded calculate populates the official boxes by projection.

    The semantic ``iva.repercutido.general`` / ``iva.soportado.interiores``
    casillas carry the seeded cuotas, and the official numbered boxes 09
    (devengado 21pct cuota) and 29 (deducible interiores cuota) now carry the SAME
    cuota — the projection copies the semantic source. The box equals its source
    registry-authoritatively (the source is the registry-computed value, never a
    hand-summed Decimal). The two seeded cuotas are distinct, so a copy/
    contamination cannot satisfy both legs.
    """
    result = _seeded_calculation(secure_objects)
    values = result.revision.casilla_values

    # Semantic layer carried the seeded cuotas.
    assert Decimal(values["iva.repercutido.general"]) == _SALE_CUOTA
    assert Decimal(values["iva.soportado.interiores"]) == _PURCHASE_CUOTA

    # Every in-scope box equals its semantic source (the projection contract).
    for box, source in _BOX_SOURCE_MAP.items():
        assert Decimal(values[box]) == Decimal(values[source]), (
            f"box {box} ({values[box]}) must equal its semantic source {source} ({values[source]})"
        )

    # Non-vacuous: the seeded distinct cuotas land on their boxes.
    assert Decimal(values[_OFFICIAL_DEVENGADO_GENERAL_CUOTA]) == _SALE_CUOTA
    assert Decimal(values[_OFFICIAL_DEDUCIBLE_INTERIORES_CUOTA]) == _PURCHASE_CUOTA
    assert _SALE_CUOTA != _PURCHASE_CUOTA

    # The Stage-1 under-declaration advisory is retired: with the boxes populated
    # by projection, no official_box_unpopulated diagnostic fires.
    assert not [diag for diag in result.source_diagnostics if diag.reason == "official_box_unpopulated"]


def test_calculate_rejects_caller_override_of_projected_box(
    secure_objects: SecureObjectRepository,
) -> None:
    """A caller cannot override a now-computed official box.

    After Stage 2 the official cuota boxes are ``input_kind = "computed"`` formula
    targets; supplying one through the manual casilla channel is refused by the
    engine (``computed registry casillas cannot be supplied as inputs``). This
    proves the box is no longer an operator-entered slot — its value comes
    exclusively from the single-source projection, so pull and calculate cannot
    diverge.
    """
    _store_profile(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(_wallet_decision())

    sale = _iva_transaction(
        "general-sale",
        direction=TransactionDirection.INCOMING,
        amount=_SALE_BASE + _SALE_CUOTA,
        taxable_base=_SALE_BASE,
        iva_amount=_SALE_CUOTA,
    )
    work_unit = _seed_work_unit(wu_repo)
    tx_repo.save(TransactionCatalogue.from_transactions((sale,)))

    with pytest.raises(RegistryValidationError, match="computed registry casillas cannot be supplied as inputs"):
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs={"09": _SALE_CUOTA},
            binding_values={
                "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
                "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
            },
            iva_compensation_decision=_wallet_decision(),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=event_repo,
            transaction_repository=tx_repo,
            clock=_T1,
        )


# ---------------------------------------------------------------------------
# Stage 2b — verify-path consistency (box-equals-source, no under-declaration)
# ---------------------------------------------------------------------------


def test_verify_passes_with_projected_boxes_and_no_under_declaration_advisory(
    secure_objects: SecureObjectRepository,
) -> None:
    """The verify gate no longer surfaces the Stage-1 under-declaration advisory.

    A ledger-folded revision now carries the cuota in its official boxes via
    projection, so the Stage-1 ``implies_any_nonzero`` under-declaration advisory
    (devengado art. 88 / deducible art. 92, ADVISORY) is retired and does not
    fire. The per-box ``equals`` consistency predicates hold (box == source by
    projection), so they surface NO BLOCKING finding — the projected filing is
    consistent.
    """
    result = _seeded_calculation(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    vr_repo = VerificationReportCatalogueRepository(objects=secure_objects)
    bv_repo = BucketEventHistoryRepository(objects=secure_objects)

    report = verify_modelo_revision(
        result.revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    # The retired Stage-1 under-declaration ADVISORY (devengado art. 88 +
    # rd-1624 art. 71 + orden) must be absent — the boxes are populated.
    under_declaration_advisories = [
        finding
        for finding in report.findings
        if finding.kind is ModeloVerificationFindingKind.ADVISORY
        and "ley-37-1992:art-88" in finding.legal_refs
        and "rd-1624-1992:art-71" in finding.legal_refs
        and "orden-eha-3786-2008:art-1" in finding.legal_refs
    ]
    assert not under_declaration_advisories

    # The per-box equals consistency predicates hold (box == source by
    # projection), so no BLOCKING_RULE finding cites their predicate-id shape.
    consistency_blockers = [
        finding
        for finding in report.findings
        if finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE and "dr303" in finding.message
    ]
    assert not consistency_blockers


def test_equals_consistency_predicate_blocks_a_drifted_box() -> None:
    """The equals consistency predicate refuses a box that has drifted from its source.

    Registry-authoritative gate: the M303 revision carries one ``equals`` BLOCKING_RULE
    predicate per projected box. Evaluated against a casilla-value map where a box has
    been mutated away from its semantic source (a simulated future mis-edit), the
    predicate is VIOLATED and the verify gate would refuse the filing. Against a map
    where every box equals its source (the projection's live state), every equals
    predicate holds. This proves the consistency operator is a real evaluator, not a
    tautology that cannot fail.
    """
    from .._verification_actions import _evaluate_verification_predicates

    auth = _authority_for_303()
    snap = auth.snapshot("303", filing_year=2026, period="1T")
    equals_predicates = tuple(
        p for p in snap.revision.verification_predicates if p.expression.strip().startswith("equals(")
    )
    assert len(equals_predicates) == len(_BOX_SOURCE_MAP), "every projected box must carry an equals predicate"

    profile = _workflow_profile()

    # Consistent state: box == source for every pair → no findings.
    consistent: dict[str, Decimal] = {}
    for index, (box, source) in enumerate(_BOX_SOURCE_MAP.items()):
        value = Decimal(10 + index)  # distinct non-zero per box so a copy cannot mask drift
        consistent[box] = value
        consistent[source] = value
    assert _evaluate_verification_predicates(equals_predicates, consistent, profile) == []

    # Drifted state: box 27 mutated away from its source → exactly one violation.
    drifted = dict(consistent)
    drifted["27"] = drifted["iva.cuota-devengada-total"] + Decimal("1")
    findings = _evaluate_verification_predicates(equals_predicates, drifted, profile)
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE


# ---------------------------------------------------------------------------
# Stage 2c — one-aggregation-path parity and export-ref value carriage
# ---------------------------------------------------------------------------


def test_each_projected_box_has_exactly_one_producing_formula() -> None:
    """No projected box has a second aggregation path.

    Each official box is produced by EXACTLY ONE projection formula whose
    expression is the single semantic casilla-id leaf — no binding, no relation,
    no second formula. One value keeps one aggregation path
    (one-aggregation-path-pull-equals-calculate,
    calculation-source-canonical-mechanism), so the pull path and the calculate
    path (both of which run the one formula graph) cannot diverge.
    """
    from collections import Counter

    snap = _authority_for_303().snapshot("303", filing_year=2026, period="1T")
    rev = snap.revision
    target_counts = Counter(f.target for f in rev.formulas)
    by_target = {f.target: f for f in rev.formulas}

    for box, source in _BOX_SOURCE_MAP.items():
        assert target_counts[box] == 1, f"box {box} must have exactly one producing formula, got {target_counts[box]}"
        formula = by_target[box]
        # The producing formula is a single-leaf projection naming the semantic source.
        assert formula.expression.op is None, f"box {box} projection must be a bare leaf, not an op"
        assert formula.expression.casilla == source, (
            f"box {box} projection must copy semantic source {source}, got {formula.expression.casilla}"
        )
        # No binding on the box casilla → no second aggregation surface.
        box_casilla = next(c for c in rev.casillas if c.id == box)
        assert box_casilla.binding is None, f"box {box} must carry no binding (projection only)"


def test_pull_and_calculate_paths_produce_equal_projected_box_values(
    secure_objects: SecureObjectRepository,
) -> None:
    """The pull path and the calculate path produce identical projected-box values.

    Both the live bucket-aggregation calculate path and the Sheets-pull path
    evaluate the SAME formula graph via ``calculate_registry_snapshot``, so a
    projection formula yields one transport-identical value. This regression runs
    the live calculate path (PATH A) and a standalone engine run over the same
    snapshot seeded with the same bound semantic values (PATH B, the pull-path
    shape) and asserts every projected box is equal across both — and non-zero, so
    a silent blank cannot pass as "equal".
    """
    # PATH A: live bucket-aggregation calculate.
    result = _seeded_calculation(secure_objects)
    live = {box: Decimal(result.revision.casilla_values[box]) for box in _BOX_SOURCE_MAP}
    live_sources = {src: Decimal(result.revision.casilla_values[src]) for src in _BOX_SOURCE_MAP.values()}

    # PATH B: standalone engine run over the same snapshot, seeded with the same
    # semantic source values the live path folded into the bound casillas. Both
    # paths call calculate_registry_snapshot, so the projection is transport-shared.
    from datetime import date as _date

    from ....domain.calculations.registry import InputKind, calculate_registry_snapshot

    snap = _authority_for_303().snapshot("303", filing_year=2026, period="1T")
    rev = snap.revision
    casilla_kind = {c.id: c.input_kind for c in rev.casillas}
    # The compensacion-pendiente-anteriores casilla is a previous_filing-bound
    # slot; feed it via binding_values, not inputs (the engine rejects a smuggled
    # previous_filing input). The computed-total sources (devengada/deducible
    # total) are produced by the engine, so they are NOT seeded as inputs.
    excluded = {"iva.compensacion-pendiente-periodos-anteriores"}
    inputs = {
        c.id: Decimal("0")
        for c in rev.casillas
        if c.input_kind not in (InputKind.COMPUTED, InputKind.INFORMATIONAL) and c.id not in excluded
    }
    # Seed only the BOUND semantic sources the live calculate folded in (the
    # computed-total sources are recomputed by the engine, never seeded).
    for source, value in live_sources.items():
        if casilla_kind.get(source) is InputKind.BOUND:
            inputs[source] = value
    relay = calculate_registry_snapshot(
        snap,
        inputs=inputs,
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        date_context={"filing_period": _date(2026, 3, 31)},
    )
    relay_boxes = {box: relay.values[box] for box in _BOX_SOURCE_MAP}

    # Non-vacuous: at least the two seeded cuotas land on their boxes, non-zero.
    assert live["09"] == _SALE_CUOTA and live["29"] == _PURCHASE_CUOTA
    assert Decimal("0") < _SALE_CUOTA and Decimal("0") < _PURCHASE_CUOTA

    # Parity: every projected box equals across the two transports.
    for box in _BOX_SOURCE_MAP:
        assert live[box] == relay_boxes[box], f"box {box} diverged: live={live[box]!r} pull-path={relay_boxes[box]!r}"


def test_export_ref_points_at_projected_box_carrying_value(
    secure_objects: SecureObjectRepository,
) -> None:
    """The casilla-27 export field references box 27, which now carries the projected value.

    The BOE/fichero export field ``modelo-303-page-01-casilla-27`` is wired to
    ``casilla = "27"`` (the numbered box). Stage 1 left box 27 manual and zero, so
    the export wrote zero. Stage 2 makes box 27 a projection of
    ``iva.cuota-devengada-total``, so the export field now reads the real cuota.
    This test confirms the export ref still targets the numbered box AND that the
    numbered box carries the positive projected value on a ledger-fed calculate.
    """
    snap = _authority_for_303().snapshot("303", filing_year=2026, period="1T")
    rev = snap.revision

    # The export layout field for casilla 27 references the numbered box "27".
    casilla_27 = next(c for c in rev.casillas if c.id == "27")
    assert "modelo-303-page-01-casilla-27" in tuple(casilla_27.export_refs), (
        "the casilla-27 export ref must still target the numbered box 27"
    )

    # On a ledger-fed calculate, box 27 carries the projected (non-zero) cuota,
    # equal to its semantic source — so the export reads value, not zero.
    result = _seeded_calculation(secure_objects)
    box_27 = Decimal(result.revision.casilla_values["27"])
    source_total = Decimal(result.revision.casilla_values["iva.cuota-devengada-total"])
    assert box_27 == source_total
    assert box_27 > Decimal("0"), "box 27 must carry the projected cuota, not zero, so the export writes value"


def _authority_for_303():
    from ....core.resources import resources

    return resources().modelos.authority
