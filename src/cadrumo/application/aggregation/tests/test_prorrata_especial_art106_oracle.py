"""Verify LIVA art. 106 prorrata-especial routing and the art. 103.Dos.2 +10% advisory.

No bundled AEAT *Manual práctico IVA* prorrata-ESPECIAL worked-example oracle
ships in the corpus (only the general-prorrata regularización oracle
``modelo-303-2025-prorrata-general-regularizacion.json`` exists). Per the
prorrata-especial policy, this verification therefore uses a hand-constructed
per-ejercicio register plus a ledger scenario driven end-to-end through the
PRODUCTION aggregation path (``aggregate_iva_ledger_observations_from_repositories``
+ ``resolve_iva_ledger_binding_values``). Expected values are derived from the
LIVA art. 106.Uno reglas grounded verbatim in the bundled corpus,
never hand-computed from the ``deductible_percentage_for`` substrate under test.

The anti-tautology proof (mirroring the art-105.Cinco global-vs-average test):
the especial routing is verified against the GENERAL-regime result over the SAME
ledger. Because especial correctly deducts the exclusively-deductible input in
full, drops the exclusively-non-deductible input to zero, and applies the general
percentage only to the common input, the especial deducible cuota MUST differ
from the flat general-regime cuota. If the regime-aware routing silently fell back
to the general percentage, especial would equal general and every assertion below
would fail.

Register (whole-entity), ejercicio 2026, provisional general percentage 60%:

* one purchase, iva cuota 10.50, ``exclusively_deductible`` -> regla 1.ª -> 100%
* one purchase, iva cuota 10.50, ``exclusively_non_deductible`` -> regla 2.ª -> 0%
* one purchase, iva cuota 10.50, ``common`` -> regla 3.ª -> the general 60%

especial deducible cuota = 10.50 + 0.00 + (10.50 * 60%) = 16.80
general deducible cuota  = (10.50 + 10.50 + 10.50) * 60% = 18.90 (all inputs flat)
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage import SecureObjectRepository
from ....core import (
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
    Period,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
)
from ....domain.bienes_inversion import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import BindingId
from ....domain.iva import InputClassification, IvaDeductionClassificationProvenance
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import build_prorrata_especial_mandatory_advisory
from .. import aggregate_iva_ledger_observations_from_repositories
from .._iva_ledger import resolve_iva_ledger_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "79797979-7979-4979-8979-797979797979"
_PERIOD = Period.from_year_and_code(2026, "1T")
_DEDUCIBLE_CUOTA_BINDING: BindingId = "modelo-303-iva-soportado-interiores-cuota"
_GENERAL_PERCENTAGE = Decimal("60")
_INPUT_CUOTA = Decimal("10.50")


def _raw(provider_id: str):
    from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 2, 10),
        value_date=date(2026, 2, 10),
        amount=Decimal("60.50"),
        currency="EUR",
        counterparty="Proveedor",
        description=f"row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="7" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _classified_purchase(provider_id: str, classification: InputClassification):
    from ....domain.transactions.enums import BusinessClassification, TransactionDirection
    from ....domain.transactions.models import Transaction

    return Transaction.model_validate(
        {
            "raw": _raw(provider_id),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "category_id": "classified_purchase",
            "taxable_base": Decimal("50.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": _INPUT_CUOTA,
            "input_classification": classification,
            "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_CURRENT,
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator=f"invoice:{provider_id}",
                evidence_digest="7" * 64,
            ),
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _seed_register(objects: SecureObjectRepository, regime: ProrrataRegisterRegime) -> None:
    ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects).save(
        ProrrataRegister(
            entries=(
                ProrrataRegisterEntry(
                    ejercicio=2026,
                    regime=regime,
                    especial_transition=None,
                    provisional_percentage=_GENERAL_PERCENTAGE,
                    provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                    source_observation_ref="303:2025:4T",
                ),
            ),
        ),
    )


def _deducible_cuota(objects: SecureObjectRepository) -> Decimal:
    from ....domain.transactions.models import TransactionCatalogue

    revision = bundled_authority().modelo("303").revisions["2022"]
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    tx_repo.save(TransactionCatalogue.from_transactions(_txns()))
    aggregation = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=_BUCKET_ID,
        period=_PERIOD,
        transaction_repository=tx_repo,
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID),
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=_BUCKET_ID,
    )
    values = resolve_iva_ledger_binding_values(
        revision,
        aggregation.observations,
        prorrata_apportionment=aggregation.prorrata_apportionment,
    )
    return values[_DEDUCIBLE_CUOTA_BINDING]


def _txns():
    return (
        _classified_purchase("buy-excl-ded", InputClassification.EXCLUSIVELY_DEDUCTIBLE),
        _classified_purchase("buy-excl-non", InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE),
        _classified_purchase("buy-common", InputClassification.COMMON),
    )


def test_especial_routes_three_art106_reglas_and_differs_from_general(tmp_path: Path) -> None:
    """The production aggregation routes the three art. 106 reglas, distinct from general."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        _seed_register(objects, ProrrataRegisterRegime.ESPECIAL)
        especial_cuota = _deducible_cuota(objects)
        _seed_register(objects, ProrrataRegisterRegime.GENERAL)
        general_cuota = _deducible_cuota(objects)

    multiplier = _GENERAL_PERCENTAGE / Decimal("100")
    # Art. 106.Uno: regla 1.ª (full) + regla 2.ª (nil) + regla 3.ª (general %).
    expected_especial = _INPUT_CUOTA + Decimal("0") + _INPUT_CUOTA * multiplier
    # General regime flat-multiplies every deducible input by the whole-entity %.
    expected_general = (_INPUT_CUOTA * 3) * multiplier

    assert especial_cuota == expected_especial
    assert general_cuota == expected_general
    # Anti-tautology: especial routing is real, not a silent fallback to general.
    assert especial_cuota != general_cuota


@pytest.mark.parametrize(
    ("classification", "expected"),
    [
        (InputClassification.EXCLUSIVELY_DEDUCTIBLE, _INPUT_CUOTA),
        (InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE, Decimal("0")),
        (InputClassification.COMMON, _INPUT_CUOTA * (_GENERAL_PERCENTAGE / Decimal("100"))),
    ],
)
def test_each_art106_regla_isolated(
    tmp_path: Path,
    classification: InputClassification,
    expected: Decimal,
) -> None:
    """Each art. 106.Uno regla, isolated, deducts at its lawful rate (100 / 0 / general)."""
    from ....domain.transactions.models import TransactionCatalogue

    revision = bundled_authority().modelo("303").revisions["2022"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        _seed_register(objects, ProrrataRegisterRegime.ESPECIAL)
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(
            TransactionCatalogue.from_transactions((_classified_purchase("solo", classification),)),
        )
        aggregation = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID),
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id=_BUCKET_ID,
        )
        values = resolve_iva_ledger_binding_values(
            revision,
            aggregation.observations,
            prorrata_apportionment=aggregation.prorrata_apportionment,
        )

    assert values.get(_DEDUCIBLE_CUOTA_BINDING, Decimal("0")) == expected


def test_plus_ten_percent_advisory_fires_on_production_general_vs_especial_totals(tmp_path: Path) -> None:
    """The art. 103.Dos.2 advisory fires on the real production general-vs-especial totals."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        _seed_register(objects, ProrrataRegisterRegime.ESPECIAL)
        especial_cuota = _deducible_cuota(objects)
        _seed_register(objects, ProrrataRegisterRegime.GENERAL)
        general_cuota = _deducible_cuota(objects)

    # general 18.90 exceeds especial 16.80 by 12.5% (> 10%): especial is obligatory.
    notice = build_prorrata_especial_mandatory_advisory(
        deduction_under_general=general_cuota,
        deduction_under_especial=especial_cuota,
        ejercicio=2026,
    )

    assert notice is not None
    assert notice.context is not None
    assert notice.context["deduction_under_general"] == str(general_cuota)
    assert notice.context["deduction_under_especial"] == str(especial_cuota)

    # Anti-tautology: an equal-or-below general deduction never fires the obligation.
    assert (
        build_prorrata_especial_mandatory_advisory(
            deduction_under_general=especial_cuota,
            deduction_under_especial=especial_cuota,
            ejercicio=2026,
        )
        is None
    )
