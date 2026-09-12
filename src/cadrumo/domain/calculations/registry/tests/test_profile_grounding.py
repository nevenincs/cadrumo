"""Wiring contract for the profile-key reverse grounding index.

Grounded against the bundled validated registry (the authority the
calculation engine itself consumes) — the expectations below quote
grounding the registry TOML declares, never values invented for the test.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core.modelo import Modelo
from ..authority import bundled_authority
from ..binding_value_contract import BindingDataType, BindingValueChannel, BindingValueContract
from ..profile_bindings import ProfileProvider
from ..profile_grounding import ProfileKeyGrounding, binding_profile_keys, build_profile_grounding_index
from ..schema import BindingDefinition

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


def _minimal_profile_binding(selector: dict[str, object]) -> BindingDefinition:
    return BindingDefinition.model_validate(
        {
            "id": "test-profile-binding",
            "provider": {"kind": "profile", **selector},
            "value": {"data_type": "text", "channel": "text"},
            "legal_refs": ("ley-35-2006:art-1",),
            "source_refs": ("aeat-modelo-036-procedure",),
        },
    )


def test_binding_profile_keys_resolves_a_real_hydrated_profile_selector() -> None:
    """The legitimate path: a real ``source = "profile"`` binding's typed selector."""
    binding = _minimal_profile_binding({"profile_key": "tax.id"})
    assert not isinstance(binding.provider, dict)
    assert binding_profile_keys(binding) == ("tax.id",)


def test_binding_profile_keys_ignores_a_non_profile_binding() -> None:
    """A different source family's typed selector never carries a profile key."""
    binding = BindingDefinition.model_validate(
        {
            "id": "test-manual-input-binding",
            "provider": {
                "kind": "manual_input",
                "casilla_id": "0003",
                "data_type": "money",
            },
            "value": {
                "data_type": "money",
                "channel": "decimal",
            },
            "legal_refs": ("ley-35-2006:art-99",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )
    assert binding_profile_keys(binding) == ()


def test_binding_profile_keys_resolves_a_model_construct_bypassed_provider() -> None:
    """The legitimate path for the ``model_construct``-bypassed shape: the
    accessor still reads the declared key off the provider member."""
    drifted = BindingDefinition.model_construct(
        id="test-profile-raw",
        provider=ProfileProvider.model_construct(profile_key="tax.id"),
        value=BindingValueContract(data_type=BindingDataType.TEXT, channel=BindingValueChannel.TEXT),
        legal_refs=("ley-35-2006:art-1",),
        source_refs=("aeat-modelo-036-procedure",),
    )
    assert binding_profile_keys(drifted) == ("tax.id",)


def test_a_profile_binding_with_a_misspelled_selector_key_is_refused_at_construction() -> None:
    """The bite proof: a profile selector key the model does not declare is
    refused where it is written, never read as "no profile key here".

    The refusal moved to a stronger owner. It used to live in this accessor's
    raw-mapping fallback, because a ``source = "profile"`` binding could carry
    an unhydrated selector whose key no longer matched the declared model, and
    a ``mapping.get("profile_key")`` read returned an empty tuple for it. The
    provider union removes the unhydrated shape entirely: ``provider`` is one
    discriminated member, so a key the member does not declare cannot reach
    the accessor at all -- it fails at construction, as asserted here.
    """
    with pytest.raises(ValidationError, match=r"provider\.profile\.profil_key"):
        BindingDefinition.model_validate(
            {
                "id": "test-profile-drift",
                "provider": {"kind": "profile", "profil_key": "tax.id"},
                "value": {"data_type": "text", "channel": "text"},
                "legal_refs": ("ley-35-2006:art-1",),
                "source_refs": ("aeat-modelo-036-procedure",),
            },
        )
