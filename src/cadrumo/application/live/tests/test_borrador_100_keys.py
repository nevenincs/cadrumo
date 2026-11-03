"""The borrador key contract over the published Modelo 100 bound-casilla map."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import InternalInvariantError
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ..borrador_100_keys import (
    BorradorPrintedBoxValue,
    borrador_admitted_bindings,
    printed_box_casilla,
    project_printed_casillas,
    require_printed_observations_resolve,
    unresolved_printed_observations,
)
from ..errors import LiveApplicationInputError

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_application]

# In the 2023 revision casilla 0596 is bound to the suffered-withholding work
# binding, one of the three credit bindings a borrador snapshot may hold; 0505
# is a computed casilla.
_CERTIFICATE: BindingId = "renta-retencion-soportada-trabajo"
_CREDIT_BINDINGS: tuple[BindingId, ...] = (
    "renta-ledger-actividad-retenciones-0599",
    _CERTIFICATE,
    "renta-retencion-soportada-capital-mobiliario",
    "renta-retencion-soportada-ganancia-patrimonial",
    "renta-retencion-soportada-arrendamiento-actividad",
)
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
    assert tuple(borrador_admitted_bindings(_revision())) == _CREDIT_BINDINGS


def test_a_bound_casilla_is_stored_under_its_binding_a_computed_one_is_observed_and_an_undeclared_one_reported() -> (
    None
):
    revision = _revision()
    projection = project_printed_casillas(
        revision,
        {_BOUND_CASILLA: Decimal("1234.56"), _COMPUTED_CASILLA: Decimal("100.00"), "9999": Decimal("1.00")},
        blank=("0545",),
    )

    assert dict(projection.binding_values) == {_CERTIFICATE: Decimal("1234.56")}
    continuity = {casilla.id: casilla.continuidad_id for casilla in revision.casillas}
    assert projection.observed == (
        BorradorPrintedBoxValue(_COMPUTED_CASILLA, continuity[_COMPUTED_CASILLA], Decimal("100.00")),
        BorradorPrintedBoxValue("0545", continuity["0545"], None),
    )
    assert continuity[_COMPUTED_CASILLA] is not None
    assert projection.unowned_casillas == ("9999",)


def test_a_casilla_bound_only_to_an_unmarked_binding_is_observed_not_stored() -> None:
    revision = _rebind(_revision(), _BOUND_CASILLA, binding=_UNMARKED)

    projection = project_printed_casillas(revision, {_BOUND_CASILLA: Decimal("1234.56")})

    assert dict(projection.binding_values) == {}
    assert tuple(box.casilla_id for box in projection.observed) == (_BOUND_CASILLA,)
    assert projection.unowned_casillas == ()


def test_a_printed_box_resolves_through_its_continuity_identity_across_revisions() -> None:
    revision = _revision()
    (computed,) = (casilla for casilla in revision.casillas if casilla.id == _COMPUTED_CASILLA)
    renumbered = BorradorPrintedBoxValue("0999", computed.continuidad_id, Decimal("1.00"))
    numbered_only = BorradorPrintedBoxValue(_COMPUTED_CASILLA, None, Decimal("1.00"))

    resolved = printed_box_casilla(revision, renumbered, captured_revision_id="another-revision")

    assert resolved is not None and resolved.id == _COMPUTED_CASILLA
    assert printed_box_casilla(revision, numbered_only, captured_revision_id=revision.id) is not None
    assert printed_box_casilla(revision, numbered_only, captured_revision_id="another-revision") is None
    assert unresolved_printed_observations(revision, (numbered_only,), captured_revision_id="another-revision") == (
        _COMPUTED_CASILLA,
    )
    with pytest.raises(LiveApplicationInputError) as refused:
        require_printed_observations_resolve(revision, (numbered_only,), captured_revision_id="another-revision")
    assert refused.value.translated_message == "application.live.borrador.errors.printed_observations_unresolved"


def test_a_printed_observation_of_a_box_an_admitted_binding_owns_is_refused_at_capture() -> None:
    revision = _revision()
    owned = BorradorPrintedBoxValue(_BOUND_CASILLA, None, Decimal("1.00"))

    require_printed_observations_resolve(revision, (owned,), captured_revision_id=revision.id)
    with pytest.raises(InternalInvariantError):
        require_printed_observations_resolve(
            revision, (owned,), captured_revision_id=revision.id, refuse_owned_casillas=True
        )


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
