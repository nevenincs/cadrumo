"""A relation whose source modelo the registry's applicability rule excludes is a proven zero.

A professional with at least 70 % of the activity income withheld is exempt from Modelo 130
(RIRPF art. 109.1), so the Modelo 100 pagos fraccionados relation it feeds is a proven zero, as one whose
source periods precede the activity start is. The verdict is the registry's own, read from the profile: an
unanswered or negative fact keeps Modelo 130 applicable and the relation unresolved.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition

from .....application.aggregation.source_mesh import CalculationSourceContext
from .....application.aggregation.tests.ledger_source_mesh_support import cash_criterion_profile
from .....application.calculations.relation_prefill import RelationPrefillSourceResolver
from .....core.modelo import Modelo
from .....core.period import Period
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.relations import relation_source_requirements
from .....domain.user_profile.values import UserProfileFact
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from .published_authority_support import published_authority_operation
from .relation_prefill_support import empty_profile_read_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = newest_authored_edition("100")
_SOURCE = str(Modelo("130"))
_FACTS = (
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.fiscal_residency", value="resident_irpf"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_simplificada"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value="false"),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value="false"),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value="false"),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value="false"),
)


def _relations(art109: bool | None, tmp_path: Path) -> dict[str, Decimal | None]:
    snapshot = published_authority_operation().snapshot("100", filing_year=_YEAR, period="0A")
    extra = (
        _FACTS
        if art109 is None
        else (*_FACTS, UserProfileFact(path="irpf.art109_activity_income_withholding_ge_70pct", value=art109))
    )
    with isolated_runtime_profile(tmp_path=tmp_path), bundled_indexed_authority().operation() as operation:
        resolution = RelationPrefillSourceResolver(
            repository=CalculationObservationRepository(),
            profile_read_ports=empty_profile_read_ports(),
            operation=operation,
            registry_snapshot=snapshot,
        ).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="100",
                filing_year=_YEAR,
                period=Period.from_year_and_code(_YEAR, "0A"),
                revision=snapshot.revision,
                profile=cash_criterion_profile(_YEAR, extra_facts=extra),
            ),
        )
    fed = {
        binding_id
        for requirement in relation_source_requirements(
            snapshot.revision, filing_year=snapshot.filing_year, period=snapshot.period
        )
        if requirement.source_modelo == _SOURCE
        for binding_id in requirement.target_bindings
    }
    assert fed, "Modelo 100 must declare a Modelo 130 fed relation"
    return {binding_id: resolution.relation_values.get(binding_id) for binding_id in fed}


def test_an_art109_professional_has_a_proven_zero_pagos_fraccionados(tmp_path: Path) -> None:
    assert set(_relations(True, tmp_path).values()) == {Decimal("0")}


@pytest.mark.parametrize("art109", [None, False], ids=["unanswered", "below-seventy-percent"])
def test_an_unanswered_or_negative_fact_keeps_the_relation_unresolved(tmp_path: Path, art109: bool | None) -> None:
    assert set(_relations(art109, tmp_path).values()) == {None}
