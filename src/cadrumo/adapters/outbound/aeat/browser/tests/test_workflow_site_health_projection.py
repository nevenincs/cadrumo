"""Boundary tests for projecting browser site-health records into workflow facts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ......application.workflow.run_models import SiteHealthAlert, WorkflowSiteHealthFacts, WorkflowStage
from ......core.errors.hierarchy import SiteHealthState
from ......tests.aeat_literal_fixtures import aeat_url
from ..site_health_records import SiteHealthEvidence, SiteHealthStatus, parse_site_health_url

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SITE_HEALTH_OBSERVED_AT = datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC)


class TestSiteHealthAlert:
    """Validation invariants at the browser-to-workflow site-health boundary."""

    def _status(self) -> SiteHealthStatus:
        evidence = SiteHealthEvidence(
            url=parse_site_health_url(aeat_url("sede", "/")),
            http_status=503,
            html_fragment="<html>servicio temporalmente no disponible</html>",
            detected_markers=("servicio temporalmente no disponible",),
        )
        return SiteHealthStatus(
            state=SiteHealthState.MANTENIMIENTO,
            evidence=evidence,
            observed_at=_SITE_HEALTH_OBSERVED_AT,
        )

    def test_alert_composes_stage_and_status(self) -> None:
        status = self._status()
        alert = SiteHealthAlert(
            stage=WorkflowStage.BUILDING_DRAFT,
            status=WorkflowSiteHealthFacts.from_status(status),
            run_id="run-1234",
        )
        assert alert.stage is WorkflowStage.BUILDING_DRAFT
        assert alert.status.state is SiteHealthState.MANTENIMIENTO
        assert alert.status.alert_code == "workflow.site.mantenimiento"
        assert alert.status.http_status == 503
        assert alert.status.detected_marker_count == 1
        persisted = alert.model_dump_json()
        assert status.evidence.html_fragment not in persisted
        assert str(status.evidence.url) not in persisted
        assert status.evidence.detected_markers[0] not in persisted

    def test_workflow_projection_rejects_adapter_evidence_shape(self) -> None:
        """Raw adapter evidence cannot cross the strict workflow boundary."""
        with pytest.raises(ValidationError):
            WorkflowSiteHealthFacts.model_validate(self._status().model_dump())

    def test_alert_rejects_empty_run_id(self) -> None:
        with pytest.raises(ValidationError, match=r"at least 1 character"):
            SiteHealthAlert(
                stage=WorkflowStage.BUILDING_DRAFT,
                status=WorkflowSiteHealthFacts.from_status(self._status()),
                run_id="",
            )
