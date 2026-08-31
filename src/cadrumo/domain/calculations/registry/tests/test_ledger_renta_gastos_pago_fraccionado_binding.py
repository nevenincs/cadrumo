"""Tests for the ledger-backed Modelo 130 gastos (casilla 02) registry binding.

Pins the committed M130 casilla 02 contract: the casilla binds
``modelo-130-actividad-economica-gastos-cumulative``, source
``ledger_renta_gastos_pago_fraccionado_aggregation``, fact
``deductible_amount_sum``. Also covers
:func:`resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values`
and :func:`unsupported_ledger_renta_gastos_pago_fraccionado_observations`
after their refactor onto the shared
:func:`~....registry._ledger_binding_resolution.resolve_ledger_family_binding_values`
/ :func:`~....registry._ledger_binding_resolution.unsupported_ledger_family_observations`
skeleton (F15): a real registry revision, a worked-example Decimal sum
independent of the resolver under test, and off-casilla / zero-amount
observations proving the shared predicate and false-fire guard still hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources._boundary import bundled_path
from ..binding_selector_utils import selector_as_dict
from ..ledger_bindings import (
    resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values,
    unsupported_ledger_renta_gastos_pago_fraccionado_observations,
    validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition,
)
from ..snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_GASTOS_BINDING = "modelo-130-actividad-economica-gastos-cumulative"
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id(
    "03",
    surface="_M130_RENDIMIENTO_NETO_CASILLA",
)


@dataclass(frozen=True)
class _GastoObservation:
    """Minimal stand-in satisfying ``RentaGastosPagoFraccionadoObservationProtocol``.

    Deliberately local and application-layer-free: the resolver only reads
    ``target_casilla_id`` / ``deductible_amount``, and a domain-layer test
    should not reach into ``application.aggregation`` internals to get them.
    """

    target_casilla_id: CasillaId
    deductible_amount: Decimal


def _modelo_130_snapshot():
    modelo, catalogues = _committed_modelo("130")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )


def test_committed_m130_casilla_02_binds_gastos_pago_fraccionado_fact() -> None:
    """The committed registry routes casilla 02 through deductible_amount_sum."""
    revision = _modelo_130_snapshot().revision

    casilla_02 = next(casilla for casilla in revision.casillas if casilla.id == _M130_GASTOS_CASILLA)
    assert casilla_02.binding == _GASTOS_BINDING

    binding = next(binding for binding in revision.bindings if binding.id == _GASTOS_BINDING)
    assert binding.source == "ledger_renta_gastos_pago_fraccionado_aggregation"
    assert selector_as_dict(binding)["fact"] == "deductible_amount_sum"
    validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition(binding)


def test_resolver_sums_matching_casilla_and_excludes_other_casilla() -> None:
    """Casilla 02's binding sums only observations targeting casilla 02.

    Worked example (mirrors the grounded application-layer aggregation
    regression in ``test_domain_resolver_folds_gasto_observations_into_the_
    m130_casilla_02_binding``): two deductible bases feeding casilla 02
    (147.93 + 100.00 = 247.93) plus a third observation carrying a
    distinguishing, non-coincidental amount routed to casilla 03. The
    expected total is derived from the two casilla-02 inputs alone, never
    copied from what the resolver under test returns — a regression that
    folded every observation regardless of ``target_casilla_id`` would
    produce 247.93 + 63.10 = 311.03, a different, checkable number.
    """
    revision = _modelo_130_snapshot().revision
    binding = next(binding for binding in revision.bindings if binding.id == _GASTOS_BINDING)

    feb_base, apr_base = Decimal("147.93"), Decimal("100.00")
    off_casilla_base = Decimal("63.10")
    feb = _GastoObservation(target_casilla_id=_M130_GASTOS_CASILLA, deductible_amount=feb_base)
    apr = _GastoObservation(target_casilla_id=_M130_GASTOS_CASILLA, deductible_amount=apr_base)
    off_casilla = _GastoObservation(
        target_casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
        deductible_amount=off_casilla_base,
    )

    resolved = resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(
        revision,
        (feb, apr, off_casilla),
    )

    assert resolved[binding.id] == feb_base + apr_base
    assert resolved[binding.id] != feb_base + apr_base + off_casilla_base, (
        "an observation routed to casilla 03 must not feed the casilla 02 binding"
    )


def test_resolver_returns_zero_for_binding_with_no_matching_observations() -> None:
    """A binding whose casilla receives no observations resolves to zero, not a missing key."""
    revision = _modelo_130_snapshot().revision
    binding = next(binding for binding in revision.bindings if binding.id == _GASTOS_BINDING)

    off_casilla = _GastoObservation(
        target_casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
        deductible_amount=Decimal("50.00"),
    )

    resolved = resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(revision, (off_casilla,))

    assert resolved[binding.id] == Decimal("0")


def test_unsupported_flags_non_zero_gasto_routed_to_no_binding() -> None:
    """A non-zero deductible expense whose target_casilla_id matches no binding is surfaced.

    Every committed M130 gastos binding selects casilla 02; an observation
    routed to casilla 03 reaches no binding and would silently vanish from
    the filing, so the fail-closed screen MUST report it
    (no-silent-under-declaration).
    """
    revision = _modelo_130_snapshot().revision

    routed = _GastoObservation(target_casilla_id=_M130_GASTOS_CASILLA, deductible_amount=Decimal("150.00"))
    unrouted = _GastoObservation(
        target_casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
        deductible_amount=Decimal("75.00"),
    )

    result = unsupported_ledger_renta_gastos_pago_fraccionado_observations(revision, (routed, unrouted))

    assert result == (unrouted,)


def test_unsupported_does_not_flag_zero_deductible_amount() -> None:
    """A zero-deductible-amount observation routed to no binding must NOT false-fire.

    A zero declarable gasto contributes nothing whether or not it is
    routed, so the false-fire guard excludes it even when its
    target_casilla_id is unbound.
    """
    revision = _modelo_130_snapshot().revision

    zero_unrouted = _GastoObservation(
        target_casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
        deductible_amount=Decimal("0.00"),
    )

    result = unsupported_ledger_renta_gastos_pago_fraccionado_observations(revision, (zero_unrouted,))

    assert result == ()


def test_committed_binding_passes_the_reachability_probe() -> None:
    """The real committed casilla-02 binding is reachable: the design proof's positive case.

    The first-family reachability probe runs inside
    ``validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition``,
    already exercised by ``test_committed_m130_casilla_02_binds_gastos_pago_
    fraccionado_fact`` above -- this test names the probe explicitly so a
    future reader does not have to infer that the committed binding's
    build-time validation now includes it.
    """
    revision = _modelo_130_snapshot().revision
    binding = next(binding for binding in revision.bindings if binding.id == _GASTOS_BINDING)

    validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition(binding)


def test_reachability_probe_is_not_tautological_against_a_mistyped_casilla_id() -> None:
    """The probe compares typed values, not coerced ones: a str/int casilla-id mismatch reddens.

    The matcher this family builds is a pure equality on ``target_casilla_id``,
    so the probe's own honesty rests entirely on comparing REAL typed values
    rather than silently coercing them equal. This proves that discipline
    directly: a probe observation whose ``target_casilla_id`` is the same
    digits but the WRONG type (``int`` where the registry's ``CasillaId`` is
    always a ``str``) must fail to match, exactly as real ledger data typed
    incorrectly upstream would fail to match in production. If this test
    passed, the probe would be validating "same digits" rather than "the
    real matcher accepts this shape", which is not the contract it claims.
    """
    from ..ledger_bindings import _renta_gastos_pago_fraccionado_build_matcher

    revision = _modelo_130_snapshot().revision
    binding = next(binding for binding in revision.bindings if binding.id == _GASTOS_BINDING)
    selector_dict = selector_as_dict(binding)
    from ..ledger_bindings import _RentaLedgerGastosPagoFraccionadoSelector

    selector = _RentaLedgerGastosPagoFraccionadoSelector.model_validate(selector_dict)
    matcher = _renta_gastos_pago_fraccionado_build_matcher(selector)

    mistyped = _GastoObservation(
        target_casilla_id=int(selector.target_casilla_id),  # ty: ignore[invalid-argument-type]  # reason: the wrong type IS the subject under test
        deductible_amount=Decimal("1.00"),
    )
    assert not matcher(mistyped), (
        "the matcher silently coerced an int casilla id equal to the str selector value -- "
        "a real reachability probe must compare typed values, not their string forms"
    )
