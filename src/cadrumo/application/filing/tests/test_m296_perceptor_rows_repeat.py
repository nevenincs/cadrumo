"""Modelo 296's perceptor record holds every payee, not just the first.

The IRNR annual withholding summary emits its Tipo 2 record once per perceptor. It was
published as a single non-repeating record, so the layout could hold exactly ONE payee: a
296 with two could not be expressed at all, and the forty-four fields of the row were
header producers that nothing resolved, so the one payee it could hold rendered blank.

Both halves are asserted here against the SHIPPED layout, because both are silent failures.
A one-payee ceiling does not raise -- it emits a structurally valid file that under-declares
by however many payees were dropped, which is exactly the failure mode the project forbids.
"""

from __future__ import annotations

import pytest

from ....core import M296PerceptorField
from ....core.resources import resources
from .._m296_projection import build_m296_filing_projection_plan
from .._producer_snapshot import Modelo296PerceptorRow, Modelo296ProfileFacts

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "296"
_REVISION = "2024-y-siguientes"
_PERCEPTOR_RECORD = "m296-perceptor"


def _perceptor_record():
    """Return the shipped snapshot, layout and perceptor record.

    Resolved through the registry authority from (modelo, filing_year, period), never from
    a stored revision id: the revision that applies is a law-determined fact.
    """
    snapshot = resources().modelos.authority.snapshot(_MODELO, filing_year=2024, period="0A", on=None)
    layout = snapshot.revision.export_layouts[0]
    record = next(r for r in layout.records if str(r.id) == _PERCEPTOR_RECORD)
    assert str(snapshot.revision.id) == _REVISION, (
        f"the law-determined revision for 296/2024/0A is {snapshot.revision.id}, not {_REVISION}"
    )
    return snapshot, layout, record


def test_the_shipped_perceptor_record_repeats_its_rows() -> None:
    """Without this the layout physically cannot express a second payee."""
    _snapshot, _layout, record = _perceptor_record()
    assert record.repeat == "projection_rows", (
        "the modelo 296 perceptor record does not repeat, so the layout holds exactly one "
        "perceptor and every payee after the first is dropped from a filed return"
    )


def test_every_perceptor_field_is_a_projection_of_the_row() -> None:
    """No perceptor field may remain a header producer.

    A header producer on this record is a per-payee value read from a single declaration-wide
    header, which is either blank or the same wrong value on every row.
    """
    _snapshot, _layout, record = _perceptor_record()
    header_fields = sorted(str(field.id) for field in record.fields if field.producer_key is not None)
    assert header_fields == [], f"perceptor fields still resolved as declaration headers: {header_fields}"

    projected = {field.projection_ref.field for field in record.fields if field.projection_ref is not None}
    assert projected == set(M296PerceptorField), (
        "the shipped record does not project exactly the perceptor field set: "
        f"missing {sorted(f.value for f in set(M296PerceptorField) - projected)}, "
        f"extra {sorted(f.value for f in projected - set(M296PerceptorField))}"
    )


class _ProducerSnapshot:
    """The one attribute the plan builder reads.

    A real :class:`FilingProducerSnapshot` additionally requires a full taxpayer identity,
    presenter and election set, none of which say anything about whether the perceptor
    record repeats. The REGISTRY snapshot is the real one, because the render context
    validates that the layout and record are snapshot-owned.
    """

    def __init__(self, model_profile: object) -> None:
        self.model_profile = model_profile


def _profile(count: int) -> Modelo296ProfileFacts:
    """A declarante carrying ``count`` distinguishable payees."""
    return Modelo296ProfileFacts(
        ejercicio="2024",
        nif_del_declarante="B12345678",
        apellidos_y_nombre_o_razon_social_del="EMPRESA PAGADORA SL",
        perceptor_rows=tuple(
            Modelo296PerceptorRow(nif_del_perceptor=f"X{index:07d}", base_retenciones_e_ingresos_a_cuenta=f"{index}00")
            for index in range(1, count + 1)
        ),
    )


@pytest.mark.parametrize("payees", [1, 2, 7])
def test_one_occurrence_is_emitted_per_payee(payees: int) -> None:
    """Occurrence depth is the number of payees, with no ceiling anywhere."""
    snapshot, layout, record = _perceptor_record()
    plan = build_m296_filing_projection_plan(
        registry_snapshot=snapshot,
        layout=layout,
        producer_snapshot=_ProducerSnapshot(_profile(payees)),
    )
    occurrences = sorted(context.occurrence for context in plan.contexts if context.record is record)
    assert occurrences == list(range(1, payees + 1))


def test_each_payee_keeps_its_own_values() -> None:
    """The anti-tautology half: equal occurrence COUNT proves nothing on its own.

    A builder that emitted N occurrences all carrying payee one's values would satisfy the
    count assertion above while still under-declaring every payee after the first -- and the
    emitted file would be structurally valid, so nothing downstream would object.
    """
    snapshot, layout, _record = _perceptor_record()
    plan = build_m296_filing_projection_plan(
        registry_snapshot=snapshot,
        layout=layout,
        producer_snapshot=_ProducerSnapshot(_profile(3)),
    )
    by_occurrence = {
        value.occurrence: value.value
        for value in plan.values
        if value.projection_ref.field is M296PerceptorField.NIF_DEL_PERCEPTOR
    }
    assert by_occurrence == {1: "X0000001", 2: "X0000002", 3: "X0000003"}


def test_a_declaration_with_no_payees_emits_no_perceptor_row() -> None:
    """An absent row is not a blank row; whether the absence is admissible is the record's
    own required flag, which is the renderer's question rather than the plan's."""
    snapshot, layout, _record = _perceptor_record()
    plan = build_m296_filing_projection_plan(
        registry_snapshot=snapshot,
        layout=layout,
        producer_snapshot=_ProducerSnapshot(_profile(0)),
    )
    assert plan.contexts == ()
    assert plan.values == ()
