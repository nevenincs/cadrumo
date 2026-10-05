"""Bounded requests and limits for profile-owned verification report reads."""

from __future__ import annotations

from uuid import UUID

from ...core.identity.hex_ids import CalculationRevisionId, VerificationReportId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.models import CredentialFreeOperationRequest
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES

MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID = "modelo.verification_report.list"


MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID = "modelo.verification_report.view"


MAX_MODELO_VERIFICATION_REPORT_LIST_ROWS = 4_096


MAX_MODELO_VERIFICATION_REPORT_FINDINGS = 2_048


MAX_MODELO_VERIFICATION_REPORT_CASILLAS = 32_768


MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS = 512


MAX_MODELO_VERIFICATION_REPORT_FACTS = 64


VERIFICATION_REPORT_RESULT_DOCUMENT_MAX_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096


class ModeloVerificationReportListRequest(CredentialFreeOperationRequest):
    """Select a profile's verification history or one calculation revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    calculation_revision_id: CalculationRevisionId | None = None


class ModeloVerificationReportViewRequest(CredentialFreeOperationRequest):
    """Select one persisted verification report in the authenticated profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    verification_report_id: VerificationReportId
