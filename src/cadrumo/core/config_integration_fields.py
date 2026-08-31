"""Google, workbook-parity, and financial-ingest settings.

Split from :mod:`~core.config` to keep the central settings facade within the
line budget. :class:`~core.config.Settings` inherits these fields with their
declared validation and defaults. Product-owned fields derive ``CADRUMO_*``
environment names; authority-owned integration fields retain explicit
``AEAT_*`` names.

See Also:
    :class:`~core.config.Settings`
        Central environment facade that inherits this mixin and normalizes its
        path fields.
    :func:`~core.config.load_settings`
        Runtime entry point used by integration consumers to read these fields.
    :mod:`~adapters.outbound.storage._factory`
        Outbound storage factory that consumes the Google Drive vault defaults.
    :mod:`~adapters.inbound.financial.providers._csv`
        CSV financial-ingest provider that reads the default CSV encoding.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import Field, field_validator

from .config_runtime_fields import CadrumoRuntimeSettings
from .external_constants import DEFAULT_CURRENCY

FORMER_PRODUCT_GOOGLE_DRIVE_VAULT_FOLDER_NAME: Final = "aeat-vault"


class CadrumoIntegrationSettings(CadrumoRuntimeSettings):
    """Settings for external integration defaults and local financial stores."""

    # ── Google integration ───────────────────────────────────────────────
    cadrumo_google_drive_vault_folder_name: str = Field(
        default="cadrumo-vault",
        min_length=1,
        description="Folder name created under the Google Drive root for the Cadrumo vault",
    )
    cadrumo_google_oauth_access_refresh_buffer_s: int = Field(
        default=300,
        gt=0,
        description="Clock-skew buffer (seconds) before nominal expiry when refreshing Google access tokens",
    )

    @field_validator("cadrumo_google_drive_vault_folder_name")
    @classmethod
    def _refuse_former_product_google_drive_vault_folder(cls, value: str) -> str:
        if value.strip().casefold() == FORMER_PRODUCT_GOOGLE_DRIVE_VAULT_FOLDER_NAME:
            raise ValueError("the former product Google Drive vault folder is not supported")
        return value

    # ── Registry cache / Sheets ──────────────────────────────────────────
    cadrumo_registry_disk_cache_dir: Path | None = Field(
        default=None,
        description=(
            "Override for the cross-process registry disk-pickle directory. "
            "When unset, production derives <cadrumo_local_storage_root>/cache/registry "
            "and pytest runs share the host temp directory for the immutable "
            "bundled-root pickle. Set only by test isolation to redirect the "
            "cache onto a test-owned directory, so a test asserting exclusive "
            "pickle state never races sibling pytest-xdist workers."
        ),
    )
    cadrumo_registry_disk_cache_max_entries: int = Field(
        default=8,
        ge=1,
        description=(
            "Maximum number of registry disk-cache pickles retained per cache "
            "directory; after each write the oldest excess pickles are pruned "
            "(best-effort) so accumulated per-fingerprint pickles cannot grow "
            "without bound."
        ),
    )
    cadrumo_calc_sheets_recalc_delay_s: float = Field(
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
    cadrumo_financial_txs_dir: Path = Field(
        default=Path("financial") / "transactions",
        description="Directory where the transaction catalogue JSON file is stored",
    )
    cadrumo_invoices_dir: Path = Field(
        default=Path("financial") / "invoices",
        description="Directory where the invoice catalogue JSON file is stored",
    )
    cadrumo_attachments_dir: Path = Field(
        default=Path("financial") / "attachments",
        description="Root directory for the attachment byte and manifest store",
    )
    cadrumo_usage_ratios_path: Path = Field(
        default=Path("financial") / "usage-ratios.json",
        description="User-configured per-category usage ratio overrides",
    )


__all__ = ["CadrumoIntegrationSettings"]
