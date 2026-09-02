"""Cross-owner and structural canonical-home controls."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_auth_provider_contract_has_one_public_home() -> None:
    from .. import core
    from ..adapters.outbound.aeat import auth as adapter_auth
    from ..application.auth.providers import AuthProvider
    from ..core import config
    from ..core.auth_provider import AuthProviderDescription, AuthProviderKind

    assert AuthProviderKind.__module__ == "cadrumo.core.auth_provider"
    assert AuthProviderDescription.__module__ == "cadrumo.core.auth_provider"
    assert not hasattr(core, "AuthProviderKindSetting")
    assert not hasattr(config, "AuthProviderKind")
    assert not hasattr(config, "AuthProviderKindSetting")
    assert AuthProvider.__module__ == "cadrumo.application.auth.providers"
    assert not hasattr(adapter_auth, "AuthProviderKind")
    assert not hasattr(adapter_auth, "AuthProviderDescription")


def test_setup_answers_has_one_core_home() -> None:
    from ..core.setup_answers import SetupAnswers

    assert SetupAnswers.__module__ == "cadrumo.core.setup_answers"


def test_counterpart_source_kind_application_imports_from_domain() -> None:
    from ..application.aggregation import CounterpartSourceKind as app_csk
    from ..core.aggregation import CounterpartSourceKind as domain_csk

    assert app_csk is domain_csk
