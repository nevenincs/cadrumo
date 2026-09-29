"""Language fallback diagnostics must not serialize private storage errors."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from .. import language_resolver

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PRIVATE_SENTINEL = "private-profile-value-and-password"
_LOGGER = "cadrumo.application.user_profile.language_resolver"


class _CorruptPrivateRecordError(Exception):
    """A storage failure whose exception text must not enter a diagnostic."""


def _fail_with_private_message(*_args: object, **_kwargs: object) -> None:
    raise _CorruptPrivateRecordError(f"raw SQL and {_PRIVATE_SENTINEL}")


def _safe_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    records = [record for record in caplog.records if record.name == _LOGGER]
    assert records
    assert all(record.exc_info is None for record in records)
    assert all(_PRIVATE_SENTINEL not in record.getMessage() for record in records)
    assert all("raw SQL" not in record.getMessage() for record in records)
    return records


def test_failed_profile_language_read_keeps_fallback_and_only_logs_error_class(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(language_resolver, "active_profile_output_language_from_storage", _fail_with_private_message)
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            assert language_resolver.refresh_active_profile_output_language() is None

    records = _safe_records(caplog)
    assert any("using settings" in record.getMessage() for record in records)
    assert any("error_type=_CorruptPrivateRecordError" in record.getMessage() for record in records)
    language_resolver.refresh_active_profile_output_language()


def test_failed_language_hint_mirror_only_logs_error_class(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(language_resolver, "write_profile_output_language_hint", _fail_with_private_message)
    with (
        override_settings(cadrumo_local_storage_root=tmp_path),
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
    ):
        language_resolver.mirror_profile_output_language_hint("a" * 32, OutputLanguage.CA)

    records = _safe_records(caplog)
    assert any("could not mirror" in record.getMessage() for record in records)
    assert any("error_type=_CorruptPrivateRecordError" in record.getMessage() for record in records)
