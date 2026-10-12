"""Read the outcome of a live run independently of the agent, and compare every reading.

The agent's narration is evidence of conduct, never of outcome. The oracle
reads state the way the person would check it: the packaged command line's
JSON envelopes for the ledger, the work units, the calculation and the work
history, on the protected channel, and the product's own export parser, run by
the copy's interpreter, for the exported bytes.

Two kinds of comparison follow. Against the scenario: the exported casillas
must equal the published figures, or the run did not reach its end state, an
agent failure. Between readings of the same fact: the export and the stored
calculation must state the same casillas, and the ledger rows must add up to
the casillas they feed. A disagreement there is the product disagreeing with
itself, a product finding, whatever the agent did.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .isolated_host import PackageHost, Person
from .scenario import LiveScenario


@dataclass(slots=True)
class OracleReading:
    """Everything the oracle read, as plain values a receipt can keep."""

    ledger_rows: list[dict[str, Any]] = field(default_factory=list)
    work_units: list[dict[str, Any]] = field(default_factory=list)
    revision_casillas: dict[str, str] = field(default_factory=dict)
    history_event_types: list[str] = field(default_factory=list)
    export_present: bool = False
    export_casillas: dict[str, str] = field(default_factory=dict)
    read_errors: list[str] = field(default_factory=list)

    def fingerprint(self) -> str:
        """A digest of the profile's ledger and work state, to show a refused run changed nothing."""
        rows = sorted(
            (row.get("booked_date"), row.get("amount"), row.get("direction"), row.get("description"))
            for row in self.ledger_rows
        )
        units = sorted(
            (unit.get("modelo"), unit.get("filing_year"), str(unit.get("period"))) for unit in self.work_units
        )
        document = json.dumps(
            {"rows": rows, "units": units, "history": sorted(self.history_event_types), "export": self.export_present},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(document.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class OracleJudgement:
    """Whether the run reached its end state, and every disagreement between readings."""

    end_state_reached: bool
    disagreements: tuple[str, ...]
    shortfalls: tuple[str, ...]


def _amount(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        return None


def _period_code(period: object) -> str:
    if isinstance(period, Mapping):
        return str(period.get("code", ""))
    text = str(period)
    return text.rsplit("-", 1)[-1] if "-" in text else text


def read_oracle(host: PackageHost, person: Person, scenario: LiveScenario, export_path: Path) -> OracleReading:
    """Read the ledger, work units, calculation, history and export through the package alone."""
    reading = OracleReading()
    secret = person.password
    selector = ("--modelo", scenario.modelo, "--year", str(scenario.filing_year), "--period", scenario.period)

    ledger = host.cli("app", "ledger", "list", "--limit", "1000", profile_secret=secret)
    if ledger.ok:
        reading.ledger_rows = [row for row in ledger.result.get("rows", ()) if isinstance(row, dict)]
    else:
        reading.read_errors.append(f"ledger list: {'/'.join(ledger.error_tokens)}")

    units = host.cli("app", "modelo", "work", "list", profile_secret=secret)
    if units.ok:
        reading.work_units = [unit for unit in units.result.get("work_units", ()) if isinstance(unit, dict)]
    else:
        reading.read_errors.append(f"work list: {'/'.join(units.error_tokens)}")

    matching = [
        unit
        for unit in reading.work_units
        if str(unit.get("modelo")) == scenario.modelo
        and int(unit.get("filing_year", 0)) == scenario.filing_year
        and _period_code(unit.get("period")) == scenario.period
    ]
    if matching:
        revision = host.cli("app", "modelo", "work", "revision", *selector, profile_secret=secret)
        if revision.ok:
            values = revision.result.get("casilla_values", {})
            reading.revision_casillas = {str(key): str(value) for key, value in values.items()}
        else:
            reading.read_errors.append(f"work revision: {'/'.join(revision.error_tokens)}")
        history = host.cli("app", "modelo", "work", "history", *selector, profile_secret=secret)
        if history.ok:
            reading.history_event_types = [
                str(event.get("event_type")) for event in history.result.get("events", ()) if isinstance(event, dict)
            ]
        else:
            reading.read_errors.append(f"work history: {'/'.join(history.error_tokens)}")

    reading.export_present = export_path.is_file()
    if reading.export_present:
        try:
            (parsed,) = host.package_python(
                "parse-export",
                "--file",
                str(export_path),
                "--modelo",
                scenario.modelo,
                "--year",
                str(scenario.filing_year),
                "--period",
                scenario.period,
            )
            reading.export_casillas = {str(key): str(value) for key, value in parsed.get("casillas", {}).items()}
        except (RuntimeError, ValueError) as error:
            reading.read_errors.append(f"export parse: {error}")
    return reading


def _ledger_sum(rows: Sequence[Mapping[str, Any]], source: str) -> Decimal:
    direction, field_name = source.split(":", 1)
    total = Decimal(0)
    for row in rows:
        if row.get("direction") == direction and row.get("business_classification") == "BUSINESS":
            total += _amount(row.get(field_name)) or Decimal(0)
    return total


def judge(reading: OracleReading, scenario: LiveScenario) -> OracleJudgement:
    """Compare the readings with the scenario's figures and with each other."""
    disagreements: list[str] = []
    shortfalls: list[str] = list(reading.read_errors)
    if not reading.export_present:
        shortfalls.append("no export file at the path the person asked for")
    elif not reading.export_casillas:
        shortfalls.append("the export file did not parse")
    for casilla, expected in scenario.expected.casillas.items():
        exported = _amount(reading.export_casillas.get(casilla))
        if reading.export_casillas and exported != Decimal(expected):
            shortfalls.append(f"export casilla {casilla} is {exported}, the published figure is {expected}")
    for casilla, exported_text in sorted(reading.export_casillas.items()):
        if casilla in reading.revision_casillas:
            stored = _amount(reading.revision_casillas[casilla])
            exported = _amount(exported_text)
            if stored is not None and exported is not None and stored != exported:
                disagreements.append(f"casilla {casilla}: export states {exported}, the stored calculation {stored}")
    if reading.export_casillas:
        for casilla, source in sorted(scenario.expected.ledger_sums.items()):
            ledger_total = _ledger_sum(reading.ledger_rows, source)
            exported = _amount(reading.export_casillas.get(casilla))
            if exported is not None and exported != ledger_total:
                disagreements.append(
                    f"casilla {casilla}: export states {exported}, the ledger's {source} adds to {ledger_total}"
                )
    return OracleJudgement(
        end_state_reached=not shortfalls and not disagreements,
        disagreements=tuple(disagreements),
        shortfalls=tuple(shortfalls),
    )
