"""Read an earlier Modelo 200 return's bare PyG boxes under their page-qualified ids.

The Modelo 200 record designs print the same box number on several pages with
different meanings: ``[00255]`` is the net turnover on the cuenta de pérdidas y
ganancias page and also, for example, a Banco de España line on another page. The
registry therefore names each of these PyG lines by its page-qualified id
(``DP200007:00255``). Before that rename it declared the PyG line under the bare
number and declared no other page's box of that number, so a bare id in a row
written then names exactly the PyG line.

A carry reads an earlier return through its page-qualified id, so without this
seam the PyG figure of a return stored before the rename would read as never
observed: the turnover that decides the next year's microempresa rate, for one.
The stored row is not rewritten. It is read through the frozen table below, and
only when the row itself shows it was written under an earlier authority:

* its stored ``authority_generation`` stamp is absent (written before stamps
  existed) or names a generation other than the one the read is pinned to; a row
  the current generation wrote is read exactly as stored, so a new write is never
  aliased; and
* its stored ``stamped_revision_id``, resolved in the pinned authority, no longer
  declares the bare id and does declare its page-qualified replacement. A bare id
  that revision still declares keeps its own meaning.

A row naming the box under both ids with different values is refused; the same
value under both is one figure and reads once.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.casilla_membership import declared_casilla_ids
from ...domain.calculations.registry.errors import RegistryError
from .errors import PriorFilingPageQualifiedConflictError
from .observations_repository import ObservationEnvelopePayload

MODELO_200: Final[str] = "200"
"""The one modelo whose earlier returns the table reads."""

MODELO_200_PAGE_QUALIFIED_CASILLAS: Final[MappingProxyType[CasillaId, CasillaId]] = MappingProxyType(
    {
        "00254": "DP200007:00254",
        "00255": "DP200007:00255",
        "00257": "DP200007:00257",
        "00279": "DP200007:00279",
        "00280": "DP200007:00280",
        "00296": "DP200007:00296",
        "00325": "DP200008:00325",
    },
)
"""Each retired bare PyG casilla id and the page-qualified id that replaced it. Frozen product data."""


def _retired_bare_ids(
    payload: ObservationEnvelopePayload,
    bare_ids: frozenset[CasillaId],
    *,
    operation: PinnedAuthorityOperation,
) -> frozenset[CasillaId]:
    """Return the bare ids the row's own stamped revision retired in favour of their qualified ids."""
    observation = payload.observation
    try:
        snapshot = operation.snapshot(
            str(observation.modelo),
            filing_year=observation.filing_year,
            period=observation.period,
            revision_id=payload.stamped_revision_id,
            grade=RegistryAuthorityGrade.CALCULATION,
        )
    except RegistryError:
        # A stamp the pinned authority cannot resolve settles nothing; the carry
        # gate refuses such a row before any value is read from it.
        return frozenset[CasillaId]()
    declared = declared_casilla_ids(snapshot.revision)
    return frozenset(
        bare for bare in bare_ids if bare not in declared and MODELO_200_PAGE_QUALIFIED_CASILLAS[bare] in declared
    )


def _moved(item: CasillaObservation, retired: frozenset[CasillaId]) -> CasillaObservation:
    def move(casilla_id: CasillaId) -> CasillaId:
        return MODELO_200_PAGE_QUALIFIED_CASILLAS[casilla_id] if casilla_id in retired else casilla_id

    casilla_refs = frozenset(item.operand_casilla_refs)
    return item.model_copy(
        update={
            "casilla_id": move(item.casilla_id),
            "operand_refs": tuple(move(ref) if ref in casilla_refs else ref for ref in item.operand_refs),
            "operand_casilla_refs": tuple(move(ref) for ref in item.operand_casilla_refs),
        },
    )


def _read_under_qualified_ids(
    observations: tuple[CasillaObservation, ...], retired: frozenset[CasillaId]
) -> tuple[tuple[CasillaObservation, ...], tuple[CasillaId, ...]]:
    """Return the observations with retired bare ids moved, and the ids held twice with different values."""
    qualified = {item.casilla_id: item for item in observations if item.casilla_id not in retired}
    read: list[CasillaObservation] = []
    conflicts: list[CasillaId] = []
    for item in observations:
        if item.casilla_id not in retired:
            read.append(item)
            continue
        moved = _moved(item, retired)
        twin = qualified.get(moved.casilla_id)
        if twin is None:
            read.append(moved)
        elif twin.value != moved.value or twin.value_kind != moved.value_kind:
            conflicts.append(moved.casilla_id)
    return tuple(read), tuple(conflicts)


def page_qualified_prior_observation(
    payload: ObservationEnvelopePayload,
    *,
    operation: PinnedAuthorityOperation,
) -> ObservationEnvelopePayload:
    """Return ``payload`` with the bare PyG boxes an earlier authority wrote read under their qualified ids.

    Any row the table does not apply to is returned unchanged, the same object.

    Raises:
        PriorFilingPageQualifiedConflictError: The row holds a box under its bare
            and its qualified id with different values.
    """
    observation = payload.observation
    if str(observation.modelo) != MODELO_200:
        return payload
    if payload.authority_generation == operation.pin().logical_generation:
        return payload
    bare_ids = frozenset(item.casilla_id for item in observation.observations) & frozenset(
        MODELO_200_PAGE_QUALIFIED_CASILLAS
    )
    if not bare_ids:
        return payload
    retired = _retired_bare_ids(payload, bare_ids, operation=operation)
    if not retired:
        return payload
    read, conflicts = _read_under_qualified_ids(observation.observations, retired)
    if conflicts:
        raise PriorFilingPageQualifiedConflictError(
            "an earlier Modelo 200 return holds a PyG box under its bare and its page-qualified id "
            "with different values",
            translated_message="errors.calc.previous_filing_casillas_conflicting",
            context={
                "source_modelo": str(observation.modelo),
                "source_filing_year": observation.filing_year,
                "source_period": observation.period,
                "casilla_ids": ", ".join(sorted(conflicts)),
            },
        )
    return payload.model_copy(update={"observation": observation.model_copy(update={"observations": read})})


__all__ = ["MODELO_200_PAGE_QUALIFIED_CASILLAS", "page_qualified_prior_observation"]
