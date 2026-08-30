"""Art. 109 measures the 70 per cent net of subvenciones, and only for the classes it names.

RD 439/2007 art. 109.3 and 109.4 grant the pago-fraccionado exemption when *al menos
el 70 por ciento de los ingresos procedentes de la explotacion, con excepcion de las
subvenciones corrientes y de capital y de las indemnizaciones*, suffered retencion.
The derivation used to sum every activity-income row.

Why that mattered, and in which direction: a subsidy carries no retencion, so it landed
in the denominator and never in the numerator. Every euro of subsidy therefore pushed
the ratio DOWN, away from the 70 per cent, and the coverage fact feeds the Modelo 130
deadline window as ``equals false``. An agricultural filer whose lawful ratio cleared
the threshold was shown an obligation and paid a pago fraccionado the reglamento
exempts them from. PAC subsidies are near-universal for that population, so this was
not a corner case, and nothing in the product refuses or warns on over-compliance.

The mirror also matters: art. 109 names profesionales, agricolas, ganaderas and
forestales, and an empresario is in none of them. Without the activity gate an
empresarial row could earn an exemption the reglamento does not grant, which runs the
other way -- a Modelo 130 obligation silently dropped.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import ConceptoIngreso, TipoActividad
from ....core.period import Period
from ....core.resources import bundled_path
from ....domain.calculations.registry.loader import load_legal_parameters_only
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.irpf_categories import IRPF_CATEGORY_ACTIVIDAD_ECONOMICA
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.tipo_actividad_partitions import tipo_actividad_code_set
from ....domain.transactions.volumen_ingresos import counts_toward_art_109_activity_income, counts_toward_volumen_de_ingresos
from ...aggregation.tests._renta_income_aggregation_support import _raw_transaction
from .._art109_activity_income import (
    Art109ActivityIncomeCoverageStatus,
    derive_art109_activity_income_coverage,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ART_109_EXEMPT = "rd-439-2007-art-109:selector-m036-actividades-exencion-pago-fraccionado"
_ART_109_NET_BASE = "rd-439-2007-art-109:selector-m036-actividades-base-neta-de-subvenciones"
_ART_109_CONCEPTS = "rd-439-2007-art-109:conceptos-ingreso-excluidos-base-agraria"
_ART_110_CONCEPTS = "rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario"

_PERIOD = Period.from_year_and_code(2025, "1T")
_IN_WINDOW = datetime(2025, 2, 10, 12, 0, tzinfo=UTC).date()


def _row(
    provider_id: str,
    *,
    amount: Decimal,
    withheld: bool,
    tipo_actividad: TipoActividad | None = TipoActividad.B01_AGRICOLA,
    concepto_ingreso: ConceptoIngreso | None = None,
) -> Transaction:
    """Build one incoming activity-income row, following the sibling agrario fixture.

    Withholding is PROVED here the way the module proves it -- the invoice gross
    exceeds the cash actually received, because the payer kept the retención -- rather
    than by asserting a flag the model does not carry.
    """
    retencion = (amount * Decimal("0.02")) if withheld else Decimal("0.00")
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=_IN_WINDOW,
                value_date=_IN_WINDOW,
                amount=amount - retencion,
                currency="EUR",
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "irpf_category": IRPF_CATEGORY_ACTIVIDAD_ECONOMICA,
            "taxable_base": amount,
            "iva_rate": None,
            "iva_amount": Decimal("0.00"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "tipo_actividad": tipo_actividad,
            "concepto_ingreso": concepto_ingreso,
        },
    )


def _coverage(*rows: Transaction):
    catalogue = TransactionCatalogue.model_validate(
        {"transactions": {row.transaction_id: row for row in rows}},
    )
    return derive_art109_activity_income_coverage(catalogue, period=_PERIOD)


def _declared_concepts(parameter_id: str) -> frozenset[ConceptoIngreso]:
    parameter = load_legal_parameters_only(bundled_path("registry", "aeat"))[parameter_id]
    return frozenset(ConceptoIngreso(token.strip()) for token in parameter.value.split(",") if token.strip())


def test_the_two_provisions_disagree_on_exactly_one_concept() -> None:
    """The whole reason both sets exist, pinned as a property rather than a listing.

    Art. 110.1.c) keeps subvenciones corrientes in the volumen de ingresos; art.
    109.3/109.4 take them out. If these ever coincide, one provision is being applied
    to the other's base.
    """
    art109 = _declared_concepts(_ART_109_CONCEPTS)
    art110 = _declared_concepts(_ART_110_CONCEPTS)

    assert art109 > art110
    assert art109 - art110 == {ConceptoIngreso.SUBVENCION_CORRIENTE}


@pytest.mark.parametrize(
    ("concepto", "art109", "art110"),
    [
        pytest.param(ConceptoIngreso.ORDINARIO, True, True, id="ordinario-in-both"),
        pytest.param(ConceptoIngreso.SUBVENCION_CORRIENTE, False, True, id="corriente-is-the-divergence"),
        pytest.param(ConceptoIngreso.SUBVENCION_CAPITAL, False, False, id="capital-out-of-both"),
        pytest.param(ConceptoIngreso.INDEMNIZACION, False, False, id="indemnizacion-out-of-both"),
        pytest.param(None, True, True, id="undeclared-stays-in-both"),
    ],
)
def test_each_concept_lands_where_its_provision_puts_it(
    concepto: ConceptoIngreso | None,
    *,
    art109: bool,
    art110: bool,
) -> None:
    """An undeclared concept stays IN the base on purpose.

    Most receipts are ordinary trading income. Defaulting a blank concept to
    "excluded" would shrink the denominator and inflate the ratio, handing out
    exemptions nobody proved -- the under-declaration direction.
    """
    assert counts_toward_art_109_activity_income(concepto) is art109
    assert counts_toward_volumen_de_ingresos(concepto) is art110


def test_the_registry_declares_the_set_the_predicate_applies() -> None:
    """Parity anchor: the exclusion is registry data, not a list living only in Python."""
    from ....core import INGRESO_CONCEPTS_OUTSIDE_THE_ART_109_BASE

    assert _declared_concepts(_ART_109_CONCEPTS) == INGRESO_CONCEPTS_OUTSIDE_THE_ART_109_BASE


def test_the_exempt_activity_set_is_the_classes_art_109_names() -> None:
    """Profesionales, agricolas, ganaderas, forestales -- and no empresario."""
    exempt = tipo_actividad_code_set(_ART_109_EXEMPT)

    assert TipoActividad.A05_PROFESIONALES in exempt
    assert TipoActividad.B01_AGRICOLA in exempt
    assert TipoActividad.B02_GANADERA in exempt
    assert TipoActividad.B03_FORESTAL in exempt
    assert TipoActividad.A02_GANADERIA_INDEPENDIENTE in exempt
    assert TipoActividad.A03_RESTO_EMPRESARIALES not in exempt, (
        "art. 109 grants no exemption to an empresario; admitting A03 would drop a "
        "Modelo 130 obligation the reglamento imposes"
    )
    assert TipoActividad.A01_ARRENDADORES_BIENES_INMUEBLES not in exempt


def test_only_the_agrarian_apartados_measure_a_net_base() -> None:
    """Apartado 2 has no exclusion clause, so a profesional's base is not filtered."""
    net_base = tipo_actividad_code_set(_ART_109_NET_BASE)
    exempt = tipo_actividad_code_set(_ART_109_EXEMPT)

    assert net_base < exempt, "every net-base activity must also be an exempt activity"
    assert TipoActividad.A05_PROFESIONALES not in net_base, (
        "art. 109.2 measures 'los ingresos de la actividad' with no exception; filtering "
        "a profesional's base would deny an exemption the apartado grants outright"
    )
    assert TipoActividad.B01_AGRICOLA in net_base
    assert TipoActividad.B03_FORESTAL in net_base


def test_a_subsidy_no_longer_depresses_the_ratio_for_an_agrarian_filer() -> None:
    """The defect itself, reproduced end to end through the real derivation.

    A farmer with 7.000 of retained sales and 3.000 of PAC subsidy has a LAWFUL ratio
    of 7.000/7.000, because art. 109.3 takes the subsidy out of the base entirely.
    Measured over the gross 10.000 the same filer sits at 70 per cent of a base the
    statute does not use.
    """
    coverage = _coverage(
        _row("sales", amount=Decimal("7000.00"), withheld=True, concepto_ingreso=ConceptoIngreso.ORDINARIO),
        _row(
            "pac",
            amount=Decimal("3000.00"),
            withheld=False,
            concepto_ingreso=ConceptoIngreso.SUBVENCION_CORRIENTE,
        ),
    )

    assert coverage.status is Art109ActivityIncomeCoverageStatus.PROVEN
    assert coverage.denominator == Decimal("7000.00"), (
        "the subsidy is still in the base; art. 109.3 excludes it and the filer is being denied an exemption they hold"
    )
    assert coverage.meets_threshold is True


def test_an_empresarial_row_neither_claims_the_exemption_nor_dilutes_it() -> None:
    """The exemption is granted "en relacion con las mismas", so it is per activity."""
    coverage = _coverage(
        _row("prof", amount=Decimal("1000.00"), withheld=True, tipo_actividad=TipoActividad.A05_PROFESIONALES),
        _row(
            "shop",
            amount=Decimal("9000.00"),
            withheld=False,
            tipo_actividad=TipoActividad.A03_RESTO_EMPRESARIALES,
        ),
    )

    assert coverage.denominator == Decimal("1000.00")
    assert coverage.meets_threshold is True


def test_a_row_that_does_not_say_which_activity_it_belongs_to_fails_closed() -> None:
    """Guessing would either invent an exemption or deny a real one."""
    coverage = _coverage(
        _row("unknown", amount=Decimal("1000.00"), withheld=True, tipo_actividad=None),
    )

    assert coverage.status is Art109ActivityIncomeCoverageStatus.INSUFFICIENT
    assert coverage.reason == "current_period_activity_class_undeclared"
