"""Project modelo 296's repeated perceptor rows.

Modelo 296 is the IRNR annual summary of retenciones e ingresos a cuenta, and AEAT emits
its Tipo 2 record once per payee. The record was published as a single non-repeating
record, so the layout could hold exactly one perceptor: a 296 with two payees could not be
expressed at all, and the forty-four fields of the row were declared as header producers
that nothing resolved, rendering the payee blank.

The record now declares ``repeat = "projection_rows"``. Row identity is the render
OCCURRENCE, not a slot on the reference -- unlike modelo 200's party blocks, which AEAT
prints a fixed number of times, the number of perceptores is the number of payees and the
design sets no ceiling. That is why
:class:`~cadrumo.core.M296PerceptorProjectionRef` carries no ``slot``: one would be a
second row axis that is always 1, and at worst an invitation to cap the payees.

A filing with no perceptores emits no occurrence, which is what AEAT expects of a
declaration with nothing to report; whether that absence is admissible is the record's own
``required`` flag, checked by the renderer.
"""

from __future__ import annotations

from ._producer_snapshot import FilingProducerSnapshot, Modelo296PerceptorRow, Modelo296ProfileFacts
from ._projection import FilingProjectionPlan, FilingProjectionValue, FilingRecordRenderContext

__all__ = ["build_m296_filing_projection_plan"]

_PERCEPTOR_KIND = "m296_perceptor"


def _perceptor_rows(profile: object) -> tuple[Modelo296PerceptorRow, ...]:
    """Return the payees this filing carries, empty when it carries none."""
    if not isinstance(profile, Modelo296ProfileFacts):
        return ()
    return profile.perceptor_rows


def build_m296_filing_projection_plan(
    *,
    registry_snapshot: object,
    layout: object,
    producer_snapshot: FilingProducerSnapshot,
) -> FilingProjectionPlan:
    """Project one perceptor record occurrence per payee from one snapshot and layout."""
    rows = _perceptor_rows(producer_snapshot.model_profile)
    contexts: list[FilingRecordRenderContext] = []
    values: list[FilingProjectionValue] = []

    for record in layout.records:
        refs = tuple(
            field.projection_ref
            for field in record.fields
            if field.projection_ref is not None and field.projection_ref.projection_kind == _PERCEPTOR_KIND
        )
        if not refs:
            continue
        for occurrence, row in enumerate(rows, 1):
            contexts.append(
                FilingRecordRenderContext(
                    registry_snapshot=registry_snapshot,
                    layout=layout,
                    record=record,
                    occurrence=occurrence,
                ),
            )
            values.extend(
                FilingProjectionValue(
                    projection_ref=ref,
                    record_id=record.id,
                    occurrence=occurrence,
                    # The reference's field IS the row attribute -- the row type is generated
                    # from the same enum -- so a missing one is a defect rather than an absent
                    # value, and getattr without a default is what surfaces it.
                    value=getattr(row, ref.field.value),
                )
                for ref in refs
            )

    return FilingProjectionPlan(contexts=tuple(contexts), values=tuple(values))
