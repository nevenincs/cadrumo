"""Focused contract tests for the RETENCIONES-01 installed CLI driver."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.acceptance.income_tax.cli_journey import CommandEvidence

from ..cli_journey import RetencionesInstalledCliError, _failure_evidence, _is_full_campaign, _select_slices
from ..scenario import build_installed_periodic_cli_slices

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_named_slice_selection_retains_the_explicit_receipt_scope() -> None:
    """An independently runnable rent slice remains visibly narrower than full acceptance."""
    (rent,) = _select_slices(
        build_installed_periodic_cli_slices(),
        requested_ids=("urban-rent-115-q2-invoice",),
    )

    assert rent.modelo == "115"
    assert rent.annual_detail_capture_supported is False
    assert _is_full_campaign((rent,), available=build_installed_periodic_cli_slices()) is False


@pytest.mark.parametrize(
    ("requested_ids", "code"),
    [
        ((), "invalid_slice_selection"),
        (("professional-111-q2-partial-payments", "professional-111-q2-partial-payments"), "invalid_slice_selection"),
        (("unknown",), "unknown_slice_selection"),
    ],
)
def test_slice_selection_refuses_ambiguous_or_unknown_scope(
    requested_ids: tuple[str, ...],
    code: str,
) -> None:
    """A failure cannot silently turn a full campaign into an arbitrary subset."""
    with pytest.raises(RetencionesInstalledCliError) as raised:
        _select_slices(build_installed_periodic_cli_slices(), requested_ids=requested_ids)

    assert raised.value.stage == "preflight"
    assert raised.value.diagnostic_code == code


def test_failure_receipt_keeps_redacted_command_evidence_and_artifact_roots(tmp_path: Path) -> None:
    """A failed installed command is actionable without retaining a raw payload or secret."""
    command = CommandEvidence(
        command="app modelo work create",
        returncode=2,
        status="error",
        notice_codes=(),
    )
    receipt = _failure_evidence(
        error=RetencionesInstalledCliError(
            stage="professional-111-q2-partial-payments:work_create",
            diagnostic_code="REFUSED_MODELO_PROFILE_READINESS",
            commands=(command,),
        ),
        executable=tmp_path / "missing-aeat.exe",
        year=2025,
        source_identity="source-id",
        package_identity="package-id",
        storage_root=tmp_path / "storage",
        output_dir=tmp_path / "exports",
        commands=(command,),
    )

    assert receipt.status == "failed"
    assert receipt.commands == (command,)
    assert receipt.storage_root == str(tmp_path / "storage")
    assert receipt.output_dir == str(tmp_path / "exports")
    assert "passphrase" not in str(receipt.to_dict()).lower()
