"""Gate tests for :class:`aeat.core._modelo.Modelo`.

These tests bind the canonical :class:`Modelo` StrEnum to the registry authority
and the domain-level shape validator, ensuring the enum cannot drift from the
registry directory listing silently.
"""

from __future__ import annotations

import pytest

from .._modelo import Modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_modelo_set_matches_registry() -> None:
    """The :class:`Modelo` member set is exactly the set of registry modelo codes.

    Uses the real registry via :func:`aeat.application.modelo.registry_modelo_codes`
    (no mocks).  A discrepancy means the enum and the registry directory tree are
    out of sync and must be reconciled — the registry is the authority.

    Note: registry-backed tests can flake under ``pytest -n`` due to a
    loader-cache race (see aeat-local-execution rule).  If this test fails under
    parallel execution, re-run sequentially (``-p no:xdist``) before concluding
    it is a real regression.
    """
    from aeat.application.modelo import registry_modelo_codes

    registry_set = set(registry_modelo_codes())
    enum_set = {m.value for m in Modelo}

    assert enum_set == registry_set, (
        f"Modelo enum is out of sync with the registry.\n"
        f"  In enum but not registry: {sorted(enum_set - registry_set)}\n"
        f"  In registry but not enum: {sorted(registry_set - enum_set)}"
    )


def test_modelo_members_are_valid_modelo_codes() -> None:
    """Every :class:`Modelo` value passes the :class:`~aeat.domain.modelos.ModeloCode` shape validator."""
    from aeat.domain.modelos import ModeloCode

    for member in Modelo:
        result = ModeloCode(member.value)
        assert result == member.value, (
            f"ModeloCode({member.value!r}) returned {result!r}; "
            f"expected {member.value!r}"
        )


def test_modelo_values_are_three_digit() -> None:
    """Every :class:`Modelo` value is a three-character ASCII digit string."""
    for member in Modelo:
        assert len(member.value) == 3, (
            f"{member.name}.value {member.value!r} is not three characters"
        )
        assert member.value.isdigit(), (
            f"{member.name}.value {member.value!r} contains non-digit characters"
        )
