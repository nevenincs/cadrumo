"""Temporal and deadline ownership proofs for Modelo 182."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import resources
from .._errors import NoRevisionForPeriodError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_182_deadline_is_owned_only_by_the_evidenced_2025_revision() -> None:
    authority = resources().modelos.authority
    modelo = authority.modelo("182")
    revision = modelo.revisions["2025"]
    assert (revision.valid_from, revision.valid_to) == (date(2025, 1, 1), date(2025, 12, 31))
    assert revision.period_selector.years == (2025,)
    assert tuple(window.id for window in revision.deadline_windows) == ("modelo-182-2025-0a",)
    window = revision.deadline_windows[0]
    assert (window.filing_year, window.period.registry_token) == (2025, "0A")
    snapshot = authority.snapshot(
        "182", filing_year=2025, period="0A", grade=revision.effective_authority_grade
    )
    assert snapshot.revision.id == "2025"
    assert tuple(item[2].id for item in authority.deadline_windows(2025, modelos=("182",))) == (window.id,)


def test_modelo_182_refuses_unsupported_design_eras_and_projects_no_deadline() -> None:
    authority = resources().modelos.authority
    for filing_year in (*range(2018, 2025), 2026):
        with pytest.raises(NoRevisionForPeriodError):
            authority.snapshot("182", filing_year=filing_year, period="0A")
        assert authority.deadline_windows(filing_year, modelos=("182",)) == ()
