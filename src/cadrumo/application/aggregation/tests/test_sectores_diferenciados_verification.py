"""End-to-end verification of the sectores-diferenciados prorrata (LIVA arts. 9.1.c / 101).

No bundled AEAT worked-example oracle for a two-sector differentiated-sectors
prorrata ships in ``src/cadrumo/_data/corpus/manual_oracles/`` (that pool carries
only the WHOLE-ENTITY Modelo 303 prorrata-general regularización example and
unrelated modelos). Per the ``aeat-quality-gates`` rule, this
verification uses a hand-constructed register with structural anti-tautology
assertions rather than numbers hand-computed from the substrate formula under
test.

The verification composes the whole differentiated-sectors lifecycle end to end:

1. Settle each sector's prior-year (2025) definitive from ITS OWN annual volumes
   (:func:`settle_sector_definitive`), giving distinct percentages with a
   >50-point spread (comercio 90 %, arrendamiento 20 %) plus a common-use 40 %.
2. Seed each 2026 provisional from that sector's prior definitive
   (:func:`seed_sector_carried_definitive_from_register`) — proving the
   lifecycle carries each sector's own definitive forward.
3. Persist the seeded 2026 register (per-sector entries + common entry + sector
   definitions) and aggregate a 2026 ledger carrying one purchase per sector plus
   one common-use purchase.
4. Assert each deducible cuota is apportioned at its OWN sector percentage and
   the common-use input at the art. 104.Dos common percentage, and — the
   anti-tautology gate — that the total is NOT any single whole-entity percentage
   applied across all inputs.

The percentages are derived from the register's own settled volumes (not
hand-copied), and the routing they drive is the production aggregation path; the
claim under test is the per-sector routing + common-use split, not the
already-verified con/total definitive substrate.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....application.prorrata_register import (
    seed_sector_carried_definitive_from_register,
    settle_sector_definitive,
)
from ....core import (
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
    Period,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from ....domain.bienes_inversion import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import BindingId
from ....domain.iva import InputClassification, IvaDeductionClassificationProvenance
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry, SectorDefinition
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from .. import aggregate_iva_ledger_observations_from_repositories
from .._iva_ledger import resolve_iva_ledger_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5c705c70-5c70-4c70-8c70-5c705c705c70"
_PERIOD = Period.from_year_and_code(2026, "1T")
_DEDUCIBLE_BASE_BINDING: BindingId = "modelo-303-iva-soportado-interiores-base"
_DEDUCIBLE_CUOTA_BINDING: BindingId = "modelo-303-iva-soportado-interiores-cuota"
_DEVENGADO_CUOTA_BINDING: BindingId = "modelo-303-iva-repercutido-general-cuota"


def _raw(provider_id: str, *, amount: Decimal, counterparty: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 2, 10),
        value_date=date(2026, 2, 10),
        amount=amount,
        currency="EUR",
        counterparty=counterparty,
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="5" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _purchase(provider_id: str, *, sector_id: str | None) -> Transaction:
    payload: dict[str, object] = {
        "raw": _raw(provider_id, amount=Decimal("60.50"), counterparty="Proveedor deducible"),
        "direction": TransactionDirection.OUTGOING,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "sectored_purchase",
        "taxable_base": Decimal("50.00"),
        "iva_rate": Decimal("0.21"),
        "iva_amount": Decimal("10.50"),
        "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_CURRENT,
        "deduction_provenance": IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            source_locator=f"invoice:{provider_id}",
            evidence_digest="5" * 64,
        ),
        "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
        "classified_by": "manual",
    }
    if sector_id is None:
        payload["input_classification"] = InputClassification.COMMON
    else:
        payload["prorrata_sector_id"] = sector_id
    return Transaction.model_validate(payload)


def _sale(provider_id: str) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, amount=Decimal("121.00"), counterparty="Cliente sujeto"),
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "category_id": "fully_taxable_sale",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _settled_2025_entry(sector_id: str | None, *, con: str, sin: str) -> ProrrataRegisterEntry:
    """A 2025 sector entry settled from its OWN annual volumes (con/total definitive)."""
    provisional = ProrrataRegisterEntry(
        ejercicio=2025,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        sector_id=sector_id,
        provisional_percentage=Decimal("50"),
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref=f"seed:{sector_id or 'comun'}",
    )
    return settle_sector_definitive(
        provisional,
        con_derecho_volume=Decimal(con),
        sin_derecho_volume=Decimal(sin),
    )


def test_two_sectors_apportion_at_own_percentage_with_common_use_split(tmp_path: Path) -> None:
    """Each sector deducts at its own percentage; common-use at art. 104.Dos; not a single rate.

    Hand-constructed-register verification (no bundled two-sector oracle ships).
    2025 settlements from own volumes give comercio 90 %, arrendamiento 20 %
    (a 70-point spread) and a common-use 40 %; the 2026 provisionals carry those
    forward; the 2026 ledger routes each purchase to its sector. The deducible
    interiores cuota is 10.50*90% + 10.50*20% + 10.50*40% = 9.45 + 2.10 + 4.20 =
    15.75 — a per-sector result, provably NOT any single whole-entity percentage
    applied across the 31.50 soportado.
    """
    revision = bundled_authority().modelo("303").revisions["2022"]

    # 1. Settle 2025 per-sector + common definitives from their own volumes.
    comercio_2025 = _settled_2025_entry("comercio", con="90000.00", sin="10000.00")  # 90%
    arrendamiento_2025 = _settled_2025_entry("arrendamiento", con="20000.00", sin="80000.00")  # 20%
    common_2025 = _settled_2025_entry(None, con="40000.00", sin="60000.00")  # 40%
    register_2025 = ProrrataRegister(entries=(comercio_2025, arrendamiento_2025, common_2025))

    # 2. Seed 2026 provisionals from each sector's own prior definitive.
    comercio_2026 = seed_sector_carried_definitive_from_register(register_2025, ejercicio=2026, sector_id="comercio")
    arrendamiento_2026 = seed_sector_carried_definitive_from_register(
        register_2025, ejercicio=2026, sector_id="arrendamiento"
    )
    assert comercio_2026 is not None
    assert arrendamiento_2026 is not None
    comercio_pct = comercio_2026.provisional_percentage
    arrendamiento_pct = arrendamiento_2026.provisional_percentage
    assert comercio_pct is not None
    assert arrendamiento_pct is not None
    assert comercio_pct == Decimal("90")
    assert arrendamiento_pct == Decimal("20")
    # A >50-point spread makes the two activities differentiated sectors (art. 9.1.c a').
    assert comercio_pct - arrendamiento_pct > Decimal("50")

    common_2026 = ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        provisional_percentage=Decimal("40"),
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref="seed:comun:2026",
    )

    register_2026 = ProrrataRegister(
        entries=(comercio_2026, arrendamiento_2026, common_2026),
        sector_definitions=(
            SectorDefinition(sector_id="comercio", letra=SectorDiferenciadoLetra.A, member_activity_codes=("4711",)),
            SectorDefinition(
                sector_id="arrendamiento", letra=SectorDiferenciadoLetra.A, member_activity_codes=("6820",)
            ),
        ),
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(
            TransactionCatalogue.from_transactions(
                (
                    _sale("sale-sec"),
                    _purchase("buy-comercio", sector_id="comercio"),
                    _purchase("buy-arrendamiento", sector_id="arrendamiento"),
                    _purchase("buy-common", sector_id=None),
                ),
            ),
        )
        ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects).save(register_2026)

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

    apportionment = aggregation.prorrata_apportionment
    assert apportionment is not None
    # Common-use apportionment is the art. 104.Dos common percentage on the carrier.
    assert apportionment.percentage == Decimal("40")
    by_sector = {sector.sector_id: sector.percentage for sector in apportionment.sector_apportionments}
    assert by_sector == {"comercio": Decimal("90"), "arrendamiento": Decimal("20")}

    # Each cuota apportions at its own percentage; the common at 40%.
    expected = (
        Decimal("10.50") * (Decimal("90") / Decimal("100"))
        + Decimal("10.50") * (Decimal("20") / Decimal("100"))
        + Decimal("10.50") * (Decimal("40") / Decimal("100"))
    )
    assert values[_DEDUCIBLE_CUOTA_BINDING] == expected
    assert expected == Decimal("15.750")

    # Anti-tautology: the total is NOT any single declared percentage across the 31.50 soportado.
    for single in (Decimal("90"), Decimal("40"), Decimal("20")):
        assert values[_DEDUCIBLE_CUOTA_BINDING] != Decimal("31.50") * (single / Decimal("100"))

    # Bases are declared in full; devengado is untouched by soportado apportionment.
    assert values[_DEDUCIBLE_BASE_BINDING] == Decimal("150.00")
    assert values[_DEVENGADO_CUOTA_BINDING] == Decimal("21.00")
