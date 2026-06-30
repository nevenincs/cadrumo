"""Site-unavailable workflow engine coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.outbound.aeat.browser._site_health import SiteHealthState
from ....adapters.outbound.aeat.browser._site_health_parsers import evaluate_response
from ....core.errors import SiteHealthError
from ....tests import FIXTURES_DIR
from .. import WorkflowAbortReason, WorkflowStage
from .._models import compute_run_id
from ._engine_support import _SEDE_ROOT_URL, _fixtures, _run_next

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestSiteUnavailableArm:
    """The typed ``SiteHealthError`` arm must fire before ``Exception``."""

    def test_site_unavailable_from_deadline_engine(self) -> None:
        fixture_path = FIXTURES_DIR / "site_health" / "mantenimiento" / "interstitial.html"
        body = Path(fixture_path).read_text(encoding="utf-8")
        real_status = evaluate_response(
            _SEDE_ROOT_URL,
            200,
            {},
            body,
            rate_limit_retry_after_default=300,
        )
        assert real_status is not None
        assert real_status.state is SiteHealthState.MANTENIMIENTO

        fx = _fixtures()
        fx.deadline_engine.raise_exc = SiteHealthError(status=real_status)
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
        assert result.final_stage is WorkflowStage.ABORTED
        last = result.steps[-1]
        assert last.stage is WorkflowStage.COMPUTING_DEADLINES
        assert last.site_health_alert is not None
        assert last.site_health_alert.status.state is SiteHealthState.MANTENIMIENTO
        assert last.site_health_alert.run_id == result.run_id

    def test_site_unavailable_after_obligation_resolved_matches_run_id(self) -> None:
        fixture_path = FIXTURES_DIR / "site_health" / "mantenimiento" / "interstitial.html"
        body = Path(fixture_path).read_text(encoding="utf-8")
        real_status = evaluate_response(
            _SEDE_ROOT_URL,
            200,
            {},
            body,
            rate_limit_retry_after_default=300,
        )
        assert real_status is not None

        fx = _fixtures()
        fx.inputs_provider.raise_exc = SiteHealthError(status=real_status)
        result = _run_next(fx)
        assert result.aborted_reason is WorkflowAbortReason.SITE_UNAVAILABLE
        last = result.steps[-1]
        assert last.stage is WorkflowStage.BUILDING_DRAFT
        assert last.site_health_alert is not None
        assert last.site_health_alert.run_id == result.run_id
        assert result.obligation is not None

        placeholder_hash = compute_run_id(
            tax_id=fx.profile.tax_id,
            modelo="-",
            period=None,
            started_at=result.started_at,
        )
        assert last.site_health_alert.run_id != placeholder_hash
