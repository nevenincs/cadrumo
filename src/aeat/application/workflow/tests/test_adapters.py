"""Tests for workflow concrete adapter boundaries."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....core import Period
from ....domain.deadlines import IVARegime, Schedule, TaxpayerProfile
from ....domain.filing import ModeloInputs
from .. import default_engine
from .._errors import WorkflowError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


class _DeadlineEngine:
    def compute(self, profile: TaxpayerProfile, year: int, *, today: date | None = None) -> Schedule:
        del year, today
        return Schedule(
            profile=profile,
            year=2026,
            obligations=(),
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


class _DraftBuilder:
    def build(
        self,
        *,
        modelo: str,
        period: Period,
        profile: TaxpayerProfile,
        inputs: ModeloInputs,
        fail_on_warning: bool = False,
    ):
        del modelo, period, profile, inputs, fail_on_warning
        raise AssertionError("draft builder should not run while constructing default_engine")


class _SubmissionEngine:
    def preflight(
        self,
        draft: object,
        *,
        today: date,
        skip_deadline_window: bool = False,
    ) -> None:
        del draft, today, skip_deadline_window


def test_default_engine_requires_bucket_backed_inputs_provider() -> None:
    with pytest.raises(WorkflowError):
        default_engine(
            submission_engine=_SubmissionEngine(),
            deadline_engine=_DeadlineEngine(),
            filing_draft_builder=_DraftBuilder(),
            inputs_provider=None,
        )
