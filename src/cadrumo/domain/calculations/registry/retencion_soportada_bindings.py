"""The suffered-withholding binding family: provider, class-to-role table and validators.

A ``retencion_soportada`` binding names an income class and a quantity; it never
names a casilla, a casilla number or a modelo. Which casilla a class may fill is
read from the casilla's own semantic role and checked against
:data:`RETENCION_SOPORTADA_CREDIT_ROLES`, so a wrong registry role is a build
failure rather than a silent misroute.

The credit set of a revision is derived, never listed: it is the operand set of
the formula that totals the payments on account, which is the casilla whose role
is :data:`TOTAL_PAGOS_A_CUENTA_ROLE`. A ``pago_a_cuenta`` binding outside that
set is refused.

The family is the perceptor's side only. Its provider carries no source modelo,
so no withholding-agent return can be named as its source;
:class:`ModeloRevision`, the registry revision a modelo is calculated against.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Final, Literal

from pydantic import BaseModel, BeforeValidator

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.retencion_soportada import RetencionSoportadaCantidad, RetencionSoportadaClase
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import provider_member
from .binding_value_contract import BindingDataType, BindingValueChannel
from .runtime_graph import expression_binding_refs, expression_casilla_refs
from .schema_base import coerce_enum_member
from .schema_input_kind import InputKind

if TYPE_CHECKING:
    from .ids import BindingId
    from .schema import BindingDefinition, ModeloRevision

__all__ = [
    "RETENCION_SOPORTADA_CREDIT_ROLES",
    "RETENCION_SOPORTADA_INCOME_ROLES",
    "TOTAL_PAGOS_A_CUENTA_ROLE",
    "RetencionSoportadaProvider",
    "credit_borrador_participation_failures",
    "credit_casilla_ids",
    "retencion_soportada_bindings",
    "retencion_soportada_revision_failures",
    "revision_declares_retencion_soportada",
    "validate_retencion_soportada_binding",
]

TOTAL_PAGOS_A_CUENTA_ROLE: Final[str] = "irpf_total_pagos_cuenta"
"""The semantic role of the casilla that totals the payments on account."""

RETENCION_SOPORTADA_CREDIT_ROLES: Final[Mapping[RetencionSoportadaClase, frozenset[str]]] = MappingProxyType(
    {
        RetencionSoportadaClase.TRABAJO: frozenset({"irpf_retencion_trabajo"}),
        RetencionSoportadaClase.CAPITAL_MOBILIARIO: frozenset({"irpf_retencion_capital_mobiliario"}),
        RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO: frozenset(
            {"irpf_retencion_arrendamientos_inmuebles_urbanos"},
        ),
        RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO_ACTIVIDAD: frozenset(
            {"irpf_retencion_arrendamientos_inmuebles_urbanos"},
        ),
        RetencionSoportadaClase.ACTIVIDAD_ECONOMICA: frozenset({"irpf_retencion_actividades_economicas"}),
        RetencionSoportadaClase.GANANCIA_PATRIMONIAL: frozenset({"irpf_retencion_ganancias_patrimoniales_premios"}),
        RetencionSoportadaClase.ATRIBUCION_CAPITAL_MOBILIARIO: frozenset(
            {"irpf_retencion_atribuida_capital_mobiliario"},
        ),
        RetencionSoportadaClase.ATRIBUCION_CAPITAL_INMOBILIARIO: frozenset(
            {"irpf_retencion_atribuida_capital_inmobiliario"},
        ),
        RetencionSoportadaClase.ATRIBUCION_ACTIVIDAD_ECONOMICA: frozenset(
            {"irpf_retencion_atribuida_actividades_economicas"},
        ),
        RetencionSoportadaClase.ATRIBUCION_GANANCIA_PATRIMONIAL: frozenset(
            {"irpf_retencion_atribuida_ganancias_patrimoniales"},
        ),
        RetencionSoportadaClase.IMPUTACION_AIE_UTE: frozenset({"irpf_retencion_imputada_aie_ute"}),
        RetencionSoportadaClase.IMPUTACION_DERECHOS_IMAGEN: frozenset({"irpf_ingreso_cuenta_art_92_8"}),
    },
)
"""The credit casilla roles each income class may fill with its ``pago_a_cuenta``.

Total over :class:`~cadrumo.core.retencion_soportada.RetencionSoportadaClase`.
Grounded in the official individual-declaration dictionaries, whose credit block
names one field per class; both urban-rental classes credit the one urban-rental
field, whether or not the rental is an activity (2024 Renta manual, page 1490).
"""

RETENCION_SOPORTADA_INCOME_ROLES: Final[Mapping[tuple[RetencionSoportadaClase, RetencionSoportadaCantidad], str]] = (
    MappingProxyType(
        {
            (
                RetencionSoportadaClase.TRABAJO,
                RetencionSoportadaCantidad.IMPORTE_INTEGRO_DINERARIO,
            ): "irpf_rendimiento_trabajo_importe_integro_dinerario",
            (
                RetencionSoportadaClase.TRABAJO,
                RetencionSoportadaCantidad.VALORACION_ESPECIE,
            ): "irpf_rendimiento_trabajo_especie_valoracion",
            (
                RetencionSoportadaClase.TRABAJO,
                RetencionSoportadaCantidad.INGRESO_A_CUENTA,
            ): "irpf_rendimiento_trabajo_especie_ingreso_cuenta",
            (
                RetencionSoportadaClase.TRABAJO,
                RetencionSoportadaCantidad.INGRESO_A_CUENTA_REPERCUTIDO,
            ): "irpf_rendimiento_trabajo_especie_ingreso_cuenta_repercutido",
            (
                RetencionSoportadaClase.TRABAJO,
                RetencionSoportadaCantidad.REDUCCIONES_APLICABLES,
            ): "irpf_rendimiento_trabajo_reduccion",
            (
                RetencionSoportadaClase.TRABAJO,
                RetencionSoportadaCantidad.GASTOS_DEDUCIBLES,
            ): "irpf_rendimiento_trabajo_gasto_ss_mutualidad",
        },
    )
)
"""The one income casilla role each (income class, quantity) pair may fill, closed.

A quantity other than the credit is admitted only through this table, so no other
class draws an income figure and no other quantity (``importe_integro``, the
combined cross-check, included) reaches a casilla. The roles come from the
payer certificate's own fields as the official individual-declaration
dictionaries name them.
"""

_INCOME_ROLE_PAIRS: Final[Mapping[str, tuple[RetencionSoportadaClase, RetencionSoportadaCantidad]]] = MappingProxyType(
    {role: pair for pair, role in RETENCION_SOPORTADA_INCOME_ROLES.items()}
)


class RetencionSoportadaProvider(BaseModel):
    """Validated form of a ``retencion_soportada`` binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.RETENCION_SOPORTADA] = BindingSourceKind.RETENCION_SOPORTADA
    income_class: Annotated[RetencionSoportadaClase, BeforeValidator(coerce_enum_member(RetencionSoportadaClase))]
    quantity: Annotated[RetencionSoportadaCantidad, BeforeValidator(coerce_enum_member(RetencionSoportadaCantidad))]


def validate_retencion_soportada_binding(binding: BindingDefinition) -> list[str]:
    """Return the build-time diagnostics for one ``retencion_soportada`` binding.

    The resolver adds up the drawn quantity of every record of the class, so the
    value is money on the decimal channel and the operation is a sum.
    """
    provider_member(binding, RetencionSoportadaProvider)
    failures: list[str] = []
    if binding.value.data_type is not BindingDataType.MONEY:
        failures.append(
            f"binding {binding.id!r} (source={binding.source!r}): value data_type must be money, "
            f"not {binding.value.data_type.value!r}",
        )
    if binding.value.channel is not BindingValueChannel.DECIMAL:
        failures.append(
            f"binding {binding.id!r} (source={binding.source!r}): value channel must be decimal, "
            f"not {binding.value.channel.value!r}",
        )
    if binding_aggregation_op(binding) is not BindingAggregationOp.SUM:
        failures.append(
            f"binding {binding.id!r} (source={binding.source!r}): the resolver sums the records of its class, "
            f"so the aggregation operation must be sum, not {binding_aggregation_op(binding).value!r}",
        )
    return failures


def retencion_soportada_bindings(
    revision: ModeloRevision,
) -> tuple[tuple[BindingDefinition, RetencionSoportadaProvider], ...]:
    """Return every family binding of ``revision`` beside its typed provider, in declaration order.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    return tuple(
        (binding, provider_member(binding, RetencionSoportadaProvider))
        for binding in revision.bindings
        if binding.source is BindingSourceKind.RETENCION_SOPORTADA
    )


def revision_declares_retencion_soportada(revision: ModeloRevision) -> bool:
    """Return whether ``revision`` declares any member of the family.

    A revision that declares none reads nothing from the family's store, which
    is a different fact from reading the store and finding it empty.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    return any(binding.source is BindingSourceKind.RETENCION_SOPORTADA for binding in revision.bindings)


def credit_casilla_ids(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return the casillas the payments-on-account total is built from.

    Empty when the revision has no casilla with :data:`TOTAL_PAGOS_A_CUENTA_ROLE`
    or no formula targeting it, so a credit binding there is refused rather
    than admitted by default.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    totals = frozenset(
        casilla.id for casilla in revision.casillas if casilla.semantic_role == TOTAL_PAGOS_A_CUENTA_ROLE
    )
    return frozenset(
        operand
        for formula in revision.formulas
        if formula.target_casilla_id in totals
        for operand in expression_casilla_refs(formula.expression)
    )


def _target_casilla_ids(revision: ModeloRevision, binding_id: BindingId) -> tuple[CasillaId, ...]:
    """Return every casilla the binding's value lands in: bound directly, or as a formula operand."""
    targets: list[CasillaId] = [
        casilla.id
        for casilla in revision.casillas
        if casilla.binding == binding_id or binding_id in casilla.alternate_bindings
    ]
    targets.extend(
        formula.target_casilla_id
        for formula in revision.formulas
        if binding_id in expression_binding_refs(formula.expression)
    )
    return tuple(dict.fromkeys(targets))


def _computed_casilla_failures(revision: ModeloRevision, binding: BindingDefinition) -> list[str]:
    failures: list[str] = []
    for casilla in revision.casillas:
        if casilla.input_kind is InputKind.COMPUTED and (
            casilla.binding == binding.id or binding.id in casilla.alternate_bindings
        ):
            failures.append(
                f"binding {binding.id!r} is bound to computed casilla {casilla.id!r}; a computed casilla takes "
                "a family value only as a formula operand",
            )
    return failures


def _credit_target_failures(
    binding: BindingDefinition,
    provider: RetencionSoportadaProvider,
    credit_set: frozenset[CasillaId],
    target_id: CasillaId,
    role: str | None,
) -> list[str]:
    failures: list[str] = []
    if target_id not in credit_set:
        failures.append(
            f"binding {binding.id!r} draws pago_a_cuenta into casilla {target_id!r}, which is not an "
            f"operand of the {TOTAL_PAGOS_A_CUENTA_ROLE!r} total",
        )
    if role not in RETENCION_SOPORTADA_CREDIT_ROLES[provider.income_class]:
        failures.append(
            f"binding {binding.id!r}: income class {provider.income_class.value!r} does not credit "
            f"casilla {target_id!r} with role {role!r}",
        )
    return failures


def _income_reach_failures(revision: ModeloRevision, binding: BindingDefinition) -> list[str]:
    """Return the refusals of an income binding read other than directly by one casilla."""
    failures: list[str] = []
    if binding.aeat_prefilled:
        failures.append(f"binding {binding.id!r} is an income binding and cannot be aeat_prefilled")
    if any(binding.id in expression_binding_refs(formula.expression) for formula in revision.formulas):
        failures.append(f"binding {binding.id!r} is an income binding and cannot be a formula operand")
    failures.extend(
        f"binding {binding.id!r} is an alternate binding of casilla {casilla.id!r}; an income binding is the "
        "only source of its casilla"
        for casilla in revision.casillas
        if binding.id in casilla.alternate_bindings
    )
    return failures


def _income_target_failures(
    revision: ModeloRevision,
    binding: BindingDefinition,
    provider: RetencionSoportadaProvider,
    expected: str,
) -> list[str]:
    """Return the refusals of an income binding whose directly bound casillas are not the pair's role."""
    direct = [casilla for casilla in revision.casillas if casilla.binding == binding.id]
    if not direct:
        return [
            f"binding {binding.id!r} is an income binding and fills a casilla of role {expected!r} directly; "
            "no casilla binds it",
        ]
    return [
        f"binding {binding.id!r}: casilla {casilla.id!r} has role {casilla.semantic_role!r}, but "
        f"{provider.quantity.value!r} of income class {provider.income_class.value!r} fills role {expected!r}"
        for casilla in direct
        if casilla.semantic_role != expected
    ]


def _income_binding_failures(
    revision: ModeloRevision,
    binding: BindingDefinition,
    provider: RetencionSoportadaProvider,
) -> list[str]:
    """Return the refusals of a binding that draws an income quantity rather than the credit.

    The pair must be in :data:`RETENCION_SOPORTADA_INCOME_ROLES`; the binding is
    the only source of exactly one casilla of that pair's role, never an
    operand, an alternate, or a borrador-supplied value.
    """
    expected = RETENCION_SOPORTADA_INCOME_ROLES.get((provider.income_class, provider.quantity))
    if expected is None:
        return [
            f"binding {binding.id!r}: quantity {provider.quantity.value!r} of income class "
            f"{provider.income_class.value!r} is admitted on no casilla role",
        ]
    return [
        *_income_reach_failures(revision, binding),
        *_income_target_failures(revision, binding, provider, expected),
    ]


def _one_source_per_figure_failures(revision: ModeloRevision) -> list[str]:
    """Return a refusal for each casilla of an income role that does not take exactly its family binding."""
    family_pairs = {
        binding.id: (provider.income_class, provider.quantity)
        for binding, provider in retencion_soportada_bindings(revision)
    }
    if not any(pair in RETENCION_SOPORTADA_INCOME_ROLES for pair in family_pairs.values()):
        return []
    failures: list[str] = []
    for casilla in revision.casillas:
        pair = _INCOME_ROLE_PAIRS.get(casilla.semantic_role or "")
        if pair is None:
            continue
        if casilla.binding is None or family_pairs.get(casilla.binding) != pair or casilla.alternate_bindings:
            failures.append(
                f"casilla {casilla.id!r} has income role {casilla.semantic_role!r}, which the "
                f"retencion_soportada family fills once it declares an income binding; the casilla must take "
                f"exactly its family binding for {pair[1].value!r} of income class {pair[0].value!r}",
            )
    return failures


def _binding_failures(
    revision: ModeloRevision,
    binding: BindingDefinition,
    provider: RetencionSoportadaProvider,
    credit_set: frozenset[CasillaId],
) -> list[str]:
    failures = _computed_casilla_failures(revision, binding)
    if provider.quantity is not RetencionSoportadaCantidad.PAGO_A_CUENTA:
        failures.extend(_income_binding_failures(revision, binding, provider))
        return failures
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    for target_id in _target_casilla_ids(revision, binding.id):
        target = casillas.get(target_id)
        role = None if target is None else target.semantic_role
        failures.extend(_credit_target_failures(binding, provider, credit_set, target_id, role))
    return failures


def retencion_soportada_revision_failures(revision: ModeloRevision) -> tuple[str, ...]:
    """Return every refusal the family's bindings earn against the revision they sit in.

    These checks need the casillas and formulas around a binding, which a
    per-binding validator does not see: the target's semantic role must be one
    the income class admits, a credit must land in the derived credit set, a
    computed casilla takes a family value only through its formula, an income
    quantity fills only the casilla of its table role as that casilla's sole
    source, and once any income binding is declared every casilla of an income
    role takes exactly its family binding.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    family = retencion_soportada_bindings(revision)
    if not family:
        return ()
    credit_set = credit_casilla_ids(revision)
    failures: list[str] = []
    for binding, provider in family:
        failures.extend(_binding_failures(revision, binding, provider, credit_set))
    failures.extend(_one_source_per_figure_failures(revision))
    return tuple(failures)


def credit_borrador_participation_failures(revision: ModeloRevision) -> tuple[str, ...]:
    """Return a refusal for each binding that would let the borrador supply a credit casilla.

    The borrador is informative: a payer's omission or error there must never
    become the credited figure. A binding whose value lands in the derived
    credit set, bound directly or as a formula operand, may therefore be held
    by a borrador snapshot only as ``cross_check_only``, so the snapshot
    corroborates the evidenced value and never stands in for a missing one.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    credit_set = credit_casilla_ids(revision)
    if not credit_set:
        return ()
    failures: list[str] = []
    for binding in revision.bindings:
        if not binding.borrador_supplies_value:
            continue
        reached = sorted(str(target) for target in _target_casilla_ids(revision, binding.id) if target in credit_set)
        if reached:
            failures.append(
                f"binding {binding.id!r} is aeat_prefilled with borrador precedence and reaches credit casilla(s) "
                f"{reached}; a borrador value may only cross-check a credit, so declare "
                "borrador_participation = 'cross_check_only'",
            )
    return tuple(failures)
