"""Inventory resolver boundary tests for registry-owned row templates.

The inventory boundary restores the displaced encrypted success, absence,
corruption, conflict, fingerprint/tamper, determinism, and multi-activity
cohort matrix once runtime activity-row expansion exists. It must fail closed
without reading storage.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import get_args

import pytest
from pydantic import ValidationError

from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    published_work_profile_declaring_activities,
)
from cadrumo.domain.calculations.registry.irpf_regimes import (
    irpf_estimation_regime_directa_normal_token,
    irpf_estimation_regime_directa_simplificada_token,
    irpf_estimation_regime_objetiva_token,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    newest_authored_edition,
    projected_exercise,
    supported_exercises_with_projection,
)
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.user_profile.values import UserProfileFact

from ....core.aggregation import (
    BindingAggregation,
    BindingAggregationOp,
    BindingSourceKind,
    CalculationSourceLineageRole,
)
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ....domain.calculations.registry.inventory_bindings import InventoryProjectionOperation, InventoryProvider
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    InventoryClosingValuationBasis,
    InventoryLedgerError,
    PhysicalClosingEvidence,
    PhysicalClosingEvidenceRole,
    PhysicalClosingObservation,
    PriorClosingContinuityEvidence,
    fingerprint_prior_authoritative_closing,
)
from ....domain.contribuyente.inventory.records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    InventoryHistoryKind,
    InventoryLedger,
    InventoryLedgerDocument,
    InventoryLedgerHistoryEntry,
    InventoryRetirementReason,
    MovementRecord,
    ValuationMethod,
)
from ....domain.contribuyente.inventory.valuation import compute_inventory_anexo_d_projection
from ....domain.filing_evidence import FilingEvidenceReference
from ..inventory import VALUE_ATTRIBUTE_BY_OPERATION, InventorySourceResolver
from ..source_mesh import CalculationSourceContext
from ..terminal_origin_audit import collect_terminal_origin_diagnostics
from .inventory_source_support import closed_no_stock_ledger, fresh_inventory_ledger

_ESTIMATION_REGIME = "irpf.estimation_regime"

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


class _InventoryLedgerRepositoryScenario:
    def __init__(self, document: InventoryLedgerDocument | None = None, *, error: bool = False) -> None:
        self.loads = 0
        self.document = document or InventoryLedgerDocument(ledgers=())
        self.error = error

    def load(self) -> InventoryLedgerDocument:
        self.loads += 1
        if self.error:
            raise InventoryLedgerError("sensitive storage detail")
        return self.document


def _ref(value: str) -> FilingEvidenceReference:
    return FilingEvidenceReference(reference=value)


def inventory_ledger(
    actividad_id: str,
    *,
    physical_closing: Decimal | None = None,
    year: int | None = None,
) -> InventoryLedger:
    """Build one complete activity ledger for ``year``, the newest authored Modelo 100 edition by default."""
    year = newest_authored_edition("100") if year is None else year
    continuity = (PriorClosingContinuityEvidence(reference=_ref(f"prior-{actividad_id}"), content_digest="f" * 64),)
    acquisition = InventoryAcquisitionCost(
        consideration_excluding_iva=Decimal("100.00"),
        consideration_iva_amount=Decimal("21.00"),
        consideration_deductible_iva_ratio=Decimal("1"),
        attributable_cost_components=(),
        evidence=(
            InventoryAcquisitionEvidence(
                reference=_ref(f"invoice-{actividad_id}"),
                evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
                content_digest="a" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref(f"cost-{actividad_id}"),
                evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
                content_digest="b" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref(f"iva-{actividad_id}"),
                evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
                content_digest="c" * 64,
            ),
        ),
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=_ref(f"invoice-{actividad_id}"),
            attributable_cost_review_evidence=_ref(f"cost-{actividad_id}"),
            iva_recoverability_review_evidence=_ref(f"iva-{actividad_id}"),
        ),
        directly_attributable_cost_total=Decimal("0.00"),
        nonrecoverable_iva_included=Decimal("0.00"),
        recoverable_iva_excluded=Decimal("21.00"),
        total_acquisition_cost=Decimal("100.00"),
    )
    movement = MovementRecord.from_purchase_acquisition(
        movement_id=f"purchase-{actividad_id}",
        movement_date=date(year, 2, 1),
        quantity=Decimal("1"),
        acquisition_cost=acquisition,
    )
    observation = None
    if physical_closing is not None:
        observation = PhysicalClosingObservation(
            observation_id=f"physical-{actividad_id}",
            observed_on=date(year + 1, 1, 1),
            as_of_date=date(year, 12, 31),
            actividad_id=actividad_id,
            filing_year=year,
            closing_value=physical_closing,
            valuation_basis=InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
            evidence=(
                PhysicalClosingEvidence(
                    reference=_ref(f"count-{actividad_id}"),
                    role=PhysicalClosingEvidenceRole.PHYSICAL_COUNT,
                    content_digest="1" * 64,
                ),
                PhysicalClosingEvidence(
                    reference=_ref(f"value-{actividad_id}"),
                    role=PhysicalClosingEvidenceRole.ACQUISITION_PRICE_VALUATION,
                    content_digest="2" * 64,
                ),
            ),
        )
    prior_fingerprint = fingerprint_prior_authoritative_closing(
        actividad_id=actividad_id,
        filing_year=year - 1,
        authoritative_closing_value=Decimal("100.00"),
        authoritative_source_fingerprint="e" * 64,
        evidence=continuity,
    )
    return InventoryLedger.model_validate(
        {
            "actividad_id": actividad_id,
            "year": year,
            "valuation_method": ValuationMethod.FIFO,
            "opening_stock": Decimal("100.00"),
            "period_movements": (movement,),
            "closing_authority_record": {
                "decision": {
                    "decision_id": f"decision-{actividad_id}",
                    "actividad_id": actividad_id,
                    "filing_year": year,
                    "authority": InventoryClosingAuthority.MOVEMENT_DERIVED,
                    "physical_observation_id": None if observation is None else observation.observation_id,
                    "physical_observation_fingerprint": None if observation is None else observation.fingerprint,
                    "reason": "Reviewed movement authority.",
                    "actor": "reviewer-secret",
                    "source_command": "inventory-secret-command",
                    "decided_at": datetime(year + 1, 1, 2, tzinfo=UTC),
                    "evidence": (
                        InventoryClosingDecisionEvidence(
                            reference=_ref(f"decision-{actividad_id}"),
                            role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                            content_digest="d" * 64,
                        ),
                    ),
                },
                "physical_observation": observation,
                "prior_closing_link": {
                    "actividad_id": actividad_id,
                    "current_filing_year": year,
                    "prior_filing_year": year - 1,
                    "prior_authoritative_closing_value": Decimal("100.00"),
                    "current_opening_value": Decimal("100.00"),
                    "prior_authoritative_source_fingerprint": "e" * 64,
                    "prior_authoritative_closing_fingerprint": prior_fingerprint,
                    "evidence": continuity,
                },
            },
        },
    )


def _binding(operation: InventoryProjectionOperation, target: str) -> BindingDefinition:
    return BindingDefinition(
        id=f"inventory-{target}",
        provider={
            "kind": "inventory",
            **{
                "modelo": "100",
                "temporal": {"kind": "same_target_context"},
                "projection_grain": "taxpayer_year_activity",
                "fact": "row_field",
                "record": "inventory_activity",
                "grouping": "per_inventory_activity",
                "row_field": operation,
                "target_casilla_id": target,
            },
        },
        value={"data_type": "money", "channel": "row_set"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=("ley-35-2006:art-30",),
        source_refs=("aeat-renta-2025-manual",),
    )


def _revision(*, inventory: bool) -> ModeloRevision:
    base = published_snapshot("100", filing_year=2025, period="0A").revision
    bindings = (
        (
            _binding("complete_acquisition_cost", "0181"),
            _binding("closing_minus_opening_positive", "0177"),
            _binding("opening_minus_closing_positive", "0182"),
        )
        if inventory
        else ()
    )
    return base.model_copy(update={"bindings": bindings})


def _context(
    revision: ModeloRevision,
    *,
    year: int | None = None,
    activities: int = 1,
    facts: tuple[UserProfileFact, ...] = (),
) -> CalculationSourceContext:
    """The calculation context of a filer whose profile declares ``activities`` economic activities.

    The year is the newest authored Modelo 100 edition unless one is given, the year the books are kept for.
    """
    year = newest_authored_edition("100") if year is None else year
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="100",
        filing_year=year,
        period=Period.from_year_and_code(year, "0A"),
        revision=revision,
        profile=published_work_profile_declaring_activities(activities, facts=facts),
    )


def test_inventory_operation_adapter_tracks_the_canonical_row_field_vocabulary() -> None:
    annotation = InventoryProvider.model_fields["row_field"].annotation
    operations = set(get_args(getattr(annotation, "__value__", annotation)))

    assert operations == set(VALUE_ATTRIBUTE_BY_OPERATION)
    assert operations == {
        "complete_acquisition_cost",
        "closing_minus_opening_positive",
        "opening_minus_closing_positive",
    }


def test_no_inventory_binding_is_allocation_and_repository_read_free() -> None:
    repository = _InventoryLedgerRepositoryScenario()

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=False)))

    assert repository.loads == 0
    assert result.binding_values == {}
    assert result.row_binding_values == {}
    assert result.row_source_identities == {}
    assert result.unresolved_binding_ids == ()
    assert result.diagnostics == ()
    assert result.provenance == ()


def test_inventory_row_templates_expand_complete_activities_in_canonical_rows() -> None:
    alpha = inventory_ledger("alpha")
    zeta = inventory_ledger("zeta")
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(zeta, alpha)))

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), activities=2)
    )

    assert repository.loads == 1
    assert result.binding_values == {}
    assert result.row_binding_values == {
        ("inventory-0177", 1): Decimal("100.00"),
        ("inventory-0181", 1): Decimal("100.00"),
        ("inventory-0182", 1): Decimal("0.00"),
        ("inventory-0177", 2): Decimal("100.00"),
        ("inventory-0181", 2): Decimal("100.00"),
        ("inventory-0182", 2): Decimal("0.00"),
    }
    assert result.unresolved_binding_ids == ()
    assert len(result.provenance) == 2
    assert result.diagnostics == ()
    for binding_id in ("inventory-0177", "inventory-0181", "inventory-0182"):
        assert result.row_source_identities[(binding_id, 1)].source_row_identity == "alpha"
        assert result.row_source_identities[(binding_id, 2)].source_row_identity == "zeta"
        assert (
            result.row_source_identities[(binding_id, 1)].fingerprint
            == compute_inventory_anexo_d_projection(alpha).projection_fingerprint
        )
    assert len({item.fingerprint for key, item in result.row_source_identities.items() if key[1] == 1}) == 1
    assert len({item.fingerprint for key, item in result.row_source_identities.items() if key[1] == 2}) == 1
    public = f"{result!r} {result.model_dump()!r} {result.model_dump_json()}"
    assert "alpha" not in public
    assert "zeta" not in public


def test_resale_stock_acquisition_projects_to_anexo_d_not_the_amortization_casilla() -> None:
    """A stock purchase remains an inventory cost, distinct from a 0208 expense."""
    result = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(
            InventoryLedgerDocument(ledgers=(inventory_ledger("retail"),))
        )
    ).resolve(_context(_revision(inventory=True)))

    assert result.row_binding_values == {
        ("inventory-0177", 1): Decimal("100.00"),
        ("inventory-0181", 1): Decimal("100.00"),
        ("inventory-0182", 1): Decimal("0.00"),
    }
    assert all("0208" not in binding_id for binding_id, _row_index in result.row_binding_values)
    assert result.unresolved_binding_ids == ()
    assert result.diagnostics == ()


def test_one_book_among_two_declared_activities_projects_no_row() -> None:
    """The return holds one activity block, so one book can be its row only when it is the one activity.

    With a second activity declared and no book of its own, the lone book's row would read as the
    block's activity, whichever activity the book belongs to.
    """
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(inventory_ledger("alpha"),)))

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), activities=2)
    )

    assert result.row_binding_values == {}
    assert set(result.unresolved_binding_ids) == {"inventory-0177", "inventory-0181", "inventory-0182"}
    assert [diagnostic.reason for diagnostic in result.diagnostics] == ["source_domain_not_ready"]
    assert "activity_books_do_not_match_activities" in result.diagnostics[0].message


def test_one_book_for_an_activity_whose_identity_changes_within_the_year_projects_no_row() -> None:
    """A row that is one activity until June and another from July holds two activities in the year.

    One book can be only one of them, and the block's figures would describe both.
    """
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(inventory_ledger("alpha"),)))
    year = newest_authored_edition("100")
    renamed = (
        UserProfileFact(path="activities.description", value="Synthetic shop", valid_to=date(year, 6, 30)),
        UserProfileFact(path="activities.description", value="Synthetic workshop", valid_from=date(year, 7, 1)),
    )

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), facts=renamed)
    )

    assert result.row_binding_values == {}
    assert "declares 2 activities in estimacion directa" in result.diagnostics[0].message


def test_an_activity_whose_identity_changes_outside_the_year_still_projects_its_row() -> None:
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(inventory_ledger("alpha"),)))
    year = newest_authored_edition("100")
    renamed = (
        UserProfileFact(path="activities.description", value="Synthetic shop", valid_to=date(year - 1, 12, 31)),
        UserProfileFact(path="activities.description", value="Synthetic workshop", valid_from=date(year, 1, 1)),
    )

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), facts=renamed)
    )

    assert result.row_binding_values[("inventory-0181", 1)] == Decimal("100.00")


def test_an_activity_in_estimacion_objetiva_is_not_one_the_book_can_belong_to() -> None:
    """The Anexo D rows sit in the direct-estimation activity block, which a modulos activity is not in."""
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(inventory_ledger("alpha"),)))
    objetiva = (UserProfileFact(path=_ESTIMATION_REGIME, value=str(irpf_estimation_regime_objetiva_token())),)

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), facts=objetiva)
    )

    assert result.row_binding_values == {}
    assert "declares 0 activities in estimacion directa" in result.diagnostics[0].message


def test_a_filer_whose_activities_are_all_in_estimacion_objetiva_keeps_no_book_for_the_rows() -> None:
    """The existencias rows belong to the direct-estimation block, so a modulos filer has nothing to answer.

    LIRPF arts. 28 and 30 and RIRPF art. 30 place the stock variation in the rendimiento of an activity
    in estimacion directa; the modulos rendimiento (RIRPF arts. 32 to 37) takes none.
    """
    repository = _InventoryLedgerRepositoryScenario()
    objetiva = (UserProfileFact(path=_ESTIMATION_REGIME, value=str(irpf_estimation_regime_objetiva_token())),)

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), facts=objetiva)
    )

    inventory_ids = {"inventory-0177", "inventory-0181", "inventory-0182"}
    assert result.row_binding_values == {}
    assert result.diagnostics == ()
    assert set(result.inapplicable_binding_ids) == inventory_ids
    assert set(result.unresolved_binding_ids) == inventory_ids


@pytest.mark.parametrize("regime", ["directa_normal", "directa_simplificada", "part_year_directa"])
def test_a_filer_with_an_activity_in_estimacion_directa_and_no_book_is_asked_for_the_book(regime: str) -> None:
    """Any day of direct estimation puts the activity in the block, so the missing book keeps its remedy."""
    year = newest_authored_edition("100")
    objetiva = str(irpf_estimation_regime_objetiva_token())
    facts = {
        "directa_normal": (
            UserProfileFact(path=_ESTIMATION_REGIME, value=str(irpf_estimation_regime_directa_normal_token())),
        ),
        "directa_simplificada": (
            UserProfileFact(path=_ESTIMATION_REGIME, value=str(irpf_estimation_regime_directa_simplificada_token())),
        ),
        "part_year_directa": (
            UserProfileFact(path=_ESTIMATION_REGIME, value=objetiva, valid_to=date(year, 6, 30)),
            UserProfileFact(
                path=_ESTIMATION_REGIME,
                value=str(irpf_estimation_regime_directa_simplificada_token()),
                valid_from=date(year, 7, 1),
            ),
        ),
    }[regime]

    result = InventorySourceResolver(inventory_repository=_InventoryLedgerRepositoryScenario()).resolve(
        _context(_revision(inventory=True), facts=facts)
    )

    assert result.row_binding_values == {}
    assert result.inapplicable_binding_ids == ()
    assert set(result.unresolved_binding_ids) == {"inventory-0177", "inventory-0181", "inventory-0182"}
    (refusal,) = result.diagnostics
    assert refusal.reason == "source_domain_not_ready"
    assert "missing_activity_ledgers" in refusal.message
    assert "inventory book" in (refusal.remedy or "")


def test_a_filer_with_no_stated_regime_and_no_book_is_not_excused_from_the_book() -> None:
    """An undeclared regime leaves the block's activities unknown, so no book is not read as not needed."""
    undeclared = (UserProfileFact(path=_ESTIMATION_REGIME, value=""),)

    result = InventorySourceResolver(inventory_repository=_InventoryLedgerRepositoryScenario()).resolve(
        _context(_revision(inventory=True), facts=undeclared)
    )

    assert result.inapplicable_binding_ids == ()
    assert [diagnostic.reason for diagnostic in result.diagnostics] == ["source_domain_not_ready"]


def test_an_activity_counts_on_the_days_the_regime_is_direct_estimation() -> None:
    """Modulos until June and directa from July: the one activity is in the block, once, for its book."""
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(inventory_ledger("alpha"),)))
    year = newest_authored_edition("100")
    regimes = (
        UserProfileFact(
            path=_ESTIMATION_REGIME, value=str(irpf_estimation_regime_objetiva_token()), valid_to=date(year, 6, 30)
        ),
        UserProfileFact(
            path=_ESTIMATION_REGIME,
            value=str(irpf_estimation_regime_directa_simplificada_token()),
            valid_from=date(year, 7, 1),
        ),
    )

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), facts=regimes)
    )

    assert result.row_binding_values[("inventory-0181", 1)] == Decimal("100.00")
    assert result.diagnostics == ()


def test_an_activity_with_no_stated_estimation_regime_asks_for_the_regime_not_its_book() -> None:
    """Without a regime the block's activities are unknown, which is a missing regime, not a missing book."""
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(inventory_ledger("alpha"),)))
    undeclared = (UserProfileFact(path=_ESTIMATION_REGIME, value=""),)

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), facts=undeclared)
    )

    assert result.row_binding_values == {}
    assert set(result.unresolved_binding_ids) == {"inventory-0177", "inventory-0181", "inventory-0182"}
    assert [diagnostic.reason for diagnostic in result.diagnostics] == ["source_domain_not_ready"]
    assert "estimation_regime_undeclared" in result.diagnostics[0].message
    assert "activity_books_do_not_match_activities" not in result.diagnostics[0].message
    assert "estimation regime" in (result.diagnostics[0].remedy or "")


def test_a_regime_stated_for_only_part_of_an_activitys_year_asks_for_the_regime() -> None:
    year = newest_authored_edition("100")
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(inventory_ledger("alpha"),)))
    partial = (
        UserProfileFact(
            path=_ESTIMATION_REGIME,
            value=str(irpf_estimation_regime_directa_normal_token()),
            valid_from=date(year, 7, 1),
        ),
    )

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), facts=partial)
    )

    assert result.row_binding_values == {}
    assert "estimation_regime_undeclared" in result.diagnostics[0].message


def test_a_book_without_a_profile_to_count_activities_against_projects_no_row() -> None:
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(inventory_ledger("alpha"),)))
    context = _context(_revision(inventory=True)).model_copy(update={"profile": None})

    result = InventorySourceResolver(inventory_repository=repository).resolve(context)

    assert result.row_binding_values == {}
    assert "activity_books_do_not_match_activities" in result.diagnostics[0].message


def test_resale_stock_document_refuses_duplicate_activity_year_collision() -> None:
    """One stock ledger is authoritative for an activity/year coordinate."""
    stock = inventory_ledger("retail")

    with pytest.raises(ValidationError, match="duplicate actividad/year"):
        InventoryLedgerDocument(ledgers=(stock, stock))


def test_inventory_activity_order_is_insertion_invariant_and_semantic_change_changes_fingerprint() -> None:
    alpha = inventory_ledger("alpha")
    zeta = inventory_ledger("zeta")
    forward = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(alpha, zeta)))
    ).resolve(_context(_revision(inventory=True), activities=2))
    reverse = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(zeta, alpha)))
    ).resolve(_context(_revision(inventory=True), activities=2))
    changed_movement = alpha.period_movements[0].model_copy(update={"movement_date": date(2025, 3, 1)})
    changed = InventoryLedger.model_validate(alpha.model_copy(update={"period_movements": (changed_movement,)}))
    mutated = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(changed, zeta)))
    ).resolve(_context(_revision(inventory=True), activities=2))

    assert forward.row_binding_values == reverse.row_binding_values == mutated.row_binding_values
    assert forward.row_source_identities == reverse.row_source_identities
    assert (
        forward.row_source_identities[("inventory-0181", 1)].fingerprint
        != mutated.row_source_identities[("inventory-0181", 1)].fingerprint
    )


def _retired(ledger: InventoryLedger) -> InventoryLedger:
    entry = InventoryLedgerHistoryEntry(
        correction_id="out",
        kind=InventoryHistoryKind.RETIRED,
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
        actor="test",
        request_fingerprint="a" * 64,
        retirement_reason=InventoryRetirementReason.CREATED_IN_ERROR,
    )
    return ledger.model_copy(update={"history": (entry,)})


def test_a_retired_inventory_holding_stock_facts_fails_the_cohort_closed() -> None:
    alpha = inventory_ledger("alpha")
    result = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(
            InventoryLedgerDocument(ledgers=(alpha, _retired(inventory_ledger("zeta"))))
        )
    ).resolve(_context(_revision(inventory=True)))

    assert result.row_binding_values == {}
    assert result.row_source_identities == {}
    assert [item.reason for item in result.diagnostics] == ["source_domain_not_ready"]


def test_a_retired_inventory_without_stock_facts_leaves_the_cohort() -> None:
    alpha = inventory_ledger("alpha")
    empty = _retired(
        InventoryLedger(
            actividad_id="zeta",
            year=2025,
            valuation_method=ValuationMethod.FIFO,
            opening_stock=Decimal("0.00"),
            closing_authority_record=None,
        )
    )

    with_empty = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(alpha, empty)))
    ).resolve(_context(_revision(inventory=True)))
    alone = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(alpha,)))
    ).resolve(_context(_revision(inventory=True)))

    assert with_empty.row_source_identities == alone.row_source_identities
    assert with_empty.diagnostics == ()


def test_inventory_conflict_is_safe_per_activity_advisory() -> None:
    ledger = inventory_ledger("secret-activity", physical_closing=Decimal("250.00"))
    result = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(ledger,)))
    ).resolve(_context(_revision(inventory=True)))

    assert result.row_binding_values[("inventory-0177", 1)] == Decimal("100.00")
    assert result.diagnostics[0].reason == "source_issue"
    rendered = f"{result.diagnostics!r} {result.diagnostics[0].message}"
    assert "secret-activity" not in rendered
    assert "250.00" not in rendered


@pytest.mark.parametrize("kind", ["missing", "unreadable", "incomplete"])
def test_inventory_failure_is_atomic_value_free_and_loads_once(kind: str) -> None:
    if kind == "missing":
        repository = _InventoryLedgerRepositoryScenario()
    elif kind == "unreadable":
        repository = _InventoryLedgerRepositoryScenario(error=True)
    else:
        ledger = inventory_ledger("secret-activity").model_copy(update={"closing_authority_record": None})
        repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument.model_construct(ledgers=(ledger,)))
    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=True)))

    assert repository.loads == 1
    assert result.row_binding_values == {}
    assert result.row_source_identities == {}
    assert set(result.unresolved_binding_ids) == {"inventory-0177", "inventory-0181", "inventory-0182"}
    rendered = f"{result!r} {result.model_dump()!r}"
    for canary in ("secret-activity", "100.00", "reviewer-secret", "inventory-secret-command", "a" * 64):
        assert canary not in rendered


def test_a_book_with_no_recorded_closing_value_is_not_ready_rather_than_tampered() -> None:
    year = newest_authored_edition("100")
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(fresh_inventory_ledger(year),)))

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=True)))

    assert result.row_binding_values == {}
    assert set(result.unresolved_binding_ids) == {"inventory-0177", "inventory-0181", "inventory-0182"}
    (diagnostic,) = result.diagnostics
    assert diagnostic.reason == "source_domain_not_ready"
    assert "closing_value_not_recorded" in diagnostic.message
    assert "tampered" not in diagnostic.message
    assert diagnostic.remedy is not None


def test_a_book_with_no_stock_closed_on_its_movements_projects_proven_zero_variation_and_purchases() -> None:
    closed = closed_no_stock_ledger(newest_authored_edition("100"))
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(closed,)))

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=True)))

    # oracle: Manual practico de Renta 2025, parte 1, pp. 422 and 425: the variation is the difference between
    # the existencias iniciales and finales; with neither stock nor purchases every operation is zero.
    assert result.unresolved_binding_ids == ()
    assert result.diagnostics == ()
    assert result.row_binding_values == {
        ("inventory-0177", 1): Decimal("0.00"),
        ("inventory-0181", 1): Decimal("0.00"),
        ("inventory-0182", 1): Decimal("0.00"),
    }


def _published_inventory_years(operation: PinnedAuthorityOperation) -> tuple[tuple[int, ModeloRevision], ...]:
    """Every supported Modelo 100 exercise, projected one included, whose published revision holds the rows."""
    years = []
    for year in supported_exercises_with_projection("100"):
        revision = published_snapshot("100", filing_year=year, period="0A").revision
        if any(binding.source is BindingSourceKind.INVENTORY for binding in revision.bindings):
            years.append((year, revision))
    return tuple(years)


def test_every_year_with_the_rows_keeps_stated_none_zero_unanswered_refused_and_held_stock_computed(
    operation: PinnedAuthorityOperation,
) -> None:
    """Through the published revision of each year: a book closed at zero, no book, and a book with stock.

    The variation and the purchases rest on the existencias iniciales and finales the taxpayer states, so a
    book with no stock proves the zero rows, while a missing book leaves them unanswered with a remedy that
    sends the operator to the book rather than reading them as zero.
    """
    years = _published_inventory_years(operation)
    assert years, "the registry authors the Anexo D inventory rows for at least one supported year"
    for year, revision in years:
        inventory_ids = {binding.id for binding in revision.bindings if binding.source is BindingSourceKind.INVENTORY}
        context = _context(revision, year=year)

        stated_none = InventorySourceResolver(
            inventory_repository=_InventoryLedgerRepositoryScenario(
                InventoryLedgerDocument(ledgers=(closed_no_stock_ledger(year),))
            )
        ).resolve(context)
        unanswered = InventorySourceResolver(inventory_repository=_InventoryLedgerRepositoryScenario()).resolve(context)
        held = InventorySourceResolver(
            inventory_repository=_InventoryLedgerRepositoryScenario(
                InventoryLedgerDocument(ledgers=(inventory_ledger("alpha", year=year),))
            )
        ).resolve(context)

        assert stated_none.unresolved_binding_ids == (), year
        assert stated_none.diagnostics == (), year
        assert set(stated_none.row_binding_values.values()) == {Decimal("0.00")}, year
        assert {binding_id for binding_id, _row in stated_none.row_binding_values} == inventory_ids, year

        assert unanswered.row_binding_values == {}, year
        assert set(unanswered.unresolved_binding_ids) == inventory_ids, year
        (refusal,) = unanswered.diagnostics
        assert refusal.reason == "source_domain_not_ready", year
        assert "missing_activity_ledgers" in refusal.message, year
        assert "inventory book" in (refusal.remedy or ""), year

        # Opening 100.00 plus one purchase at 100.00 closing on movements at 200.00: the increase and the
        # purchases are each 100.00 and nothing decreased.
        assert held.unresolved_binding_ids == (), year
        assert held.diagnostics == (), year
        assert sorted(held.row_binding_values.values()) == [
            Decimal("0.00"),
            Decimal("100.00"),
            Decimal("100.00"),
        ], year


@pytest.mark.parametrize("actividad_id", [" alpha", "alpha ", "alpha\ncontrol"])
def test_inventory_ledger_refuses_noncanonical_activity_identity(actividad_id: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        inventory_ledger("alpha").model_copy(update={"actividad_id": actividad_id}).model_dump_json()
        InventoryLedger.model_validate(
            inventory_ledger("alpha").model_copy(update={"actividad_id": actividad_id}).model_dump(),
        )
    assert actividad_id not in str(exc_info.value)


def test_a_projected_year_expands_the_rows_the_registry_authors_for_the_edition_it_is_carried_from() -> None:
    year = projected_exercise("100")
    revision = published_snapshot("100", filing_year=year, period="0A").revision
    repository = _InventoryLedgerRepositoryScenario(
        InventoryLedgerDocument(ledgers=(inventory_ledger("alpha", year=year),))
    )

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(revision, year=year))

    assert repository.loads == 1
    assert result.unresolved_binding_ids == ()
    assert result.diagnostics == ()
    assert sorted(result.row_binding_values.values()) == [Decimal("0.00"), Decimal("100.00"), Decimal("100.00")]
    assert {binding_id for binding_id, _row in result.row_binding_values} == {
        binding.id for binding in revision.bindings if binding.source is BindingSourceKind.INVENTORY
    }


@pytest.mark.parametrize("shape", ["missing", "duplicate"])
def test_inventory_template_cohort_refuses_atomically_before_storage(shape: str) -> None:
    revision = _revision(inventory=True)
    bindings = revision.bindings[:-1] if shape == "missing" else (*revision.bindings, revision.bindings[0])
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(inventory_ledger("alpha"),)))

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(revision.model_copy(update={"bindings": bindings})),
    )

    assert repository.loads == 0
    assert result.row_binding_values == {}
    assert result.row_source_identities == {}
    assert result.diagnostics[0].reason == "unresolved_derived_binding"


def _terminal_origin_binding(operation: InventoryProjectionOperation, target: str) -> BindingDefinition:
    """Build one inventory row template against the live provider model."""
    return BindingDefinition(
        id=f"inventory-{target}",
        provider={
            "kind": "inventory",
            "modelo": "100",
            "projection_grain": "taxpayer_year_activity",
            "fact": "row_field",
            "record": "inventory_activity",
            "grouping": "per_inventory_activity",
            "row_field": operation,
            "target_casilla_id": target,
        },
        value={"data_type": "money", "channel": "row_set"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=("ley-35-2006:art-30",),
        source_refs=("aeat-renta-2025-manual",),
    )


def _terminal_origin_revision() -> ModeloRevision:
    """Build the inventory row-template cohort on a self-contained revision."""
    return ModeloRevision(
        id="renta-2025-inventory-terminal-origin",
        localization_key="registry.modelo.100.2025",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2025,), periods=("0A",)),
        legal_refs=("ley-35-2006:art-30",),
        source_refs=("aeat-renta-2025-manual",),
        bindings=(
            _terminal_origin_binding("complete_acquisition_cost", "0181"),
            _terminal_origin_binding("closing_minus_opening_positive", "0177"),
            _terminal_origin_binding("opening_minus_closing_positive", "0182"),
        ),
    )


def test_inventory_rows_carry_a_primary_detail_record_node_the_terminal_audit_admits() -> None:
    revision = _terminal_origin_revision()
    repository = _InventoryLedgerRepositoryScenario(
        InventoryLedgerDocument(ledgers=(inventory_ledger("zeta"), inventory_ledger("alpha"))),
    )

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(revision, activities=2))

    assert len(result.row_binding_values) == 6
    # One activity record stands behind the three operation values it produced.
    assert len(result.provenance) == 2
    assert all(node.lineage_role is CalculationSourceLineageRole.PRIMARY for node in result.provenance)
    assert all(node.terminal_origin is TerminalOriginClass.DETAIL_RECORD for node in result.provenance)
    assert all(node.resolved_binding_source is BindingSourceKind.INVENTORY for node in result.provenance)
    assert all(node.parent_source_ref is None for node in result.provenance)
    assert all(node.fingerprint is not None for node in result.provenance)
    assert all(node.source_ref == f"inventory_activity:{node.fingerprint}" for node in result.provenance)
    assert len({node.source_ref for node in result.provenance}) == 2
    assert collect_terminal_origin_diagnostics(revision, result) == ()
    public = f"{result!r} {result.model_dump()!r} {result.model_dump_json()}"
    assert "alpha" not in public
    assert "zeta" not in public


def test_inventory_resolution_without_activity_rows_claims_no_terminal_origin() -> None:
    revision = _terminal_origin_revision()
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=()))

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(revision))

    assert result.row_binding_values == {}
    assert result.provenance == ()
    assert collect_terminal_origin_diagnostics(revision, result) == ()
