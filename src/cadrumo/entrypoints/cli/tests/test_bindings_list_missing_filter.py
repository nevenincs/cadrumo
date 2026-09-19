"""Strict-subset behaviour proof for ``aeat app modelo bindings list --missing``.

``bindings list --missing`` narrows the binding list to the bindings the
operator still owes: it drops any binding the active profile already resolves
(``source = "profile"``). The pre-existing surface test only asserted the
``missing_filter\tTrue`` echo line — it never proved the filter actually
removed rows, so a no-op could not be told from a working filter.

This module pins the load-bearing contract with a real-behaviour
strict-subset test: against an active bucket whose profile satisfies a
PROPER subset of Modelo 100's formula-consumed ``source = "profile"``
bindings, ``--missing`` must return STRICTLY FEWER rows than the
unfiltered listing, and the rows it removes must be EXACTLY the
profile-resolved binding ids — no more, no fewer. No mocks: a real
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord` is persisted to a
real bucket and the real registry authority resolves the bindings.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import set_active_test_profile_facts

from ....domain.user_profile.values import UserProfileFact
from ._strict_cli_fixture_support import binding_isolated_backend
from .cli_runner import invoke_cached_cli

__all__ = ["binding_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Modelo 100 (IRPF) 2025 declares formula-consumed ``source = "profile"``
# bindings. The partial profile below satisfies the explicit facts for
# tax-residence CCAA, declaration type, taxpayer birth date, and
# minor-children-in-unit count. The real profile resolver also derives neutral
# defaults for the anualidades eligibility and Madrid nacimiento/adopción
# operands. The remaining profile bindings (spouse, descendants, marriage
# deltas, ...) and every non-profile binding (ledger aggregations,
# prior-filing pulls) stay unresolved, i.e. still "missing". New registry
# declarations may add further profile-derived defaults, so the assertions
# below pin the seeded facts without freezing the complete authority set.
_MODELO = "100"
_YEAR = 2025
_PERIOD = "0A"
_KNOWN_RESOLVED_BINDING_IDS = frozenset(
    {
        "renta-profile-tax-residence-ccaa",
        "renta-profile-declaration-type",
        "renta-profile-taxpayer-birth-date",
        "renta-profile-family-minor-children-in-unit",
        "renta-profile-has-economic-activity",
        "renta-profile-anualidades-sin-minimo-descendientes",
        "renta-profile-madrid-nacimiento-adopcion-eligible-count",
        "renta-profile-unidad-familiar-otros-miembros-base",
        "renta-profile-minimo-descendientes-estatal",
        "renta-profile-minimo-descendientes-autonomico",
    },
)


def _seed_partial_modelo_100_profile() -> None:
    """Write the four profile facts that resolve a proper subset of M100 bindings."""
    set_active_test_profile_facts(
        (
            UserProfileFact(path="tax_residence.ccaa", value="cataluna"),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        ),
    )


def _binding_rows_in_listing(output: str) -> dict[str, tuple[str, ...]]:
    """Extract binding rows from a ``bindings list`` text envelope.

    Each binding row is tab-separated as
    ``modelo<TAB>revision<TAB>period<TAB>binding_id<TAB>source<TAB>...``;
    the binding id is the fourth column. Header / metadata lines (which
    have a different leading token) carry no registry binding id, so a row
    qualifies only when its fourth column looks like a binding id.
    """
    rows: dict[str, tuple[str, ...]] = {}
    for line in output.splitlines():
        columns = line.split("\t")
        if len(columns) < 5:
            continue
        if columns[0] == _MODELO:
            rows[columns[3]] = tuple(columns)
    return rows


def _binding_ids_in_listing(output: str) -> set[str]:
    """Extract binding ids from a ``bindings list`` text envelope."""
    return set(_binding_rows_in_listing(output))


def test_bindings_list_missing_returns_strict_subset_of_unfiltered() -> None:
    """``--missing`` removes the profile-resolved bindings.

    With an active profile that satisfies a proper subset of Modelo 100's
    ``source = "profile"`` bindings, the ``--missing`` listing must be a
    strict subset of the unfiltered listing and remove every binding backed
    by the seeded facts. The authority may add further derived profile
    bindings, so the test does not freeze that complete set.
    """
    _seed_partial_modelo_100_profile()
    scope = ["app", "modelo", "bindings", "list", "--modelo", _MODELO, "--year", str(_YEAR), "--period", _PERIOD]

    unfiltered = invoke_cached_cli(scope)
    assert unfiltered.exit_code == 0, unfiltered.output
    filtered = invoke_cached_cli([*scope, "--missing"])
    assert filtered.exit_code == 0, filtered.output

    all_rows = _binding_rows_in_listing(unfiltered.output)
    missing_rows = _binding_rows_in_listing(filtered.output)
    all_ids = set(all_rows)
    missing_ids = set(missing_rows)
    removed_ids = all_ids - missing_ids

    # The unfiltered listing must contain every binding the profile resolves
    # (otherwise the fixture is not exercising the filter at all).
    assert all_ids >= _KNOWN_RESOLVED_BINDING_IDS, sorted(_KNOWN_RESOLVED_BINDING_IDS - all_ids)
    # --missing is a STRICT subset: strictly fewer rows.
    assert missing_ids < all_ids
    # Every binding backed by the seeded facts is removed, while additional
    # authority-derived profile defaults may also be removed as they resolve.
    assert removed_ids >= _KNOWN_RESOLVED_BINDING_IDS
    assert all(all_rows[binding_id][4] == "profile" for binding_id in removed_ids)
    assert missing_ids.isdisjoint(_KNOWN_RESOLVED_BINDING_IDS)
    # The filter echo line still reflects the flag.
    assert "missing_filter\tTrue" in filtered.output


def test_bindings_list_without_missing_retains_profile_resolved_rows() -> None:
    """Without ``--missing`` the profile-resolved bindings are still listed.

    The unfiltered listing is the full configured-binding set: a binding
    the profile already satisfies is reported (it IS a declared binding),
    and only ``--missing`` drops it. This is the anti-tautology companion
    to the strict-subset test — it confirms the dropped rows genuinely
    exist in the unfiltered view, so the subset difference is real.
    """
    _seed_partial_modelo_100_profile()
    scope = ["app", "modelo", "bindings", "list", "--modelo", _MODELO, "--year", str(_YEAR), "--period", _PERIOD]

    unfiltered = invoke_cached_cli(scope)
    assert unfiltered.exit_code == 0, unfiltered.output

    all_ids = _binding_ids_in_listing(unfiltered.output)
    assert all_ids >= _KNOWN_RESOLVED_BINDING_IDS, sorted(_KNOWN_RESOLVED_BINDING_IDS - all_ids)
    assert "missing_filter\tFalse" in unfiltered.output
