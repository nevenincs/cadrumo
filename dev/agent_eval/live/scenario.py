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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    """The casilla and binding values and filing answers the person supplies to the calculation.

    ``joint_return_elected`` is the person's answer to the one question every
    Modelo 303 period asks; it stays ``None`` for a modelo that does not ask it.
    """

    model_config = _FROZEN

    casillas: dict[str, str] = {}
    bindings: dict[str, str] = {}
    joint_return_elected: bool | None = None


class Expected(BaseModel):
    """The oracle's figures, and which ledger sums each casilla must agree with.

    ``ledger_sums`` maps a casilla to ``DIRECTION:field``: the sum of that
    ledger field over the business rows of that direction, read back through the
    command line, must equal the exported casilla.
    """

    model_config = _FROZEN

    casillas: dict[str, str] = Field(min_length=1)
    ledger_sums: dict[str, str] = {}

    @field_validator("ledger_sums")
    @classmethod
    def _sources(cls, value: dict[str, str]) -> dict[str, str]:
        for source in value.values():
            direction, _, field_name = source.partition(":")
            if direction not in {"INCOMING", "OUTGOING"} or not field_name:
                raise ValueError(f"a ledger sum is DIRECTION:field, not {source!r}")
        return value

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
    provisional: str = ""
    """Why the scenario cannot run yet; a provisional scenario is reported unavailable, never run."""

    @model_validator(mode="after")
    def _303_answers_the_joint_return_question(self) -> LiveScenario:
        if (self.modelo == "303") != (self.calculation.joint_return_elected is not None):
            raise ValueError("a Modelo 303 scenario states the joint-return answer, and no other modelo does")
        return self

    def profile_options(self) -> tuple[str, ...]:
        """The profile facts spelled as ``config profile edit`` options: a switch for a yes or no."""
        options: list[str] = []
        for name, value in self.profile.items():
            if value in {"true", "false"}:
                options.append(f"--{name}" if value == "true" else f"--no-{name}")
            else:
                options.extend((f"--{name}", value))
        return tuple(options)

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
