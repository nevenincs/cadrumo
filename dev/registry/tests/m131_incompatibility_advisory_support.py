"""Shared fixtures for the Modelo 131 incompatibility-advisory verification tests."""

from __future__ import annotations

from functools import cache

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile

from ..maintenance_support import load_modelo_path


def taxpayer_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X0001500M",
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


@cache
def m131_2025_revision() -> ModeloRevision:
    """The newest Modelo 131 revision that governs one whole calendar year and nothing beyond it."""
    whole_year = tuple(
        revision
        for revision in authored_revisions("131")
        if revision.valid_to is not None
        and (revision.valid_from.month, revision.valid_from.day) == (1, 1)
        and (revision.valid_to.month, revision.valid_to.day) == (12, 31)
        and revision.valid_from.year == revision.valid_to.year
    )
    modelo = load_modelo_path(bundled_path("registry", "aeat", "modelos", "131"))
    return modelo.revisions[str(whole_year[-1].id)]


def predicate_by_id(predicate_id: str) -> VerificationPredicateDefinition:
    revision = m131_2025_revision()
    return next(p for p in revision.verification_predicates if p.predicate_id == predicate_id)


def assert_incompatibility_predicates_ship(predicate_ids: tuple[str, ...]) -> None:
    """Every predicate exists on the 2025 revision, is ADVISORY, and cites the Anexo II grounding."""
    revision = m131_2025_revision()
    predicates_by_id = {p.predicate_id: p for p in revision.verification_predicates}

    for predicate_id in predicate_ids:
        assert predicate_id in predicates_by_id, predicate_id
        found = predicates_by_id[predicate_id]
        assert found.finding_kind == "ADVISORY", predicate_id
        assert "orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades" in tuple(
            str(r) for r in found.legal_refs
        ), predicate_id
