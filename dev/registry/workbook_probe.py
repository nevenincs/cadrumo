"""Probe one empty form scenario per declared revision using the actual compiler.

This inventory is structural evidence only. It does not verify official visual
fidelity, populated calculations, XLSX rendering or live Google Sheets.
Run ``python -m dev.registry.workbook_probe --output PATH`` for a JSON report;
omit ``--output`` to write the report to stdout. No taxpayer profile is opened.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from time import monotonic
from typing import Literal

from cadrumo.application.storage.calc_sheets.engine import build_export_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_form_workbook
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.config import override_settings
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.temporal import select_revision

from .compiler.authority import compiled_bundled_authority
from .form_layout.coverage import RevisionCoverage, coverage_rows, coverage_totals
from .maintenance_support import declared_revision_selection_date, revision_selection_coordinates


@dataclass(frozen=True, slots=True)
class ProbeFrame:
    """One admitted, explicitly declared coordinate; never a revision-name guess."""

    filing_year: int
    period: str
    on: date | None

    def as_json(self) -> dict[str, object]:
        """Serialize the selected coordinate without a profile or runtime handle."""
        return {"filing_year": self.filing_year, "period": self.period, "on": self.on.isoformat() if self.on else None}


type ProbeStatus = Literal["compiled", "unsupported_frame", "snapshot_refused", "compiler_refused", "unexpected_error"]


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """A revision is always accounted for, including refusals and unexpected defects."""

    coverage: RevisionCoverage
    status: ProbeStatus
    frame: ProbeFrame | None = None
    stage: str = "frame"
    error_type: str | None = None
    message: str | None = None
    context: dict[str, object] | None = None
    value_cells: int = 0
    formula_cells: int = 0
    seconds: float = 0

    def as_json(self) -> dict[str, object]:
        """Serialize coverage and the observed outcome without a success inference."""
        return {
            **self.coverage.as_json(),
            "status": self.status,
            "frame": self.frame.as_json() if self.frame else None,
            "stage": self.stage,
            "error_type": self.error_type,
            "message": self.message,
            "context": self.context,
            "value_cells": self.value_cells,
            "formula_cells": self.formula_cells,
            "seconds": round(self.seconds, 3),
        }


def declared_probe_frame(
    modelo: ModeloDefinition, revision: ModeloRevision, support: SupportedFilingYearsCatalogue
) -> ProbeFrame | None:
    """Choose the first admitted coordinate in the bounded declared support span."""
    coordinates = revision_selection_coordinates(
        revision, assessment_floor=support.floor, assessment_horizon=support.horizon
    )
    last_refusal: CadrumoError | ValueError | None = None
    for year, period in coordinates:
        on = declared_revision_selection_date(revision, year)
        try:
            selected = select_revision(
                modelo, filing_year=year, period=str(period), on=on, revision_id=revision.id, support=support
            )
        except (CadrumoError, ValueError) as error:
            last_refusal = error
            continue
        if selected.id != revision.id:
            raise ValueError("temporal selector returned another revision")
        return ProbeFrame(year, str(period), on)
    if last_refusal is not None:
        raise last_refusal
    return None


def probe_revision(authority: ValidatedRegistryAuthority, coverage: RevisionCoverage) -> ProbeResult:
    """Run the real scenario engine and form compiler after selecting a frame."""
    started = monotonic()
    frame = None
    stage = "frame"
    try:
        modelo = authority.modelo(coverage.modelo_id)
        revision = modelo.revisions[coverage.revision_id]
        frame = declared_probe_frame(modelo, revision, authority.supported_filing_years())
        if frame is None:
            return ProbeResult(
                coverage,
                "unsupported_frame",
                message="No declared coordinate within the supported assessment span",
                seconds=monotonic() - started,
            )
        stage = "snapshot"
        snapshot = authority.snapshot(
            coverage.modelo_id,
            filing_year=frame.filing_year,
            period=frame.period,
            on=frame.on,
            revision_id=coverage.revision_id,
            grade=RegistryAuthorityGrade.CALCULATION,
        )
        stage = "engine"
        with override_settings(cadrumo_output_language="es"), validating_governed_facts(authority):
            plan = build_export_plan(snapshot)
            stage = "form"
            plan = add_form_workbook(plan, snapshot)
        return ProbeResult(
            coverage,
            "compiled",
            frame,
            "form",
            value_cells=len(plan.value_cells),
            formula_cells=len(plan.formula_cells),
            seconds=monotonic() - started,
        )
    except Exception as error:
        # One failed revision must not erase the rest of the inventory. Known
        # admission/compiler refusals stay distinct from unexpected defects;
        # KeyboardInterrupt/SystemExit are deliberately not swallowed.
        status: ProbeStatus = "unexpected_error"
        if isinstance(error, (CadrumoError, ValueError)):
            status = (
                "unsupported_frame"
                if stage == "frame"
                else "snapshot_refused"
                if stage == "snapshot"
                else "compiler_refused"
            )
        return ProbeResult(
            coverage,
            status,
            frame,
            stage,
            type(error).__name__,
            str(error),
            dict(error.context or {}) if isinstance(error, CadrumoError) else None,
            seconds=monotonic() - started,
        )


def probe_authority(
    authority: ValidatedRegistryAuthority,
    *,
    modelos: frozenset[str] | None = None,
    on_result: Callable[[ProbeResult], None] | None = None,
) -> dict[str, object]:
    """Enumerate through the existing coverage owner and account for every row."""
    inventory = coverage_rows(authority.modelos)
    known = {row.modelo_id for row in inventory}
    if modelos is not None and (not modelos or modelos - known):
        raise ValueError("probe modelo selection must be nonempty and present in the registry")
    selected = tuple(row for row in inventory if modelos is None or row.modelo_id in modelos)
    results = []
    for row in selected:
        result = probe_revision(authority, row)
        results.append(result)
        if on_result is not None:
            on_result(result)
    counts = Counter(result.status for result in results)
    errors = Counter(
        f"{result.stage}: {result.error_type or 'NoSupportedFrame'}"
        for result in results
        if result.status != "compiled"
    )
    references = Counter(
        str(result.context["reference"]) for result in results if result.context and "reference" in result.context
    )
    return {
        "schema_version": 1,
        "evidence_kind": "one_empty_structural_scenario_per_revision",
        "full_inventory": modelos is None,
        "runtime_authority_adopted": False,
        "official_visual_verification": False,
        "populated_calculation_verification": False,
        "live_google_verification": False,
        "snapshot_grade": RegistryAuthorityGrade.CALCULATION.value,
        "support_floor": authority.supported_filing_years().floor,
        "assessment_horizon": authority.supported_filing_years().horizon,
        "inventory_revisions": len(inventory),
        "coverage": coverage_totals(selected),
        "outcomes": dict(sorted(counts.items())),
        "failure_classes": dict(sorted(errors.items())),
        "blocking_references": dict(sorted(references.items())),
        "results": [result.as_json() for result in results],
    }


def main() -> None:
    """Write a complete machine-readable report without external side effects."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--modelo", action="append", help="Optional explicit subset; report marks incomplete inventory")
    parser.add_argument("--progress", action="store_true", help="Write revision outcomes to stderr")
    args = parser.parse_args()

    def progress(result: ProbeResult) -> None:
        if args.progress:
            print(
                f"{result.coverage.modelo_id}/{result.coverage.revision_id}: {result.status}",
                file=sys.stderr,
                flush=True,
            )

    report = probe_authority(
        compiled_bundled_authority(), modelos=frozenset(args.modelo) if args.modelo else None, on_result=progress
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
