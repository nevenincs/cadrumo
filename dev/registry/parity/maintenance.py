"""Repository-only registry verification and parity workflows.

This module is intentionally outside ``src/cadrumo``.  Its capabilities audit
release inputs, execute official workbook backends, and archive/replay curated
parity tapes; installed consumers do not need any of those operations.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.domain.calculations.registry.live_parity import (
    CrossReferenceApplicabilityDeclaracion,
    LiveParityCatalogue,
    OracleEnvironment,
    audit_registry_oracle_bindings,
    collect_applicability_declarations,
    collect_orphan_oracle_ids,
)
from cadrumo.domain.calculations.registry.loader import load_registry_tree
from cadrumo.tests.aeat_nif_iva_oracle import AeatNifIvaCheckerOracle
from cadrumo.tests.groi_oracle import GroiOracle

from ._parity_tapes import (
    ParityTape,
    ParityTapeReplayReport,
    generate_parity_tape_path,
    load_parity_scenario,
    load_parity_tape,
    replay_parity_tape,
    run_parity_scenario,
    save_parity_tape,
)
from ._workbook_parity import WorkbookBackendVerificationReport, verify_workbook_backend


class RegistryOracleAuditReport(BaseModel):
    """Result of the contributor-facing live-oracle binding audit."""

    model_config = ConfigDict(frozen=True)

    environment: str
    registered_oracle_ids: tuple[str, ...]
    failure_count: int
    failures: tuple[str, ...]
    applicability_declarations: tuple[CrossReferenceApplicabilityDeclaracion, ...]
    orphan_oracle_ids: tuple[str, ...]


def audit_registry_oracles(registry_root: Path, *, environment: OracleEnvironment) -> RegistryOracleAuditReport:
    """Audit committed oracle adapters against registry cross-references.

    Reads the compiled modelo definitions through the raw compiler rather than
    the validated authority. This audit consumes exactly one surface --
    ``modelos`` -- and never the legal catalogue, which is the distinction that
    makes the move safe: the compiler and the authority return an identical
    modelo set, while the authority's ``catalogues.legal`` additionally carries
    the annual-Orden compiler's synthesised refs that the compiler tier cannot
    see.

    Routing it through the authority meant this audit refused whenever registry
    validation refused anywhere in the tree -- so an instrument whose whole
    purpose is auditing registry grounding was unavailable exactly when the
    registry was under repair.
    """
    modelos, _catalogues = load_registry_tree(registry_root)
    catalogue = LiveParityCatalogue()
    catalogue.register(AeatNifIvaCheckerOracle(), environment=OracleEnvironment.PRODUCTION)
    catalogue.register(GroiOracle(), environment=OracleEnvironment.PRODUCTION)
    failures = audit_registry_oracle_bindings(modelos, catalogue, environment=environment)
    return RegistryOracleAuditReport(
        environment=environment.value,
        registered_oracle_ids=tuple(sorted(catalogue.ids())),
        failure_count=len(failures),
        failures=tuple(failures),
        applicability_declarations=collect_applicability_declarations(modelos),
        orphan_oracle_ids=tuple(collect_orphan_oracle_ids(modelos, catalogue)),
    )


def verify_registry_workbooks(
    *,
    root: Path,
    limit: int | None = None,
    per_file_timeout_seconds: float = 15.0,
    resume_from: Path | None = None,
    output: Path | None = None,
) -> WorkbookBackendVerificationReport:
    """Run the repository workbook backend verification."""
    previous = None
    if resume_from is not None:
        previous = WorkbookBackendVerificationReport.model_validate_json(
            resume_from.read_text(encoding=UTF_8_ENCODING),
        )
    report = verify_workbook_backend(
        root,
        scan_limit=limit,
        per_file_timeout_seconds=per_file_timeout_seconds,
        previous_report=previous,
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report.model_dump_json(indent=2), encoding=UTF_8_ENCODING, newline="\n")
    return report


def run_registry_parity(
    *,
    scenario_path: Path,
    registry_root: Path,
    source_root: Path,
    store_root: Path,
    output: Path | None = None,
) -> tuple[ParityTape, Path]:
    """Execute one curated scenario and archive its parity tape."""
    scenario = load_parity_scenario(scenario_path)
    tape = run_parity_scenario(
        scenario,
        registry_root=registry_root,
        source_root=source_root,
        scenario_path=scenario_path,
    )
    target = output or generate_parity_tape_path(store_root, scenario.id, tape.created_at)
    save_parity_tape(tape, target)
    return tape, target


def replay_registry_parity(
    *,
    tape_path: Path,
    registry_root: Path,
    source_root: Path,
) -> ParityTapeReplayReport:
    """Replay one archived parity tape against current product behavior."""
    tape = load_parity_tape(tape_path)
    return replay_parity_tape(
        tape,
        registry_root=registry_root,
        source_root=source_root,
        tape_path=tape_path,
    )


__all__ = [
    "RegistryOracleAuditReport",
    "audit_registry_oracles",
    "replay_registry_parity",
    "run_registry_parity",
    "verify_registry_workbooks",
]
