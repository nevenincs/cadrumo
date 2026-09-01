"""Cross-owner error typing contracts."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_financial_validation_error_typing_and_registry() -> None:
    from ..adapters.inbound.financial.providers.base import FinancialValidationError
    from ..core.errors.error_codes import ERROR_REGISTRY, get_registered_error_code
    from ..core.errors.hierarchy import CadrumoError

    assert not issubclass(FinancialValidationError, ValueError)
    assert issubclass(FinancialValidationError, CadrumoError)
    assert get_registered_error_code(FinancialValidationError("test")).code in ERROR_REGISTRY


def test_censo_sync_error_typing() -> None:
    from ..application.user_profile.censo_errors import CensoSyncError
    from ..core.errors.hierarchy import CadrumoError

    assert issubclass(CensoSyncError, CadrumoError)
    assert not issubclass(CensoSyncError, ValueError)
