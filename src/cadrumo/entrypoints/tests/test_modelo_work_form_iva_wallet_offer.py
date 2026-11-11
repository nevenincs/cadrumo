"""A declaration's form says whether it offers the IVA compensation wallet, from its revision's own bindings.

Driven over real encrypted storage and the pinned authority, then read back through
the form loading service and the workbench projection. The flag follows the registry:
a revision that declares the compensación-pendiente binding the wallet decision owns
offers the wallet before any calculation, and one that declares none does not,
whatever its modelo number is.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.entrypoints.tests.modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...application.modelo.work_form_service import ModeloWorkFormLoadV1, load_modelo_work_form
from ...application.modelo.workbench_projection import PublicModeloWorkFormLoadV1
from ...application.operations.public_mirror import project_public_mirror
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.iva_wallet_carry_targets import (
    MODELO_303_IVA_COMPENSATION_BINDING_ID,
    revision_offers_iva_wallet,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _load(work: SeededOperatorWork) -> ModeloWorkFormLoadV1:
    unit = work.work_unit
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=VerificationReportCatalogueRepository(bucket_id=unit.bucket_id),
        admission=None,
        language=OutputLanguage.EN,
    )


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period_code", "offers"),
    [
        ("303", 2025, "1T", True),
        ("303", 2026, "1T", True),
        ("390", 2025, "0A", False),
        ("130", 2025, "1T", False),
        ("100", 2025, "0A", False),
    ],
)
def test_an_uncalculated_form_offers_the_wallet_exactly_where_its_revision_declares_the_wallet_binding(
    tmp_path: Path, modelo: str, filing_year: int, period_code: str, offers: bool
) -> None:
    with seeded_operator_work(tmp_path, modelo=modelo, filing_year=filing_year, period_code=period_code) as work:
        loaded = _load(work)
        assert loaded.form.offers_iva_wallet is offers
        served = project_public_mirror(loaded, ModeloWorkFormLoadV1, PublicModeloWorkFormLoadV1)
        assert isinstance(served, PublicModeloWorkFormLoadV1)
        assert served.form.offers_iva_wallet is offers


def test_the_offer_follows_the_revisions_own_bindings_and_not_the_modelo_number() -> None:
    with bundled_indexed_authority().operation() as operation:
        offering = operation.revision_for_context("303", filing_year=2025, period="1T")
        assert revision_offers_iva_wallet(modelo_id="303", revision=offering) is True
        without_wallet_binding = offering.model_copy(
            update={
                "bindings": tuple(
                    binding for binding in offering.bindings if binding.id != MODELO_303_IVA_COMPENSATION_BINDING_ID
                )
            }
        )
        assert revision_offers_iva_wallet(modelo_id="303", revision=without_wallet_binding) is False
        silent = operation.revision_for_context("130", filing_year=2025, period="1T")
        assert revision_offers_iva_wallet(modelo_id="130", revision=silent) is False
