"""The edit-surface contract bound against every published registry edition.

The bound on permitted-surface entries is a contract limit, not a registry
fact, so it has to stay above what the registry actually publishes. These
proofs measure every edition through the admission producer's own surface
builder and carry the largest real baseline through the paged result channel
an operation result travels on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache

import pytest

from cadrumo_client.contracts.projection_pages import (
    PROJECTION_RESULT_MAX_BYTES,
    ProjectionPageRequest,
    encode_projection_document,
    project_encoded_page,
)
from cadrumo_client.contracts.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.hashing import sha256_hex
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...operations.contract_manifest import load_operation_contract_manifest
from ..edit_admission import _permitted_surface, admit_modelo_edit_baseline
from ..edit_baseline_projection import ModeloEditApplyBaselineV1
from ..edit_models import MAX_MODELO_EDIT_SURFACE_ENTRIES, ModeloEditAdmittedV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(1980, 9, 21, 10, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _EditionSurface:
    """One published edition, the filing coordinates it serves and its measured edit surface."""

    modelo_id: str
    revision_id: str
    coordinates: tuple[tuple[int, str], ...]
    surface_entries: int


@cache
def _edition_surfaces() -> tuple[tuple[_EditionSurface, ...], tuple[tuple[str, str], ...]]:
    """Measure every published edition inside the support envelope; name the ones entirely outside it.

    Each edition is snapshotted at the first supported coordinate it serves,
    pinned to its own revision, at the lowest grade, so an edition authored
    below calculation grade is measured too: promoting it must not cross the
    bound unnoticed. The surface is built by the admission producer's own
    function with the edition's real form layout. ``attestable_binding_ids`` is
    the empty set, the production default for a fresh work unit without carry
    sources; that set only decides whether a binding's single entry is
    writable, never how many entries the surface has.

    An edition whose window lies wholly outside the envelope serves no
    supported coordinate, so no snapshot and no baseline can be admitted for it.
    """
    measured: list[_EditionSurface] = []
    outside: list[tuple[str, str]] = []
    with bundled_indexed_authority().operation() as operation:
        envelope = operation.supported_filing_years()
        for modelo_id in operation.modelo_ids():
            for metadata in operation.modelo_directory(modelo_id).revisions:
                last_year = metadata.valid_to.year if metadata.valid_to is not None else envelope.horizon
                coordinates = tuple(
                    (year, period)
                    for year in envelope.years
                    if metadata.valid_from.year <= year <= last_year
                    for period in metadata.period_selector.periods_for_year(year)
                )
                if not coordinates:
                    outside.append((modelo_id, str(metadata.id)))
                    continue
                year, period = coordinates[0]
                snapshot = operation.build_unretained_snapshot(
                    modelo_id,
                    filing_year=year,
                    period=period,
                    revision_id=metadata.id,
                    grade=RegistryAuthorityGrade.APPLICABILITY,
                )
                surface = _permitted_surface(
                    snapshot,
                    period=period,
                    layout=operation.form_layout(modelo_id, str(metadata.id)),
                    attestable_binding_ids=frozenset(),
                )
                measured.append(
                    _EditionSurface(
                        modelo_id=modelo_id,
                        revision_id=str(metadata.id),
                        coordinates=coordinates,
                        surface_entries=len(surface),
                    )
                )
    return tuple(measured), tuple(outside)


def test_the_edit_surface_bound_exceeds_every_published_edition() -> None:
    measured, outside = _edition_surfaces()
    with bundled_indexed_authority().operation() as operation:
        envelope = operation.supported_filing_years()
        for modelo_id, revision_id in outside:
            metadata = next(
                item for item in operation.modelo_directory(modelo_id).revisions if str(item.id) == revision_id
            )
            ends_below_floor = metadata.valid_to is not None and metadata.valid_to.year < envelope.floor
            assert ends_below_floor or metadata.valid_from.year > envelope.horizon, (
                f"modelo {modelo_id} revision {revision_id} lies inside the envelope but serves no coordinate"
            )
    assert measured

    largest_per_modelo: dict[str, _EditionSurface] = {}
    for edition in measured:
        current = largest_per_modelo.get(edition.modelo_id)
        if current is None or edition.surface_entries > current.surface_entries:
            largest_per_modelo[edition.modelo_id] = edition
    over = [edition for edition in measured if edition.surface_entries >= MAX_MODELO_EDIT_SURFACE_ENTRIES]
    ranked = sorted(largest_per_modelo.values(), key=lambda edition: edition.surface_entries, reverse=True)
    report = ", ".join(f"{edition.modelo_id} {edition.revision_id}: {edition.surface_entries}" for edition in ranked)
    assert not over, f"surface bound {MAX_MODELO_EDIT_SURFACE_ENTRIES}; largest per modelo: {report}"


def _largest_admissible_baseline() -> ModeloEditApplyBaselineV1:
    """Admit the real edit baseline of the edition with the largest measured surface."""
    measured, _ = _edition_surfaces()
    largest = max(measured, key=lambda edition: edition.surface_entries)
    with bundled_indexed_authority().operation() as operation:
        law_selected = []
        for year, period in largest.coordinates:
            try:
                selected = operation.revision_for_context(largest.modelo_id, filing_year=year, period=period)
            except RegistryValidationError:
                continue
            if str(selected.id) == largest.revision_id:
                law_selected.append((year, period))
        assert law_selected, f"no supported coordinate law-selects {largest.modelo_id} {largest.revision_id}"
        year, code = law_selected[0]
        period = Period.from_year_and_code(year, code)
        work_unit = WorkUnit(
            work_unit_id=derive_work_unit_id(
                bucket_id="edit-bound-bucket",
                modelo=largest.modelo_id,
                filing_year=year,
                period=period,
                revision_id=largest.revision_id,
            ),
            bucket_id="edit-bound-bucket",
            modelo=largest.modelo_id,
            filing_year=year,
            period=period,
            revision_id=largest.revision_id,
            name=f"{largest.modelo_id} {year}",
            created_at=_NOW,
            updated_at=_NOW,
        )
        outcome = admit_modelo_edit_baseline(
            work_unit_id=work_unit.work_unit_id,
            work_catalogue=WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit}),
            calculation_catalogue=CalculationRevisionCatalogue(),
            operation=operation,
            operation_contracts=load_operation_contract_manifest().contract_set,
            issued_at=_NOW,
        )
    assert isinstance(outcome, ModeloEditAdmittedV1), outcome
    assert len(outcome.baseline.permitted_surface) == largest.surface_entries
    return ModeloEditApplyBaselineV1.from_baseline(outcome.baseline)


def test_the_largest_real_baseline_round_trips_through_the_paged_result_channel() -> None:
    """The wire baseline rides in the form-read result and the apply request.

    A result leaves the worker as one canonical document sliced into bounded
    pages, each of which fits one transport frame; the request travels as a
    chunked submission payload. The document must fit both whole-document
    bounds and decode back to the same baseline from its reassembled pages.
    """
    baseline = _largest_admissible_baseline()
    document = encode_projection_document(baseline.model_dump(mode="json"))
    size = len(document.encoded)
    assert size <= PROJECTION_RESULT_MAX_BYTES, f"{size} bytes exceed the result bound {PROJECTION_RESULT_MAX_BYTES}"
    assert size <= SUBMISSION_PAYLOAD_MAX_BYTES, f"{size} bytes exceed the request bound {SUBMISSION_PAYLOAD_MAX_BYTES}"

    reassembled = bytearray()
    while len(reassembled) < size:
        page = project_encoded_page(
            document,
            ProjectionPageRequest(offset=len(reassembled), expected_digest=document.digest if reassembled else None),
        )
        assert page.total_bytes == size
        assert page.document_digest == document.digest
        reassembled.extend(page.decode())
    assert sha256_hex(bytes(reassembled)) == document.digest

    decoded = ModeloEditApplyBaselineV1.model_validate_json(bytes(reassembled))
    assert decoded == baseline
    assert decoded.to_baseline() == baseline.to_baseline()
