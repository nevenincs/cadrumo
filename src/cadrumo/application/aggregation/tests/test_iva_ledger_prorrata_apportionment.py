"""Prorrata apportionment regressions for the shared IVA ledger path.

See Also:
    :func:`~application.aggregation._iva_ledger.aggregate_iva_ledger_observations_from_repositories`
        Repository-backed aggregation path that loads the active prorrata
        register and emits the apportionment carrier under test.
    :func:`~application.aggregation._iva_ledger.resolve_iva_ledger_binding_values`
        Binding resolver wrapper that applies prorrata only to deducible cuota
        bindings.
    :mod:`~domain.prorrata_register`
        Register model used to record ``NINGUNA`` and active ``GENERAL``
        scenarios in these regressions.
    :class:`~application.aggregation._modelo_bindings.LedgerIvaAggregationSourceResolver`
        Production source-mesh route that threads the same aggregation and
        binding resolver.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage import SecureObjectRepository
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.prorrata_register import (
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from ....core.period import Period
from ....domain.bienes_inversion import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import BindingId
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.prorrata import InputClassification
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry, SectorDefinition
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from .. import AggregationValidationError
from .. import aggregate_iva_ledger_observations_from_repositories as _aggregate_from_repositories
from .._iva_ledger import _active_prorrata_apportionment, resolve_iva_ledger_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "78787878-7878-4878-8878-787878787878"
_PERIOD = Period.from_year_and_code(2026, "1T")
_DEVENGADO_CUOTA_BINDING: BindingId = "modelo-303-iva-repercutido-general-cuota"
_DEDUCIBLE_BASE_BINDING: BindingId = "modelo-303-iva-soportado-interiores-base"
_DEDUCIBLE_CUOTA_BINDING: BindingId = "modelo-303-iva-soportado-interiores-cuota"


def _deduction_authority(provider_id: str) -> dict[str, object]:
    return {
        "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_CURRENT,
        "deduction_provenance": IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
            source_locator=f"invoice:{provider_id}",
            evidence_digest="7" * 64,
        ),
    }


def aggregate_iva_ledger_observations_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepository,
):
    """Exercise the injected-repository path with its explicit asset authority."""
    return _aggregate_from_repositories(
        bucket_id=bucket_id,
        period=period,
        transaction_repository=transaction_repository,
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=bucket_id),
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=bucket_id,
    )


def _raw_transaction(
    provider_id: str,
    *,
    amount: Decimal = Decimal("60.50"),
    counterparty: str = "Proveedor plenamente deducible",
) -> RawTransaction:
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
            source_sha256="7" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _fully_taxable_purchase(provider_id: str) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "category_id": "fully_taxable_purchase",
            "taxable_base": Decimal("50.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("10.50"),
            **_deduction_authority(provider_id),
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _classified_purchase(provider_id: str, classification: InputClassification) -> Transaction:
    """A fully-domestic 21% purchase carrying an art. 106 input_classification.

    Same base/cuota shape as :func:`_fully_taxable_purchase` (taxable_base
    50.00, iva 10.50) so the three art. 106 reglas can be exercised against a
    single deducible cuota binding.
    """
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "category_id": "classified_purchase",
            "taxable_base": Decimal("50.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("10.50"),
            "input_classification": classification,
            **_deduction_authority(provider_id),
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _fully_taxable_sale(provider_id: str) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                amount=Decimal("121.00"),
                counterparty="Cliente plenamente sujeto",
            ),
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


def _canonical_binding_bytes(values: Mapping[BindingId, Decimal]) -> bytes:
    return json.dumps(
        {binding_id: str(values[binding_id]) for binding_id in sorted(values)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def test_repository_aggregation_refuses_an_implicit_prorrata_store(tmp_path: Path) -> None:
    """A caller must name the encrypted register it expects to consume."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        tx_repo.save(TransactionCatalogue.from_transactions((_fully_taxable_purchase("missing-prorrata-owner"),)))

        with pytest.raises(TypeError, match="prorrata_register_repository"):
            cast(Any, _aggregate_from_repositories)(
                bucket_id=_BUCKET_ID,
                period=_PERIOD,
                transaction_repository=tx_repo,
                investment_asset_register=BienesInversionIvaRegister(),
                investment_asset_profile_id=_BUCKET_ID,
            )


def test_non_prorrata_register_keeps_fully_taxable_deducible_aggregation_byte_identical(tmp_path: Path) -> None:
    """A taxpayer recorded as no-prorrata keeps the previous full-deduction output."""
    revision = bundled_authority().modelo("303").revisions["2022"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(TransactionCatalogue.from_transactions((_fully_taxable_purchase("purchase-full"),)))

        baseline = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        baseline_binding_bytes = _canonical_binding_bytes(
            resolve_iva_ledger_binding_values(
                revision,
                baseline.observations,
                prorrata_apportionment=baseline.prorrata_apportionment,
            ),
        )
        baseline_aggregation_bytes = baseline.model_dump_json().encode()

        ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects).save(
            ProrrataRegister(
                entries=(
                    ProrrataRegisterEntry(
                        ejercicio=2026,
                        regime=ProrrataRegisterRegime.NINGUNA,
                        especial_transition=None,
                    ),
                ),
            ),
        )
        non_prorrata = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        non_prorrata_binding_bytes = _canonical_binding_bytes(
            resolve_iva_ledger_binding_values(
                revision,
                non_prorrata.observations,
                prorrata_apportionment=non_prorrata.prorrata_apportionment,
            ),
        )

    assert non_prorrata.model_dump_json().encode() == baseline_aggregation_bytes
    assert non_prorrata_binding_bytes == baseline_binding_bytes


def test_general_prorrata_register_reduces_deducible_cuota_without_reducing_base(tmp_path: Path) -> None:
    """The active provisional percentage bites only on deducible IVA cuota fields."""
    revision = bundled_authority().modelo("303").revisions["2022"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(
            TransactionCatalogue.from_transactions(
                (
                    _fully_taxable_sale("sale-full"),
                    _fully_taxable_purchase("purchase-prorrata"),
                ),
            ),
        )

        baseline = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        baseline_values = resolve_iva_ledger_binding_values(
            revision,
            baseline.observations,
            prorrata_apportionment=baseline.prorrata_apportionment,
        )

        ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects).save(
            ProrrataRegister(
                entries=(
                    ProrrataRegisterEntry(
                        ejercicio=2026,
                        regime=ProrrataRegisterRegime.GENERAL,
                        especial_transition=None,
                        provisional_percentage=Decimal("80"),
                        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                        source_observation_ref="303:2025:4T",
                    ),
                ),
            ),
        )
        apportioned = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        apportioned_values = resolve_iva_ledger_binding_values(
            revision,
            apportioned.observations,
            prorrata_apportionment=apportioned.prorrata_apportionment,
        )

    assert baseline.prorrata_apportionment is None
    assert apportioned.prorrata_apportionment is not None
    assert apportioned.prorrata_apportionment.percentage == Decimal("80")
    assert apportioned.prorrata_apportionment.regime is ProrrataRegisterRegime.GENERAL
    assert apportioned.prorrata_apportionment.provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
    assert apportioned_values[_DEDUCIBLE_CUOTA_BINDING] < baseline_values[_DEDUCIBLE_CUOTA_BINDING]
    assert apportioned_values[_DEDUCIBLE_BASE_BINDING] == baseline_values[_DEDUCIBLE_BASE_BINDING]
    assert apportioned_values[_DEVENGADO_CUOTA_BINDING] == baseline_values[_DEVENGADO_CUOTA_BINDING]


def _seed_register(
    objects: SecureObjectRepository,
    *,
    regime: ProrrataRegisterRegime,
    percentage: Decimal,
) -> None:
    ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects).save(
        ProrrataRegister(
            entries=(
                ProrrataRegisterEntry(
                    ejercicio=2026,
                    regime=regime,
                    especial_transition=None,
                    provisional_percentage=percentage,
                    provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                    source_observation_ref="303:2025:4T",
                ),
            ),
        ),
    )


def test_general_regime_apportionment_is_byte_identical_to_pre_especial(tmp_path: Path) -> None:
    """The GENERAL path stays the flat `cuota * percentage` behaviour.

    The deducible cuota is pinned to the exact pre-especial value
    (10.50 * 80% = 8.400): the regime-aware branch must not perturb a single
    Decimal on the general path. The base and devengado bindings are untouched.
    """
    revision = bundled_authority().modelo("303").revisions["2022"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(
            TransactionCatalogue.from_transactions(
                (
                    _fully_taxable_sale("sale-general"),
                    _fully_taxable_purchase("purchase-general"),
                ),
            ),
        )
        _seed_register(objects, regime=ProrrataRegisterRegime.GENERAL, percentage=Decimal("80"))
        aggregation = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        values = resolve_iva_ledger_binding_values(
            revision,
            aggregation.observations,
            prorrata_apportionment=aggregation.prorrata_apportionment,
        )

    assert aggregation.prorrata_apportionment is not None
    assert aggregation.prorrata_apportionment.regime is ProrrataRegisterRegime.GENERAL
    # 10.50 * 80/100 == 8.400, exactly as the pre-especial flat multiplier produced.
    assert values[_DEDUCIBLE_CUOTA_BINDING] == Decimal("10.50") * (Decimal("80") / Decimal("100"))
    assert values[_DEDUCIBLE_CUOTA_BINDING] == Decimal("8.400")
    assert values[_DEDUCIBLE_BASE_BINDING] == Decimal("50.00")
    assert values[_DEVENGADO_CUOTA_BINDING] == Decimal("21.00")


def test_especial_regime_routes_each_input_by_art_106_classification(tmp_path: Path) -> None:
    """Prorrata especial routes deducible cuota per LIVA art. 106.Uno reglas.

    Three domestic 21% purchases each carrying iva cuota 10.50 are classified
    exclusively-deductible (regla 1.ª, 100%), exclusively-non-deductible
    (regla 2.ª, 0%) and common-use (regla 3.ª, the general 80%). The deducible
    interiores cuota is therefore 10.50 (full) + 0 (dropped) + 8.40 (10.50*80%)
    = 18.90 — an art. 106 result, not the flat general 80% of the whole
    (which would be 25.20). Bases stay full; devengado is untouched.
    """
    revision = bundled_authority().modelo("303").revisions["2022"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(
            TransactionCatalogue.from_transactions(
                (
                    _fully_taxable_sale("sale-especial"),
                    _classified_purchase("buy-excl-ded", InputClassification.EXCLUSIVELY_DEDUCTIBLE),
                    _classified_purchase("buy-excl-non", InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE),
                    _classified_purchase("buy-common", InputClassification.COMMON),
                ),
            ),
        )
        _seed_register(objects, regime=ProrrataRegisterRegime.ESPECIAL, percentage=Decimal("80"))
        aggregation = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        values = resolve_iva_ledger_binding_values(
            revision,
            aggregation.observations,
            prorrata_apportionment=aggregation.prorrata_apportionment,
        )

    assert aggregation.prorrata_apportionment is not None
    assert aggregation.prorrata_apportionment.regime is ProrrataRegisterRegime.ESPECIAL
    # regla 1.ª (100%) + regla 2.ª (0%) + regla 3.ª (general 80%): 10.50 + 0 + 8.40.
    assert values[_DEDUCIBLE_CUOTA_BINDING] == Decimal("10.50") + Decimal("10.50") * (Decimal("80") / Decimal("100"))
    assert values[_DEDUCIBLE_CUOTA_BINDING] == Decimal("18.900")
    # Strictly less than the flat general 80% of the whole 31.50 soportado (25.20).
    assert values[_DEDUCIBLE_CUOTA_BINDING] < Decimal("31.50") * (Decimal("80") / Decimal("100"))
    # Bases are declared in full under especial (only cuotas apportion).
    assert values[_DEDUCIBLE_BASE_BINDING] == Decimal("150.00")
    assert values[_DEVENGADO_CUOTA_BINDING] == Decimal("21.00")


def test_especial_all_common_reduces_to_general_byte_identical(tmp_path: Path) -> None:
    """An all-common especial bucket collapses to the general result, byte-identical.

    Especial reuses the one canonical binding resolver: when every input is
    common-use (regla 3.ª), the art. 106 routing must reproduce the general
    percentage applied to the whole deducible cuota, proving especial is an
    extension of the single aggregation path rather than a fork.
    """
    revision = bundled_authority().modelo("303").revisions["2022"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(
            TransactionCatalogue.from_transactions(
                (
                    _fully_taxable_sale("sale-cmp"),
                    _classified_purchase("buy-common-a", InputClassification.COMMON),
                    _classified_purchase("buy-common-b", InputClassification.COMMON),
                ),
            ),
        )
        _seed_register(objects, regime=ProrrataRegisterRegime.ESPECIAL, percentage=Decimal("80"))
        especial = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        especial_bytes = _canonical_binding_bytes(
            resolve_iva_ledger_binding_values(
                revision,
                especial.observations,
                prorrata_apportionment=especial.prorrata_apportionment,
            ),
        )

        _seed_register(objects, regime=ProrrataRegisterRegime.GENERAL, percentage=Decimal("80"))
        general = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        general_bytes = _canonical_binding_bytes(
            resolve_iva_ledger_binding_values(
                revision,
                general.observations,
                prorrata_apportionment=general.prorrata_apportionment,
            ),
        )

    assert especial.prorrata_apportionment is not None
    assert especial.prorrata_apportionment.regime is ProrrataRegisterRegime.ESPECIAL
    assert especial_bytes == general_bytes


# --- Sectores diferenciados (LIVA arts. 9.1.c / 101) --------------------------


def _sectored_purchase(provider_id: str, sector_id: str | None) -> Transaction:
    """A fully-domestic 21% purchase (base 50, cuota 10.50) tagged to a sector.

    ``sector_id`` ``None`` is a common-use input; a value references a declared
    differentiated sector so the sector-aware apportionment applies that sector's
    percentage.
    """
    payload: dict[str, object] = {
        "raw": _raw_transaction(provider_id),
        "direction": TransactionDirection.OUTGOING,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "sectored_purchase",
        "taxable_base": Decimal("50.00"),
        "iva_rate": Decimal("0.21"),
        "iva_amount": Decimal("10.50"),
        **_deduction_authority(provider_id),
        "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
        "classified_by": "manual",
    }
    if sector_id is None:
        payload["input_classification"] = InputClassification.COMMON
    else:
        payload["prorrata_sector_id"] = sector_id
    return Transaction.model_validate(payload)


def _sector_entry(sector_id: str | None, percentage: Decimal) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=2026,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        sector_id=sector_id,
        provisional_percentage=percentage,
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref=f"303:2025:4T:{sector_id or 'comun'}",
    )


def test_single_sector_all_inputs_equals_whole_entity_general_byte_identical(tmp_path: Path) -> None:
    """A one-sector register with every input in that sector equals whole-entity general.

    Routing every deducible cuota through a single differentiated sector at 80%
    must reproduce, byte-for-byte, the whole-entity general 80% result — proving
    the sector-aware path composes correctly and does not perturb the aggregate
    when the partition is trivial.
    """
    revision = bundled_authority().modelo("303").revisions["2022"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(
            TransactionCatalogue.from_transactions(
                (
                    _fully_taxable_sale("sale-1sec"),
                    _sectored_purchase("buy-1sec-a", "comercio"),
                    _sectored_purchase("buy-1sec-b", "comercio"),
                ),
            ),
        )
        ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects).save(
            ProrrataRegister(
                entries=(
                    _sector_entry(None, Decimal("80")),
                    _sector_entry("comercio", Decimal("80")),
                ),
                sector_definitions=(
                    SectorDefinition(
                        sector_id="comercio",
                        letra=SectorDiferenciadoLetra.A,
                        member_activity_codes=("4711",),
                    ),
                ),
            ),
        )
        sectored = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        sectored_bytes = _canonical_binding_bytes(
            resolve_iva_ledger_binding_values(
                revision,
                sectored.observations,
                prorrata_apportionment=sectored.prorrata_apportionment,
            ),
        )

        # Untag every purchase and drop the partition: whole-entity general 80%.
        tx_repo.save(
            TransactionCatalogue.from_transactions(
                (
                    _fully_taxable_sale("sale-1sec"),
                    _sectored_purchase("buy-1sec-a", None),
                    _sectored_purchase("buy-1sec-b", None),
                ),
            ),
        )
        ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects).save(
            ProrrataRegister(entries=(_sector_entry(None, Decimal("80")),)),
        )
        whole_entity = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        whole_entity_bytes = _canonical_binding_bytes(
            resolve_iva_ledger_binding_values(
                revision,
                whole_entity.observations,
                prorrata_apportionment=whole_entity.prorrata_apportionment,
            ),
        )

    assert sectored.prorrata_apportionment is not None
    assert sectored.prorrata_apportionment.sector_apportionments  # sectorized carrier
    assert whole_entity.prorrata_apportionment is not None
    assert not whole_entity.prorrata_apportionment.sector_apportionments  # whole-entity carrier
    assert sectored_bytes == whole_entity_bytes


def test_each_input_routes_to_its_own_sector_percentage(tmp_path: Path) -> None:
    """Two differentiated sectors (>50pp spread) each apply their own percentage.

    Wiring proof for the per-sector routing: a purchase in the high-deduction
    sector (90%), a purchase in the low-deduction sector (20%, a 70-point spread)
    and a common-use purchase (art. 104.Dos common 50%) each contribute their own
    apportioned cuota. The declared-sector percentages must each bite on their
    own input, not a single whole-entity percentage across all three. The exact
    figure is an oracle claim proven in the verification test; here the
    structural claim is that the three percentages are applied independently.
    """
    revision = bundled_authority().modelo("303").revisions["2022"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        tx_repo.save(
            TransactionCatalogue.from_transactions(
                (
                    _fully_taxable_sale("sale-2sec"),
                    _sectored_purchase("buy-high", "comercio"),
                    _sectored_purchase("buy-low", "arrendamiento"),
                    _sectored_purchase("buy-common", None),
                ),
            ),
        )
        ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=objects).save(
            ProrrataRegister(
                entries=(
                    _sector_entry(None, Decimal("50")),
                    _sector_entry("comercio", Decimal("90")),
                    _sector_entry("arrendamiento", Decimal("20")),
                ),
                sector_definitions=(
                    SectorDefinition(
                        sector_id="comercio",
                        letra=SectorDiferenciadoLetra.A,
                        member_activity_codes=("4711",),
                    ),
                    SectorDefinition(
                        sector_id="arrendamiento",
                        letra=SectorDiferenciadoLetra.A,
                        member_activity_codes=("6820",),
                    ),
                ),
            ),
        )
        aggregation = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            transaction_repository=tx_repo,
        )
        values = resolve_iva_ledger_binding_values(
            revision,
            aggregation.observations,
            prorrata_apportionment=aggregation.prorrata_apportionment,
        )

    apportionment = aggregation.prorrata_apportionment
    assert apportionment is not None
    # The common (art. 104.Dos) percentage is the top-level carrier percentage.
    assert apportionment.percentage == Decimal("50")
    # Both sectors resolve independently with a >50-point spread.
    by_sector = {sector.sector_id: sector.percentage for sector in apportionment.sector_apportionments}
    assert by_sector == {"comercio": Decimal("90"), "arrendamiento": Decimal("20")}
    assert max(by_sector.values()) - min(by_sector.values()) > Decimal("50")
    # comercio 10.50*90% + arrendamiento 10.50*20% + common 10.50*50%.
    expected = (
        Decimal("10.50") * (Decimal("90") / Decimal("100"))
        + Decimal("10.50") * (Decimal("20") / Decimal("100"))
        + Decimal("10.50") * (Decimal("50") / Decimal("100"))
    )
    assert values[_DEDUCIBLE_CUOTA_BINDING] == expected
    # Not a single whole-entity percentage across the 31.50 soportado.
    for single in (Decimal("90"), Decimal("50"), Decimal("20")):
        assert values[_DEDUCIBLE_CUOTA_BINDING] != Decimal("31.50") * (single / Decimal("100"))
    # Bases stay full; devengado untouched.
    assert values[_DEDUCIBLE_BASE_BINDING] == Decimal("150.00")
    assert values[_DEVENGADO_CUOTA_BINDING] == Decimal("21.00")

    sector_input = next(row for row in aggregation.observations if row.prorrata_sector_id == "comercio")
    with pytest.raises(
        AggregationValidationError,
        match=r"aggregation\.iva_ledger\.errors\.sectorized_input_missing_sector_identity",
    ):
        resolve_iva_ledger_binding_values(
            revision,
            (sector_input.model_copy(update={"prorrata_sector_id": None, "input_classification": None}),),
            prorrata_apportionment=apportionment,
        )
    with pytest.raises(
        AggregationValidationError,
        match=r"aggregation\.iva_ledger\.errors\.sectorized_input_unknown_sector",
    ):
        resolve_iva_ledger_binding_values(
            revision,
            (sector_input.model_copy(update={"prorrata_sector_id": "unknown"}),),
            prorrata_apportionment=apportionment,
        )


@pytest.mark.parametrize(
    ("sector_entry", "message"),
    (
        (None, "aggregation.iva_ledger.errors.differentiated_sector_without_filing_year_entry"),
        (
            ProrrataRegisterEntry(
                ejercicio=2026, sector_id="comercio", regime=ProrrataRegisterRegime.NINGUNA, especial_transition=None
            ),
            "aggregation.iva_ledger.errors.differentiated_sector_inactive_for_filing_year",
        ),
        (
            ProrrataRegisterEntry(
                ejercicio=2026, sector_id="comercio", regime=ProrrataRegisterRegime.GENERAL, especial_transition=None
            ),
            "aggregation.iva_ledger.errors.differentiated_sector_without_provisional_percentage",
        ),
    ),
)
def test_sectorized_register_refuses_missing_inactive_or_unresolved_sector_entry(
    tmp_path: Path, sector_entry: ProrrataRegisterEntry | None, message: str
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        entries = [_sector_entry(None, Decimal("50"))]
        if sector_entry is not None:
            entries.append(sector_entry)
        repository.save(
            ProrrataRegister(
                entries=tuple(entries),
                sector_definitions=(
                    SectorDefinition(
                        sector_id="comercio",
                        letra=SectorDiferenciadoLetra.A,
                        member_activity_codes=("4711",),
                    ),
                ),
            )
        )
        with pytest.raises(AggregationValidationError, match=message):
            _active_prorrata_apportionment(
                bucket_id=_BUCKET_ID, ejercicio=2026, prorrata_register_repository=repository
            )
