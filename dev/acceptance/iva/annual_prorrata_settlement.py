"""Installed IVA journey for the year's last Modelo 303: exported before filing, settled into the register by filing.

LIVA art. 105.Cuatro settles the definitive prorrata in the year's last return and art. 105.Uno
reads the filed definitive as the next year's provisional one. The export of a verified fourth
quarter therefore reads the register as its filing will leave it, derived in memory from the
exported revision's own casillas, and writes nothing to the register.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager, ExitStack
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_store import AUTHORITY_DESCRIPTOR_FILENAME
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from dev.acceptance.installed_cli import InstalledCli

from .annual_capture import add_documented_ledger_facts
from .annual_contracts import FINAL_QUARTER, QUARTERS
from .annual_projection import decimal_casilla
from .annual_quarter_work import (
    VerifiedQuarter,
    calculate_and_verify_quarter,
    file_quarter,
    file_verified_quarter,
    seed_first_period,
)
from .annual_runtime import reopen, start
from .cli_journey import (
    IvaCliJourneyError,
    SanitizedCommandReceipt,
    result,
    run,
)
from .filing_year import IvaJourneyYear, require_journey_year
from .multirate_cli_journey import add_purchase_evidence

#: The 303 coordinates and the annual summary a year needs for its four quarters to file.
PRORRATA_SETTLEMENT_COORDINATES: tuple[tuple[str, str], ...] = tuple(("303", quarter) for quarter in QUARTERS)

#: The expected IVA result of each documented quarter, from the documented ledger facts.
_EXPECTED_RESULT: dict[str, Decimal] = {
    "1T": Decimal("315.00"),
    "2T": Decimal("315.00"),
    "3T": Decimal("210.00"),
    "4T": Decimal("525.00"),
}

_OPTION_CONTEXT = "opcion-prorrata"
_REVOCATION_CONTEXT = "revocacion-prorrata"
_ESPECIAL_EVIDENCE = "Synthetic especial prorrata declaration; not sent to AEAT"
_ESPECIAL_PROVENANCE = "aeat_autorizada"
_SECTOR_ID = "software"
_SECTOR_ACTIVITY_CODE = "763"
_NO = "2"
_SI = "1"


@dataclass(frozen=True, slots=True)
class FinalQuarterSession:
    """The installed CLI of a year whose first three quarters are filed and whose fourth is verified."""

    cli: InstalledCli
    receipts: list[SanitizedCommandReceipt]
    artifact: Path
    artifact_root: Path
    authority_root: Path
    journey_year: IvaJourneyYear
    quarter: VerifiedQuarter


def open_final_quarter(
    *,
    resources: ExitStack,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    artifact_root: Path,
    year: int,
    runtime_scope: AbstractContextManager[object] | None,
) -> FinalQuarterSession:
    """File the first three quarters of ``year`` locally, then calculate and verify the fourth.

    Raises:
        IvaFilingYearUnsupportedError: Before any side effect, when the published authority has
            no Modelo 303 revision authored for ``year`` for any quarter.
    """
    journey_year = require_journey_year(
        authority_root=authority_root, year=year, coordinates=PRORRATA_SETTLEMENT_COORDINATES
    )
    cli, receipts, artifact = start(
        executable,
        authority_root,
        storage_root,
        artifact_root,
        journey_year,
        resources=resources,
        runtime_scope=runtime_scope,
    )
    evidence_id = add_purchase_evidence(cli=cli, receipts=receipts, artifact=artifact)
    add_documented_ledger_facts(
        cli=cli, receipts=receipts, artifact=artifact, purchase_evidence_id=evidence_id, journey_year=journey_year
    )
    work_cli = reopen(cli, authority_root, storage_root)
    seed_first_period(cli=work_cli, receipts=receipts, artifact=artifact, journey_year=journey_year)
    for period in QUARTERS[:-1]:
        file_quarter(
            cli=work_cli,
            receipts=receipts,
            artifact=artifact,
            journey_year=journey_year,
            period=period,
            expected=_EXPECTED_RESULT[period],
        )
    quarter = calculate_and_verify_quarter(
        cli=work_cli,
        receipts=receipts,
        artifact=artifact,
        journey_year=journey_year,
        period=FINAL_QUARTER,
        expected=_EXPECTED_RESULT[FINAL_QUARTER],
    )
    return FinalQuarterSession(work_cli, receipts, artifact, artifact_root, authority_root, journey_year, quarter)


def register_entry(session: FinalQuarterSession, ejercicio: int) -> Mapping[str, object] | None:
    """The whole-entity register entry of ``ejercicio`` as the public list reports it, or ``None``."""
    listed = result(
        run(session.cli, session.receipts, session.artifact, ("app", "ledger", "prorrata", "list"), result_keys=())
    )
    entries = listed.get("entries")
    if not isinstance(entries, list):
        raise IvaCliJourneyError("prorrata list returned no entries")
    matches = [
        cast(Mapping[str, object], entry)
        for entry in entries
        if isinstance(entry, Mapping) and entry.get("ejercicio") == ejercicio and entry.get("sector_id") is None
    ]
    if len(matches) > 1:
        raise IvaCliJourneyError("prorrata list returned the whole-entity entry twice")
    return matches[0] if matches else None


def export_final_quarter(session: FinalQuarterSession, name: str) -> bytes:
    """Export the verified fourth quarter and return the fichero it wrote."""
    target = session.artifact_root / name
    exported = result(
        run(
            session.cli,
            session.receipts,
            session.artifact,
            ("app", "modelo", "export", session.quarter.work_unit_id, "--output", str(target)),
            result_keys=(),
        )
    )
    if exported.get("calculation_revision_id") != session.quarter.calculation_revision_id:
        raise IvaCliJourneyError("Modelo 303 4T export returned a different calculation revision")
    if not target.is_file() or target.stat().st_size == 0:
        raise IvaCliJourneyError("Modelo 303 4T export reported success without an artifact")
    return target.read_bytes()


def refused_export(session: FinalQuarterSession, name: str) -> Mapping[str, object]:
    """Run the 4T export expecting a refusal; return its error document and require that nothing was written."""
    target = session.artifact_root / name
    document = session.cli.run(
        ("app", "modelo", "export", session.quarter.work_unit_id, "--output", str(target)), allow_error=True
    )
    if session.cli.commands[-1].returncode == 0:
        raise IvaCliJourneyError("Modelo 303 4T export succeeded although the register cannot cover the year")
    if target.exists():
        raise IvaCliJourneyError("a refused Modelo 303 4T export still wrote an artifact")
    error = document.get("error")
    if not isinstance(error, Mapping):
        raise IvaCliJourneyError("a refused Modelo 303 4T export returned no error document")
    return cast(Mapping[str, object], error)


def exported_election_fields(session: FinalQuarterSession, payload: bytes) -> dict[str, str]:
    """The raw option and revocation fields of the exported fichero, read through the registry parser."""
    descriptor = session.authority_root.resolve(strict=True) / AUTHORITY_DESCRIPTOR_FILENAME
    authority = IndexedRegistryAuthority(descriptor)
    try:
        with authority.operation() as operation:
            year = session.journey_year.year
            snapshot = operation.reading_snapshot("303", filing_year=year, period=FINAL_QUARTER)
            form_layout = operation.form_layout("303", snapshot.revision.id)
            if form_layout is None:
                raise IvaCliJourneyError("the 4T edition declares no form layout")
            blocks = {
                block.id: block
                for page in form_layout.pages
                for section in page.sections
                for block in section.blocks
                if isinstance(block, FormContextFieldBlock)
            }
            layout = operation.revision_with_export_layouts("303", snapshot.revision.id).export_layouts[0]
            parsed = parse_export_payload(layout, payload).fields
    finally:
        authority.close()
    fields: dict[str, str] = {}
    for name in (_OPTION_CONTEXT, _REVOCATION_CONTEXT):
        field_id = blocks[name].export_field_id
        raw = [field.raw for field in parsed if field.field_id == field_id]
        if len(raw) != 1:
            raise IvaCliJourneyError(f"the exported fichero carries no single {name} field")
        fields[name] = raw[0]
    return fields


def require_election_fields(fields: Mapping[str, str], *, option: str, revocation: str) -> None:
    """Require the exported option and revocation marks (``1`` SI, ``2`` NO)."""
    if fields != {_OPTION_CONTEXT: option, _REVOCATION_CONTEXT: revocation}:
        raise IvaCliJourneyError("the exported prorrata option and revocation marks are not the stated ones")


def final_quarter_percentage(quarter: VerifiedQuarter) -> Decimal:
    """The definitive percentage the verified 4T calculated."""
    return decimal_casilla(quarter.calculated, "iva.prorrata-porcentaje")


def require_entry_percentage(entry: Mapping[str, object] | None, percentage: Decimal, *, field: str) -> None:
    """Require a register entry whose ``field`` equals ``percentage``."""
    if entry is None:
        raise IvaCliJourneyError("the register holds no entry for the settled year")
    value = entry.get(field)
    if not isinstance(value, str) or Decimal(value).quantize(Decimal("0.01")) != percentage:
        raise IvaCliJourneyError(f"the register entry's {field} is not the exported revision's percentage")


def seed_next_year(session: FinalQuarterSession) -> Mapping[str, object]:
    """Carry the filed definitive into the next year's provisional percentage; return its entry."""
    seeded = result(
        run(
            session.cli,
            session.receipts,
            session.artifact,
            ("app", "ledger", "prorrata", "seed", "--ejercicio", str(session.journey_year.year + 1)),
            result_keys=(),
        )
    )
    entry = seeded.get("entry")
    if not isinstance(entry, Mapping):
        raise IvaCliJourneyError("prorrata seed returned no entry")
    return cast(Mapping[str, object], entry)


def file_final_quarter(session: FinalQuarterSession) -> str:
    """File the verified 4T locally and return its filing record id."""
    return file_verified_quarter(
        cli=session.cli, receipts=session.receipts, artifact=session.artifact, quarter=session.quarter
    ).filing_record_id


def declare_sector_command() -> tuple[str, ...]:
    """The public command that declares a differentiated sector whose year entry nobody states."""
    return (
        "app",
        "ledger",
        "prorrata",
        "declare-sector",
        "--sector-id",
        _SECTOR_ID,
        "--letra",
        "a",
        "--activity-code",
        _SECTOR_ACTIVITY_CODE,
    )


def elect_especial_command(ejercicio: int) -> tuple[str, ...]:
    """The public command that elects the especial prorrata for ``ejercicio``."""
    return (
        "app",
        "ledger",
        "prorrata",
        "elect-especial",
        "--ejercicio",
        str(ejercicio),
        "--percentage",
        "100",
        "--provenance",
        _ESPECIAL_PROVENANCE,
        "--reference",
        _ESPECIAL_EVIDENCE,
    )
