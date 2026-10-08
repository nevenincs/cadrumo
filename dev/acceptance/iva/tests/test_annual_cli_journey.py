"""Public installed-CLI acceptance for the first IVA annual-foundation slice."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ..annual_cli_journey import (
    run_iva_annual_foundation_cli_journey,
    run_iva_annual_m390_cli_journey,
)
from .journey_year_support import newest_fully_authored_journey_year

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# Measured on a quiet host on 2026-09-23: 96 s wheel build and install, then 337 s of fresh-process
# authenticated CLI calls. These are historical timings; correctness completion has no elapsed ceiling.
def test_installed_cli_first_quarter_local_filing_establishes_annual_foundation(
    tmp_path: Path, installed_wheel_aeat: Path
) -> None:
    """A verified ordinary 303 persists its local filing identity for later annual work."""
    repository_root = Path(__file__).resolve().parents[4]
    authority_root = repository_root / ".authority"
    assert (authority_root / "authority.current.json").is_file(), authority_root
    year = newest_fully_authored_journey_year(authority_root)

    receipt = run_iva_annual_foundation_cli_journey(
        executable=installed_wheel_aeat,
        authority_root=authority_root,
        storage_root=tmp_path / "secure-store",
        artifact_root=tmp_path / "private-source-artifacts",
        year=year,
    )

    assert receipt.acceptance_ids == (f"IVA-01-ANNUAL-FOUNDATION-{year}-1T",)
    assert receipt.filing_year == year
    assert Decimal(receipt.iva_resultado) == Decimal("21.00") - Decimal("10.50")
    assert receipt.calculation_revision_id
    assert receipt.verification_report_id
    assert receipt.verification_status
    assert receipt.filing_record_id
    assert receipt.filing_origin == "local"
    assert receipt.filing_confirmation == "pendiente"
    assert receipt.filing_aeat_accepted is False
    assert receipt.filing_live_submission is False
    assert receipt.authority_generation
    assert receipt.source_identity
    assert receipt.package_identity.startswith("cadrumo==")
    assert receipt.purchase_artifact == "<synthetic-purchase-artifact>"
    assert any(command.argv[2:6] == ("app", "modelo", "work", "file") for command in receipt.commands)
    assert any(command.argv[2:6] == ("app", "modelo", "work", "list") for command in receipt.commands)
    assert any(command.argv[2:6] == ("app", "modelo", "filing-record", "list") for command in receipt.commands)
    assert not any(command.argv[2:5] == ("app", "modelo", "export") for command in receipt.commands)
    assert not any("attest-m303-exonerado-390" in command.argv for command in receipt.commands)
    assert not any("--m303-exonerado-390-attachment-id" in command.argv for command in receipt.commands)
    rendered = str(receipt.to_dict())
    assert "synthetic-annual-foundation-purchase.pdf" not in rendered
    assert "profile_passphrase" not in rendered
    assert "attachment:" not in rendered
    assert all(command.returncode == 0 for command in receipt.commands)


# Measured on a quiet host on 2026-09-23: 713 s of fresh-process authenticated CLI calls across four
# quarters and the annual summary. These are historical timings; correctness completion has no elapsed ceiling.
def test_installed_cli_four_local_303_quarters_verify_the_annual_m390(
    tmp_path: Path, installed_wheel_aeat: Path
) -> None:
    """Four local-pending 303 records reconcile to a verified annual 0A 390."""
    repository_root = Path(__file__).resolve().parents[4]
    authority_root = repository_root / ".authority"
    assert (authority_root / "authority.current.json").is_file(), authority_root
    year = newest_fully_authored_journey_year(authority_root)

    receipt = run_iva_annual_m390_cli_journey(
        executable=installed_wheel_aeat,
        authority_root=authority_root,
        storage_root=tmp_path / "secure-store",
        artifact_root=tmp_path / "private-source-artifacts",
        year=year,
    )

    assert receipt.acceptance_ids == (f"IVA-01-ANNUAL-M390-{year}-0A",)
    assert receipt.filing_year == year
    assert tuple(item.period for item in receipt.quarterly_filings) == ("1T", "2T", "3T", "4T")
    assert tuple(Decimal(item.iva_resultado) for item in receipt.quarterly_filings) == (
        Decimal("315.00"),
        Decimal("315.00"),
        Decimal("210.00"),
        Decimal("525.00"),
    )
    for filing in receipt.quarterly_filings:
        assert filing.work_unit_id
        assert filing.calculation_revision_id
        assert filing.verification_report_id
        assert filing.verification_status
        assert filing.filing_record_id
        assert filing.filing_origin == "local"
        assert filing.filing_confirmation == "pendiente"
        assert filing.filing_aeat_accepted is False
        assert filing.filing_live_submission is False
    assert Decimal(receipt.annual_devengada) == Decimal("1470.00")
    assert Decimal(receipt.annual_deducible) == Decimal("105.00")
    assert Decimal(receipt.annual_resultado) == Decimal("1365.00")
    assert receipt.annual_work_unit_id
    assert receipt.annual_calculation_revision_id
    assert receipt.annual_verification_report_id
    assert receipt.annual_verification_status
    assert receipt.authority_generation
    assert receipt.source_identity
    assert receipt.package_identity.startswith("cadrumo==")
    assert receipt.purchase_artifact == "<synthetic-purchase-artifact>"
    assert sum(command.argv[2:6] == ("app", "modelo", "work", "file") for command in receipt.commands) == 4
    attestations = [
        command
        for command in receipt.commands
        if command.argv[2:6] == ("app", "modelo", "work", "attest-m303-exonerado-390")
    ]
    assert len(attestations) == 1
    assert attestations[0].argv[attestations[0].argv.index("--period") + 1] == "4T"
    assert sum("--m303-exonerado-390-attachment-id" in command.argv for command in receipt.commands) == 1
    assert sum("--no-joint-return-elected" in command.argv for command in receipt.commands) == 4
    assert not any("--m303-filing-evidence" in command.argv for command in receipt.commands)
    assert any(
        command.argv[2:6] == ("app", "modelo", "work", "create") and "390" in command.argv and "0A" in command.argv
        for command in receipt.commands
    )
    assert not any(command.argv[2:5] == ("app", "modelo", "export") for command in receipt.commands)
    rendered = str(receipt.to_dict())
    assert "synthetic-annual-foundation-purchase.pdf" not in rendered
    assert "profile_passphrase" not in rendered
    assert "attachment:" not in rendered
    assert all(command.returncode == 0 for command in receipt.commands)
