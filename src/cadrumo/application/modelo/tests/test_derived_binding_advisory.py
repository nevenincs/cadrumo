"""The derived-scoped advisory: fires on a structural gap, silent on ordinary filers.

Every derived injector now computes unconditionally, writing a zero default
where the law says zero. That is what makes a narrow advisory possible: a
binding that SELECTS an engine-derived path and still resolves to nothing
cannot be an ordinary absence, because no legitimate profile leaves a derived
path unwritten. Every fire is a structural gap -- a registry year the
injectors do not cover, or a pattern whose consuming binding drifted.

The false-fire direction is the load-bearing test here, not the true one. A
blanket "profile binding resolved to nothing" advisory would fire constantly
on optional facts an ordinary filer leaves blank, and an operator who learns
to ignore an advisory is worse off than one who never saw it. The guarderia
aggregate is the specific trap: before it moved to unconditional injection it
emitted only when positive, so an ordinary filer with descendants and no
childcare spend left it unwritten and would have tripped this advisory on the
majority case.

Real adapters: the resident registry authority and a real
:class:`UserProfileRecord` passed through the production resolver entry point.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import lru_cache

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.calculations.registry.tests.published_authority import (
    published_profile_schema,
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..profile_binding import _derived_binding_diagnostics, resolve_profile_sourced_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one authority generation for the resolver under test."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


_BUCKET = "0de41ce4-0000-4000-8000-000000000512"
_T0 = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)
_ADVISORY_REASON = "unresolved_derived_binding"


@lru_cache
def _snapshot(year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=year, period="0A")


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=facts,
        created_at=_T0,
        updated_at=_T0,
        context=_profile_creation_context_for_test(),
    )


def _derived_advisories(
    record: UserProfileRecord,
    *,
    operation: PinnedAuthorityOperation,
    year: int = 2024,
) -> tuple[str, ...]:
    """Binding ids the derived-scoped advisory fired for, via the real resolver."""
    resolution = resolve_profile_sourced_bindings(
        _snapshot(year),
        bucket_id=_BUCKET,
        profile_record=record,
        operation=operation,
    )
    return tuple(
        str(diagnostic.binding_id) for diagnostic in resolution.diagnostics if diagnostic.reason == _ADVISORY_REASON
    )


# ---------------------------------------------------------------------------
# FALSE-fire direction: the ordinary cases must stay silent.
# ---------------------------------------------------------------------------


def test_descendants_without_childcare_spend_do_not_fire_the_advisory(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The majority case: real descendants, no guardería spend, no advisory.

    This is the exact shape that would have false-fired while the guardería
    aggregate emitted only when positive.
    """
    descendientes = (
        DescendantInfo(birth_date=date(2023, 2, 10)),
        DescendantInfo(birth_date=date(2015, 7, 4)),
    )
    record = _record(*(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(descendientes)))

    assert _derived_advisories(record, operation=authority_operation) == ()


def test_childless_profile_does_not_fire_the_advisory(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A genuinely childless filer resolves every derived path to a legal zero."""
    assert (
        _derived_advisories(
            _record(UserProfileFact(path="tax_residence.ccaa", value="cataluna")),
            operation=authority_operation,
        )
        == ()
    )


def test_empty_profile_does_not_fire_the_advisory(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A profile carrying nothing at all still leaves no derived path unwritten."""
    assert _derived_advisories(_record(), operation=authority_operation) == ()


def _supported_filing_years() -> tuple[int, ...]:
    supported_years = published_supported_filing_years()
    assert supported_years is not None, "the bundled registry declares no supported filing years"
    return supported_years.years


@pytest.mark.parametrize("year", _supported_filing_years())
def test_no_advisory_on_any_covered_filing_year(
    year: int,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Every year the registry declares derived bindings for resolves them all."""
    descendientes = (DescendantInfo(birth_date=date(2015, 7, 4)),)
    record = _record(*(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(descendientes)))

    assert _derived_advisories(record, year=year, operation=authority_operation) == ()


# ---------------------------------------------------------------------------
# TRUE-fire direction: a real structural gap must be reported.
# ---------------------------------------------------------------------------


def test_advisory_fires_when_a_selected_derived_binding_resolves_to_nothing() -> None:
    """A derived binding no injector claims is reported, not silently blank.

    The real gap this guards -- an injector stopping short while the registry
    still binds the path -- is reached here by handing the advisory the real
    M100 2024 profile bindings alongside a fact index in which the injectors
    wrote nothing. That is precisely the state a registry year with no
    injector coverage produces, and it drives the shipped predicate rather
    than re-stating it.

    Without this the four silence assertions above would be satisfied just as
    well by an advisory that can never fire at all.
    """
    schema = published_profile_schema()
    snapshot = _snapshot(2024)
    bindings = tuple(b for b in snapshot.revision.bindings if b.source == "profile")

    fired = _derived_binding_diagnostics(bindings, {}, schema, bucket_id=_BUCKET)

    reasons = {diagnostic.reason for diagnostic in fired}
    assert reasons == {_ADVISORY_REASON}, reasons
    # Exactly the declared derived bindings, and nothing else: an empty fact
    # index leaves every ordinary profile binding unresolved too, so a wider
    # set would mean the advisory had escaped its derived scope.
    assert {str(d.binding_id) for d in fired} == {
        "renta-profile-anualidades-sin-minimo-descendientes",
        "renta-profile-deduccion-maternidad",
        "renta-profile-descendientes-guarderia",
        "renta-profile-guarderia-gastos-reales",
        "renta-profile-incremento-guarderia",
        "renta-profile-minimo-descendientes-autonomico",
        "renta-profile-minimo-descendientes-estatal",
    }
    assert all(d.source_kind == "profile" for d in fired)
    assert all("derives" in d.message or "derived" in d.message for d in fired)


def test_every_derived_binding_actually_resolves_for_an_ordinary_profile(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The positive control behind the silence: the bindings resolve to real values.

    Four assertions of "no advisory" mean nothing if the derived bindings were
    never selected. This proves the resolver produced a value for each of
    them, so the silence above is resolution succeeding rather than the
    advisory being unreachable.
    """
    descendientes = (DescendantInfo(birth_date=date(2023, 2, 10)),)
    record = _record(*(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(descendientes)))
    resolution = resolve_profile_sourced_bindings(
        _snapshot(2024),
        bucket_id=_BUCKET,
        profile_record=record,
        operation=authority_operation,
    )

    # Each derived binding lands in the value channel its registry declaration
    # names; the boolean régimen flag is not a decimal.
    resolved = {**resolution.binding_values, **resolution.boolean_binding_values}
    for binding_id in (
        "renta-profile-minimo-descendientes-estatal",
        "renta-profile-minimo-descendientes-autonomico",
        "renta-profile-anualidades-sin-minimo-descendientes",
        "renta-profile-descendientes-guarderia",
        "renta-profile-guarderia-gastos-reales",
    ):
        assert binding_id in resolved, f"{binding_id} was not resolved at all"

    # The guardería aggregate is the one that legitimately lands on zero for
    # this profile, and it must be a real zero rather than an absence.
    assert resolved["renta-profile-guarderia-gastos-reales"] == Decimal("0")
    assert resolved["renta-profile-descendientes-guarderia"] == Decimal("1")
