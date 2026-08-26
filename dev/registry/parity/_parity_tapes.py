"""Scenario tape parity harness for manual AEAT workbook checks.

Loads, runs, and saves parity scenarios using a :class:`ValidatedRegistryAuthority`
to obtain snapshots and evaluate formulas against official AEAT workbooks.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from cadrumo.core import STRICT_FROZEN_CONFIG, CasillaId, Period, hydrate_scenario_filing_period
from cadrumo.core.time import now
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import (
    RegistrySnapshotError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.ids import (
    RelationId,
    WorkbookOutputId,
)
from cadrumo.domain.calculations.registry.period_selector_match import selector_period_matches_request

from ._workbook_parity import (
    SyntheticInputSet,
    WorkbookArtefactReport,
    WorkbookCellRef,
    WorkbookParityRunReport,
    WorkbookRunnerAvailability,
    run_registry_workbook_parity,
    scan_workbook,
)

ParityStatus = Literal["match", "mismatch"]
_JSON_OBJECT_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(
    dict[str, object],
    config=ConfigDict(strict=True),
)
_JSON_ARRAY_ADAPTER: TypeAdapter[list[object]] = TypeAdapter(list[object], config=ConfigDict(strict=True))


class ParityTapeModel(BaseModel):
    """Strict frozen base for parity tape records."""

    model_config = STRICT_FROZEN_CONFIG


class ParityScenario(ParityTapeModel):
    """One manually curated workbook parity scenario."""

    id: str
    modelo: str
    revision: str
    filing_period: Period | None = None
    filing_year: int = Field(ge=2000, le=2099)
    period: str
    workbook_path: Path
    synthetic_input: SyntheticInputSet
    output_cells: dict[WorkbookOutputId, WorkbookCellRef] = Field(min_length=1)
    # registry-driven shape: the value is a CasillaId (the registry's
    # typed casilla identifier), not a free-form string. The pattern on
    # CasillaId rejects whitespace, empty strings, and unsupported
    # punctuation at validation time, lifting the constraint out of
    # ad-hoc downstream checks.
    registry_outputs: dict[WorkbookOutputId, CasillaId] = Field(min_length=1)
    date_context: dict[str, date] = Field(default_factory=dict)
    relation_values: dict[RelationId, Decimal] = Field(default_factory=dict)
    tolerance: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    notes: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _hydrate_filing_period(cls, data: object) -> object:
        return hydrate_scenario_filing_period(data)

    @model_validator(mode="after")
    def _validate_scenario(self) -> ParityScenario:
        if self.synthetic_input.modelo != self.modelo:
            raise RegistryValidationError("scenario synthetic input modelo must match scenario modelo")
        if self.synthetic_input.revision != self.revision:
            raise RegistryValidationError("scenario synthetic input revision must match scenario revision")
        if set(self.output_cells) != set(self.registry_outputs):
            raise RegistryValidationError(
                "scenario workbook outputs and registry outputs must use the same identifiers",
            )
        if len(set(self.registry_outputs.values())) != len(self.registry_outputs):
            raise RegistryValidationError("scenario registry outputs must target unique casillas")
        if self.period.strip() != self.period:
            raise RegistryValidationError("scenario period must not include leading or trailing whitespace")
        if self.filing_period is not None and (
            self.filing_period.filing_year != self.filing_year
            or not selector_period_matches_request(self.period, self.filing_period.registry_token)
        ):
            raise RegistryValidationError("scenario filing_period must match filing_year and period")
        return self


class ParityTape(ParityTapeModel):
    """Stored trace for one workbook parity execution."""

    created_at: datetime
    scenario_path: str | None = None
    scenario: ParityScenario
    workbook: WorkbookArtefactReport
    runner: WorkbookRunnerAvailability
    report: WorkbookParityRunReport
    path: str | None = None


class ParityTapeReplayReport(ParityTapeModel):
    """Replay comparison between an archived tape and the current runtime."""

    tape_path: str
    scenario_id: str
    status: ParityStatus
    differences: tuple[str, ...] = ()
    stored: ParityTape
    current: ParityTape


def load_parity_scenario(path: Path) -> ParityScenario:
    """Load one parity scenario from JSON.

    Returns:
        The validated :class:`ParityScenario` from the file.
    """
    return ParityScenario.model_validate_json(path.read_text(encoding="utf-8"))


def save_parity_scenario(scenario: ParityScenario, path: Path) -> Path:
    """Persist one parity scenario to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(scenario.model_dump_json(indent=2), encoding="utf-8", newline="\n")
    return path


def load_parity_tape(path: Path) -> ParityTape:
    """Load one :class:`ParityTape` from JSON."""
    return ParityTape.model_validate_json(path.read_text(encoding="utf-8"))


def save_parity_tape(tape: ParityTape, path: Path) -> Path:
    """Persist one parity tape to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tape.model_dump_json(indent=2), encoding="utf-8", newline="\n")
    return path


def generate_parity_tape_path(root: Path, scenario_id: str, created_at: datetime) -> Path:
    """Return a deterministic archive path for one parity tape."""
    stamp = created_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / _slugify(scenario_id) / f"{stamp}.json"


def run_parity_scenario(
    scenario: ParityScenario,
    *,
    registry_root: Path,
    source_root: Path,
    scenario_path: Path | None = None,
    executable: str | None = None,
) -> ParityTape:
    """Execute one scenario against the registry and return a :class:`ParityTape`."""
    workbook_path = _resolve_scenario_path(scenario.workbook_path, scenario_path=scenario_path)
    snapshot = _snapshot_for_scenario(scenario, registry_root=registry_root, source_root=source_root)
    workbook_root = _common_root(
        scenario_path.resolve().parent if scenario_path is not None else Path.cwd(),
        workbook_path,
    )
    workbook = scan_workbook(workbook_path, root=workbook_root)
    report = run_registry_workbook_parity(
        snapshot=snapshot,
        synthetic_input=scenario.synthetic_input,
        workbook_path=workbook_path,
        workbook=workbook,
        output_cells=scenario.output_cells,
        registry_outputs=scenario.registry_outputs,
        date_context=scenario.date_context,
        relation_values=scenario.relation_values,
        tolerance=scenario.tolerance,
        executable=executable,
    )
    return ParityTape(
        created_at=now(),
        scenario_path=scenario_path.resolve().as_posix() if scenario_path is not None else None,
        scenario=scenario,
        workbook=workbook,
        runner=report.runner,
        report=report,
    )


def replay_parity_tape(
    tape: ParityTape,
    *,
    registry_root: Path,
    source_root: Path,
    tape_path: Path | None = None,
    scenario_path: Path | None = None,
    executable: str | None = None,
) -> ParityTapeReplayReport:
    """Replay an archived tape against the current registry implementation.

    Returns:
        A :class:`ParityTapeReplayReport` comparing the archived tape to the current output.
    """
    current = run_parity_scenario(
        tape.scenario,
        registry_root=registry_root,
        source_root=source_root,
        scenario_path=Path(tape.scenario_path) if tape.scenario_path is not None else scenario_path,
        executable=executable,
    )
    stored_dump = _stable_tape_dump(tape)
    current_dump = _stable_tape_dump(current)
    differences = _diff_paths(stored_dump, current_dump)
    status: ParityStatus = "match" if not differences else "mismatch"
    return ParityTapeReplayReport(
        tape_path=tape_path.as_posix() if tape_path is not None else "",
        scenario_id=tape.scenario.id,
        status=status,
        differences=differences,
        stored=tape,
        current=current,
    )


def _snapshot_for_scenario(
    scenario: ParityScenario,
    *,
    registry_root: Path,
    source_root: Path,
):
    authority = ValidatedRegistryAuthority.load(registry_root, source_root=source_root)
    try:
        return authority.snapshot(
            scenario.modelo,
            filing_year=scenario.filing_year,
            period=scenario.period,
        )
    except RegistrySnapshotError as exc:
        raise RegistryValidationError(f"invalid registry snapshot for parity scenario {scenario.id!r}: {exc}") from exc


def _stable_tape_dump(tape: ParityTape) -> dict[str, object]:
    data = tape.model_dump(mode="json")
    data.pop("created_at", None)
    workbook = dict(data["workbook"])
    workbook.pop("elapsed_seconds", None)
    data["workbook"] = workbook
    report = dict(data["report"])
    report_workbook = dict(report["workbook"])
    report_workbook.pop("elapsed_seconds", None)
    report["workbook"] = report_workbook
    data["report"] = report
    return data


def _as_json_object(value: object) -> dict[str, object] | None:
    """Narrow a ``model_dump(mode="json")`` value to a string-keyed dict.

    JSON object keys are always strings, so a dict produced by
    ``model_dump(mode="json")`` (or ``json.loads``) is always string-keyed in
    practice; the runtime check restores that static guarantee for the
    recursive tape diff below.
    """
    if not isinstance(value, dict):
        return None
    try:
        return _JSON_OBJECT_ADAPTER.validate_python(value)
    except ValidationError:
        return None


def _as_json_array(value: object) -> list[object] | None:
    """Narrow a JSON array to object entries, or return ``None``."""
    if not isinstance(value, list):
        return None
    try:
        return _JSON_ARRAY_ADAPTER.validate_python(value)
    except ValidationError:
        return None


def _diff_paths(left: object, right: object, prefix: str = "") -> tuple[str, ...]:
    differences: list[str] = []
    left_object = _as_json_object(left)
    right_object = _as_json_object(right)
    if left_object is not None and right_object is not None:
        keys = sorted(set(left_object) | set(right_object))
        for key in keys:
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            if key not in left_object:
                differences.append(f"{next_prefix}: missing from stored tape")
                continue
            if key not in right_object:
                differences.append(f"{next_prefix}: missing from current tape")
                continue
            differences.extend(_diff_paths(left_object[key], right_object[key], next_prefix))
        return tuple(differences)
    left_array = _as_json_array(left)
    right_array = _as_json_array(right)
    if left_array is not None and right_array is not None:
        if len(left_array) != len(right_array):
            differences.append(f"{prefix}: length differs ({len(left_array)} != {len(right_array)})")
        for index, (left_item, right_item) in enumerate(zip(left_array, right_array, strict=False)):
            next_prefix = f"{prefix}[{index}]"
            differences.extend(_diff_paths(left_item, right_item, next_prefix))
        return tuple(differences)
    if left != right:
        differences.append(f"{prefix}: {left!r} != {right!r}")
    return tuple(differences)


def _resolve_scenario_path(path: Path, *, scenario_path: Path | None) -> Path:
    if path.is_absolute():
        return path
    base = scenario_path.parent if scenario_path is not None else Path.cwd()
    return (base / path).resolve()


def _common_root(left: Path, right: Path) -> Path:
    left_root = left.resolve()
    right_root = right.resolve()
    left_parts = left_root.parts
    right_parts = right_root.parts
    common: list[str] = []
    for left_part, right_part in zip(left_parts, right_parts, strict=False):
        if left_part != right_part:
            break
        common.append(left_part)
    if not common:
        if left_root.anchor:
            return Path(left_root.anchor)
        if right_root.anchor:
            return Path(right_root.anchor)
        return Path.cwd()
    return Path(*common)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-").lower()
    return slug or "parity-tape"


__all__ = [
    "ParityScenario",
    "ParityTape",
    "ParityTapeReplayReport",
    "generate_parity_tape_path",
    "load_parity_scenario",
    "load_parity_tape",
    "replay_parity_tape",
    "run_parity_scenario",
    "save_parity_scenario",
    "save_parity_tape",
]
