"""Real CSV source entry into an amendable external Modelo baseline."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.application.modelo.filing_record_import_operation import (
    MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
)
from cadrumo.application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.revision_selection_operation import MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.revision_snapshot_operation import (
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
)
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.tests.cli_envelope import unwrap_cli_result

from ...tests import modelo_operation_test_support
from .native_api_cli_support import native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PERIOD = Period.from_year_and_code(2025, "1T")


def _external_import_scope(client_id: UUID) -> AccessScope:
    """Enroll the external import and exact-profile status and revision reads."""
    operations = (
        MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
        MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
        MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
    )
    return AccessScope(
        operations=frozenset(operations),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.COMMIT,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{operation_id}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    )
                    for operation_id in operations
                ),
            }
        ),
        periods=frozenset({_PERIOD}),
        allow_period_independent=False,
        allow_delegation=False,
    )


def test_filing_record_import_file_uses_real_csv_parser_and_persists_lexicals(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A real source file is parsed by the CLI and its lexicals reach storage."""

    def prepare_profile(profile_id: UUID, _root: Path) -> str:
        unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=authority_operation)
        return unit.work_unit_id

    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_external_import_scope,
        prepare_profile=prepare_profile,
    ) as session:
        source = tmp_path / "m130-filed.csv"
        source.write_text("casilla_code;value\n01; 001500.00 \n02;300,0\n", encoding="utf-8")
        result = session.invoke_credential_reference(
            "app",
            "modelo",
            "filing-record",
            "import",
            session.prepared,
            "--evidence-kind",
            "aeat_csv_register",
            "--evidence-id",
            "REALCSV23301",
            "--file",
            str(source),
        )
        assert result.exit_code == 0, result.output
        payload = unwrap_cli_result(result)

        revision_result = session.invoke_password(
            "app", "modelo", "work", "revision", payload["calculation_revision_id"]
        )
        assert revision_result.exit_code == 0, revision_result.output
        revision = unwrap_cli_result(revision_result)
        assert revision["input_values_by_casilla_id"] == {"01": " 001500.00 ", "02": "300,0"}
        assert payload["external_evidence"]["reference_id"] == "REALCSV23301"


def test_failed_csv_file_import_creates_no_filing_or_revision(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A partial source is refused and leaves the exact work unit unchanged."""

    def prepare_profile(profile_id: UUID, _root: Path) -> str:
        unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=authority_operation)
        return unit.work_unit_id

    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_external_import_scope,
        prepare_profile=prepare_profile,
    ) as session:
        partial = tmp_path / "partial.csv"
        partial.write_text("casilla_code;value\n01;1500\n", encoding="utf-8")
        refused = session.invoke_credential_reference(
            "app",
            "modelo",
            "filing-record",
            "import",
            session.prepared,
            "--evidence-kind",
            "aeat_csv_register",
            "--evidence-id",
            "PARTIALCSV113",
            "--file",
            str(partial),
        )
        assert refused.exit_code != 0

        filings = session.invoke_password("app", "modelo", "filing-record", "list")
        assert filings.exit_code == 0, filings.output
        assert unwrap_cli_result(filings)["record_count"] == 0

        status = session.invoke_credential_reference("app", "modelo", "work", "status", session.prepared)
        assert status.exit_code == 0, status.output
        status_payload = unwrap_cli_result(status)
        assert status_payload["current_calculation_revision_id"] is None
        assert status_payload["current_filing_record_id"] is None
