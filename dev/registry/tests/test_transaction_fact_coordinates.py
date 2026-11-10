"""Development-authority contracts for transaction fact applicability coordinates."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.tipos_actividad import TipoActividad
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.facts.payloads import ScalarFactPayload
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.domain.transactions.retencion_facts import (
    load_retencion_actividades_rates,
    retencion_effective_date,
)
from cadrumo.domain.transactions.tipo_actividad_partitions import (
    resolve_tipo_actividad_selector,
    tipo_actividad_code_set,
)

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFESSIONAL_SELECTOR = "rirpf-art-95:selector-m036-actividades-profesionales"
_GENERAL_RATE_FACT_ID = "rirpf-art-95:retencion-actividades-profesionales-general"


@cache
def _authority() -> ValidatedRegistryAuthority:
    """Compile the development catalogue without pretending it is a published artifact."""
    return compiled_bundled_authority()


def test_retencion_rates_select_the_supplied_coordinate_not_the_wall_clock() -> None:
    """The rate set is selected from the supplied coordinate.

    The coordinates are read off the registry rather than pinned here: the
    general rate's own variants name a redaction whose value differs from the
    one in force at the floor, and reading that redaction's first day returns
    its value. An implementation reading the wall clock would return the
    floor's rate there instead, because today shares it.
    """
    authority = _authority()
    support = authority.supported_filing_years()

    floor_rates = load_retencion_actividades_rates(effective_date=date(support.floor, 6, 30), authority=authority)
    assert floor_rates.general_rate > Decimal("0")

    redactions = [
        (variant.valid_from, Decimal(str(variant.payload.value)))
        for variant in authority.catalogues.facts.facts[_GENERAL_RATE_FACT_ID].variants
        if isinstance(variant.payload, ScalarFactPayload) and isinstance(variant.valid_from, date)
    ]
    differing = [(starts, rate) for starts, rate in redactions if rate != floor_rates.general_rate]
    assert differing, "no redaction of the general rate differs from the floor's, so the coordinate proves nothing"
    for starts, rate in differing:
        selected = load_retencion_actividades_rates(effective_date=starts, authority=authority)
        assert selected.general_rate == rate, starts

    value_date, booked_date = date(support.floor, 7, 12), date(support.floor, 7, 11)
    assert retencion_effective_date(value_date=value_date, booked_date=booked_date) == value_date
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
    # The table's opening date is read from the catalogued source the selector cites, never written here.
    probe = resolve_tipo_actividad_selector(
        _PROFESSIONAL_SELECTOR,
        effective_date=date(authority.supported_filing_years().horizon, 1, 1),
        authority=authority,
    )
    table_source = authority.catalogues.sources[probe.source_refs[0]]
    assert table_source.applies_from is not None
    effective_date = table_source.applies_from
    day_before = effective_date - timedelta(days=1)

    selector = resolve_tipo_actividad_selector(
        _PROFESSIONAL_SELECTOR,
        effective_date=effective_date,
        authority=authority,
    )
    codes = tipo_actividad_code_set(
        _PROFESSIONAL_SELECTOR,
        effective_date=effective_date,
        authority=authority,
    )

    assert selector.effective_date == effective_date
    assert selector.legal_refs == ("rd-439-2007:art-95", "orden-eha-1274-2007:art-1")
    assert selector.source_refs == (
        f"aeat-m036-activity-code-table-{effective_date.isoformat()}",
        "boe-rirpf-art-95-2023-01-26",
    )
    assert selector.authority_digest
    assert codes == frozenset({TipoActividad("A04"), TipoActividad("A05")})
    assert tipo_actividad_code_set(
        _PROFESSIONAL_SELECTOR,
        effective_date=day_before,
        authority=authority,
    ) == frozenset({TipoActividad("A04"), TipoActividad("A05")})
    with pytest.raises(TransactionValidationError, match="is not declared by the registry catalogue"):
        tipo_actividad_code_set(
            "rirpf-art-95:selector-m036-no-such-selector",
            effective_date=effective_date,
            authority=authority,
        )
