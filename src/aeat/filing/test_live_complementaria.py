"""Opt-in live-marked tests for the amendment dry-run path.

The complementaria issue explicitly forbids mutating remote AEAT state
as part of automated tests. This module therefore exercises only the
dry-run/read-only amendment submission path and still requires the
standard live opt-in gate.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from aeat.cli._live import requires_live_enabled
from aeat.cli.submission._helpers import build_engine
from aeat.config import Settings
from aeat.filing import AmendmentKind, CasillaChange, FilingAmendment, build_draft
from aeat.filing.testing import SyntheticProfile, default_schema_provider

pytestmark = pytest.mark.live


def test_live_complementaria_dry_run_only(tmp_path) -> None:
    requires_live_enabled()

    amended_draft = build_draft(
        modelo="130",
        period="2024Q1",
        profile=SyntheticProfile(
            tax_id="00000000T",
            display_name="Live dry-run amendment",
            applicable_modelos=("130",),
        ),
        inputs={"01": 13000, "02": 3500, "05": 400, "06": 0},
        schema_provider=default_schema_provider(),
    )
    amendment = FilingAmendment(
        amendment_id="live-amendment",
        submission_id="live-submission",
        original_csv="CSV-LIVE-ORIGINAL",
        original_model="130",
        original_period="2024Q1",
        amendment_kind=AmendmentKind.COMPLEMENTARIA,
        delta=(
            CasillaChange(
                casilla_code="01",
                old_value=None,
                new_value=Decimal("13000"),
                reason="Dry-run-only live safety test.",
            ),
        ),
        amended_draft=amended_draft,
        created_at=datetime.now(UTC),
    )
    engine = build_engine(
        Settings(
            aeat_submissions_dir=tmp_path / "submissions",
            aeat_submission_browser_trace_dir=tmp_path / "traces",
        )
    )
    result = asyncio.run(engine.submit_amendment(amendment, dry_run=True))
    assert result.dry_run is True
    assert result.filing.status.value == "PENDING"
