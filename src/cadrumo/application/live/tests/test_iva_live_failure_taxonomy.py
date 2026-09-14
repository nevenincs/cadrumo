"""Application taxonomy for live IVA acquisition failures."""

from __future__ import annotations

import pytest

from ..errors import (
    LiveIvaAcquisitionFailureMode,
    classify_live_iva_acquisition_failure,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _InwardFailureError(Exception):
    """Application-test fake implementing the inward live-failure contract."""

    def __init__(self, mode: LiveIvaAcquisitionFailureMode) -> None:
        """Retain the application-owned mode that an adapter would expose."""
        super().__init__()
        self._mode = mode

    @property
    def live_iva_failure_mode(self) -> LiveIvaAcquisitionFailureMode:
        """Expose the inward protocol property used by the application."""
        return self._mode


@pytest.mark.parametrize(
    "mode",
    tuple(mode for mode in LiveIvaAcquisitionFailureMode if mode is not LiveIvaAcquisitionFailureMode.AUTHENTICATED),
)
def test_application_classifier_consumes_the_inward_failure_contract(
    mode: LiveIvaAcquisitionFailureMode,
) -> None:
    """The application consumes a mode, without knowing its adapter producer."""
    assert classify_live_iva_acquisition_failure(_InwardFailureError(mode)) is mode


def test_unclassified_failure_stays_unknown() -> None:
    """Failures that do not implement the contract stay explicitly unknown."""
    assert (
        classify_live_iva_acquisition_failure(RuntimeError("not classified")) is LiveIvaAcquisitionFailureMode.UNKNOWN
    )
