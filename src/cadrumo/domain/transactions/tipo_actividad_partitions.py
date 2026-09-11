"""Registry-backed resolution of a Modelo 036 activity code to its art. 95 arm.

RIRPF art. 95 fixes a different retención rate per kind of activity, and Modelo 036
codes the taxpayer's activity. Which code falls in which arm is a legal
correspondence, so it lives in the registry as data — the
``rirpf-art-95:selector-m036-*`` governed facts, each carrying its own
``legal_refs`` — and this module reads them. There is deliberately no code-to-arm
mapping written here: a literal map would be a second authority for the same fact,
and the registry's is the one that carries its legal basis.

The answer is an :class:`~domain.deadlines.IrpfActivityKind`, the axis that already
existed for exactly this question, rather than a new enum. Its docstring recorded
the derivation as impossible for want of an input, not for want of authority; a
declared ``tipo_actividad`` on a ledger row is that input, so this module closes it.
The apartado-level detail — that agrícola/ganadera comes from art. 95.4.2.º and
forestal from art. 95.5, both yielding 2 % — stays where it belongs, on the
registry facts' own ``legal_refs``, instead of becoming a second public
classifier that would then have to be kept true.

Two of the correspondences would be plausible inferences and are not inferred:

* ``A04 Artísticas y Deportivas`` is professional because art. 95.2.a) counts
  Sección Tercera of the IAE tarifas among rendimientos de actividades
  profesionales alongside Sección Segunda — not because artistic work reads as
  professional.
* ``A02 Ganadería independiente`` is sectorial although it sits in the IAE-subject
  half of the Modelo 036 table, because art. 95.4 says so outright: *Se entenderán
  incluidas entre las actividades agrícolas y ganaderas: a) La ganadería
  independiente*.

``A01``, ``A03``, ``B04`` and ``B05`` fall in no arm: arrendamiento retains under
art. 100, and resto empresariales, mejillón and pesquera reach art. 95 only through
apartado 6.1.º by estimación objetiva, which is a method axis rather than an
activity one.

See Also:
    :class:`~core.TipoActividad`
        The closed code set this resolves from.
    :class:`~domain.deadlines.IrpfActivityKind`
        The arm this resolves to.
    :mod:`~domain.transactions.retencion_facts`
        Reads the rates each arm selects.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING, Final

from ...core.tipos_actividad import TipoActividad
from ..calculations.registry.facts.resolution import EntitySetFactQuery, ResolvedEntitySetFact
from ..calculations.registry.schema_base import DateAxis
from ..deadlines.models import IrpfActivityKind
from .errors import TransactionValidationError

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority

__all__ = [
    "load_tipo_actividad_selectors",
    "resolve_tipo_actividad_selector",
    "tipo_actividad_code_set",
]


#: The art. 95 selector facts, and which arm of :class:`IrpfActivityKind` each
#: one feeds. Keyed by fact id rather than by a second enum: the apartado-level
#: detail is already carried by the registry fact's own ``legal_refs``, and
#: minting an enum for it would be a second public answer to the question
#: ``IrpfActivityKind`` exists to answer.
#:
#: The engorde fact is listed even though its code set is empty, because the
#: emptiness is a finding rather than an omission -- art. 95.4.1.º fixes 1 % for
#: engorde de porcino y avicultura and the Modelo 036 table's finest livestock grain
#: is ``B02``, so no code reaches it. Dropping the entry would hide that.
_ART_95_SELECTORS: Final[Mapping[str, IrpfActivityKind]] = {
    "rirpf-art-95:selector-m036-actividades-profesionales": IrpfActivityKind.PROFESIONAL,
    "rirpf-art-95:selector-m036-actividades-agricolas-ganaderas": IrpfActivityKind.SECTORIAL,
    "rirpf-art-95:selector-m036-actividades-forestales": IrpfActivityKind.SECTORIAL,
    "rirpf-art-95:selector-m036-actividades-ganaderas-engorde-porcino-avicultura": IrpfActivityKind.SECTORIAL,
}

_GOVERNED_ACTIVITY_SELECTOR_IDS: Final[frozenset[str]] = frozenset(
    {
        *_ART_95_SELECTORS,
        "rd-439-2007-art-109:selector-m036-actividades-base-neta-de-subvenciones",
        "rd-439-2007-art-109:selector-m036-actividades-exencion-pago-fraccionado",
        "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrarias-pesqueras",
        "modelo-131:selector-m036-volumen-ingresos-agrario",
    }
)


def resolve_tipo_actividad_selector(
    fact_id: str,
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedEntitySetFact:
    """Resolve one legally grounded Modelo 036 selector through fact authority.

    The result deliberately retains the fact's legal references, exact temporal
    coordinate, and authority digest for a caller that must explain why an
    activity was classified into this arm.
    """
    if fact_id not in _GOVERNED_ACTIVITY_SELECTOR_IDS:
        raise TransactionValidationError(
            f"registry fact {fact_id!r} has no typed governed Modelo 036 activity-selector fact",
        )
    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    try:
        resolved = authority.resolve_governed_fact(
            EntitySetFactQuery(
                fact_id=fact_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
    except Exception as exc:
        from ..calculations.registry.errors import RegistryError

        if isinstance(exc, RegistryError):
            raise TransactionValidationError(
                f"failed to resolve Modelo 036 activity selector {fact_id!r}: {exc}",
            ) from exc
        raise
    if not isinstance(resolved, ResolvedEntitySetFact):
        raise TransactionValidationError(
            f"Modelo 036 activity selector {fact_id!r} did not resolve to an entity-set fact",
        )
    return resolved


def _typed_code_set(selector: ResolvedEntitySetFact) -> frozenset[TipoActividad]:
    """Narrow a resolved entity-set fact to the closed Modelo 036 code type."""
    codes: set[TipoActividad] = set()
    for token in selector.payload.entities:
        try:
            codes.add(TipoActividad(token))
        except ValueError as exc:
            raise TransactionValidationError(
                f"registry fact {selector.fact_id!r} names {token!r}, which is not a "
                f"Modelo 036 activity code; accepted: {', '.join(sorted(t.value for t in TipoActividad))}",
            ) from exc
    return frozenset(codes)


def tipo_actividad_code_set(
    fact_id: str,
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> frozenset[TipoActividad]:
    """Return the Modelo 036 codes a registry selector fact declares.

    The ONE way to read a ``m036-tipo-actividad-code-set`` fact. Several
    unrelated selectors exist -- the four art. 95 partitions and the art. 110.1.c)
    agrarian set -- and each additional caller that splits the string itself is a
    second place the unit check, the unknown-token refusal and the typing can drift.

    Args:
        fact_id: The registry fact to read.
        effective_date: Filing-period coordinate for the exact fact variant.
        authority: Optional validated authority used for fact resolution.

    Returns:
        The declared codes, empty when the fact declares none.

    Raises:
        TransactionValidationError: If the fact is absent, carries the wrong
            unit, names a non-code token, or the catalogue cannot be loaded.
    """
    return _typed_code_set(
        resolve_tipo_actividad_selector(
            fact_id,
            effective_date=effective_date,
            authority=authority,
        ),
    )


def load_tipo_actividad_selectors(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> Mapping[str, frozenset[TipoActividad]]:
    """Return the codes each art. 95 selector fact declares.

    Every selector is present, including the engorde one whose set is empty. An
    empty set is data, not an absence: it records that the Modelo 036 axis cannot
    reach that partition, which is why a code's absence from the other sets must
    not be read as "no rate applies".

    Returns:
        A mapping from selector fact id to its declared codes.

    Args:
        effective_date: Filing-period coordinate for the exact selector variants.
        authority: Optional validated authority used for fact resolution.

    Raises:
        TransactionValidationError: If a selector is absent or malformed, if the
            same code appears in two selectors, or if the catalogue cannot load.
    """
    selectors = {
        fact_id: _typed_code_set(
            resolve_tipo_actividad_selector(
                fact_id,
                effective_date=effective_date,
                authority=authority,
            ),
        )
        for fact_id in _ART_95_SELECTORS
    }

    seen: dict[TipoActividad, str] = {}
    for fact_id, codes in selectors.items():
        for code in codes:
            previous = seen.get(code)
            if previous is not None:
                raise TransactionValidationError(
                    f"Modelo 036 code {code.value!r} is declared by both {previous!r} and "
                    f"{fact_id!r}; a code must select at most one art. 95 arm",
                )
            seen[code] = fact_id
    return selectors
