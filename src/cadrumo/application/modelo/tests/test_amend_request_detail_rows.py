"""An amendment submitted as an operation can state the rows it declares.

The authority has required this since it stopped guessing: for M184, M232,
M347 and M349 the per-counterpart rows ARE the declaration, so
``_require_amendment_detail_rows`` refuses an amendment that says nothing
about them. But the registered ``modelo.work.amend`` request carried no such
field, and its executor therefore called the authority without one -- which
made the refusal unconditional. Amending any of those four modelos through the
operation could not succeed at all.

That was the safe direction to fail in and still a withdrawn capability. What
restores it is a field that can express all THREE states the authority reads,
not two: ``None`` is the caller having said nothing and is refused, an empty
tuple is the positive declaration that the period had no rows, and a populated
tuple is the rows themselves. A field that collapsed the first two would hand
the authority a nil declaration the operator never made.

The rows cross as the payload-safe wire mirror rather than the domain row.
That is not ceremony: two of the six domain rows hydrate registry codes
through before-validators, and the operations payload gate refuses those
because a published schema would then not describe what validation accepts.
The mirror already existed for the edit submission, so this reuses it rather
than minting a second translation free to drift from the first.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from ....domain.modelos.row_models import DETAIL_ROW_BEARING_MODELOS, Modelo347ContraparteRow
from ..operation_definitions import (
    ModeloWorkAmendBaseline,
    ModeloWorkAmendOverride,
    ModeloWorkAmendRequest,
    wire_detail_row,
)
from .test_edit_detail_row_wire_mirror import _PAIRS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The four modelos whose rows constitute the declaration, named here so the
#: test fails if the domain ever changes which they are rather than silently
#: covering a set that no longer matches.
_EXPECTED_BEARING = frozenset({"184", "232", "347", "349"})


def _request(**overrides: object) -> ModeloWorkAmendRequest:
    """One valid amendment, re-validated with a single field moved.

    Built from a dump rather than by writing field literals, so a cross-field
    rule added to the request is satisfied by construction instead of
    discovered one rejection at a time.
    """
    valid = ModeloWorkAmendRequest(
        baseline=ModeloWorkAmendBaseline(from_filing_record_id="filing-1"),
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        overrides=(ModeloWorkAmendOverride(casilla_id="01", value="1250.00"),),
        reason="corrected a mistyped base",
        actor="operator-1",
    )
    if not overrides:
        return valid
    return ModeloWorkAmendRequest.model_validate({**valid.model_dump(), **overrides})


def test_the_domain_still_names_the_four_modelos_this_field_exists_for() -> None:
    """The premise: rows are the declaration for exactly these four."""
    assert DETAIL_ROW_BEARING_MODELOS == _EXPECTED_BEARING


def test_an_amendment_that_declares_nothing_about_rows_is_the_default() -> None:
    """The control, and the majority path: most modelos have no rows at all.

    ``None`` must remain reachable without being spelled, because it is the
    ordinary shape for every modelo outside the four -- and it is also the
    exact state the authority refuses for those four, which is why the two
    cannot be told apart here and must not be.
    """
    request = _request()

    assert request.detail_rows is None


def test_declaring_no_rows_is_a_different_state_from_declaring_nothing() -> None:
    """The distinction the whole field exists to carry.

    An empty tuple says the period had no counterparties; ``None`` says the
    caller did not answer. Collapsing them would file a nil declaration nobody
    made.
    """
    said_nothing = _request()
    declared_none = _request(detail_rows=())

    assert said_nothing.detail_rows is None
    assert declared_none.detail_rows == ()
    assert said_nothing.detail_rows != declared_none.detail_rows


def test_rows_reach_the_authority_as_the_exact_domain_rows_submitted() -> None:
    """What the executor hands the authority must be what the caller meant.

    The mirror is only sound if the trip out and back is lossless, so the
    assertion is on the translated domain row rather than on the wire form
    the request happens to hold.
    """
    row = Modelo347ContraparteRow(
        nif="B12345674",
        nombre="Acme SL",
        importe_Q1=Decimal("1000.00"),
        clave_operacion="B",
        pais_codigo="ES",
    )

    request = _request(detail_rows=(wire_detail_row(row).model_dump(),))

    carried = request.detail_rows
    assert carried is not None
    assert len(carried) == 1
    translated = carried[0].to_row()
    assert translated == row
    assert type(translated) is type(row)


@pytest.mark.parametrize("kind", sorted(_PAIRS), ids=sorted(_PAIRS))
def test_every_detail_row_kind_can_be_carried_by_an_amendment(kind: str) -> None:
    """All six kinds, not just the one a hand-picked example would exercise.

    An amendment addresses whichever modelo the baseline belongs to, so a
    request that admitted only some row kinds would refuse a lawful correction
    for reasons the operator could not see.
    """
    mirror, expected = _PAIRS[kind]()

    request = _request(detail_rows=(mirror.model_dump(),))

    carried = request.detail_rows
    assert carried is not None
    assert carried[0].to_row() == expected


def test_all_three_states_survive_the_journal_round_trip() -> None:
    """The request is journalled, so it is read back before the executor sees it.

    A round trip that lost the ``None``/empty distinction would restore the
    refusal this change removes -- or worse, turn a silent caller into one
    that declared nil.
    """
    row_payload = wire_detail_row(
        Modelo347ContraparteRow(
            nif="B12345674",
            nombre="Acme SL",
            importe_Q1=Decimal("1000.00"),
            clave_operacion="B",
            pais_codigo="ES",
        )
    ).model_dump()
    for label, request in (
        ("said nothing", _request()),
        ("declared none", _request(detail_rows=())),
        ("declared rows", _request(detail_rows=(row_payload,))),
    ):
        restored = ModeloWorkAmendRequest.model_validate_json(request.model_dump_json())

        assert restored == request, label
        assert restored.detail_rows == request.detail_rows, label


def test_a_domain_row_cannot_be_submitted_in_place_of_its_mirror() -> None:
    """Why the mirror exists, stated as a refusal rather than a comment.

    The domain row is the richer type and the tempting one to pass. It is
    refused here because the payload gate refuses it upstream: two of the six
    hydrate registry codes through before-validators, so a published schema
    would not describe what validation accepts. Admitting it at this boundary
    would move that mismatch to where nothing checks for it.
    """
    row = Modelo347ContraparteRow(
        nif="B12345674",
        nombre="Acme SL",
        importe_Q1=Decimal("1000.00"),
        clave_operacion="B",
        pais_codigo="ES",
    )

    with pytest.raises(ValidationError):
        ModeloWorkAmendRequest.model_validate(
            {**_request().model_dump(), "detail_rows": (row,)},
        )
