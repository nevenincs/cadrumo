"""A captured header fact reaches storage instead of dying at the projection.

The header facts AEAT states in a filed fichero were reaching the raw
observation and then vanishing, because the persisted provenance is assembled by
:func:`filed_observation_source_metadata` from a FIXED key set that copies
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

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.tests._filed_capture_history_support import (
    _prior_303_observation,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.live.filed_observation_persistence import filed_observation_source_metadata
from cadrumo.core.observed_header_fact import ObservedHeaderFact
from cadrumo.core.period import Period
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.entrypoints.live_state_composition import compose_filed_observation_persistence_ports

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


def _leaked_header_keys(metadata: dict[str, str]) -> list[str]:
    """Name every metadata key that carries a header fact's key.

    Containment rather than equality, because the projection NAMESPACES every
    key it writes -- ``aeat_register_status``, ``aeat_expediente_id``,
    ``aeat_tipo_solicitud``. A flattening regression would follow that same
    convention and write ``aeat_declaration_type``, which an equality test
    would not reach while still passing, because no key in this projection ever
    equals a bare header key. The sibling assertion in the sede adapter tests
    compares casilla ids against RAW header keys and is exact for the same
    reason inverted: there both sides share one namespace.
    """
    return sorted(key for key in metadata if any(fact.header_key in key for fact in _FACTS))


def test_captured_header_facts_are_readable_back_out_of_storage(tmp_path: Path) -> None:
    """The end the bug was at: persisted, then read back, with provenance intact."""
    from cadrumo.application.live.filed_observation_persistence import persist_filed_calculation_observation

    observation = _prior_303_observation(
        pending_compensation=Decimal("0.00"),
        result=Decimal("-1.00"),
    ).model_copy(
        update={"headers": _FACTS},
    )

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        ports = compose_filed_observation_persistence_ports(
            bucket_id=profile.bucket_id,
            output_root=tmp_path,
            objects=profile.repository,
        )
        persist_filed_calculation_observation(observation, ports=ports)

        stored = CalculationObservationRepository(
            bucket_id=profile.bucket_id, objects=profile.repository
        ).load_observation(
            "303",
            Period.from_year_and_code(observation.ejercicio, "1T"),
        )
        history_state = IvaCompensationHistoryRepository(
            bucket_id=profile.bucket_id, objects=profile.repository
        ).load_period(
            Period.from_year_and_code(observation.ejercicio, "1T"),
        )

        assert stored is not None, "nothing was persisted, so this proves nothing about the header channel"
        assert stored.source_headers == _FACTS, (
            "the header facts did not survive persistence with their provenance intact"
        )
        assert stored.result_disposition is not None
        assert stored.result_disposition.disposition is ResultDisposition.COMPENSACION
        assert stored.result_disposition.provenance_kind == "source_header"
        assert history_state is not None
        assert history_state.generated_amount == Decimal("1.00")
        assert history_state.available_end_amount == Decimal("1.00")


def test_the_metadata_projection_still_does_not_carry_headers(tmp_path: Path) -> None:
    """The trap is closed by a separate channel, not by widening the fixed key set.

    This is the discriminating half. If a later change routed header facts back
    through ``source_metadata``, the test above would still pass while the facts
    silently lost their locators and their types on the way -- a flat map has
    nowhere to put them. Asserting the projection stays header-free is what
    keeps "it arrived" from being satisfiable by the shape we moved away from.
    """
    del tmp_path
    observation = _prior_303_observation(
        pending_compensation=Decimal("0.00"),
        result=Decimal("-1.00"),
    ).model_copy(
        update={"headers": _FACTS},
    )

    metadata = filed_observation_source_metadata(observation)

    assert metadata, "the projection returned nothing, so the absence below is meaningless"

    # The projection being non-empty proves the subject exists; it does not
    # prove the leak predicate can FIRE. Feed it the shape a real flattening
    # regression would take -- the namespaced key, not the bare one -- so that
    # the silence asserted below is measured reach rather than an untested
    # expression that would stay quiet however the projection changed.
    planted = f"aeat_{_FACTS[0].header_key}"
    assert _leaked_header_keys({planted: _FACTS[0].value}) == [planted], (
        "the leak predicate did not fire on a planted header key, so its silence below proves nothing"
    )

    leaked = _leaked_header_keys(metadata)
    assert not leaked, f"a header fact was flattened into the metadata map: {leaked}"
