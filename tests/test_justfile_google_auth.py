"""Contract checks for the Google auth wrapper recipes in ``justfile``."""

from __future__ import annotations

import pytest

from aeat.core.config import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


def test_gsuite_bootstrap_sa_persists_service_account_path_selection() -> None:
    justfile = (PROJECT_ROOT / "justfile").read_text(encoding="utf-8")

    assert "gsuite-bootstrap-sa:" in justfile
    assert "GOOGLE_AUTH_PATH': 'service-account-automation'" in justfile
    assert "GOOGLE_APPLICATION_CREDENTIALS': 'env/sa.json'" in justfile
