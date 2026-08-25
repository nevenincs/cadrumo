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

from ....domain.user_profile.values import UserProfileFact
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import set_active_test_profile_facts
from ._strict_cli_fixture_support import binding_isolated_backend

__all__ = ["binding_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Modelo 100 (IRPF) 2025 declares formula-consumed ``source = "profile"``
# bindings. The partial profile below satisfies the explicit facts for
# tax-residence CCAA, declaration type, taxpayer birth date, and
# minor-children-in-unit count. The real profile resolver also derives neutral
# defaults for the anualidades eligibility and Madrid nacimiento/adopción
# operands. The remaining profile bindings (spouse, descendants, marriage
# deltas, ...) and every non-profile binding (ledger aggregations,
# prior-filing pulls) stay unresolved, i.e. still "missing".
_MODELO = "100"
_YEAR = 2025
_PERIOD = "0A"
_RESOLVED_BINDING_IDS = frozenset(
    {
        "renta-2025-profile-tax-residence-ccaa",
        "renta-2025-profile-declaration-type",
        "renta-2025-profile-taxpayer-birth-date",
        "renta-2025-profile-family-minor-children-in-unit",
        "renta-2025-profile-has-economic-activity",
        "renta-2025-profile-anualidades-sin-minimo-descendientes",
        "renta-2025-profile-madrid-nacimiento-adopcion-eligible-count",
        "renta-2025-profile-unidad-familiar-otros-miembros-base",
        "renta-2025-profile-minimo-descendientes-estatal",
        "renta-2025-profile-minimo-descendientes-autonomico",
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


def _binding_ids_in_listing(output: str) -> set[str]:
    """Extract the binding ids from a ``bindings list`` text envelope.

    Each binding row is tab-separated as
    ``modelo<TAB>revision<TAB>period<TAB>binding_id<TAB>source<TAB>...``;
    the binding id is the fourth column. Header / metadata lines (which
    have a different leading token) carry no registry binding id, so a row
    qualifies only when its fourth column looks like a binding id.
    """
    ids: set[str] = set()
    for line in output.splitlines():
        columns = line.split("\t")
        if len(columns) < 5:
            continue
        if columns[0] == _MODELO:
            ids.add(columns[3])
    return ids


def test_bindings_list_missing_returns_strict_subset_of_unfiltered() -> None:
    """``--missing`` removes EXACTLY the profile-resolved bindings.

    With an active profile that satisfies a proper subset of Modelo 100's
    ``source = "profile"`` bindings, the ``--missing`` listing must be a
    strict subset of the unfiltered listing whose removed rows are exactly
    those resolved binding ids — proving the filter actually narrows the
    set rather than echoing the flag while returning everything.
    """
    _seed_partial_modelo_100_profile()
    scope = ["app", "modelo", "bindings", "list", "--modelo", _MODELO, "--year", str(_YEAR), "--period", _PERIOD]

    unfiltered = invoke_cached_cli(scope)
    assert unfiltered.exit_code == 0, unfiltered.output
    filtered = invoke_cached_cli([*scope, "--missing"])
    assert filtered.exit_code == 0, filtered.output

    all_ids = _binding_ids_in_listing(unfiltered.output)
    missing_ids = _binding_ids_in_listing(filtered.output)

    # The unfiltered listing must contain every binding the profile resolves
    # (otherwise the fixture is not exercising the filter at all).
    assert all_ids >= _RESOLVED_BINDING_IDS, sorted(_RESOLVED_BINDING_IDS - all_ids)
    # --missing is a STRICT subset: strictly fewer rows.
    assert missing_ids < all_ids
    # The removed rows are EXACTLY the profile-resolved bindings.
    assert all_ids - missing_ids == _RESOLVED_BINDING_IDS
    # None of the profile-resolved bindings survive the filter.
    assert missing_ids.isdisjoint(_RESOLVED_BINDING_IDS)
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
    assert all_ids >= _RESOLVED_BINDING_IDS, sorted(_RESOLVED_BINDING_IDS - all_ids)
    assert "missing_filter\tFalse" in unfiltered.output
