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

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import lru_cache

import pytest

from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.contribuyente import DescendantInfo, descendant_facts_from_list
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..profile_binding import _derived_binding_diagnostics, resolve_profile_sourced_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "0de41ce4-0000-4000-8000-000000000512"
_T0 = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)
_ADVISORY_REASON = "unresolved_derived_binding"


@lru_cache
def _snapshot(year: int) -> RegistrySnapshot:
    return bundled_authority().snapshot("100", filing_year=year, period="0A")


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=facts,
        created_at=_T0,
        updated_at=_T0,
    )


def _derived_advisories(record: UserProfileRecord, *, year: int = 2024) -> tuple[str, ...]:
    """Binding ids the derived-scoped advisory fired for, via the real resolver."""
    resolution = resolve_profile_sourced_bindings(
        _snapshot(year),
        bucket_id=_BUCKET,
        profile_record=record,
    )
    return tuple(
        str(diagnostic.binding_id) for diagnostic in resolution.diagnostics if diagnostic.reason == _ADVISORY_REASON
    )


# ---------------------------------------------------------------------------
# FALSE-fire direction: the ordinary cases must stay silent.
# ---------------------------------------------------------------------------


def test_descendants_without_childcare_spend_do_not_fire_the_advisory() -> None:
    """The majority case: real descendants, no guardería spend, no advisory.

    This is the exact shape that would have false-fired while the guardería
    aggregate emitted only when positive.
    """
    descendientes = (
        DescendantInfo(birth_date=date(2023, 2, 10)),
        DescendantInfo(birth_date=date(2015, 7, 4)),
    )
    record = _record(*(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(descendientes)))

    assert _derived_advisories(record) == ()


def test_childless_profile_does_not_fire_the_advisory() -> None:
    """A genuinely childless filer resolves every derived path to a legal zero."""
    assert _derived_advisories(_record(UserProfileFact(path="tax_residence.ccaa", value="cataluna"))) == ()


def test_empty_profile_does_not_fire_the_advisory() -> None:
    """A profile carrying nothing at all still leaves no derived path unwritten."""
    assert _derived_advisories(_record()) == ()


@pytest.mark.parametrize("year", [2020, 2021, 2022, 2023, 2024, 2025])
def test_no_advisory_on_any_covered_filing_year(year: int) -> None:
    """Every year the registry declares derived bindings for resolves them all."""
    descendientes = (DescendantInfo(birth_date=date(2015, 7, 4)),)
    record = _record(*(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(descendientes)))

    assert _derived_advisories(record, year=year) == ()


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
    schema = load_user_profile_schema()
    snapshot = _snapshot(2024)
    bindings = tuple(b for b in snapshot.revision.bindings if b.source == "profile")

    fired = _derived_binding_diagnostics(bindings, {}, schema, bucket_id=_BUCKET)

    reasons = {diagnostic.reason for diagnostic in fired}
    assert reasons == {_ADVISORY_REASON}, reasons
    # Exactly the six declared derived namespaces, and nothing else: an empty
    # fact index leaves every ordinary profile binding unresolved too, so a
    # wider count would mean the advisory had escaped its derived scope.
    assert len(fired) == 6, sorted(str(d.binding_id) for d in fired)
    assert all(d.source_kind == "profile" for d in fired)
    assert all("derives" in d.message or "derived" in d.message for d in fired)


def test_every_derived_binding_actually_resolves_for_an_ordinary_profile() -> None:
    """The positive control behind the silence: the bindings resolve to real values.

    Four assertions of "no advisory" mean nothing if the derived bindings were
    never selected. This proves the resolver produced a value for each of
    them, so the silence above is resolution succeeding rather than the
    advisory being unreachable.
    """
    descendientes = (DescendantInfo(birth_date=date(2023, 2, 10)),)
    record = _record(*(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(descendientes)))
    resolution = resolve_profile_sourced_bindings(_snapshot(2024), bucket_id=_BUCKET, profile_record=record)

    resolved = resolution.binding_values
    for binding_id in (
        "renta-2024-profile-minimo-descendientes-estatal",
        "renta-2024-profile-minimo-descendientes-autonomico",
        "renta-2024-profile-anualidades-sin-minimo-descendientes",
        "renta-2024-profile-descendientes-guarderia",
        "renta-2024-profile-guarderia-gastos-reales",
    ):
        assert binding_id in resolved, f"{binding_id} was not resolved at all"

    # The guardería aggregate is the one that legitimately lands on zero for
    # this profile, and it must be a real zero rather than an absence.
    assert resolved["renta-2024-profile-guarderia-gastos-reales"] == Decimal("0")
    assert resolved["renta-2024-profile-descendientes-guarderia"] == Decimal("1")
