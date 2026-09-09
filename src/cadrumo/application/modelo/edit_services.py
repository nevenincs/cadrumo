"""Edit admission, schema projection, parsing, and preflight for the Modelo Edit Contract V1.

Behind :mod:`cadrumo.application.modelo`. This module owns the read-only half
of the edit contract: it independently re-resolves a target, projects the
registry-declared permitted surface, and rechecks a submission before
execution. It never writes -- persistence and the guarded compare-and-swap
commit belong to :mod:`.revision_persistence` and :mod:`._edit_execution`.

A :class:`~.workspace_models.ModeloWorkspaceBaselineV1` read-consistency token
is never accepted here as mutation authority: every coordinate below is
independently re-resolved from the target and the current catalogues, never
copied from a Workspace read.
"""

from __future__ import annotations

from ...core.hashing import content_hash_hex
from ...core.time.clock import now as clock_now
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.row_models import ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnitCatalogue
from .edit_models import (
    ModeloEditAddressV1,
    ModeloEditBaselineV1,
    ModeloEditDomainRefusalV1,
    ModeloEditRefusalCode,
    ModeloEditRefusalV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)

RESPONSIBLE_OWNER = "modelo.edit"
"""The owner recorded on every refusal and advisory the modelo edit surface raises."""


def reconfirm_modelo_edit_baseline(
    baseline: ModeloEditBaselineV1,
    *,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
) -> ModeloEditRefusalV1 | None:
    """Recheck every baseline coordinate against the current catalogues.

    Returns ``None`` when nothing has drifted, or the exact typed
    compare-and-swap refusal naming every coordinate that disagreed. Shared by
    preflight (D3) and, once execution lands, the guarded commit point (D6) so
    both recheck through one comparison.
    """
    mismatches: list[str] = []
    if content_hash_hex(work_catalogue.model_dump(mode="json")) != baseline.work_catalogue_revision:
        mismatches.append("work_catalogue_revision")
    if content_hash_hex(calculation_catalogue.model_dump(mode="json")) != baseline.calculation_catalogue_revision:
        mismatches.append("calculation_catalogue_revision")
    work_unit = work_catalogue.work_units.get(baseline.work_unit_id)
    if work_unit is None or work_unit.current_calculation_revision_id != baseline.current_calculation_revision_id:
        mismatches.append("current_calculation_revision_id")
    if clock_now() >= baseline.expires_at:
        mismatches.append("baseline_expiry")
    if not mismatches:
        return None
    return ModeloEditStaleBaselineRefusalV1(
        baseline_id=baseline.baseline_id,
        mismatching_coordinates=tuple(mismatches),
        responsible_owner=RESPONSIBLE_OWNER,
        reconsideration_condition="admit a fresh baseline and resubmit",
    )


def writable_scalar_entry(
    baseline: ModeloEditBaselineV1, casilla_id: str
) -> ModeloEditWritableScalarSurfaceEntryV1 | None:
    """Return the baseline's writable-scalar surface entry for ``casilla_id``, or ``None``."""
    for entry in baseline.permitted_surface:
        if isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1) and entry.casilla_id == casilla_id:
            return entry
    return None


DETAIL_ROW_NATURAL_KEY_SEPARATOR = "|"
"""The one separator a compound detail-row natural key is joined on.

Declared once because both the key derivation here and the operation wire
form that carries the key's components must agree on it exactly; two
literals would be free to drift into addressing different rows.
"""

_DETAIL_ROW_NATURAL_KEY_FIELDS: dict[str, tuple[str, ...]] = {
    "miembro": ("nif", "clave", "subclave"),
    "vinculada": ("nif",),
    "operador": ("nif_comunitario", "clave_operacion"),
    "rectificacion": ("nif_comunitario", "clave_operacion"),
    "contraparte": ("nif",),
    "agrupacion_renta": ("source_id",),
}


def detail_row_identity_components(row: ModeloDetailRow) -> tuple[str, ...]:
    """Return the row's declared identity fields, unjoined and in declared order.

    The components and the joined key are the SAME facts read from the same
    declaration, which is why they live together: a caller that needs the
    parts must never obtain them by splitting the key. Splitting cannot be
    made correct -- a component containing the separator is indistinguishable
    from a boundary once joined -- so the only safe direction is components
    first, key derived.
    """
    fields = _DETAIL_ROW_NATURAL_KEY_FIELDS[row.row_type]
    return tuple(str(getattr(row, field)) for field in fields)


def detail_row_natural_key(row: ModeloDetailRow) -> str:
    """Return the row's own already-declared business key, joined for compound keys.

    Never a minted or positional identity -- see :class:`ModeloEditDetailRowAddressV1`.
    """
    return DETAIL_ROW_NATURAL_KEY_SEPARATOR.join(detail_row_identity_components(row))


def _disallowed_intent_refusal(address: ModeloEditAddressV1) -> ModeloEditRefusalV1:
    return ModeloEditDomainRefusalV1(
        code=ModeloEditRefusalCode.DISALLOWED_INTENT,
        address=address,
        responsible_owner=RESPONSIBLE_OWNER,
        reconsideration_condition=(
            "address only a casilla, binding override, detail row, or row group the baseline's permitted surface admits"
        ),
    )


def validate_scalar_intent(
    baseline: ModeloEditBaselineV1, address: ModeloEditScalarAddressV1, kind: ModeloEditScalarIntentKind
) -> ModeloEditRefusalV1 | None:
    """Return a refusal when ``kind`` is not a permitted intent for the addressed casilla, else ``None``."""
    entry = writable_scalar_entry(baseline, address.casilla_id)
    if entry is None or kind not in entry.allowed_intents:
        return _disallowed_intent_refusal(address)
    return None


__all__ = [
    "detail_row_identity_components",
    "detail_row_natural_key",
    "reconfirm_modelo_edit_baseline",
    "validate_scalar_intent",
    "writable_scalar_entry",
]
