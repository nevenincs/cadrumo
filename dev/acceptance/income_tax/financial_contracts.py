"""Synthetic installed financial inputs and value-free child receipt contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Final, Literal, cast

if TYPE_CHECKING:
    pass


_SCHEMA_VERSION = "income-01-installed-tui-financial-v2"


_N26_HEADER = "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID"


_SYNTHETIC_COUNTERPARTY_NIF = "A58818501"


@dataclass(frozen=True, slots=True)
class ProfileFactEntry:
    """One public Profile Manager edit, addressed by row and visible choice."""

    path: str
    value: str | None = None
    option_index: int | None = None


@dataclass(frozen=True, slots=True)
class FinancialChildReceipt:
    """Sanitized installed-TUI financial-run evidence."""

    schema_version: str
    status: Literal["proven"]
    product_origin: str
    product_init_sha256: str
    year: int
    transaction_imports: int
    invoice_forms: int
    reconciliation_links: int
    calendar_work: tuple[str, ...]
    lifecycle_operations: tuple[str, ...]
    canonical_value_fingerprint: str
    artifact_sha256s: tuple[str, ...]
    annual_xsd_validation: dict[str, object]
    fresh_session_readback: str

    def to_dict(self) -> dict[str, object]:
        """Return the value-free receipt representation."""
        return cast("dict[str, object]", asdict(self))


_EDIT_SECONDS: Final = 120.0


#: The annual-only facts the scenario declares, addressed as the workbench addresses them.
_ANNUAL_EDITS: Final[tuple[tuple[tuple[str, str], str], ...]] = (
    (("casilla", "0001"), "declarante"),
    (("casilla", "0165"), "declarante"),
    (("casilla", "0166"), "A05"),
    (("binding", "renta-modelo-100-estimacion-directa-es-normal"), "1"),
    (("binding", "renta-certificado-trabajo-retenciones"), "0"),
)
