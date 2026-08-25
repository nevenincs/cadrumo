"""Snapshot-time referential integrity for the M130 retenciones output casilla.

The ``modelo-130-actividad-economica-retenciones-cumulative`` binding matches
casilla 01 income rows (``target_casilla_id = "01"``, the OBSERVATION-MATCH
key: see :class:`~domain.calculations.registry._ledger_bindings._RentaLedgerIncomeSelector`'s
docstring for why that field cannot also name the output casilla) but its
resolved value is redirected onto casilla 06 -- retenciones e ingresos a
cuenta soportados -- by a hardcoded application-layer constant
(:data:`RENTA_130_RETENCIONES_OUTPUT_CASILLA`, read by
``application.aggregation._modelo_bindings._m130_retenciones_backend_inputs``).
A hardcoded casilla routed to outside the registry is a routing-integrity
hazard: nothing stops the constant from drifting out of sync with a revision
that drops or renumbers the casilla it names, and that drift fails silently
-- the value simply lands nowhere the filed form reads. This module closes
it the same way :mod:`cadrumo.domain.renta._first_slice_routing_integrity`
closes the equivalent M100 hazard: the constant stays, and a snapshot-time
cross-domain check confirms it names a real casilla on the revision before
any calculation can silently write a value nowhere the filed form will ever
read it.

This check is owned by the ``renta`` domain because the routing fact is
renta domain knowledge -- M130 pago fraccionado retención a cuenta is a
renta (IRPF) concept, the same domain that owns the Modelo 100 first-slice
routing table. The registry must not import ``renta`` directly -- that
reverses the dependency direction the hexagonal architecture enforces.
Instead this module registers a
:class:`~cadrumo.domain.calculations.registry.CrossDomainSnapshotCheck` with
the registry validator via
:func:`~cadrumo.domain.calculations.registry.register_cross_domain_snapshot_check`.
The registration runs at ``renta`` package import time (see
:mod:`cadrumo.domain.renta` ``__init__``); the registry calls the check
through the abstract Protocol without naming ``renta``. The Protocol's third
parameter (``renta_first_slice_binding_targets``) is the first-slice check's
own concern, not this one's -- this check ignores it and reads only
``modelo_id`` and ``casilla_ids``, which is all the shared Protocol shape
needs to express a second, independent domain fact.
"""

from __future__ import annotations

from ...core import CasillaId, Modelo, validated_casilla_id
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.validate_references import register_cross_domain_snapshot_check

RENTA_130_RETENCIONES_OUTPUT_CASILLA: CasillaId = validated_casilla_id(
    "06",
    surface="RENTA_130_RETENCIONES_OUTPUT_CASILLA",
)
"""The M130 casilla the retenciones-a-cuenta binding's resolved value reports on.

Read by ``application.aggregation._modelo_bindings`` as the single source
of truth for the redirect; a second literal declaring the same casilla id
anywhere else is a duplication this constant exists to prevent.
"""

RENTA_130_RETENCIONES_BINDING_ID: BindingId = "modelo-130-actividad-economica-retenciones-cumulative"
"""The binding whose resolved value is redirected onto the output casilla above.

Lives beside the casilla it routes to because the two are one fact -- "this
binding reports on that casilla" -- and splitting them let the requirement be
asserted without reference to the thing that creates it. The application-layer
redirect reads both from here rather than re-declaring either.
"""


def check_m130_retenciones_output_casilla(
    modelo_id: str,
    casilla_ids: frozenset[CasillaId],
    renta_first_slice_binding_targets: frozenset[CasillaId],  # shared Protocol shape, unused here
    revision_binding_ids: frozenset[BindingId] = frozenset(),
) -> list[str]:
    """Assert the M130 retenciones output casilla exists when its binding is declared.

    The requirement is conditional on the binding that creates it, mirroring
    the sibling first-slice check, which likewise asserts only over the casillas
    a revision's own bindings target. A revision declaring no retenciones
    binding runs no redirect, so there is nothing for casilla 06 to receive and
    nothing to protect.

    Asserting it unconditionally for every modelo-130 revision was both wider
    than the fact and wrong in practice: it fired on synthetic revisions built
    to exercise unrelated referential-integrity properties, which legitimately
    declare a minimal casilla set. A gate that reddens on revisions it has no
    claim over trains its readers to work around it.

    Returns a list of failure strings (empty when consistent). The registry
    validator prefixes each failure with the snapshot coordinates and raises
    a single ``RegistryValidationError``.
    """
    if modelo_id != Modelo.M130:
        return []
    if RENTA_130_RETENCIONES_BINDING_ID not in revision_binding_ids:
        return []
    if RENTA_130_RETENCIONES_OUTPUT_CASILLA in casilla_ids:
        return []
    return [
        f"M130 revision declares binding {RENTA_130_RETENCIONES_BINDING_ID!r} but its "
        f"retenciones-a-cuenta output casilla {RENTA_130_RETENCIONES_OUTPUT_CASILLA!r} "
        "is absent from the revision -- the resolved retencion would be written nowhere "
        "the filed form reads",
    ]


register_cross_domain_snapshot_check(check_m130_retenciones_output_casilla)


__all__ = ["RENTA_130_RETENCIONES_OUTPUT_CASILLA", "check_m130_retenciones_output_casilla"]
