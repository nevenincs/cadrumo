"""The persona catalogue check that runs before any producer is trusted.

Until the persona reader exists, this is a structural parse: every TOML file
loads and every ledger is a CSV with a header and rows. When the reader lands,
:func:`persona_catalogue_findings` is the one hook to route through it, so the
check validates personas by the same contract the materialiser reads.
"""

from __future__ import annotations

import csv
import tomllib
from pathlib import Path
from typing import Final

PERSONA_FILES: Final[tuple[str, ...]] = ("persona.toml", "documents.toml", "expectations.toml")
LEDGER_FILE: Final[str] = "ledger.csv"
IDENTITIES_FILE: Final[str] = "identities.toml"


def _toml_finding(path: Path) -> str | None:
    try:
        tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return f"{path.name}: {exc}"
    return None


def _ledger_finding(path: Path) -> str | None:
    try:
        rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return f"{path.name}: {exc}"
    if len(rows) < 2:
        return f"{path.name}: no header and rows"
    width = len(rows[0])
    ragged = [number for number, row in enumerate(rows[1:], start=2) if row and len(row) != width]
    if ragged:
        return f"{path.name}: rows {ragged} do not have the header's {width} columns"
    return None


def persona_catalogue_findings(catalogue: Path) -> tuple[str, ...]:
    """Every reason the catalogue at ``catalogue`` cannot be read; empty when it can."""
    if not catalogue.is_dir():
        return (f"no persona catalogue at {catalogue}",)
    findings: list[str] = []
    identities = catalogue / IDENTITIES_FILE
    if not identities.is_file():
        findings.append(f"{IDENTITIES_FILE}: absent")
    elif (finding := _toml_finding(identities)) is not None:
        findings.append(finding)
    personas = sorted(path for path in catalogue.iterdir() if path.is_dir())
    if not personas:
        findings.append("no personas")
    for persona in personas:
        for name in PERSONA_FILES:
            path = persona / name
            finding = _toml_finding(path) if path.is_file() else f"{name}: absent"
            if finding is not None:
                findings.append(f"{persona.name}/{finding}")
        ledger = persona / LEDGER_FILE
        finding = _ledger_finding(ledger) if ledger.is_file() else f"{LEDGER_FILE}: absent"
        if finding is not None:
            findings.append(f"{persona.name}/{finding}")
    return tuple(findings)
