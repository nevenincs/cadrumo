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
    :mod:`~domain.transactions._retencion_parameters`
        Reads the rates each arm selects.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Final

from ...core import TipoActividad
from ...core.resources import bundled_path
from ..deadlines import IrpfActivityKind
from .errors import TransactionValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "irpf_activity_kind_for",
    "load_tipo_actividad_selectors",
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


def tipo_actividad_code_set(parameter_id: str) -> frozenset[TipoActividad]:
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
    return _code_set(_legal_parameters(), parameter_id)


def _legal_parameters() -> Mapping[str, object]:
    """Load the registry parameter catalogue, translating its failure.

    Raises:
        TransactionValidationError: If the catalogue cannot be loaded.
    """
    # Imported inside the function for the reason the retención-rate loader gives:
    # the registry import path reaches back into the domain packages this module
    # belongs to, and a module-level import would close that cycle.
    from ..calculations.registry import RegistryError, load_legal_parameters_only

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
    parameters = _legal_parameters()
    selectors = {parameter_id: _code_set(parameters, parameter_id) for parameter_id in _ART_95_SELECTORS}

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


def irpf_activity_kind_for(tipo: TipoActividad) -> IrpfActivityKind | None:
    """Return the art. 95 retención arm a Modelo 036 activity code falls in.

    This is the derivation :class:`IrpfActivityKind` was declared operator-only
    for. The authority was never the obstacle -- the registry has carried the
    code-to-arm correspondence with its own ``legal_refs`` since the art. 95
    selectors landed -- the missing piece was an input, and a declared
    ``tipo_actividad`` on a ledger row is one.

    Args:
        tipo: The declared Modelo 036 activity code.

    Returns:
        :attr:`IrpfActivityKind.PROFESIONAL` for the codes art. 95.1 covers,
        :attr:`IrpfActivityKind.SECTORIAL` for the agrarian and forestal ones, and
        ``None`` for ``A01``, ``A03``, ``B04`` and ``B05``, which art. 95 fixes no
        rate for at all -- arrendamiento retains under art. 100, and the other
        three reach art. 95 only through apartado 6.1.º by estimación objetiva,
        which is a method axis rather than an activity one.

        A livestock code returns ``SECTORIAL``, and that answer carries a caveat no
        return value can express: art. 95.4.1.º carves *engorde de porcino y
        avicultura* out at 1 % while the general agrarian rate is 2 %, and no
        Modelo 036 code distinguishes them. ``SECTORIAL`` is right for both; which
        of the two sectoral figures applies is not settled here.

    Raises:
        TransactionValidationError: If the registry selectors cannot be loaded.
    """
    for parameter_id, codes in load_tipo_actividad_selectors().items():
        if tipo in codes:
            return _ART_95_SELECTORS[parameter_id]
    return None
