"""Real encrypted-store validation for certificate-session resume."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from ......adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ......application.auth_credentials import unnamed_certificate_credentials
from ......core.config import Settings
from ......core.errors.hierarchy import AeatLoginAssertionError
from .. import session_store as session_store
from ..authenticator import AeatAuthenticator
from ..authenticator_persistence import PersistedSessionMetadata
from ..certificate import extract_nif_from_subject
from ._auth_fixtures import CERTIFICATE_INPUT
from ._authenticator_support import _build_bundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


