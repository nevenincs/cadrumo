"""A captured header fact reaches storage instead of dying at the projection.

The header facts AEAT states in a filed fichero were reaching the raw
observation and then vanishing, because the persisted provenance is assembled by
:func:`_filed_observation_source_metadata` from a FIXED key set that copies
exactly one key off the observation. Anything else on the observation was simply
not named there, so it never reached the repository -- the capture succeeded, the
parse succeeded, and the evidence was gone one layer later.

That is the specific failure this module exists to prevent recurring, and it is
why the assertion is on what came back OUT of storage rather than on what the
capture put together. A test that checked the observation carried its headers
would have passed throughout the entire period the bug existed.

See Also:
    :class:`~core.ObservedHeaderFact`
        The typed fact, and the record of which of its values are unexercised.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import ObservedHeaderFact, Period
from ...calculations import CalculationObservationRepository
from .._filed_observation_persistence import _filed_observation_source_metadata
from ._filed_capture_history_support import _prior_303_observation, _secure_backend

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FACTS = (
    ObservedHeaderFact(
        header_key="declaration_type",
        value="C",
        source_artefact_kind="submitted_file",
        source_locator="modelo-303-fichero-boe:modelo-303-page-01:modelo-303-declaration-type:13:1",
    ),
    ObservedHeaderFact(
        header_key="redeme",
        value="N",
        source_artefact_kind="submitted_file",
        source_locator="modelo-303-fichero-boe:modelo-303-page-01:modelo-303-redeme:400:1",
    ),
)


def test_captured_header_facts_are_readable_back_out_of_storage(tmp_path: Path) -> None:
    """The end the bug was at: persisted, then read back, with provenance intact."""
    from ...live import persist_filed_calculation_observation

    observation = _prior_303_observation(pending_compensation=Decimal("0.00")).model_copy(
        update={"headers": _FACTS},
    )

    with _secure_backend(tmp_path):
        persist_filed_calculation_observation(observation)

        stored = CalculationObservationRepository().load_observation(
            "303",
            Period.from_year_and_code(observation.ejercicio, "1T"),
        )

        assert stored is not None, "nothing was persisted, so this proves nothing about the header channel"
        assert stored.source_headers == _FACTS, (
            "the header facts did not survive persistence with their provenance intact"
        )


def test_the_metadata_projection_still_does_not_carry_headers(tmp_path: Path) -> None:
    """The trap is closed by a separate channel, not by widening the fixed key set.

    This is the discriminating half. If a later change routed header facts back
    through ``source_metadata``, the test above would still pass while the facts
    silently lost their locators and their types on the way -- a flat map has
    nowhere to put them. Asserting the projection stays header-free is what
    keeps "it arrived" from being satisfiable by the shape we moved away from.
    """
    del tmp_path
    observation = _prior_303_observation(pending_compensation=Decimal("0.00")).model_copy(
        update={"headers": _FACTS},
    )

    metadata = _filed_observation_source_metadata(observation)

    assert metadata, "the projection returned nothing, so the absence below is meaningless"
    leaked = sorted(key for key in metadata if any(fact.header_key in key for fact in _FACTS))
    assert not leaked, f"a header fact was flattened into the metadata map: {leaked}"
