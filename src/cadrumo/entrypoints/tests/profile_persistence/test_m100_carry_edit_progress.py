"""Answering a Modelo 100's earlier-ejercicio carries always moves the declaration forward.

The four carries of the negative general bases still pending (Ley 35/2006
art. 50.3) are read from the previous return; with none held, each one needs
the filer's answer before the declaration calculates. An Apply that answers
them all calculates. One that answers only some is refused, and the refusal
names a carry the filer has not answered yet, so the door the window opens on
it leads to a box still open: answering it never brings back the same
refusal, and once every carry is answered the Apply goes through.

Real behaviour throughout: an isolated encrypted profile with the year's
Modelo 130 instalments stored, the bundled authority, the production
admission and edit executor.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....application.modelo import edit_operation
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditDomainRefusalV1,
    ModeloEditRefusalV1,
    ModeloEditScalarAddressV1,
)
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .observation_seeding_support import save_stamped_observation
from .test_m100_carry_attestation import _FACTS, _PENDING_CARRIES, _carry_fields, _form, _renta_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_QUARTERS = ("1T", "2T", "3T", "4T")


def _zero(binding_id: BindingId) -> ModeloBindingEditIntentV1:
    return ModeloBindingEditIntentV1(
        address=ModeloEditBindingAddressV1(binding_id=binding_id),
        kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
        value=Decimal("0"),
    )


def _store_instalments(year: int) -> None:
    """Store the year's four Modelo 130 instalments, as an autónomo who filed them holds them."""
    for quarter in _QUARTERS:
        save_stamped_observation(
            CalculationObservationRepository(),
            registry_grounded_modelo_observation(
                modelo="130",
                filing_year=year,
                period=quarter,
                casilla_values={"18": Decimal("0"), "19": Decimal("10.13")},
            ),
            source_kind="app_filing",
        )


def _refused_box(work: SeededOperatorWork, answered: tuple[BindingId, ...], monkeypatch: pytest.MonkeyPatch) -> str:
    """Apply ``answered`` and return the box the typed refusal names; fail if the Apply goes through."""
    typed: list[ModeloEditRefusalV1] = []
    raise_refusal = edit_operation.modelo_edit_refusal_error

    def keep(refusal: ModeloEditRefusalV1) -> Exception:
        typed.append(refusal)
        return raise_refusal(refusal)

    monkeypatch.setattr(edit_operation, "modelo_edit_refusal_error", keep)
    applied = work.apply(binding=tuple(_zero(binding_id) for binding_id in answered))
    monkeypatch.setattr(edit_operation, "modelo_edit_refusal_error", raise_refusal)
    assert applied.refusal is not None, answered
    (refusal,) = typed
    assert isinstance(refusal, ModeloEditDomainRefusalV1)
    assert "calculation_source_unresolved" in refusal.facts
    assert isinstance(refusal.address, ModeloEditScalarAddressV1)
    return refusal.address.casilla_id


@pytest.mark.parametrize("year", _renta_years())
def test_each_refused_answer_names_a_carry_still_open_until_all_are_answered(
    tmp_path: Path, year: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=_FACTS) as renta,
    ):
        _store_instalments(year)
        box_of = {binding_id: field.box for binding_id, field in _carry_fields(_form(renta, OutputLanguage.EN)).items()}
        carry_of = {box: binding_id for binding_id, box in box_of.items()}
        # ANTI-VACUITY: the form shows a box for every carry, so each door has somewhere to go.
        assert set(box_of) == set(_PENDING_CARRIES)

        answered: list[BindingId] = [_PENDING_CARRIES[0]]
        named: list[str] = []
        while len(answered) < len(_PENDING_CARRIES):
            box = _refused_box(renta, tuple(answered), monkeypatch)
            # The refusal names a box the filer has not answered, never one already staged.
            assert box in carry_of, box
            assert carry_of[box] not in answered, (box, answered)
            named.append(box)
            answered.append(carry_of[box])

        # Every carry answered, by following the doors alone: the Apply calculates.
        applied = renta.apply(binding=tuple(_zero(binding_id) for binding_id in answered))
        assert applied.refusal is None, named
        assert len(set(named)) == len(_PENDING_CARRIES) - 1
