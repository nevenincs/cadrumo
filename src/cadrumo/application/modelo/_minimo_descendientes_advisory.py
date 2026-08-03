"""Calculate-path advisory for an undeclared Art. 58/61 mínimo por descendientes.

Modelo 100 casillas ``irpf_minimo_descendientes_estatal`` (0513) and
``irpf_minimo_descendientes_autonomico`` (0514) are ``input_kind = computed``: the
Art. 58/61 LIRPF aggregate is derived from the active profile's
``renta_family.descendiente.{n}.*`` facts by
:func:`~application.modelo._profile_binding.inject_derived_minimo_descendientes_facts`.
A profile that carries no descendiente facts at all resolves 0513/0514 to the
legally-correct zero for a genuinely childless filer — but the SAME zero also results
when a filer with real descendants simply never declared them (no live production
surface wrote ``renta_family.descendiente.*`` before
``aeat config profile descendiente add`` was introduced). The two cases are
indistinguishable from the computed value alone, so this collector raises a
non-blocking advisory whenever 0513 resolves to zero AND the profile has NOT
explicitly declared its descendientes situation, pointing the operator at the
entry command (`no-silent-under-declaration`). "Explicitly declared" covers both
a per-descendant ``renta_family.descendiente.{n}.*`` fact (the ``config profile
descendiente add`` entry surface) and a bare ``renta_family.descendientes_count``
fact (even ``0``) written by another surface — a persona that positively declares
zero children is not a silent gap, whether or not any declared descendant turns
out Art. 58.1-eligible.

See Also:
    :mod:`~application.modelo._calculation_diagnostics`:
        Post-calculation coordinator that calls this collector with the engine
        casilla values and the owning bucket id.
    :func:`~application.modelo._profile_binding.inject_derived_minimo_descendientes_facts`:
        Computes the Art. 58/61 aggregate this collector's zero-check inspects.
    :func:`~domain.contribuyente.parse_descendiente_flag`:
        Parses the ``--descendiente`` flag the advisory's ``next_action`` names.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import Modelo
from ...domain.calculations.registry import CasillaId, ModeloRevision
from ...domain.user_profile import ProfileNotFoundError
from ..aggregation import CalculationSourceDiagnostic
from ._semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_revision_semantic_role

__all__ = ["collect_minimo_descendientes_undeclared_diagnostics"]

_MINIMO_ESTATAL_SEMANTIC_ROLE = "irpf_minimo_descendientes_estatal"
_DESCENDANT_FACT_PREFIX = "renta_family.descendiente."
_DESCENDANTS_COUNT_PATH = "renta_family.descendientes_count"

_UNDECLARED_SOURCE_KIND = "minimo_descendientes_undeclared"


def _has_descendiente_facts(bucket_id: str) -> bool:
    """Return whether the active profile has explicitly declared its descendientes.

    Recognises two forms of an explicit declaration: at least one per-descendant
    ``renta_family.descendiente.{n}.*`` fact (the ``config profile descendiente add``
    entry surface), or an explicit ``renta_family.descendientes_count`` fact (even
    ``0``) -- a persona that positively declares zero children through the aggregate
    count, without ever using the per-descendant entry surface, has still declared
    its family situation and must not be flagged as a silent gap.

    Returns ``False`` when the bucket has no profile yet, mirroring the silent-absent
    handling :func:`~application.modelo._profile_binding.resolve_profile_sourced_bindings`
    already applies to profile-sourced bindings.
    """
    from ..user_profile import UserProfileLifecycleRepository

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError:
        return False
    return any(
        fact.value is not None
        and (fact.path.startswith(_DESCENDANT_FACT_PREFIX) or fact.path == _DESCENDANTS_COUNT_PATH)
        for fact in record.facts
    )


def _casilla_id_for_role(revision: ModeloRevision, semantic_role: str, *, modelo_id: str) -> CasillaId | None:
    try:
        return casilla_id_for_unique_revision_semantic_role(revision, semantic_role, modelo_id=modelo_id)
    except AmbiguousSemanticRoleCasillaError:
        return None


def collect_minimo_descendientes_undeclared_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return an advisory when 0513 resolved to zero with no descendientes declared.

    Args:
        revision: The :class:`ModeloRevision` being calculated. Only Modelo 100
            revisions declare the mínimo por descendientes semantic role; every other
            modelo returns an empty tuple immediately.
        casilla_values: The computed engine values keyed by :class:`CasillaId`.
        modelo: The modelo identifier of the filing being calculated.
        bucket_id: Bucket identifier used to load the active profile's descendientes
            facts.

    Returns:
        A one-element tuple carrying the advisory, or an empty tuple when 0513 is
        nonzero or the profile already declares at least one descendiente fact.
    """
    if modelo != Modelo.M100.value:
        return ()
    estatal_id = _casilla_id_for_role(revision, _MINIMO_ESTATAL_SEMANTIC_ROLE, modelo_id=modelo)
    if estatal_id is None:
        return ()
    estatal_value = casilla_values.get(estatal_id, Decimal(0))
    if estatal_value != Decimal(0):
        return ()
    if _has_descendiente_facts(bucket_id):
        # The profile explicitly declared descendientes (even if none turned out
        # Art. 58.1-eligible, e.g. every child is over 25 and non-discapacitado); a
        # declared zero is not a silent gap.
        return ()
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=_UNDECLARED_SOURCE_KIND,
            message=(
                f"casilla {estatal_id!r} (mínimo por descendientes, parte estatal) resolved to zero and "
                "the active profile declares no renta_family.descendiente facts -- if you have children "
                "or other eligible descendants, declare them with `aeat config profile descendiente add "
                "--descendiente NACIMIENTO=YYYY-MM-DD[,...]` before filing, or the Art. 58 LIRPF allowance "
                "is silently omitted"
            ),
            casilla_id=estatal_id,
        ),
    )
