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
from ..invoice_bindings import (
    InvoiceObservation,
)

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
