"""Wiring contract for the profile-key reverse grounding index.

Grounded against the bundled validated registry (the authority the
calculation engine itself consumes) — the expectations below quote
grounding the registry TOML declares, never values invented for the test.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.profile_grounding import (
    ProfileKeyGrounding,
    binding_profile_keys,
    build_profile_grounding_index,
)
from cadrumo.domain.calculations.registry.schema import DataBindingDefinition

from .....core import BindingSourceKind, Modelo
from ..authority import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def index() -> dict[str, ProfileKeyGrounding]:
    return dict(build_profile_grounding_index(bundled_authority()))


def test_index_inverts_the_censo_status_binding(index: dict[str, ProfileKeyGrounding]) -> None:
    """The M036 censo-status binding's declared grounding survives inversion intact."""
    grounding = index["censo.status"]
    assert Modelo.M036 in grounding.modelos
    assert "rd-1065-2007:art-9" in grounding.legal_refs
    assert "orden-eha-1274-2007:art-1" in grounding.legal_refs
    assert "aeat-modelo-036-procedure" in grounding.source_refs


def test_every_entry_is_sorted_union_shape(index: dict[str, ProfileKeyGrounding]) -> None:
    """Entries are deterministic: sorted keys, sorted tuple unions, no empties."""
    assert list(index) == sorted(index)
    for key, grounding in index.items():
        assert grounding.profile_key == key
        assert grounding.modelos, key
        assert list(grounding.legal_refs) == sorted(set(grounding.legal_refs))
        assert list(grounding.source_refs) == sorted(set(grounding.source_refs))


def test_unconsumed_keys_are_absent_not_empty(index: dict[str, ProfileKeyGrounding]) -> None:
    """A key no profile binding consumes renders no legal zone — absent, never invented."""
    assert "identity.notes" not in index
    assert all(grounding.legal_refs or grounding.source_refs for grounding in index.values())


def test_index_spans_multiple_modelos(index: dict[str, ProfileKeyGrounding]) -> None:
    """Profile bindings exist across several modelos, not only M036."""
    consuming = {modelo for grounding in index.values() for modelo in grounding.modelos}
    assert len(consuming) >= 3
    assert Modelo.M036 in consuming


def _minimal_profile_binding(selector: dict[str, object]) -> DataBindingDefinition:
    return DataBindingDefinition.model_validate(
        {
            "id": "test-profile-binding",
            "source": "profile",
            "selector": selector,
            "legal_refs": ("ley-35-2006:art-1",),
            "source_refs": ("aeat-modelo-036-procedure",),
        },
    )


def test_binding_profile_keys_resolves_a_real_hydrated_profile_selector() -> None:
    """The legitimate path: a real ``source = "profile"`` binding's typed selector."""
    binding = _minimal_profile_binding({"profile_key": "tax.id"})
    assert not isinstance(binding.selector, dict)
    assert binding_profile_keys(binding) == ("tax.id",)


def test_binding_profile_keys_ignores_a_non_profile_binding() -> None:
    """A different source family's typed selector never carries a profile key."""
    binding = DataBindingDefinition.model_validate(
        {
            "id": "test-manual-input-binding",
            "source": "manual_input",
            "selector": {"casilla_id": "0003", "data_type": "money"},
            "legal_refs": ("ley-35-2006:art-99",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )
    assert binding_profile_keys(binding) == ()


def test_binding_profile_keys_resolves_an_unhydrated_but_well_formed_selector() -> None:
    """The legitimate path for the ``model_construct``-bypassed shape: re-validation
    through ``ProfileSelector`` still resolves a well-formed raw selector."""
    drifted = DataBindingDefinition.model_construct(
        id="test-profile-raw",
        source=BindingSourceKind.PROFILE,
        selector={"profile_key": "tax.id"},
        legal_refs=("ley-35-2006:art-1",),
        source_refs=("aeat-modelo-036-procedure",),
    )
    assert binding_profile_keys(drifted) == ("tax.id",)


def test_a_profile_binding_with_a_renamed_selector_key_is_refused_not_silently_dropped() -> None:
    """The bite proof: an un-hydrated ``source = "profile"`` selector whose key
    does not match ``ProfileSelector``'s declared field names must be refused,
    not silently read as "no profile key here".

    Every real ``source = "profile"`` binding is hydrated into ``ProfileSelector``
    at construction time (``DataBindingDefinition``'s discriminated-union field
    validator), so this residual risk is a selector that bypassed that hydration
    (``model_construct``) with a key that no longer matches the declared model --
    standing in for a rename of ``ProfileSelector.profile_key``. Before the fix,
    the raw-dict fallback read ``mapping.get("profile_key")`` by string literal
    and silently returned an empty tuple; the fix re-validates through the
    declared model and fails loud instead.
    """
    drifted = DataBindingDefinition.model_construct(
        id="test-profile-drift",
        source=BindingSourceKind.PROFILE,
        selector={"profil_key": "tax.id"},  # deliberate typo of profile_key
        legal_refs=("ley-35-2006:art-1",),
        source_refs=("aeat-modelo-036-procedure",),
    )
    with pytest.raises(RegistryValidationError, match="malformed profile selector"):
        binding_profile_keys(drifted)
