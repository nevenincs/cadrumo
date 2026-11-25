"""The published authority serves each revision's declared form layout as its own component."""

from __future__ import annotations

import pytest

from ..authority import PinnedAuthorityOperation
from ..authority_artifact import (
    AuthorityComponentKind,
    FormLayoutComponentQuery,
    authority_component_identity,
    authority_query_from_identity,
)
from ..errors import RegistrySnapshotError
from ..schema_form_layouts import FormLayoutDefinition, FormPlacementKind
from .authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
    open_ended_revision,
    revision_covering,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_M303_REVISION = str(revision_covering("303", filing_year_envelope().floor).id)
_M130_REVISION = str(open_ended_revision("130").id)
_M100_REVISION = str(revision_covering("100", newest_authored_edition("100")).id)


@pytest.mark.parametrize(
    ("modelo", "revision"), [("303", _M303_REVISION), ("130", _M130_REVISION), ("100", _M100_REVISION)]
)
def test_the_runtime_reader_serves_a_layout_that_places_every_casilla(
    modelo: str, revision: str, *, operation: PinnedAuthorityOperation
) -> None:
    layout = operation.form_layout(modelo, revision)
    assert isinstance(layout, FormLayoutDefinition)
    assert layout.revision_id == revision
    casillas = {casilla.id for casilla in operation.revision(modelo, revision).casillas}
    assert {placement.casilla_id for placement in layout.placements} == casillas
    shown = layout.casilla_sections()
    assert {item.casilla_id for item in layout.placements if item.kind is FormPlacementKind.ON_FORM} == set(shown)


def test_the_revision_payload_does_not_carry_the_layout(*, operation: PinnedAuthorityOperation) -> None:
    assert operation.revision("303", _M303_REVISION).form_layouts == ()


def test_an_unknown_revision_is_refused_rather_than_read_as_undeclared(*, operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(RegistrySnapshotError):
        operation.form_layout("303", "1999")


def test_the_component_identity_round_trips() -> None:
    query = FormLayoutComponentQuery("303", _M303_REVISION)
    kind, key = authority_component_identity(query)
    assert kind is AuthorityComponentKind.FORM_LAYOUT
    assert authority_query_from_identity(kind.value, key) == query
