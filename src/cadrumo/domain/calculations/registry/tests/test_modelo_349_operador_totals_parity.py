"""Modelo 349 totals-parity gate: the per-operador row set vs the declarant summary casillas.

Modelo 349's declarant-summary scalar casillas (``decl.numero-operadores``,
``decl.importe-operaciones``) and the per-operador-clave row-producer bindings
(``iva-349-operador-row-*``, the AEAT Diseno de Registros Tipo-2 "registro de
operador" detail) are resolved by two structurally INDEPENDENT code paths over
the same :class:`~domain.calculations.registry.InvoiceObservation` set:
:func:`~domain.calculations.registry.resolve_invoice_binding_values` folds
the observations directly into a scalar (``operator_count`` / ``base_sum``
facts), while
:func:`~domain.calculations.registry.resolve_invoice_binding_row_values`
groups them into per-``(country, party_tax_id, clave)`` rows.

Nothing in the registry cross-checks that these two independently-derived
totals agree: the scalar path could produce one figure while the per-operador
row detail (the row-level breakdown an operator or AEAT audit would actually
reconstruct the declarant summary from) sums to a different figure, and
today's engine would silently accept both without complaint
(``no-silent-under-declaration``).

This module drives the REAL registry-loaded Modelo 349 ``2020-y-siguientes``
snapshot and the REAL scalar/row resolvers (no mocks) to prove
:func:`~domain.calculations.registry.compute_modelo_349_operador_totals_parity`:
a consistent observation set (rows reconstruct the resolved scalar summary)
passes, and a dropped operator observation (the row set no longer accounts for
the full summary total) is CAUGHT with the exact delta named, never silently
accepted.

Grounding: Orden HAC/174/2020 Anexo (Diseno de Registros), Tipo 2 "registro de
operador intracomunitario" (posiciones 76-146); the declarant summary
(posiciones 138-161, registro Tipo 1) is defined as an aggregation over the
Tipo 2 records sharing the same clave set (``E``, ``M``, ``H``, ``A``, ``T``,
``S``, ``I``, ``R``, ``D``, ``C``) per the bundled AEAT instructions text
cited by the registry's own ``iva-349-declarante-*`` bindings.

See Also:
    :class:`~domain.calculations.registry.Modelo349OperadorTotalsParity`
        Typed parity verdict asserted by these consistency and shortfall cases.
    :func:`~domain.calculations.registry.resolve_invoice_binding_values`
        Scalar declarant-summary resolver compared against the row set.
    :func:`~domain.calculations.registry.resolve_invoice_binding_row_values`
        Per-operador row resolver whose totals reconstruct the summary.
    :mod:`~domain.calculations.registry._invoice_bindings`
        Invoice-binding implementation that owns the Modelo 349 row and scalar
        aggregation paths.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from .....tests.registry_tree import bundled_registry_tree
from cadrumo.domain.calculations.registry.bindings import InvoiceObservation, Modelo349OperadorTotalsParity, compute_modelo_349_operador_totals_parity, resolve_invoice_binding_values
from ._modelo_349_registry_support import _modelo_349_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CONSISTENT_OBSERVATIONS: tuple[InvoiceObservation, ...] = (
    InvoiceObservation(
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        invoice_id="inv-de-1",
        party_tax_id="DE123456789",
        country_code="DE",
        transaction_date=date(2026, 3, 1),
        base_amount=Decimal("1000.00"),
        intracommunity_clave="E",
        party_legal_name="DE Auto GmbH",
    ),
    InvoiceObservation(
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        invoice_id="inv-fr-1",
        party_tax_id="FR12345678901",
        country_code="FR",
        transaction_date=date(2026, 3, 5),
        base_amount=Decimal("500.50"),
        intracommunity_clave="S",
        party_legal_name="Equipement Garage SARL",
    ),
    # Second observation for the SAME (country, party, clave) as the first —
    # AEAT accumulates same-operator-same-clave operations into one Tipo 2
    # record (Orden HAC/174/2020 Anexo instructions), so this must fold into
    # the DE/E row rather than producing a second row.
    InvoiceObservation(
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        invoice_id="inv-de-2",
        party_tax_id="DE123456789",
        country_code="DE",
        transaction_date=date(2026, 3, 12),
        base_amount=Decimal("250.25"),
        intracommunity_clave="E",
        party_legal_name="DE Auto GmbH",
    ),
)
_EXPECTED_OPERATOR_COUNT = Decimal("2")  # distinct (country, party, clave): DE/E, FR/S
_EXPECTED_BASE_TOTAL = Decimal("1000.00") + Decimal("500.50") + Decimal("250.25")  # 1750.75


def test_totals_parity_passes_when_operador_rows_reconstruct_the_summary() -> None:
    """A complete per-operador observation set that sums to the resolved scalar summary is consistent."""
    revision = _modelo_349_revision()
    binding_values = resolve_invoice_binding_values(revision, _CONSISTENT_OBSERVATIONS)

    operator_summary_total = binding_values["iva-349-declarante-numero-operadores"]
    base_summary_total = binding_values["iva-349-declarante-importe-operaciones"]
    assert operator_summary_total == _EXPECTED_OPERATOR_COUNT
    assert base_summary_total == _EXPECTED_BASE_TOTAL

    parity = compute_modelo_349_operador_totals_parity(
        revision,
        _CONSISTENT_OBSERVATIONS,
        operator_summary_total=operator_summary_total,
        base_summary_total=base_summary_total,
    )

    assert isinstance(parity, Modelo349OperadorTotalsParity)
    assert parity.is_consistent
    assert parity.operator_delta == 0
    assert parity.base_delta == Decimal("0.00")
    assert parity.operator_row_total == 2
    assert parity.base_row_total == _EXPECTED_BASE_TOTAL

    # Per-clave breakdown must reconstruct DE/E (accumulated) and FR/S separately.
    by_clave = {entry.clave: entry for entry in parity.by_clave}
    assert set(by_clave) == {"E", "S"}
    assert by_clave["E"].operator_count == 1
    assert by_clave["E"].base_total == Decimal("1000.00") + Decimal("250.25")
    assert by_clave["S"].operator_count == 1
    assert by_clave["S"].base_total == Decimal("500.50")


def test_totals_parity_catches_a_dropped_operator_observation() -> None:
    """Dropping one operator's observation under-declares the row-level total below the summary.

    Grounded regression for the totals-parity gap: prior to this gate, the
    per-operador row-producer bindings and the declarant-summary scalar
    bindings were never cross-checked against each other, so an observation
    silently dropped between the two resolvers (a data-loss bug, an
    incomplete invoice sync, or a divergent manual-entry set) produced no
    finding at all. The scalar summary here is computed from the FULL
    consistent set (as a real declarant summary would already reflect), but
    the row detail the gate reconstructs from omits the FR/S operator
    entirely — the gate must name the exact shortfall.
    """
    revision = _modelo_349_revision()
    full_binding_values = resolve_invoice_binding_values(revision, _CONSISTENT_OBSERVATIONS)
    incomplete_observations = _CONSISTENT_OBSERVATIONS[:1]  # drop inv-fr-1 and inv-de-2

    parity = compute_modelo_349_operador_totals_parity(
        revision,
        incomplete_observations,
        operator_summary_total=full_binding_values["iva-349-declarante-numero-operadores"],
        base_summary_total=full_binding_values["iva-349-declarante-importe-operaciones"],
    )

    assert not parity.is_consistent
    # Missing FR/S operator: one fewer distinct operator row than the summary claims.
    assert parity.operator_delta == -1
    # Missing base: 500.50 (FR) + 250.25 (second DE observation) = 750.75 under-declared.
    assert parity.base_delta == Decimal("-750.75")
    assert parity.operator_row_total == 1


def test_totals_parity_over_empty_observations_reports_full_shortfall() -> None:
    """No persisted per-operador detail at all is a full shortfall, not a vacuous pass.

    A filer with no intracommunity operations legitimately has zero
    observations AND a zero summary total; this test pins that when the
    summary total is nonzero but the observation set is empty, the gate
    reports the entire summary amount as the delta rather than silently
    treating "no observations" as "nothing to check".
    """
    parity = compute_modelo_349_operador_totals_parity(
        _modelo_349_revision(),
        (),
        operator_summary_total=_EXPECTED_OPERATOR_COUNT,
        base_summary_total=_EXPECTED_BASE_TOTAL,
    )

    assert not parity.is_consistent
    assert parity.operator_row_total == 0
    assert parity.base_row_total == Decimal("0")
    assert parity.operator_delta == -int(_EXPECTED_OPERATOR_COUNT)
    assert parity.base_delta == -_EXPECTED_BASE_TOTAL
    assert parity.by_clave == ()


def test_totals_parity_default_is_exact_equality_not_a_hardcoded_cent() -> None:
    """The DEFAULT tolerance is exact equality, and a genuine one-cent gap is caught by it.

    A caller that resolves no explicit tolerance must not have a one-cent gap
    silently absorbed by this function's own default. A prior version of that
    default was a hardcoded cent, which would have masked exactly this gap.

    This used to rest on modelo 349 declaring NO verification expectations, the
    argument being that with no published contract there is no authority to
    widen the comparison. The campaign has since authored
    `modelo-349-recapitulativa-verification`, so that premise is simply false
    now and the case failed on it rather than on the default. The replacement is
    stronger rather than weaker: the published expectation declares
    `tolerance = 0.00`, so the registry's own contract AGREES with exact
    equality instead of merely being silent, and the default is pinned against a
    positive statement.
    """
    from .....core.resources import bundled_path
    from .....domain.calculations.registry.tests import build_snapshot

    # Scoped to M349 alone rather than through ``resources().modelos.authority``,
    # whose ``.load()`` validates every modelo in the bundled tree before
    # returning anything.
    modelos, catalogues = bundled_registry_tree()
    modelo = next(item for item in modelos if item.id == "349")
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="01")
    expectations = snapshot.revision.verification_expectations
    assert expectations, "test precondition: modelo 349 must publish its verification expectation"
    assert all(expectation.tolerance == Decimal("0.00") for expectation in expectations), (
        "the published contract must declare exact equality, which is what this default mirrors"
    )

    revision = _modelo_349_revision()

    one_cent_off = compute_modelo_349_operador_totals_parity(
        revision,
        _CONSISTENT_OBSERVATIONS,
        operator_summary_total=_EXPECTED_OPERATOR_COUNT,
        base_summary_total=_EXPECTED_BASE_TOTAL + Decimal("0.01"),
    )
    assert not one_cent_off.is_consistent, "the default must not silently absorb a genuine one-cent divergence"
    assert one_cent_off.base_delta == Decimal("-0.01")


def test_totals_parity_tolerance_absorbs_sub_cent_rounding_only() -> None:
    """A one-cent delta is within an EXPLICITLY PASSED tolerance; a two-cent delta is not.

    Pure unit-level boundary check on the comparison primitive itself (no
    resolver dependency) — the monetary tolerance is symmetric and exclusive
    of the boundary+epsilon. Passed explicitly rather than relied on as a
    default, because the registry (not this test) is the authority for what
    value a real caller resolves. The operator-count axis is an exact
    integer match with no tolerance.
    """
    revision = _modelo_349_revision()

    within_tolerance = compute_modelo_349_operador_totals_parity(
        revision,
        _CONSISTENT_OBSERVATIONS,
        operator_summary_total=_EXPECTED_OPERATOR_COUNT,
        base_summary_total=_EXPECTED_BASE_TOTAL + Decimal("0.01"),
        tolerance=Decimal("0.01"),
    )
    assert within_tolerance.is_consistent

    beyond_tolerance = compute_modelo_349_operador_totals_parity(
        revision,
        _CONSISTENT_OBSERVATIONS,
        operator_summary_total=_EXPECTED_OPERATOR_COUNT,
        base_summary_total=_EXPECTED_BASE_TOTAL + Decimal("0.02"),
        tolerance=Decimal("0.01"),
    )
    assert not beyond_tolerance.is_consistent
    assert beyond_tolerance.base_delta == Decimal("-0.02")

    operator_mismatch = compute_modelo_349_operador_totals_parity(
        revision,
        _CONSISTENT_OBSERVATIONS,
        operator_summary_total=_EXPECTED_OPERATOR_COUNT + 1,
        base_summary_total=_EXPECTED_BASE_TOTAL,
    )
    assert not operator_mismatch.is_consistent
    assert operator_mismatch.operator_delta == -1
