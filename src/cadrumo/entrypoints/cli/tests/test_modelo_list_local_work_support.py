"""Modelo list local-work support surface tests."""

from __future__ import annotations

import pytest

from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_envelope import unwrap_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _modelo_row(payload: dict[str, object], code: str) -> dict[str, object]:
    rows = payload["modelos"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        # ``isinstance(row, dict)`` only proves *some* dict, not that its keys
        # are ``str`` — this data is always parsed JSON envelope output, so
        # re-keying with ``str(k)`` gives an honestly-typed ``dict[str, object]``.
        typed_row = STR_KEYED_MAPPING_ADAPTER.validate_python(row)
        if typed_row.get("code") == code:
            return typed_row
    raise AssertionError(f"modelo {code!r} was not listed in payload: {payload!r}")


def test_modelo_list_marks_m210_as_visible_but_not_local_work_supported() -> None:
    text_result = invoke_cached_cli(["--language", "en", "app", "modelo", "list", "--year", "2025"])
    assert text_result.exit_code == 0, text_result.output
    assert "local_work" in text_result.output
    assert "210\t" in text_result.output
    assert "unsupported-local-work" in text_result.output
    assert "G320" in text_result.output

    json_result = invoke_cached_cli(["--format", "json", "app", "modelo", "list", "--year", "2025"])
    assert json_result.exit_code == 0, json_result.output
    payload = unwrap_schema_envelope(json_result.output)

    m210 = _modelo_row(payload, "210")
    assert m210["local_work_supported"] is False
    assert m210["local_work_status"] == "unsupported-local-work"
    assert "G320" in str(m210["local_work_guidance"])

    m303 = _modelo_row(payload, "303")
    assert m303["local_work_supported"] is True
    assert m303["local_work_status"] == "supported-model-level"
    assert m303["local_work_guidance"] is None


def test_modelo_list_distinguishes_model_level_support_from_revision_scope() -> None:
    unscoped_result = invoke_cached_cli(["--format", "json", "app", "modelo", "list"])
    assert unscoped_result.exit_code == 0, unscoped_result.output
    unscoped = unwrap_schema_envelope(unscoped_result.output)
    m100 = _modelo_row(unscoped, "100")
    assert m100["local_work_supported"] is True
    assert m100["local_work_status"] == "supported-model-level"

    scoped_result = invoke_cached_cli(["--format", "json", "app", "modelo", "list", "--year", "2026"])
    assert scoped_result.exit_code == 0, scoped_result.output
    scoped = unwrap_schema_envelope(scoped_result.output)
    codes = {row["code"] for row in scoped["modelos"]}
    assert "100" not in codes
