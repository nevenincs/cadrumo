"""Cross-owner and structural canonical-home controls."""

from __future__ import annotations

import importlib.util
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_auth_provider_contract_has_one_public_home() -> None:
    from .. import core
    from ..adapters.outbound.aeat import auth as adapter_auth
    from ..application.auth.providers import AuthProvider
    from ..core import config

    assert core.AuthProviderKind.__module__ == "cadrumo.core._auth_provider"
    assert core.AuthProviderDescription.__module__ == "cadrumo.core._auth_provider"
    assert not hasattr(core, "AuthProviderKindSetting")
    assert not hasattr(config, "AuthProviderKind")
    assert not hasattr(config, "AuthProviderKindSetting")
    assert AuthProvider.__module__ == "cadrumo.application.auth.providers"
    assert not hasattr(adapter_auth, "AuthProviderKind")
    assert not hasattr(adapter_auth, "AuthProviderDescription")


def test_setup_answers_module_not_importable() -> None:
    sys.modules.pop("cadrumo.application.wizard._setup_answers", None)

    spec = importlib.util.find_spec("cadrumo.application.wizard._setup_answers")

    assert spec is None


def test_counterpart_source_kind_application_imports_from_domain() -> None:
    from ..application.aggregation import CounterpartSourceKind as app_csk
    from ..domain.calculations.registry import CounterpartSourceKind as domain_csk

    assert app_csk is domain_csk
