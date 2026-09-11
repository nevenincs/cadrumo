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
from dev.registry.compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFESSIONAL_SELECTOR = "rirpf-art-95:selector-m036-actividades-profesionales"


@cache
def _authority() -> ValidatedRegistryAuthority:
    """Compile the development catalogue without pretending it is a published artifact."""
    return compiled_bundled_authority()


def test_retencion_rates_select_the_explicit_historical_filing_coordinate() -> None:
    """The 2015 legal change is selected from input evidence, never the wall clock."""
    authority = _authority()

    before = load_retencion_actividades_rates(effective_date=date(2015, 7, 11), authority=authority)
    after = load_retencion_actividades_rates(effective_date=date(2015, 7, 12), authority=authority)

    assert before.general_rate == Decimal("0.18")
    assert after.general_rate == Decimal("0.15")
    assert retencion_effective_date(value_date=date(2015, 7, 12), booked_date=date(2015, 7, 11)) == date(2015, 7, 12)
    with pytest.raises(TransactionValidationError, match="requires a transaction value or booked date"):
        retencion_effective_date(value_date=None, booked_date=None)


def test_activity_selector_preserves_provenance_and_refuses_pre_source_coordinate() -> None:
    """A selector is an evidenced fact, not a Python activity-code mapping."""
    authority = _authority()
    effective_date = date(2026, 3, 26)

    selector = resolve_tipo_actividad_selector(
        _PROFESSIONAL_SELECTOR,
        effective_date=effective_date,
        authority=authority,
    )
    selectors = load_tipo_actividad_selectors(effective_date=effective_date, authority=authority)

    assert selector.effective_date == effective_date
    assert selector.legal_refs == ("rd-439-2007:art-95", "orden-eha-1274-2007:art-1")
    assert selector.source_refs == ("aeat-m036-activity-code-table-2026-03-26", "boe-rirpf-art-95-2023-01-26")
    assert selector.authority_digest
    assert selectors[_PROFESSIONAL_SELECTOR] == frozenset({TipoActividad("A04"), TipoActividad("A05")})
    with pytest.raises(TransactionValidationError, match="failed to resolve Modelo 036 activity selector"):
        tipo_actividad_code_set(
            _PROFESSIONAL_SELECTOR,
            effective_date=date(2026, 3, 25),
            authority=authority,
        )
