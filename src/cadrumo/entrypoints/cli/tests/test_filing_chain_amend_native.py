"""Native API-key admission for an amendment over a synthetic filing chain."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.profile.tests.cross_period_seeding import SEEDED_SOURCE_TAX_ID
from ....application.modelo.external_import_actions import import_external_filing_evidence
from ....application.modelo.filing_selection_operation import MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID
from ....application.modelo.operation_definitions import MODELO_WORK_AMEND_OPERATION_DEFINITION_ID
from ....application.modelo.revision_selection_operation import MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
from ....application.modelo.revision_snapshot_operation import MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.filing_record import ExternalEvidenceKind
from ....tests.cli_envelope import unwrap_cli_result
from ...adapter_composition import build_calculation_action_ports
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
_BASELINE_INCOME = Decimal("1000.00")
_CORRECTED_INCOME = Decimal("1100.00")


def _amend_scope(client_id: UUID) -> AccessScope:
    """Enroll only the exact period's filing selection and amend operations."""
    return AccessScope(
        operations=frozenset(
            {
                MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID,
                MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
                MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
                MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
            }
        ),
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
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{MODELO_WORK_AMEND_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{MODELO_WORK_REVISION_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
            }
        ),
        periods=frozenset({_PERIOD}),
        allow_period_independent=False,
        allow_delegation=False,
    )


def test_native_api_key_amends_synthetic_confirmed_filing_chain(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The exact-profile worker amends persisted evidence without provider access."""

    def prepare_profile(profile_id: UUID, _root: Path) -> tuple[str, str]:
        unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=authority_operation)
        ports = build_calculation_action_ports(bucket_id=str(profile_id), operation=authority_operation)
        baseline = import_external_filing_evidence(
            work_unit_id=unit.work_unit_id,
            casilla_values={
                validated_casilla_id("01", surface="native amend synthetic baseline"): _BASELINE_INCOME,
                validated_casilla_id("02", surface="native amend synthetic baseline"): Decimal("250.00"),
            },
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id="SYNTHETIC-NATIVE-AMEND-M130-2025-1T",
            expected_tax_id=SEEDED_SOURCE_TAX_ID,
            work_unit_repository=ports.work_unit_repository,
            calculation_repository=ports.calculation_repository,
            filing_repository=ports.filing_repository,
            bucket_event_repository=ports.bucket_event_repository,
            observation_repository=ports.observation_repository,
            operation=authority_operation,
        )
        return unit.work_unit_id, baseline.filing_record.filing_record_id

    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_amend_scope,
        prepare_profile=prepare_profile,
    ) as session:
        work_unit_id, baseline_filing_record_id = session.prepared
        result = session.invoke_credential_reference(
            "app",
            "modelo",
            "work",
            "amend",
            "--from-filing-record",
            baseline_filing_record_id,
            "--kind",
            "complementaria",
            "--reason",
            "under-reported turnover",
            "--set",
            "01=1100.00",
        )
        assert result.exit_code == 0, result.output
        amendment = unwrap_cli_result(result)

        assert amendment["work_unit_id"] == work_unit_id
        assert amendment["amendment_kind"] == "complementaria"
        assert amendment["status"] == "vigente"
        assert amendment["origin"] == "local"
        assert amendment["confirmation"] == "pendiente"
        assert amendment["external_evidence"] is None
        assert amendment["live_submission"] is False
        assert amendment["amends_filing_record_id"] == baseline_filing_record_id

        listed = session.invoke_password("app", "modelo", "filing-record", "list", "--include-superseded")
        assert listed.exit_code == 0, listed.output
        records = unwrap_cli_result(listed)["records"]
        baseline_record = next(record for record in records if record["filing_record_id"] == baseline_filing_record_id)
        amended_record = next(
            record for record in records if record["filing_record_id"] == amendment["filing_record_id"]
        )
        assert baseline_record["status"] == "supersedido"
        assert baseline_record["confirmation"] == "confirmada"
        assert baseline_record["superseded_by_filing_record_id"] == amended_record["filing_record_id"]
        assert amended_record["status"] == "vigente"
        assert amended_record["amends_filing_record_id"] == baseline_filing_record_id

        revision_result = session.invoke_password(
            "app", "modelo", "work", "revision", amendment["calculation_revision_id"]
        )
        assert revision_result.exit_code == 0, revision_result.output
        revision = unwrap_cli_result(revision_result)
        assert Decimal(revision["casilla_values"]["01"]) == _CORRECTED_INCOME
