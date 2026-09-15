"""Anti-dormant proof: the LIVA art. 103.Dos.2 +10% advisory fires on the live path.

The mandatory-especial builder
(:func:`~application.calculations.build_prorrata_especial_mandatory_advisory`)
shipped with zero production callers — a dormant advisory now wired into the live
Modelo 303 settlement collector
(:func:`~application.modelo.prorrata_regularizacion_advisory.collect_prorrata_regularizacion_diagnostics`)
with a real +10% check where both regime totals are
honestly computable, a classify-to-enable PROMPT for the general filer whose
especial total is not yet derivable).

This module drives the check through the REAL registry-loaded Modelo 303 revision,
a REAL bucket-local ledger + prorrata register inside a genuine bucket runtime
(``isolated_runtime_profile``) — no mocks, no stubs. Expected magnitudes derive
from the LIVA art. 104 (single whole-entity percentage) and art. 106.Uno reglas
(100 / 0 / general %), never from the ``deductible_percentage_for`` /
``is_especial_mandatory`` substrate under test
(``aeat-quality-gates``): the FIRES cases are paired with SILENT
non-breach cases so the check is proven to bite, not merely to always fire. At
least one FIRES case is asserted through the actual calculate fan-out
(:func:`~application.modelo.calculation_diagnostics.collect_bucket_aggregation_advisory_diagnostics`),
proving the emit is not dormant.

See Also:
    :mod:`~application.modelo.prorrata_regularizacion_advisory`
        Collector carrying the settlement branch under test.
    :func:`~application.aggregation.compute_annual_deducible_totals_by_regime`
        The dual-regime annual totals helper the branch consumes.
    :func:`~application.calculations.build_prorrata_especial_mandatory_advisory`
        The +10% comparison/message owner, consumed verbatim.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from cadrumo.adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.aggregation.source_mesh import CalculationSourceDiagnostic
from cadrumo.application.modelo.calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from cadrumo.application.modelo.prorrata_regularizacion_advisory import collect_prorrata_regularizacion_diagnostics
from cadrumo.application.prorrata_register.service import ProrrataRegisterService
from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from cadrumo.core.modelo import Modelo
from cadrumo.core.prorrata_register import (
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from cadrumo.domain.iva.prorrata import InputClassification
from cadrumo.domain.prorrata_register.register import ProrrataRegisterEntry, SectorDefinition
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "6e6e6e6e-6e6e-4e6e-8e6e-6e6e6e6e6e6e"
_EJERCICIO = 2026
_GENERAL_PCT = Decimal("50")
_SETTLEMENT_PERIOD = "4T"
_MID_YEAR_PERIOD = "1T"


def _prior_m303_snapshot_ref():
    return compiled_bundled_authority().snapshot("303", filing_year=2025, period="4T").snapshot_ref


def _revision():
    snapshot = compiled_bundled_authority().snapshot(Modelo("303").value, filing_year=_EJERCICIO, period="4T")
    return snapshot.revision


def _raw(provider_id: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 2, 10),
        value_date=date(2026, 2, 10),
        amount=Decimal("1210.00"),
        currency="EUR",
        counterparty="Proveedor",
        description=f"row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="6" * 64,
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
    cuota: Decimal,
    classification: InputClassification | None = None,
    sector_id: str | None = None,
) -> Transaction:
    base = cuota / Decimal("0.21")
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "category_id": "classified_purchase",
            "taxable_base": base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": cuota,
            "input_classification": classification,
            "prorrata_sector_id": sector_id,
            "deduction_fact_kind": IvaDeductionFactKind._from_registry("domestic_current"),
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority._from_registry("invoice_evidence"),
                source_locator=f"invoice:{provider_id}",
                evidence_digest="6" * 64,
            ),
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _save_txns(profile: TestRuntimeProfile, txns: tuple[Transaction, ...]) -> None:
    repo = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=profile.repository)
    repo.save(TransactionCatalogue.from_transactions(txns))


def _service(*, operation: PinnedAuthorityOperation) -> ProrrataRegisterService:
    return ProrrataRegisterService(repository=ProrrataRegisterRepository(bucket_id=_BUCKET), operation=operation)


def _declare(
    regime: ProrrataRegisterRegime,
    *,
    operation: PinnedAuthorityOperation,
    percentage: Decimal,
    sector_id: str | None = None,
) -> None:
    _service(operation=operation).declare(
        ProrrataRegisterEntry(
            ejercicio=_EJERCICIO,
            regime=regime,
            especial_transition=None,
            sector_id=sector_id,
            provisional_percentage=percentage,
            provisional_provenance=ProrrataProvisionalProvenance._from_registry("carried_prior_definitiva"),
            source_registry_snapshot_refs=(_prior_m303_snapshot_ref(),),
        )
    )


def _collect(period_token: str = _SETTLEMENT_PERIOD) -> tuple[CalculationSourceDiagnostic, ...]:
    return collect_prorrata_regularizacion_diagnostics(
        _revision(),
        {},
        modelo=Modelo("303").value,
        period_token=period_token,
        filing_year=_EJERCICIO,
        bucket_id=_BUCKET,
        observation_repository=CalculationObservationRepository(),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET),
    )


def _especial_diagnostics(diagnostics: tuple[CalculationSourceDiagnostic, ...]) -> list[CalculationSourceDiagnostic]:
    return [
        d for d in diagnostics if d.reason in {"prorrata_especial_obligatoria", "prorrata_especial_check_unavailable"}
    ]


def _parenthesised_amounts(message: str) -> list[Decimal]:
    return [Decimal(match) for match in re.findall(r"\(([0-9]+\.[0-9]+)\)", message)]


# ---------------------------------------------------------------------------
# FIRES — the intended general-filer audience
# ---------------------------------------------------------------------------


def test_fires_for_fully_classified_general_bucket_with_breach(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """GENERAL bucket, every deducible row classified, >10% spread -> obligation fires.

    LIVA art. 106: one COMMON row deducts at the general % (50%), one
    EXCLUSIVELY_NON_DEDUCTIBLE row deducts 0 under especial but at 50% under
    general -> the general regime over-deducts by more than 10% (art. 103.Dos.2).
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase(
                    "buy-common", cuota=Decimal("210.00"), classification=InputClassification._from_registry("common")
                ),
                _purchase(
                    "buy-non-ded",
                    cuota=Decimal("210.00"),
                    classification=InputClassification._from_registry("exclusively_non_deductible"),
                ),
            ),
        )
        _declare(ProrrataRegisterRegime._from_registry("general"), operation=operation, percentage=_GENERAL_PCT)
        especial = _especial_diagnostics(_collect())

    assert len(especial) == 1
    diagnostic = especial[0]
    assert diagnostic.reason == "prorrata_especial_obligatoria"
    assert diagnostic.source_kind == "prorrata_especial_mandatory"
    assert str(_EJERCICIO) in diagnostic.message
    # Both regime totals ride in the verbatim message, and the general total
    # genuinely exceeds the especial total (a real breach, law-derived).
    amounts = _parenthesised_amounts(diagnostic.message)
    assert len(amounts) == 2
    deduction_general, deduction_especial = amounts
    mult = _GENERAL_PCT / Decimal("100")
    assert deduction_general == Decimal("420.00") * mult  # art. 104: both rows at the single %
    assert deduction_especial == Decimal("210.00") * mult  # art. 106: COMMON only; NON_DED -> 0
    assert deduction_general > deduction_especial * Decimal("1.10")


def test_fires_confirmatorily_for_especial_bucket_with_breach(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """ESPECIAL bucket -> the general shadow is mechanical, so the check always runs."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase(
                    "buy-common", cuota=Decimal("210.00"), classification=InputClassification._from_registry("common")
                ),
                _purchase(
                    "buy-non-ded",
                    cuota=Decimal("210.00"),
                    classification=InputClassification._from_registry("exclusively_non_deductible"),
                ),
            ),
        )
        _declare(ProrrataRegisterRegime._from_registry("especial"), operation=operation, percentage=_GENERAL_PCT)
        especial = _especial_diagnostics(_collect())

    assert len(especial) == 1
    assert especial[0].reason == "prorrata_especial_obligatoria"


# ---------------------------------------------------------------------------
# PROMPT — the general filer whose especial total is not yet derivable
# ---------------------------------------------------------------------------


def test_prompt_for_general_bucket_with_unclassified_row(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """GENERAL bucket with an unclassified deducible row -> classify-to-enable prompt.

    The especial total is not honestly derivable, so the app names the obligation
    and the enabling actions and carries NO fabricated amount.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase(
                    "buy-common", cuota=Decimal("210.00"), classification=InputClassification._from_registry("common")
                ),
                _purchase("buy-unclassified", cuota=Decimal("210.00"), classification=None),
            ),
        )
        _declare(ProrrataRegisterRegime._from_registry("general"), operation=operation, percentage=_GENERAL_PCT)
        especial = _especial_diagnostics(_collect())

    assert len(especial) == 1
    diagnostic = especial[0]
    assert diagnostic.reason == "prorrata_especial_check_unavailable"
    assert diagnostic.source_kind == "prorrata_especial_mandatory"
    assert "--input-classification" in diagnostic.message
    assert "elect-especial" in diagnostic.message
    assert "1 operaciones sin clasificar" in diagnostic.message
    # No fabricated amount: the prompt carries no monetary figure.
    assert not _parenthesised_amounts(diagnostic.message)


# ---------------------------------------------------------------------------
# SILENT — no advisory
# ---------------------------------------------------------------------------


def test_silent_mid_year_period(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    """A mid-year quarter is never a settlement event: the check never runs."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase(
                    "buy-common", cuota=Decimal("210.00"), classification=InputClassification._from_registry("common")
                ),
                _purchase(
                    "buy-non-ded",
                    cuota=Decimal("210.00"),
                    classification=InputClassification._from_registry("exclusively_non_deductible"),
                ),
            ),
        )
        _declare(ProrrataRegisterRegime._from_registry("general"), operation=operation, percentage=_GENERAL_PCT)
        especial = _especial_diagnostics(_collect(period_token=_MID_YEAR_PERIOD))

    assert especial == []


def test_silent_when_no_register_apportionment_resolves(tmp_path: Path) -> None:
    """No prorrata register entry -> no apportionment resolves -> prorrata inapplicable."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase(
                    "buy-common", cuota=Decimal("210.00"), classification=InputClassification._from_registry("common")
                ),
            ),
        )
        # No _declare(...) call: the register is empty.
        especial = _especial_diagnostics(_collect())

    assert especial == []


def test_silent_when_spread_within_ten_percent(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    """A fully-classified all-common general bucket -> general == especial -> no breach."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase(
                    "buy-common-a", cuota=Decimal("210.00"), classification=InputClassification._from_registry("common")
                ),
                _purchase(
                    "buy-common-b", cuota=Decimal("210.00"), classification=InputClassification._from_registry("common")
                ),
            ),
        )
        _declare(ProrrataRegisterRegime._from_registry("general"), operation=operation, percentage=_GENERAL_PCT)
        especial = _especial_diagnostics(_collect())

    assert especial == []


def test_silent_for_sectorized_register(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    """A sectorized register is a named v1 deferral -> no branch fires."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase(
                    "buy-common",
                    cuota=Decimal("210.00"),
                    classification=InputClassification._from_registry("common"),
                    sector_id="sector-a",
                ),
                _purchase(
                    "buy-non-ded",
                    cuota=Decimal("210.00"),
                    classification=InputClassification._from_registry("exclusively_non_deductible"),
                    sector_id="sector-a",
                ),
            ),
        )
        service = _service(operation=operation)
        service.declare_sector(
            SectorDefinition(
                sector_id="sector-a", letra=SectorDiferenciadoLetra._from_registry("a"), member_activity_codes=("4711",)
            )
        )
        for sector_id in (None, "sector-a"):
            service.declare(
                ProrrataRegisterEntry(
                    ejercicio=_EJERCICIO,
                    regime=ProrrataRegisterRegime._from_registry("general"),
                    especial_transition=None,
                    sector_id=sector_id,
                    provisional_percentage=_GENERAL_PCT,
                    provisional_provenance=ProrrataProvisionalProvenance._from_registry("carried_prior_definitiva"),
                    source_registry_snapshot_refs=(_prior_m303_snapshot_ref(),),
                )
            )
        especial = _especial_diagnostics(_collect())

    assert especial == []


# ---------------------------------------------------------------------------
# LIVE-PATH — the anti-dormant essence
# ---------------------------------------------------------------------------


def test_fires_through_live_calculate_fan_out(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    """The obligation fires through the ACTUAL calculate advisory fan-out, not the collector alone."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase(
                    "buy-common", cuota=Decimal("210.00"), classification=InputClassification._from_registry("common")
                ),
                _purchase(
                    "buy-non-ded",
                    cuota=Decimal("210.00"),
                    classification=InputClassification._from_registry("exclusively_non_deductible"),
                ),
            ),
        )
        _declare(ProrrataRegisterRegime._from_registry("general"), operation=operation, percentage=_GENERAL_PCT)
        diagnostics = collect_bucket_aggregation_advisory_diagnostics(
            _revision(),
            {},
            modelo=Modelo("303").value,
            period_token=_SETTLEMENT_PERIOD,
            filing_year=_EJERCICIO,
            bucket_id=_BUCKET,
            observation_repository=CalculationObservationRepository(),
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET),
            bienes_inversion_repository=BienesInversionIvaRegisterRepository(bucket_id=_BUCKET),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET),
        )

    obligation = [d for d in diagnostics if d.reason == "prorrata_especial_obligatoria"]
    assert len(obligation) == 1
    assert obligation[0].source_kind == "prorrata_especial_mandatory"
