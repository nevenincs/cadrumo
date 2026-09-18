"""Development-authority contracts for transaction fact applicability coordinates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.tipos_actividad import TipoActividad
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.domain.transactions.retencion_facts import (
    load_retencion_actividades_rates,
    retencion_effective_date,
)
from cadrumo.domain.transactions.tipo_actividad_partitions import (
    load_tipo_actividad_selectors,
    resolve_tipo_actividad_selector,
    tipo_actividad_code_set,
)

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFESSIONAL_SELECTOR = "rirpf-art-95:selector-m036-actividades-profesionales"


@cache
def _authority() -> ValidatedRegistryAuthority:
    """Compile the development catalogue without pretending it is a published artifact."""
    return compiled_bundled_authority()


def test_retencion_rates_select_the_supplied_coordinate_not_the_wall_clock() -> None:
    """The rate set is selected from the supplied coordinate, inside the product's envelope.

    The coordinates are read off the registry's own support declaration rather
    than pinned here: the floor is a hard gate, so a year below it is refused
    however well the corpus authors it, and a test naming a fixed historical
    year would break every time the envelope moved. The refusal is the proof
    that selection is input-driven -- today's date is inside the envelope, so an
    implementation reading the wall clock would resolve happily instead.
    """
    authority = _authority()
    support = authority.supported_filing_years()

    floor_rates = load_retencion_actividades_rates(effective_date=date(support.floor, 6, 30), authority=authority)
    assert floor_rates.general_rate > Decimal("0")

    below_floor = support.floor - 1
    assert not support.admits_filing_year(below_floor)
    with pytest.raises(TransactionValidationError, match=str(below_floor)):
        load_retencion_actividades_rates(effective_date=date(below_floor, 6, 30), authority=authority)

    assert retencion_effective_date(value_date=date(2015, 7, 12), booked_date=date(2015, 7, 11)) == date(2015, 7, 12)
    with pytest.raises(TransactionValidationError, match="requires a transaction value or booked date"):
        retencion_effective_date(value_date=None, booked_date=None)


def test_activity_selector_preserves_provenance_and_refuses_an_unknown_selector() -> None:
    """A selector is an evidenced fact, not a Python activity-code mapping.

    The selector variant is authored open-ended: its ``source_refs`` carry the
    date the AEAT code table was captured, and a capture date is not a statement
    about when the codes took effect, so a coordinate earlier than the capture
    resolves the same evidenced set rather than being refused. What is refused
    is a selector the catalogue does not declare, which is the boundary a Python
    activity-code mapping would quietly answer for.
    """
    authority = _authority()
    effective_date = date(2026, 3, 26)

    selector = resolve_tipo_actividad_selector(
        _PROFESSIONAL_SELECTOR,
        effective_date=effective_date,
        authority=authority,
    )
    selectors = load_tipo_actividad_selectors(
        (_PROFESSIONAL_SELECTOR,),
        effective_date=effective_date,
        authority=authority,
    )

    assert selector.effective_date == effective_date
    assert selector.legal_refs == ("rd-439-2007:art-95", "orden-eha-1274-2007:art-1")
    assert selector.source_refs == ("aeat-m036-activity-code-table-2026-03-26", "boe-rirpf-art-95-2023-01-26")
    assert selector.authority_digest
    assert selectors[_PROFESSIONAL_SELECTOR] == frozenset({TipoActividad("A04"), TipoActividad("A05")})
    assert tipo_actividad_code_set(
        _PROFESSIONAL_SELECTOR,
        effective_date=date(2026, 3, 25),
        authority=authority,
    ) == frozenset({TipoActividad("A04"), TipoActividad("A05")})
    with pytest.raises(TransactionValidationError, match="is not declared by the registry catalogue"):
        tipo_actividad_code_set(
            "rirpf-art-95:selector-m036-no-such-selector",
            effective_date=effective_date,
            authority=authority,
        )
