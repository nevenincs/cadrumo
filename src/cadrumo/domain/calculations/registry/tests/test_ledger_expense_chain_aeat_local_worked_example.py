"""The gasto leg driven by the AEAT worked example, for premises that are a local.

The income leg of this same caso practico is grounded by
``test_ledger_income_chain_aeat_exempt_worked_example``. This module does the
other half: it drives the example's described PURCHASE facts through the
production expense aggregation and the registry's own expense bindings, and
checks the figures the manual prints.

The example (Manual practico de Renta 2024, Parte 1, Cap. 7, caso practico of
the medico radiologo, extracted markdown L19807-L19965). Its gastos, quoted::

    RETA del titular de la actividad             3.300   (L19829)
    Gastos financieros                           1.100   (L19831)
    Tributos no estatales                        1.700   (L19835)
    Suministro electrico                         4.000   (L19838)
    Suministro de agua                             300   (L19839)
    Suministro de gas                            1.000   (L19840)
    Suministro de telefonia e Internet           2.500   (L19841)
    Reparaciones y conservacion                  3.800   (L19843)

The manual's own table then prints "Suministro (electricidad, agua, gas,
telefonia e internet)" as a single 7.800 row in the valores-fiscales column,
which is the figure casilla 0194 has to reach.

**Why the premises matter, and why this module exists.** The taxpayer "ejerce
su actividad profesional exclusivamente en una consulta privada situada en un
local adquirido por el matrimonio" -- a dedicated local, not a home. The
immovable property where the activity is carried on is afecto under LIRPF art.
29.1.a), so its supply costs are ordinary deductible expense under art. 28.1,
in full.

That is a different rule from the one governing a home office. Art. 30.2.5.a b)
grants only 30 % of the affected floor-area proportion, and it is written for
the case "en que el contribuyente afecte parcialmente su vivienda habitual al
desarrollo de la actividad" -- a restrictive carve-out that exists because a
dwelling cannot be exclusively affected. Before ``SUMINISTROS_LOCAL_AFECTO``
existed, the only categories routing to casilla 0194 were the four home-office
ones, so this taxpayer's 7.800 of utility bills resolved to 2.340: an article
that does not govern them, applied at a 5.460 cost. The gate below is what
holds that closed.

**Fixture provenance.** Every row carries an amount the manual states as a
described fact, and the category each expense actually belongs to. Nothing is
derived from the manual's printed 7.800 subtotal -- that is what the chain has
to produce, and what the assertions check.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.ledger_bindings import (
    resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.snapshot import build_snapshot

from .....application.aggregation import aggregate_renta_ledger_expenses
from .....core import CasillaId, Period, validated_casilla_id
from .....core.resources import bundled_path
from ....categories import SpendingCategory
from ....invoices import InvoiceCatalogue
from ....transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FILING_YEAR = 2024
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "0A")
_BUCKET = "8c2f817f-ca4d-4527-97f0-9e71dee6589f"  # was 'bucket-aeat-local-gasto-worked-example'

# The manual's utility lines, each quoted from its own bullet.
_SUMINISTRO_ELECTRICO = Decimal("4000.00")
_SUMINISTRO_AGUA = Decimal("300.00")
_SUMINISTRO_GAS = Decimal("1000.00")
_SUMINISTRO_TELEFONIA = Decimal("2500.00")

#: The manual's printed "Suministro" row in the valores-fiscales column. Stated
#: by the manual on its own account beside the four bullets it aggregates, so
#: it is a published figure rather than this module's arithmetic.
_SUMINISTROS_TOTAL = Decimal("7800.00")

# The other gasto lines that reach a bound first-slice casilla.
_RETA = Decimal("3300.00")
_GASTOS_FINANCIEROS = Decimal("1100.00")
_TRIBUTOS_NO_ESTATALES = Decimal("1700.00")
_REPARACIONES = Decimal("3800.00")

_SUMINISTROS_BINDING = "renta-2024-ledger-expense-0194-deductible"
_RETA_BINDING = "renta-2024-ledger-expense-0186-deductible"
_FINANCIEROS_BINDING = "renta-2024-ledger-expense-0203-deductible"
_TRIBUTOS_BINDING = "renta-2024-ledger-expense-0206-deductible"
_REPARACIONES_BINDING = "renta-2024-ledger-expense-0193-deductible"

#: The casilla the suministros binding populates, asserted below through the
#: revision rather than trusted from the binding id's own name.
_CASILLA_SUMINISTROS: CasillaId = validated_casilla_id("0194", surface="_CASILLA_SUMINISTROS")

#: The example's utility bills, as the operator would classify them: premises
#: used for the activity, not a dwelling partly given over to it.
_SUMINISTRO_ROWS: tuple[tuple[str, Decimal], ...] = (
    ("suministro-electrico", _SUMINISTRO_ELECTRICO),
    ("suministro-agua", _SUMINISTRO_AGUA),
    ("suministro-gas", _SUMINISTRO_GAS),
    ("suministro-telefonia-internet", _SUMINISTRO_TELEFONIA),
)

_OTHER_ROWS: tuple[tuple[str, Decimal, SpendingCategory], ...] = (
    ("reta-titular", _RETA, SpendingCategory.CUOTAS_AUTONOMOS_SS),
    ("gastos-financieros", _GASTOS_FINANCIEROS, SpendingCategory.GASTOS_FINANCIEROS),
    ("tributos-no-estatales", _TRIBUTOS_NO_ESTATALES, SpendingCategory.TRIBUTOS_FISCALMENTE_DEDUCIBLES),
    ("reparaciones-conservacion", _REPARACIONES, SpendingCategory.REPARACIONES_CONSERVACION),
)


def _modelo_100_revision() -> ModeloRevision:
    """The committed Modelo 100 revision the expense bindings resolve against."""
    modelo, catalogues = _committed_modelo("100")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=_FILING_YEAR,
        period=_PERIOD.registry_token,
    ).revision


def _expense_row(reference: str, amount: Decimal, category: SpendingCategory) -> Transaction:
    """One of the example's purchase facts as a classified ledger row."""
    when = date(_FILING_YEAR, 6, 30)
    raw = RawTransaction(
        provider_transaction_id=reference,
        booked_date=when,
        value_date=when,
        amount=amount,
        currency="EUR",
        counterparty="Proveedor de la consulta",
        description=reference,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_FILING_YEAR, 12, 31, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": reference},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": category.value,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_FILING_YEAR, 12, 31, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _aggregated(*, suministros_category: SpendingCategory = SpendingCategory.SUMINISTROS_LOCAL_AFECTO):
    """Drive the example's purchase facts through the production aggregation."""
    rows = [_expense_row(reference, amount, suministros_category) for reference, amount in _SUMINISTRO_ROWS]
    rows.extend(_expense_row(reference, amount, category) for reference, amount, category in _OTHER_ROWS)
    return aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions(tuple(rows)),
        InvoiceCatalogue(),
        bucket_id=_BUCKET,
        period=_PERIOD,
        modelo="100",
    )


def _resolved(**kwargs) -> dict[str, Decimal]:
    aggregation = _aggregated(**kwargs)
    assert aggregation.issues == (), f"the example's own facts produced aggregation issues: {aggregation.issues}"
    return resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values(
        _modelo_100_revision(),
        aggregation.observations,
    )


def test_the_premises_utilities_reach_the_manuals_printed_subtotal() -> None:
    """0194 = 7.800, the manual's own "Suministro" row.

    The figure is the manual's, stated beside the four bullets it aggregates,
    and the chain has to produce it from those bullets: aggregation, category
    deductibility, and the registry binding all run for real. A rule that
    reduced these bills -- as the home-office carve-out does -- would miss the
    published total rather than quietly agreeing with itself.
    """
    resolved = _resolved()

    assert resolved[_SUMINISTROS_BINDING] == _SUMINISTROS_TOTAL
    assert resolved[_SUMINISTROS_BINDING] == (
        _SUMINISTRO_ELECTRICO + _SUMINISTRO_AGUA + _SUMINISTRO_GAS + _SUMINISTRO_TELEFONIA
    ), "the premises utilities deduct in full, so the box equals the sum of the bills"


def test_the_home_office_carve_out_is_not_applied_to_a_local() -> None:
    """The same bills under a home-office category resolve to 2.340, not 7.800.

    This is the defect the new category closes, pinned as a live contrast
    rather than described. Art. 30.2.5.a b) grants 30 % of the affected
    floor-area proportion of a VIVIENDA HABITUAL; applying it to a dedicated
    local costs this taxpayer 5.460 of deductible expense. Asserting both
    branches in one place is what stops a future edit from quietly routing the
    local case back through the dwelling rule.
    """
    local = _resolved()[_SUMINISTROS_BINDING]
    home_office = _resolved(suministros_category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ)[_SUMINISTROS_BINDING]

    assert local == _SUMINISTROS_TOTAL
    assert home_office == (_SUMINISTROS_TOTAL * Decimal("0.30")).quantize(Decimal("0.01"))
    assert local - home_office == Decimal("5460.00")


def test_the_suministros_binding_targets_the_casilla_this_module_claims() -> None:
    """0194 is where the suministros binding lands, read off the revision.

    Every figure below is discussed as "casilla 0194", but the assertions read
    a BINDING id. If the registry ever repointed that binding at another box,
    this module would keep passing while describing the wrong casilla, and the
    5.460 contrast would be attributed to a box it no longer touches.
    """
    revision = _modelo_100_revision()

    targets = {casilla.id for casilla in revision.casillas if casilla.binding == _SUMINISTROS_BINDING}

    assert targets == {_CASILLA_SUMINISTROS}


def test_the_other_gasto_lines_reach_their_own_printed_figures() -> None:
    """Each remaining bound expense casilla carries the manual's own amount.

    These four were already correct before the new category existed, and
    asserting them here keeps the module honest about what changed: the
    suministros routing, not the expense chain as a whole.
    """
    resolved = _resolved()

    assert resolved[_RETA_BINDING] == _RETA
    assert resolved[_FINANCIEROS_BINDING] == _GASTOS_FINANCIEROS
    assert resolved[_TRIBUTOS_BINDING] == _TRIBUTOS_NO_ESTATALES
    assert resolved[_REPARACIONES_BINDING] == _REPARACIONES


def test_the_premises_category_needs_no_censo_derived_ratio() -> None:
    """The local case reaches its full figure with no usage ratio supplied.

    The home-office categories are bound to the censo vivienda-area invariant:
    an override must equal the censo-derived proportion, and is refused
    outright without a censo snapshot. A taxpayer whose premises are not a
    dwelling has no such data, so a route that depended on an override would be
    closed to exactly the population entitled to full deduction. This asserts
    the new category does not depend on one -- ``_resolved`` passes no
    ``usage_ratios`` at all.
    """
    resolved = _resolved()

    assert resolved[_SUMINISTROS_BINDING] == _SUMINISTROS_TOTAL


def test_moving_one_bill_moves_the_published_subtotal() -> None:
    """Anti-tautology: the chain carries the change rather than emitting a constant.

    Every assertion above compares against a figure the manual printed, and a
    chain that returned those constants regardless of what it aggregated would
    satisfy all of them. One euro added to a single bill must move 0194 by one
    euro, and the change enters at the ledger row so it has to survive the
    aggregation and the binding resolver.
    """
    baseline = _resolved()[_SUMINISTROS_BINDING]

    nudged_rows = [
        _expense_row(
            "suministro-electrico", _SUMINISTRO_ELECTRICO + Decimal("1.00"), SpendingCategory.SUMINISTROS_LOCAL_AFECTO
        ),
        *(
            _expense_row(reference, amount, SpendingCategory.SUMINISTROS_LOCAL_AFECTO)
            for reference, amount in _SUMINISTRO_ROWS[1:]
        ),
    ]
    aggregation = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions(tuple(nudged_rows)),
        InvoiceCatalogue(),
        bucket_id=_BUCKET,
        period=_PERIOD,
        modelo="100",
    )
    nudged = resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values(
        _modelo_100_revision(),
        aggregation.observations,
    )[_SUMINISTROS_BINDING]

    assert baseline == _SUMINISTROS_TOTAL
    assert nudged - baseline == Decimal("1.00")
