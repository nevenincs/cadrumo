"""Prepare the isolated synthetic data used by the README CLI recording."""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

from cadrumo.application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from cadrumo.application.aggregation.retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress
from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from cadrumo.core.link_safety import is_link_like
from dev._paths import REPO_ROOT, UTF_8
from dev.packaging.command_execution import run_command

_UTF_8: Final[str] = UTF_8

VAR_ROOT = REPO_ROOT / "var"
DEMO_ROOT = VAR_ROOT / "readme-demo"
DEMO_VALUE = "readme-demo-only-synthetic-passphrase-2026"
_CLI_BOOTSTRAP = "from cadrumo.entrypoints.cli.bootstrap import main; main()"


def _reset_demo_root() -> None:
    """Recreate the demo root after proving recursive cleanup cannot escape ``var``."""
    resolved_repo = REPO_ROOT.resolve(strict=True)
    resolved_var = VAR_ROOT.resolve(strict=False)
    resolved_demo = DEMO_ROOT.resolve(strict=False)
    if is_link_like(VAR_ROOT):
        raise RuntimeError(f"refusing to use symlinked var root: {VAR_ROOT}")
    try:
        resolved_var.relative_to(resolved_repo)
    except ValueError as exc:
        raise RuntimeError(f"refusing demo root outside repository: {resolved_var}") from exc
    try:
        relative_demo = resolved_demo.relative_to(resolved_var)
    except ValueError as exc:
        raise RuntimeError(f"refusing cleanup outside {resolved_var}") from exc
    if relative_demo == Path("."):
        raise RuntimeError("refusing to clean the var root itself")
    if is_link_like(DEMO_ROOT):
        raise RuntimeError(f"refusing to clean symlinked demo root: {DEMO_ROOT}")
    if DEMO_ROOT.exists():
        shutil.rmtree(resolved_demo)
    DEMO_ROOT.mkdir(parents=True)


def demo_environment() -> dict[str, str]:
    """Return a clean Cadrumo environment rooted in the disposable demo directory."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    environment.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(DEMO_ROOT),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "CADRUMO_SECRET_PASSPHRASE": DEMO_VALUE,
            "CADRUMO_SECRET_STORE_DIR": str(DEMO_ROOT / "secrets"),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        },
    )
    return environment


def _run_cli(stage: str, *arguments: str, environment: dict[str, str], secrets: dict[str, str] | None = None) -> str:
    """Run one real CLI process, returning its stdout, and surface diagnostics if setup fails.

    ``secrets`` is written as one JSON document to the process's stdin for verbs
    invoked with ``--secrets-stdin``; CLI secret input never reads the environment.
    """
    result = run_command(
        [sys.executable, "-c", _CLI_BOOTSTRAP, *arguments],
        cwd=REPO_ROOT,
        environment=environment,
        errors="replace",
        timeout_seconds=180,
        input_text=None if secrets is None else json.dumps(secrets, separators=(",", ":")),
    )
    if result.returncode == 0:
        return result.stdout
    diagnostics = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    raise RuntimeError(f"{stage} failed with exit code {result.returncode}\n{diagnostics}")


def _received_rent_invoice_id(stdout: str) -> str:
    """Return the invoice id from the JSON payload printed by ``ledger invoice add``."""
    document = json.loads(stdout)
    payload = document.get("result") if isinstance(document, dict) else None
    invoice_id = payload.get("invoice_id") if isinstance(payload, dict) else None
    if not isinstance(invoice_id, str) or not invoice_id:
        raise RuntimeError(f"rent invoice setup returned no invoice_id\n{stdout.strip()}")
    return invoice_id


def prepare_demo() -> None:
    """Create the proven profile and one invoice-backed Modelo 115 2025 1T retención.

    The received urban-rent invoice carries a 2700.00 base and a 19% retención
    of 513.00; its single paid allocation settles the invoice grand total
    (2700.00 + 21% IVA = 3267.00) less the retención, 2754.00, and carries the
    property detail Modelo 180 requires for rent.
    """
    _reset_demo_root()
    # An operator-selected directory override must already exist; the product refuses to create it.
    (DEMO_ROOT / "secrets").mkdir()
    environment = demo_environment()
    _run_cli(
        "profile setup",
        "config",
        "profile",
        "create",
        "operator",
        "--quiet",
        "--secrets-stdin",
        "--accept-defaults",
        "--entity-type",
        "natural_person",
        "--tax-id",
        "12345678Z",
        "--name",
        "Operator",
        "--surnames",
        "Quickfile",
        "--activity",
        "design",
        "--activity-start-date",
        "2025-01-01",
        "--tax-residence-jurisdiction-scope",
        "common_regime",
        "--tax-residence-ccaa",
        "madrid",
        "--irpf-income-categories",
        "actividad_economica",
        "--irpf-estimation-regime",
        "directa_normal",
        "--iva-regime",
        "GENERAL",
        "--iva-m303-regime-composition",
        "general",
        "--no-iva-redeme-enrolled",
        "--no-iva-cash-accounting-regime-enrolled",
        "--no-iva-voluntary-sii-enrolled",
        "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
        environment=environment,
        secrets={"passphrase": DEMO_VALUE, "passphrase_confirmation": DEMO_VALUE},
    )
    # The login session lets the recorded quickfile run without a secrets channel on a
    # host with an OS keychain; the setup commands below authenticate per process so
    # they do not depend on one.
    _run_cli(
        "profile login",
        "config",
        "login",
        "operator",
        "--secrets-stdin",
        environment=environment,
        secrets={"passphrase": DEMO_VALUE},
    )
    profile_secrets = {"profile_passphrase": DEMO_VALUE}
    _run_cli(
        "profile complete setup",
        "--format", "json", "--profile-secrets-stdin",
        "config", "profile", "complete-setup",
        environment=environment,
        secrets=profile_secrets,
    )  # fmt: skip
    paid_on = date(2025, 3, 15)
    invoice_output = _run_cli(
        "rent invoice setup",
        "--format", "json", "--profile-secrets-stdin",
        "app", "ledger", "invoice", "add",
        "--kind", "received",
        "--counterparty-name", "Arrendador Ejemplo SL",
        "--counterparty-nif", "B12345674",
        "--invoice-number", "M115-RENT-2025-001",
        "--invoice-date", paid_on.isoformat(),
        "--country-code", "ES",
        "--taxable-base", "2700.00", "--iva-rate", "21",
        "--retention-rate", "0.19", "--retention-amount", "513.00",
        "--iva-category", "domestic_general",
        environment=environment,
        secrets=profile_secrets,
    )  # fmt: skip
    request = InvoiceWithholdingEvidenceRequest(
        invoice_id=_received_rent_invoice_id(invoice_output),
        income_kind=WithholdingIncomeKind.URBAN_RENT,
        scheme="arrendamiento_urbano",
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id="readme-rent-payment-2025-03-15",
        payment_occurred_on=paid_on,
        allocation_id="readme-rent-allocation-1",
        allocated_base=Decimal("2700.00"),
        allocated_withholding=Decimal("513.00"),
        allocated_settlement=Decimal("2754.00"),
        idempotency_key="readme-rent-allocation-1",
        modelo_180_property=Modelo180PropertyEvidence(
            property_key="readme-rent-property",
            situation="1",
            cadastral_reference="1234567VK4713C0001XY",
            address=Modelo180StructuredAddress(
                province_code="28",
                municipality_code="079",
                municipality="Madrid",
                locality="Madrid",
                postal_code="28001",
                street_type="CL",
                street_name="Ejemplo",
                number_type="NUM",
                house_number="1",
            ),
            recipient_province_code="28",
            modality="1",
            accrual_year=2025,
            withholding_percentage=Decimal("19.00"),
        ),
    )
    _run_cli(
        "rent retencion setup",
        "--format", "json", "--profile-secrets-stdin",
        "app", "modelo", "aggregate",
        "--modelo", "115", "--year", "2025", "--period", "1T",
        "--received-invoice-retencion", request.model_dump_json(),
        environment=environment,
        secrets=profile_secrets,
    )  # fmt: skip


def main() -> None:
    """Prepare the demo and print the stable renderer handoff marker."""
    prepare_demo()
    print("demo ready")


if __name__ == "__main__":
    main()
