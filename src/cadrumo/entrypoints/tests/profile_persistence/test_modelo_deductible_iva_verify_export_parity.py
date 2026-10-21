"""Verify and export agree on whether a ledger expense's deductible IVA is evidenced.

One business expense is the only ledger contributor to a sealed revision. It is
judged by the real verification finding projector over the persisted
transaction catalogue, and by the real export action over the evidence bundle
frozen from that catalogue. The two lifecycle points used to disagree on an
expense with no captured ``iva_amount``: verify read it as "no cuota, nothing to
evidence" and granted, export read it as an uncaptured deductible claim and
refused, so the operator was told the revision was complete and then could not
export it.

Both now read one evaluation, and that evaluation follows whether the revision
claims IVA at all. An IRPF return (Modelo 130) has no IVA ledger bindings, so
no expense on it is a deductible-IVA gap at any cuota. Modelo 303 has them, so
there an absent cuota is a missing input, an explicit ``0.00`` passes, and a
positive cuota needs a purchase invoice, on both gates alike.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.modelo_export_support import (
    export_m303_filing_evidence,
    export_taxpayer_profile,
    isolated_backend,
    seed_profile,
    seed_revision,
)
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.application.aggregation.ledger_filing_snapshot import (
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
)
from cadrumo.application.modelo.export import (
    ModeloExportCommand,
    ModeloExportEvidenceMissingError,
    export_modelo_revision,
)
from cadrumo.application.modelo.verification_gate_findings import missing_evidence_findings
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionState, derive_calculation_revision_id
from cadrumo.domain.modelos.verification_report import ModeloVerificationFindingSeverity
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

__all__ = ["isolated_backend"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_FILING_YEAR = 2026
_PERIOD = "3T"
_SURFACE = "deductible evidence parity test"
_CAPTURED_AT = datetime(_FILING_YEAR, 10, 5, 10, 0, tzinfo=UTC)
_EXPORTED_AT = datetime(_FILING_YEAR, 10, 15, 12, 0, tzinfo=UTC)
_REFUSED = "refused: deductible IVA evidence missing"
_EXPORTED = "exported"


@dataclass(frozen=True, slots=True)
class _Revision:
    """A sealed revision shape to export, independent of the ledger under test."""

    modelo: str
    input_values_by_casilla_id: dict[CasillaId, str]
    binding_overrides: dict[BindingId, str]
    casilla_values: dict[CasillaId, Decimal]
    m303_filing_evidence: bool


# An IRPF return: Modelo 130 declares no IVA ledger bindings. The figures are
# the negative third-quarter result whose export is pinned elsewhere.
_IRPF = _Revision(
    modelo="130",
    input_values_by_casilla_id={
        validated_casilla_id("01", surface=_SURFACE): "250.00",
        validated_casilla_id("02", surface=_SURFACE): "0.00",
    },
    binding_overrides={
        "modelo-130-pagos-fraccionados-anteriores": "0",
        "modelo-130-resultados-negativos-anteriores": "0",
        "irpf.previous_year_economic_activity_net_income": "0",
    },
    casilla_values={validated_casilla_id("19", surface=_SURFACE): Decimal("-50.00")},
    m303_filing_evidence=False,
)
# An IVA return: Modelo 303 declares IVA ledger bindings. Its result casilla
# grounds the registry observations the evidence bundle cites.
_IVA = _Revision(
    modelo="303",
    input_values_by_casilla_id={},
    binding_overrides={},
    casilla_values={validated_casilla_id("71", surface=_SURFACE): Decimal("0.00")},
    m303_filing_evidence=True,
)


@dataclass(frozen=True, slots=True)
class _Cuota:
    """The IVA facts an expense row stores, kept apart from its evidence."""

    taxable_base: Decimal
    iva_rate: Decimal | None
    iva_amount: Decimal | None


def _expense(
    cuota: _Cuota,
    *,
    purchase_invoice_evidence_id: str | None = None,
    attachment_ids: tuple[str, ...] = (),
) -> Transaction:
    """A synthetic business expense with no IVA category, as manual entry stores it."""
    booked = date(_FILING_YEAR, 8, 10)
    gross = cuota.taxable_base + (cuota.iva_amount or Decimal("0.00"))
    payload: dict[str, object] = {
        "raw": RawTransaction(
            provider_transaction_id="parity-expense",
            booked_date=booked,
            value_date=booked,
            amount=gross,
            currency="EUR",
            counterparty="Proveedor sintetico",
            description="deductible evidence parity expense",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="c" * 64,
                source_row_index=1,
                source_format=SourceFormat.MANUAL,
                ingested_at=datetime(_FILING_YEAR, 8, 11, 9, 0, tzinfo=UTC),
                provider_name="manual-ledger",
            ),
            raw_fields={"source_kind": "ledger_transaction"},
        ),
        "direction": TransactionDirection.OUTGOING,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "iva_category": None,
        "attachment_ids": attachment_ids,
        "taxable_base": cuota.taxable_base,
        "iva_rate": cuota.iva_rate,
        "iva_amount": cuota.iva_amount,
    }
    if purchase_invoice_evidence_id is not None:
        payload["purchase_invoice_evidence_id"] = purchase_invoice_evidence_id
    return Transaction.model_validate(payload)


def _seed(shape: _Revision, *, bucket_id: str, operation: PinnedAuthorityOperation) -> tuple[str, str]:
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD)
    return seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo=shape.modelo,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        input_values_by_casilla_id=dict(shape.input_values_by_casilla_id),
        binding_overrides=dict(shape.binding_overrides),
        casilla_values=dict(shape.casilla_values),
        filing_instance_evidence=(
            export_m303_filing_evidence(period, operation=operation) if shape.m303_filing_evidence else None
        ),
    )


def _export_outcome(
    calculation_revision_id: str,
    *,
    bucket_id: str,
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> str:
    """Run the real export and name its outcome, keeping the deductible refusal distinct."""
    output_path = tmp_path / f"{calculation_revision_id[:12]}.txt"
    try:
        export_modelo_revision(
            ModeloExportCommand(calculation_revision_id=calculation_revision_id, output_path=output_path, actor="op"),
            workflow_profile=export_taxpayer_profile().model_copy(
                update={"activity_start_date": date(_FILING_YEAR, 7, 1)},
            ),
            export_ports=modelo_export_ports_for_test(bucket_id=bucket_id),
            clock=_EXPORTED_AT,
            operation=operation,
        )
    except ModeloExportEvidenceMissingError as refusal:
        if refusal.context is not None and refusal.context.get("reason") == "deductible_iva_evidence_missing":
            assert not output_path.exists()
            return _REFUSED
        return f"{type(refusal).__name__}: {refusal.context}"
    except CadrumoError as other:
        return type(other).__name__
    assert output_path.read_bytes()
    return _EXPORTED


def _verify_and_export(shape: _Revision, expense: Transaction, tmp_path: Path) -> tuple[bool, str, str]:
    """Return (verify blocks, export outcome, export outcome with no ledger contributor)."""
    with bundled_indexed_authority().operation() as operation:
        bucket_id = seed_profile()
        work_unit_id, baseline_id = _seed(shape, bucket_id=bucket_id, operation=operation)
        transactions = TransactionCatalogueRepository(bucket_id=bucket_id)
        transactions.save(TransactionCatalogue.from_transactions((expense,)))
        catalogue = transactions.load()
        revisions = CalculationRevisionCatalogueRepository()
        seeded = revisions.load().get(baseline_id)
        work_unit = WorkUnitCatalogueRepository().load().get(work_unit_id)
        assert seeded is not None
        assert work_unit is not None
        contributors = (expense.transaction_id,)
        snapshot = compute_ledger_filing_snapshot(
            source_transaction_ids=contributors,
            catalogue=catalogue,
            captured_at=_CAPTURED_AT,
        )
        # The revision id is content-addressed over its contributors, so the
        # ledger-backed revision is a distinct revision beside the seeded one.
        calculation_revision_id = derive_calculation_revision_id(
            work_unit_id=work_unit_id,
            input_values_by_casilla_id=seeded.input_values_by_casilla_id,
            binding_overrides=seeded.binding_overrides,
            casilla_values=seeded.casilla_values,
            source_transaction_ids=contributors,
            filing_instance_evidence=seeded.filing_instance_evidence,
            source_provenance=(),
        )
        sealed = seeded.model_copy(
            update={
                "calculation_revision_id": calculation_revision_id,
                "source_transaction_ids": contributors,
                "ledger_filing_snapshot": snapshot,
                "ledger_filing_evidence": compute_ledger_filing_evidence(
                    source_transaction_ids=contributors,
                    catalogue=catalogue,
                    snapshot_fingerprint=snapshot.snapshot_fingerprint,
                    captured_at=_CAPTURED_AT,
                    legal_refs=tuple(dict.fromkeys(ref for obs in seeded.observations for ref in obs.legal_refs)),
                    source_refs=tuple(dict.fromkeys(ref for obs in seeded.observations for ref in obs.source_refs)),
                ),
            },
        )
        revisions.save(upsert_calculation_revision(revisions.load(), sealed))

        findings = missing_evidence_findings(
            target=sealed,
            work_unit=work_unit,
            transaction_repository=transactions,
            operation=operation,
        )
        verify_blocks = any(finding.severity is ModeloVerificationFindingSeverity.BLOCKING for finding in findings)
        outcome = _export_outcome(calculation_revision_id, bucket_id=bucket_id, tmp_path=tmp_path, operation=operation)
        baseline = _export_outcome(baseline_id, bucket_id=bucket_id, tmp_path=tmp_path, operation=operation)
        return verify_blocks, outcome, baseline


_POSITIVE_CUOTA = _Cuota(taxable_base=Decimal("100.00"), iva_rate=Decimal("0.21"), iva_amount=Decimal("21.00"))
_ABSENT_CUOTA = _Cuota(taxable_base=Decimal("121.00"), iva_rate=None, iva_amount=None)
_ZERO_CUOTA = _Cuota(taxable_base=Decimal("121.00"), iva_rate=Decimal("0.00"), iva_amount=Decimal("0.00"))


@pytest.mark.parametrize(
    ("shape", "cuota", "invoice", "expected_gap"),
    [
        pytest.param(_IRPF, _ABSENT_CUOTA, None, False, id="irpf-absent-cuota-claims-no-iva"),
        pytest.param(_IRPF, _ZERO_CUOTA, None, False, id="irpf-explicit-zero"),
        pytest.param(_IRPF, _POSITIVE_CUOTA, None, False, id="irpf-positive-cuota-claims-no-iva"),
        pytest.param(_IRPF, _POSITIVE_CUOTA, "synthetic-invoice", False, id="irpf-positive-with-invoice"),
        pytest.param(_IVA, _ABSENT_CUOTA, None, True, id="iva-absent-cuota-is-a-gap"),
        pytest.param(_IVA, _ZERO_CUOTA, None, False, id="iva-explicit-zero"),
        pytest.param(_IVA, _POSITIVE_CUOTA, None, True, id="iva-positive-without-evidence"),
        pytest.param(_IVA, _POSITIVE_CUOTA, "synthetic-invoice", False, id="iva-positive-with-invoice"),
    ],
)
def test_verify_and_export_reach_the_same_answer_on_deductible_iva_evidence(
    isolated_backend: None,
    tmp_path: Path,
    shape: _Revision,
    cuota: _Cuota,
    invoice: str | None,
    *,
    expected_gap: bool,
) -> None:
    """Verification may not report complete what export then refuses, nor the reverse.

    Where no gap is expected, the export must end exactly as the same revision
    ends with no ledger contributor at all: the deductible gate changed nothing.
    The Modelo 130 baseline exports, so there the ledger-backed revision must
    export too. The seeded Modelo 303 carries no IVA wallet decision, so its
    baseline stops at the wallet gate, which export runs after the deductible
    gate; reaching it is proof the deductible gate let the revision through.
    """
    verify_blocks, outcome, baseline = _verify_and_export(
        shape,
        _expense(cuota, purchase_invoice_evidence_id=invoice),
        tmp_path,
    )

    assert baseline != _REFUSED
    assert verify_blocks is expected_gap
    assert (outcome == _REFUSED) is expected_gap
    if not expected_gap:
        assert outcome == baseline
    if shape is _IRPF:
        assert baseline == _EXPORTED


def test_verify_is_never_laxer_than_export_on_the_evidence_axis(isolated_backend: None, tmp_path: Path) -> None:
    """A bare attachment: verify blocks while export passes, never the other way.

    What counts as evidence is the one axis each gate still supplies itself, and
    the difference is recorded and one-directional: LIVA art. 97 holds verify to
    the purchase-invoice axis, while the frozen-bundle gate also credits a
    generic attachment. Verify blocking first is the safe order, because a
    revision it refuses never seals a bundle for export to judge.
    """
    expense = _expense(_POSITIVE_CUOTA, attachment_ids=("d" * 64,))

    verify_blocks, outcome, baseline = _verify_and_export(_IVA, expense, tmp_path)

    assert verify_blocks is True
    assert baseline != _REFUSED
    assert outcome == baseline
