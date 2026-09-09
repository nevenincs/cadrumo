"""Registry-backed resolution of a Modelo 036 activity code to its art. 95 arm.

RIRPF art. 95 fixes a different retención rate per kind of activity, and Modelo 036
codes the taxpayer's activity. Which code falls in which arm is a legal
correspondence, so it lives in the registry as data — the
``rirpf-art-95:selector-m036-*`` parameters in
``registry/aeat/legal/irpf-retencion-actividades.toml``, each carrying its own
``legal_refs`` — and this module reads it. There is deliberately no code-to-arm
mapping written here: a literal map would be a second authority for the same fact,
and the registry's is the one that carries its legal basis.

The answer is an :class:`~domain.deadlines.IrpfActivityKind`, the axis that already
existed for exactly this question, rather than a new enum. Its docstring recorded
the derivation as impossible for want of an input, not for want of authority; a
declared ``tipo_actividad`` on a ledger row is that input, so this module closes it.
The apartado-level detail — that agrícola/ganadera comes from art. 95.4.2.º and
forestal from art. 95.5, both yielding 2 % — stays where it belongs, on the
registry parameters' own ``legal_refs``, instead of becoming a second public
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
    :mod:`~domain.transactions.retencion_parameters`
        Reads the rates each arm selects.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import TYPE_CHECKING, Final, cast

from ...core.resources.bundled_data import bundled_path
from ...core.tipos_actividad import TipoActividad
from ..calculations.registry.facts.resolution import EntitySetFactQuery, ResolvedEntitySetFact
from ..calculations.registry.schema_base import DateAxis
from ..deadlines.models import IrpfActivityKind
from .errors import TransactionValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from ..calculations.registry.authority import ValidatedRegistryAuthority

__all__ = [
    "load_tipo_actividad_selectors",
    "resolve_tipo_actividad_selector",
    "tipo_actividad_code_set",
]


#: The art. 95 selector parameters, and which arm of :class:`IrpfActivityKind` each
#: one feeds. Keyed by parameter id rather than by a second enum: the apartado-level
#: detail is already carried by the registry parameter's own ``legal_refs``, and
#: minting an enum for it would be a second public answer to the question
#: ``IrpfActivityKind`` exists to answer.
#:
#: The engorde parameter is listed even though its code set is empty, because the
#: emptiness is a finding rather than an omission -- art. 95.4.1.º fixes 1 % for
#: engorde de porcino y avicultura and the Modelo 036 table's finest livestock grain
#: is ``B02``, so no code reaches it. Dropping the entry would hide that.
_ART_95_SELECTORS: Final[Mapping[str, IrpfActivityKind]] = {
    "rirpf-art-95:selector-m036-actividades-profesionales": IrpfActivityKind.PROFESIONAL,
    "rirpf-art-95:selector-m036-actividades-agricolas-ganaderas": IrpfActivityKind.SECTORIAL,
    "rirpf-art-95:selector-m036-actividades-forestales": IrpfActivityKind.SECTORIAL,
    "rirpf-art-95:selector-m036-actividades-ganaderas-engorde-porcino-avicultura": IrpfActivityKind.SECTORIAL,
}

_EXPECTED_UNIT: Final[str] = "m036-tipo-actividad-code-set"


def _code_set(parameters: Mapping[str, object], parameter_id: str) -> frozenset[TipoActividad]:
    """Parse one selector parameter into its typed code set.

    Raises:
        TransactionValidationError: If the parameter is absent, carries the wrong
            unit, or names a token that is not a Modelo 036 activity code.
    """
    parameter = parameters.get(parameter_id)
    if parameter is None:
        raise TransactionValidationError(
            f"registry parameter {parameter_id!r} is absent; the Modelo 036 activity "
            "selectors must be declared in the legal catalogue",
        )
    unit = getattr(parameter, "unit", None)
    if unit != _EXPECTED_UNIT:
        raise TransactionValidationError(
            f"registry parameter {parameter_id!r} carries unit {unit!r}, expected {_EXPECTED_UNIT!r}",
        )
    raw = getattr(parameter, "value", None)
    if not isinstance(raw, str):
        raise TransactionValidationError(
            f"registry parameter {parameter_id!r} carries no string value",
        )
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    codes: set[TipoActividad] = set()
    for token in tokens:
        try:
            codes.add(TipoActividad(token))
        except ValueError as exc:
            raise TransactionValidationError(
                f"registry parameter {parameter_id!r} names {token!r}, which is not a "
                f"Modelo 036 activity code; accepted: {', '.join(sorted(t.value for t in TipoActividad))}",
            ) from exc
    return frozenset(codes)


def resolve_tipo_actividad_selector(
    parameter_id: str,
    *,
    effective_date: date,
    authority: "ValidatedRegistryAuthority | None" = None,
) -> ResolvedEntitySetFact:
    """Resolve a migrated art. 95 selector through the canonical fact authority.

    The result deliberately retains the fact's legal references, exact temporal
    coordinate, and authority digest for a caller that must explain why an
    activity was classified into this arm.
    """
    if parameter_id not in _ART_95_SELECTORS:
        raise TransactionValidationError(
            f"registry parameter {parameter_id!r} has no typed Modelo 036 activity-selector fact",
        )
    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    try:
        resolved = authority.resolve_governed_fact(
            EntitySetFactQuery(
                fact_id=parameter_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
    except Exception as exc:
        from ..calculations.registry.errors import RegistryError

        if isinstance(exc, RegistryError):
            raise TransactionValidationError(
                f"failed to resolve Modelo 036 activity selector {parameter_id!r}: {exc}",
            ) from exc
        raise
    return cast("ResolvedEntitySetFact", resolved)


def _typed_code_set(selector: ResolvedEntitySetFact) -> frozenset[TipoActividad]:
    """Narrow a resolved entity-set fact to the closed Modelo 036 code type."""
    codes: set[TipoActividad] = set()
    for token in selector.payload.entities:
        try:
            codes.add(TipoActividad(token))
        except ValueError as exc:
            raise TransactionValidationError(
                f"registry parameter {selector.fact_id!r} names {token!r}, which is not a "
                f"Modelo 036 activity code; accepted: {', '.join(sorted(t.value for t in TipoActividad))}",
            ) from exc
    return frozenset(codes)


def tipo_actividad_code_set(
    parameter_id: str,
    *,
    effective_date: date | None = None,
    authority: "ValidatedRegistryAuthority | None" = None,
) -> frozenset[TipoActividad]:
    """Return the Modelo 036 codes a registry selector parameter declares.

    The ONE way to read a ``m036-tipo-actividad-code-set`` parameter. Several
    unrelated selectors exist -- the four art. 95 partitions and the art. 110.1.c)
    agrarian set -- and each additional caller that splits the string itself is a
    second place the unit check, the unknown-token refusal and the typing can drift.

    Args:
        parameter_id: The registry parameter to read.

    Returns:
        The declared codes, empty when the parameter declares none.

    Raises:
        TransactionValidationError: If the parameter is absent, carries the wrong
            unit, names a non-code token, or the catalogue cannot be loaded.
    """
    if parameter_id in _ART_95_SELECTORS:
        return _typed_code_set(
            resolve_tipo_actividad_selector(
                parameter_id,
                effective_date=effective_date or date.today(),
                authority=authority,
            ),
        )
    return _code_set(_legal_parameters(), parameter_id)


def _legal_parameters() -> Mapping[str, object]:
    """Load the registry parameter catalogue, translating its failure.

    Raises:
        TransactionValidationError: If the catalogue cannot be loaded.
    """
    # Imported inside the function for the reason the retención-rate loader gives:
    # the registry import path reaches back into the domain packages this module
    # belongs to, and a module-level import would close that cycle.
    from ..calculations.registry.errors import RegistryError
    from ..calculations.registry.loader import load_legal_parameters_only

    try:
        return load_legal_parameters_only(bundled_path("registry", "aeat"))
    except RegistryError as exc:
        raise TransactionValidationError(
            f"failed to load the registry parameter catalogue: {exc}",
        ) from exc


@lru_cache(maxsize=1)
def load_tipo_actividad_selectors() -> Mapping[str, frozenset[TipoActividad]]:
    """Return the codes each art. 95 selector parameter declares.

    Every selector is present, including the engorde one whose set is empty. An
    empty set is data, not an absence: it records that the Modelo 036 axis cannot
    reach that partition, which is why a code's absence from the other sets must
    not be read as "no rate applies".

    Returns:
        A mapping from selector parameter id to its declared codes.

    Raises:
        TransactionValidationError: If a selector is absent or malformed, if the
            same code appears in two selectors, or if the catalogue cannot load.
    """
    selectors = {
        parameter_id: _typed_code_set(
            resolve_tipo_actividad_selector(parameter_id, effective_date=date.today()),
        )
        for parameter_id in _ART_95_SELECTORS
    }

    seen: dict[TipoActividad, str] = {}
    for parameter_id, codes in selectors.items():
        for code in codes:
            previous = seen.get(code)
            if previous is not None:
                raise TransactionValidationError(
                    f"Modelo 036 code {code.value!r} is declared by both {previous!r} and "
                    f"{parameter_id!r}; a code must select at most one art. 95 arm",
                )
            seen[code] = parameter_id
    return selectors
