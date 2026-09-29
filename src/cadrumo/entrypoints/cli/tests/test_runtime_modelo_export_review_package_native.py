"""Native CLI export and review-package builds use the registered profile worker."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile

import pytest
from click.testing import Result

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.user_profile.login_session import resolve_login_target
from ....core.period import Period
from ....core.redaction.rules import CLI_BUCKET_ID_PLACEHOLDER
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import require_schema_envelope
from ...tests import modelo_operation_test_support
from ._runtime_profile_cli_fixture import native_cli_profile_scope
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_LABEL = "Native export-review operator"


def _invoke_with_human_password(*, fixture_passphrase: str, label: str, command: tuple[str, ...]) -> Result:
    """Run an installed CLI command through its protected password channel."""
    result = invoke_cached_cli(
        ("--format", "json", "--profile", label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": fixture_passphrase}),
    )
    if fixture_passphrase in result.output:
        pytest.fail("profile credential appeared in CLI output", pytrace=False)
    return result


def test_native_cli_export_and_review_package_publish_canonical_receipts(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Both side-effecting commands settle typed results through the real worker."""
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(
            label=_LABEL,
            facts={
                "taxpayer_type.entity_type": "natural_person",
                "identity.name": "Operator",
                "identity.surnames": "Export Review",
                "activities.description": "consulting",
                "censo.activity_start_date": "2025-01-01",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )
        bucket_id = resolve_login_target(_LABEL).bucket_id
        revision_id, report_id = modelo_operation_test_support.seeded_modelo_verification_report(
            UUID(bucket_id), operation=authority_operation
        )
        revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
        assert revision is not None
        assert revision.verified_at is not None
        assert report_id
        work_unit_id = revision.work_unit_id
        period = Period.from_year_and_code(2025, "1T")
        close_active_bucket_session()

        export_path = (tmp_path / "modelo-export.txt").resolve()
        exported = _invoke_with_human_password(
            fixture_passphrase=fixture.passphrase,
            label=_LABEL,
            command=("app", "modelo", "export", work_unit_id, "--output", str(export_path)),
        )
        assert exported.exit_code == 0, exported.output
        export_result = require_schema_envelope(exported.output)
        assert export_result["calculation_revision_id"] == revision_id
        assert export_result["work_unit_id"] == work_unit_id
        assert export_result["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
        assert export_result["filing_year"] == period.filing_year
        expected_period = {"filing_year": period.filing_year, "code": period.registry_token}
        assert export_result["period"] == expected_period
        assert Path(export_result["output_path"]) == export_path
        exported_bytes = export_path.read_bytes()
        assert len(exported_bytes) == export_result["byte_size"] > 0
        assert hashlib.sha256(exported_bytes).hexdigest() == export_result["file_sha256"]
        assert export_result["bucket_event_id"]

        package_path = (tmp_path / "modelo-review-package.zip").resolve()
        packaged = _invoke_with_human_password(
            fixture_passphrase=fixture.passphrase,
            label=_LABEL,
            command=(
                "app",
                "modelo",
                "review-package",
                "build",
                work_unit_id,
                "--output",
                str(package_path),
            ),
        )
        assert packaged.exit_code == 0, packaged.output
        package_result = require_schema_envelope(packaged.output)
        assert package_result["calculation_revision_id"] == revision_id
        assert package_result["work_unit_id"] == work_unit_id
        assert package_result["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
        assert package_result["filing_year"] == period.filing_year
        assert package_result["period"] == expected_period
        assert Path(package_result["output_path"]) == package_path
        assert package_result["member_count"] >= 1
        assert package_result["built_by"]
        assert package_result["built_at"]
        with ZipFile(package_path) as archive:
            assert archive.testzip() is None
            assert archive.namelist()
