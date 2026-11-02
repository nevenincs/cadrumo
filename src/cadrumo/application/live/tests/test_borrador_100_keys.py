"""The borrador key contract over the published Modelo 100 bound-casilla map."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ..borrador_100_keys import borrador_admitted_bindings, project_printed_casillas
from ..errors import LiveApplicationInputError

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_application]

# In the 2023 revision casilla 0596 is bound to the work-certificate binding, the
# one binding marked prefilled by AEAT; 0505 is a computed casilla.
_CERTIFICATE: BindingId = "renta-certificado-trabajo-retenciones"
_UNMARKED: BindingId = "renta-profile-minimo-descendientes-estatal"
_BOUND_CASILLA: CasillaId = "0596"
_COMPUTED_CASILLA: CasillaId = "0505"


def _revision() -> ModeloRevision:
    return published_snapshot("100", filing_year=2023, period="0A").revision


def _admit(revision: ModeloRevision, binding_id: BindingId) -> ModeloRevision:
    """Mark one more binding prefilled by AEAT, as a revision could declare it."""
    return revision.model_copy(
        update={
            "bindings": tuple(
                binding.model_copy(update={"aeat_prefilled": True}) if binding.id == binding_id else binding
                for binding in revision.bindings
            )
        }
    )


def _rebind(revision: ModeloRevision, casilla_id: CasillaId, **fields: object) -> ModeloRevision:
    return revision.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(update=fields) if casilla.id == casilla_id else casilla
                for casilla in revision.casillas
            )
        }
    )


def test_published_revision_admits_only_the_bindings_marked_prefilled() -> None:
    assert tuple(borrador_admitted_bindings(_revision())) == (_CERTIFICATE,)


def test_a_printed_bound_casilla_is_stored_under_its_binding_and_a_computed_one_is_reported() -> None:
    projection = project_printed_casillas(
        _revision(),
        {_BOUND_CASILLA: Decimal("1234.56"), _COMPUTED_CASILLA: Decimal("100.00"), "9999": Decimal("1.00")},
    )

    assert dict(projection.binding_values) == {_CERTIFICATE: Decimal("1234.56")}
    assert projection.unowned_casillas == ("0505", "9999")


def test_a_casilla_bound_only_to_an_unmarked_binding_is_reported_not_stored() -> None:
    revision = _rebind(_revision(), _BOUND_CASILLA, binding=_UNMARKED)

    projection = project_printed_casillas(revision, {_BOUND_CASILLA: Decimal("1234.56")})

    assert dict(projection.binding_values) == {}
    assert projection.unowned_casillas == (_BOUND_CASILLA,)


def test_a_casilla_two_admitted_bindings_could_own_is_refused() -> None:
    revision = _rebind(_admit(_revision(), _UNMARKED), _BOUND_CASILLA, alternate_bindings=(_UNMARKED,))

    with pytest.raises(LiveApplicationInputError) as refused:
        project_printed_casillas(revision, {_BOUND_CASILLA: Decimal("1234.56")})

    assert refused.value.translated_message == "cli.app.live.borrador.import_casilla_owner_ambiguous"
    assert refused.value.context == {"casillas": _BOUND_CASILLA}


def test_one_admitted_binding_owning_two_printed_casillas_is_refused() -> None:
    revision = _rebind(_revision(), _COMPUTED_CASILLA, input_kind=InputKind.BOUND, binding=_CERTIFICATE)

    with pytest.raises(LiveApplicationInputError) as refused:
        project_printed_casillas(revision, {_BOUND_CASILLA: Decimal("1234.56"), _COMPUTED_CASILLA: Decimal("1.00")})

    assert refused.value.context == {"casillas": "0505, 0596"}
