"""Real refusal-boundary coverage for ``aeat app modelo work amend-wizard``."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....application.user_profile import profile_storage_session
from ....core import Period, resolve_active_bucket_id
from ....domain.justificante import Justificante
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401
from ._modelo_work_ux_support import _create_m130_work_unit

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TAX_ID = "12345678Z"


def _invoke(args: list[str]):
    return invoke_cached_cli(args)


def _create_profile() -> None:
    result = _invoke(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--irpf-income-categories",
            "actividad_economica",
            "--tax-id",
            _TAX_ID,
            "--name",
            "Operator",
            "--surnames",
            "Amend",
            "--activity",
            "design",
        ],
    )
    assert result.exit_code == 0, result.output


def _seed_justificante(*, csv: str) -> None:
    body = f"{csv}-pdf".encode()
    receipt = Justificante(
        csv=csv,
        modelo="130",
        period=Period.from_year_and_code(2025, "1T"),
        ejercicio="2025",
        presentation_id=None,
        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
        tax_id=_TAX_ID,
        total_a_ingresar=None,
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
        source_pdf_sha256=hashlib.sha256(body).hexdigest(),
        parsed_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
    )
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    with profile_storage_session(bucket_id):
        JustificanteRepository(bucket_id=bucket_id).save(receipt)


def _import_external_baseline(work_unit_id: str) -> None:
    csv = "JUST-2025-130-1T-AMEND-WIZARD"
    _seed_justificante(csv=csv)
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "filing-record",
            "import",
            work_unit_id,
            "--evidence-kind",
            "aeat_justificante_pdf",
            "--evidence-id",
            csv,
            "--set",
            f"01={Decimal('1000.00')}",
            "--set",
            f"02={Decimal('250.00')}",
        ],
    )
    assert result.exit_code == 0, result.output


def test_amend_wizard_refuses_without_evidence_baseline() -> None:
    """A local work unit cannot enter the external-filing amendment path."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()

    result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_amend_wizard_non_interactive_host_refuses_with_instructive_message() -> None:
    """A real non-TTY invocation refuses before attempting an interactive prompt."""
    _create_profile()
    work_unit_id = _create_m130_work_unit()
    _import_external_baseline(work_unit_id)

    result = _invoke(["--format", "json", "app", "modelo", "work", "amend-wizard", work_unit_id])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "interactive" in result.output.lower() or "console" in result.output.lower()
