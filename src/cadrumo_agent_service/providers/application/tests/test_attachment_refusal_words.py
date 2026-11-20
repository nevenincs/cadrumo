"""The refusal that points at the profile setting words that setting as the profile does."""

from __future__ import annotations

from pathlib import Path
from typing import Final, cast

import pytest
import yaml

import cadrumo
import cadrumo_agent_service

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOCALES: Final = ("en", "es", "ca", "hu")
_CAPABILITY: Final = "cloud_evidence_upload"


def _find(node: object, name: str) -> object:
    if isinstance(node, dict):
        mapping = cast(dict[str, object], node)
        if name in mapping:
            return mapping[name]
        for child in mapping.values():
            found = _find(child, name)
            if found is not None:
                return found
    return None


def _profile_label(locale: str) -> str:
    path = Path(cadrumo.__file__).parent / "locales" / locale / "profile.yml"
    capability = _find(yaml.safe_load(path.read_text(encoding="utf-8")), _CAPABILITY)
    assert isinstance(capability, dict)
    label = cast(dict[str, object], capability)["label"]
    assert isinstance(label, str)
    return label


def _service_refusal(locale: str, code: str) -> str:
    path = Path(cadrumo_agent_service.__file__).parent / "locales" / f"{locale}.yml"
    value = _find(yaml.safe_load(path.read_text(encoding="utf-8")), "attachment_refusal")
    assert isinstance(value, dict)
    words = cast(dict[str, object], value)[code]
    assert isinstance(words, str)
    return words


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_profile_refusal_names_the_setting_by_the_profile_label(locale: str) -> None:
    assert _profile_label(locale) in _service_refusal(locale, "profile_not_eligible")


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_installation_refusal_offers_no_profile_setting(locale: str) -> None:
    assert _profile_label(locale) not in _service_refusal(locale, "cloud_upload_not_permitted")
