"""Source artefact bytes stay staged until the application enters its fence."""

from __future__ import annotations

import pytest

from ......core.period import Period
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..filed_data_capture_port import DeferredSedeObservations
from ..schema import FiledDeclaracionArtefact, FiledDeclaracionObservation

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_YEAR = filing_year_envelope().horizon


def test_source_batch_persists_in_observation_order_once() -> None:
    period = Period.from_year_and_code(_YEAR, "1T")
    key1 = ("303", _YEAR, period, "1")
    key2 = ("303", _YEAR, period, "2")
    first = FiledDeclaracionArtefact.model_construct(kind="register_row", storage_ref=None)
    second = FiledDeclaracionArtefact.model_construct(kind="justificante_pdf", storage_ref=None)
    observed = (
        FiledDeclaracionObservation.model_construct(artefacts=(first,)),
        FiledDeclaracionObservation.model_construct(artefacts=(second,)),
    )
    deferred = DeferredSedeObservations(
        observations=observed,
        staged=[(key1, first, b"one"), (key2, second, b"two")],
    )
    calls: list[tuple[tuple[str, int, Period, str], bytes]] = []

    def persist(key, artefact, body):
        calls.append((key, body))
        return artefact.model_copy(update={"storage_ref": str(len(calls))})

    stored = deferred.persist_artefacts(persist)
    assert calls == [(key1, b"one"), (key2, b"two")]
    assert tuple(row.artefacts[0].storage_ref for row in stored) == ("1", "2")
    with pytest.raises(ValueError, match="twice"):
        deferred.persist_artefacts(persist)


def test_source_batch_refuses_mismatched_staged_artefacts_before_writing() -> None:
    period = Period.from_year_and_code(_YEAR, "1T")
    artefact = FiledDeclaracionArtefact.model_construct(kind="register_row", storage_ref=None)
    foreign = FiledDeclaracionArtefact.model_construct(kind="justificante_pdf", storage_ref=None)
    deferred = DeferredSedeObservations(
        observations=(FiledDeclaracionObservation.model_construct(artefacts=(artefact,)),),
        staged=[(("303", _YEAR, period, "1"), foreign, b"foreign")],
    )

    def forbidden(*args):
        del args
        raise AssertionError("mismatched staged source wrote an artefact")

    with pytest.raises(ValueError, match="differ"):
        deferred.persist_artefacts(forbidden)
