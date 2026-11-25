"""Focused contract tests for the RETENCIONES-01 installed CLI driver."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from dev.acceptance.installed_cli import CommandEvidence, InstalledCli

from ..cli_annual import is_full_annual_campaign, select_annual_slices
from ..cli_annual_source import attest_annual_no_activity_periods, materialize_annual_source_period
from ..cli_contracts import RetencionesInstalledCliError
from ..cli_invoice_capture import declare_perceptor_filing_names
from ..cli_journey import failure_evidence
from ..cli_periodic import is_full_campaign, select_slices
from ..cli_profile import create_withholding_profile
from ..scenario import (
    LANDLORD_NIF,
    LANDLORD_RAZON_SOCIAL,
    PROFESSIONAL_NIF,
    PROFESSIONAL_RAZON_SOCIAL,
    SUPPORTED_YEAR,
    build_installed_annual_cli_slices,
    build_installed_periodic_cli_slices,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_named_slice_selection_retains_the_explicit_receipt_scope() -> None:
    """An independently runnable rent slice remains visibly narrower than full acceptance."""
    (rent,) = select_slices(
        build_installed_periodic_cli_slices(),
        requested_ids=("urban-rent-115-q2-invoice",),
    )

    assert rent.modelo == "115"
    assert rent.annual_detail_capture_supported is True
    assert is_full_campaign((rent,), available=build_installed_periodic_cli_slices()) is False


def test_annual_slice_selection_keeps_m180_and_m190_completion_scope_explicit() -> None:
    """A passed Modelo 180 slice is not relabelled as the complete annual campaign."""
    (rent,) = select_annual_slices(
        build_installed_annual_cli_slices(),
        requested_ids=("urban-rent-180-annual-properties",),
    )

    assert rent.modelo == "180"
    assert is_full_annual_campaign((rent,), available=build_installed_annual_cli_slices()) is False


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
        select_slices(build_installed_periodic_cli_slices(), requested_ids=requested_ids)

    assert raised.value.stage == "preflight"
    assert raised.value.diagnostic_code == code


@pytest.mark.parametrize(
    ("requested_ids", "code"),
    [
        ((), "invalid_annual_slice_selection"),
        (("professional-190-annual-detail", "professional-190-annual-detail"), "invalid_annual_slice_selection"),
        (("unknown",), "unknown_annual_slice_selection"),
    ],
)
def test_annual_slice_selection_refuses_ambiguous_or_unknown_scope(
    requested_ids: tuple[str, ...],
    code: str,
) -> None:
    with pytest.raises(RetencionesInstalledCliError) as raised:
        select_annual_slices(build_installed_annual_cli_slices(), requested_ids=requested_ids)

    assert raised.value.stage == "annual_preflight"
    assert raised.value.diagnostic_code == code


def test_failure_receipt_keeps_redacted_command_evidence_and_artifact_roots(tmp_path: Path) -> None:
    """A failed installed command is actionable without retaining a raw payload or secret."""
    command = CommandEvidence(
        command="app modelo work create",
        returncode=2,
        status="error",
        notice_codes=(),
    )
    receipt = failure_evidence(
        error=RetencionesInstalledCliError(
            stage="professional-111-q2-partial-payments:work_create",
            diagnostic_code="REFUSED_MODELO_PROFILE_READINESS",
            commands=(command,),
        ),
        executable=tmp_path / "missing-aeat.exe",
        year=SUPPORTED_YEAR,
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


def test_synthetic_withholding_profile_explicitly_attests_not_a_colegio_concertado() -> None:
    """M111 readiness must not depend on a defaulted profile fact."""
    cli = _ProfileCli()

    create_withholding_profile(cast(InstalledCli, cli), year=SUPPORTED_YEAR)

    assert cli.created_year == SUPPORTED_YEAR
    assert "--no-colegio-concertado" in cli.calls[0]


def test_each_perceptor_filing_name_is_declared_once_under_its_own_tax_id() -> None:
    """A filing name is keyed by tax id, so two perceptors must not share one."""
    cli = _ProfileCli()
    captures = tuple(
        capture for slice_ in build_installed_annual_cli_slices(SUPPORTED_YEAR) for capture in slice_.captures
    )

    declare_perceptor_filing_names(cast(InstalledCli, cli), captures)

    assert PROFESSIONAL_NIF != LANDLORD_NIF
    assert sorted(cli.calls) == sorted(
        [
            (
                "app",
                "ledger",
                "counterparty",
                "filing-name",
                nif,
                "--kind",
                "entity",
                "--razon-social",
                name,
            )
            for nif, name in (
                (PROFESSIONAL_NIF, PROFESSIONAL_RAZON_SOCIAL),
                (LANDLORD_NIF, LANDLORD_RAZON_SOCIAL),
            )
        ]
    )


def test_perceptor_filing_names_refuse_two_names_for_one_tax_id() -> None:
    cli = _ProfileCli()
    first, second = build_installed_periodic_cli_slices(SUPPORTED_YEAR)
    clashing = replace(second, counterparty_nif=first.counterparty_nif)

    with pytest.raises(RetencionesInstalledCliError) as raised:
        declare_perceptor_filing_names(cast(InstalledCli, cli), (first, clashing))

    assert raised.value.diagnostic_code == "perceptor_name_conflict"
    assert cli.calls == []


def test_m190_no_activity_uses_the_public_profile_attestation_not_zero_filings() -> None:
    """The annual M190 chain labels and sends the supported no-duty evidence."""
    _rent, professional = build_installed_annual_cli_slices()
    cli = _ProfileCli()

    tokens = attest_annual_no_activity_periods(
        cli=cast(InstalledCli, cli),
        slice_=professional,
        captures_by_period={"2T": professional.captures},
        year=SUPPORTED_YEAR,
    )

    assert tokens == frozenset({f"{SUPPORTED_YEAR}:1T", f"{SUPPORTED_YEAR}:3T", f"{SUPPORTED_YEAR}:4T"})
    assert cli.calls == [
        (
            "config",
            "profile",
            "edit",
            f"income-{SUPPORTED_YEAR}",
            "--quiet",
            "--modelo-111-no-retenciones-periods",
            f"{SUPPORTED_YEAR}:1T,{SUPPORTED_YEAR}:3T,{SUPPORTED_YEAR}:4T",
        )
    ]


def test_m180_no_activity_uses_its_public_no_relevant_payment_attestation() -> None:
    """The annual M180 chain sends supported public zero-history evidence."""
    rent, _professional = build_installed_annual_cli_slices()
    cli = _ProfileCli()

    tokens = attest_annual_no_activity_periods(
        cli=cast(InstalledCli, cli),
        slice_=rent,
        captures_by_period={"1T": (rent.captures[0],), "2T": rent.captures[1:]},
        year=SUPPORTED_YEAR,
    )

    assert tokens == frozenset({f"{SUPPORTED_YEAR}:3T", f"{SUPPORTED_YEAR}:4T"})
    assert cli.calls == [
        (
            "config",
            "profile",
            "edit",
            f"income-{SUPPORTED_YEAR}",
            "--quiet",
            "--modelo-115-no-relevant-payment-periods",
            f"{SUPPORTED_YEAR}:3T,{SUPPORTED_YEAR}:4T",
        )
    ]


def test_m180_no_activity_refuses_without_the_public_attestation_before_work_creation() -> None:
    """An empty 115 quarter cannot materialize merely because it is zero-valued."""
    rent, _professional = build_installed_annual_cli_slices()
    cli = _ProfileCli()

    with pytest.raises(RetencionesInstalledCliError) as raised:
        materialize_annual_source_period(
            cli=cast(InstalledCli, cli),
            source_modelo=rent.source_modelo,
            source_revision=rent.captures[0].revision,
            source_period=rent.source_periods[2],
            captures=(),
            year=SUPPORTED_YEAR,
            no_activity_attestations=frozenset(),
        )

    assert raised.value.stage == "115:3T:annual_source:preflight"
    assert raised.value.diagnostic_code == "annual_source_m115_no_relevant_payment_attestation_missing"
    assert cli.calls == []


class _ProfileCli:
    """Minimal secure-runner double for profile command construction."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.created_year: int | None = None

    def create_profile(self, *, year: int) -> None:
        self.created_year = year

    def run(
        self,
        args: Sequence[str],
        *,
        authenticated: bool = True,
        allow_error: bool = False,
    ) -> dict[str, Any]:
        del authenticated, allow_error
        self.calls.append(tuple(args))
        return {"status": "success", "result": {}}
