"""Resumable seed receipt and stable refusal contracts for export parity."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from .scenario import (
    YEARS,
)

RECEIPT_SCHEMA: Final = "export-parity.seed-receipt/v1"


_ACTOR: Final = "export-parity-seed"


_UNCHANGED_UPDATE: Final = "must change at least one ledger field"


_PROFILE: Final = f"income-{YEARS[0]}"


_PERIODIC: Final = ("303", "130", "111", "115")


_ANNUAL: Final = ("390", "190", "180", "100")


_M100_CASILLAS: Final = ("0001=declarante", "0165=declarante", "0166=A05")


#: Renta bindings the scenario answers, applied only where the selected revision declares them.
_M100_BINDINGS: Final = {
    "renta-modelo-100-estimacion-directa-es-normal": "1",
    "renta-certificado-trabajo-retenciones": "0",
}


class SeedError(RuntimeError):
    """A seed stage could not complete through the public CLI."""


class SeedRefusalError(SeedError):
    """The product refused one seed command; the refusal is already on the receipt."""


@dataclass(slots=True)
class SeedReceipt:
    """Sanitized, resumable record of a seed run: identifiers and codes, never amounts or secrets."""

    scenario: str
    authority_generation: str
    executable_sha256: str
    carry_evidence: str
    completed_stages: list[str] = field(default_factory=list)
    identifiers: dict[str, str] = field(default_factory=dict)
    blocked: dict[str, str] = field(default_factory=dict)
    updated: str = ""

    def save(self, path: Path) -> None:
        """Write the receipt beside the store."""
        self.updated = datetime.now(UTC).isoformat()
        path.write_text(json.dumps(asdict(self) | {"schema": RECEIPT_SCHEMA}, indent=2, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path: Path) -> SeedReceipt | None:
        """Read an earlier receipt so completed stages are skipped."""
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.pop("schema", None)
        return cls(**payload)
