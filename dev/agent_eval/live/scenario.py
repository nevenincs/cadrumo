"""Live scenario files: what the person sets up, what the agent is asked, and what the oracle expects.

A live scenario sits beside the golden scenarios but answers a different
question. A golden scenario declares a trajectory the runner checks against
the command tree. A live scenario declares a run against a real package: the
profile facts the person states, the ledger rows, the inputs a calculation
needs, the export file, the required subsequence of operations, and the
figures the oracle compares. The agent's prompt is part of it and carries no
secret. :meth:`LiveScenario.golden` projects the parts the existing scorer
reads.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cadrumo.core.toml import parse_toml

from .._models import GoldenScenario

_FROZEN = ConfigDict(frozen=True, strict=True, extra="forbid")
SCENARIO_DIRECTORY: Final = Path(__file__).with_name("scenarios")
EXPORT_PATH_PLACEHOLDER: Final = "{export_path}"


def _decimal(value: str) -> str:
    try:
        Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"not a decimal amount: {value!r}") from error
    return value


class LedgerRow(BaseModel):
    """One ledger row the agent books and classifies, in the operations' own field names."""

    model_config = _FROZEN

    booked_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount: str
    direction: str = Field(pattern=r"^(INCOMING|OUTGOING)$")
    description: str = Field(min_length=1)
    counterparty: str = Field(min_length=1)
    classification: dict[str, str]

    @field_validator("amount")
    @classmethod
    def _amount(cls, value: str) -> str:
        return _decimal(value)


class CalculationInputs(BaseModel):
    """The casilla and binding values the person supplies to the calculation."""

    model_config = _FROZEN

    casillas: dict[str, str] = {}
    bindings: dict[str, str] = {}


class Expected(BaseModel):
    """The oracle's figures: casilla values from the published example, and IVA agreement keys."""

    model_config = _FROZEN

    casillas: dict[str, str] = Field(min_length=1)
    ledger_iva_casillas: dict[str, str] = {}

    @field_validator("casillas")
    @classmethod
    def _decimals(cls, value: dict[str, str]) -> dict[str, str]:
        for amount in value.values():
            _decimal(amount)
        return value


class Prompt(BaseModel):
    """The agent's system text and task; the task names the export path through a placeholder."""

    model_config = _FROZEN

    system: str = Field(min_length=1)
    task: str = Field(min_length=1)

    @field_validator("task")
    @classmethod
    def _names_export_path(cls, value: str) -> str:
        if EXPORT_PATH_PLACEHOLDER not in value:
            raise ValueError(f"the task must name the export file through {EXPORT_PATH_PLACEHOLDER}")
        return value


class LiveScenario(BaseModel):
    """One live scenario file."""

    model_config = _FROZEN

    name: str = Field(min_length=1)
    modelo: str = Field(pattern=r"^\d{3}$")
    filing_year: int = Field(ge=2000, le=2100)
    period: str = Field(min_length=1)
    registry_revision: str = Field(min_length=1)
    skill_name: str = Field(min_length=1)
    export_file: str = Field(pattern=r"^[A-Za-z0-9._-]+$")
    required_trajectory: tuple[str, ...] = Field(min_length=1)
    profile: dict[str, str] = Field(min_length=1)
    rows: tuple[LedgerRow, ...] = Field(min_length=1)
    calculation: CalculationInputs
    expected: Expected
    prompt: Prompt

    def task(self, export_path: Path) -> str:
        """The agent's task with the run's export path filled in."""
        return self.prompt.task.replace(EXPORT_PATH_PLACEHOLDER, str(export_path)).strip()

    def golden(self) -> GoldenScenario:
        """The projection the existing live scorer reads: the required subsequence as the expected trajectory."""
        return GoldenScenario(
            name=self.name,
            modelo=self.modelo,
            filing_year=self.filing_year,
            period=self.period,
            skill_name=self.skill_name,
            expected_trajectory=self.required_trajectory,
            provenance_required=False,
        )


def load_scenario(name: str, directory: Path = SCENARIO_DIRECTORY) -> LiveScenario:
    """Load one live scenario by its file stem or its declared name."""
    for path in sorted(directory.glob("*.toml")):
        document = parse_toml(path.read_text(encoding="utf-8"))
        if name in {path.stem, document.get("name")}:
            return LiveScenario.model_validate(document, strict=False)
    known = ", ".join(sorted(path.stem for path in directory.glob("*.toml")))
    raise KeyError(f"no live scenario named {name!r}; known: {known}")


def scenario_names(directory: Path = SCENARIO_DIRECTORY) -> tuple[str, ...]:
    """Every live scenario file stem."""
    return tuple(sorted(path.stem for path in directory.glob("*.toml")))
