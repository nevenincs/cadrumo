"""Value-free installed IVA source, authority, capture and reopen receipt contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final, Literal, cast

_SCHEMA_VERSION: Final = "iva-01-installed-tui-capture-reopen-v2"


_PERIOD: Final = "1T"


_N26_HEADER: Final = "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID"


_SOURCE_MODULES: Final[tuple[tuple[str, str], ...]] = (
    ("cadrumo.application.ledger.actions_manual", "src/cadrumo/application/ledger/actions_manual.py"),
    ("cadrumo.entrypoints.tui.launcher", "src/cadrumo/entrypoints/tui/launcher.py"),
    ("cadrumo.entrypoints.tui.ledger.classification", "src/cadrumo/entrypoints/tui/ledger/classification.py"),
    ("cadrumo.entrypoints.tui.ledger.entries", "src/cadrumo/entrypoints/tui/ledger/entries.py"),
    ("cadrumo.entrypoints.tui.ledger.import_flow", "src/cadrumo/entrypoints/tui/ledger/import_flow.py"),
)


_CLASSIFICATION_FIELDS: Final[tuple[str, ...]] = (
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "iva_category",
    "deduction_fact_kind",
)


_UNEXERCISED: Final[tuple[str, ...]] = (
    "invoice_capture_or_link",
    "m303_secure_attestation",
    "m303_work_creation",
    "m303_calculation",
    "m303_verification",
    "m303_export",
)


class IvaInstalledTuiError(RuntimeError):
    """Raised when the bounded installed IVA evidence cannot be proven."""


@dataclass(frozen=True, slots=True)
class AuthorityIdentity:
    """The published authority pair selected for this isolated run."""

    logical_generation: str
    descriptor_sha256: str
    database_sha256: str


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """A digest of the TUI source members that must be in the built wheel."""

    manifest_sha256: str
    module_sha256s: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ChildHandle:
    """Value-free handle for one fresh installed TUI child process."""

    mode: Literal["capture", "reopen"]
    returncode: int
    receipt_status: str
    receipt_sha256: str
    stdout_sha256: str
    stderr_sha256: str


@dataclass(frozen=True, slots=True)
class InstalledIvaTuiReceipt:
    """Sanitized evidence for the deliberately limited IVA acceptance slice."""

    schema_version: str
    status: Literal["proven"]
    filing_year: int
    partial_acceptance_ids: tuple[str, ...]
    acceptance_scope: Literal["partial_ledger_capture_classification_reopen"]
    tui_only_path: str
    continuation_path: str
    product_origin: str
    product_init_sha256: str
    package_version: str
    package_payload_sha256: str
    source_manifest_sha256: str
    source_module_count: int
    authority_generation: str
    authority_descriptor_sha256: str
    authority_database_sha256: str
    child_handles: tuple[ChildHandle, ChildHandle]
    transaction_count: int
    classification_fields_submitted: tuple[str, ...]
    canonical_fields_read_back: tuple[str, ...]
    canonical_classification_fingerprint: str
    continuation_command_handles: tuple[str, ...]
    deduction_kind_readback: str
    unexercised: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return only identity, control, and digest evidence."""
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class _CaptureChildReceipt:
    """Value-free capture-child receipt passed to the outer driver."""

    schema_version: str
    status: Literal["proven"]
    mode: Literal["capture"]
    product_origin: str
    product_init_sha256: str
    package_version: str
    source_manifest_sha256: str
    source_module_count: int
    authority_generation: str
    authority_descriptor_sha256: str
    authority_database_sha256: str
    transaction_ids: tuple[str, str]
    classification_fields_submitted: tuple[str, ...]
    public_control_handles: tuple[str, ...]
    unexercised: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class _ReopenChildReceipt:
    """Value-free fresh-TUI-session receipt passed to the outer driver."""

    schema_version: str
    status: Literal["proven"]
    mode: Literal["reopen"]
    product_origin: str
    product_init_sha256: str
    package_version: str
    source_manifest_sha256: str
    source_module_count: int
    authority_generation: str
    authority_descriptor_sha256: str
    authority_database_sha256: str
    observed_transaction_ids: tuple[str, str]
    public_control_handles: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))
