"""Tests for the cloud-upload consent gate governing off-host evidence reads.

On-host reading is always the default; this gate governs only the cloud
exception. It must be off by default, re-affirmed per invocation, and barred
absolutely in gestor deployments (sensitive-financial-data-secure-storage-only).
"""

from __future__ import annotations

import pytest

from ....core.config import Settings
from .._evidence_input import cloud_evidence_read_permitted

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_default_posture_refuses_cloud_even_when_acknowledged() -> None:
    settings = Settings()
    assert settings.aeat_evidence_cloud_upload_permitted is False
    assert settings.aeat_evidence_gestor_mode is False
    assert cloud_evidence_read_permitted(settings, acknowledged=True) is False


def test_permitted_deployment_still_requires_per_invocation_acknowledgement() -> None:
    settings = Settings(aeat_evidence_cloud_upload_permitted=True, aeat_evidence_gestor_mode=False)
    # Not acknowledged this invocation -> refused (no sticky enable).
    assert cloud_evidence_read_permitted(settings, acknowledged=False) is False
    # Acknowledged this invocation -> permitted.
    assert cloud_evidence_read_permitted(settings, acknowledged=True) is True


def test_gestor_mode_bars_cloud_absolutely() -> None:
    settings = Settings(aeat_evidence_cloud_upload_permitted=True, aeat_evidence_gestor_mode=True)
    # Gestor mode overrides both the deployment permit and per-invocation consent.
    assert cloud_evidence_read_permitted(settings, acknowledged=True) is False
