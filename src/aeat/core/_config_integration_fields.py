"""Google, workbook-parity, and financial-ingest settings.

Split from :mod:`core.config` to keep the central settings facade within the
line budget. :class:`~core.config.Settings` inherits these fields, so each field
keeps the same ``AEAT_*`` environment variable name, validation, and default.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from ._config_runtime_fields import AeatRuntimeSettings
from .external_constants import DEFAULT_CURRENCY
from .paths import PROJECT_ROOT


class AeatIntegrationSettings(AeatRuntimeSettings):
    """Settings for external integration defaults and local financial stores."""

    # ── Google integration ───────────────────────────────────────────────
    aeat_google_drive_vault_folder_name: str = Field(
        default="aeat-vault",
        min_length=1,
        description="Folder name created under the Google Drive root for the AEAT vault",
    )
    aeat_google_oauth_access_refresh_buffer_s: int = Field(
        default=300,
        gt=0,
        description="Clock-skew buffer (seconds) before nominal expiry when refreshing Google access tokens",
    )
    # ── Workbook parity / Sheets ─────────────────────────────────────────
    aeat_workbook_parity_per_file_timeout_s: float = Field(
        default=15.0,
        gt=0,
        description="Default per-file timeout (seconds) for workbook-parity scans",
    )
    aeat_workbook_parity_recalc_timeout_s: int = Field(
        default=60,
        gt=0,
        description="Subprocess timeout (seconds) when forcing workbook recalculation",
    )
    aeat_workbook_parity_libreoffice_timeout_s: int = Field(
        default=120,
        gt=0,
        description="Subprocess timeout (seconds) for the LibreOffice binary XLS conversion fall-back",
    )
    aeat_registry_parity_store_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "audit" / "registry" / "parity",
        description="Directory where registry parity tape artifacts are archived by default",
    )
    aeat_calc_sheets_recalc_delay_s: float = Field(
        default=2.0,
        gt=0,
        description="Delay (seconds) waiting for Google Sheets server-side recalculation between parity polls",
    )
    # ── Financial ingest ───────────────────────────────────────────────────
    financial_base_currency: str = Field(
        default=DEFAULT_CURRENCY,
        description="Fallback ISO 4217 currency used when a financial source omits a per-row currency",
    )
    financial_default_csv_encoding: str = Field(
        default="utf-8",
        description="Preferred encoding attempted first when decoding financial CSV sources",
    )
    aeat_financial_txs_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "transactions",
        description="Directory where the transaction catalogue JSON file is stored",
    )
    aeat_invoices_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "invoices",
        description="Directory where the invoice catalogue JSON file is stored",
    )
    aeat_attachments_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "attachments",
        description="Root directory for the attachment byte and manifest store",
    )
    aeat_purchase_invoice_evidence_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "purchase-invoice-evidence",
        description="Root directory for purchase invoice evidence record manifests",
    )
    aeat_usage_ratios_path: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "usage-ratios.json",
        description="User-configured per-category usage ratio overrides",
    )
    aeat_ledgers_dir: Path = Field(
        default=PROJECT_ROOT / "var" / "financial" / "ledgers",
        description="Directory for encrypted inventory and amortization ledgers",
    )


__all__ = ["AeatIntegrationSettings"]
