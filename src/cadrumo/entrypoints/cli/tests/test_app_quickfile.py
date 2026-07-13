"""Real-behavior CLI tests for ``aeat app quickfile``.

Drives the one-command filing chain through the real ``cadrumo`` CLI against an
isolated real-session backend (real KEK/DEK, real encrypted SQLite) — no mocks,
no seeded revisions. Each test runs the actual
readiness -> create -> calculate -> verify -> export services in sequence.

Coverage:
- a calculable modelo (115, fed one real retención observation) runs the whole
  chain to a written fichero-BOE file;
- a modelo whose verify gate refuses (130 without clean cross-period evidence)
  halts instructively at ``verify`` with ``export`` skipped and a non-zero exit.

The chain is build + export only: no live AEAT submission path is exercised or
reachable (``aeat-safety-legal-gates``).
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core import Period
from ....domain.iva_compensation import IvaCompensationReconciliationDecision
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....domain.user_profile import UserProfileFact
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from .envelope_helpers import unwrap_envelope_notices as _notices
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Signatures of a concurrent-registry-write race: a concurrent process may be
# editing the registry TOML tree while these tests load it, producing a
# transient mid-edit validation/fingerprint error. Re-run rather than triage
# as a regression; ``_invoke`` encodes that as a bounded retry keyed strictly
# on these transient markers so a real failure (a genuine refusal, a wrong
# value) is never masked.
_TRANSIENT_REGISTRY_RACE_MARKERS = (
    "registry directory changed during cache fingerprinting",
    "required-role gate",
    "duplicate catalogue ids",
    "references unknown source id",
)
_IVA_WALLET_DECIDED_AT = datetime(2026, 4, 5, 10, 0, tzinfo=UTC)


def _invoke(args: Sequence[str], *, attempts: int = 8) -> Result:
    """Invoke the CLI, re-running only on the transient registry-write race."""
    result = invoke_cached_cli(list(args))
    tries = 1
    while (
        tries < attempts
        and result.exit_code != 0
        and any(marker in result.output for marker in _TRANSIENT_REGISTRY_RACE_MARKERS)
    ):
        time.sleep(2)
        dispose_engine()
        result = invoke_cached_cli(list(args))
        tries += 1
    return result


def _create_profile() -> None:
    result = _invoke(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--entity-type", "natural_person",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--surnames", "Quickfile",
            "--activity", "design",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _seed_m115_retencion_observation() -> None:
    """Persist one real URBAN_RENTAL retención observation for M115 2026 1T.

    Modelo 115 aggregates its cuota from persisted retención evidence; with one
    observation seeded the calculate stage resolves and the chain runs to
    completion. This is the source-preflight the ``calculate`` stage reads.
    """
    observation = json.dumps(
        {
            "source_kind": "ledger_transaction",
            "source_object_id": "rent-ledger-row-001",
            "perceptor_nif": "B12345678",
            "perceptor_name": "Arrendador Ejemplo SL",
            "scheme": "arrendamiento_urbano",
            "taxable_base": "2700.00",
            "retencion_amount": "513.00",
            "accrued_on": "2026-03-15",
        },
    )
    result = _invoke(
        [
            "--format", "json",
            "app", "modelo", "aggregate",
            "--modelo", "115", "--year", "2026", "--period", "1T",
            "--retencion-observation", observation,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _seed_m303_profile_facts() -> str:
    from ....application.user_profile import UserProfileLifecycleRepository, profile_storage_session
    from ....core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "profile create must install an active-profile pointer"
    with profile_storage_session(bucket_id):
        repository = UserProfileLifecycleRepository(bucket_id=bucket_id)
        record = repository.load(bucket_id)
        additions = (
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="censo.activity_start_date", value=date(2026, 1, 1)),
        )
        facts_by_path = {fact.path: fact for fact in record.facts}
        facts_by_path.update({fact.path: fact for fact in additions})
        repository.save(
            record.model_copy(
                update={
                    "facts": tuple(facts_by_path[path] for path in sorted(facts_by_path)),
                    "updated_at": record.created_at,
                },
            ),
        )
    return bucket_id


def _raw_m303_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"M303 quickfile {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="7" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_IVA_WALLET_DECIDED_AT,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _m303_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
    iva_amount: Decimal,
    purchase_invoice_evidence_id: str | None = None,
) -> Transaction:
    booked_date = date(2026, 2, 15)
    payload: dict[str, object] = {
        "raw": _raw_m303_transaction(
            provider_id,
            booked_date=booked_date,
            amount=taxable_base + iva_amount,
        ),
        "direction": direction,
        "group_label": None,
        "source_jurisdiction": "ES",
        "business_classification": BusinessClassification.BUSINESS,
        "category_id": "test_iva_operation",
        "taxable_base": taxable_base,
        "iva_rate": Decimal("0.21"),
        "iva_amount": iva_amount,
        "classified_at": _IVA_WALLET_DECIDED_AT,
        "classified_by": "manual",
    }
    if purchase_invoice_evidence_id is not None:
        payload["purchase_invoice_evidence_id"] = purchase_invoice_evidence_id
    return Transaction.model_validate(payload)


def _seed_m303_ledger_and_wallet(bucket_id: str) -> None:
    from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ....application.calculations import IvaWalletDecisionRepository
    from ....application.invoices import build_catalogue_invoice
    from ....application.user_profile import profile_storage_session
    from ....domain.invoices import InvoiceCatalogue
    from ....domain.iva import InvoiceKind

    purchase_invoice = build_catalogue_invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor Quickfile SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="REC-2026-1T",
        issued_at=date(2026, 2, 15),
        taxable_base=Decimal("200.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
    )
    sale = _m303_transaction(
        "quickfile-sale-general",
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    purchase = _m303_transaction(
        "quickfile-purchase-general",
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        purchase_invoice_evidence_id=purchase_invoice.invoice_id,
    )
    with profile_storage_session(bucket_id):
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions((sale, purchase)),
        )
        InvoiceCatalogueRepository(bucket_id=bucket_id).save(InvoiceCatalogue.from_invoices((purchase_invoice,)))
        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif="12345678Z",
                target_year=2026,
                target_period=Period.from_year_and_code(2026, "1T"),
                selected_authority="aeat_wallet",
                selected_amount=Decimal("0.00"),
                wallet_amount=Decimal("0.00"),
                local_recurrence_amount=Decimal("0.00"),
                override_amount=None,
                divergence="match",
                blocked=False,
                stale_wallet=False,
                reason="quickfile M303 first-period neutral balance",
                wallet_captured_at=_IVA_WALLET_DECIDED_AT,
                decided_at=_IVA_WALLET_DECIDED_AT,
            ),
        )


def _stage_status(payload: dict[str, object]) -> dict[str, str]:
    stages = payload["stages"]
    assert isinstance(stages, list)
    result: dict[str, str] = {}
    for stage in stages:
        assert isinstance(stage, dict)
        # ``isinstance(stage, dict)`` only proves *some* dict — this data is
        # always parsed JSON envelope output, so re-keying with ``str(k)``
        # gives an honestly-typed ``dict[str, object]`` to index into.
        typed_stage = {str(k): v for k, v in stage.items()}
        name, status = typed_stage["stage"], typed_stage["status"]
        assert isinstance(name, str)
        assert isinstance(status, str)
        result[name] = status
    return result


def test_quickfile_runs_full_chain_to_exported_fichero(tmp_path: Path) -> None:
    """``aeat app quickfile`` for a calculable modelo writes a fichero-BOE file.

    Modelo 115 1T 2026 with one seeded retención observation is calculable, so
    the whole chain — readiness, create, calculate, verify, export — completes in
    one command and leaves a non-empty local artefact on disk.
    """

    _create_profile()
    _seed_m115_retencion_observation()
    out = tmp_path / "modelo-115.txt"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "115", "--year", "2026", "--period", "1T",
            "--casilla", "04=0",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    # The completed chain rides the shared envelope spine under the ``quickfile``
    # command key. Its ``status`` is an exit-0 state (``success``, or ``warning``
    # when the advisory readiness notice fires) — never ``error``; the exit code
    # and ``completed`` flag are the authoritative success signals.
    envelope = json.loads(result.output)
    assert envelope["command"] == "quickfile"
    assert envelope["status"] in {"success", "warning"}, result.output
    payload = _payload(result.output)
    assert payload["completed"] is True, result.output
    assert payload["stopped_at_stage"] is None
    assert payload["granted_verificado_completo"] is True
    assert payload["work_unit_id"]
    assert payload["calculation_revision_id"]

    statuses = _stage_status(payload)
    assert statuses["create"] == "ok"
    assert statuses["calculate"] == "ok"
    assert statuses["verify"] == "ok"
    assert statuses["export"] == "ok"
    # readiness is advisory and may be ok or warning; it must never refuse.
    assert statuses["readiness"] in {"ok", "warning"}

    # The terminal stage wrote a real fichero-BOE artefact locally.
    assert payload["export"] is not None
    assert payload["export"]["output_path"] == str(out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_quickfile_m303_fully_taxable_ledger_reaches_granted_boe_without_prorrata_input(
    tmp_path: Path,
) -> None:
    """A fully taxable M303 ledger path reaches granted verification and fichero-BOE export."""

    _create_profile()
    bucket_id = _seed_m303_profile_facts()
    _seed_m303_ledger_and_wallet(bucket_id)
    out = tmp_path / "modelo-303-2026-1T.boe"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "303", "--year", "2026", "--period", "1T",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    assert payload["completed"] is True, result.output
    assert payload["stopped_at_stage"] is None
    assert payload["granted_verificado_completo"] is True

    statuses = _stage_status(payload)
    assert statuses["calculate"] == "ok"
    assert statuses["verify"] == "ok"
    assert statuses["export"] == "ok"

    notice_text = json.dumps(_notices(result.output), sort_keys=True)
    assert "prorrata" not in notice_text.lower()
    assert payload["export"] is not None
    assert payload["export"]["output_path"] == str(out)
    exported = out.read_bytes()
    assert exported
    assert b"12345678Z" in exported


def test_quickfile_stops_instructively_when_verify_refuses(tmp_path: Path) -> None:
    """A verify refusal halts the chain at ``verify`` with ``export`` skipped.

    Modelo 130 1T 2025 verify refuses without clean cross-period evidence
    (M130 -> M100 dependency). Quickfile must stop at verify, mark export
    skipped, exit non-zero, and surface the blocking cross-period finding on the
    notices channel — never write an export file.
    """

    _create_profile()
    out = tmp_path / "modelo-130.txt"

    result = _invoke(
        [
            "--format", "json",
            "app", "quickfile",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
            "--output", str(out),
        ],
    )  # fmt: skip

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    payload = _payload(result.output)
    assert payload["completed"] is False
    assert payload["stopped_at_stage"] == "verify"
    assert payload["granted_verificado_completo"] is False
    assert payload["export"] is None

    statuses = _stage_status(payload)
    assert statuses["create"] == "ok"
    assert statuses["calculate"] == "ok"
    assert statuses["verify"] == "refused"
    assert statuses["export"] == "skipped"

    # The instructive stop carries the cross-period blocking finding on the shared
    # notices channel (a non-granted verify reads as a warning; NoticeSeverity has
    # no ERROR member), and the export artefact was never written.
    codes = {notice["code"] for notice in _notices(result.output)}
    assert any("cross_period" in code for code in codes), codes
    assert not out.exists()


def test_quickfile_requires_output_flag() -> None:
    """Quickfile refuses without ``--output`` (the export destination is required)."""

    _create_profile()
    result = _invoke(
        ["app", "quickfile", "--modelo", "115", "--year", "2026", "--period", "1T"],
    )
    assert result.exit_code != 0
    assert "output" in result.output.lower()
