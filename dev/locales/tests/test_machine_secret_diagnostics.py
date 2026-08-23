"""Semantic contract for the four localized machine-secret diagnostics."""

from __future__ import annotations

import pytest

from .._paths import LOCALES_DIR, SRC_DIR
from ..manager import LocaleManager, locale_catalogue_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")
_ERRORS_PREFIX = "cli.config.custody.errors"
_ACCEPTED_FD_ZERO_COPY = {
    "en": "use descriptor 0",
    "es": "use el descriptor 0",
    "ca": "useu el descriptor 0",
    "hu": "használja a 0-s",
}


def _catalogue(locale: str) -> dict[str, object]:
    source = locale_catalogue_source(LOCALES_DIR, locale)
    assert source is not None
    payload = LocaleManager(src_dir=SRC_DIR, locales_dir=LOCALES_DIR).load_locale(source)
    inner = payload.get(locale, payload)
    assert isinstance(inner, dict)
    return inner


def _leaf(catalogue: dict[str, object], key: str) -> str:
    node: object = catalogue
    for segment in key.split("."):
        assert isinstance(node, dict)
        node = node[segment]
    assert isinstance(node, str)
    return node


@pytest.mark.parametrize("locale", _LOCALES)
def test_machine_secret_guidance_names_both_explicit_channels_without_environment_fallback(locale: str) -> None:
    catalogue = _catalogue(locale)
    guidance_keys = (
        f"{_ERRORS_PREFIX}.echo_suppression_unavailable",
        f"{_ERRORS_PREFIX}.non_interactive_secret_required",
        "cli.config.login.passphrase_channel_absent",
        "cli.config.profile.create_passphrase_channel_absent",
    )
    for key in guidance_keys:
        copy = _leaf(catalogue, key)
        assert "--secrets-stdin" in copy
        assert "--secrets-fd" in copy
        assert "CADRUMO_SECRET_PASSPHRASE" not in copy


@pytest.mark.parametrize("locale", _LOCALES)
def test_machine_secret_descriptor_copy_accepts_fd_zero_and_reserves_only_output_streams(locale: str) -> None:
    copy = _leaf(_catalogue(locale), f"{_ERRORS_PREFIX}.secrets_fd_reserved_stream")
    assert _ACCEPTED_FD_ZERO_COPY[locale] in copy.casefold()
    assert "1" in copy
    assert "2" in copy


@pytest.mark.parametrize("locale", _LOCALES)
def test_malformed_missing_and_oversize_copy_is_channel_neutral(locale: str) -> None:
    catalogue = _catalogue(locale)
    for suffix in ("invalid_json", "missing_fields", "too_large"):
        fd_copy = _leaf(catalogue, f"{_ERRORS_PREFIX}.secrets_fd_{suffix}")
        stdin_copy = _leaf(catalogue, f"{_ERRORS_PREFIX}.secrets_stdin_{suffix}")
        assert fd_copy == stdin_copy
        assert "--secrets-fd" not in fd_copy
        assert "--secrets-stdin" not in fd_copy

