"""The runtime subview projects the profile bindings that carry an export address.

The export header composer needs the registry's own declarations to populate the
identity slots AEAT's dictionary names. Without them the join is hand-written per
field, which is what the two escapes in the XML renderer and the four hardcoded
paths in ``_operator_name_facts`` currently are.

The projection is deliberately narrow. A subview carrying every binding for every
source kind would stop being a projection and become a second snapshot beside the
registry authority, so only bindings that declare a ``dictionary_field`` -- the
thing that gives a binding somewhere to land on the exported record -- are
projected.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....tests.registry_tree import bundled_registry_tree
from ..runtime import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _modelo_100_bindings(filing_year: int):
    provider = build_runtime_schema_provider(
        modelos=("100",),
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "0A"),
    )
    return provider.get_subview("100").profile_export_bindings


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_every_projected_binding_declares_an_export_address(filing_year: int) -> None:
    """The discriminator holds: nothing lands here without somewhere to land."""
    for binding in _modelo_100_bindings(filing_year):
        assert getattr(binding.selector, "dictionary_field", None), binding.id


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_the_projection_is_narrower_than_the_revision_binding_set(filing_year: int) -> None:
    """It is a projection, not a second snapshot.

    If this ever stops holding, the subview has begun carrying the registry's
    binding set wholesale and the authority boundary has been crossed.
    """
    projected = _modelo_100_bindings(filing_year)
    modelos, _catalogues = bundled_registry_tree()
    revision = next(m for m in modelos if m.id == "100").revisions[str(filing_year)]

    assert 0 < len(projected) < len(revision.bindings), filing_year


def test_a_fixed_width_modelo_projects_nothing() -> None:
    """Modelo 303 has no dictionary-addressed profile bindings, so none are carried.

    Keeps the projection honest: a discriminator that matched everything would
    make the assertions above vacuous.
    """
    provider = build_runtime_schema_provider(modelos=("303",))

    assert provider.get_subview("303").profile_export_bindings == ()


def test_the_identity_fields_the_export_needs_are_reachable() -> None:
    """The fields the renderer hardcodes today are present in the declarations.

    ``DPNIF_D`` and ``DP_APENOM_D`` are the two the XML renderer special-cases.
    Their presence here is what makes replacing those escapes a join rather than
    a relocation of the same hardcoding.
    """
    addressed = {str(binding.selector.dictionary_field) for binding in _modelo_100_bindings(2024)}

    assert {"DPNIF_D", "DP_APENOM_D"} <= addressed


def test_the_projection_is_ordered_deterministically() -> None:
    """Two reads of the same revision agree, so a consumer cannot depend on luck."""
    assert [binding.id for binding in _modelo_100_bindings(2024)] == [
        binding.id for binding in _modelo_100_bindings(2024)
    ]
    assert [binding.id for binding in _modelo_100_bindings(2024)] == sorted(
        binding.id for binding in _modelo_100_bindings(2024)
    )
