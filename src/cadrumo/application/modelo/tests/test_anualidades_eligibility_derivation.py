"""LIRPF art. 64/75 anualidades separate-escala eligibility flag derivation.

The régimen predicate for casillas 0528/0530/0529/0531 consumes a profile
binding whose value is derived, not operator-typed: it is true (eligible — the
non-custodial payer without the mínimo por descendientes) unless custody is
shared, in which case the payer retains the mínimo and the régimen is off
(flag false). These tests pin the derivation
(:func:`inject_derived_anualidades_eligibility_facts`) directly on a
fact-index dict so the custody negation and the per-year gating are exercised
without the full calculation harness.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ..profile_derived_facts import inject_derived_anualidades_eligibility_facts

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR = newest_authored_edition("100")


def _key(year: int) -> str:
    return f"renta_family.anualidades_sin_minimo_descendientes_{year}"


def _snapshot(year: int) -> RegistrySnapshot:
    """Real Modelo 100 snapshot: the flag now shares the aggregates' eligibility
    predicate, which reads the Art. 58.1 / Art. 61 norma 2a ceilings from the
    revision's own registry parameters."""
    return published_snapshot("100", filing_year=year, period="0A")


def test_default_eligible_when_no_descendants() -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        fact_index: dict[str, object] = {}
        fact_index_narrowed: Any = fact_index
        inject_derived_anualidades_eligibility_facts(
            fact_index_narrowed, _snapshot(_YEAR), operation=_authority_operation_for_test
        )
        assert fact_index[_key(_YEAR)] is True


def test_flag_off_when_custody_shared() -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        fact_index: dict[str, object] = {
            "renta_family.descendiente.0.birth_date": date(_YEAR - 10, 5, 1).isoformat(),
            "renta_family.descendiente.0.custodia_compartida": "true",
        }
        fact_index_narrowed: Any = fact_index
        inject_derived_anualidades_eligibility_facts(
            fact_index_narrowed, _snapshot(_YEAR), operation=_authority_operation_for_test
        )
        assert fact_index[_key(_YEAR)] is False


def test_flag_eligible_when_custody_not_shared() -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        fact_index: dict[str, object] = {
            "renta_family.descendiente.0.birth_date": date(_YEAR - 10, 5, 1).isoformat(),
            "renta_family.descendiente.0.custodia_compartida": "false",
        }
        fact_index_narrowed: Any = fact_index
        inject_derived_anualidades_eligibility_facts(
            fact_index_narrowed, _snapshot(_YEAR), operation=_authority_operation_for_test
        )
        assert fact_index[_key(_YEAR)] is True


def test_shared_custody_ignored_when_descendant_not_eligible_ordinary() -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        # A non-cohabiting descendant is not eligible for the Art. 58.1 ordinary
        # mínimo, so a shared-custody flag on that row does not negate eligibility.
        fact_index: dict[str, object] = {
            "renta_family.descendiente.0.birth_date": date(_YEAR - 10, 5, 1).isoformat(),
            "renta_family.descendiente.0.custodia_compartida": "true",
            "renta_family.descendiente.0.convivencia": "false",
        }
        fact_index_narrowed: Any = fact_index
        inject_derived_anualidades_eligibility_facts(
            fact_index_narrowed, _snapshot(_YEAR), operation=_authority_operation_for_test
        )
        assert fact_index[_key(_YEAR)] is True


def test_untouched_for_out_of_scope_year() -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        # Modelo 100 publishes no 2019 revision, so the out-of-scope year is
        # exercised by re-stamping a real snapshot's filing_year rather than by
        # asking the authority for a revision that does not exist.
        out_of_scope = _snapshot(_YEAR).model_copy(update={"filing_year": filing_year_envelope().floor - 1})
        fact_index: dict[str, object] = {}
        fact_index_narrowed: Any = fact_index
        inject_derived_anualidades_eligibility_facts(
            fact_index_narrowed, out_of_scope, operation=_authority_operation_for_test
        )
        assert _key(filing_year_envelope().floor - 1) not in fact_index


def test_stored_fact_at_the_derived_path_is_overwritten_by_the_computation() -> None:
    """The art. 64/75 eligibility derivation wins over a value stored at the path.

    Inverted from the former idempotency test, which pinned the injector
    deferring to a stored fact and so let an operator decide a régimen
    question the law owns.

    The seeded ``False`` discriminates here for a reason worth stating, since
    unlike its mínimo sibling ``False`` IS reachable by the real derivation (a
    shared-custody descendant yields it). It cannot be reached by THIS
    profile: no descendants are declared, so the form-faithful default is
    ``True``. Seed and computation therefore differ, and the assertion proves
    which one survived rather than restating the seed.
    """
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        fact_index: dict[str, object] = {_key(_YEAR): False}
        fact_index_narrowed: Any = fact_index
        inject_derived_anualidades_eligibility_facts(
            fact_index_narrowed, _snapshot(_YEAR), operation=_authority_operation_for_test
        )
        assert fact_index[_key(_YEAR)] is True


def test_a_snapshot_without_projection_is_keyed_by_its_own_filing_year() -> None:
    """An unprojected snapshot still gets the flag, keyed by its filing year.

    Formatting the optional authored year directly produced ``..._None``,
    which no declared selector matches, so the injector returned without
    deriving anything and the régimen went silently unresolved.
    """
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        unprojected = _snapshot(_YEAR).model_copy(update={"authored_filing_year": None})
        fact_index: dict[str, object] = {}
        fact_index_narrowed: Any = fact_index
        inject_derived_anualidades_eligibility_facts(
            fact_index_narrowed, unprojected, operation=_authority_operation_for_test
        )
        assert fact_index[_key(_YEAR)] is True
        assert not any(key.endswith("_None") for key in fact_index)


def test_all_in_scope_years_default_eligible() -> None:
    """Every filing year the published support envelope admits defaults eligible.

    A projected year reuses its source revision's declared selector, so the
    flag is keyed by the snapshot's authored year, the key the régimen
    predicate of that same revision reads.
    """
    supported_years = published_supported_filing_years()
    assert supported_years is not None
    for year in supported_years.years:
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            snapshot = _snapshot(year)
            fact_index: dict[str, object] = {}
            fact_index_narrowed: Any = fact_index
            inject_derived_anualidades_eligibility_facts(
                fact_index_narrowed, snapshot, operation=_authority_operation_for_test
            )
            assert fact_index[_key(snapshot.authored_filing_year or snapshot.filing_year)] is True, year
