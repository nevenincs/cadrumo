"""Anti-dormant proof: the operator ingress makes especial + sectores fire.

The especial and sectores apportionment engines
(:func:`~application.aggregation._iva_ledger._apply_especial_apportionment`,
:func:`~application.aggregation._iva_ledger._apply_sector_apportionment`) were
verified end-to-end — but those verifications seed
the register through the RAW adapter (``ProrrataRegisterRepository(...).save``),
not through any operator surface: the engines therefore fired
ONLY from tests, with no production code writing an ``ESPECIAL`` register entry
or a ``SectorDefinition``.

This test closes that gap. It drives the register write through the EXACT
application service the ``aeat app ledger prorrata`` CLI verbs call
(:meth:`ProrrataRegisterService.declare` for ``elect-especial`` /
``elect-general``, :meth:`ProrrataRegisterService.declare_sector` for
``declare-sector``) and tags each ledger row with the operator-declared
``prorrata_sector_id`` (the ``ledger add --sector`` field), then runs the SAME
production aggregation the live calculate path runs and asserts the especial /
sector apportionment ACTUALLY fires — the deducible cuota is apportioned per the
elected regime / sector and DIFFERS from the whole-entity general result. The
non-electing operator's path (no service write) stays byte-identical to the
unapportioned aggregate.

Expected values derive from the LIVA art. 106.Uno reglas and the art. 101
per-sector rule, never from the ``deductible_percentage_for`` substrate under
test (aeat-quality-gates).
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
    SectorDiferenciadoLetra,
)
from ....core.resources import resources
from ....domain.bienes_inversion import BienesInversionIvaRegister
from cadrumo.domain.calculations.registry.ids import BindingId
from ....domain.iva import InputClassification, IvaDeductionClassificationProvenance
from ....domain.prorrata_register import ProrrataRegisterEntry, SectorDefinition
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....tests.secure_sql import isolated_runtime_profile
from ...prorrata_register import ProrrataRegisterService
from .. import aggregate_iva_ledger_observations_from_repositories
from .._iva_ledger import resolve_iva_ledger_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5d5d5d5d-5d5d-4d5d-8d5d-5d5d5d5d5d5d"
_PERIOD = Period.from_year_and_code(2026, "1T")
_EJERCICIO = 2026
_DEDUCIBLE_CUOTA_BINDING: BindingId = "modelo-303-iva-soportado-interiores-cuota"
_INPUT_CUOTA = Decimal("10.50")
_REVISION = "2022"


def _raw(provider_id: str) -> RawTransaction:
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
            source_sha256="5" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _purchase(
    provider_id: str,
    *,
    classification: InputClassification | None = None,
    sector_id: str | None = None,
) -> Transaction:
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
            "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_CURRENT,
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator=f"invoice:{provider_id}",
                evidence_digest="5" * 64,
            ),
            "input_classification": classification,
            "prorrata_sector_id": sector_id,
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _save_txns(
    objects: SecureObjectRepository,
    txns: tuple[Transaction, ...],
) -> TransactionCatalogueRepository:
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    tx_repo.save(TransactionCatalogue.from_transactions(txns))
    return tx_repo


def _deducible_cuota(tx_repo: TransactionCatalogueRepository) -> Decimal:
    revision = resources().modelos.get("303").revisions[_REVISION]
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
    return values.get(_DEDUCIBLE_CUOTA_BINDING, Decimal("0"))


def _active_service() -> ProrrataRegisterService:
    """The service the elect / declare-sector CLI verbs call (active-bucket bound)."""
    return ProrrataRegisterService(repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID))


def test_elect_especial_via_service_makes_art106_apportionment_fire(tmp_path: Path) -> None:
    """Electing especial through the CLI's service routes the three art. 106 reglas."""
    txns = (
        _purchase("buy-excl-ded", classification=InputClassification.EXCLUSIVELY_DEDUCTIBLE),
        _purchase("buy-excl-non", classification=InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE),
        _purchase("buy-common", classification=InputClassification.COMMON),
    )
    general_percentage = Decimal("60")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = _save_txns(objects, txns)

        # Non-electing operator: no register write -> whole-entity, no apportionment.
        baseline = _deducible_cuota(tx_repo)

        # Operator elects especial through the exact service `elect-especial` calls.
        _active_service().declare(
            ProrrataRegisterEntry(
                ejercicio=_EJERCICIO,
                regime=ProrrataRegisterRegime.ESPECIAL,
                especial_transition=None,
                provisional_percentage=general_percentage,
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            )
        )
        especial = _deducible_cuota(tx_repo)

    multiplier = general_percentage / Decimal("100")
    # LIVA art. 106.Uno: regla 1.a (full) + regla 2.a (nil) + regla 3.a (general %).
    expected_especial = _INPUT_CUOTA + Decimal("0") + _INPUT_CUOTA * multiplier
    # Baseline is unapportioned: every deducible input at full cuota.
    expected_baseline = _INPUT_CUOTA * 3

    assert baseline == expected_baseline
    assert especial == expected_especial
    # Anti-dormant: the operator election actually changed the deducible cuota.
    assert especial != baseline


def test_declare_sector_via_service_makes_per_sector_apportionment_fire(tmp_path: Path) -> None:
    """Declaring sectors + tagging rows through the CLI's service routes per-sector %."""
    txns = (
        _purchase("sector-a-row", sector_id="sector-a"),
        _purchase("sector-b-row", sector_id="sector-b"),
    )
    sector_a_pct = Decimal("90")
    sector_b_pct = Decimal("10")
    common_pct = Decimal("50")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = _save_txns(objects, txns)

        baseline = _deducible_cuota(tx_repo)

        service = _active_service()
        # Operator declares the art. 9.1.c partition (`declare-sector`) ...
        service.declare_sector(
            SectorDefinition(sector_id="sector-a", letra=SectorDiferenciadoLetra.A, member_activity_codes=("4711",))
        )
        service.declare_sector(
            SectorDefinition(sector_id="sector-b", letra=SectorDiferenciadoLetra.A, member_activity_codes=("6201",))
        )
        # ... a common (whole-entity) base entry and one entry per sector
        # (`elect-general --sector`), each at its own percentage.
        for sector_id, pct in ((None, common_pct), ("sector-a", sector_a_pct), ("sector-b", sector_b_pct)):
            service.declare(
                ProrrataRegisterEntry(
                    ejercicio=_EJERCICIO,
                    regime=ProrrataRegisterRegime.GENERAL,
                    especial_transition=None,
                    sector_id=sector_id,
                    provisional_percentage=pct,
                    provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                )
            )
        sectored = _deducible_cuota(tx_repo)

    # LIVA art. 101: each sector's input deducts at its sector percentage.
    expected_sectored = _INPUT_CUOTA * (sector_a_pct / Decimal("100")) + _INPUT_CUOTA * (sector_b_pct / Decimal("100"))
    expected_baseline = _INPUT_CUOTA * 2

    assert baseline == expected_baseline
    assert sectored == expected_sectored
    # Anti-dormant: the operator's sector declaration actually re-routed the cuota.
    assert sectored != baseline


def test_non_electing_operator_path_is_byte_identical(tmp_path: Path) -> None:
    """With no operator election, the aggregate is exactly the unapportioned cuota."""
    txns = (
        _purchase("row-1"),
        _purchase("row-2"),
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        tx_repo = _save_txns(objects, txns)
        result = _deducible_cuota(tx_repo)

    assert result == _INPUT_CUOTA * 2
