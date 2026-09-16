"""Real encrypted-store validation for certificate-session resume."""

from __future__ import annotations

import pytest

from .. import session_store as session_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
