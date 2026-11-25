"""Value-free installed ledger receipt types and synthetic scenario constants."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Final, Literal, cast

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

SCHEMA_VERSION = "ledger-01-installed-tui-v1"


def _supported_year() -> int:
    """The newest filing year the pinned authority supports."""
    with bundled_indexed_authority().operation() as operation:
        return operation.supported_filing_years().horizon


YEAR: Final = _supported_year()


COUNTERPARTY_NIF = "B00000281"


INVOICE_BASE = Decimal("100.00")


INVOICE_IVA = Decimal("21.00")


INVOICE_TOTAL = INVOICE_BASE + INVOICE_IVA


TUI_IMPORTED_TRANSACTION_AMOUNT = Decimal("10.00")


TUI_IMPORTED_TRANSACTION_DIRECTION = "INCOMING"


LINKED_IDENTITY_REFUSAL = "linked transaction identity cannot change without updating its invoice link"


STATEMENT_CSV_HEADER = "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID"


type ChildMode = Literal[
    "tui_only_capture_update",
    "tui_only_reopen",
    "cli_to_tui",
    "linked_refusal_readback",
    "tui_to_cli_reopen",
]


class LedgerInstalledTuiError(RuntimeError):
    """Raised when an installed public Ledger journey cannot prove its claim."""


@dataclass(frozen=True, slots=True)
class LedgerTuiChildReceipt:
    """Value-free result from one fresh installed Textual child."""

    schema_version: str
    status: Literal["proven"]
    mode: ChildMode
    product_origin: str
    product_init_sha256: str
    observations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return only public route and package evidence."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class LedgerContinuationReceipt:
    """Sanitized evidence for one sequential public-frontend continuation."""

    direction: Literal["cli_to_tui", "tui_to_cli"]
    status: Literal["proven"]
    tui_observations: tuple[str, ...]
    cli_command_count: int
    export_rows: int
    export_sha256: str

    def to_dict(self) -> dict[str, object]:
        """Return an artifact-safe continuation receipt."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class InstalledLedgerTuiReceipt:
    """Value-free result for the installed TUI-only and continuation journeys."""

    schema_version: str
    status: Literal["proven"]
    package_identity: str
    year: int
    product_origin: str
    product_init_sha256: str
    tui_only_observations: tuple[str, ...]
    cli_to_tui: LedgerContinuationReceipt
    tui_to_cli: LedgerContinuationReceipt

    def to_dict(self) -> dict[str, object]:
        """Return the durable acceptance receipt without financial payloads."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class TuiOnlyCliOracleReceipt:
    """Sanitized installed-CLI readback for the independently TUI-written fixture."""

    schema_version: str
    status: Literal["proven"]
    journey: Literal["tui_only_cli_oracle"]
    package_identity: str
    year: int
    product_origin: str
    product_init_sha256: str
    tui_only_observations: tuple[str, ...]
    cli_oracle_observations: tuple[str, ...]
    cli_command_count: int

    def to_dict(self) -> dict[str, object]:
        """Return value-free evidence for the supplemental installed journey."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class TuiOnlyRun:
    """Private coordinates retained only while an outer journey reads back its own store."""

    receipt: LedgerTuiChildReceipt
    cli_oracle_observations: tuple[str, ...]
    cli_command_count: int
