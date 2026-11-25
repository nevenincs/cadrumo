"""Modelo 390 apartado 12 boxes 114 to 118 read their facts from the prorrata register rows.

Each activity row of the register fills the CNAE code, the volume of
operations, the volume with the right to deduct, the kind of prorrata and the
definitive percentage of its own slot. A CNAE code travels as text so its
leading zero survives. A register that records no prorrata leaves every box
absent rather than zero, an empty slot stays absent, and a register whose
applicable year lacks a row is reported as a gap instead of being filled.

Real behaviour: the published Modelo 390 revision and the real resolver over a
real typed register; the register store is a one-method in-memory reader.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.core.prorrata_register import (
    ProrrataActivityRowType,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_grade_exercises
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....core.secure_object_write import SecureObjectWrite
from ....domain.prorrata_register.register import ProrrataActivityRow, ProrrataRegister, ProrrataRegisterEntry
from ..prorrata_register_activity import ProrrataRegisterActivitySourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

YEAR = filing_grade_exercises("390")[-1]
_FACTS = ("codigo-cnae", "importe-operaciones", "importe-con-derecho", "tipo", "porcentaje")
_SLOTS = range(1, 6)


def _binding(slot: int, fact: str) -> str:
    return f"modelo-390-prorrata-actividad-{slot}-{fact}"


_ALL_BINDINGS = frozenset(_binding(slot, fact) for slot in _SLOTS for fact in _FACTS)


class _Register:
    """An in-memory register store; this resolver only reads it."""

    def __init__(self, register: ProrrataRegister) -> None:
        self.register = register

    @property
    def bucket_id(self) -> str:
        return "operator"

    def load(self) -> ProrrataRegister:
        return self.register

    def load_revisioned(self) -> tuple[ProrrataRegister, str]:
        return self.register, "test-revision"

    def to_secure_object_write(
        self,
        register: ProrrataRegister,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        del register, expected_revision_id
        raise AssertionError("the prorrata activity resolver never writes the register")


def _row(slot: int, *, cnae: str, total: str, con_derecho: str, kind: str, percentage: str) -> ProrrataActivityRow:
    return ProrrataActivityRow(
        ejercicio=YEAR,
        activity_id=f"activity-{slot}",
        slot=slot,
        cnae_code=cnae,
        operaciones_total=Decimal(total),
        operaciones_con_derecho=Decimal(con_derecho),
        prorrata_type=ProrrataActivityRowType(kind),
        percentage=Decimal(percentage),
        evidence_reference=f"operator-evidence:activity-{slot}",
    )


def _general_entry() -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=YEAR,
        regime=ProrrataRegisterRegime.from_registry("general"),
        especial_transition=None,
        provisional_percentage=Decimal("80"),
        provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
        source_observation_ref=f"prorrata-register:{YEAR - 1}",
        source_registry_snapshot_refs=(published_snapshot("303", filing_year=YEAR - 1, period="4T").snapshot_ref,),
    )


def _resolve(register: ProrrataRegister | None) -> CalculationSourceResolution:
    context = CalculationSourceContext(
        bucket_id="operator",
        modelo="390",
        filing_year=YEAR,
        period=Period.from_year_and_code(YEAR, "0A"),
        revision=published_snapshot("390", filing_year=YEAR, period="0A").revision,
    )
    repository = None if register is None else _Register(register)
    return ProrrataRegisterActivitySourceResolver(prorrata_register_repository=repository).resolve(context)


def test_each_box_reads_its_own_row_fact_and_the_cnae_keeps_its_leading_zero() -> None:
    dental = _row(1, cnae="0113", total="72650.00", con_derecho="0.00", kind="G", percentage="0")
    shop = _row(2, cnae="4711", total="1000.00", con_derecho="800.00", kind="E", percentage="80")
    resolution = _resolve(ProrrataRegister(activity_rows=(shop, dental)))

    assert dict(resolution.enum_binding_values) == {
        _binding(1, "codigo-cnae"): "0113",
        _binding(1, "tipo"): "G",
        _binding(2, "codigo-cnae"): "4711",
        _binding(2, "tipo"): "E",
    }
    assert dict(resolution.binding_values) == {
        _binding(1, "importe-operaciones"): Decimal("72650.00"),
        _binding(1, "importe-con-derecho"): Decimal("0.00"),
        _binding(1, "porcentaje"): Decimal("0"),
        _binding(2, "importe-operaciones"): Decimal("1000.00"),
        _binding(2, "importe-con-derecho"): Decimal("800.00"),
        _binding(2, "porcentaje"): Decimal("80"),
    }
    empty_slots = {_binding(slot, fact) for slot in (3, 4, 5) for fact in _FACTS}
    assert set(resolution.unresolved_binding_ids) == empty_slots
    assert set(resolution.inapplicable_binding_ids) == empty_slots
    assert resolution.diagnostics == ()
    assert {row.contributor_source_kind for row in resolution.provenance} == {
        BindingSourceKind.PRORRATA_REGISTER_ACTIVITY.value
    }
    assert len(resolution.provenance) == 2


def test_a_register_without_prorrata_leaves_every_box_absent_not_zero() -> None:
    resolution = _resolve(ProrrataRegister())

    assert dict(resolution.binding_values) == {}
    assert dict(resolution.enum_binding_values) == {}
    assert set(resolution.unresolved_binding_ids) == _ALL_BINDINGS
    assert set(resolution.inapplicable_binding_ids) == _ALL_BINDINGS
    assert resolution.diagnostics == ()


def test_an_applicable_year_missing_rows_is_a_reported_gap_not_a_partial_fill() -> None:
    one_row = _row(1, cnae="4711", total="1000.00", con_derecho="800.00", kind="G", percentage="80")
    resolution = _resolve(ProrrataRegister(entries=(_general_entry(),), activity_rows=(one_row,)))

    assert dict(resolution.binding_values) == {}
    assert dict(resolution.enum_binding_values) == {}
    assert set(resolution.unresolved_binding_ids) == _ALL_BINDINGS
    assert resolution.inapplicable_binding_ids == ()
    (diagnostic,) = resolution.diagnostics
    assert diagnostic.reason == "unresolved_binding"
    assert "activity_rows_incomplete" in diagnostic.message


def test_no_register_store_refuses_every_box() -> None:
    resolution = _resolve(None)

    assert dict(resolution.binding_values) == {}
    assert set(resolution.unresolved_binding_ids) == _ALL_BINDINGS
    (diagnostic,) = resolution.diagnostics
    assert "storage_unavailable" in diagnostic.message
