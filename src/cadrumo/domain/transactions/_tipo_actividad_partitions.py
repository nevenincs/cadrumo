"""Registry-backed resolution of a Modelo 036 activity code to its art. 95 partition.

RIRPF art. 95 fixes a different retención rate per kind of activity, and Modelo 036
codes the taxpayer's activity. Which code selects which apartado is a legal
correspondence, so it lives in the registry as data — the
``rirpf-art-95:selector-m036-*`` parameters in
``registry/aeat/legal/irpf-retencion-actividades.toml``, each carrying its own
``legal_refs`` — and this module reads it. There is deliberately no code-to-partition
mapping written here: a literal map would be a second authority for the same fact,
and the one in the registry is the one that carries its legal basis.

Two of the correspondences would be plausible inferences and are not inferred:

* ``A04 Artísticas y Deportivas`` partitions as professional because art. 95.2.a)
  counts Sección Tercera of the IAE tarifas among rendimientos de actividades
  profesionales alongside Sección Segunda — not because artistic work reads as
  professional.
* ``A02 Ganadería independiente`` partitions as agrícola/ganadera although it sits in
  the IAE-subject half of the M036 table, because art. 95.4 says so outright: *Se
  entenderán incluidas entre las actividades agrícolas y ganaderas: a) La ganadería
  independiente*.

Not every code selects a partition, and the two ways of not selecting are different.
``A01``, ``A03``, ``B04`` and ``B05`` genuinely have no art. 95 rate — arrendamiento
retains under art. 100, and resto empresariales, mejillón and pesquera reach art. 95
only through apartado 6.1.º by estimación objetiva, which is a method axis rather than
an activity one. The engorde de porcino y avicultura carve-out is the other case: it
is a real partition that this table cannot select, because its finest livestock grain
is ``B02 Ganadera``. The registry carries it with an empty code set so the gap is
visible, and :func:`art_95_partition_for` returns ``None`` for a livestock code rather
than pretending the general 2 % is settled.

See Also:
    :class:`~core.TipoActividad`
        The closed code set this resolves from.
    :mod:`~domain.transactions._retencion_parameters`
        Reads the rates these partitions select.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import TYPE_CHECKING, Final

from ...core import TipoActividad
from ...core.resources import bundled_path
from ._errors import TransactionValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "Art95ActivityPartition",
    "art_95_partition_for",
    "load_tipo_actividad_partitions",
]


class Art95ActivityPartition(StrEnum):
    """One RIRPF art. 95 activity partition a Modelo 036 code can select.

    Attributes:
        PROFESIONAL: art. 95.1 — 15 % general, 7 % in the inicio period.
        AGRICOLA_GANADERA: art. 95.4.2.º — 2 %.
        FORESTAL: art. 95.5 — 2 %. Equal in value to the agrícola/ganadera rate but
            fixed by its own apartado, so it stays a distinct partition.
        GANADERA_ENGORDE_PORCINO_AVICULTURA: art. 95.4.1.º — 1 %. Declared for
            completeness of the partition set; no Modelo 036 code selects it.
    """

    PROFESIONAL = "profesional"
    AGRICOLA_GANADERA = "agricola_ganadera"
    FORESTAL = "forestal"
    GANADERA_ENGORDE_PORCINO_AVICULTURA = "ganadera_engorde_porcino_avicultura"


_SELECTOR_PARAM_IDS: Final[Mapping[Art95ActivityPartition, str]] = {
    Art95ActivityPartition.PROFESIONAL: "rirpf-art-95:selector-m036-actividades-profesionales",
    Art95ActivityPartition.AGRICOLA_GANADERA: "rirpf-art-95:selector-m036-actividades-agricolas-ganaderas",
    Art95ActivityPartition.FORESTAL: "rirpf-art-95:selector-m036-actividades-forestales",
    Art95ActivityPartition.GANADERA_ENGORDE_PORCINO_AVICULTURA: (
        "rirpf-art-95:selector-m036-actividades-ganaderas-engorde-porcino-avicultura"
    ),
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


@lru_cache(maxsize=1)
def load_tipo_actividad_partitions() -> Mapping[Art95ActivityPartition, frozenset[TipoActividad]]:
    """Return the registry-declared code set for every art. 95 activity partition.

    Every partition is present, including the engorde carve-out whose set is empty.
    An empty set is data, not an absence: it records that the Modelo 036 axis cannot
    reach that partition, which is why callers must not treat a code's absence from
    the other sets as "no rate applies".

    Returns:
        A mapping from partition to the codes that select it.

    Raises:
        TransactionValidationError: If a selector parameter is absent or malformed,
            if the same code selects two partitions, or if the registry parameter
            catalogue cannot be loaded.
    """
    # Imported inside the function for the reason the retención-rate loader gives:
    # the registry import path reaches back into the domain packages this module
    # belongs to, and a module-level import would close that cycle.
    from ..calculations.registry import RegistryError, load_legal_parameters_only

    try:
        parameters = load_legal_parameters_only(bundled_path("registry", "aeat"))
    except RegistryError as exc:
        raise TransactionValidationError(
            f"failed to load the Modelo 036 activity selectors: {exc}",
        ) from exc

    partitions = {
        partition: _code_set(parameters, parameter_id)
        for partition, parameter_id in _SELECTOR_PARAM_IDS.items()
    }

    seen: dict[TipoActividad, Art95ActivityPartition] = {}
    for partition, codes in partitions.items():
        for code in codes:
            previous = seen.get(code)
            if previous is not None:
                raise TransactionValidationError(
                    f"Modelo 036 code {code.value!r} selects both {previous.value!r} and "
                    f"{partition.value!r}; a code must select at most one art. 95 partition",
                )
            seen[code] = partition
    return partitions


def art_95_partition_for(tipo: TipoActividad) -> Art95ActivityPartition | None:
    """Return the art. 95 partition a Modelo 036 code selects, if any.

    Args:
        tipo: The declared Modelo 036 activity code.

    Returns:
        The selected partition, or ``None`` for ``A01``, ``A03``, ``B04`` and
        ``B05``, which art. 95 fixes no rate for.

        A livestock code returns
        :attr:`Art95ActivityPartition.AGRICOLA_GANADERA`, and that answer carries a
        caveat this function cannot express: art. 95.4.1.º carves *engorde de
        porcino y avicultura* out at 1 %, and no Modelo 036 code distinguishes it
        from the 2 % general case. A caller that applies the returned partition's
        rate to a livestock row is right for every livestock filer except an
        engordador. Where that difference matters, the discriminator has to come
        from somewhere other than this axis.

    Raises:
        TransactionValidationError: If the registry selectors cannot be loaded.
    """
    for partition, codes in load_tipo_actividad_partitions().items():
        if tipo in codes:
            return partition
    return None
