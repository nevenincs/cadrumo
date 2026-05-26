"""Calculation revision identity contract tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._calculation_revision import derive_calculation_revision_id

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _base_id() -> str:
    return derive_calculation_revision_id(
        work_unit_id="a" * 64,
        inputs_snapshot={"001": "10.00"},
        binding_overrides={},
        casilla_values={"002": Decimal("15.00")},
    )


def test_revision_id_is_stable_across_equal_inputs() -> None:
    """Same inputs must always yield the same id (content-addressing contract)."""
    first = _base_id()
    second = _base_id()
    assert first == second
    assert len(first) == 64
    assert first == first.lower()


def test_revision_id_pinned_against_fully_populated_fixture() -> None:
    """Anti-tautology proof: pin the exact SHA-256 for a fully-populated
    derivation against a known-good hex string.

    Staged for linkage P02.S09 (the planned collapse of
    ``CalculationRevision.casilla_values`` into a derived ``@property``
    over the typed ``observations`` envelope). The collapse must
    preserve the hash domain — every already-persisted revision id
    must still derive identically after the field-shape change, or
    every catalogue row gets a phantom mismatch and the
    content-addressing contract breaks.

    The fixture sets every defaultable parameter to a non-default
    value so the pin exercises every branch of the hash payload:
    inputs, overrides, outputs, source_transaction_ids,
    borrador_snapshot_id, and bindings_sourced_from_borrador.

    Update procedure: if a future change to the hash domain is
    explicitly intended (e.g. a migration-bumping schema rev), update
    the pinned hex in tandem with the change and document the
    migration. If this test fails without an explicit hash-domain
    change, the regression is in the hash derivation itself.
    """
    pinned = "5b78dd04e614a50fe448439b7fdb843f1e31afe76f9d424d0276866679dee7ca"
    derived = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        inputs_snapshot={"01": "1000.00", "02": "250.00", "03": "50.00"},
        binding_overrides={
            "previous_year_net_income": "13000.00",
            "profile.iva_regime": "GENERAL",
        },
        casilla_values={
            "04": Decimal("1300.00"),
            "07": Decimal("-50.50"),
            "19": Decimal("200.25"),
        },
        source_transaction_ids=("a" * 64, "c" * 64),
        borrador_snapshot_id="borrador-2026-q1-snapshot",
        bindings_sourced_from_borrador=(
            "iva.aggregation",
            "renta.expense.aggregation",
        ),
    )
    assert derived == pinned, (
        f"Hash domain shifted — derive_calculation_revision_id returned "
        f"{derived!r} for a fully-populated fixture but the pinned value "
        f"is {pinned!r}. Every persisted CalculationRevision id now mismatches "
        f"its derived form; either revert the hash change or run a migration "
        f"and update the pin."
    )


def test_revision_id_changes_when_input_casilla_value_changes() -> None:
    """A different inputs_snapshot must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        inputs_snapshot={"001": "10.00"},
        binding_overrides={},
        casilla_values={"002": Decimal("15.00")},
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        inputs_snapshot={"001": "99.00"},  # changed
        binding_overrides={},
        casilla_values={"002": Decimal("15.00")},
    )
    assert id_a != id_b


def test_revision_id_changes_when_output_casilla_value_changes() -> None:
    """A different casilla_values mapping must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        inputs_snapshot={"001": "10.00"},
        binding_overrides={},
        casilla_values={"002": Decimal("15.00")},
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        inputs_snapshot={"001": "10.00"},
        binding_overrides={},
        casilla_values={"002": Decimal("16.00")},  # changed
    )
    assert id_a != id_b


def test_revision_id_changes_when_work_unit_id_changes() -> None:
    """A different parent work_unit_id must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        inputs_snapshot={"001": "10.00"},
        binding_overrides={},
        casilla_values={"002": Decimal("15.00")},
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        inputs_snapshot={"001": "10.00"},
        binding_overrides={},
        casilla_values={"002": Decimal("15.00")},
    )
    assert id_a != id_b


def test_revision_id_is_insensitive_to_dict_key_insertion_order() -> None:
    """Dict key ordering must not affect the derived id (sort_keys guarantee)."""
    id_ordered = derive_calculation_revision_id(
        work_unit_id="c" * 64,
        inputs_snapshot={"001": "1.00", "002": "2.00"},
        binding_overrides={},
        casilla_values={"010": Decimal("5.00"), "020": Decimal("6.00")},
    )
    id_reversed = derive_calculation_revision_id(
        work_unit_id="c" * 64,
        inputs_snapshot={"002": "2.00", "001": "1.00"},
        binding_overrides={},
        casilla_values={"020": Decimal("6.00"), "010": Decimal("5.00")},
    )
    assert id_ordered == id_reversed


def test_revision_id_includes_present_borrador_metadata() -> None:
    """Adding borrador metadata to otherwise-identical inputs must change the id."""
    base = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        inputs_snapshot={"001": "10.00"},
        binding_overrides={},
        casilla_values={"002": Decimal("15.00")},
    )
    with_borrador = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        inputs_snapshot={"001": "10.00"},
        binding_overrides={},
        casilla_values={"002": Decimal("15.00")},
        borrador_snapshot_id="snapshot-100-2025",
        bindings_sourced_from_borrador=("casilla_001",),
    )

    assert with_borrador != base
