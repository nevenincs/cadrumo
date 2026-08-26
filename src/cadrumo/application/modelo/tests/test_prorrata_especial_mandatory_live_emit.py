"""Anti-dormant proof: the LIVA art. 103.Dos.2 +10% advisory fires on the live path.

The mandatory-especial builder
(:func:`~application.calculations.build_prorrata_especial_mandatory_advisory`)
shipped with zero production callers — a dormant advisory now wired into the live
Modelo 303 settlement collector
(:func:`~application.modelo._prorrata_regularizacion_advisory.collect_prorrata_regularizacion_diagnostics`)
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
(:func:`~application.modelo._calculation_diagnostics.collect_bucket_aggregation_advisory_diagnostics`),
proving the emit is not dormant.

See Also:
    :mod:`~application.modelo._prorrata_regularizacion_advisory`
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

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import (
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
    Modelo,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from ....domain.calculations.registry.authority import bundled_authority
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
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...aggregation import CalculationSourceDiagnostic
from ...calculations import CalculationObservationRepository
from ...prorrata_register import ProrrataRegisterRepository, ProrrataRegisterService
from .._calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from .._prorrata_regularizacion_advisory import collect_prorrata_regularizacion_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "6e6e6e6e-6e6e-4e6e-8e6e-6e6e6e6e6e6e"
_EJERCICIO = 2026
_GENERAL_PCT = Decimal("50")
_SETTLEMENT_PERIOD = "4T"
_MID_YEAR_PERIOD = "1T"


def _revision():
    snapshot = bundled_authority().snapshot(Modelo.M303.value, filing_year=_EJERCICIO, period="4T")
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
            "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_CURRENT,
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
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


def _service() -> ProrrataRegisterService:
    return ProrrataRegisterService(repository=ProrrataRegisterRepository(bucket_id=_BUCKET))


def _declare(regime: ProrrataRegisterRegime, *, percentage: Decimal, sector_id: str | None = None) -> None:
    _service().declare(
        ProrrataRegisterEntry(
            ejercicio=_EJERCICIO,
            regime=regime,
            especial_transition=None,
            sector_id=sector_id,
            provisional_percentage=percentage,
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        )
    )


def _collect(period_token: str = _SETTLEMENT_PERIOD) -> tuple[CalculationSourceDiagnostic, ...]:
    return collect_prorrata_regularizacion_diagnostics(
        _revision(),
        {},
        modelo=Modelo.M303.value,
        period_token=period_token,
        filing_year=_EJERCICIO,
        bucket_id=_BUCKET,
        observation_repository=CalculationObservationRepository(),
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


def test_fires_for_fully_classified_general_bucket_with_breach(tmp_path: Path) -> None:
    """GENERAL bucket, every deducible row classified, >10% spread -> obligation fires.

    LIVA art. 106: one COMMON row deducts at the general % (50%), one
    EXCLUSIVELY_NON_DEDUCTIBLE row deducts 0 under especial but at 50% under
    general -> the general regime over-deducts by more than 10% (art. 103.Dos.2).
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase("buy-common", cuota=Decimal("210.00"), classification=InputClassification.COMMON),
                _purchase(
                    "buy-non-ded",
                    cuota=Decimal("210.00"),
                    classification=InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE,
                ),
            ),
        )
        _declare(ProrrataRegisterRegime.GENERAL, percentage=_GENERAL_PCT)
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


def test_fires_confirmatorily_for_especial_bucket_with_breach(tmp_path: Path) -> None:
    """ESPECIAL bucket -> the general shadow is mechanical, so the check always runs."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase("buy-common", cuota=Decimal("210.00"), classification=InputClassification.COMMON),
                _purchase(
                    "buy-non-ded",
                    cuota=Decimal("210.00"),
                    classification=InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE,
                ),
            ),
        )
        _declare(ProrrataRegisterRegime.ESPECIAL, percentage=_GENERAL_PCT)
        especial = _especial_diagnostics(_collect())

    assert len(especial) == 1
    assert especial[0].reason == "prorrata_especial_obligatoria"


# ---------------------------------------------------------------------------
# PROMPT — the general filer whose especial total is not yet derivable
# ---------------------------------------------------------------------------


def test_prompt_for_general_bucket_with_unclassified_row(tmp_path: Path) -> None:
    """GENERAL bucket with an unclassified deducible row -> classify-to-enable prompt.

    The especial total is not honestly derivable, so the app names the obligation
    and the enabling actions and carries NO fabricated amount.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase("buy-common", cuota=Decimal("210.00"), classification=InputClassification.COMMON),
                _purchase("buy-unclassified", cuota=Decimal("210.00"), classification=None),
            ),
        )
        _declare(ProrrataRegisterRegime.GENERAL, percentage=_GENERAL_PCT)
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


def test_silent_mid_year_period(tmp_path: Path) -> None:
    """A mid-year quarter is never a settlement event: the check never runs."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase("buy-common", cuota=Decimal("210.00"), classification=InputClassification.COMMON),
                _purchase(
                    "buy-non-ded",
                    cuota=Decimal("210.00"),
                    classification=InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE,
                ),
            ),
        )
        _declare(ProrrataRegisterRegime.GENERAL, percentage=_GENERAL_PCT)
        especial = _especial_diagnostics(_collect(period_token=_MID_YEAR_PERIOD))

    assert especial == []


def test_silent_when_no_register_apportionment_resolves(tmp_path: Path) -> None:
    """No prorrata register entry -> no apportionment resolves -> prorrata inapplicable."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (_purchase("buy-common", cuota=Decimal("210.00"), classification=InputClassification.COMMON),),
        )
        # No _declare(...) call: the register is empty.
        especial = _especial_diagnostics(_collect())

    assert especial == []


def test_silent_when_spread_within_ten_percent(tmp_path: Path) -> None:
    """A fully-classified all-common general bucket -> general == especial -> no breach."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase("buy-common-a", cuota=Decimal("210.00"), classification=InputClassification.COMMON),
                _purchase("buy-common-b", cuota=Decimal("210.00"), classification=InputClassification.COMMON),
            ),
        )
        _declare(ProrrataRegisterRegime.GENERAL, percentage=_GENERAL_PCT)
        especial = _especial_diagnostics(_collect())

    assert especial == []


def test_silent_for_sectorized_register(tmp_path: Path) -> None:
    """A sectorized register is a named v1 deferral -> no branch fires."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase(
                    "buy-common",
                    cuota=Decimal("210.00"),
                    classification=InputClassification.COMMON,
                    sector_id="sector-a",
                ),
                _purchase(
                    "buy-non-ded",
                    cuota=Decimal("210.00"),
                    classification=InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE,
                    sector_id="sector-a",
                ),
            ),
        )
        service = _service()
        service.declare_sector(
            SectorDefinition(sector_id="sector-a", letra=SectorDiferenciadoLetra.A, member_activity_codes=("4711",))
        )
        for sector_id in (None, "sector-a"):
            service.declare(
                ProrrataRegisterEntry(
                    ejercicio=_EJERCICIO,
                    regime=ProrrataRegisterRegime.GENERAL,
                    especial_transition=None,
                    sector_id=sector_id,
                    provisional_percentage=_GENERAL_PCT,
                    provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                )
            )
        especial = _especial_diagnostics(_collect())

    assert especial == []


# ---------------------------------------------------------------------------
# LIVE-PATH — the anti-dormant essence
# ---------------------------------------------------------------------------


def test_fires_through_live_calculate_fan_out(tmp_path: Path) -> None:
    """The obligation fires through the ACTUAL calculate advisory fan-out, not the collector alone."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        _save_txns(
            profile,
            (
                _purchase("buy-common", cuota=Decimal("210.00"), classification=InputClassification.COMMON),
                _purchase(
                    "buy-non-ded",
                    cuota=Decimal("210.00"),
                    classification=InputClassification.EXCLUSIVELY_NON_DEDUCTIBLE,
                ),
            ),
        )
        _declare(ProrrataRegisterRegime.GENERAL, percentage=_GENERAL_PCT)
        diagnostics = collect_bucket_aggregation_advisory_diagnostics(
            _revision(),
            {},
            modelo=Modelo.M303.value,
            period_token=_SETTLEMENT_PERIOD,
            filing_year=_EJERCICIO,
            bucket_id=_BUCKET,
        )

    obligation = [d for d in diagnostics if d.reason == "prorrata_especial_obligatoria"]
    assert len(obligation) == 1
    assert obligation[0].source_kind == "prorrata_especial_mandatory"
