"""Period-versioned IVA rate lookup tests.

Confirms that :func:`cadrumo.domain.iva.lookup_rate` resolves the correct
:class:`cadrumo.domain.iva.IvaRateRecord` record across the 2024 / 2025 ES window
boundary, and that the committed registry has no overlapping effective
windows.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from itertools import pairwise

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.authority_artifact import AuthorityComponentQuery, GovernedFactComponentQuery
from ...calculations.registry.facts.schema import GovernedFact
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader
from ..errors import IvaRateNotFoundError, IvaRateOverlapError
from ..lookup import lookup_rate, rate_kinds_for_declared_rate, resolve_iva_rate, resolve_iva_rate_from_component
from ..rates import load_iva_rate_table
from ..schema import EUMemberState, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ES = EUMemberState._from_registry("es")
_GENERAL = IvaRateKind("general")
_REDUCED = IvaRateKind("reduced")
_SUPER_REDUCED = IvaRateKind("super_reduced")
_ZERO = IvaRateKind("zero")


def _mapping_fact(
    fact_id: str,
    variant_id: str,
    *,
    valid_from: date,
    valid_to: date | None = None,
    date_axis: str = "devengo_date",
    selectors: tuple[dict[str, object], ...] = (),
    entries: tuple[dict[str, object], ...],
) -> GovernedFact:
    """Build one narrow typed fact fixture for the pinned IVA reader seam."""
    return GovernedFact.model_validate(
        {
            "fact_id": fact_id,
            "family": "mapping",
            "variants": (
                {
                    "variant_id": variant_id,
                    "selectors": selectors,
                    "date_axis": date_axis,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "payload": {"kind": "mapping", "entries": entries},
                    "source_refs": ("aeat-iva-rate-schedule",),
                    "review_status": "agent_reviewed",
                    "ownership": "authored",
                },
            ),
        },
    )


def _rate_variant(
    variant_id: str,
    *,
    kind: str,
    role: str,
    valid_from: date,
    valid_to: date | None = None,
    pct: str,
    supersedes_tier_default: bool = False,
) -> dict[str, object]:
    """Build one representative ES rate variant for the pinned fixture."""
    return {
        "variant_id": variant_id,
        "selectors": (
            {"name": "member_state", "value": "es"},
            {"name": "kind", "value": kind},
            {"name": "rate_role", "value": role},
        ),
        "date_axis": "devengo_date",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "payload": {
            "kind": "mapping",
            "entries": (
                {"key": "pct", "value_type": "decimal", "value": pct},
                {"key": "supersedes_tier_default", "value": supersedes_tier_default},
            ),
        },
        "legal_refs": ("ley-37-1992:art-90",),
        "review_status": "agent_reviewed",
        "ownership": "authored",
    }


def _pinned_iva_facts(
    *,
    include_component_probe: bool = True,
) -> dict[AuthorityComponentQuery, object]:
    """Return the rate and vocabulary facts required by the focused tests."""
    return {
        GovernedFactComponentQuery("eu-member-state-catalogue"): _mapping_fact(
            "eu-member-state-catalogue",
            "eu-member-state-catalogue:2021-01-01",
            valid_from=date(1900, 1, 1),
            date_axis="filing_period",
            entries=(
                {"key": "member_state.order", "value": "es"},
                {"key": "member_state.aliases", "value": "ES=es"},
            ),
        ),
        GovernedFactComponentQuery("iva-rate-slot-catalogue"): _mapping_fact(
            "iva-rate-slot-catalogue",
            "iva-rate-slot-catalogue:1993-01-01",
            valid_from=date(1993, 1, 1),
            entries=(
                {"key": "rate_kind.order", "value": "general,reduced,super_reduced,zero,exempt"},
                {"key": "rate_kind.positive_order", "value": "general,reduced,super_reduced"},
                {"key": "rate_kind.zero_token", "value": "zero"},
                {"key": "rate_kind.exempt_token", "value": "exempt"},
                {"key": "rate_kind.non_rate_token", "value": "none"},
                {"key": "rate_kind.general.value", "value": "general"},
                {"key": "rate_kind.general.description", "value": "General IVA rate tier."},
                {"key": "rate_kind.general.category", "value": "domestic_general"},
                {"key": "rate_kind.reduced.value", "value": "reduced"},
                {"key": "rate_kind.reduced.description", "value": "Reduced IVA rate tier."},
                {"key": "rate_kind.reduced.category", "value": "domestic_reduced"},
                {"key": "rate_kind.super_reduced.value", "value": "super_reduced"},
                {"key": "rate_kind.super_reduced.description", "value": "Super-reduced IVA rate tier."},
                {"key": "rate_kind.super_reduced.category", "value": "domestic_super_reduced"},
                {"key": "rate_kind.zero.value", "value": "zero"},
                {"key": "rate_kind.zero.description", "value": "Zero-rated IVA tier."},
                {"key": "rate_kind.zero.category", "value": "domestic_zero"},
                {"key": "rate_kind.exempt.value", "value": "exempt"},
                {"key": "rate_kind.exempt.description", "value": "Exempt IVA tier."},
                {"key": "rate_kind.exempt.category", "value": "domestic_exempt"},
            ),
        ),
        GovernedFactComponentQuery("iva-rate-schedule"): GovernedFact.model_validate(
            {
                "fact_id": "iva-rate-schedule",
                "family": "mapping",
                "variants": (
                    # The direct component-reader assertion uses a deliberately
                    # narrow row; the operation fixture omits it because the
                    # committed 2012--2024 row already covers that date.
                    *(
                        (
                            _rate_variant(
                                "iva-rate.es.general.2024.ordinary",
                                kind="general",
                                role="ordinary",
                                valid_from=date(2024, 1, 1),
                                valid_to=date(2024, 12, 31),
                                pct="21",
                            ),
                        )
                        if include_component_probe
                        else ()
                    ),
                    *(
                        (
                            _rate_variant(
                                "iva-rate.es.general.2012-09-01.ordinary",
                                kind="general",
                                role="ordinary",
                                valid_from=date(2012, 9, 1),
                                valid_to=date(2024, 12, 31),
                                pct="21",
                            ),
                        )
                        if not include_component_probe
                        else ()
                    ),
                    _rate_variant(
                        "iva-rate.es.reduced.2012-09-01.ordinary",
                        kind="reduced",
                        role="ordinary",
                        valid_from=date(2012, 9, 1),
                        valid_to=date(2024, 12, 31),
                        pct="10",
                    ),
                    _rate_variant(
                        "iva-rate.es.super_reduced.1995-01-01.ordinary",
                        kind="super_reduced",
                        role="ordinary",
                        valid_from=date(1995, 1, 1),
                        valid_to=date(2024, 12, 31),
                        pct="4",
                    ),
                    _rate_variant(
                        "iva-rate.es.zero.2023-01-01.ordinary",
                        kind="zero",
                        role="ordinary",
                        valid_from=date(2023, 1, 1),
                        valid_to=date(2024, 6, 30),
                        pct="0",
                    ),
                    _rate_variant(
                        "iva-rate.es.zero.2024-07-01.ordinary",
                        kind="zero",
                        role="ordinary",
                        valid_from=date(2024, 7, 1),
                        valid_to=date(2024, 9, 30),
                        pct="0",
                    ),
                    _rate_variant(
                        "iva-rate.es.general.2025-01-01.ordinary",
                        kind="general",
                        role="ordinary",
                        valid_from=date(2025, 1, 1),
                        pct="21",
                    ),
                    _rate_variant(
                        "iva-rate.es.reduced.2025-01-01.ordinary",
                        kind="reduced",
                        role="ordinary",
                        valid_from=date(2025, 1, 1),
                        pct="10",
                    ),
                    _rate_variant(
                        "iva-rate.es.super_reduced.2025-01-01.ordinary",
                        kind="super_reduced",
                        role="ordinary",
                        valid_from=date(2025, 1, 1),
                        pct="4",
                    ),
                    _rate_variant(
                        "iva-rate.es.reduced.2023-01-01.coexisting-5",
                        kind="reduced",
                        role="coexisting-5",
                        valid_from=date(2023, 1, 1),
                        valid_to=date(2024, 6, 30),
                        pct="5",
                        supersedes_tier_default=True,
                    ),
                    _rate_variant(
                        "iva-rate.es.reduced.2024-07-01.coexisting-5",
                        kind="reduced",
                        role="coexisting-5",
                        valid_from=date(2024, 7, 1),
                        valid_to=date(2024, 9, 30),
                        pct="5",
                        supersedes_tier_default=True,
                    ),
                    _rate_variant(
                        "iva-rate.es.super_reduced.2024-10-01.coexisting-2",
                        kind="super_reduced",
                        role="coexisting-2",
                        valid_from=date(2024, 10, 1),
                        valid_to=date(2024, 12, 31),
                        pct="2",
                        supersedes_tier_default=True,
                    ),
                    _rate_variant(
                        "iva-rate.es.reduced.2024-10-01.coexisting-7.5",
                        kind="reduced",
                        role="coexisting-7.5",
                        valid_from=date(2024, 10, 1),
                        valid_to=date(2024, 12, 31),
                        pct="7.5",
                        supersedes_tier_default=True,
                    ),
                    {
                        "variant_id": "iva-rate-schedule:rate-role-catalogue:1995-01-01",
                        "selectors": ({"name": "scope", "value": "rate_role_catalogue"},),
                        "date_axis": "devengo_date",
                        "valid_from": date(1995, 1, 1),
                        "payload": {
                            "kind": "mapping",
                            "entries": (
                                {
                                    "key": "rate_role.order",
                                    "value": "ordinary,coexisting-5,coexisting-2,coexisting-7.5",
                                },
                                {"key": "rate_role.default", "value": "ordinary"},
                                {"key": "rate_role.ordinary.value", "value": "ordinary"},
                                {"key": "rate_role.ordinary.is_default", "value": "true"},
                                {"key": "rate_role.ordinary.supersedes_tier_default", "value": "false"},
                                {"key": "rate_role.coexisting-5.value", "value": "coexisting-5"},
                                {"key": "rate_role.coexisting-5.is_default", "value": "false"},
                                {"key": "rate_role.coexisting-5.supersedes_tier_default", "value": "true"},
                                {"key": "rate_role.coexisting-2.value", "value": "coexisting-2"},
                                {"key": "rate_role.coexisting-2.is_default", "value": "false"},
                                {"key": "rate_role.coexisting-2.supersedes_tier_default", "value": "true"},
                                {"key": "rate_role.coexisting-7.5.value", "value": "coexisting-7.5"},
                                {"key": "rate_role.coexisting-7.5.is_default", "value": "false"},
                                {
                                    "key": "rate_role.coexisting-7.5.supersedes_tier_default",
                                    "value": "true",
                                },
                            ),
                        },
                        "legal_refs": ("ley-37-1992:art-90",),
                        "review_status": "agent_reviewed",
                        "ownership": "authored",
                    },
                ),
            },
        ),
    }


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    """Pin one representative in-memory authority for all public lookups."""
    reader = FakeAuthorityComponentReader(_pinned_iva_facts(include_component_probe=False))
    pinned = PinnedAuthorityOperation(reader, reader.pin())
    with validating_governed_facts(pinned):
        yield pinned


def test_component_reader_resolves_dated_iva_rate_with_one_pin() -> None:
    """Load the rate declaration by exact fact id and retain its generation."""
    reader = FakeAuthorityComponentReader(_pinned_iva_facts())
    generation = reader.pin()

    resolved = resolve_iva_rate_from_component(
        reader,
        pin=generation,
        member_state="es",
        kind=IvaRateKind("general"),
        on_date=date(2024, 6, 15),
    )

    assert resolved.fact_id == "iva-rate-schedule"
    assert resolved.variant_id == "iva-rate.es.general.2024.ordinary"
    assert resolved.effective_date == date(2024, 6, 15)
    assert resolved.valid_from == date(2024, 1, 1)
    assert resolved.valid_to == date(2024, 12, 31)
    assert resolved.authority_digest == generation.logical_generation
    assert reader.loads == [
        GovernedFactComponentQuery("eu-member-state-catalogue"),
        GovernedFactComponentQuery("iva-rate-slot-catalogue"),
        GovernedFactComponentQuery("iva-rate-schedule"),
    ]


def test_es_general_2024_rate(operation: PinnedAuthorityOperation) -> None:
    """A 2024 date resolves the 21 % general rate.

    ``effective_from`` is 2012-09-01, not 2024-01-01. The earlier value was a
    bulk-refresh boundary sitting in a field defined as "First date the rate
    applies", so the table asserted the general rate began in 2024 -- and this
    test asserted it back. RDL 20/2012 art. 23.Dos fixed 21 % from 1 September
    2012 and nothing has changed it since.
    """
    rate = lookup_rate(_ES, _GENERAL, date(2024, 6, 15), operation=operation)
    assert rate.pct == Decimal("21")
    assert rate.effective_from == date(2012, 9, 1)
    assert rate.effective_until == date(2024, 12, 31)


def test_rate_lookup_retains_the_matched_authority_provenance(operation: PinnedAuthorityOperation) -> None:
    """The public projection is backed by the exact coexisting fact variant."""
    resolved = resolve_iva_rate(
        _ES,
        _SUPER_REDUCED,
        date(2024, 11, 1),
        rate_role="coexisting-2",
        operation=operation,
    )

    assert resolved.fact_id == "iva-rate-schedule"
    assert resolved.date_axis.value == "devengo_date"
    assert resolved.effective_date == date(2024, 11, 1)
    assert {selector.name: selector.value for selector in resolved.matched_selectors} == {
        "member_state": "es",
        "kind": "super_reduced",
        "rate_role": "coexisting-2",
    }
    assert resolved.legal_refs
    assert len(resolved.authority_digest) == 64


def test_es_general_2025_rate(operation: PinnedAuthorityOperation) -> None:
    rate = lookup_rate(_ES, _GENERAL, date(2025, 6, 15), operation=operation)
    assert rate.pct == Decimal("21")
    assert rate.effective_from == date(2025, 1, 1)
    assert rate.effective_until is None


def test_es_general_2024_last_day(operation: PinnedAuthorityOperation) -> None:
    """December 31 2024 still resolves to the 2024 record."""
    rate = lookup_rate(_ES, _GENERAL, date(2024, 12, 31), operation=operation)
    assert rate.effective_until == date(2024, 12, 31)


def test_es_general_2025_first_day(operation: PinnedAuthorityOperation) -> None:
    """January 1 2025 resolves to the 2025 record (no overlap)."""
    rate = lookup_rate(_ES, _GENERAL, date(2025, 1, 1), operation=operation)
    assert rate.effective_from == date(2025, 1, 1)


def test_es_super_reduced_2024_and_2025_both_resolve(operation: PinnedAuthorityOperation) -> None:
    """The 4 % super-reducido is registered for both years."""
    rate_2024 = lookup_rate(_ES, _SUPER_REDUCED, date(2024, 6, 15), operation=operation)
    rate_2025 = lookup_rate(_ES, _SUPER_REDUCED, date(2025, 6, 15), operation=operation)
    assert rate_2024.pct == Decimal("4")
    assert rate_2025.pct == Decimal("4")


def test_es_reduced_2024_and_2025_both_resolve(operation: PinnedAuthorityOperation) -> None:
    """The 10 % reducido is registered for both years."""
    rate_2024 = lookup_rate(_ES, _REDUCED, date(2024, 6, 15), operation=operation)
    rate_2025 = lookup_rate(_ES, _REDUCED, date(2025, 6, 15), operation=operation)
    assert rate_2024.pct == Decimal("10")
    assert rate_2025.pct == Decimal("10")


def test_es_lookup_before_the_general_rate_existed_raises(operation: PinnedAuthorityOperation) -> None:
    """A date before 1 September 2012 has no registered general rate, and must refuse.

    This replaces an assertion that 2023 raises. That was true of the table and
    false of the law: the boundary it pinned was a refresh artefact, so the test
    encoded the defect as the contract and would have kept the correction out.

    The boundary is still real and still worth a gate -- it has simply moved to
    where the statute puts it. Before RDL 20/2012 took effect the general rate
    was 18 %, which this table does not carry, so 2012-08-31 must refuse while
    2012-09-01 resolves. Both directions are asserted, because a refusal test
    with no matching acceptance cannot tell a boundary from a blanket gap.
    """
    with pytest.raises(IvaRateNotFoundError, match=r"ES|GENERAL|2012|rate"):
        lookup_rate(_ES, _GENERAL, date(2012, 8, 31), operation=operation)

    assert lookup_rate(_ES, _GENERAL, date(2012, 9, 1), operation=operation).pct == Decimal("21")


def test_es_pre_2024_years_inside_prescripcion_now_resolve(operation: PinnedAuthorityOperation) -> None:
    """2022 and 2023 price correctly, which is the point of the correction.

    Both years sit inside the four-year prescripción window, and the registry
    declares pre-2024 revisions on more than thirty modelos, so a taxpayer
    amending either year needs the rate. Before the correction every tier
    refused for both.
    """
    for year in (2022, 2023):
        assert lookup_rate(_ES, _GENERAL, date(year, 6, 1), operation=operation).pct == Decimal("21")
        assert lookup_rate(_ES, _REDUCED, date(year, 6, 1), operation=operation).pct == Decimal("10")


def test_committed_registry_has_no_overlapping_windows(operation: PinnedAuthorityOperation) -> None:
    """No two TIER-DEFINING rates claim the same tier at the same moment.

    Scoped to records that define what a tier means, mirroring the loader's own
    rule. A ``supersedes_tier_default`` rate exists precisely to overlap: a
    statute applied it to part of a tier's supplies while the rest stayed on the
    ordinary rate, so both are simultaneously correct and neither replaces the
    other. Asserting over those would reject the shape the registry is meant to
    carry; asserting only over them would let two genuine tier definitions
    collide, which is the ambiguity ``lookup_rate`` depends on this invariant to
    prevent.
    """
    for member_state, rates in load_iva_rate_table(operation=operation).items():
        by_kind: dict[IvaRateKind, list[tuple[date, date]]] = {}
        for rate in rates:
            if rate.supersedes_tier_default:
                continue
            by_kind.setdefault(rate.kind, []).append((rate.effective_from, rate.effective_until or date.max))
        for kind, windows in by_kind.items():
            ordered = sorted(windows)
            for previous, current in pairwise(ordered):
                if previous[1] >= current[0]:
                    raise IvaRateOverlapError(f"{member_state.value}/{kind.value}: {previous} overlaps {current}")


def test_a_declared_zero_resolves_to_the_zero_tier_on_every_date(operation: PinnedAuthorityOperation) -> None:
    """0 % is always a legitimate Spanish declared rate, whatever the table records.

    Spain zero-rates on FOUR grounds, three of them permanent: exports to a
    third country (LIVA art. 21), intra-community supplies (art. 25), entregas
    of donativos to Ley 49/2002 entities (art. 91.Cuatro), and the temporary
    RD-ley 4/2024 basic-foods window. The authored rate schedule records only
    the last, because a flat ``kind = "zero"`` record cannot be
    bounded to a class of supply.

    Reading that partial table as exhaustive made ``rate_kinds_for_declared_rate``
    answer nothing for 0 % outside July-September 2024, so every export and
    intra-EU supply became unclassifiable at any other date -- live for 2025 and
    2026, not a historical-fixture problem. Seventeen tests failed on it.

    Whether a PARTICULAR supply was entitled to zero-rating is a question about
    the supply, and it lives on the category axis, which can tell
    ``DOMESTIC_ZERO`` from ``EXPORT_THIRD_COUNTRY_ZERO_RATED``. The rate axis
    structurally cannot express it, so it must not pretend to answer it.
    """
    for on_date in (date(2024, 3, 15), date(2024, 8, 15), date(2024, 11, 15), date(2025, 6, 1), date(2026, 6, 1)):
        assert rate_kinds_for_declared_rate(_ES, Decimal("0"), on_date, operation=operation) == (_ZERO,), (
            f"0 % must resolve to the zero tier on {on_date.isoformat()}: the table's silence about a zero "
            "record is incomplete coverage, not a statement that zero-rating was unlawful that day"
        )


def test_the_zero_exemption_does_not_leak_into_the_dated_temporary_rates(
    operation: PinnedAuthorityOperation,
) -> None:
    """Control: the RD-ley 4/2024 rates stay window-bound, so the narrowing is not reverted.

    The zero answer is unconditional; nothing else is. Without this the fix
    above could have been implemented by making every rate date-blind, which
    would re-admit a 2 % foodstuffs line in 2025 -- a rate the statute had
    withdrawn, and precisely what the tax review closed.

    Each rate is checked both INSIDE its own window and OUTSIDE it, so the
    assertion fails if the window collapses in either direction.
    """
    inside_summer = date(2024, 8, 15)
    inside_autumn = date(2024, 11, 15)
    after = date(2025, 6, 1)

    assert rate_kinds_for_declared_rate(_ES, Decimal("0.05"), inside_summer, operation=operation) == (_REDUCED,)
    assert rate_kinds_for_declared_rate(_ES, Decimal("0.02"), inside_autumn, operation=operation) == (_SUPER_REDUCED,)
    assert rate_kinds_for_declared_rate(_ES, Decimal("0.075"), inside_autumn, operation=operation) == (_REDUCED,)

    for withdrawn in (Decimal("0.02"), Decimal("0.05"), Decimal("0.075")):
        assert rate_kinds_for_declared_rate(_ES, withdrawn, after, operation=operation) == (), (
            f"{withdrawn} must not resolve in 2025 -- the temporary windows closed, and a date-blind fix "
            "would silently re-admit a rate the statute withdrew"
        )
