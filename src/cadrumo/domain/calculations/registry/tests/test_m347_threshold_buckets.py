"""Modelo 347's declaration floor is judged per counterparty and per threshold bucket.

RD 1065/2007 art. 33.1 relates every person whose operations exceed 3.005,06
EUR in the año natural and computes "de forma separada las entregas y las
adquisiciones de bienes y servicios"; arts. 32.c and 33.4 give clave C a
separate 300,51 EUR floor; art. 33.3 relates clave E "cualquiera que sea su
importe" from 2014, as the 2025 record design does. The dated ``m347-clave-threshold-buckets``
fact carries that grouping. Every scenario here runs through the real row
resolver (the declarado row family) and the real scalar resolver (the type 1
declarante summary), both of which delegate to the one declarable-set
function, against the published authority.

The refusal tests feed deliberately malformed bucket mappings through a fact
source that answers only that one query itself and delegates every other query,
including the floor facts, to the published authority.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..errors import RegistryValidationError
from ..facts.payloads import MappingFactEntry, MappingFactPayload
from ..facts.resolution import GovernedFactQuery, ResolvedGovernedFact, ResolvedMappingFact
from ..invoice_bindings import InvoiceObservation, resolve_invoice_binding_row_values, resolve_invoice_binding_values
from ..m347_threshold import (
    M347ThresholdBuckets,
    m347_declarable_party_buckets,
    m347_threshold_decimal,
    resolve_m347_counterparty_annual_threshold,
    resolve_m347_threshold_buckets,
)
from ..schema import SupportedFilingYearsCatalogue
from .published_authority import published_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FILING_2025 = date(2025, 12, 31)
_FILING_2024 = date(2024, 12, 31)
_REVISION_2025 = "2025-y-siguientes"
_REVISION_2024 = "2011-2024"
_BUCKET_FACT_ID = "m347-clave-threshold-buckets"
_PARTY = "B11111112"
_COUNT_BINDING = "modelo-347-declarante-numero-personas-entidades"
_TOTAL_BINDING = "modelo-347-declarante-importe-total-anual-operaciones"
_CLAVE_BINDING = "modelo-347-contraparte-row-clave"
_NIF_BINDING = "modelo-347-contraparte-row-nif"


@pytest.fixture(autouse=True)
def _generation_pinned_authority() -> Iterator[None]:
    """Run every test inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation():
        yield


def _observation(
    clave: str,
    total: str,
    *,
    party_tax_id: str = _PARTY,
    invoice_id: str | None = None,
    transaction_date: date = date(2025, 3, 10),
) -> InvoiceObservation:
    source_kind = (
        BindingSourceKind.COLLECTIBLE_INVOICE if clave in {"B", "F", "C"} else BindingSourceKind.PAYABLE_INVOICE
    )
    return InvoiceObservation(
        invoice_id=invoice_id or f"inv-{party_tax_id}-{clave}-{total}",
        source_kind=source_kind,
        party_tax_id=party_tax_id,
        country_code="ES",
        transaction_date=transaction_date,
        base_amount=Decimal(total),
        invoice_total_amount=Decimal(total),
        operation_clave=clave,
        party_legal_name="Contraparte Umbral SL",
    )


@dataclass(frozen=True, slots=True)
class _Declared:
    """What one filing declares: its declarado rows and its type 1 totals."""

    rows: frozenset[tuple[str, str]]
    count: Decimal
    total: Decimal


def _declare(
    observations: tuple[InvoiceObservation, ...],
    *,
    revision_id: str = _REVISION_2025,
    effective_date: date = _FILING_2025,
) -> _Declared:
    revision = published_revision("347", revision_id)
    row_values = resolve_invoice_binding_row_values(revision, observations, effective_date=effective_date)
    rows_by_index: dict[int, dict[str, object]] = {}
    for (binding_id, row_index), value in row_values.items():
        rows_by_index.setdefault(row_index, {})[str(binding_id)] = value
    rows = frozenset((str(row[_NIF_BINDING]), str(row[_CLAVE_BINDING])) for row in rows_by_index.values())
    summary = resolve_invoice_binding_values(revision, observations, effective_date=effective_date)
    return _Declared(rows=rows, count=summary[_COUNT_BINDING], total=summary[_TOTAL_BINDING])


def _general_floor() -> Decimal:
    return m347_threshold_decimal(resolve_m347_counterparty_annual_threshold(effective_date=_FILING_2025))


def _clave_c_floor() -> Decimal:
    bucket = resolve_m347_threshold_buckets(effective_date=_FILING_2025).bucket_of("C")
    assert bucket.floor_fact is not None
    return m347_threshold_decimal(bucket.floor_fact)


def test_the_scenario_amounts_straddle_the_published_floors() -> None:
    """Guard the premise every scenario below relies on, read from the facts themselves."""
    general = _general_floor()
    assert Decimal("2000") < general < Decimal("4000")
    assert _clave_c_floor() < Decimal("500") < general


def test_entregas_and_adquisiciones_below_the_floor_each_are_not_declared_together() -> None:
    """2,000 of sales and 2,000 of purchases with one party: each bucket is below the floor."""
    declared = _declare((_observation("B", "2000.00"), _observation("A", "2000.00")))

    assert declared.rows == frozenset()
    assert declared.count == Decimal("0")
    assert declared.total == Decimal("0")


def test_only_the_bucket_above_the_floor_is_declared() -> None:
    """4,000 of sales and 2,000 of purchases: the B row alone, and the totals read off it."""
    declared = _declare((_observation("B", "4000.00"), _observation("A", "2000.00")))

    assert declared.rows == frozenset({(_PARTY, "B")})
    assert declared.count == Decimal("1")
    assert declared.total == Decimal("4000.00")


def test_travel_agency_ventas_combine_with_entregas() -> None:
    """F and B share the entregas bucket: 2,000 + 2,000 clears the floor, so both rows are declared."""
    declared = _declare((_observation("F", "2000.00"), _observation("B", "2000.00")))

    assert declared.rows == frozenset({(_PARTY, "B"), (_PARTY, "F")})
    assert declared.count == Decimal("2")
    assert declared.total == Decimal("4000.00")


def test_travel_agency_compras_combine_with_adquisiciones() -> None:
    """G and A share the adquisiciones bucket: 2,000 + 2,000 clears the floor, so both rows are declared."""
    declared = _declare((_observation("G", "2000.00"), _observation("A", "2000.00")))

    assert declared.rows == frozenset({(_PARTY, "A"), (_PARTY, "G")})
    assert declared.count == Decimal("2")


def test_clave_c_is_declared_above_its_own_floor() -> None:
    """500 collected for a colegiado clears the clave C floor though it is far below the general one."""
    declared = _declare((_observation("C", "500.00"),))

    assert declared.rows == frozenset({(_PARTY, "C")})
    assert declared.total == Decimal("500.00")


def test_clave_c_does_not_lift_the_entregas_bucket() -> None:
    """A party above the C floor keeps none of its below-floor entregas: the buckets never merge."""
    declared = _declare((_observation("C", "500.00"), _observation("B", "2000.00")))

    assert declared.rows == frozenset({(_PARTY, "C")})


def test_clave_d_is_its_own_bucket_apart_from_adquisiciones() -> None:
    """D and A are not summed: 2,000 + 2,000 leaves both below the floor."""
    declared = _declare((_observation("D", "2000.00"), _observation("A", "2000.00")))

    assert declared.rows == frozenset()
    assert declared.count == Decimal("0")


def test_clave_e_below_the_general_floor_is_declared_from_2025() -> None:
    """The 2025 design relates subvenciones whatever their amount."""
    declared = _declare((_observation("E", "1000.00"),))

    assert declared.rows == frozenset({(_PARTY, "E")})
    assert declared.count == Decimal("1")


def test_clave_e_below_the_general_floor_is_declared_for_2024_on_the_consolidated_reading() -> None:
    """From 2014 the consolidated art. 33.3 relates subvenciones whatever their amount.

    The 2011 design still in use for 2024 states a floor; the bucket follows the
    regulation and carries that conflict as an unsettled reading.
    """
    declared = _declare(
        (_observation("E", "1000.00", transaction_date=date(2024, 3, 10)),),
        revision_id=_REVISION_2024,
        effective_date=_FILING_2024,
    )

    assert declared.rows == frozenset({(_PARTY, "E")})
    assert declared.count == Decimal("1")
    assert resolve_m347_threshold_buckets(effective_date=_FILING_2024).bucket_of("E").reading_unsettled


def test_the_floor_must_be_exceeded_not_reached() -> None:
    """A bucket landing exactly on the floor is not declared; one cent above it is."""
    floor = _general_floor()
    declarable = m347_declarable_party_buckets(
        {("A58818501", "B"): floor, ("B12345674", "B"): floor + Decimal("0.01")},
        effective_date=_FILING_2025,
    )

    assert not declarable.admits("A58818501", "B")
    assert declarable.admits("B12345674", "B")


def test_the_published_buckets_partition_every_clave() -> None:
    """Every M347 clave sits in exactly one bucket, and each floor keeps its fact provenance."""
    buckets = resolve_m347_threshold_buckets(effective_date=_FILING_2025)
    by_clave = {clave: bucket for bucket in buckets.buckets for clave in bucket.claves}

    assert set(by_clave) == {"A", "B", "C", "D", "E", "F", "G"}
    assert by_clave["B"] is by_clave["F"]
    assert by_clave["A"] is by_clave["G"]
    assert len({by_clave[clave].token for clave in ("A", "B", "C", "D", "E")}) == 5
    assert by_clave["E"].floor is None
    assert not by_clave["E"].reading_unsettled
    assert by_clave["D"].reading_unsettled
    assert by_clave["C"].floor_fact is not None
    assert by_clave["C"].floor_fact.fact_id == "m347-clave-c-beneficiary-declaration-threshold"


# --- refusals of a malformed bucket mapping ---------------------------------


@dataclass(frozen=True, slots=True)
class _BucketMappingSource:
    """Answer the bucket query with ``entries``; delegate everything else to the published operation."""

    base: PinnedAuthorityOperation
    entries: tuple[tuple[str, str], ...]

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        if query.fact_id != _BUCKET_FACT_ID:
            return self.base.resolve_governed_fact(query)
        context = resolve_m347_counterparty_annual_threshold(effective_date=query.effective_date, authority=self.base)
        return ResolvedMappingFact(
            fact_id=_BUCKET_FACT_ID,
            variant_id=f"{_BUCKET_FACT_ID}:2025-01-01",
            date_axis=context.date_axis,
            effective_date=context.effective_date,
            valid_from=context.valid_from,
            legal_refs=context.legal_refs,
            source_refs=context.source_refs,
            review_status=context.review_status,
            ownership=context.ownership,
            authority_digest=context.authority_digest,
            source_variant_id=f"{_BUCKET_FACT_ID}:2025-01-01",
            source_revision_ids=(f"{_BUCKET_FACT_ID}:2025-01-01",),
            payload=MappingFactPayload(
                entries=tuple(MappingFactEntry(key=key, value=value) for key, value in self.entries),
            ),
        )

    def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
        return self.base.supported_filing_years()


_GENERAL = "m347-counterparty-declaration-threshold"
_WELL_FORMED: tuple[tuple[str, str], ...] = (
    ("bucket.order", "entregas,adquisiciones,resto"),
    ("bucket.entregas.claves", "B,F"),
    ("bucket.entregas.floor_fact", _GENERAL),
    ("bucket.adquisiciones.claves", "A,G"),
    ("bucket.adquisiciones.floor_fact", _GENERAL),
    ("bucket.resto.claves", "C,D,E"),
    ("bucket.resto.declared_regardless_of_amount", "true"),
)


def _resolve_with(entries: tuple[tuple[str, str], ...]) -> M347ThresholdBuckets:
    with bundled_indexed_authority().operation() as operation:
        return resolve_m347_threshold_buckets(
            effective_date=_FILING_2025,
            authority=_BucketMappingSource(base=operation, entries=entries),
        )


def test_the_override_source_resolves_a_well_formed_mapping() -> None:
    """The refusals below are meaningful only because this same source accepts a valid mapping."""
    buckets = _resolve_with(_WELL_FORMED)

    assert [bucket.token for bucket in buckets.buckets] == ["entregas", "adquisiciones", "resto"]
    assert buckets.bucket_of("E").floor is None
    assert not any(bucket.reading_unsettled for bucket in buckets.buckets)


def test_a_bucket_flagged_unsettled_carries_the_flag() -> None:
    buckets = _resolve_with((*_WELL_FORMED, ("bucket.adquisiciones.reading_unsettled", "true")))

    assert buckets.bucket_of("A").reading_unsettled
    assert not buckets.bucket_of("B").reading_unsettled


def test_a_no_floor_bucket_records_the_parties_it_admits_on_a_nonpositive_total() -> None:
    """A bucket related whatever its amount admits nil and negative totals, and says which they are."""
    with bundled_indexed_authority().operation() as operation:
        declarable = m347_declarable_party_buckets(
            {
                ("B11111112", "E"): Decimal("-50.00"),
                ("C22222229", "E"): Decimal("0.00"),
                ("D33333335", "E"): Decimal("10.00"),
                ("E44444441", "B"): Decimal("-50.00"),
            },
            effective_date=_FILING_2025,
            authority=_BucketMappingSource(base=operation, entries=_WELL_FORMED),
        )

    assert declarable.admits("B11111112", "E")
    assert declarable.admits("C22222229", "E")
    assert declarable.admits("D33333335", "E")
    assert declarable.admits_unconditional_nonpositive("B11111112", "E")
    assert declarable.admits_unconditional_nonpositive("C22222229", "E")
    assert not declarable.admits_unconditional_nonpositive("D33333335", "E")
    assert not declarable.admits("E44444441", "B")
    assert not declarable.admits_unconditional_nonpositive("E44444441", "B")


def test_a_floored_bucket_leaves_out_a_nonpositive_total_and_says_which_it_left_out() -> None:
    """Rectifications that reach a party's operations net its total to nil; the floor leaves it out, visibly."""
    with bundled_indexed_authority().operation() as operation:
        declarable = m347_declarable_party_buckets(
            {
                ("B11111112", "B"): Decimal("-1000.00"),
                ("C22222229", "B"): Decimal("0.00"),
                ("D33333335", "B"): Decimal("1000.00"),
                ("E44444441", "B"): Decimal("4000.00"),
            },
            effective_date=_FILING_2025,
            authority=_BucketMappingSource(base=operation, entries=_WELL_FORMED),
        )

    assert not declarable.admits("B11111112", "B")
    assert not declarable.admits("C22222229", "B")
    assert declarable.leaves_out_floored_nonpositive("B11111112", "B")
    assert declarable.leaves_out_floored_nonpositive("C22222229", "B")
    assert not declarable.admits("D33333335", "B")
    assert not declarable.leaves_out_floored_nonpositive("D33333335", "B")
    assert declarable.admits("E44444441", "B")
    assert not declarable.leaves_out_floored_nonpositive("E44444441", "B")
    assert not declarable.admits_unconditional_nonpositive("B11111112", "B")


def _replace(key: str, value: str | None) -> tuple[tuple[str, str], ...]:
    kept = tuple(entry for entry in _WELL_FORMED if entry[0] != key)
    return kept if value is None else (*kept, (key, value))


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        pytest.param(_replace("bucket.resto.claves", "C,D"), "exactly one bucket", id="clave-unassigned"),
        pytest.param(_replace("bucket.resto.claves", "C,D,E,A"), "exactly one bucket", id="clave-assigned-twice"),
        pytest.param(_replace("bucket.resto.claves", "C,D,E,Z"), "unknown claves", id="unknown-clave"),
        pytest.param(
            (*_WELL_FORMED, ("bucket.resto.floor_fact", _GENERAL)), "exactly one of a floor_fact", id="floor-and-any"
        ),
        pytest.param(
            _replace("bucket.resto.declared_regardless_of_amount", None),
            "exactly one of a floor_fact",
            id="no-floor-declared",
        ),
        pytest.param(
            _replace("bucket.resto.declared_regardless_of_amount", "false"),
            "exactly one of a floor_fact",
            id="regardless-false-without-floor",
        ),
        pytest.param((*_WELL_FORMED, ("bucket.resto.umbral", "1")), "unknown entry", id="unknown-field"),
        pytest.param(
            (*_WELL_FORMED, ("bucket.resto.reading_unsettled", "yes")), "reading_unsettled", id="unsettled-not-boolean"
        ),
        pytest.param((*_WELL_FORMED, ("bucket.otro.claves", "A")), "unknown entry", id="undeclared-bucket"),
    ],
)
def test_a_malformed_bucket_mapping_is_refused(entries: tuple[tuple[str, str], ...], message: str) -> None:
    with pytest.raises(RegistryValidationError, match=message):
        _resolve_with(entries)


def test_a_floor_fact_that_is_not_a_monetary_scalar_is_refused() -> None:
    """A bucket naming a non-scalar fact as its floor cannot be compared and is refused."""
    entries = _replace("bucket.entregas.floor_fact", "m347-clave-threshold-buckets")
    with pytest.raises(RegistryValidationError, match="must resolve as a scalar fact"):
        _resolve_with(entries)
