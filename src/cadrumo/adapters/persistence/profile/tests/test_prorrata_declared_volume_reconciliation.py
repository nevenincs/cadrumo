"""Real annual ledger evidence reaches the prorrata advisory without replacing declarations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation.iva_ledger import aggregate_iva_ledger_observations_from_repositories
from .....application.aggregation.prorrata_volume import project_prorrata_declared_volume_rollup
from .....application.modelo.calculation_notes import BLOCKING_REASONS, note_attention
from .....application.modelo.prorrata_regularizacion_advisory import collect_prorrata_regularizacion_diagnostics
from .....core.casilla_id import validated_casilla_id
from .....core.period import Period
from .....core.prorrata_exclusions import Art104TresExclusion
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.iva_category_catalogue import require_iva_category
from .....domain.calculations.registry.iva_legal_vocabulary import require_iva_exemption_article
from .....domain.transactions.models import Transaction, TransactionCatalogue
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..bienes_inversion import BienesInversionIvaRegisterRepository
from ..calculation_observations import CalculationObservationRepository
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import TransactionCatalogueRepository
from .test_iva_ledger_prorrata_apportionment import _fully_taxable_purchase, _fully_taxable_sale

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("operation")]
_BUCKET = "108e9631-8e8f-4a81-840f-39ba3e07a70b"
_SETTLEMENT = "4T"


def _sale(
    name: str,
    *,
    category: str = "domestic_general",
    article: str | None = None,
    excluded: bool = False,
    year: int = 2026,
) -> Transaction:
    original = _fully_taxable_sale(name)
    data = original.model_dump()
    data.pop("transaction_id")
    raw = original.raw.model_dump()
    raw.update(booked_date=date(year, 10, 10), value_date=date(year, 10, 10))
    data.update(raw=raw, iva_category=require_iva_category(category))
    if category == "domestic_exempt":
        raw["amount"] = Decimal("50")
        data.update(
            taxable_base=Decimal("50"),
            iva_rate=Decimal(0),
            iva_amount=Decimal(0),
            exemption_article=require_iva_exemption_article(article) if article else None,
        )
    if excluded:
        data["art_104_tres_exclusion"] = Art104TresExclusion("non_habitual_real_estate_or_financial")
    return Transaction.model_validate(data)


@pytest.mark.parametrize("unclassified", [False, True])
def test_annual_volume_comparison_preserves_authority_and_marks_incomplete_evidence(
    tmp_path: Path, unclassified: bool
) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile,
        bundled_indexed_authority().operation() as operation,
    ):
        transactions = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=profile.repository)
        prorrata = ProrrataRegisterRepository(bucket_id=_BUCKET, objects=profile.repository)
        bienes = BienesInversionIvaRegisterRepository(bucket_id=_BUCKET, objects=profile.repository)
        rows = (
            _sale("first-sale"),
            _sale("second-sale"),
            _sale("exempt-sale", category="domestic_exempt", article=None if unclassified else "art_20_uno_8"),
            _sale("excluded-sale", excluded=True),
            _sale("prior-year-sale", year=2025),
            _fully_taxable_purchase("purchase-not-turnover"),
        )
        transactions.save(TransactionCatalogue.from_transactions(rows))
        aggregation = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET,
            period=Period.from_year_and_code(2026, "0A"),
            transaction_repository=transactions,
            prorrata_register_repository=prorrata,
            investment_asset_register=bienes.load(),
            investment_asset_profile_id=_BUCKET,
            operation=operation,
        )
        rollup = project_prorrata_declared_volume_rollup(
            aggregation,
            declared_volume_total=Decimal("999"),
            declared_volume_con_derecho=Decimal("999"),
            operation=operation,
        )
        assert rollup.ledger_volume_con_derecho == Decimal("200")
        assert rollup.ledger_volume_sin_derecho == (Decimal(0) if unclassified else Decimal("50"))
        assert set(rollup.included_ledger_ids) == {rows[0].transaction_id, rows[1].transaction_id} | (
            set() if unclassified else {rows[2].transaction_id}
        )
        assert rollup.art_104_tres_excluded_ledger_ids == (rows[3].transaction_id,)
        assert rollup.unclassified_ledger_ids == ((rows[2].transaction_id,) if unclassified else ())
        values = {
            validated_casilla_id("iva.prorrata-volumen-total", surface="test"): Decimal("999"),
            validated_casilla_id("iva.prorrata-volumen-con-derecho", surface="test"): Decimal("999"),
        }
        original = dict(values)
        diagnostics = collect_prorrata_regularizacion_diagnostics(
            operation.snapshot("303", filing_year=2026, period="4T").revision,
            values,
            modelo="303",
            period_token=_SETTLEMENT,
            filing_year=2026,
            bucket_id=_BUCKET,
            observation_repository=CalculationObservationRepository(objects=profile.repository),
            prorrata_register_repository=prorrata,
            transaction_repository=transactions,
            bienes_inversion_repository=bienes,
            operation=operation,
        )
        reasons = {diagnostic.reason for diagnostic in diagnostics}
        expected = "prorrata_volume_check_unavailable" if unclassified else "prorrata_volume_divergence"
        assert expected in reasons
        assert ("prorrata_volume_divergence" in reasons) is not unclassified
        assert not reasons & BLOCKING_REASONS
        assert values == original
        for diagnostic in diagnostics:
            note_attention(diagnostic.reason, box=None)
        if not unclassified:
            assert any("ledger_sin_derecho_volume" in diagnostic.message for diagnostic in diagnostics)
