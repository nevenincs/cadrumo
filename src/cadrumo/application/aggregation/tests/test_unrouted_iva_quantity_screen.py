"""The IVA quantity screen catches a dropped quantity the row screen cannot see.

Every IVA row carries three INDEPENDENT quantities -- the taxable base, the
cuota charged on it, and the recargo de equivalencia surcharged alongside. The
row-level screen (``unsupported_ledger_iva_observations``) reports a row as
consumed the moment ANY binding selects it, so a row consumed for its cuota
stays "routed" while its base imponible reaches no binding at all. These tests
pin that gap closed on the axis the row screen is blind to, and prove the
blindness rather than asserting it.

Every row here starts from a real :class:`Transaction` driven through the
production projection. Hand-building an ``IvaLedgerObservation`` would let the
fixture assert its own classification: the observation carries category, rate
kind and flow direction as fields, so such a test passes with the projection
deleted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import IvaDeductionEvidenceAuthority, IvaDeductionFactKind, Period
from ....core.resources import resources
from ....domain.bienes_inversion import BienesInversionIvaRegister
from ....domain.calculations.registry import (
    IvaLedgerObservation,
    ModeloRevision,
    unrouted_ledger_iva_quantities,
    unsupported_ledger_iva_observations,
)
from ....domain.iva import (
    InvoiceKind,
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaDeductionClassificationProvenance,
    IvaLedgerObservationRole,
    IvaRateKind,
    derive_flow_for_classification,
)
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._modelo_bindings import LedgerIvaAggregationSourceResolver as _LedgerIvaAggregationSourceResolver
from .._source_mesh import CalculationSourceContext
from ._iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2025, 2, 10, 12, 0, tzinfo=UTC)
_Q1_2025 = Period.from_year_and_code(2025, "1T")
_BUCKET_ID = "28282828-2828-4828-8828-282828282828"


class LedgerIvaAggregationSourceResolver(_LedgerIvaAggregationSourceResolver):
    """Bind injected real repositories to an explicit empty Bienes authority."""

    def __init__(self, *, transaction_repository: TransactionCatalogueRepository | None = None) -> None:
        super().__init__(
            transaction_repository=transaction_repository,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=(transaction_repository.bucket_id if transaction_repository is not None else _BUCKET_ID),
            ),
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id=(
                transaction_repository.bucket_id if transaction_repository is not None else _BUCKET_ID
            ),
        )


@cache
def _revision(modelo_id: str) -> ModeloRevision:
    """The committed revision governing each modelo's IVA ledger bindings.

    Resolved from ``(modelo, filing_year, period)`` through the authority for
    BOTH modelos rather than indexed by a literal id. Modelo 390 was reached by
    ``revisions["2010-y-siguientes"]``, a revision the span split retired into
    four exact-year ones, so this raised ``KeyError`` instead of screening
    anything. Modelo 303 is quarterly and 390 annual, which is the only
    difference between them here.
    """
    period = "1T" if modelo_id == "303" else "0A"
    return (
        resources()
        .modelos.authority.snapshot(
            modelo_id,
            filing_year=_Q1_2025.filing_year,
            period=period,
        )
        .revision
    )


def _row(category: IvaCategory) -> IvaLedgerObservation:
    """One purchase row of ``category``, with the flow direction PRODUCTION derives.

    ``derive_flow_for_classification`` routes every reverse-charge category to
    ``INVERSION_SUJETO_PASIVO`` regardless of invoice direction. Hand-setting
    ``SOPORTADO`` screens a shape the projection never emits and manufactures
    findings from the fixture's own error — which is exactly what an earlier
    probe of this residue did.
    """
    return IvaLedgerObservation(
        ledger_id=f"residue-{category.value}",
        transaction_date=date(2024, 6, 1),
        category=category,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=derive_flow_for_classification(category=category, invoice_direction=InvoiceKind.RECEIVED),
        cash_accounting_treatment=IvaCashAccountingTreatment.NONE,
        base_amount=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        recargo_amount=Decimal("0"),
        deduction_fact_kind=(
            IvaDeductionFactKind.IMPORT_CURRENT
            if category is IvaCategory.IMPORT_THIRD_COUNTRY
            else IvaDeductionFactKind.INTRA_EU_CURRENT
            if category
            in {
                IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
                IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
            }
            else IvaDeductionFactKind.DOMESTIC_CURRENT
        ),
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=(
                IvaDeductionEvidenceAuthority.CUSTOMS_DECLARATION
                if category is IvaCategory.IMPORT_THIRD_COUNTRY
                else IvaDeductionEvidenceAuthority.INTRA_EU_SELF_ASSESSMENT
                if category
                in {
                    IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
                    IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
                }
                else IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE
            ),
            source_locator=f"fixture:{category.value}",
            evidence_digest="d" * 64,
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _sale(
    provider_id: str,
    *,
    base: str,
    iva: str,
    recargo: str | None = None,
) -> Transaction:
    """A domestic standard-rate sale carrying base, cuota and optional recargo."""
    recargo_amount = None if recargo is None else Decimal(recargo)
    gross = Decimal(base) + Decimal(iva) + (recargo_amount or Decimal("0"))
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=gross,
        currency="EUR",
        counterparty="Minorista Recargo SL",
        description=f"venta {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": provider_id},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal(base),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal(iva),
            "recargo_amount": recargo_amount,
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _observations(*transactions: Transaction) -> tuple[IvaLedgerObservation, ...]:
    """Project real transactions through the production IVA aggregation."""
    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions(transactions),
        period=_Q1_2025,
    )
    assert result.observations, "the projection emitted no declarable observation to screen"
    return tuple(result.observations)


def _revision_without_fact(revision: ModeloRevision, fact: str) -> ModeloRevision:
    """Return ``revision`` with every ``ledger_iva_aggregation`` binding drawing ``fact`` removed.

    Models one of the two shapes the screen catches: a revision declaring no
    binding for this fact at all. Pinning on a stripped revision rather than on
    a modelo that happens to lack the fact today was the right call and has
    already paid — Modelo 390 was the standing instance for ``base_amount_sum``
    and the annual-form campaign closed it. A test keyed on that state would now
    be asserting something false about a correctly-modelled form.

    The other shape, a fact declared by bindings that reach only SOME rows, is
    covered by the partitioned tests below against the committed revision.
    """
    kept = [
        binding
        for binding in revision.bindings
        if not (binding.source.value == "ledger_iva_aggregation" and getattr(binding.selector, "fact", None) == fact)
    ]
    return revision.model_copy(update={"bindings": tuple(kept)})


def test_the_committed_revision_draws_every_quantity_its_rows_carry() -> None:
    """The real Modelo 303 revision routes base, cuota and recargo -- no advisory."""
    rows = _observations(_sale("s-1", base="1000.00", iva="210.00", recargo="52.00"))

    assert unrouted_ledger_iva_quantities(_revision("303"), rows) == ()


def test_a_revision_drawing_no_base_surfaces_the_whole_base() -> None:
    """A revision declaring no base binding at all reports the whole base.

    The simpler of the two shapes: the fact reaches no binding on the revision,
    so every row carrying it is uncovered. Modelo 390 was the standing real
    instance until the annual-form campaign declared its base boxes.
    """
    revision = _revision_without_fact(_revision("303"), "base_amount_sum")
    rows = _observations(
        _sale("s-1", base="1000.00", iva="210.00"),
        _sale("s-2", base="2000.00", iva="420.00"),
    )

    unrouted = unrouted_ledger_iva_quantities(revision, rows)

    assert len(unrouted) == 1
    assert unrouted[0].fact == "base_amount_sum"
    assert unrouted[0].total == Decimal("3000.00")
    assert len(unrouted[0].observations) == 2


def test_the_row_screen_stays_silent_on_the_same_defect() -> None:
    """The blindness this screen exists for, proved rather than asserted.

    Same revision and rows as the test above. The row screen reports nothing,
    because both rows are still consumed by the cuota bindings -- so without the
    quantity screen the undrawn base imponible has a clean screen on both sides.
    """
    revision = _revision_without_fact(_revision("303"), "base_amount_sum")
    rows = _observations(_sale("s-1", base="1000.00", iva="210.00"))

    assert unsupported_ledger_iva_observations(revision, rows) == ()
    assert unrouted_ledger_iva_quantities(revision, rows) != ()


def test_a_quantity_the_rows_do_not_carry_raises_nothing() -> None:
    """A legitimate zero is not a modelling gap.

    Anti-false-fire control: the recargo bindings are absent AND the rows carry
    no recargo. Without this the screen would fire on every taxpayer who simply
    sells to no recargo-regime retailer.
    """
    revision = _revision_without_fact(_revision("303"), "recargo_amount_sum")
    rows = _observations(_sale("s-1", base="1000.00", iva="210.00"))

    assert unrouted_ledger_iva_quantities(revision, rows) == ()


@pytest.mark.parametrize(
    ("fact", "expected_total"),
    [
        ("base_amount_sum", Decimal("1000.00")),
        ("iva_amount_sum", Decimal("210.00")),
        ("recargo_amount_sum", Decimal("52.00")),
    ],
)
def test_no_iva_fact_is_excluded_as_an_alternative_measure(fact: str, expected_total: Decimal) -> None:
    """The IVA exclusion set is empty, and that is a measured property.

    On the renta side three income measures ARE alternatives, so omitting two of
    them is a modelling choice and screening them would fire on every revision.
    Base, cuota and recargo are not measures of one quantity: no one of them
    stands in for another, so dropping ANY of the three loses a real amount and
    every one of them must report.
    """
    revision = _revision_without_fact(_revision("303"), fact)
    rows = _observations(_sale("s-1", base="1000.00", iva="210.00", recargo="52.00"))

    unrouted = unrouted_ledger_iva_quantities(revision, rows)

    assert [entry.fact for entry in unrouted] == [fact]
    assert unrouted[0].total == expected_total


def test_the_screen_reads_the_revision_it_is_given() -> None:
    """Guards against a screen that hardcodes which facts M303 draws.

    An implementation asserting "the IVA family draws all three" would pass
    every test above. This one fails it: the same rows must report differently
    against a revision that draws the fact and one that does not.
    """
    committed = _revision("303")
    stripped = _revision_without_fact(committed, "base_amount_sum")
    rows = _observations(_sale("s-1", base="1000.00", iva="210.00"))

    assert unrouted_ledger_iva_quantities(committed, rows) == ()
    assert unrouted_ledger_iva_quantities(stripped, rows) != ()


def test_the_advisory_reaches_the_resolver_envelope(tmp_path: Path) -> None:
    """The screen is wired, not merely written.

    Everything above calls the screen directly, so all of it would still pass
    with the resolver never invoking it -- the failure mode where a correct
    screen ships switched off. This drives the real
    :class:`LedgerIvaAggregationSourceResolver` end to end from a stored
    transaction and asserts the advisory arrives in its diagnostics envelope
    carrying the amount and its attribution.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(
            TransactionCatalogue.from_transactions((_sale("s-1", base="1000.00", iva="210.00"),)),
        )
        resolution = LedgerIvaAggregationSourceResolver(transaction_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=_Q1_2025,
                revision=_revision_without_fact(_revision("303"), "base_amount_sum"),
            ),
        )

    advisories = [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]
    assert len(advisories) == 1, "a revision drawing no base must surface exactly one advisory"
    assert "base_amount_sum" in advisories[0].message
    assert "1000.00" in advisories[0].message, "the advisory must name the amount that goes undeclared"
    assert advisories[0].resolver_id == "ledger_iva_aggregation"


def test_the_committed_revision_raises_no_advisory_in_the_envelope(tmp_path: Path) -> None:
    """Anti-false-fire control on the wired path.

    The test above would pass just as well if the resolver emitted the advisory
    unconditionally. Against the real Modelo 303 revision, which draws all three
    quantities, the envelope must carry none.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(
            TransactionCatalogue.from_transactions((_sale("s-1", base="1000.00", iva="210.00"),)),
        )
        resolution = LedgerIvaAggregationSourceResolver(transaction_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=_Q1_2025,
                revision=_revision("303"),
            ),
        )

    assert not [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]


def _reverse_charge_purchase() -> Transaction:
    """An intra-community acquisition: cuota self-assessed, base imponible carried.

    The flow direction is NOT set here. ``derive_flow_for_classification``
    routes every reverse-charge category to ``INVERSION_SUJETO_PASIVO``
    regardless of invoice direction, and the projection applies it — a fixture
    that hand-set ``SOPORTADO`` would screen a shape production never emits and
    manufacture findings from its own error.
    """
    raw = RawTransaction(
        provider_transaction_id="aic-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("1000.00"),
        currency="EUR",
        counterparty="Proveedor UE",
        description="adquisicion intracomunitaria",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=2,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "aic-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _third_country_import() -> Transaction:
    """A third-country import: cuota self-assessed at customs, base imponible carried.

    Mirrors :func:`_reverse_charge_purchase`'s shape exactly, differing only in
    the classified category. Kept as the residue fixture for the tests below
    because ``INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`` and
    ``INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE`` stopped being residue
    once M390's AIC box layer (d3c2438371) and M303's box 10 base binding
    (717af32acc) landed -- both now declare a ``base_amount_sum`` binding for
    those two categories, so a fixture of either would no longer prove the
    partitioned-gap shape these tests exist to pin.
    """
    raw = RawTransaction(
        provider_transaction_id="import-1",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=Decimal("1000.00"),
        currency="EUR",
        counterparty="Proveedor extracomunitario",
        description="importacion de bienes",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=2,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": "import-1"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory.IMPORT_THIRD_COUNTRY,
            "deduction_fact_kind": IvaDeductionFactKind.IMPORT_CURRENT,
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.CUSTOMS_DECLARATION,
                source_locator="customs:import-1",
                evidence_digest="e" * 64,
            ),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def test_a_partitioned_fact_is_screened_per_row_not_per_revision() -> None:
    """The live Modelo 303 gap a flat coverage set cannot see.

    Modelo 303 declares ``base_amount_sum`` bindings, so "is this fact drawn"
    answers yes for every row. But those bindings select the domestic tiers,
    intra-community supplies/exports and (since 717af32acc) the intra-community
    reverse-charge categories, while the cuota bindings ALSO reach the import
    category. A third-country import's base imponible is therefore reached by
    no base binding at all, on the COMMITTED revision, with no fact stripped by
    this test.

    A flat drawn-set is silent here, which is the same defect the quantity
    screen exists to catch, one level in: coverage must be asked per row and per
    fact, never per fact alone.
    """
    rows = _observations(_third_country_import())

    unrouted = unrouted_ledger_iva_quantities(_revision("303"), rows)

    assert [entry.fact for entry in unrouted] == ["base_amount_sum"]
    assert unrouted[0].total == Decimal("1000.00")
    # The cuota IS reached, by a binding selecting this row's category. Asserted
    # so the test cannot pass by reporting everything.
    assert "iva_amount_sum" not in {entry.fact for entry in unrouted}


def test_the_row_screen_is_silent_on_the_partitioned_gap() -> None:
    """Proved, not asserted: the row screen cannot report the case above.

    The import row IS consumed -- by the cuota bindings that select its
    category -- so the row-keyed screen sees nothing wrong while its base
    imponible reaches no binding.
    """
    rows = _observations(_third_country_import())

    assert unsupported_ledger_iva_observations(_revision("303"), rows) == ()
    assert unrouted_ledger_iva_quantities(_revision("303"), rows) != ()


def test_an_ordinary_domestic_row_stays_silent_on_the_committed_revision() -> None:
    """Anti-false-fire control for the per-row coverage change.

    Per-row screening is strictly more sensitive than the flat set it replaced,
    so the risk it introduces is firing on the ordinary case and training
    operators to ignore the advisory. A domestic sale and a domestic purchase
    are both fully covered on the committed revision and must stay silent.
    """
    sale = _observations(_sale("dom-sale", base="1000.00", iva="210.00"))
    assert unrouted_ledger_iva_quantities(_revision("303"), sale) == ()


@pytest.mark.parametrize("modelo_id", ["303", "390"])
def test_the_import_base_residue_is_reported_on_both_modelos(modelo_id: str) -> None:
    """The residue that survives a modelo declaring the fact, pinned on both.

    Modelo 390 declared no ``base_amount_sum`` binding at all until the
    annual-form campaign added its base boxes. Closing that gap is exactly what
    would have BLINDED a screen keyed on the fact alone: ``base_amount_sum``
    became "drawn" for M390, and the import row whose base is still reached by
    nothing would have gone quiet.

    ``INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`` and
    ``INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE`` were part of this
    residue too until M390's AIC box layer (d3c2438371) and M303's box 10 base
    binding (717af32acc) each declared a ``base_amount_sum`` binding for them;
    asserted silent below rather than dropped, so a regression reopening either
    gap reddens here rather than by omission.

    Both modelos are asserted together because the residue is the same
    category on each, and pinning only the modelo that happened to be broken
    first is how this test would rot the next time a campaign lands.
    """
    revision = _revision(modelo_id)

    reported = {
        category: [entry.fact for entry in unrouted_ledger_iva_quantities(revision, [_row(category)])]
        for category in (IvaCategory.IMPORT_THIRD_COUNTRY,)
    }

    assert all(facts == ["base_amount_sum"] for facts in reported.values()), reported
    # The domestic tiers and the (now closed) reverse-charge pair ARE covered
    # on both modelos, so the screen must be silent there. Without this the
    # test would pass on a screen that reports every row of every category.
    assert unrouted_ledger_iva_quantities(revision, [_row(IvaCategory.DOMESTIC_GENERAL)]) == ()
    assert (
        unrouted_ledger_iva_quantities(revision, [_row(IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE)]) == ()
    )
    assert (
        unrouted_ledger_iva_quantities(revision, [_row(IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE)])
        == ()
    )


def test_the_advisory_names_the_categories_carrying_the_residue(tmp_path: Path) -> None:
    """The residue must be attributable, not merely reported.

    A fact can be drawn for some categories and undrawn for others: Modelo 303
    draws ``base_amount_sum`` for the domestic tiers and (since 717af32acc) the
    intra-community reverse-charge pair, while import carries it undrawn. An
    advisory naming only the fact tells an operator base is missing without
    saying where, so a partially closed gap reads as wholly open -- and, once
    the domestic half lands, the same message would read as wholly closed to
    anyone diffing it.

    Naming the categories is what lets a later reader tell a genuine remainder from
    a regression. Asserted against the COMMITTED Modelo 303 revision with no fact
    stripped, so it is the live residue rather than a manufactured one.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((_third_country_import(),)))
        resolution = LedgerIvaAggregationSourceResolver(transaction_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=_BUCKET_ID,
                modelo="303",
                filing_year=2025,
                period=_Q1_2025,
                revision=_revision("303"),
            ),
        )

    advisories = [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]
    assert len(advisories) == 1, "the live import base residue must surface exactly one advisory"
    message = advisories[0].message
    assert "base_amount_sum" in message
    assert "import_third_country" in message, (
        "the advisory must NAME the category carrying the undrawn quantity; without it a reader "
        "cannot tell which categories remain open from which are genuinely closed"
    )
    # Anti-vacuity: the covered domestic tiers and the closed reverse-charge
    # pair must NOT appear. An advisory naming every category would satisfy the
    # assertion above while telling a reader nothing, and would falsely
    # implicate categories whose base IS drawn.
    for covered in (
        "domestic_general",
        "domestic_reduced",
        "domestic_super_reduced",
        "intra_community_acquisition_reverse_charge",
        "intra_community_service_acquisition_reverse_charge",
    ):
        assert covered not in message, f"{covered} draws base on this revision and must not be blamed"
