"""Gate tests for :class:`cadrumo.core.Modelo`.

These tests bind the canonical :class:`Modelo` StrEnum to the registry authority
and the domain-level shape validator, ensuring the enum cannot drift from the
registry directory listing silently.
"""

from __future__ import annotations

import pytest

from ...domain.calculations.registry.authority import bundled_authority
from .. import NON_REGISTRY_MODELOS, Modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_modelo_registry_backed_members_match_registry() -> None:
    """The registry-backed :class:`Modelo` members are exactly the registry codes.

    Uses the real registry via
    :func:`cadrumo.application.modelo.registry_discovery.registry_modelo_codes`
    (no mocks).  The enum is the full identifier taxonomy; subtracting the
    documented :data:`NON_REGISTRY_MODELOS` (retired codes with no registry
    definition, e.g. M037) must leave exactly the registry directory listing.
    A discrepancy means the enum and the registry tree have drifted and must be
    reconciled — the registry is the authority for its members.

    Note: registry-backed tests can flake under ``pytest -n`` due to a
    loader-cache race (see aeat-local-execution rule).  If this test fails under
    parallel execution, re-run sequentially (``-p no:xdist``) before concluding
    it is a real regression.
    """
    from ...application.modelo.registry_discovery import registry_modelo_codes

    registry_set = set(registry_modelo_codes())
    enum_set = {m.value for m in Modelo}
    non_registry = {m.value for m in NON_REGISTRY_MODELOS}

    assert enum_set - non_registry == registry_set, (
        f"Modelo registry-backed members are out of sync with the registry.\n"
        f"  In enum (registry-backed) but not registry: {sorted((enum_set - non_registry) - registry_set)}\n"
        f"  In registry but not enum: {sorted(registry_set - enum_set)}"
    )
    assert non_registry.isdisjoint(registry_set), (
        f"NON_REGISTRY_MODELOS unexpectedly present in the registry: {sorted(non_registry & registry_set)}"
    )


def test_non_registry_modelos_are_not_registry_loadable() -> None:
    """Every :data:`NON_REGISTRY_MODELOS` member is deliberately absent from the registry.

    Binds the carve-out to its invariant: a retired code (M037) carried by the
    enum must still raise from ``validate_modelo`` — adding a registry TOML for
    it (reviving active support) would break this test.
    """
    from ...domain.calculations.registry.errors import RegistrySnapshotError

    authority = bundled_authority()
    assert NON_REGISTRY_MODELOS, "expected at least the retired M037 carve-out"
    for member in NON_REGISTRY_MODELOS:
        with pytest.raises(RegistrySnapshotError):
            authority.validate_modelo(member.value)


def test_non_registry_modelos_have_no_registry_source_paths() -> None:
    """Known non-registry modelos must not appear as authoritative registry TOML."""

    from ..resources import bundled_path

    modelos_dir = bundled_path("registry", "aeat", "modelos")
    offenders = [
        member.value
        for member in NON_REGISTRY_MODELOS
        if (modelos_dir / f"{member.value}.toml").exists() or (modelos_dir / member.value / "manifest.toml").exists()
    ]

    assert offenders == [], f"NON_REGISTRY_MODELOS have registry sources: {offenders}"


def test_modelo_members_are_valid_modelo_codes() -> None:
    """Every :class:`Modelo` value passes the :class:`~ModeloCode` shape validator."""
    from ...domain.modelos.codes import ModeloCode

    for member in Modelo:
        result = ModeloCode(member.value)
        assert result == member.value, f"ModeloCode({member.value!r}) returned {result!r}; expected {member.value!r}"


def test_modelo_values_are_three_digit() -> None:
    """Every :class:`Modelo` value is a three-character ASCII digit string."""
    for member in Modelo:
        assert len(member.value) == 3, f"{member.name}.value {member.value!r} is not three characters"
        assert member.value.isdigit(), f"{member.name}.value {member.value!r} contains non-digit characters"
